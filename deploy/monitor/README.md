# Health monitoring daemon + GitHub Pages dashboard

Durable uptime tracking for the Persian RAG stack. One nightly report run on the
GPU host appends a compact record to **one** `main` branch of
[`AliNikkhah2001/Work_RAG_HealthCheck`](https://github.com/AliNikkhah2001/Work_RAG_HealthCheck),
and a static dashboard served by GitHub Pages renders the whole history.

- **Dashboard:** <https://alinikkhah2001.github.io/Work_RAG_HealthCheck/>
- **Repo (data + site):** <https://github.com/AliNikkhah2001/Work_RAG_HealthCheck>
- **No CI here.** Pages builds straight from the `main` branch root, so report
  pushes never reach Jenkins (which is a multibranch job on a different repo).
  There is no workflow file and no webhook in the HealthCheck repo by design.

---

## 1. Setup on the GPU host (tonight, ~2 minutes)

```bash
# 1) clone / update the umbrella repo (submodules matter for the KB probe)
cd /workspace/Work_Credit-RAG_Phase1        # or wherever the repo lives
git fetch origin && git checkout feature/health-dashboard-pages
git submodule update --init components/knowledgebase

# 2) install the systemd timer (daily 16:00 UTC + retry every 3h on failure)
sudo bash deploy/monitor/install.sh --machine-name gpu-prod

# 3) verify it is armed
systemctl list-timers 'gpu-health-report*'
tail -f /var/log/dana-rag/health-report.log

# 4) force one run right now (do not wait for 16:00)
sudo systemctl start gpu-health-report.service
```

Then open the Pages URL above: the new run appears as a row in the heatmap, in
the run log, and in the "last 24h failures" table if anything was down.

### Install options

```bash
sudo bash deploy/monitor/install.sh                      # defaults: 16:00 UTC, retry 3h
sudo bash deploy/monitor/install.sh --daily-time 04:30   # different UTC time
sudo bash deploy/monitor/install.sh --machine-name h200-1
sudo bash deploy/monitor/install.sh --no-push            # collect locally, publish nothing
sudo bash deploy/monitor/install.sh --dry-run            # print the units, change nothing
sudo bash deploy/monitor/install.sh --health-repo-dir /srv/healthcheck
```

Uninstall (never deletes published data or the repo clone):

```bash
sudo bash deploy/monitor/uninstall.sh                 # remove units + timers
sudo bash deploy/monitor/uninstall.sh --purge-state    # also drop /var/lib/dana-health markers
```

### What gets installed

| Unit | Purpose |
|---|---|
| `gpu-health-report.service` | oneshot: run `scripts/gpu_full_recover_report.sh --daemon` and publish to `main` |
| `gpu-health-report.timer` | daily at `--daily-time` UTC, `Persistent=true`, up to 10 min jitter |
| `gpu-health-report-retry.service` | same run, but gated by `ExecCondition` |
| `gpu-health-report-retry.timer` | every `--retry-hours` (default 3h); the gate makes it a no-op once today succeeded |

The retry gate is a pair of marker files rather than a transient unit result, so
a reboot cannot silently swallow a failed day:

- `/var/lib/dana-health/failing` — written by `ExecStopPost` when the run exits non-zero
- `/var/lib/dana-health/last-success` — UTC timestamp of the last successful run

The retry fires when `failing` exists **or** `last-success` is from an earlier
UTC day. Each retry also re-checks the services, so a host that came back up at
02:00 logs a healthy run at 03:00 without waiting for 16:00.

Logs: `/var/log/dana-rag/health-report.log`, `…err.log`. One oneshot run per
invocation, `TimeoutStartSec=3600`, `StartLimitIntervalSec=0` so a bad hour can
never block the next attempt.

### MacOS / dev laptop

The systemd installer refuses to run on macOS (it targets a Linux GPU host) but
`--dry-run` still prints the units. For a laptop-side manual publish:

```bash
DANA_HOST_REPO=$(pwd) bash scripts/gpu_full_recover_report.sh \
  --no-restart --machine-name laptop
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
- `screenshots/`: newest **7** runs only (`--keep-screenshots`)

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
| **Historical uptime** | one row per service, one cell per run; green up, red down, amber degraded, grey no-data. Hover for timestamp, HTTP code, and detail. Window selector: 24h / 7d / 30d / all |
| **Downtime percentage** | per-service and overall uptime % for the selected window, plus run counts (up/degraded/down) |
| **Failures — last 24 hours** | incident count; each incident lists service, first seen, last seen, duration, and the error/detail excerpt |
| **Knowledge base version** | ingested (live DB) vs expected (repo pin) side by side, match/mismatch badge, per-check matrix, and the corpus change history |
| **Run log** | newest first; status, QA pass count, KB verdict, link to the per-run detail page |

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
