#!/usr/bin/env bash
# =============================================================================
# deploy/monitor/install.sh — Install the health-monitor daemon on a GPU host.
#
# What it installs
#   gpu-health-report.service   oneshot: run the report once, publish to main
#   gpu-health-report.timer     daily at 16:00 (configurable, with jitter)
#   gpu-health-retry.timer      every 3h: re-run ONLY if the daily run failed
#                               (OnFailure-style retry without a second daemon)
#
# Safe to re-run: unit files are rewritten and the timers re-armed. Use
# ./uninstall.sh to remove everything.
#
# Usage (on the GPU host, from the repo root):
#   sudo bash deploy/monitor/install.sh
#   sudo bash deploy/monitor/install.sh --daily-time 04:30 --machine-name gpu-prod
#   sudo bash deploy/monitor/install.sh --check            # validate the plan, change nothing
#   sudo bash deploy/monitor/install.sh --dry-run          # print units, change nothing
#   sudo bash deploy/monitor/install.sh --no-push          # collect locally only
#
# Exit codes: 0 ok, 1 --check failed, 2 bad arguments/missing file,
#              3 not a Linux/systemd host.
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPORT="$REPO_ROOT/scripts/gpu_full_recover_report.sh"

DAILY_TIME="16:00"
RETRY_HOURS=3
MACHINE_NAME=""
DRY_RUN=0
CHECK_ONLY=0
NO_PUSH=0
HEALTH_REPO="https://github.com/AliNikkhah2001/Work_RAG_HealthCheck.git"
HEALTH_REPO_DIR=""
SERVICE_NAME="gpu-health-report"
UNIT_DIR="${UNIT_DIR:-/etc/systemd/system}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { printf "%b[OK]%b   %s\n" "$GREEN" "$NC" "$*"; }
warn() { printf "%b[WARN]%b %s\n" "$YELLOW" "$NC" "$*"; }
fail() { printf "%b[FAIL]%b %s\n" "$RED" "$NC" "$*"; }
info() { printf "%b[INFO]%b %s\n" "$CYAN" "$NC" "$*"; }

usage() {
  sed -n '3,22p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --daily-time)     DAILY_TIME="$2"; shift 2 ;;
    --retry-hours)    RETRY_HOURS="$2"; shift 2 ;;
    --machine-name)   MACHINE_NAME="$2"; shift 2 ;;
    --health-repo)    HEALTH_REPO="$2"; shift 2 ;;
    --health-repo-dir) HEALTH_REPO_DIR="$2"; shift 2 ;;
    --no-push)        NO_PUSH=1; shift ;;
    --dry-run)        DRY_RUN=1; shift ;;
    --check)          CHECK_ONLY=1; shift ;;
    -h|--help)        usage; exit 0 ;;
    *) fail "Unknown option: $1"; usage; exit 2 ;;
  esac
done

# --- Validate environment ---------------------------------------------------
# --dry-run and --check are read-only previews: they print what would happen and
# never require root, systemd, or a Linux host, so an operator can validate the
# install on any machine before touching the GPU host.
PREVIEW=0
[[ "$DRY_RUN" -eq 1 || "$CHECK_ONLY" -eq 1 ]] && PREVIEW=1

if [[ "$(uname -s)" != "Linux" ]]; then
  if [[ "$PREVIEW" -eq 1 ]]; then
    warn "not a Linux host ($(uname -s)) — previewing the units without installing"
  else
    fail "This installer targets a Linux GPU host with systemd (got: $(uname -s))."
    echo "  On macOS use: bash scripts/install_daemon_macos.sh"
    exit 3
  fi
fi
if [[ "$PREVIEW" -eq 0 ]] && ! command -v systemctl >/dev/null 2>&1; then
  fail "systemctl not found — this host has no systemd"
  exit 3
fi
if [[ ! -f "$REPORT" ]]; then
  fail "report script missing: $REPORT"
  exit 2
fi
if [[ ! -x "$REPORT" ]]; then
  chmod +x "$REPORT" 2>/dev/null || true
