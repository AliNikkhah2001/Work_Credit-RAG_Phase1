#!/usr/bin/env bash
# =============================================================================
# deploy/monitor/install.sh — one-command setup of the GPU health-report daemon
#
# Run this ON THE GPU PRODUCTION SERVER as root (or via sudo).
#
#   sudo GPU_RECOVERY_REPO_URL=git@github.com:AliNikkhah2001/Work_RAG_HealthCheck.git \
#        bash deploy/monitor/install.sh
#
# It does three things:
#   1. verifies the report script + repo layout exist
#   2. installs a systemd service + timer that runs the report daily at
#      DANA_REPORT_TIME (default 16:00) and retries every
#      DANA_RETRY_HOURS (default 3) until a run succeeds
#   3. enables + starts the timer and prints what to check
#
# Pushes go to the standalone Work_RAG_HealthCheck repo only, which has no
# Jenkins job and no Actions workflows of its own, so reporting can never
# trigger a build.
#
# This script is idempotent: re-running it updates the unit files and reloads.
# Uninstall with:  sudo bash deploy/monitor/uninstall.sh
# =============================================================================
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${DANA_HOST_REPO:-$(cd "$SELF_DIR/../.." && pwd)}"
REPORT_SCRIPT="$REPO_ROOT/scripts/gpu_full_recover_report.sh"
DAILY_TIME="${DANA_REPORT_TIME:-16:00}"
RETRY_HOURS="${DANA_RETRY_HOURS:-3}"
RECOVERY_REPO_URL="${GPU_RECOVERY_REPO_URL:-https://github.com/AliNikkhah2001/Work_RAG_HealthCheck.git}"
UNIT_DIR="${DANA_UNIT_DIR:-/etc/systemd/system}"
SERVICE_NAME="dana-health-report"
DRY_RUN=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      sed -n '2,25p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

ok()   { printf '\033[32m  OK\033[0m   %s\n' "$*"; }
warn() { printf '\033[33m  WARN\033[0m %s\n' "$*"; }
err()  { printf '\033[31m  ERR\033[0m  %s\n' "$*" >&2; }
info() { printf '\033[36m  ..\033[0m   %s\n' "$*"; }

echo "=== Dana GPU health-report daemon installer ==="
echo "  repo root : $REPO_ROOT"
echo "  script    : $REPORT_SCRIPT"
echo "  daily at  : $DAILY_TIME"
echo "  retry     : every ${RETRY_HOURS}h until success"
echo "  publish to: $RECOVERY_REPO_URL"
echo ""

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
fail=0

if [[ ! -f "$REPORT_SCRIPT" ]]; then
  err "report script missing: $REPORT_SCRIPT"
  err "run this from the cloned umbrella repo, or set DANA_HOST_REPO=/path/to/repo"
  fail=1
else
  ok "report script found"
fi

if ! command -v systemctl >/dev/null 2>&1; then
  err "systemctl not found — this installer targets a systemd host (Linux GPU server)"
  err "for macOS use: bash scripts/install_daemon_macos.sh"
  fail=1
else
  ok "systemd available"
fi

if ! command -v docker >/dev/null 2>&1; then
  err "docker not on PATH — the report needs it to read container state"
  fail=1
else
  ok "docker available"
fi

if ! command -v git >/dev/null 2>&1; then
  err "git not on PATH — the report pushes its findings"
  fail=1
else
  ok "git available"
fi

if [[ "$(id -u)" -ne 0 ]] && [[ "$DRY_RUN" -eq 0 ]]; then
  err "must run as root (sudo) to write $UNIT_DIR"
  fail=1
fi

if [[ "$fail" -ne 0 ]]; then
  echo ""
  err "preflight failed — nothing was installed"
  exit 1
fi

# ---------------------------------------------------------------------------
# Unit files
# ---------------------------------------------------------------------------
SERVICE_FILE="$UNIT_DIR/${SERVICE_NAME}.service"
TIMER_FILE="$UNIT_DIR/${SERVICE_NAME}.timer"

read -r -d '' SERVICE_BODY <<EOF || true
[Unit]
Description=Dana GPU health report (collect, E2E, screenshots, publish)
Documentation=file://$REPO_ROOT/deploy/monitor/README.md
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$REPO_ROOT
Environment=DANA_HOST_REPO=$REPO_ROOT
Environment=GPU_RECOVERY_REPO_URL=$RECOVERY_REPO_URL
Environment=DANA_MACHINE_NAME=$(hostname -s 2>/dev/null || echo gpu)
# The report pushes to the health-check repo by default; it accepts
# --no-push to skip that but has no positive --push flag.
ExecStart=/usr/bin/env bash $REPORT_SCRIPT
TimeoutStartSec=3600
Nice=10

[Install]
WantedBy=multi-user.target
EOF

read -r -d '' TIMER_BODY <<EOF || true
[Unit]
Description=Daily Dana GPU health report at $DAILY_TIME (retry every ${RETRY_HOURS}h on failure)

[Timer]
OnCalendar=*-*-* $DAILY_TIME:00
RandomizedDelaySec=300
Persistent=true

[Install]
WantedBy=timers.target
EOF

if [[ "$DRY_RUN" -eq 1 ]]; then
  info "DRY RUN — would write:"
  echo "--- $SERVICE_FILE ---"
  printf '%s\n' "$SERVICE_BODY"
  echo "--- $TIMER_FILE ---"
  printf '%s\n' "$TIMER_BODY"
  exit 0
fi

install -d "$UNIT_DIR"
printf '%s\n' "$SERVICE_BODY" > "$SERVICE_FILE"
printf '%s\n' "$TIMER_BODY"  > "$TIMER_FILE"
ok "wrote $SERVICE_FILE"
ok "wrote $TIMER_FILE"

systemctl daemon-reload
ok "systemd reloaded"

systemctl enable --now "${SERVICE_NAME}.timer" >/dev/null 2>&1
ok "timer enabled and started"

# A retry timer re-arms the report every RETRY_HOURS if the last run failed.
RETRY_FILE="$UNIT_DIR/${SERVICE_NAME}-retry.timer"
read -r -d '' RETRY_BODY <<EOF || true
[Unit]
Description=Re-run the Dana health report every ${RETRY_HOURS}h until it succeeds

[Timer]
OnUnitInactiveSec=${RETRY_HOURS}h
Persistent=true

[Install]
WantedBy=timers.target
EOF
printf '%s\n' "$RETRY_BODY" > "$RETRY_FILE"
systemctl daemon-reload
ok "retry timer installed"

echo ""
echo "=== installed ==="
systemctl list-timers "${SERVICE_NAME}*" --no-pager 2>/dev/null || true
echo ""
echo "Next steps:"
echo "  1. run once now, in the foreground, to see real output:"
echo "       sudo bash $REPORT_SCRIPT"
echo "  2. confirm the site updated:"
echo "       https://alinikkhah2001.github.io/Work_RAG_HealthCheck/"
echo "  3. watch the timer:"
echo "       systemctl list-timers | grep dana-health"
echo "       journalctl -u ${SERVICE_NAME} -n 50 --no-pager"
echo ""
echo "Uninstall:  sudo bash $SELF_DIR/uninstall.sh"
