#!/usr/bin/env bash
# =============================================================================
# deploy/heal/install.sh — Install the self-heal daemon (reconcile) on a GPU host.
#
# What it installs
#   dana-gpu-reconcile.service   oneshot: verify published ports, heal towards
#                                the recorded last-known-good if red
#   dana-gpu-reconcile.timer     hourly wake + daily full check (04:10),
#                                3h retry while unhealthy, Persistent=true
#
# Why a separate installer from deploy/monitor/install.sh
#   The monitor reports; this repairs. They have different failure semantics:
#   the monitor must retry a failed report, while the heal path must NOT
#   stampede (reconcile.sh gates itself on schedule.next_retry_at in the state
#   file, so the hourly timer is a no-op unless a retry is actually due).
#
# The checked-in units under deploy/gpu/systemd/ hardcode
# /workspace/Work_Credit-RAG_Phase1. That is correct on the reference host and
# wrong everywhere else, so this installer renders the SAME unit content with
# this checkout's real path. Re-run it after moving the checkout.
#
# Usage (on the GPU host, from the repo root):
#   sudo bash deploy/heal/install.sh
#   sudo bash deploy/heal/install.sh --check        # validate the plan only
#   sudo bash deploy/heal/install.sh --dry-run      # print the units
#   sudo bash deploy/heal/install.sh --retry-hours 2
#
# Exit codes: 0 ok, 1 --check failed, 2 bad args / missing file,
#              3 not a Linux/systemd host, 64 refused (dev host, not prod).
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RECONCILE="$REPO_ROOT/deploy/gpu/reconcile.sh"

SERVICE_NAME="dana-gpu-reconcile"
UNIT_DIR="${UNIT_DIR:-/etc/systemd/system}"
RETRY_HOURS="${DANA_RETRY_HOURS:-3}"
DAILY_TIME="${DANA_DAILY_CHECK:-04:10}"
PROFILE="${DANA_PROFILE:-gpu}"
DRY_RUN=0
CHECK_ONLY=0
ALLOW_DEV=0

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { printf "%b[OK]%b   %s\n" "$GREEN" "$NC" "$*"; }
warn() { printf "%b[WARN]%b %s\n" "$YELLOW" "$NC" "$*"; }
fail() { printf "%b[FAIL]%b %s\n" "$RED" "$NC" "$*"; }
info() { printf "%b[INFO]%b %s\n" "$CYAN" "$NC" "$*"; }

usage() { sed -n '3,26p' "$0" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --retry-hours)  RETRY_HOURS="$2"; shift 2 ;;
    --daily-time)   DAILY_TIME="$2"; shift 2 ;;
    --profile)      PROFILE="$2"; shift 2 ;;
    --allow-dev)    ALLOW_DEV=1; shift ;;
    --dry-run)      DRY_RUN=1; shift ;;
    --check)        CHECK_ONLY=1; shift ;;
    -h|--help)      usage; exit 0 ;;
    *) fail "Unknown option: $1"; usage; exit 2 ;;
  esac
done

PREVIEW=0
[[ "$DRY_RUN" -eq 1 || "$CHECK_ONLY" -eq 1 ]] && PREVIEW=1

if [[ "$(uname -s)" != "Linux" ]]; then
  if [[ "$PREVIEW" -eq 1 ]]; then
    warn "not a Linux host ($(uname -s)) — previewing without installing"
  else
    fail "the heal daemon targets a Linux systemd host (got: $(uname -s))"
    exit 3
  fi
fi
if [[ "$PREVIEW" -eq 0 ]] && ! command -v systemctl >/dev/null 2>&1; then
  fail "systemctl not found — this host has no systemd"
  exit 3
fi
if [[ ! -f "$RECONCILE" ]]; then
  fail "reconcile script missing: $RECONCILE"
  exit 2
fi
if [[ ! "$RETRY_HOURS" =~ ^[0-9]+$ ]] || [[ "$RETRY_HOURS" -lt 1 ]]; then
  fail "invalid --retry-hours '$RETRY_HOURS'"
  exit 2
fi
if ! [[ "$DAILY_TIME" =~ ^([01][0-9]|2[0-3]):[0-5][0-9]$ ]]; then
  fail "invalid --daily-time '$DAILY_TIME' (expected HH:MM)"
  exit 2
fi

# The heal path is only meaningful on a host that actually runs the stack. Running
# it on a laptop would "heal" towards a stack that does not exist there, so it
# refuses unless the operator says --allow-dev explicitly.
MACHINE_TYPE="generic_linux"
if [[ "$(uname -s)" == "Darwin" ]]; then
  MACHINE_TYPE="dev_laptop"
