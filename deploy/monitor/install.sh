#!/usr/bin/env bash
# =============================================================================
# deploy/monitor/install.sh — Install the health-monitor daemon on a GPU host.
#
# What it installs
#   gpu-health-report.service   oneshot: run the report once, publish to main
#   gpu-health-report.timer     every INTERVAL_HOURS (default 1h) — primary cadence
#   gpu-health-retry.timer      every RETRY_HOURS: re-run ONLY if the last run failed
#                               (OnFailure-style retry without a second daemon)
#   Optional: --daily-time also arms a calendar timer in addition to the interval
#
# Publishes into Work_RAG_HealthCheck (Pages) and appends compact JSON into
# Work_RAG_Metrics. Screenshots are age+count pruned so hourly pushes stay
# under GitHub storage / rate pressure.
#
# Safe to re-run: unit files are rewritten and the timers re-armed. Use
# ./uninstall.sh to remove everything.
#
# Usage (on the GPU host, from the repo root):
#   sudo bash deploy/monitor/install.sh
#   sudo bash deploy/monitor/install.sh --interval-hours 1 --machine-name gpu-prod
#   sudo bash deploy/monitor/install.sh --daily-time 04:30 --interval-hours 1
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

DAILY_TIME=""
INTERVAL_HOURS=1
RETRY_HOURS=1
MACHINE_NAME=""
DRY_RUN=0
CHECK_ONLY=0
NO_PUSH=0
HEALTH_REPO="https://github.com/AliNikkhah2001/Work_RAG_HealthCheck.git"
HEALTH_REPO_DIR=""
METRICS_REPO="https://github.com/AliNikkhah2001/Work_RAG_Metrics.git"
METRICS_REPO_DIR=""
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
    --interval-hours) INTERVAL_HOURS="$2"; shift 2 ;;
    --retry-hours)    RETRY_HOURS="$2"; shift 2 ;;
    --machine-name)   MACHINE_NAME="$2"; shift 2 ;;
    --health-repo)    HEALTH_REPO="$2"; shift 2 ;;
    --health-repo-dir) HEALTH_REPO_DIR="$2"; shift 2 ;;
    --metrics-repo)   METRICS_REPO="$2"; shift 2 ;;
    --metrics-repo-dir) METRICS_REPO_DIR="$2"; shift 2 ;;
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

# Optional daily calendar time (HH:MM); primary cadence is INTERVAL_HOURS.
if [[ -n "$DAILY_TIME" ]] && ! [[ "$DAILY_TIME" =~ ^([01][0-9]|2[0-3]):[0-5][0-9]$ ]]; then
  fail "invalid --daily-time '$DAILY_TIME' (expected HH:MM, 24h)"
  exit 2
fi
if ! [[ "$INTERVAL_HOURS" =~ ^[0-9]+$ ]] || [[ "$INTERVAL_HOURS" -lt 1 ]]; then
  fail "invalid --interval-hours '$INTERVAL_HOURS' (expected a positive integer)"
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
[[ -z "$METRICS_REPO_DIR" ]] && METRICS_REPO_DIR="${METRICS_REPO_DIR:-/var/lib/dana-health/Work_RAG_Metrics}"

info "repo root:      $REPO_ROOT"
info "machine:        $MACHINE_NAME ($MACHINE_TYPE)"
info "interval:       every ${INTERVAL_HOURS}h (primary)"
info "daily time:     ${DAILY_TIME:-disabled} UTC"
info "retry interval: every ${RETRY_HOURS}h while the last run is failing"
info "publish:        $([ "$NO_PUSH" -eq 1 ] && echo 'disabled (--no-push)' || echo "main → $HEALTH_REPO")"
info "metrics:        $([ "$NO_PUSH" -eq 1 ] && echo 'disabled (--no-push)' || echo "main → $METRICS_REPO")"
info "health clone:   $HEALTH_REPO_DIR"
info "metrics clone:  $METRICS_REPO_DIR"
echo ""

