#!/bin/bash
# =============================================================================
# deploy/gpu/stop.sh — stop the GPU stack. Port-scoped only, never `pkill python`.
#
# Two modes:
#   bash deploy/gpu/stop.sh                 # compose down (project-scoped), then
#                                           # sweep any leftover host-venv listeners
#   bash deploy/gpu/stop.sh --host-venv     # only kill host-venv processes by port
#   bash deploy/gpu/stop.sh --profile stage # stop dana-stage instead of dana-prod
#
# Why compose `down --project-name` first: the old version killed processes by
# port. That works for host-venv services but leaves containers running (docker
# proxy holds the port, so `fuser -k` either misses or kills the proxy and the
# container restarts on top of it). Either way the stack survives a "stop".
#
# `-v` is DELIBERATELY NOT used: volumes hold pgdata/webui_data and must survive a
# stop/start cycle. Use `docker compose ... down -v` by hand if you really mean it.
# =============================================================================
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$HERE/lib/common.sh"

PROFILE="gpu"
MODE="compose"

while [ $# -gt 0 ]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --profile=*) PROFILE="${1#*=}"; shift ;;
    --host-venv) MODE="host"; shift ;;
    -h|--help) sed -n '1,26p' "$0"; exit 0 ;;
    *) echo "stop.sh: unknown arg: $1" >&2; exit 2 ;;
  esac
done

PROJECT="$(dana_profile_project "$PROFILE")"

if [ "$MODE" = "compose" ] && dana_have_compose; then
  COMPOSE_FILES=()
  while IFS= read -r f; do [ -n "$f" ] && COMPOSE_FILES+=("$f"); done < <(dana_profile_files "$PROFILE")
  if [ "${#COMPOSE_FILES[@]}" -gt 0 ]; then
    ENV_FILE="$(dana_profile_env "$PROFILE")"
    log "stopping compose project '$PROJECT' (profile=$PROFILE)"
    dana_compose_args "$PROFILE" "$PROJECT" "$ENV_FILE" "${COMPOSE_FILES[@]}"
    # stop (not down): keeps containers/volumes so start is fast and data is safe.
    docker compose "${DANA_COMPOSE_ARGS[@]}" stop 2>&1 | tail -5
    ok "compose services stopped (containers and volumes preserved)"
  fi
else
  log "host-venv mode: port-scoped stops only"
fi

# --- Sweep host-venv / stray listeners on the contract ports -----------------
PORTS=""
case "$PROFILE" in
  gpu|prod-sim|local) PORTS="8000 8100 8200 13000 13002 3000 3001 2024 18000" ;;
  stage)              PORTS="18000 18100 18200 13100 13001 14000 3000 18010" ;;
  host)               PORTS="8000 8100 8200 13000 3000 3001 2024 18000" ;;
esac

for p in $PORTS; do
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${p}/tcp" 2>/dev/null || true
  else
    # No fuser (macOS): use lsof to find the exact PID holding the port, then
    # TERM it. Never pattern-kill a language interpreter.
    pid="$(lsof -nP -iTCP:"$p" -sTCP:LISTEN -t 2>/dev/null | head -1)"
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  fi
done

sleep 2
echo "remaining listeners on our ports (empty = all stopped):"
if command -v ss >/dev/null 2>&1; then
  ss -tln 2>/dev/null | grep -E ":($(echo "$PORTS" | tr ' ' '|'))" || echo "all stopped"
elif command -v lsof >/dev/null 2>&1; then
  out="$(lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -E ":($(echo "$PORTS" | tr ' ' '|'))" | grep -v docker || true)"
  [ -n "$out" ] && echo "$out" || echo "all stopped"
else
  echo "(no ss/lsof available)"
fi
