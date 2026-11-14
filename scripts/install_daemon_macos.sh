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
# The report script reads GPU_HEALTH_REPO / GPU_HEALTH_REPO_DIR / GPU_HEALTH_BRANCH
# and nothing else. This installer used to export GPU_RECOVERY_REPO(_URL), which
# no script in the repo reads, so a publish target set here was silently ignored
# and every run fell back to the default health-check repo.
HEALTH_REPO="${GPU_HEALTH_REPO:-https://github.com/AliNikkhah2001/Work_RAG_HealthCheck.git}"
HEALTH_REPO_DIR="${GPU_HEALTH_REPO_DIR:-$HOME/Work_RAG_HealthCheck}"
HEALTH_BRANCH="${GPU_HEALTH_BRANCH:-main}"

echo "=== Installing macOS launchd GPU recovery agent ==="
echo "Repo root:     $REPO_ROOT"
echo "Script:        $SCRIPT"
echo "Daily time:    $DAILY_TIME (local time)"
echo "Publish to:    $HEALTH_BRANCH → $HEALTH_REPO"

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
        <key>GPU_HEALTH_REPO</key>
        <string>$HEALTH_REPO</string>
        <key>GPU_HEALTH_REPO_DIR</key>
        <string>$HEALTH_REPO_DIR</string>
        <key>GPU_HEALTH_BRANCH</key>
        <string>$HEALTH_BRANCH</string>
        <key>GPU_MACHINE_NAME</key>
        <string>$(hostname -s 2>/dev/null || hostname)</string>
        <key>GPU_MACHINE_TYPE</key>
        <string>dev_laptop</string>
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

# --- Warn about TCC before arming --------------------------------------------
# macOS TCC gates ~/Documents, ~/Desktop and ~/Downloads per *executable*.
# launchd runs /bin/bash as a background item, which is not the app the user
# granted access to, so reading the report script out of ~/Documents fails with
# "Operation not permitted" and the agent exits 126 on every tick — silently,
# because the plist redirects output to a log nobody is watching. `ls`/`stat`
# still work, which is what makes this so easy to misdiagnose.
TCC_RISK=0
case "$SCRIPT" in
  "$HOME/Documents/"*|"$HOME/Desktop/"*|"$HOME/Downloads/"*) TCC_RISK=1 ;;
esac
if [[ "$TCC_RISK" -eq 1 ]]; then
  echo ""
  echo "WARNING: this repo lives under a TCC-protected folder:"
  echo "  $REPO_ROOT"
  echo ""
  echo "  launchd cannot read files there. Every scheduled run will fail with"
  echo "  'Operation not permitted' (exit 126) and write only to the err log."
  echo "  Fix by either:"
  echo "    a) granting Full Disk Access to /bin/bash (System Settings ->"
  echo "       Privacy & Security -> Full Disk Access), or"
  echo "    b) moving the clone outside ~/Documents, ~/Desktop, ~/Downloads"
  echo "       (e.g. ~/work/Work_Credit-RAG_Phase1) and re-running this script."
  echo ""
fi

# --- Load the agent ---
launchctl unload "$PLIST_FILE" 2>/dev/null || true
launchctl load "$PLIST_FILE"

echo ""
echo "=== macOS launchd agent installed ==="
echo "Plist:    $PLIST_FILE"
echo "Schedule: Daily at $DAILY_TIME ($HOUR:$MINUTE) LOCAL time"
echo "Logs:     $HOME/Library/Logs/com.dana.gpu-recovery-report.{out,err}.log"
echo ""
echo "Check status with:"
echo "  launchctl list | grep gpu-recovery"
echo "  tail -f $HOME/Library/Logs/com.dana.gpu-recovery-report.err.log"
echo ""
echo "Prove one run now (does not wait for the schedule):"
echo "  launchctl start com.dana.gpu-recovery-report"
echo ""
echo "Remove it again with:"
echo "  launchctl unload $PLIST_FILE && rm -f $PLIST_FILE"
echo ""
echo "Reports will be pushed to:"
echo "  $HEALTH_BRANCH → $HEALTH_REPO (standalone repo — no Jenkins triggers)"
echo ""
echo "Override on a re-install with:"
echo "  GPU_HEALTH_REPO=<url> GPU_HEALTH_BRANCH=main bash $0"
echo "  or fallback: components/server-setup/docs/ops/gpu-recover-reports/"