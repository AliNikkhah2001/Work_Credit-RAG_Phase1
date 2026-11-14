#!/usr/bin/env bash
# =============================================================================
# deploy/monitor/should-retry.sh — the gate for the 3-hourly retry timer.
#
# Usage in a systemd unit:  ExecCondition=/bin/bash .../should-retry.sh
#
# Exit 0  → run the report now
# Exit 1  → skip this tick (systemd records the unit as skipped, not failed)
#
# It runs the report when ANY of these is true:
#   * `failing` marker exists (the last attempt exited 1)
#   * no successful run has ever been recorded
#   * the last success was on an earlier UTC day (the daily run was missed —
#     e.g. the host was down at the scheduled time)
#
# It does NOT run when:
#   * the last attempt was REFUSED (exit 64). Retrying a configuration error
#     every 3 hours produces 8 identical failures a day and buries the one line
#     an operator needs to read. The refusal is surfaced on the dashboard and in
#     `systemctl status`; a human fixes GPU_HEALTH_REPO and the next daily run
#     proceeds normally.
#   * today already succeeded and nothing has failed since.
#
# Markers are written by deploy/monitor/mark-result.sh from ExecStopPost.
#
# Exit codes: 0 run, 1 skip, 2 bad args.
# =============================================================================
set -uo pipefail

STATE_DIR="${DANA_HEALTH_STATE_DIR:-/var/lib/dana-health}"
QUIET=0

while [ $# -gt 0 ]; do
  case "$1" in
    --state-dir) STATE_DIR="${2:-$STATE_DIR}"; shift 2 ;;
    --quiet|-q)  QUIET=1; shift ;;
    -h|--help)   sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "should-retry.sh: unknown arg: $1" >&2; exit 2 ;;
  esac
done

say() { [ "$QUIET" = "1" ] || printf '[retry-gate] %s\n' "$*"; }

FAILING="$STATE_DIR/failing"
SUCCESS="$STATE_DIR/last-success"
REFUSED="$STATE_DIR/refused"

if [ -f "$FAILING" ]; then
  say "last attempt failed ($(cat "$FAILING" 2>/dev/null)) — retrying"
  exit 0
fi

if [ ! -f "$SUCCESS" ]; then
  if [ -f "$REFUSED" ]; then
    say "last attempt was REFUSED at $(cat "$REFUSED" 2>/dev/null) and nothing has run since — not retrying a config error"
    exit 1
  fi
  say "no successful run recorded yet — running"
  exit 0
fi

TODAY="$(date -u +%Y-%m-%d)"
LAST="$(cut -c1-10 "$SUCCESS" 2>/dev/null)"
if [ "$LAST" != "$TODAY" ]; then
  say "last success was $LAST (before today) — running the missed daily report"
  exit 0
fi

say "already succeeded today ($(cat "$SUCCESS" 2>/dev/null)) — skipping"
exit 1
