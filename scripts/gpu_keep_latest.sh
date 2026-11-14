#!/usr/bin/env bash
# GPU / prod — keep app stack on the latest *healthy* origin/main tip.
#
# Preferred production path is still Jenkins Multibranch (pollSCM + [ci prod]).
# This script is a backup daemon/timer for hosts where you want a simple
# "always track successful main" loop without clicking Scan Now.
#
# One-shot:
#   bash scripts/gpu_keep_latest.sh
#   bash scripts/gpu_keep_latest.sh --dry-run
#
# Daemon (foreground loop):
#   bash scripts/gpu_keep_latest.sh --loop --interval 300
#
# systemd (example unit): deploy/jenkins/dana-keep-latest.service
#
# Behavior:
#   1) git fetch origin main
#   2) if origin/main == currently deployed SHA → exit 0
#   3) checkout worktree / update host clone to that SHA + submodule sync
#   4) compose up dana-prod (apps only — never Gemma/TRT)
#   5) health probe :8100/:8200/:8000; on success record .last_good_sha
#      on failure → ci_rollback.sh (previous good) and exit non-zero
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST_REPO="${DANA_HOST_REPO:-$ROOT}"
cd "$HOST_REPO"

DRY=0
LOOP=0
INTERVAL=300
BRANCH="${DANA_TRACK_BRANCH:-main}"
REMOTE="${DANA_TRACK_REMOTE:-origin}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --loop) LOOP=1; shift ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    -h|--help)
      sed -n '1,35p' "$0"
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

log() { printf '[keep-latest] %s\n' "$*"; }

deployed_sha_file() {
  echo "$HOST_REPO/deploy/compose/.deployed_sha"
}

current_target() {
  git -C "$HOST_REPO" rev-parse "${REMOTE}/${BRANCH}" 2>/dev/null \
    || git -C "$HOST_REPO" rev-parse "$BRANCH"
}

last_deployed() {
  local f
  f="$(deployed_sha_file)"
  if [[ -f "$f" ]]; then
    tr -d '[:space:]' <"$f"
  elif [[ -f "$HOST_REPO/deploy/compose/.last_good_sha" ]]; then
    tr -d '[:space:]' <"$HOST_REPO/deploy/compose/.last_good_sha"
  else
    git -C "$HOST_REPO" rev-parse HEAD 2>/dev/null || echo ""
  fi
}

health_ok() {
  local p
  for p in 8100 8200 8000; do
    curl -sf --max-time 8 "http://127.0.0.1:$p/health" >/dev/null \
      || curl -sf --max-time 8 "http://127.0.0.1:$p/health/liveliness" >/dev/null \
      || return 1
  done
  return 0
}

compose_up() {
  local envf="$HOST_REPO/deploy/compose/.env.prod"
  [[ -f "$envf" ]] || envf="$HOST_REPO/deploy/compose/.env"
  docker compose -p dana-prod \
    -f "$HOST_REPO/deploy/compose/compose.base.yml" \
    -f "$HOST_REPO/deploy/compose/compose.gpu.yml" \
    --env-file "$envf" \
    up -d --build \
    kb guardrails orchestrator tracing webui 2>/dev/null \
    || docker compose -p dana-prod \
      -f "$HOST_REPO/deploy/compose/compose.base.yml" \
      -f "$HOST_REPO/deploy/compose/compose.gpu.yml" \
      --env-file "$envf" \
      up -d --build
}

once() {
  log "fetch ${REMOTE}/${BRANCH}"
  git -C "$HOST_REPO" fetch "$REMOTE" "$BRANCH" --prune

  local target deployed
  target="$(current_target)"
  deployed="$(last_deployed)"
  log "remote tip=${target:0:12} deployed=${deployed:0:12}"

  if [[ -n "$deployed" && "$target" == "$deployed" ]]; then
    log "already on tip — nothing to do"
    if health_ok; then
      log "health OK"
      return 0
    fi
    warn_health=1
    log "health FAILED on current tip — attempting rollback"
    if [[ "$DRY" == "1" ]]; then
      log "dry-run: would rollback"
      return 1
    fi
    bash "$HOST_REPO/scripts/ci_rollback.sh"
    return $?
  fi

  if [[ "$DRY" == "1" ]]; then
    log "dry-run: would checkout $target and compose up dana-prod"
    return 0
  fi

  # Move host clone (or worktree) to tip
  git -C "$HOST_REPO" checkout -f "$target"
  bash "$HOST_REPO/scripts/ci_submodule_sync.sh" || git -C "$HOST_REPO" submodule update --init --recursive

  log "compose up…"
  compose_up
  sleep 20

  if health_ok; then
    printf '%s\n' "$target" >"$(deployed_sha_file)"
    bash "$HOST_REPO/scripts/ci_record_last_good.sh" "$target"
    log "deployed OK → recorded last_good=$target"
    return 0
  fi

  log "health FAILED after deploy — rolling back apps"
  bash "$HOST_REPO/scripts/ci_rollback.sh" || true
  return 1
}

if [[ "$LOOP" == "1" ]]; then
  log "loop every ${INTERVAL}s (Ctrl-C to stop)"
  while true; do
    once || log "cycle failed (will retry)"
    sleep "$INTERVAL"
  done
else
  once
fi