fi
for helper in mark-result.sh should-retry.sh; do
  if [[ ! -f "$SCRIPT_DIR/$helper" ]]; then
    fail "helper missing: $SCRIPT_DIR/$helper (the units ExecStopPost/ExecCondition call it)"
    exit 2
  fi
done
if [[ "$PREVIEW" -eq 0 && "$EUID" -ne 0 ]]; then
  fail "run with sudo (needs to write $UNIT_DIR)"
  exit 2
fi

# Daily time must be HH:MM for OnCalendar
if ! [[ "$DAILY_TIME" =~ ^([01][0-9]|2[0-3]):[0-5][0-9]$ ]]; then
  fail "invalid --daily-time '$DAILY_TIME' (expected HH:MM, 24h)"
  exit 2
fi
if ! [[ "$RETRY_HOURS" =~ ^[0-9]+$ ]] || [[ "$RETRY_HOURS" -lt 1 ]]; then
  fail "invalid --retry-hours '$RETRY_HOURS' (expected a positive integer)"
  exit 2
fi

# --- Machine identity ------------------------------------------------------
# Reuse the SAME dev/prod classification the report script applies, so the
# dashboard cannot receive two different names for one host. Keep this in sync
# with the detection block in scripts/gpu_full_recover_report.sh:
#   Darwin                     -> dev_laptop
#   Debian/RHEL-family distro  -> production_gpu
#   NVIDIA tooling present     -> production_gpu
#   anything else              -> generic_linux
# Presence of docker is deliberately NOT a signal: every dev laptop has it.
detect_machine_type() {
  # An explicit override wins so the unit and the report cannot disagree.
  case "${GPU_MACHINE_TYPE:-}" in
    dev_laptop|production_gpu|generic_linux) echo "$GPU_MACHINE_TYPE"; return 0 ;;
  esac
  if [[ "$(uname -s)" == "Darwin" ]]; then
    echo "dev_laptop"
    return 0
  fi
  if [[ -f /etc/os-release ]] && grep -qiE 'ubuntu|centos|rhel|amzn|rocky|almalinux' /etc/os-release 2>/dev/null; then
    echo "production_gpu"
    return 0
  fi
  if [[ -n "${NVIDIA_VISIBLE_DEVICES:-}" ]] || command -v nvidia-smi >/dev/null 2>&1; then
    echo "production_gpu"
    return 0
  fi
  echo "generic_linux"
}
MACHINE_TYPE="$(detect_machine_type)"
[[ -z "$MACHINE_NAME" ]] && MACHINE_NAME="$(hostname -s 2>/dev/null || hostname)"
[[ -z "$HEALTH_REPO_DIR" ]] && HEALTH_REPO_DIR="${HEALTH_REPO_DIR:-/var/lib/dana-health/Work_RAG_HealthCheck}"

info "repo root:      $REPO_ROOT"
info "machine:        $MACHINE_NAME ($MACHINE_TYPE)"
info "daily time:     $DAILY_TIME UTC"
info "retry interval: every ${RETRY_HOURS}h while the day is failing"
info "publish:        $([ "$NO_PUSH" -eq 1 ] && echo 'disabled (--no-push)' || echo "main → $HEALTH_REPO")"
info "health clone:   $HEALTH_REPO_DIR"
echo ""

# Jitter keeps a fleet of hosts from pushing to main at the same instant.
JITTER_SEC="$(( RANDOM % 600 ))"

# --- Units -----------------------------------------------------------------
# Marker bookkeeping and the retry decision live in two small scripts
# (mark-result.sh, should-retry.sh) instead of quoted `sh -c` one-liners: the
# one-liner could not tell a *failure* apart from a *refusal*, so a bad
# GPU_HEALTH_REPO re-ran the same refusal every 3 hours forever.
SERVICE_UNIT="[Unit]
Description=Dana RAG health report (collect + publish to GitHub Pages)
Documentation=file://$SCRIPT_DIR/README.md
After=network-online.target docker.service
Wants=network-online.target
# Never let a failing report block the next scheduled attempt.
StartLimitIntervalSec=0

