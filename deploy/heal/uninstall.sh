#!/usr/bin/env bash
# =============================================================================
# deploy/heal/uninstall.sh — Remove the self-heal (reconcile) daemon.
#
# Stops and disables the timer, deletes both unit files, and reloads systemd.
# Never touches the last-known-good state, logs, or the repo checkout — removing
# the healer must not destroy the evidence of what it healed.
#
# Usage:
#   sudo bash deploy/heal/uninstall.sh
#   sudo bash deploy/heal/uninstall.sh --dry-run
#
# Exit codes: 0 ok, 2 bad args, 3 not a Linux host.
# =============================================================================
set -uo pipefail

SERVICE_NAME="dana-gpu-reconcile"
UNIT_DIR="${UNIT_DIR:-/etc/systemd/system}"
DRY_RUN=0

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { printf "%b[OK]%b   %s\n" "$GREEN" "$NC" "$*"; }
warn() { printf "%b[WARN]%b %s\n" "$YELLOW" "$NC" "$*"; }
fail() { printf "%b[FAIL]%b %s\n" "$RED" "$NC" "$*"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) fail "Unknown option: $1"; exit 2 ;;
  esac
done

if [[ "$(uname -s)" != "Linux" ]]; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    warn "not a Linux host ($(uname -s)) — --dry-run will preview, no changes made"
  else
    fail "this uninstaller targets a Linux systemd host (got: $(uname -s))"
    exit 3
  fi
fi
if [[ "$DRY_RUN" -eq 0 && "$EUID" -ne 0 ]]; then
  fail "run with sudo"
  exit 2
fi

UNITS=("$SERVICE_NAME.timer" "$SERVICE_NAME.service")

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
  systemctl reset-failed "$SERVICE_NAME.service" >/dev/null 2>&1 || true
fi

echo ""
echo "The heal daemon is removed. Kept on disk (delete manually if unwanted):"
echo "  deploy/gpu/state/            last-known-good + health snapshots (KEEP: rollback needs it)"
echo "  /var/log/dana-rag/reconcile.log"
