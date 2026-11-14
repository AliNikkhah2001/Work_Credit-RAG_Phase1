# GPU health-report daemon

Daily health report for the production GPU host: probes every service, runs an
end-to-end chat check, captures screenshots, publishes a JSON run record plus a
static dashboard to GitHub Pages, and retries every few hours if anything failed.

Live dashboard: <https://alinikkhah2001.github.io/Work_RAG_HealthCheck/>

## Why this exists

On 2026-11-12 the stack went down silently. Nothing in git had changed; the
containers were recreated from `compose.base.yml` alone, which publishes **no
host ports**, so every service reported healthy to Docker while `:13000` was
dark. No daemon was watching and nothing pushed telemetry outward, so nobody
found out. This daemon is the fix for the "nobody found out" half.

## What it publishes

| Path | Contents |
|---|---|
| `runs/<UTC>-<machine>.json` | one compact record per run (services, E2E, KB version, gate) |
| `runs/index.json` | manifest of every run, rebuilt at publish time |
| `latest/` | `run.json`, `REPORT.md`, `dashboard.html` for the newest run |
| `logs/<run-id>/` | raw logs, retained for the most recent runs only |

Pushes go **only** to `Work_RAG_HealthCheck`, which has no Jenkins job and no
repo-authored Actions workflow, so reporting can never trigger a build.
`deploy/gpu/sim/verify_report_repo.sh` asserts that invariant.

## Install on the GPU server

```bash
cd /splunk-data/production/Work_Credit-RAG_Phase1
git pull

# preview the unit files without writing anything
sudo DANA_HOST_REPO=$(pwd) bash deploy/monitor/install.sh --dry-run

# install
sudo DANA_HOST_REPO=$(pwd) \
     GPU_RECOVERY_REPO_URL=git@github.com:AliNikkhah2001/Work_RAG_HealthCheck.git \
     DANA_REPORT_TIME=16:00 \
     DANA_RETRY_HOURS=3 \
     bash deploy/monitor/install.sh
```

Then run it once in the foreground to see real output before trusting the timer:

```bash
sudo bash scripts/gpu_full_recover_report.sh
```

Verify:

```bash
systemctl list-timers | grep dana-health
journalctl -u dana-health-report -n 50 --no-pager
curl -sI https://alinikkhah2001.github.io/Work_RAG_HealthCheck/ | head -1
```

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `DANA_HOST_REPO` | auto-detected | repo root on the host |
| `DANA_REPORT_TIME` | `16:00` | daily `OnCalendar` time (host local time) |
| `DANA_RETRY_HOURS` | `3` | retry cadence when a run fails |
| `GPU_RECOVERY_REPO_URL` | health-check repo | push target |
| `DANA_UNIT_DIR` | `/etc/systemd/system` | where unit files are written |
| `DANA_LASTGOOD_KEEP` | `5` | last-known-good image tags retained per repo |

## Uninstall

```bash
sudo bash deploy/monitor/uninstall.sh
```

Published reports are left intact.

## Notes and limits

- The report **collects evidence**; it does not itself restart anything. Service
  recovery is `scripts/gpu_auto_heal.sh` (60s port probes + restart).
- A health report is not a deploy. It records what is running, including which
  KB index version is ingested in the DB versus what production expects.
- The retry timer re-arms the unit, but the report script also retries
  internally, so a transient failure does not necessarily surface as a red unit.
- GitHub Pages caches for ~10 minutes (`cache-control: max-age=600`); a fresh
  run may take a moment to appear.
