#!/usr/bin/env bash
# =============================================================================
# gpu_auto_heal.sh — Proactive production auto-heal daemon for GPU server.
#
# Runs ON the GPU / production host. Ensures the RAG app stack (KB, guardrails,
# orchestrator, WebUI, Jenkins prod controller) stays healthy even when you
# cannot access the server. It:
#   1) Probes every critical port on a short interval.
#   2) On any critical port failure → attempts self-heal:
#      - Restart the failing compose service (compose.gpu.yml stack)
#      - Restart Jenkins prod controller if :8085 is down
#      - Fall back to the host-venv stack (deploy/gpu/start.sh) if compose is gone
#   3) Records health history + last-known-good SHA
#   4) Pushes a status report to the standalone Work_RAG_HealthCheck repo so
#      you can see production health remotely from your laptop.
#
# IMPORTANT: reports must NEVER be pushed into an umbrella submodule. Doing so
# dirties a pinned gitlink in the repo Jenkins polls, which can trigger a
# production build from a health report. Only $DANA_REPORT_REPO (default:
# Work_RAG_HealthCheck) is used.
#
# Install as a systemd service (as root on GPU server):
#   cp scripts/gpu_auto_heal.service /etc/systemd/system/
#   cp scripts/gpu_auto_heal.timer   /etc/systemd/system/
#   systemctl daemon-reload
#   systemctl enable --now gpu_auto_heal.timer
#
# Or run one-shot:  DANA_HOST_REPO=/path bash scripts/gpu_auto_heal.sh --once
# =============================================================================
set -uo pipefail

ROOT="${DANA_HOST_REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT" || exit 1

ONCE=0
INTERVAL="${DANA_HEAL_INTERVAL:-60}"   # seconds between health sweeps
LOG_DIR="${DANA_HEAL_LOG_DIR:-/var/log/dana-rag}"
PROJECT="${DANA_GATE_PROJECT:-dana-prod}"

# Reporting repo: standalone, NOT a submodule of the umbrella repo.
REPORT_REPO="${DANA_REPORT_REPO:-$HOME/Work_RAG_HealthCheck}"
REPORT_REMOTE="${DANA_REPORT_REMOTE:-https://github.com/AliNikkhah2001/Work_RAG_HealthCheck.git}"
REPORT_SUBDIR="reports"
STATUS_FILE="${LOG_DIR}/last-status.json"

mkdir -p "$LOG_DIR" 2>/dev/null || LOG_DIR="${TMPDIR:-/tmp}/dana-rag-logs"
mkdir -p "$LOG_DIR"

log()  { printf '[auto-heal %s] %s\n' "$(date -u +%H:%M:%SZ)" "$*" | tee -a "$LOG_DIR/auto-heal.log"; }
err()  { printf '[auto-heal %s] [ERR] %s\n' "$(date -u +%H:%M:%SZ)" "$*" | tee -a "$LOG_DIR/auto-heal.log" >&2; }

# Critical app ports (compose.gpu.yml stack). Gemma (:18000) and Manager (:9000)
# are host-managed by server-setup — we probe but do not restart them here.
CRITICAL_PORTS="8000 8200 8100 13000"
JENKINS_PORT="8085"

# ---------------------------------------------------------------------------
# Health probe
# ---------------------------------------------------------------------------
port_up() {
  local p="$1"
  curl -sf --max-time 4 "http://127.0.0.1:$p/health" >/dev/null 2>&1 \
    || curl -sf --max-time 4 "http://127.0.0.1:$p/health/liveliness" >/dev/null 2>&1 \
    || curl -sf --max-time 4 "http://127.0.0.1:$p/" >/dev/null 2>&1
}

collect_health() {
  local out="{"
  local sep=""
  for p in $CRITICAL_PORTS; do
    if port_up "$p"; then
      out+="${sep}\"$p\":\"up\""
    else
      out+="${sep}\"$p\":\"down\""
    fi
    sep=","
  done
  if port_up "$JENKINS_PORT"; then
    out+="${sep}\"$JENKINS_PORT\":\"up\""
  else
    out+="${sep}\"$JENKINS_PORT\":\"down\""
  fi
  out+="}"
  echo "$out"
}