[Service]
Type=oneshot
User=root
WorkingDirectory=$REPO_ROOT
Environment=DANA_HOST_REPO=$REPO_ROOT
Environment=GPU_HEALTH_REPO=$HEALTH_REPO
Environment=GPU_HEALTH_REPO_DIR=$HEALTH_REPO_DIR
Environment=GPU_MACHINE_NAME=$MACHINE_NAME
Environment=GPU_MACHINE_TYPE=$MACHINE_TYPE
Environment=GPU_HEALTH_KEEP_LOGS=30
Environment=PYTHONUNBUFFERED=1
ExecStart=/bin/bash $REPORT --daemon --daily-time $DAILY_TIME --retry-hours $RETRY_HOURS --machine-name $MACHINE_NAME$([[ "$NO_PUSH" -eq 1 ]] && echo ' --no-push')
Nice=10
TimeoutStartSec=3600
StandardOutput=append:/var/log/dana-rag/health-report.log
StandardError=append:/var/log/dana-rag/health-report.err.log
# Records 0 / 1 / 64 so the retry gate can distinguish a retryable failure
# from a config error that must stop re-running.
ExecStopPost=/bin/bash $SCRIPT_DIR/mark-result.sh --rc \$EXIT_STATUS

[Install]
WantedBy=multi-user.target"

TIMER_UNIT="[Unit]
Description=Dana RAG health report — daily at $DAILY_TIME UTC

[Timer]
OnCalendar=*-*-* $DAILY_TIME:00 UTC
RandomizedDelaySec=$JITTER_SEC
Persistent=true
Unit=$SERVICE_NAME.service

[Install]
WantedBy=timers.target"

# Retry timer fires every N hours but the service's own state gate decides
# whether it actually runs the report (see gpu-health-retry.service below).
RETRY_SERVICE_UNIT="[Unit]
Description=Dana RAG health report — conditional retry
Documentation=file://$SCRIPT_DIR/README.md
After=network-online.target

[Service]
Type=oneshot
User=root
WorkingDirectory=$REPO_ROOT
Environment=DANA_HOST_REPO=$REPO_ROOT
Environment=GPU_HEALTH_REPO=$HEALTH_REPO
Environment=GPU_HEALTH_REPO_DIR=$HEALTH_REPO_DIR
Environment=GPU_MACHINE_NAME=$MACHINE_NAME
Environment=GPU_MACHINE_TYPE=$MACHINE_TYPE
# Only re-run when the last attempt genuinely failed (exit 1), when nothing has
# ever succeeded, or when today's daily run was missed. A *refused* run (exit 64)
# deliberately does NOT re-arm: retrying a bad GPU_HEALTH_REPO every 3h buries
# the single line an operator needs. Logic lives in should-retry.sh so it is
# testable and readable, and the markers are files (not transient unit results),
# so a reboot cannot silently swallow a failed day.
ExecCondition=/bin/bash $SCRIPT_DIR/should-retry.sh
ExecStart=/bin/bash $REPORT --daemon --daily-time $DAILY_TIME --retry-hours $RETRY_HOURS --machine-name $MACHINE_NAME$([[ "$NO_PUSH" -eq 1 ]] && echo ' --no-push')
Nice=10
TimeoutStartSec=3600
StandardOutput=append:/var/log/dana-rag/health-report.log
StandardError=append:/var/log/dana-rag/health-report.err.log
ExecStopPost=/bin/bash $SCRIPT_DIR/mark-result.sh --rc \$EXIT_STATUS"

RETRY_TIMER_UNIT="[Unit]
Description=Dana RAG health report — retry every ${RETRY_HOURS}h if today failed

[Timer]
# After boot plus the first offset, then every N hours. Persistent=true replays
# a tick missed while the host was down. AccuracySec=60s (not 1s) keeps a fleet
# from waking in lockstep.
OnBootSec=15min
OnUnitActiveSec=${RETRY_HOURS}h
AccuracySec=60s
Persistent=true
Unit=${SERVICE_NAME}-retry.service

