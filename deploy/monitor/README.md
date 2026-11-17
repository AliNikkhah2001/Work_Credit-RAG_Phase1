# Health monitoring daemon + GitHub Pages dashboard

Durable uptime tracking for the Persian RAG stack. An **hourly** systemd timer on the
GPU host appends a compact record to **one** `main` branch of
[`AliNikkhah2001/Work_RAG_HealthCheck`](https://github.com/AliNikkhah2001/Work_RAG_HealthCheck),
appends a tiny status/series point to
[`AliNikkhah2001/Work_RAG_Metrics`](https://github.com/AliNikkhah2001/Work_RAG_Metrics)
(no screenshots), syncs `metrics/` into the Pages tree, and a static dashboard
renders the history (prod + stage ports).

Screenshots are auto-pruned (newest **3** runs **and** ≤ **24h**) so hourly
publishes do not fill GitHub storage or trip soft rate limits.

### What each hourly report now includes

| Area | Behavior |
|---|---|
| **Random FAQ QA** | 10 random Q&A from the canned KB pack (`faq_shortlist`); new sample every run |
| **Latency** | KB `stage_ms` + orchestrator `audit.stage_timing_ms` / `latency_ms` → `e2e/latency_summary.json` + Pages charts |
| **Screenshots** | Jenkins **login → dashboard**, KB manager `/docs`, WebUI main `:13000` + alt `:8088` (+ stage `:13100`), manager `:9000`, orch/guard docs — **10s settle** between shots |
| **Host inventory** | Open ports, disk, RAM, NVIDIA GPU → `meta/host_inventory.json` + diagrams |
| **Jenkins status** | Auth + Multibranch job + image freshness (missing/stale) → `meta/jenkins_status.json` on Pages |
| **Jenkins forensics** | Last build `consoleText` (tail-truncated), error/`docker`/`npm` excerpt, `wfapi`/stage dump, heuristic `diagnosis.json` → `meta/jenkins/*` (published under `logs/<run>/meta/jenkins/`) |
| **QA samples on dashboard** | Per-run HTML reads `e2e/random_qa.json` (question + answer_preview); no longer looks for missing `random_qa_N.json` files |
| **WebUI submodule watch** | Same hourly timer: compares `components/webui` gitlink vs `Work_RAG-WebUI` `main` tip; nudges Jenkins scan (does **not** auto-push umbrella) |
| **KB version** | Pack pins normalized (`schemas/v1.0.1.yaml` ≡ `1.0.1`) so false “discrepancy / unknown latest” is gone when corpus matches |


- **Dashboard:** <https://alinikkhah2001.github.io/Work_RAG_HealthCheck/>
- **Repo (data + site):** <https://github.com/AliNikkhah2001/Work_RAG_HealthCheck>
- **Metrics (append-only JSON):** <https://github.com/AliNikkhah2001/Work_RAG_Metrics>
- **Host status file:** `/var/lib/dana-health/status.json`
- **Jenkins status file:** `/var/lib/dana-health/jenkins-status.json`
- **WebUI watch file:** `/var/lib/dana-health/webui-watch.json`
- **No CI here.** Pages builds straight from the `main` branch root, so report
  pushes never reach Jenkins (which is a multibranch job on a different repo).
  There is no workflow file and no webhook in the HealthCheck repo by design.

### How the frontend (`rag-webui`) image actually builds

A red `dana/validate` / `last_build_FAILURE` on GitHub is often **not** an npm/Docker failure.
Laptop Jenkins (`DANA_ROLE=stage`, job `dana-rag`) correctly refuses to call `main` verified
(`main NOT verified: no prod controller`). That status does **not** rebuild prod images.

| Requirement | Detail |
|---|---|
| Controller | GPU `dana-jenkins-prod` with `DANA_ROLE=prod` → Multibranch job **`dana-rag-prod`** |
| Branch | **`main` only** on the prod controller |
| Commit trigger | Message must include **`[ci prod]`** or **`[ci auto]`** (or heavy path changes / `[ci build]`) |
| Preferred path | PR `develop` → `main` with title/body containing `[ci prod]`, or `bash scripts/promote_stage_to_main.sh --execute --push` |
| H200 Jenkins recreate | Always `docker-compose.yml` + `docker-compose.gpu.yml` + `docker-compose.h200.yml`. Never omit h200 (see server-setup `imagebugfix.txt`). |
| WebUI pin | Bump `components/webui` gitlink on the umbrella **before** the `[ci prod]` commit — watcher alone does not advance the pin |
| After push | Wait for hourly `pollSCM` or **Scan Multibranch Now** on `dana-rag-prod` |
| Pin hygiene | Every gitlink SHA must exist on its GitHub remote (`git submodule update --init --recursive` green) or sync fails before build |
| Tip without keys | A `main` merge **without** `[ci prod]` skips Build/Deploy; coverage then fails with `missing prod-deploy` — use an empty `[ci prod] [ci all]` commit to rebuild |

On a real prod build, Jenkins runs `npm ci` + `npm run build` in `components/webui`, then
`docker compose … build … webui`, and retags `rag-webui:local` → `:production` / `:dana` on deploy.
If the agent has no npm and no `components/webui/build`, the log says
`Skipping rag-webui image build` — that is a real skip, visible in `meta/jenkins/console_excerpt.txt`
after the next health publish.

### How to test Jenkins sees submodule commits (no manual rebuild from this host)

1. On your laptop, push WebUI changes to `Work_RAG-WebUI` `main`.
2. **Also** bump the umbrella gitlink on `Work_Credit-RAG_Phase1` `main` and commit with `[ci prod]` or `[ci auto]` (Jenkins only polls the parent).
3. Within ~1h the `gpu-webui-watch.timer` + Multibranch `pollSCM` pick up the parent tip and build.
4. Confirm: `cat /var/lib/dana-health/webui-watch.json` (`ahead: true` until the pin catches up) and Jenkins job `dana-rag-prod/main`.

Force-heal / snapshot from any computer (no GPU needed on the committer):

```text
git commit -m "freeze tested images [ci snapshot]"
git commit -m "restore LKG freeze [ci heal]"
git commit -m "restore specific freeze [ci heal:20261115T124350Z]"
git commit -m "break-glass restore [ci force-heal]"
```

Push to `main` — the GPU Jenkins controller runs `create_snapshot.sh` / `restore_from_snapshot.sh --apply`.

---

## 1. Setup on the GPU host (tonight, ~2 minutes)

```bash
# 1) clone / update the umbrella repo (submodules matter for the KB probe).
#    Everything below lives on main — no feature branch required.
cd /workspace/Work_Credit-RAG_Phase1        # or wherever the repo lives
git fetch origin && git checkout main && git pull --ff-only origin main
git submodule update --init components/knowledgebase

# 2) validate the plan first — read-only, needs no root, changes nothing
bash deploy/monitor/install.sh --check

# 3) install the systemd timer (hourly primary + retry hourly on failure)
sudo bash deploy/monitor/install.sh --interval-hours 1 --machine-name ai-gpu1

# 4) verify it is armed (two timers, both enabled)
systemctl list-timers 'gpu-health-report*'

# 5) force one run right now
sudo systemctl start gpu-health-report.service
tail -f /var/log/dana-rag/health-report.log
```

Headless screenshots on this TUI host use snap Chromium (`/usr/local/bin/chromium`)
and/or `/opt/dana-playwright` — see `scripts/gpu_full_recover_report.sh` `shoot()`.

Then open the Pages URL above: the new run appears as a row in the heatmap, in
the run log, and in the "last 24h failures" table if anything was down.


### Where to look after the forced run

| What | Where |
|---|---|
| Did it run and what exit code? | `systemctl status gpu-health-report.service` (or `journalctl -u gpu-health-report.service -n 80`) |
| Full transcript | `tail -f /var/log/dana-rag/health-report.log` (errors in `…err.log`) |
| Local report + dashboard | the run prints `Output dir:` / `Report:` / `Dashboard:` paths — typically `<repo>/components/server-setup/docs/ops/gpu-recover-reports/<RUN_ID>/REPORT.md` |
| Published record | `https://github.com/AliNikkah2001/Work_RAG_HealthCheck/tree/main/runs` → `<RUN_ID>.json` |
| Dashboard row | <https://alinikkhah2001.github.io/Work_RAG_HealthCheck/> |
| Live status JSON | `/var/lib/dana-health/status.json` and Pages `metrics/status.json` |
| Metrics series | <https://github.com/AliNikkhah2001/Work_RAG_Metrics/tree/main/metrics> |
| Retry state | `cat /var/lib/dana-health/{last-success,failing,refused} 2>/dev/null` |

If `last-success` has today's timestamp the daily run is done; if `failing`
exists the retry timer will re-run within `--retry-hours`. If `refused` exists
nothing will retry — fix `GPU_HEALTH_REPO` first.

### Install options

```bash
sudo bash deploy/monitor/install.sh                      # defaults: every 1h + retry 1h
sudo bash deploy/monitor/install.sh --interval-hours 1   # primary cadence (configurable)
sudo bash deploy/monitor/install.sh --daily-time 04:30   # optional extra calendar tick
sudo bash deploy/monitor/install.sh --retry-hours 1      # retry cadence while failing
sudo bash deploy/monitor/install.sh --machine-name ai-gpu1
sudo bash deploy/monitor/install.sh --no-push            # collect locally, publish nothing
sudo bash deploy/monitor/install.sh --health-repo <url>  # non-default publish target
sudo bash deploy/monitor/install.sh --health-repo-dir /srv/healthcheck
sudo bash deploy/monitor/install.sh --metrics-repo <url> # dedicated metrics repo
sudo bash deploy/monitor/install.sh --check              # validate the plan, change nothing
sudo bash deploy/monitor/install.sh --dry-run            # print the units, change nothing
```

`--interval-hours` / `--retry-hours` must be positive integers; optional `--daily-time`
must be `HH:MM` 24-hour. `--check` and `--dry-run` never need root.

Uninstall (never deletes published data or the repo clone):

```bash
sudo bash deploy/monitor/uninstall.sh                 # remove units + timers
sudo bash deploy/monitor/uninstall.sh --purge-state    # also drop /var/lib/dana-health markers
```

### What gets installed

| Unit | Purpose |
|---|---|
| `gpu-health-report.service` | oneshot: run `scripts/gpu_full_recover_report.sh --daemon` and publish to `main` |
| `gpu-health-report.timer` | every `--interval-hours` (default 1h), `Persistent=true`, up to 10 min jitter |
| `gpu-health-report-retry.service` | same run, but gated by `ExecCondition` |
| `gpu-health-report-retry.timer` | every `--retry-hours` (default 1h); the gate makes it a no-op once today succeeded |

The retry decision comes from **marker files** rather than a transient unit
result, so a reboot cannot silently swallow a failed day. Three markers, all
under `/var/lib/dana-health`:

| Marker | Written when the run exits | Effect on the retry timer |
|---|---|---|
| `last-success` | `0` | clears `failing` and `refused` |
| `failing` | `1` (unhealthy stack, or publish failed) | **arms** — the retry re-runs |
| `refused` | `64` (bad `GPU_HEALTH_REPO` or bad arguments) | **disarms** — nothing re-runs |

Bookkeeping is split into two small scripts so the logic is readable and
testable instead of buried in quoted `sh -c` one-liners inside the unit:

- `deploy/monitor/mark-result.sh` — `ExecStopPost`, maps exit code → markers
- `deploy/monitor/should-retry.sh` — `ExecCondition`, decides run (`0`) vs skip (`1`)

`should-retry.sh` runs the report when **any** of these is true:

- `failing` exists, i.e. the last attempt genuinely failed
- no successful run has ever been recorded
- the last success was on an earlier UTC day (the daily run was missed — e.g.
  the host was down at 16:00)

It skips when the last attempt was **refused** (`64`) and nothing has run since.
Retrying a configuration error every 3h produces 8 identical failures a day and
buries the one line an operator needs; the refusal is visible on the dashboard
and in `systemctl status`, and a human fixes `GPU_HEALTH_REPO`.

Each retry also re-checks the services, so a host that came back up at 02:00
logs a healthy run at 03:00 without waiting for 16:00.

Logs: `/var/log/dana-rag/health-report.log`, `…err.log`. One oneshot run per
invocation, `TimeoutStartSec=3600`, `StartLimitIntervalSec=0` so a bad hour can
never block the next attempt.

### MacOS / dev laptop

The systemd installer refuses to run on macOS (it targets a Linux GPU host) and
exits `3` with a pointer to the launchd path. `--check` and `--dry-run` are the
exceptions: they are read-only previews, so they work on any host and are the
right way to validate a change before touching the GPU box.

```bash
bash deploy/monitor/install.sh --check     # validate the plan (exit 1 if incoherent)
bash deploy/monitor/install.sh --dry-run   # print the four unit files
```

For a one-off laptop run that produces a report without pushing:

```bash
DANA_HOST_REPO=$(pwd) bash scripts/gpu_full_recover_report.sh \
  --no-restart --no-push --machine-name laptop
```

To arm a **daily** run on the laptop, use launchd instead of systemd:

```bash
bash scripts/install_daemon_macos.sh                  # daily at 16:00
DAILY_TIME=09:30 bash scripts/install_daemon_macos.sh # different local time
launchctl list | grep gpu-recovery                    # verify loaded
```

It writes `~/Library/LaunchAgents/com.dana.gpu-recovery-report.plist` and logs
to `~/Library/Logs/com.dana.gpu-recovery-report.{out,err}.log`. The launchd
agent schedules in **local** time, whereas the systemd timer is UTC. To revert:

```bash
launchctl unload ~/Library/LaunchAgents/com.dana.gpu-recovery-report.plist
rm -f ~/Library/LaunchAgents/com.dana.gpu-recovery-report.plist
```

---

## 2. What happens on each run

```
scripts/gpu_full_recover_report.sh
  ├─ collect health matrix (curl/matrix.tsv), E2E QA, screenshots, HTML dashboard
  ├─ probe KB version  → scripts/monitor/kb_version.py  → kb/kb_version.json
  └─ publish           → scripts/monitor/publish_report.py
```

`publish_report.py` writes this tree and pushes it to `main`:

```
index.html                  static dashboard (no build step)
.nojekyll                   keep paths with _ and .
runs/<RUN_ID>.json          one compact health-run/v1 record per run
runs/index.json             manifest, rebuilt from the directory listing
latest/run.json             newest record (stable URL)
latest/dashboard.html       redirect to the newest per-run detail page
latest/REPORT.md            newest markdown report
logs/<RUN_ID>/              raw evidence + detail page + screenshots
```

Retention keeps the repo small without losing history:

- JSON records: **never pruned** (each is ~4 KB, so 3 runs/day is ~4 MB/year)
- `logs/<RUN_ID>/`: newest **30** runs only (`--keep-logs`)
- `screenshots/`: newest **3** runs **and** ≤ **24h** (`--keep-screenshots` / `--keep-screenshots-hours`)
- `metrics/`: `status.json` + `series.json` + `latest.json` (copied from Work_RAG_Metrics each publish)

Nothing sensitive is ever published: the report redacts secrets before packing,
and the publisher additionally refuses to copy shell history and verbose host
logs (`command_shutdown_reboot_user.log`, `host-*.log`) even if they exist in the
run directory, because env exports split over continuation lines survive regex
redaction. The KB probe JSON also redacts the Postgres password. Verify with:

```bash
python3 scripts/monitor/test_monitor.py        # includes a sentinel-secret check
```

Concurrency: every publish does `git pull --rebase --autostash` in a retry loop
(5 attempts, exponential backoff + jitter). **Never force-pushes.** Laptop and
GPU can publish at the same time; both records survive. `runs/index.json` is
regenerated from the directory listing on every publish, so a bad merge heals on
the next run.

### Manual publish

```bash
python3 scripts/monitor/publish_report.py \
  --run-dir /tmp/report-out --run-id 20261114T160000Z-gpu-prod \
  --machine-name gpu-prod --status HEALTHY \
  --kb-version /tmp/report-out/kb/kb_version.json
```

Flags: `--dry-run` (build the tree, no git writes), `--no-push` (commit locally
only), `--no-logs`, `--keep-logs N`, `--keep-screenshots N`, `--retries N`,
`--repo`, `--remote`, `--branch`.

---

## 3. The dashboard

`scripts/monitor/site/index.html` is hand-written HTML/CSS/JS — no framework, no
bundler, no build step. It fetches `runs/index.json` and then the individual
`runs/*.json` records with relative paths, which is exactly what GitHub Pages
serves.

Panels:

  | Panel | Reading |
  |---|---|
  | **Deploy &amp; release** | which commit/release this run reports on: release tag (highest `vX.Y.Z` pointing at the checked-out commit), umbrella SHA, last-known-good SHA, rollback target, server-setup SHA. Reads `meta/deploy.json` (`deploy-state/v1`); falls back to the legacy `meta/host_metadata.txt` `key=value` block. An untagged commit shows *untagged*, and a missing state file shows *unknown* — never a fabricated SHA |
  | **Historical uptime** | one row per service, one cell per run; green up, red down, amber degraded, grey no-data. Hover for timestamp, HTTP code, and detail. Window selector: 24h / 7d / 30d / all |
  | **Downtime percentage** | per-service and overall uptime % for the selected window, plus run counts (up/degraded/down) |
  | **Failures — last 24 hours** | incident count; each incident lists service, first seen, last seen, duration, and the error/detail excerpt |
  | **Knowledge base version** | ingested (live DB) vs expected (repo pin) side by side, match/mismatch badge, per-check matrix, and the corpus change history |
  | **Run log** | newest first; status, QA pass count, KB verdict, release tag, deployed SHA, link to the per-run detail page |

  The `runs/index.json` row also carries `release` and `sha` (last-known-good,
  else umbrella) so the run log answers "which build produced this run?" without
  opening the record.

`latest/dashboard.html` redirects to the newest run's detail page, so a stable
URL always shows the most recent full report with logs and screenshots.

---

## 4. Knowledge base version probe

`scripts/monitor/kb_version.py` writes a `kb-version/v1` document. Names come
from the real implementation, not guesses:

| Value | Source |
|---|---|
| `actual.*` | Postgres `kb_manager`: `SELECT count(*) FROM chunks / documents / entity_lists`, `chunks.embedding_model` histogram, newest `ingestion_jobs` row |
| `served.*` | KB API `GET /health` (`chunk_count`, `doc_count`, `db_mode`, `reranker_ok`) and `GET /registry/api/active` (manifest, pack pins, DVC snapshot pin) |
| `expected.*` | repo pins `components/knowledgebase/kb-source/.dvc_pins/{current,processed}.txt|.json`, plus KB submodule `git rev-parse` |

DB access order: `psql` → `docker exec` into the postgres container that holds
`kb_manager` (this is what makes it work on the laptop compose stack, where
postgres is published on `15432`) → `psycopg2` if installed. Credentials are
never written to the published JSON (`password` is redacted).

Anything unreadable is emitted as `null` and listed under `unknown[]`; the
dashboard renders **unknown** rather than a fabricated number.

```bash
# inspect by hand
python3 scripts/monitor/kb_version.py --repo-root "$PWD" \
  --db-url postgresql://postgres:postgres@127.0.0.1:5432/kb_manager \
  --kb-api http://127.0.0.1:8000 --out /tmp/kb.json && \
  python3 -m json.tool /tmp/kb.json | head -40
```

Verdicts: `match`, `mismatch`, or `unknown`. `verdict.corpus_lagging` is a
forward-looking signal — a newer corpus exists in the repo than the one the DB
serves.

---

## 5. Enabling GitHub Pages

Pages must be enabled once per repo (it is off by default, and until the first
`main` push exists the API 404s).

```bash
bash scripts/enable_pages.sh            # enable from main/ root, then verify HTTP 200
bash scripts/enable_pages.sh --check    # verify only (exit 1 if not live)
```

Idempotent: it creates Pages when absent, repoints the source when it points at
the wrong branch, and leaves a custom domain alone unless `HEALTH_PAGES_CNAME`
is set. `.nojekyll` is written by the publisher, which keeps `logs/<RUN_ID>/`
and dotted paths working.

First-deploy note: Pages builds the site on the first push to `main` after
enabling, so give it a few minutes and re-run `--check`.

---

## 6. Troubleshooting

| Symptom | Check |
|---|---|
| `runs/index.json` 404 on the site | `.nojekyll` missing → the publisher writes it; re-run with `--no-push` then push |
| Page renders but panels are empty | the JSON fetch failed; open `runs/index.json` directly and check `count` |
| KB panel says `unknown` | `logs/<RUN_ID>/kb/kb_version.log`; usually KB `:8000` unreachable or `kb-source/.dvc_pins` not checked out |
| Publisher says `push rejected` | expected under concurrency; it rebases and retries. Persistent failure = credential/host key problem |
| Timer never fires | `systemctl list-timers 'gpu-health-report*'`, then `journalctl -u gpu-health-report.service -n 80` |
| Retry loop runs every 3h forever | `/var/lib/dana-health/failing` exists because runs keep failing — read `/var/log/dana-rag/health-report.err.log` |

Run the offline self-checks (no network, no git) after changing the pipeline:

```bash
python3 scripts/monitor/test_monitor.py
```
