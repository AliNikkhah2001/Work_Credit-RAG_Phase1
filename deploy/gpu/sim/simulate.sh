#!/usr/bin/env bash
# =============================================================================
# deploy/gpu/sim/simulate.sh — prove the GPU deploy guarantees without a GPU.
#
# Runs a disposable compose project (default name dana-sim) that mirrors the REAL
# production failure mode: a base compose file with NO `ports:` plus an overlay
# that publishes them. Nothing here touches dana-local or dana-stage; the project
# name, host ports (19300-19302 range), and volumes are private to the sim and are
# torn down at the end (volumes included).
#
# Three scenarios:
#   (a) missing-published-port  — start base-only (the Nov 2026 outage shape) and
#                                 prove health.sh names NO_PUBLISHED_PORT and exits 1.
#   (b) promote-on-success      — start base+overlay, prove health.sh is green and
#                                 that deploy/gpu/deploy.sh writes last_good.json.
#   (c) rollback                — corrupt the running stack (drop the published
#                                 port / swap image), prove rollback.sh restores
#                                 the recorded images and re-verifies health.
#
# Usage:
#   bash deploy/gpu/sim/simulate.sh            # all scenarios
#   bash deploy/gpu/sim/simulate.sh --keep     # leave the sim project running
#   bash deploy/gpu/sim/simulate.sh a b c      # selected scenarios
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GPU_DIR="$(cd "$HERE/.." && pwd)"
# shellcheck source=../lib/common.sh
. "$GPU_DIR/lib/common.sh"

SIM_PROJECT="${SIM_PROJECT:-dana-sim}"

# --- single-instance lock -----------------------------------------------------
# The sim binds fixed host ports (19300-19302). Two concurrent runs would fight
# over them and produce phantom failures. Serialise instead of racing.
#
# There is exactly ONE EXIT trap in this script: sim_exit(), defined after the
# cleanup helpers. It releases the lock and tears the sim project down, so the
# two responsibilities can never overwrite each other's trap.
LOCK_FILE="${TMPDIR:-/tmp}/dana-sim.lock"
LOCK_HELD=0

sim_acquire_lock() {
  if mkdir "$LOCK_FILE" 2>/dev/null; then
    printf '%s\n' "$$" > "$LOCK_FILE/pid"
    LOCK_HELD=1
    return 0
  fi
  local holder
  holder="$(cat "$LOCK_FILE/pid" 2>/dev/null || true)"
  # A lock with no readable pid, or whose pid is dead, is stale — reclaim it.
  if [ -z "$holder" ] || ! kill -0 "$holder" 2>/dev/null; then
    rm -rf "$LOCK_FILE"
    if mkdir "$LOCK_FILE" 2>/dev/null; then
      printf '%s\n' "$$" > "$LOCK_FILE/pid"
      LOCK_HELD=1
      echo "reclaimed stale sim lock (previous holder: ${holder:-unknown})" >&2
      return 0
    fi
  fi
  echo "another simulation is already running (pid ${holder:-unknown}); refusing to race on ports 193xx" >&2
  echo "  if you are sure it is dead: rm -rf $LOCK_FILE" >&2
  return 3
}
SIM_DIR="$HERE/stack"
SIM_STATE_DIR="$HERE/.state-$SIM_PROJECT"
KEEP=0
SCENARIOS=()

for arg in "$@"; do
  case "$arg" in
    --keep) KEEP=1 ;;
    a|b|c) SCENARIOS+=("$arg") ;;
    -h|--help) sed -n '1,30p' "$0"; exit 0 ;;
    *) die "simulate.sh: unknown arg: $arg" ;;
  esac
done
[ "${#SCENARIOS[@]}" -gt 0 ] || SCENARIOS=(a b c)

# Reset per-run state BEFORE freezing the code under test (the frozen copy lives
# inside the state dir).
rm -rf "$SIM_STATE_DIR"
mkdir -p "$SIM_STATE_DIR"

