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
#      - Fall back to host-venv stack (deploy/gpu/start.sh) if compose is gone
#   3) Records health history + last-known-good SHA
#   4) Pushes a status report to the server-setup repo (GitHub) so you can see
#      production health remotely from your laptop.
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
cd "$ROOT"

ONCE=0
INTERVAL="${DANA_HEAL_INTERVAL:-60}"   # seconds between health sweeps
LOG_DIR="${DANA_HEAL_LOG_DIR:-/var/log/dana-rag}"
REPORT_REPO="${DANA_REPORT_REPO:-$ROOT/components/server-setup}"
REPORT_DIR="${REPORT_REPO}/docs/ops/gpu-health"
STATUS_FILE="${LOG_DIR}/last-status.json"

mkdir -p "$LOG_DIR" "$REPORT_DIR"

log()  { printf '[auto-heal %s] %s\n' "$(date -u +%H:%M:%SZ)" "$*" | tee -a "$LOG_DIR/auto-heal.log"; }
err()  { printf '[auto-heal %s] [ERR] %s\n' "$(date -u +%H:%M:%SZ)" "$*" | tee -a "$LOG_DIR/auto-heal.log"; }

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
  log "restarting compose apps (dana-prod)…"
  docker compose -p dana-prod \
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
# Report to GitHub (server-setup repo) so status is visible remotely
# ---------------------------------------------------------------------------
push_health_report() {
  local status_json="$1"
  local ts
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  local run_dir="$REPORT_DIR/$ts"
  mkdir -p "$run_dir"
  echo "$status_json" >"$run_dir/health.json"
  echo "$ts" >"$run_dir/timestamp.txt"

  # Latest symlink
  ln -sfn "$ts" "$REPORT_DIR/latest"

  # Append to history log
  echo "[$ts] $status_json" >>"$LOG_DIR/health-history.log"

  if [[ -d "$REPORT_REPO/.git" ]]; then
    (
      cd "$REPORT_REPO"
      git fetch origin 2>/dev/null || true
      git checkout -B "ops/gpu-health-$ts" 2>/dev/null | tee -a "$LOG_DIR/report.log" || true
      git add "docs/ops/gpu-health/$ts" "docs/ops/gpu-health/latest" >>"$LOG_DIR/report.log" 2>&1 || true
      if ! git diff --cached --quiet 2>/dev/null; then
        git commit -m "docs(ops): GPU health report $ts" >>"$LOG_DIR/report.log" 2>&1 || true
        git push -u origin "ops/gpu-health-$ts" >>"$LOG_DIR/report.log" 2>&1 || err "failed to push health report to GitHub"
      fi
    ) || err "could not operate on server-setup repo for health report"
  else
    err "server-setup not a git checkout at $REPORT_REPO — health not pushed to GitHub"
  fi
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

  write_status_json "$health"
  push_health_report "$health"
}

if [[ "${1:-}" == "--once" ]]; then
  run_once
  exit 0
fi

log "auto-heal daemon starting (interval=${INTERVAL}s)…"
while true; do
  run_once || err "sweep failed"
  sleep "$INTERVAL"
done
