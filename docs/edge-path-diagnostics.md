# Edge path diagnostics — capturing and publishing `diagnose_edge_path.sh`

`scripts/diagnose_edge_path.sh` isolates which hop of the `chat.ics24.ir → :13000`
chain is broken: public DNS, internal DNS, edge IP ownership, routes, host bind,
Docker publish, loopback app, edge reachability, TLS/SNI, and host firewall.

The script is **read-only by default** — it prints to the terminal, creates no
files, pushes nothing, and exits `0`/`1`. Publishing is opt-in.

---

## 1. Modes

| Mode | Command | What it does |
|---|---|---|
| Read-only (default) | `bash scripts/diagnose_edge_path.sh` | Prints the per-hop verdict. Creates no files, no repo, no push. |
| Report | `--report` | Captures every probe into a run directory on disk. No push. |
| Push | `--push` | Implies `--report`, then publishes the run to `Work_RAG_HealthCheck`. |

Existing flags (`--edge-ip`, `--edge-host`, `--port`, `--dns`) are unchanged, so
current callers keep working with no edits.

### Flags

| Flag | Meaning |
|---|---|
| `--edge-ip IP` | Edge address DNS points at (default `10.10.34.36`) |
| `--edge-host NAME` | Public hostname (default `chat.ics24.ir`) |
| `--port N` | App port on the host (default `13000`) |
| `--dns IP` | Internal resolver to query (default: system resolver) |
| `--report` | Write a full run directory; do not push |
| `--push` | Implies `--report`, then publish |
| `--out-dir DIR` | Override the run directory (see below) |
| `--run-id ID` | Reuse an explicit run id instead of `<UTCSTAMP>-<host>` |
| `--no-push` | Explicit override; collects on disk and publishes nothing |
| `--redact-only DIR` | Sanitize `DIR` in place and exit (used by the secret self-test) |

Default run directory:

```
$DANA_STATE_DIR/dana-edge-diag/<RUN_ID>     # when DANA_STATE_DIR is set
${TMPDIR:-/tmp}/dana-edge-diag/<RUN_ID>     # otherwise
```

`<RUN_ID>` is `YYYYMMDDTHHMMSSZ-<short-hostname>`, the same shape the nightly
health report uses, so both run types sort together.

---

## 2. Diagnose and publish on the GPU server

```bash
cd /workspace/Work_Credit-RAG_Phase1
git fetch origin && git checkout <branch-with-this-script>

# 1) look first, change nothing
bash scripts/diagnose_edge_path.sh --port 13000

# 2) capture the evidence on disk
bash scripts/diagnose_edge_path.sh --report --port 13000

# 3) capture and publish so it is readable from a laptop
sudo bash scripts/diagnose_edge_path.sh --push --port 13000
```

`sudo` is not required, but without it hop 5 cannot name the owning process, hop
6 may not reach the Docker daemon, and hop 10 cannot read `iptables`/`pf`. Those
hops report `SKIP` with a `tool_missing=` or `permission` line rather than
silently passing.

### Read the result

- Dashboard (all runs, all machines): <https://alinikkhah2001.github.io/Work_RAG_HealthCheck/>
- This run's report: `logs/<RUN_ID>/REPORT.md`
- Newest report (stable URL): `latest/REPORT.md`
- Per-run record: `runs/<RUN_ID>.json`

The ten hops appear as ten "services" in the heatmap, so a broken hop is visible
as a red cell without opening any file.

---

## 3. What gets pushed, and where

`--push` hands the run directory to `scripts/monitor/publish_report.py`, the same
publisher the nightly health report uses. It writes this tree into
`Work_RAG_HealthCheck` and pushes one commit to `main`:

```
index.html                  static dashboard (no build step)
.nojekyll                   keep paths with _ and .
runs/<RUN_ID>.json          compact record: one entry per hop, with status
runs/index.json             manifest, rebuilt from the directory listing
latest/run.json             newest record
latest/REPORT.md            newest report
latest/dashboard.html       redirect to the newest per-run detail page
logs/<RUN_ID>/REPORT.md     this run's markdown report
logs/<RUN_ID>/run.log       full terminal transcript
logs/<RUN_ID>/curl/matrix.tsv   per-hop rows the dashboard reads
logs/<RUN_ID>/meta/*            raw per-hop evidence
```