# Freeze the code under test into a private copy. bash reads scripts incrementally
# by byte offset, so if a concurrently-edited file changes size mid-run the shell
# can execute garbage ("syntax error near unexpected token" at a nonsense line).
# The frozen copy makes each run a test of ONE immutable revision.
FROZEN="$SIM_STATE_DIR/frozen"
mkdir -p "$FROZEN/lib"
cp "$GPU_DIR/health.sh" "$GPU_DIR/deploy.sh" "$GPU_DIR/rollback.sh" \
   "$GPU_DIR/reconcile.sh" "$FROZEN/"
cp "$GPU_DIR/lib/common.sh" "$GPU_DIR/lib/state.py" "$FROZEN/lib/"
chmod +x "$FROZEN"/*.sh
# common.sh derives DANA_DEPLOY_DIR/DANA_ROOT from its own location. Point it at
# the real repo (so compose files and git facts resolve normally) while the CODE
# under test stays frozen, and pin the state helper to the frozen copy too.
sed -i.bak 's#^DANA_GPU_DIR=.*#DANA_GPU_DIR="'"$GPU_DIR"'"#' "$FROZEN/lib/common.sh"
rm -f "$FROZEN/lib/common.sh.bak"
export DANA_STATE_PY="$FROZEN/lib/state.py"

PASS=0
FAIL=0
record() { # name ok detail
  if [ "$2" = "1" ]; then
    printf '%s  PASS%s  %s\n' "$C_GREEN" "$C_OFF" "$1"
    PASS=$((PASS + 1))
  else
    printf '%s  FAIL%s  %s  (%s)\n' "$C_RED" "$C_OFF" "$1" "${3:-}"
    FAIL=$((FAIL + 1))
  fi
}

banner() {
  printf '\n%s=====================================================================%s\n' "$C_BOLD" "$C_OFF"
  printf '%s  %s%s\n' "$C_BOLD" "$*" "$C_OFF"
  printf '%s=====================================================================%s\n\n' "$C_BOLD" "$C_OFF"
}

# --- sim environment: reuse the real scripts, point them at the sim stack -----
export DANA_COMPOSE_FILES="$SIM_DIR/compose.base.yml $SIM_DIR/compose.override.yml"
export DANA_PROJECT="$SIM_PROJECT"
export DANA_ENV_FILE="$SIM_DIR/sim.env"
export DANA_STATE_DIR="$SIM_STATE_DIR"
export DANA_STATE_FILE="$SIM_STATE_DIR/last_good.json"
export DANA_LOG_DIR="$SIM_STATE_DIR/logs"
# Same port contract SHAPE as prod, different numbers so nothing collides.
export DANA_PORT_SPEC="web:19300:8080:/health api:19301:8100:/health worker:19302:8200:/health"
# The sim deliberately targets a non-production stack through the production code
# path; DANA_ALLOW_OVERRIDE acknowledges that (see dana_guard_overrides).
export DANA_ALLOW_OVERRIDE=1

sim_teardown() {
  # Primary: project-scoped compose down (also drops the sim's own volumes).
  docker compose -p "$SIM_PROJECT" \
    -f "$SIM_DIR/compose.base.yml" -f "$SIM_DIR/compose.override.yml" \
    --env-file "$SIM_DIR/sim.env" down -v --remove-orphans >/dev/null 2>&1 || true
  # Fallback: rollback re-creates containers from a *different* file set
  # (frozen copy + generated pin), so compose down alone can miss them.
  # Container IDs are always labelled with their project — sweep by label.
  local ids
  ids="$(docker ps -aq --filter "label=com.docker.compose.project=$SIM_PROJECT" 2>/dev/null || true)"
  if [ -n "$ids" ]; then
    # shellcheck disable=SC2086
    docker rm -f $ids >/dev/null 2>&1 || true
  fi
  # Sim-local volumes only; never touches dana-local or dana-stage volumes.
  local vols
  vols="$(docker volume ls -q --filter "label=com.docker.compose.project=$SIM_PROJECT" 2>/dev/null || true)"
  if [ -n "$vols" ]; then
    # shellcheck disable=SC2086
    docker volume rm $vols >/dev/null 2>&1 || true
  fi
}

cleanup() {
  if [ "$KEEP" = "1" ]; then
    warn "leaving sim project '$SIM_PROJECT' running (--keep)"
    return
  fi
  sim_teardown
}

# Single EXIT trap: release the lock first (cheap, must always happen), then tear
# down the throwaway project. Never touches dana-local / dana-stage.
sim_exit() {
  local rc=$?
  if [ "$LOCK_HELD" = "1" ]; then
    rm -rf "$LOCK_FILE"
    LOCK_HELD=0
  fi
  cleanup
  exit "$rc"
}
trap sim_exit EXIT

sim_up() { # $1..=compose files
  local files=() f
  for f in "$@"; do files+=(-f "$f"); done
  docker compose -p "$SIM_PROJECT" "${files[@]}" --env-file "$SIM_DIR/sim.env" \
    up -d --no-build >/dev/null 2>&1
}
sim_down() {
  docker compose -p "$SIM_PROJECT" \
    -f "$SIM_DIR/compose.base.yml" -f "$SIM_DIR/compose.override.yml" \
    --env-file "$SIM_DIR/sim.env" down -v --remove-orphans >/dev/null 2>&1 || true
}

sim_acquire_lock || exit 3

banner "simulation: $SIM_PROJECT  (scenarios: ${SCENARIOS[*]})"
log "sim dir    : $SIM_DIR"
log "sim state  : $SIM_STATE_DIR"
log "port spec  : $DANA_PORT_SPEC"

# =============================================================================
# (a) missing published port — the exact production failure shape
# =============================================================================
if printf '%s\n' "${SCENARIOS[@]}" | grep -qx a; then
  banner "(a) healthy container but NO published port  → health.sh must FAIL loudly"
  sim_down
  log "starting base-only (no ports: mapping at all — mirrors compose.base.yml alone)"
  sim_up "$SIM_DIR/compose.base.yml"
  sleep 3

  echo
  echo "--- docker sees: ---"
  docker compose -p "$SIM_PROJECT" -f "$SIM_DIR/compose.base.yml" ps --format \
    '{{.Service}} state={{.State}} health={{.Health}} ports=<{{.Publishers}}>' 2>/dev/null || true

  echo
  echo "--- health.sh verdict table ---"
  bash "$FROZEN/health.sh" --profile gpu --json "$SIM_STATE_DIR/health-a.json"
  RC_A=$?
  echo "exit=$RC_A"

  [ "$RC_A" -eq 1 ] && record "(a1) health.sh exits 1 (deploy/layering bug class)" 1 \
    || record "(a1) health.sh exits 1 (deploy/layering bug class)" 0 "got exit=$RC_A"

  grep -q '"verdict": "NO_PUBLISHED_PORT"' "$SIM_STATE_DIR/health-a.json" 2>/dev/null \
    && record "(a2) verdict names NO_PUBLISHED_PORT explicitly" 1 \
    || record "(a2) verdict names NO_PUBLISHED_PORT explicitly" 0 "verdict json missing"

  grep -q 'NO_PUBLISHED_PORT' "$SIM_STATE_DIR/health-a.json" 2>/dev/null \
    && python3 - "$SIM_STATE_DIR/health-a.json" <<'PY' && record "(a3) detail explains the missing overlay" 1 || record "(a3) detail explains the missing overlay" 0 "no explanatory detail"
import json, sys
d = json.load(open(sys.argv[1]))
detail = next(r["detail"] for r in d["rows"] if r["verdict"] == "NO_PUBLISHED_PORT")
sys.exit(0 if ("publishes NO host port" in detail and "compose.base.yml" in detail) else 1)
PY

  echo
  echo "--- deploy.sh port preflight must refuse to deploy this layering ---"
  DANA_COMPOSE_FILES="$SIM_DIR/compose.base.yml" bash "$FROZEN/deploy.sh" --profile gpu --no-build 2>&1 | tail -12
  RC_DEPLOY=${PIPESTATUS[0]}
  [ "$RC_DEPLOY" -eq 1 ] && record "(a4) deploy.sh refuses the portless layering (exit 1)" 1 \
    || record "(a4) deploy.sh refuses the portless layering (exit 1)" 0 "got exit=$RC_DEPLOY"

  sim_down
fi

# =============================================================================
# (b) successful deploy promotes to last-known-good
# =============================================================================
if printf '%s\n' "${SCENARIOS[@]}" | grep -qx b; then
  banner "(b) healthy deploy (base + overlay) → health green + last_good.json written"
  sim_down
  rm -f "$DANA_STATE_FILE" "$SIM_STATE_DIR/last_good.prev.json"

  log "deploying base + overlay through deploy/gpu/deploy.sh (real script)"
  bash "$FROZEN/deploy.sh" --profile gpu --no-build 2>&1 | tail -30
  RC_B=${PIPESTATUS[0]}
  echo "deploy exit=$RC_B"

  [ "$RC_B" -eq 0 ] && record "(b1) deploy.sh exit 0 (health gate green)" 1 \
    || record "(b1) deploy.sh exit 0 (health gate green)" 0 "exit=$RC_B"

  [ -f "$DANA_STATE_FILE" ] && record "(b2) last_good.json written on success" 1 \
    || record "(b2) last_good.json written on success" 0 "missing $DANA_STATE_FILE"

  python3 "$FROZEN/lib/state.py" validate --state "$DANA_STATE_FILE" >/dev/null 2>&1 \
    && record "(b3) state validates against schema v1" 1 \
    || record "(b3) state validates against schema v1" 0 "validation failed"

  SVC_COUNT="$(python3 "$FROZEN/lib/state.py" get --state "$DANA_STATE_FILE" --field images --default '[]' | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')"
  [ "$SVC_COUNT" -ge 3 ] && record "(b4) images[] records all $SVC_COUNT services with IDs" 1 \
    || record "(b4) images[] records all services with IDs" 0 "only $SVC_COUNT"

  python3 "$FROZEN/lib/state.py" get --state "$DANA_STATE_FILE" --field compose.config_sha256 --default "" \
    | grep -qE '^[0-9a-f]{64}$' \
    && record "(b5) compose.config_sha256 recorded (sha256 of resolved config)" 1 \
    || record "(b5) compose.config_sha256 recorded" 0 "not a sha256"

  CRIT="$(python3 "$FROZEN/lib/state.py" get --state "$DANA_STATE_FILE" --field status --default "")"
  [ "$CRIT" = "healthy" ] && record "(b6) promoted state status=healthy" 1 \
    || record "(b6) promoted state status=healthy" 0 "status=$CRIT"

  [ -f "$SIM_STATE_DIR/last_good.history.jsonl" ] && record "(b7) promote appended a history record" 1 \
    || record "(b7) promote appended a history record" 0 "no history file"

  echo
  echo "--- health.sh after successful deploy ---"
  bash "$FROZEN/health.sh" --profile gpu
  echo "exit=$?"
fi

# =============================================================================
# (c) rollback restores the recorded images and re-verifies
# =============================================================================
if printf '%s\n' "${SCENARIOS[@]}" | grep -qx c; then
  banner "(c) stack broken after deploy → rollback.sh restores last-known-good"
  [ -f "$DANA_STATE_FILE" ] || { bash "$FROZEN/deploy.sh" --profile gpu --no-build >/dev/null 2>&1; }

  SAVED_IDS_BEFORE="$(python3 "$FROZEN/lib/state.py" get --state "$DANA_STATE_FILE" --field images | python3 -c '
import json,sys
d=json.load(sys.stdin)
print("\n".join("%s=%s" % (i["service"], (i.get("image_id") or "")[:19]) for i in d))')"
  echo "recorded images:"; echo "$SAVED_IDS_BEFORE" | sed 's/^/  /'

  echo
  log "breaking the stack: recreate WITHOUT the overlay (no published ports) — the prod outage shape"
  sim_down
  sim_up "$SIM_DIR/compose.base.yml"
  sleep 2
  bash "$FROZEN/health.sh" --profile gpu --quiet; RC_C1=$?
  echo "health after break: exit=$RC_C1 (expect non-zero)"
  [ "$RC_C1" -ne 0 ] && record "(c1) broken stack is detected as unhealthy" 1 \
    || record "(c1) broken stack is detected as unhealthy)" 0 "health still green"

  echo
  log "running reconcile.sh (auto-heal) — must heal via last-known-good, not blind up"
  bash "$FROZEN/reconcile.sh" --force 2>&1 | tail -35
  RC_C2=${PIPESTATUS[0]}
  echo "reconcile exit=$RC_C2"
  [ "$RC_C2" -eq 0 ] && record "(c2) reconcile.sh heals a broken stack (exit 0)" 1 \
    || record "(c2) reconcile.sh heals a broken stack (exit 0)" 0 "exit=$RC_C2"

  # Re-verify. rollback.sh already waited for green, but give it a short bounded
  # window here: a concurrent docker event (or a lingering socket) can make the
  # very next probe flap. Retry for up to 30s before declaring failure.
  RC_C3=1
  for _try in 1 2 3 4 5 6; do
    bash "$FROZEN/health.sh" --profile gpu --quiet 2>/tmp/sim_c3.err
    RC_C3=$?
    [ "$RC_C3" -eq 0 ] && break
    [ "$RC_C3" -eq 64 ] && { echo "health.sh refused to run (exit 64):"; sed 's/^/  /' /tmp/sim_c3.err; break; }
    sleep 5
  done
  [ "$RC_C3" -eq 0 ] && record "(c3) re-verification green after rollback" 1 \
    || record "(c3) re-verification green after rollback" 0 "exit=$RC_C3$( [ -s /tmp/sim_c3.err ] && echo " $(tr '\n' ' ' </tmp/sim_c3.err)" )"

  # Ports must be back, and the container must be on the recorded image.
  LIVE_PORTS="$(docker compose -p "$SIM_PROJECT" -f "$SIM_DIR/compose.base.yml" -f "$SIM_DIR/compose.override.yml" --env-file "$SIM_DIR/sim.env" ps --format '{{.Service}}={{.Publishers}}' 2>/dev/null)"
  echo "$LIVE_PORTS" | grep -q "19300" && record "(c4) published port 19300 restored" 1 \
    || record "(c4) published port 19300 restored" 0 "$LIVE_PORTS"

  NOW_ID="$(docker compose -p "$SIM_PROJECT" -f "$SIM_DIR/compose.base.yml" -f "$SIM_DIR/compose.override.yml" --env-file "$SIM_DIR/sim.env" ps -q web 2>/dev/null | xargs -r docker inspect --format '{{.Image}}' 2>/dev/null | cut -c8-26)"
  REC_ID="$(python3 "$FROZEN/lib/state.py" get --state "$DANA_STATE_FILE" --field images | python3 -c '
import json,sys
for i in json.load(sys.stdin):
    if i["service"]=="web": print((i.get("image_id") or "")[7:26])')"
  [ -n "$NOW_ID" ] && [ "$NOW_ID" = "$REC_ID" ] \
    && record "(c5) running image == recorded last-good image ($NOW_ID)" 1 \
    || record "(c5) running image == recorded last-good image" 0 "now=$NOW_ID recorded=$REC_ID"

  echo
  echo "--- rolled-back state (rollback annotation) ---"
  python3 "$FROZEN/lib/state.py" get --state "$DANA_STATE_FILE" --field schedule
fi

# =============================================================================
banner "simulation summary"
printf '  passed: %s%d%s\n' "$C_GREEN" "$PASS" "$C_OFF"
printf '  failed: %s%d%s\n' "$([ "$FAIL" -eq 0 ] && echo "$C_GREEN" || echo "$C_RED")" "$FAIL" "$C_OFF"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
