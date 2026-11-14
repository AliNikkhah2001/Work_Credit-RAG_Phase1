#!/usr/bin/env bash
# =============================================================================
# deploy/monitor/uninstall.sh — remove the GPU health-report daemon
#
#   sudo bash deploy/monitor/uninstall.sh
#
# Stops and disables the timers, removes the unit files, reloads systemd.
# Does NOT delete reports already published to the health-check repo, and does
# not touch running services.
# =============================================================================
set -euo pipefail

UNIT_DIR="${DANA_UNIT_DIR:-/etc/systemd/system}"
SERVICE_NAME="dana-health-report"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "must run as root (sudo)" >&2
  exit 1
fi

for unit in "${SERVICE_NAME}.timer" "${SERVICE_NAME}-retry.timer" "${SERVICE_NAME}.service"; do
  if systemctl list-unit-files "$unit" >/dev/null 2>&1; then
    systemctl disable --now "$unit" >/dev/null 2>&1 || true
    echo "  disabled $unit"
  fi
done

for f in "$UNIT_DIR/${SERVICE_NAME}.timer" \
         "$UNIT_DIR/${SERVICE_NAME}-retry.timer" \
         "$UNIT_DIR/${SERVICE_NAME}.service"; do
  if [[ -f "$f" ]]; then
    rm -f "$f" && echo "  removed $f"
  fi
done

systemctl daemon-reload
systemctl reset-failed "${SERVICE_NAME}.service" >/dev/null 2>&1 || true
echo "uninstalled. published reports were left intact."
