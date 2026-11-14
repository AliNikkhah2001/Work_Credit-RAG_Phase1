#!/usr/bin/env bash
# =============================================================================
# gpu_keep_latest.sh — keep the app stack on the latest *healthy* main tip.
#
# Preferred production path is still the Jenkins prod controller (pollSCM +
# [ci prod]). This is the backup loop for when the controller itself is
# unhealthy: it advances the host only if the deploy passes the health gate,
# and otherwise restores the last-known-good manifest.
#
# One-shot:   bash scripts/gpu_keep_latest.sh
#             bash scripts/gpu_keep_latest.sh --dry-run
# Daemon:     bash scripts/gpu_keep_latest.sh --loop --interval 300
# systemd:    deploy/jenkins/dana-keep-latest.{service,timer}
#
# Guarantees:
#   * never advances to a tip that does not pass ci_deploy_gate.sh
#   * never overwrites .last_good.json on a failed deploy
#   * on failure, restores the recorded images (ci_rollback.sh), not a rebuild
# =============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST_REPO="${DANA_HOST_REPO:-$ROOT}"
cd "$HOST_REPO" || exit 1

DRY=0
LOOP=0
INTERVAL=300
BRANCH="${DANA_TRACK_BRANCH:-main}"
REMOTE="${DANA_TRACK_REMOTE:-origin}"
PROJECT="${DANA_GATE_PROJECT:-dana-prod}"

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --loop) LOOP=1; shift ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    -h|--help) sed -n '1,26p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

log() { printf '[keep-latest] %s\n' "$*"; }
err() { printf '[keep-latest][ERR] %s\n' "$*" >&2; }

MANIFEST="$HOST_REPO/deploy/compose/.last_good.json"
DEPLOYED_FILE="$HOST_REPO/deploy/compose/.deployed_sha"

current_target() {
  git -C "$HOST_REPO" rev-parse "${REMOTE}/${BRANCH}" 2>/dev/null \
    || git -C "$HOST_REPO" rev-parse "$BRANCH"
}

last_good_sha() {
  if [ -f "$MANIFEST" ]; then
    sed -n 's/.*"sha"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$MANIFEST" | head -1
  elif [ -f "$HOST_REPO/deploy/compose/.last_good_sha" ]; then
    tr -d '[:space:]' <"$HOST_REPO/deploy/compose/.last_good_sha"
  fi
}

compose_cmd() {
  local envf="$HOST_REPO/deploy/compose/.env.prod"
  [ -f "$envf" ] || envf="$HOST_REPO/deploy/compose/.env"
  local overlay="$HOST_REPO/deploy/compose/compose.gpu.yml"
  [ -f "$overlay" ] || overlay="$HOST_REPO/deploy/compose/compose.local.yml"
  printf 'docker compose -p %s -f %s -f %s --env-file %s' \
    "$PROJECT" "$HOST_REPO/deploy/compose/compose.base.yml" "$overlay" "$envf"
}

health_ok() {
  DANA_GATE_PROJECT="$PROJECT" bash "$ROOT/scripts/ci_deploy_gate.sh" >/dev/null 2>&1
}

compose_up() {
  local envf="$HOST_REPO/deploy/compose/.env.prod"
  [ -f "$envf" ] || envf="$HOST_REPO/deploy/compose/.env"
  local overlay="$HOST_REPO/deploy/compose/compose.gpu.yml"
  [ -f "$overlay" ] || overlay="$HOST_REPO/deploy/compose/compose.local.yml"

  # --no-build on purpose: the tip may not have images built yet (built by CI).
  # If the images are missing, the deploy gate will fail and we roll back
  # rather than silently building from an unverified tip.
  docker compose -p "$PROJECT" \
    -f "$HOST_REPO/deploy/compose/compose.base.yml" \
    -f "$overlay" \
    --env-file "$envf" \
    up -d --no-build kb guardrails orchestrator tracing webui
}

once() {
  log "fetch ${REMOTE}/${BRANCH}"
  if ! git -C "$HOST_REPO" fetch "$REMOTE" "$BRANCH" --prune; then
    err "fetch failed — keeping current stack"
    return 1
  fi

  local target deployed
  target="$(current_target)"
  deployed="$(last_good_sha)"

  if [ -z "$target" ]; then
    err "could not resolve ${REMOTE}/${BRANCH}"
    return 1
  fi

  log "remote tip=${target:0:12} last_good=${deployed:0:12}"

  if [ -n "$deployed" ] && [ "$target" = "$deployed" ]; then
    log "already on the last-known-good tip"
    if health_ok; then
      log "health OK"
      return 0
    fi
    err "health FAILED on the recorded-good tip — restoring last-known-good images"
    [ "$DRY" = "1" ] && { log "dry-run: would restore"; return 1; }
    bash "$ROOT/scripts/ci_rollback.sh" --target current
    return $?
  fi

  if [ "$DRY" = "1" ]; then
    log "dry-run: would checkout $target, compose up --no-build, then gate"
    log "dry-run: on gate failure would restore .last_good.json.prev"
    return 0
  fi

  local prev_head
  prev_head="$(git -C "$HOST_REPO" rev-parse HEAD 2>/dev/null || echo '')"

  log "advancing host clone to $target"
  if ! git -C "$HOST_REPO" checkout -q -f "$target"; then
    err "checkout failed — staying on $prev_head"
    return 1
  fi
  bash "$ROOT/scripts/ci_submodule_sync.sh" >/dev/null 2>&1 \
    || git -C "$HOST_REPO" submodule update --init --recursive >/dev/null 2>&1

  log "compose up --no-build (project=$PROJECT)"
  if ! compose_up; then
    err "compose up failed — restoring last-known-good"
    bash "$ROOT/scripts/ci_rollback.sh" --target current || true
    return 1
  fi

  log "gating (ports + container health + endpoints)"
  if DANA_GATE_PROJECT="$PROJECT" bash "$ROOT/scripts/ci_record_last_good.sh" --if-gate-passes "$target"; then
    printf '%s\n' "$target" >"$DEPLOYED_FILE"
    log "deployed OK → recorded last_good=$target"
    return 0
  fi

  err "gate FAILED for $target — NOT recorded; restoring last-known-good"
  bash "$ROOT/scripts/ci_rollback.sh" --target current || true
  # Put the clone back where it was so the host tree matches what is running.
  [ -n "$prev_head" ] && git -C "$HOST_REPO" checkout -q -f "$prev_head" 2>/dev/null
  return 1
}

if [ "$LOOP" = "1" ]; then
  log "loop every ${INTERVAL}s (project=$PROJECT, Ctrl-C to stop)"
  while true; do
    once || log "cycle failed (retrying in ${INTERVAL}s)"
    sleep "$INTERVAL"
  done
else
  once
fi