elif [[ -f /etc/os-release ]] && grep -qiE 'ubuntu|centos|rhel|amzn|rocky|almalinux' /etc/os-release 2>/dev/null; then
  MACHINE_TYPE="production_gpu"
elif [[ -n "${NVIDIA_VISIBLE_DEVICES:-}" ]] || command -v nvidia-smi >/dev/null 2>&1; then
  MACHINE_TYPE="production_gpu"
fi

info "repo root:      $REPO_ROOT"
info "machine:        $MACHINE_TYPE"
info "profile:        $PROFILE"
info "retry interval: every ${RETRY_HOURS}h while unhealthy (state-gated)"
info "daily deep check: $DAILY_TIME host-local"
echo ""

if [[ "$MACHINE_TYPE" == "dev_laptop" && "$ALLOW_DEV" -eq 0 ]]; then
  fail "refusing to install the heal daemon on a dev laptop (use --allow-dev to override)"
  exit 64
fi

# --- Legacy healer conflict --------------------------------------------------
# scripts/gpu_auto_heal.{service,timer} is the PREVIOUS self-heal daemon. It
# restarts services it thinks are broken on a fixed interval and knows nothing
# about last-known-good, so running it alongside reconcile means two processes
# racing to "fix" the same stack, one of them rolling back to a known-good
# image while the other restarts whatever the working tree says. The outage this
# layer was written to stop was caused by exactly that kind of blind healing.
LEGACY_HEAL_STATE="absent"
if [[ "$MACHINE_TYPE" != "dev_laptop" ]] && command -v systemctl >/dev/null 2>&1; then
  if systemctl is-enabled --quiet gpu_auto_heal.timer 2>/dev/null \
     || systemctl is-active --quiet gpu_auto_heal.timer 2>/dev/null \
     || systemctl is-enabled --quiet gpu_auto_heal.service 2>/dev/null; then
    LEGACY_HEAL_STATE="active"
  fi
fi
if [[ "$LEGACY_HEAL_STATE" == "active" ]]; then
  warn "legacy healer detected: gpu_auto_heal.{service,timer} is enabled/active"
  warn "  it restarts services blindly and has no last-known-good concept"
  warn "  disable it before installing the reconcile daemon, or they will fight:"
  warn "    sudo systemctl disable --now gpu_auto_heal.timer gpu_auto_heal.service"
  if [[ "${DANA_ALLOW_LEGACY_HEAL:-0}" != "1" ]]; then
    fail "refusing to install two self-healers (set DANA_ALLOW_LEGACY_HEAL=1 to override)"
    exit 64
  fi
  warn "DANA_ALLOW_LEGACY_HEAL=1 — continuing anyway"
fi

# --- Units -----------------------------------------------------------------
SERVICE_UNIT="# Generated by deploy/heal/install.sh — re-run the installer instead of
# editing this file. Mirrors deploy/gpu/systemd/dana-gpu-reconcile.service.
[Unit]
Description=Dana GPU RAG reconcile (verify published ports, heal to last-known-good)
Documentation=file://$REPO_ROOT/deploy/gpu/README.md
After=docker.service network-online.target
Wants=network-online.target docker.service

[Service]
Type=oneshot
User=root
WorkingDirectory=$REPO_ROOT
Environment=DANA_HOST_REPO=$REPO_ROOT
Environment=DANA_HOST=gpu
Environment=DANA_ROLE=prod
Environment=DANA_PROFILE=$PROFILE
Environment=DANA_RETRY_HOURS=$RETRY_HOURS
ExecStart=/bin/bash $RECONCILE --profile $PROFILE
# The exit code is the signal this unit exists to emit. 64 means the probe was
# refused (bad layering or a leaked override), which is NOT an outage, so it must
# not fail the unit and must not trigger a rollback. reconcile.sh decides.
SuccessExitStatus=0 64
TimeoutStartSec=1800
Nice=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target"

TIMER_UNIT="# Generated by deploy/heal/install.sh
[Unit]
Description=Dana GPU RAG reconcile: hourly wake + daily full check, ${RETRY_HOURS}h retry on failure
Documentation=file://$REPO_ROOT/deploy/gpu/README.md

[Timer]
# Hourly wake-up. reconcile.sh decides whether it is DUE using
# schedule.next_retry_at in the state file, so this timer cannot stampede: a
# healthy stack skips every tick except the daily deep check, and an unhealthy
# one re-checks at most every ${RETRY_HOURS}h.
OnCalendar=hourly
OnCalendar=*-*-* $DAILY_TIME:00
Persistent=true
RandomizedDelaySec=300
AccuracySec=1min
Unit=$SERVICE_NAME.service