[Install]
WantedBy=timers.target"

if [[ "$DRY_RUN" -eq 1 ]]; then
  warn "--dry-run: printing units, not writing anything"
  echo "===== $SERVICE_NAME.service ====="; echo "$SERVICE_UNIT"
  echo; echo "===== $SERVICE_NAME.timer ====="; echo "$TIMER_UNIT"
  echo; echo "===== $SERVICE_NAME-retry.service ====="; echo "$RETRY_SERVICE_UNIT"
  echo; echo "===== $SERVICE_NAME-retry.timer ====="; echo "$RETRY_TIMER_UNIT"
  echo
  info "would also run: systemctl daemon-reload && systemctl enable --now $SERVICE_NAME.timer ${SERVICE_NAME}-retry.timer"
  exit 0
fi

# --- --check: validate the plan without changing anything --------------------
# Everything here is read-only: assert the paths/units are coherent and that the
# retry gate behaves, so an operator can prove the machinery before enabling it.
if [[ "$CHECK_ONLY" -eq 1 ]]; then
  info "--check: validating the install plan (no changes made)"
  echo ""
  CHECK_FAIL=0
  chk() { # chk <ok-flag 0/1> <label> [detail]
    if [[ "$1" -eq 0 ]]; then
      ok "$2"
    else
      fail "$2${3:+ — $3}"
      CHECK_FAIL=$((CHECK_FAIL + 1))
    fi
  }

  [[ -f "$REPORT" && -r "$REPORT" ]] && chk 0 "report script readable" || chk 1 "report script readable" "$REPORT"
  bash -n "$REPORT" 2>/dev/null && chk 0 "report script parses (bash -n)" || chk 1 "report script parses"
  for helper in mark-result.sh should-retry.sh; do
    bash -n "$SCRIPT_DIR/$helper" 2>/dev/null \
      && chk 0 "$helper parses" || chk 1 "$helper parses"
  done
  # `.git` is a DIRECTORY in a normal clone but a FILE in a linked worktree,
  # submodule checkout and `--separate-git-dir` clone. Testing only for -d
  # reported "not a git checkout" on perfectly valid deployments (caught while
  # validating a promotion worktree). Ask git instead of inspecting the layout.
  if git -C "$REPO_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
    chk 0 "repo root is a git checkout"
  else
    chk 1 "repo root is a git checkout" "$REPO_ROOT"
  fi

  # Publishing must target the standalone health-check repo, never production.
  case "$(printf '%s' "$HEALTH_REPO" | tr 'A-Z' 'a-z')" in
    *healthcheck*) chk 0 "publish target is the health-check repo" ;;
    *) chk 1 "publish target is the health-check repo" "$HEALTH_REPO (must contain 'healthcheck')" ;;
  esac

  # Prove the retry gate: temp markers, no side effects on the real state dir.
  GATE_TMP="$(mktemp -d "${TMPDIR:-/tmp}/retry-gate.XXXXXX")" || GATE_TMP=""
  if [[ -n "$GATE_TMP" ]]; then
    if bash "$SCRIPT_DIR/should-retry.sh" --quiet --state-dir "$GATE_TMP"; then
      chk 0 "retry gate runs when nothing has succeeded yet"
    else
      chk 1 "retry gate runs when nothing has succeeded yet"
    fi
    bash "$SCRIPT_DIR/mark-result.sh" --rc 0 --state-dir "$GATE_TMP"
    if bash "$SCRIPT_DIR/should-retry.sh" --quiet --state-dir "$GATE_TMP"; then
      chk 1 "retry gate is idle after today's success"
    else
      chk 0 "retry gate is idle after today's success"
    fi
    bash "$SCRIPT_DIR/mark-result.sh" --rc 1 --state-dir "$GATE_TMP"
    if bash "$SCRIPT_DIR/should-retry.sh" --quiet --state-dir "$GATE_TMP"; then
      chk 0 "retry gate re-runs after a genuine failure (exit 1)"
    else
      chk 1 "retry gate re-runs after a genuine failure (exit 1)"
    fi
    rm -f "$GATE_TMP/last-success"
    bash "$SCRIPT_DIR/mark-result.sh" --rc 64 --state-dir "$GATE_TMP"
    if bash "$SCRIPT_DIR/should-retry.sh" --quiet --state-dir "$GATE_TMP"; then
      chk 1 "retry gate does NOT stampede on a refusal (exit 64)"
    else
      chk 0 "retry gate does NOT stampede on a refusal (exit 64)"
    fi
    rm -rf "$GATE_TMP"
  fi

  echo ""
  if [[ "$CHECK_FAIL" -eq 0 ]]; then
    ok "install plan is coherent — run without --check to install"
    exit 0
  fi
  fail "$CHECK_FAIL check(s) failed — fix them before installing"
  exit 1
