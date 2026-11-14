#!/usr/bin/env bash
# =============================================================================
# install_daemon_macos.sh — Install macOS launchd agent for daily GPU recovery
#
# Runs gpu_full_recover_report.sh daily at 16:00 (4 PM).
# On failure, retries every 3 hours (handled inside the script).
# Pushes to standalone recovery repo (no Jenkins triggers).
#
# Install as user on the macOS dev laptop.
# =============================================================================
set -euo pipefail

REPO_ROOT="${DANA_HOST_REPO:-$(pwd)}"
SCRIPT="$REPO_ROOT/scripts/gpu_full_recover_report.sh"
DAILY_TIME="${DAILY_TIME:-16:00}"
RECOVERY_REPO="${GPU_RECOVERY_REPO:-}"
RECOVERY_REPO_URL="${GPU_RECOVERY_REPO_URL:-}"

echo "=== Installing macOS launchd GPU recovery agent ==="
echo "Repo root:     $REPO_ROOT"
echo "Script:        $SCRIPT"
echo "Daily time:    $DAILY_TIME"
echo "Recovery repo: ${RECOVERY_REPO:-<not set — will use server-setup submodule>}"

if [[ ! -f "$SCRIPT" ]]; then
  echo "ERROR: script not found at $SCRIPT"
  exit 1
fi

# --- Create launchd plist ---
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$PLIST_DIR/com.dana.gpu-recovery-report.plist"
mkdir -p "$PLIST_DIR"

# Convert 16:00 to launchd calendar format (Hour=16, Minute=0)
HOUR=$(echo "$DAILY_TIME" | cut -d: -f1)
MINUTE=$(echo "$DAILY_TIME" | cut -d: -f2)

cat >"$PLIST_FILE" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.dana.gpu-recovery-report</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$SCRIPT</string>
        <string>--daemon</string>
        <string>--daily-time</string>
        <string>$DAILY_TIME</string>
        <string>--retry-hours</string>
        <string>3</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>DANA_HOST_REPO</key>
        <string>$REPO_ROOT</string>
        <key>GPU_RECOVERY_REPO</key>
        <string>$RECOVERY_REPO</string>
        <key>GPU_RECOVERY_REPO_URL</key>
        <string>$RECOVERY_REPO_URL</string>
    </dict>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>$HOUR</integer>
        <key>Minute</key>
        <integer>$MINUTE</integer>
    </dict>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$HOME/Library/Logs/com.dana.gpu-recovery-report.out.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/Library/Logs/com.dana.gpu-recovery-report.err.log</string>
</dict>
</plist>
PLISTEOF

# --- Load the agent ---
launchctl unload "$PLIST_FILE" 2>/dev/null || true
launchctl load "$PLIST_FILE"

echo ""
echo "=== macOS launchd agent installed ==="
echo "Plist:    $PLIST_FILE"
echo "Schedule: Daily at $DAILY_TIME ($HOUR:$MINUTE)"
echo "Logs:     $HOME/Library/Logs/com.dana.gpu-recovery-report.{out,err}.log"
echo ""
echo "Check status with:"
echo "  launchctl list | grep gpu-recovery"
echo "  tail -f $HOME/Library/Logs/com.dana.gpu-recovery-report.out.log"
echo ""
echo "Reports will be pushed to:"
echo "  $RECOVERY_REPO (standalone repo — no Jenkins triggers)"
echo "  or fallback: components/server-setup/docs/ops/gpu-recover-reports/"