[Install]
WantedBy=timers.target"

if [[ "$DRY_RUN" -eq 1 ]]; then
  warn "--dry-run: printing units, not writing anything"
  echo "===== $SERVICE_NAME.service ====="; echo "$SERVICE_UNIT"
  echo; echo "===== $SERVICE_NAME.timer ====="; echo "$TIMER_UNIT"
  echo
  info "would also run: systemctl daemon-reload && systemctl enable --now $SERVICE_NAME.timer"
  exit 0
fi

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  info "--check: validating the install plan (no changes made)"
  echo ""
  CHECK_FAIL=0
  chk() { if [[ "$1" -eq 0 ]]; then ok "$2"; else fail "$2${3:+ — $3}"; CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }

  bash -n "$RECONCILE" 2>/dev/null && chk 0 "reconcile.sh parses" || chk 1 "reconcile.sh parses"
  [[ -r "$REPO_ROOT/deploy/gpu/lib/common.sh" ]] \
    && chk 0 "deploy/gpu/lib/common.sh present" \
    || chk 1 "deploy/gpu/lib/common.sh present"
  [[ -r "$REPO_ROOT/deploy/gpu/lib/state.py" ]] \
    && chk 0 "deploy/gpu/lib/state.py present" \
    || chk 1 "deploy/gpu/lib/state.py present"
  # The heal path heals towards last-known-good; with no state file it can only
  # bootstrap a fresh deploy, which is a different and riskier action.
  STATE_FILE="${DANA_STATE_FILE:-$REPO_ROOT/deploy/gpu/state/last_good.json}"
  if [[ -f "$STATE_FILE" ]]; then
    chk 0 "last-known-good state present (heal can restore, not just bootstrap)"
  else
    warn "no last-known-good state at $STATE_FILE — the first heal attempt would bootstrap a deploy"
  fi
  # Exactly one overlay must be layered on base (the portless-base trap).
  case "$PROFILE" in
    gpu|prod-sim|stage|local|host) chk 0 "profile '$PROFILE' is known" ;;
    *) chk 1 "profile '$PROFILE' is known" ;;
  esac
  # A refusal must not be treated as an outage.
  grep -q 'SuccessExitStatus=0 64' <<<"$SERVICE_UNIT" \
    && chk 0 "unit does not treat exit 64 (refused) as a failure" \
    || chk 1 "unit does not treat exit 64 (refused) as a failure"

  echo ""
  if [[ "$CHECK_FAIL" -eq 0 ]]; then
    ok "heal install plan is coherent — run without --check to install"
    exit 0
  fi
  fail "$CHECK_FAIL check(s) failed"
  exit 1
fi

if [[ "$EUID" -ne 0 ]]; then
  fail "run with sudo (needs to write $UNIT_DIR)"
  exit 2
fi

# --- Install ---------------------------------------------------------------
install -d -m 0755 "$UNIT_DIR" /var/log/dana-rag
printf '%s\n' "$SERVICE_UNIT" >"$UNIT_DIR/$SERVICE_NAME.service"
printf '%s\n' "$TIMER_UNIT"   >"$UNIT_DIR/$SERVICE_NAME.timer"
chmod 0644 "$UNIT_DIR/$SERVICE_NAME.service" "$UNIT_DIR/$SERVICE_NAME.timer"
ok "wrote 2 unit files to $UNIT_DIR"

systemctl daemon-reload || { fail "systemctl daemon-reload failed"; exit 1; }
systemctl enable --now "$SERVICE_NAME.timer" >/dev/null 2>&1 \
  && ok "enabled $SERVICE_NAME.timer" \
  || { fail "could not enable $SERVICE_NAME.timer"; exit 1; }

echo ""
echo "=== Installed ==="
echo "  Wake:    hourly; reconcile.sh no-ops unless schedule.next_retry_at is due"
echo "  Retry:   every ${RETRY_HOURS}h while unhealthy (state-gated, cannot stampede)"
echo "  Deep:    daily at $DAILY_TIME host-local"
echo "  Status:  systemctl list-timers '$SERVICE_NAME*'"
echo "  Run now: sudo systemctl start $SERVICE_NAME.service"
echo "  Logs:    journalctl -u $SERVICE_NAME.service -n 100 --no-pager"
echo "           /var/log/dana-rag/reconcile.log"
echo ""
echo "  Uninstall: sudo bash $SCRIPT_DIR/uninstall.sh"