# Jitter keeps a fleet of hosts from pushing to main at the same instant.
JITTER_SEC="$(( RANDOM % 600 ))"
DAILY_ARG=""
[[ -n "$DAILY_TIME" ]] && DAILY_ARG=" --daily-time $DAILY_TIME"


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
Environment=GPU_METRICS_REPO=$METRICS_REPO
Environment=GPU_METRICS_REPO_DIR=$METRICS_REPO_DIR
Environment=GPU_MACHINE_NAME=$MACHINE_NAME
Environment=GPU_MACHINE_TYPE=$MACHINE_TYPE
Environment=GPU_HEALTH_KEEP_LOGS=48
Environment=PYTHONUNBUFFERED=1
ExecStart=/bin/bash $REPORT --daemon$DAILY_ARG --retry-hours $RETRY_HOURS --machine-name $MACHINE_NAME$([[ "$NO_PUSH" -eq 1 ]] && echo ' --no-push')
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
Description=Dana RAG health report — every ${INTERVAL_HOURS}h

[Timer]
OnBootSec=5min
OnUnitActiveSec=${INTERVAL_HOURS}h
RandomizedDelaySec=$JITTER_SEC
AccuracySec=60s
Persistent=true
Unit=$SERVICE_NAME.service

[Install]
WantedBy=timers.target"

# Optional extra calendar tick (in addition to the interval timer).
DAILY_TIMER_UNIT=""
if [[ -n "$DAILY_TIME" ]]; then
DAILY_TIMER_UNIT="[Unit]
Description=Dana RAG health report — daily at $DAILY_TIME UTC

[Timer]
OnCalendar=*-*-* $DAILY_TIME:00 UTC
RandomizedDelaySec=$JITTER_SEC
Persistent=true
Unit=$SERVICE_NAME.service

[Install]
WantedBy=timers.target"
fi


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
Environment=GPU_METRICS_REPO=$METRICS_REPO
Environment=GPU_METRICS_REPO_DIR=$METRICS_REPO_DIR
Environment=GPU_MACHINE_NAME=$MACHINE_NAME
Environment=GPU_MACHINE_TYPE=$MACHINE_TYPE
Environment=GPU_HEALTH_KEEP_LOGS=48
# Only re-run when the last attempt genuinely failed (exit 1), when nothing has
# ever succeeded, or when today's daily run was missed. A *refused* run (exit 64)
# deliberately does NOT re-arm: retrying a bad GPU_HEALTH_REPO every 1h buries
# the single line an operator needs. Logic lives in should-retry.sh so it is
# testable and readable, and the markers are files (not transient unit results),
# so a reboot cannot silently swallow a failed day.
ExecCondition=/bin/bash $SCRIPT_DIR/should-retry.sh
ExecStart=/bin/bash $REPORT --daemon$DAILY_ARG --retry-hours $RETRY_HOURS --machine-name $MACHINE_NAME$([[ "$NO_PUSH" -eq 1 ]] && echo ' --no-push')
Nice=10
TimeoutStartSec=3600
StandardOutput=append:/var/log/dana-rag/health-report.log
StandardError=append:/var/log/dana-rag/health-report.err.log
ExecStopPost=/bin/bash $SCRIPT_DIR/mark-result.sh --rc \$EXIT_STATUS"

RETRY_TIMER_UNIT="[Unit]
Description=Dana RAG health report — retry every ${RETRY_HOURS}h if last run failed

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
  if [[ -n "$DAILY_TIMER_UNIT" ]]; then
    echo; echo "===== $SERVICE_NAME-daily.timer ====="; echo "$DAILY_TIMER_UNIT"
  fi
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
  case "$(printf '%s' "$METRICS_REPO" | tr 'A-Z' 'a-z')" in
    *metric*) chk 0 "metrics target is a metrics repo" ;;
    *) chk 1 "metrics target is a metrics repo" "$METRICS_REPO (must contain 'metric')" ;;
  esac
  [[ -f "$REPO_ROOT/scripts/monitor/publish_metrics.py" ]] \
    && chk 0 "publish_metrics.py present" \
    || chk 1 "publish_metrics.py present"

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
UNIT_COUNT=4
if [[ -n "$DAILY_TIMER_UNIT" ]]; then
  printf '%s\n' "$DAILY_TIMER_UNIT" > "$UNIT_DIR/$SERVICE_NAME-daily.timer"
  UNIT_COUNT=$((UNIT_COUNT + 1))
fi
chmod 0644 "$UNIT_DIR/$SERVICE_NAME"*.service "$UNIT_DIR/$SERVICE_NAME"*.timer
ok "wrote $UNIT_COUNT unit files to $UNIT_DIR"