# ---------------------------------------------------------------------------
# Self-heal actions
# ---------------------------------------------------------------------------
restart_compose_services() {
  local envf="$ROOT/deploy/compose/.env.prod"
  [[ -f "$envf" ]] || envf="$ROOT/deploy/compose/.env"
  if [[ ! -f "$envf" ]]; then
    err "no .env.prod/.env — cannot restart compose"
    return 1
  fi
  # compose.base.yml has no ports; the gpu overlay supplies them. Never run
  # base alone or the stack comes back healthy with zero published ports.
  log "restarting compose apps (project=$PROJECT)…"
  docker compose -p "$PROJECT" \
    -f "$ROOT/deploy/compose/compose.base.yml" \
    -f "$ROOT/deploy/compose/compose.gpu.yml" \
    --env-file "$envf" \
    up -d --no-build kb guardrails orchestrator webui tracing >>"$LOG_DIR/heal.log" 2>&1 \
    || { err "compose up failed"; return 1; }
  return 0
}

restart_jenkins_prod() {
  log "restarting Jenkins prod controller (:8085)…"
  if docker ps --format '{{.Names}}' | grep -qx 'dana-jenkins-prod'; then
    docker restart dana-jenkins-prod >>"$LOG_DIR/heal.log" 2>&1 || return 1
  elif [[ -f "$ROOT/deploy/jenkins/docker-compose.gpu.yml" ]]; then
    docker compose -f "$ROOT/deploy/jenkins/docker-compose.yml" \
      -f "$ROOT/deploy/jenkins/docker-compose.gpu.yml" \
      up -d >>"$LOG_DIR/heal.log" 2>&1 || return 1
  else
    err "no jenkins prod container or compose found"
    return 1
  fi
  return 0
}

fallback_host_venv() {
  log "falling back to host-venv stack (deploy/gpu/start.sh)…"
  nohup bash "$ROOT/deploy/gpu/start.sh" >>"$LOG_DIR/host-venv.log" 2>&1 &
  return 0
}

# ---------------------------------------------------------------------------
# Report to the standalone health repo so status is visible remotely.
#
# NEVER push into components/server-setup: that is a submodule of the repo
# Jenkins polls, and a dirty gitlink there can trigger a production build.
# ---------------------------------------------------------------------------
push_health_report() {
  local status_json="$1"
  local ts
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  local rel_dir="$REPORT_SUBDIR/gpu-health/$ts"

  # Always append local history (survives even if the push is blocked).
  echo "[$ts] $status_json" >>"$LOG_DIR/health-history.log"

  # Throttle: a 60s sweep must not create 1440 commits/day. Push when the
  # status actually changed, or every DANA_REPORT_MIN_INTERVAL minutes.
  local min_interval="${DANA_REPORT_MIN_INTERVAL:-30}"
  local stamp="$LOG_DIR/.last-report-push"
  local last_state_file="$LOG_DIR/.last-report-state"
  local last_state=""
  [ -f "$last_state_file" ] && last_state="$(cat "$last_state_file" 2>/dev/null)"
  if [ "$status_json" = "$last_state" ] && [ -f "$stamp" ]; then
    local age=$(( $(date +%s) - $(date -r "$stamp" +%s 2>/dev/null || echo 0) ))
    if [ "$age" -lt $(( min_interval * 60 )) ]; then
      return 0
    fi
  fi

  if [ ! -d "$REPORT_REPO/.git" ]; then
    log "health repo not cloned at $REPORT_REPO — attempting clone"
    git clone --depth 1 "$REPORT_REMOTE" "$REPORT_REPO" >>"$LOG_DIR/report.log" 2>&1 \
      || { err "cannot clone $REPORT_REMOTE — health stays local only"; return 1; }
  fi

  (
    cd "$REPORT_REPO" || exit 1
    # Never let a report land on a branch Jenkins watches.
    git fetch origin >/dev/null 2>&1 || true
    git checkout -B "ops/gpu-health-$ts" >/dev/null 2>&1 || true

    mkdir -p "$rel_dir"
    echo "$status_json" >"$rel_dir/health.json"
    echo "$ts" >"$rel_dir/timestamp.txt"
    echo "$(hostname -s 2>/dev/null || hostname)" >"$rel_dir/host.txt"

    # Snapshot of the running artifact set, if we have one.
    if [ -f "$ROOT/deploy/compose/.last_good.json" ]; then
      cp -f "$ROOT/deploy/compose/.last_good.json" "$rel_dir/last_good.json"
    fi

    mkdir -p "$REPORT_SUBDIR"
    echo "- [$ts](gpu-health/$ts/health.json) — $status_json" >>"$REPORT_SUBDIR/README.md"

    git add "$rel_dir" "$REPORT_SUBDIR/README.md" >>"$LOG_DIR/report.log" 2>&1 || true
    if ! git diff --cached --quiet 2>/dev/null; then
      git -c user.name="${GIT_AUTHOR_NAME:-Dana Health Bot}" \
          -c user.email="${GIT_AUTHOR_EMAIL:-health@local}" \
          commit -m "docs(ops): GPU health $ts $(hostname -s 2>/dev/null || hostname) — $status_json" \
          >>"$LOG_DIR/report.log" 2>&1 || true
      if git push -u origin "ops/gpu-health-$ts" >>"$LOG_DIR/report.log" 2>&1; then
        printf '%s\n' "$status_json" >"$last_state_file"
        : >"$stamp"
      else
        err "failed to push health report (will retry next sweep)"
      fi
    fi
  ) || err "could not operate health repo at $REPORT_REPO"
}

