#!/usr/bin/env bash
# =============================================================================
# deploy/gpu/reconcile.sh — the keep-alive / auto-heal entry point.
#
# This replaces blind `docker compose up -d` healing. Blind `up -d` is what
# re-applied a broken layering and turned a transient problem into a 2-day
# outage. Reconcile always heals *towards the recorded last-known-good*, never
# towards "whatever the working tree says right now".
#
# Behaviour per run:
#   1. Run health.sh (host-published ports). If green → touch schedule, exit 0.
#   2. If red AND a last-known-good exists → rollback.sh (which re-verifies).
#      Optionally retry once more after RETRY_AFTER seconds.
#   3. If red AND no last-known-good → attempt a normal deploy ONCE (bootstrap),
#      which promotes only if the health gate passes.
#   4. Never loops forever: each run is bounded and idempotent, so the timer can
#      fire while a previous run is still going without stacking damage.
#
# Cadence: see deploy/gpu/systemd/dana-gpu-reconcile.timer
#   - daily full check (04:10 host-local, Persistent=true catches missed runs)
#   - retry every 3h while unhealthy, driven by schedule.next_retry_at in state
#   A single timer wakes hourly; the script itself decides using next_retry_at
#   whether it is due. That keeps the cadence visible in the state file and
#   survives restarts (no in-memory counters).
#
# Usage:
#   bash deploy/gpu/reconcile.sh                 # respect next_retry_at (timer mode)
#   bash deploy/gpu/reconcile.sh --force         # ignore next_retry_at, check now
#   bash deploy/gpu/reconcile.sh --dry-run
#   bash deploy/gpu/reconcile.sh --profile stage
#   bash deploy/gpu/reconcile.sh --once-fail-ok # exit 0 even if unhealthy (reporting)
#
# Exit codes: 0 healthy (or healed), 1 unhealthy and heal failed, 2 usage.
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$HERE/lib/common.sh"

PROFILE="gpu"
FORCE=0
DRY_RUN=0
REPORT_ONLY=0
# Cadence: a healthy stack is re-verified once a day; a failing one retries every
# 3h. Both intervals live in the state file (schedule.next_retry_at), so the
# timer can stay dumb and the schedule survives reboots and manual runs.
RETRY_INTERVAL_HOURS="${DANA_RETRY_HOURS:-3}"
DAILY_INTERVAL_HOURS="${DANA_DAILY_HOURS:-24}"

while [ $# -gt 0 ]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --profile=*) PROFILE="${1#*=}"; shift ;;
    --force) FORCE=1; shift ;;
    --dry-run|-n) DRY_RUN=1; shift ;;
    --report-only) REPORT_ONLY=1; shift ;;
    --retry-hours) RETRY_INTERVAL_HOURS="$2"; shift 2 ;;
    --daily-hours) DAILY_INTERVAL_HOURS="$2"; shift 2 ;;
    -h|--help) sed -n '1,40p' "$0"; exit 0 ;;
    *) die "reconcile.sh: unknown arg: $1" ;;
  esac
done

dana_guard_overrides "$PROFILE" || exit 2
dana_ensure_log_dir
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_LOG="$DANA_LOG_DIR/reconcile.log"
HEALTH_JSON="$DANA_STATE_DIR/health-$RUN_ID.json"
mkdir -p "$DANA_STATE_DIR"

say() { log "$*" | tee -a "$RUN_LOG" >/dev/null; printf '%s\n' "$*"; }

say "=== reconcile $RUN_ID profile=$PROFILE (force=$FORCE dry_run=$DRY_RUN) ==="

# ---------------------------------------------------------------------------
# Cadence gate
#   schedule.next_retry_at is the single scheduling source of truth:
#     - healthy run  -> now + DAILY_INTERVAL_HOURS (daily re-verify)
#     - failing run  -> now + RETRY_INTERVAL_HOURS (3h retry)
#   --force bypasses the gate (manual operator check / post-deploy verification).
# ---------------------------------------------------------------------------
NEXT="$(dana_state_field schedule.next_retry_at "")"
if [ "$FORCE" != "1" ] && [ -n "$NEXT" ]; then
  if ! dana_due "$NEXT"; then
    say "not due yet (next_retry_at=$NEXT) — skipping. Use --force to check now."
    exit 0
  fi
fi

# ---------------------------------------------------------------------------
# 1. Health check from the host (authoritative)
# ---------------------------------------------------------------------------
say "health gate"
bash "$HERE/health.sh" --profile "$PROFILE" --json "$HEALTH_JSON" 2>&1 | tee -a "$RUN_LOG"
HEALTH_RC=${PIPESTATUS[0]}

if [ "$HEALTH_RC" -eq 0 ]; then
  say "healthy (exit 0)"
  NEXT_DAILY="$(dana_iso_plus_seconds $((DAILY_INTERVAL_HOURS * 3600)))"
  say "next check scheduled: $NEXT_DAILY (daily re-verify, ${DAILY_INTERVAL_HOURS}h)"
  if [ "$DRY_RUN" != "1" ] && [ -f "$DANA_STATE_FILE" ]; then
    python3 - "$DANA_STATE_FILE" "$NEXT_DAILY" <<'PY' 2>/dev/null || true