# Prime the health + metrics repo clones so the first run does not pay clone
# cost while services are flapping. Non-fatal: publishers clone on demand too.
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
  if [[ ! -d "$METRICS_REPO_DIR/.git" ]]; then
    if git clone "$METRICS_REPO" "$METRICS_REPO_DIR" >/dev/null 2>&1; then
      git -C "$METRICS_REPO_DIR" checkout main >/dev/null 2>&1 \
        || git -C "$METRICS_REPO_DIR" checkout -B main >/dev/null 2>&1 \
        || true
      ok "cloned metrics repo → $METRICS_REPO_DIR"
    else
      warn "could not pre-clone $METRICS_REPO (the metrics publisher will retry at run time)"
    fi
  else
    ok "metrics repo already cloned at $METRICS_REPO_DIR"
  fi
fi

systemctl daemon-reload || { fail "systemctl daemon-reload failed"; exit 1; }
systemctl enable --now "$SERVICE_NAME.timer" >/dev/null 2>&1 \
  && ok "enabled $SERVICE_NAME.timer (every ${INTERVAL_HOURS}h)" \
  || { fail "could not enable $SERVICE_NAME.timer"; exit 1; }
if [[ -n "$DAILY_TIMER_UNIT" ]]; then
  systemctl enable --now "$SERVICE_NAME-daily.timer" >/dev/null 2>&1 \
    && ok "enabled $SERVICE_NAME-daily.timer ($DAILY_TIME UTC)" \
    || warn "could not enable $SERVICE_NAME-daily.timer"
fi
systemctl enable --now "$SERVICE_NAME-retry.timer" >/dev/null 2>&1 \
  && ok "enabled $SERVICE_NAME-retry.timer (every ${RETRY_HOURS}h)" \
  || warn "could not enable $SERVICE_NAME-retry.timer"

# WebUI submodule tip watcher — same hourly cadence as status pushes.
WATCH_SH="$REPO_ROOT/scripts/ci_submodule_watch.sh"
if [[ -f "$WATCH_SH" ]]; then
  cat > "$UNIT_DIR/gpu-webui-watch.service" <<EOF
[Unit]
Description=Dana RAG — watch Work_RAG-WebUI tip vs umbrella gitlink
After=network-online.target

[Service]
Type=oneshot
User=root
WorkingDirectory=$REPO_ROOT
Environment=JENKINS_URL=http://127.0.0.1:8085
Environment=JENKINS_USER=admin
Environment=JENKINS_PASS_FILE=/splunk-data/production/.jenkins-admin-pass
ExecStart=/bin/bash $WATCH_SH
Nice=10
EOF
  cat > "$UNIT_DIR/gpu-webui-watch.timer" <<EOF
[Unit]
Description=Dana RAG — WebUI submodule watch every ${INTERVAL_HOURS}h (aligned with health push)

[Timer]
OnBootSec=6min
OnUnitActiveSec=${INTERVAL_HOURS}h
AccuracySec=60s
Persistent=true
Unit=gpu-webui-watch.service

[Install]
WantedBy=timers.target
EOF
  chmod 0644 "$UNIT_DIR/gpu-webui-watch.service" "$UNIT_DIR/gpu-webui-watch.timer"
  systemctl daemon-reload || true
  systemctl enable --now gpu-webui-watch.timer >/dev/null 2>&1 \
    && ok "enabled gpu-webui-watch.timer (every ${INTERVAL_HOURS}h)" \
    || warn "could not enable gpu-webui-watch.timer"
fi

echo ""
echo "=== Installed ==="
echo "  Interval: every ${INTERVAL_HOURS}h (+ up to 10 min jitter)"
echo "  Daily:    ${DAILY_TIME:-disabled}"
echo "  Retry:    every ${RETRY_HOURS}h while last run is missing or failing"
echo "  Logs:     tail -f /var/log/dana-rag/health-report.log"
echo "  Status:   systemctl list-timers '$SERVICE_NAME*'"
echo "  Run now:  sudo systemctl start $SERVICE_NAME.service"
echo ""
echo "  Status:    /var/lib/dana-health/status.json (written each run)"
echo "  Dashboard: https://alinikkhah2001.github.io/Work_RAG_HealthCheck/"
echo "  Metrics:   https://github.com/AliNikkhah2001/Work_RAG_Metrics"
echo "  Retention: screenshots ≤3 newest runs AND ≤24h; text logs ≤48 runs"
echo ""
echo "  Uninstall: sudo bash $SCRIPT_DIR/uninstall.sh"