write_status_json() {
  local json="$1"
  echo "$json" >"$STATUS_FILE"
  echo "$(date -u +%Y%m%dT%H%M%SZ) $json" >"$LOG_DIR/last-status.txt"
}

# ---------------------------------------------------------------------------
# Main sweep
# ---------------------------------------------------------------------------
run_once() {
  local health
  health="$(collect_health)"
  local down_ports=""
  for p in $CRITICAL_PORTS $JENKINS_PORT; do
    case "$health" in
      *"\"$p\":\"down\"") down_ports="$down_ports $p" ;;
    esac
  done

  log "health=$health"

  if [[ -z "$down_ports" ]]; then
    write_status_json "$health"
    push_health_report "$health"
    return 0
  fi

  err "DOWN ports detected:$down_ports — initiating self-heal"

  # Try compose restart first
  if restart_compose_services; then
    sleep 20
    health="$(collect_health)"
    log "post-heal health=$health"
  fi

  # If Jenkins prod controller down, restart it
  case "$health" in
    *"\"$JENKINS_PORT\":\"down\"") restart_jenkins_prod ;;
  esac

  # Final fallback: host-venv stack
  local still_down=0
  for p in $CRITICAL_PORTS; do
    if ! port_up "$p"; then still_down=1; break; fi
  done
  if [[ "$still_down" == "1" ]]; then
    err "compose heal failed — falling back to host venv"
    fallback_host_venv
    sleep 30
    health="$(collect_health)"
    log "post-fallback health=$health"
  fi

  # Still down after all local recovery: restore the recorded good artifact set.
  # This is the difference between "containers were recreated" and "the thing
  # that used to serve is running again".
  still_down=0
  for p in $CRITICAL_PORTS; do
    if ! port_up "$p"; then still_down=1; break; fi
  done
  if [[ "$still_down" == "1" ]]; then
    if [ -f "$ROOT/deploy/compose/.last_good.json" ]; then
      err "still down — restoring last-known-good manifest"
      DANA_GATE_PROJECT="$PROJECT" bash "$ROOT/scripts/ci_rollback.sh" --target current \
        >>"$LOG_DIR/heal.log" 2>&1 \
        || err "last-known-good restore failed"
      sleep 15
      health="$(collect_health)"
      log "post-restore health=$health"
    else
      err "still down and no .last_good.json recorded — manual intervention needed"
    fi
  fi

  write_status_json "$health"
  push_health_report "$health"
}

if [[ "${1:-}" == "--once" ]]; then
  run_once
  exit 0
fi

if [[ "${1:-}" == "--check" ]]; then
  # Probe-only: exit non-zero if any critical port is down. Never mutates.
  h="$(collect_health)"
  log "check health=$h"
  for p in $CRITICAL_PORTS $JENKINS_PORT; do
    case "$h" in *"\"$p\":\"down\"") exit 1 ;; esac
  done
  exit 0
fi

log "auto-heal daemon starting (interval=${INTERVAL}s)…"
while true; do
  run_once || err "sweep failed"
  sleep "$INTERVAL"
done
