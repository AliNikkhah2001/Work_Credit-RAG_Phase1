#!/usr/bin/env bash
# =============================================================================
# deploy/monitor/mark-result.sh — translate one report run's exit code into the
# marker files the retry timer reads.
#
# Called from systemd `ExecStopPost` (and usable by hand), because the decision
# "should we retry?" must not live in a quoted one-liner buried in a unit file.
#
# The exit-code contract of scripts/gpu_full_recover_report.sh is:
#     0   healthy, published
#     1   unhealthy or publish failed  → RETRY is the correct response
#    64   refused (bad publish target / bad args) → retrying repeats the same
#         refusal forever, so it must NOT arm the retry loop
#
# Markers live in $STATE_DIR (default /var/lib/dana-health):
#   last-success   UTC timestamp of the last exit-0 run
#   failing        UTC timestamp of the last exit-1 run (arms the retry timer)
#   refused        UTC timestamp of the last exit-64 run (disarms the retry timer)
#
# Exit codes: 0 always (a marker-writer must never fail a unit), 2 bad args.
# =============================================================================
set -uo pipefail

STATE_DIR="${DANA_HEALTH_STATE_DIR:-/var/lib/dana-health}"
RC=1
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

while [ $# -gt 0 ]; do
  case "$1" in
    --rc)      RC="${2:-1}"; shift 2 ;;
    --state-dir) STATE_DIR="${2:-$STATE_DIR}"; shift 2 ;;
    -h|--help) sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "mark-result.sh: unknown arg: $1" >&2; exit 2 ;;
  esac
done

case "$RC" in
  ''|*[!0-9]*) echo "mark-result.sh: --rc must be an integer (got '$RC')" >&2; exit 2 ;;
esac

mkdir -p "$STATE_DIR" 2>/dev/null || {
  echo "mark-result.sh: cannot create $STATE_DIR" >&2
  exit 0
}

case "$RC" in
  0)
    printf '%s\n' "$NOW" >"$STATE_DIR/last-success"
    rm -f "$STATE_DIR/failing" "$STATE_DIR/refused"
    ;;
  64)
    # Refusal is a configuration problem, not an outage. Stamp it, and clear
    # `failing` so the retry timer stops re-running the same refusal every 3h.
    printf '%s\n' "$NOW" >"$STATE_DIR/refused"
    rm -f "$STATE_DIR/failing"
    ;;
  *)
    printf '%s\n' "$NOW" >"$STATE_DIR/failing"
    rm -f "$STATE_DIR/refused"
    ;;
esac

exit 0
