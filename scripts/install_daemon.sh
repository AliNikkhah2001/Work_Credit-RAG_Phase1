#!/usr/bin/env bash
# =============================================================================
# install_daemon.sh — Install systemd service + timer for daily GPU recovery report
#
# Runs gpu_full_recover_report.sh daily at 16:00 (4 PM).
# On failure, retries every 3 hours until success.
# Pushes to standalone recovery repo (no Jenkins triggers).
#
# Install as root on the production GPU server.
# =============================================================================
set -euo pipefail

REPO_ROOT="${DANA_HOST_REPO:-$(pwd)}"
SCRIPT="$REPO_ROOT/scripts/gpu_full_recover_report.sh"
DAILY_TIME="${DAILY_TIME:-16:00}"
RETRY_HOURS="${RETRY_HOURS:-3}"
RECOVERY_REPO="${GPU_RECOVERY_REPO:-}"
RECOVERY_REPO_URL="${GPU_RECOVERY_REPO_URL:-}"

echo "=== Installing GPU recovery daemon ==="
echo "Repo root:     $REPO_ROOT"
echo "Script:        $SCRIPT"
echo "Daily time:    $DAILY_TIME"
echo "Retry hours:   $RETRY_HOURS"
echo "Recovery repo: ${RECOVERY_REPO:-<not set — will use server-setup submodule>}"

if [[ ! -f "$SCRIPT" ]]; then
  echo "ERROR: script not found at $SCRIPT"
  exit 1
fi

if [[ ! -d "$REPO_ROOT/.git" ]]; then
  echo "ERROR: not a git repository: $REPO_ROOT"
  exit 1
fi

# --- Create systemd service unit ---
SERVICE_FILE="/etc/systemd/system/gpu-recovery-report.service"
cat >"$SERVICE_FILE" <<UNITEOF
[Unit]
Description=GPU Full Recovery Report (daily diagnostic)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=root
WorkingDirectory=$REPO_ROOT
Environment=DANA_HOST_REPO=$REPO_ROOT
Environment=GPU_RECOVERY_REPO=$RECOVERY_REPO
Environment=GPU_RECOVERY_REPO_URL=$RECOVERY_REPO_URL
ExecStart=$SCRIPT --daemon
# No restart here — the timer handles scheduling; retry logic is inside the script
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNITEOF

# --- Create systemd timer unit ---
TIMER_FILE="/etc/systemd/system/gpu-recovery-report.timer"
cat >"$TIMER_FILE" <<TIMEREOF
[Unit]
Description=Run GPU Full Recovery Report daily at $DAILY_TIME

[Timer]
OnCalendar=*-*-* $DAILY_TIME
Persistent=true
Unit=gpu-recovery-report.service

[Install]
WantedBy=timers.target
TIMEREOF

# --- Reload systemd ---
systemctl daemon-reload

# --- Enable and start the timer ---
systemctl enable gpu-recovery-report.timer
systemctl start gpu-recovery-report.timer

echo ""
echo "=== Daemon installed ==="
echo "Service:  gpu-recovery-report.service"
echo "Timer:    gpu-recovery-report.timer"
echo "Schedule: Daily at $DAILY_TIME (retry every $RETRY_HOURS h on failure — handled inside script)"
echo ""
echo "Check status with:"
echo "  systemctl status gpu-recovery-report.timer"
echo "  systemctl status gpu-recovery-report.service"
echo "  journalctl -u gpu-recovery-report.service -f"
echo ""
echo "Reports will be pushed to:"
echo "  $RECOVERY_REPO (standalone repo — no Jenkins triggers)"
echo "  or fallback: components/server-setup/docs/ops/gpu-recover-reports/"