fi

# --- Install ---------------------------------------------------------------
install -d -m 0755 /var/log/dana-rag /var/lib/dana-health "$UNIT_DIR"

printf '%s\n' "$SERVICE_UNIT"       > "$UNIT_DIR/$SERVICE_NAME.service"
printf '%s\n' "$TIMER_UNIT"         > "$UNIT_DIR/$SERVICE_NAME.timer"
printf '%s\n' "$RETRY_SERVICE_UNIT" > "$UNIT_DIR/$SERVICE_NAME-retry.service"
printf '%s\n' "$RETRY_TIMER_UNIT"   > "$UNIT_DIR/$SERVICE_NAME-retry.timer"
chmod 0644 "$UNIT_DIR/$SERVICE_NAME"*.service "$UNIT_DIR/$SERVICE_NAME"*.timer
ok "wrote 4 unit files to $UNIT_DIR"

# Prime the health repo clone so the first run does not pay clone cost while
# services are flapping. Non-fatal: the publisher clones on demand too.
if [[ "$NO_PUSH" -eq 0 ]] && command -v git >/dev/null 2>&1; then
  if [[ ! -d "$HEALTH_REPO_DIR/.git" ]]; then
    if git clone "$HEALTH_REPO" "$HEALTH_REPO_DIR" >/dev/null 2>&1; then
      git -C "$HEALTH_REPO_DIR" checkout main >/dev/null 2>&1 \
        || git -C "$HEALTH_REPO_DIR" checkout -B main >/dev/null 2>&1 \
        || true
      ok "cloned health repo → $HEALTH_REPO_DIR"
    else
      warn "could not pre-clone $HEALTH_REPO (the publisher will retry at run time)"
    fi
  else
    ok "health repo already cloned at $HEALTH_REPO_DIR"
  fi
fi

systemctl daemon-reload || { fail "systemctl daemon-reload failed"; exit 1; }
systemctl enable --now "$SERVICE_NAME.timer" >/dev/null 2>&1 \
  && ok "enabled $SERVICE_NAME.timer" \
  || { fail "could not enable $SERVICE_NAME.timer"; exit 1; }
systemctl enable --now "$SERVICE_NAME-retry.timer" >/dev/null 2>&1 \
  && ok "enabled $SERVICE_NAME-retry.timer (every ${RETRY_HOURS}h)" \
  || warn "could not enable $SERVICE_NAME-retry.timer"

echo ""
echo "=== Installed ==="
echo "  Daily:   $DAILY_TIME UTC (+ up to 10 min jitter)"
echo "  Retry:   every ${RETRY_HOURS}h while today's run is missing or failing"
echo "  Logs:    tail -f /var/log/dana-rag/health-report.log"
echo "  Status:  systemctl list-timers '$SERVICE_NAME*'"
echo "  Run now: sudo systemctl start $SERVICE_NAME.service"
echo ""
echo "  Dashboard: https://alinikkhah2001.github.io/Work_RAG_HealthCheck/"
echo "  (run scripts/enable_pages.sh once from your laptop to publish it)"
echo ""
echo "  Uninstall: sudo bash $SCRIPT_DIR/uninstall.sh"