Retention: JSON records are never pruned; `logs/<RUN_ID>/` keeps the newest 30
runs (`GPU_HEALTH_KEEP_LOGS`). Every push rebases and retries and never
force-pushes, so laptop and GPU can publish concurrently.

### The verdict maps to the dashboard like this

| Hop result | `curl/matrix.tsv` code | Dashboard |
|---|---|---|
| `PASS` | `200` | up (green) |
| `WARN` | `408` | degraded (amber) |
| `FAIL` | `000` | down (red) |
| `SKIP` | `SKIP` | no-data (grey) |

Overall verdict → run status: `PASS` → `HEALTHY`, `WARN` → `DEGRADED`,
`FAIL` → `DOWN`.

---

## 4. Safety

### The publish target is guarded

Only the standalone health-check repo may receive a run. Before probing anything,
`--push` resolves the remote and refuses with **exit 64** if it normalises to a
production repo — `Work_Credit-RAG_Phase1`, `Work_RAG-Server-Setup`, or any
component submodule — or to anything that is not the health repo. Nothing is
probed in that case.

A local filesystem path (used by the offline end-to-end test) is always allowed,
because it cannot be a production host.

Override the target when needed:

```bash
GPU_HEALTH_REPO=https://github.com/AliNikkhah2001/Work_RAG_HealthCheck.git
GPU_HEALTH_REPO_DIR=~/Work_RAG_HealthCheck
GPU_HEALTH_BRANCH=main
# or the script-specific names:
DANA_EDGE_DIAG_REPO / DANA_EDGE_DIAG_REPO_DIR / DANA_EDGE_DIAG_BRANCH
```

### Secrets are removed before publication

Every text artifact passes through `redact_tree()` **before** the publisher copies
anything. Removed shapes:

- `Authorization: Bearer|Basic|Token …` headers, and bare `Bearer <token>`
- `sk-…` API keys, `ghp_`/`github_pat_` tokens
- `KEY|SECRET|PASSWORD|PASS|TOKEN|CREDENTIAL|PRIVATE_KEY|ACCESS_KEY|…=value`
  in any case, quoted or bare
- `postgres://`, `postgresql+asyncpg://`, `mysql://`, `redis://` URLs
- `https://user:password@host` userinfo
- PEM private-key bodies (the multi-line block, not just the header)

Files whose names the publisher refuses to ship (shell history, `env*`, `host-*`,
`commands.txt`, `docker_inspect.txt`) are moved to `redacted/`, which is not a
published subdirectory. If a file cannot be sanitized it is **deleted** rather
than published — the pass fails closed.

Redaction quality is recorded in `logs/<RUN_ID>/meta/redaction.txt` as counts
only; the removed values never appear there.

Verify it yourself, with no host and no network:

```bash
mkdir -p /tmp/redact_test
printf 'Authorization: Bearer SENTINEL_TOKEN_123\nOPENAI_API_KEY=sk-x\n' \
  > /tmp/redact_test/probe.txt
bash scripts/diagnose_edge_path.sh --redact-only /tmp/redact_test
cat /tmp/redact_test/probe.txt      # both values must read [REDACTED] / REDACTED
```

---

## 5. Exit codes

Same convention as `deploy/gpu/lib/common.sh`:

| Code | Meaning |
|---|---|
| `0` | Every hop passed. `WARN`/`SKIP` do not fail a run. |
| `1` | At least one hop FAILED. |
| `64` | Refused or usage error — nothing was probed (bad flag, unsafe push target). |

---

## 6. What is never fabricated

If a tool or privilege is missing, the hop records the fact instead of guessing:

- `meta/tools.txt` lists every probed command as `present` or `missing`
- the affected hop is `SKIP`, with `tool_missing=<names>` in its evidence file
- `SKIP` is never counted as a pass, and the report says so explicitly

That distinction is the point: "not tested" and "test passed" must never look the
same in a document someone uses to decide what to fix.