import json, sys, datetime, os
state, next_daily = sys.argv[1], sys.argv[2]
data = json.load(open(state))
now = datetime.datetime.now(datetime.timezone.utc)
sched = data.setdefault("schedule", {})
sched["last_check_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
sched["last_success_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
sched["next_retry_at"] = next_daily
sched["consecutive_failures"] = 0
tmp = state + ".tmp"
with open(tmp, "w") as fh:
    json.dump(data, fh, indent=2, sort_keys=True); fh.write("\n")
os.replace(tmp, state)
PY
  fi
  exit 0
fi

say "UNHEALTHY (health exit $HEALTH_RC)"

if [ "$REPORT_ONLY" = "1" ]; then
  say "--report-only: not healing"
  exit 1
fi

# ---------------------------------------------------------------------------
# 2. Decide heal strategy: last-known-good first, bootstrap deploy only if none
# ---------------------------------------------------------------------------
HAVE_LKG=0
dana_state_healthy && HAVE_LKG=1

if [ "$HAVE_LKG" = "1" ]; then
  LKG_SHA="$(dana_state_field compose.config_sha256 "")"
  LKG_AT="$(dana_state_field promoted_at "")"
  say "healing towards last-known-good config=${LKG_SHA:0:12} promoted_at=$LKG_AT"
  while IFS= read -r f; do
    [ -n "$f" ] && say "  layer: $f"
  done < <(dana_profile_files "$PROFILE")
  if [ "$DRY_RUN" = "1" ]; then
    say "dry-run: would run rollback.sh --profile $PROFILE --reason 'reconcile $RUN_ID: health exit $HEALTH_RC'"
    exit 0
  fi
  bash "$HERE/rollback.sh" --profile "$PROFILE" \
    --reason "reconcile $RUN_ID: health exit $HEALTH_RC" 2>&1 | tee -a "$RUN_LOG"
  RB_RC=${PIPESTATUS[0]}
  if [ "$RB_RC" -eq 0 ]; then
    say "HEALED via rollback to last-known-good"
    NEXT_DAILY="$(dana_iso_plus_seconds $((DAILY_INTERVAL_HOURS * 3600)))"
    python3 - "$DANA_STATE_FILE" "$NEXT_DAILY" <<'PY' 2>/dev/null || true
import json, sys, datetime, os
state, next_daily = sys.argv[1], sys.argv[2]
data = json.load(open(state))
sched = data.setdefault("schedule", {})
sched["last_check_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
sched["last_success_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
sched["next_retry_at"] = next_daily
sched["consecutive_failures"] = 0
tmp = state + ".tmp"
with open(tmp, "w") as fh:
    json.dump(data, fh, indent=2, sort_keys=True); fh.write("\n")
os.replace(tmp, state)
PY
    say "next check scheduled: $NEXT_DAILY (daily re-verify)"
    exit 0
  fi
  say "rollback did not reach healthy (exit $RB_RC)"
else
  warn "no last-known-good on record — attempting a controlled deploy (bootstrap)"
  if [ "$DRY_RUN" = "1" ]; then
    say "dry-run: would run deploy.sh --profile $PROFILE"
    exit 0
  fi
  if bash "$HERE/deploy.sh" --profile "$PROFILE" --no-rollback 2>&1 | tee -a "$RUN_LOG"; then
    say "HEALED via bootstrap deploy (promoted)"
    exit 0
  fi
  say "bootstrap deploy failed"
fi

# ---------------------------------------------------------------------------
# 3. Still unhealthy: schedule the retry cadence (3h) and fail loudly
# ---------------------------------------------------------------------------
RETRY_SECONDS=$((RETRY_INTERVAL_HOURS * 3600))
NEXT_AT="$(dana_iso_plus_seconds "$RETRY_SECONDS")"
FAILS=0
if [ -f "$DANA_STATE_FILE" ]; then
  FAILS="$(dana_state_field schedule.consecutive_failures 0)"
  case "$FAILS" in ''|*[!0-9]*) FAILS=0 ;; esac
  FAILS=$((FAILS + 1))
  python3 - "$DANA_STATE_FILE" "$NEXT_AT" "$FAILS" <<'PY' 2>/dev/null || true
import json, sys, datetime, os
state, next_at, fails = sys.argv[1], sys.argv[2], int(sys.argv[3])
data = json.load(open(state))
sched = data.setdefault("schedule", {})
sched["last_check_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
sched["next_retry_at"] = next_at
sched["consecutive_failures"] = fails
tmp = state + ".tmp"
with open(tmp, "w") as fh:
    json.dump(data, fh, indent=2, sort_keys=True); fh.write("\n")
os.replace(tmp, state)
PY
else
  NEXT_AT="$(dana_iso_plus_seconds "$RETRY_SECONDS")"
fi

say "STILL UNHEALTHY after heal attempts — consecutive_failures=$FAILS next_retry_at=$NEXT_AT"
say "state file: $DANA_STATE_FILE  log: $RUN_LOG"
exit 1
