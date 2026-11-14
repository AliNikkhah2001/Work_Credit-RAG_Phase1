#!/usr/bin/env bash
# =============================================================================
# deploy/monitor/uninstall.sh — Remove the health-monitor daemon from a GPU host.
#
# Stops and disables both timers, deletes the four unit files, and optionally
# removes state. It never deletes the repo checkout or the published reports.
#
# Usage:
#   sudo bash deploy/monitor/uninstall.sh
#   sudo bash deploy/monitor/uninstall.sh --purge-state   # also drop /var/lib/dana-health
#   sudo bash deploy/monitor/uninstall.sh --dry-run
# =============================================================================
set -uo pipefail

SERVICE_NAME="gpu-health-report"
UNIT_DIR="${UNIT_DIR:-/etc/systemd/system}"
PURGE=0
DRY_RUN=0

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { printf "%b[OK]%b   %s\n" "$GREEN" "$NC" "$*"; }
warn() { printf "%b[WARN]%b %s\n" "$YELLOW" "$NC" "$*"; }
fail() { printf "%b[FAIL]%b %s\n" "$RED" "$NC" "$*"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --purge-state) PURGE=1; shift ;;
    --dry-run)     DRY_RUN=1; shift ;;
    -h|--help)     sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) fail "Unknown option: $1"; exit 2 ;;
  esac
done

if [[ "$(uname -s)" != "Linux" ]]; then
  fail "this uninstaller targets a Linux systemd host (got: $(uname -s))"
  exit 3
fi
if [[ "$DRY_RUN" -eq 0 && "$EUID" -ne 0 ]]; then
  fail "run with sudo"
  exit 2
fi

UNITS=(
  "$SERVICE_NAME.timer"
  "$SERVICE_NAME-retry.timer"
  "$SERVICE_NAME.service"
  "$SERVICE_NAME-retry.service"
)

for unit in "${UNITS[@]}"; do
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "would: systemctl disable --now $unit ; rm -f $UNIT_DIR/$unit"
    continue
  fi
  systemctl disable --now "$unit" >/dev/null 2>&1 || true
  if [[ -f "$UNIT_DIR/$unit" ]]; then
    rm -f "$UNIT_DIR/$unit" && ok "removed $unit" || warn "could not remove $unit"
  else
    warn "$unit not installed"
  fi
done

if [[ "$DRY_RUN" -eq 0 ]]; then
  systemctl daemon-reload >/dev/null 2>&1 && ok "systemctl daemon-reload"
  systemctl reset-failed "$SERVICE_NAME.service" "$SERVICE_NAME-retry.service" >/dev/null 2>&1 || true
fi

if [[ "$PURGE" -eq 1 ]]; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "would: rm -rf /var/lib/dana-health"
  else
    rm -rf /var/lib/dana-health 2>/dev/null && ok "removed /var/lib/dana-health (state markers)"
  fi
fi

echo ""
echo "The daemon is removed. Kept on disk (delete manually if unwanted):"
echo "  /var/log/dana-rag/health-report.log"
echo "  \$HOME/Work_RAG_HealthCheck (or /var/lib/dana-health/Work_RAG_HealthCheck)"
