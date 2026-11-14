#!/usr/bin/env bash
# =============================================================================
# deploy/gpu/deploy.sh — the ONLY supported way to deploy the Dana GPU stack.
#
# Guarantees, in order:
#   1. Layering is fixed by profile (base + overlay) and the project name is
#      always explicit (-p). An env file's COMPOSE_PROJECT_NAME can no longer
#      retarget a prod deploy onto dana-local, and compose.base.yml alone (no
#      `ports:`) can no longer be used by accident.
#   2. A PORT PREFLIGHT runs before anything is started: the resolved config must
#      publish every expected loopback port, or the deploy aborts untouched.
#   3. Startup is ordered with readiness gates (up --wait + per-port waits), not
#      sleeps. A slow model load cannot be mistaken for a healthy stack.
#   4. Health is verified from the HOST via health.sh (published ports, not just
#      container-internal health).
#   5. ONLY a fully green deploy is promoted to last-known-good. The previous
#      good record is rotated to last_good.prev.json and kept for rollback.
#   6. If health fails, deploy.sh automatically rolls back to last-known-good
#      instead of leaving the (possibly port-less) new stack serving.
#
# Usage:
#   bash deploy/gpu/deploy.sh                     # prod gpu, current checkout
#   bash deploy/gpu/deploy.sh --dry-run           # validate + plan, change nothing
#   bash deploy/gpu/deploy.sh --no-promote        # deploy, verify, do not record LKG
#   bash deploy/gpu/deploy.sh --no-rollback       # on failure, leave stack as-is
#   bash deploy/gpu/deploy.sh --profile stage     # dana-stage
#   bash deploy/gpu/deploy.sh --tag sha-abc1234   # build with an explicit image tag
#   bash deploy/gpu/deploy.sh --no-build          # use images as they are
#   bash deploy/gpu/deploy.sh --skip-images-mode  # host-venv: delegate to start.sh
#
# Exit codes: 0 promoted, 1 deploy/health failure (rolled back), 2 usage,
#             3 rolled back AND the rollback also failed (page a human).
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$HERE/lib/common.sh"

PROFILE="gpu"
DRY_RUN=0
DO_PROMOTE=1
DO_ROLLBACK=1
DO_BUILD=1
TAG=""
HEALTH_TIMEOUT=600
ALLOW_DIRTY=0
HOST_VENV=0

while [ $# -gt 0 ]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --profile=*) PROFILE="${1#*=}"; shift ;;
    --dry-run|-n) DRY_RUN=1; shift ;;
    --no-promote) DO_PROMOTE=0; shift ;;
    --no-rollback) DO_ROLLBACK=0; shift ;;
    --no-build) DO_BUILD=0; shift ;;
    --tag) TAG="$2"; shift 2 ;;
    --timeout) HEALTH_TIMEOUT="$2"; shift 2 ;;
    --allow-dirty) ALLOW_DIRTY=1; shift ;;
    --host-venv) HOST_VENV=1; PROFILE="host"; shift ;;
    -h|--help) sed -n '1,42p' "$0"; exit 0 ;;
    *) die "deploy.sh: unknown arg: $1" ;;
  esac
done

PROJECT="$(dana_profile_project "$PROFILE")" || die "unknown profile '$PROFILE'"
ENV_FILE="${DANA_ENV_FILE:-$(dana_profile_env "$PROFILE")}"
SPEC="$(dana_port_spec "$PROFILE")"
dana_ensure_log_dir

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_LOG="$DANA_LOG_DIR/deploy-$RUN_ID.log"
CANDIDATE="$DANA_STATE_DIR/candidate-$RUN_ID.json"
mkdir -p "$DANA_STATE_DIR"

log "deploy start profile=$PROFILE project=$PROJECT run=$RUN_ID"
log "log=$RUN_LOG"
log "state=$DANA_STATE_FILE"

# ---------------------------------------------------------------------------
# 0. Host-venv path: delegate and still gate promotion on health
# ---------------------------------------------------------------------------
if [ "$PROFILE" = "host" ] || [ "$HOST_VENV" = "1" ]; then
  log "host-venv profile: delegating to deploy/gpu/start.sh (no compose, no images)"
  if [ "$DRY_RUN" = "1" ]; then
    log "dry-run: would run bash $HERE/start.sh"
    exit 0
  fi
  bash "$HERE/start.sh" 2>&1 | tee -a "$RUN_LOG"
  if bash "$HERE/health.sh" --profile host --json "$DANA_STATE_DIR/health-$RUN_ID.json" 2>&1 | tee -a "$RUN_LOG"; then
    ok "host-venv stack healthy"
    exit 0
  fi
  err "host-venv stack unhealthy — see $RUN_LOG"
  exit 1
fi

dana_have_compose || die "docker compose is not available on this host"

COMPOSE_FILES=()
while IFS= read -r f; do [ -n "$f" ] && COMPOSE_FILES+=("$f"); done < <(dana_profile_files "$PROFILE")
[ "${#COMPOSE_FILES[@]}" -gt 0 ] || die "profile '$PROFILE' has no compose layering"
for f in "${COMPOSE_FILES[@]}"; do
  [ -f "$f" ] || die "compose file missing: $f"
done

CFG_HASH="$(dana_config_sha "$PROFILE" "$PROJECT" "$ENV_FILE" || true)"

if [ "$DRY_RUN" != "1" ] && [ "$ALLOW_DIRTY" != "1" ]; then
  if [ -d "$DANA_ROOT/.git" ] && [ -n "$(git -C "$DANA_ROOT" status --porcelain 2>/dev/null)" ]; then
    warn "working tree is dirty — deploying uncommitted code (SHA will be recorded as-is)"
    warn "pass --allow-dirty to silence, or commit first so rollback is reproducible"
  fi
fi

# ---------------------------------------------------------------------------
# 1. Validate the compose layering + preview the config hash
# ---------------------------------------------------------------------------
log "preflight: validating compose layering"
log "config sha256 (pre-deploy) = ${CFG_HASH:-unknown}"
ARGS=(--project "$PROJECT")
for f in "${COMPOSE_FILES[@]}"; do ARGS+=(-f "$f"); done
[ -n "$ENV_FILE" ] && ARGS+=(--env-file "$ENV_FILE")
ARGS+=(--spec "$SPEC" --json-out "$DANA_STATE_DIR/preflight-$RUN_ID.json")

if ! python3 "$DANA_STATE_PY" check-ports "${ARGS[@]}" 2>&1 | tee -a "$RUN_LOG"; then
  err "PORT PREFLIGHT FAILED — refusing to deploy a stack with unpublished ports."
  err "This is the exact failure that darkened production in Nov 2026."
  err "fix the overlay (deploy/compose/compose.$PROFILE.yml) — do not bypass this gate."
  exit 1
fi
ok "port preflight passed (config sha256=${CFG_HASH:0:12})"

if [ "$DRY_RUN" = "1" ]; then
  echo
  log "dry-run plan:"
  echo "  project   : $PROJECT"
  echo "  layering  : ${COMPOSE_FILES[*]}"
  echo "  env file  : ${ENV_FILE:-<none>}"
  echo "  config sha: $CFG_HASH"
  echo "  would run : docker compose ${ARGS[*]//--spec*/} up -d --wait"
  echo "  then      : deploy/gpu/health.sh --profile $PROFILE"
  echo "  then      : promote $CANDIDATE -> $DANA_STATE_FILE"
  echo "  rollback  : deploy/gpu/rollback.sh --from-state $DANA_STATE_FILE"
  exit 0
fi

dana_compose_args "$PROFILE" "$PROJECT" "$ENV_FILE" "${COMPOSE_FILES[@]}"

ORDER_ARGS=(--project "$PROJECT")
for f in "${COMPOSE_FILES[@]}"; do ORDER_ARGS+=(-f "$f"); done
[ -n "$ENV_FILE" ] && ORDER_ARGS+=(--env-file "$ENV_FILE")

# ---------------------------------------------------------------------------
# 2. Snapshot what is currently running (for diagnostics / manual rollback)
# ---------------------------------------------------------------------------
PREV_HEALTH_FILE="$DANA_STATE_DIR/health-pre-$RUN_ID.json"
bash "$HERE/health.sh" --profile "$PROFILE" --quiet --json "$PREV_HEALTH_FILE" >/dev/null 2>&1
PREV_STATUS=$?
log "pre-deploy health exit=$PREV_STATUS (0=currently healthy)"

# ---------------------------------------------------------------------------
# 3. Ordered rollout with readiness gates
# ---------------------------------------------------------------------------
# Startup order is expressed by compose depends_on (condition: service_healthy)
# in compose.base.yml. We additionally walk the order explicitly so a dependency
# that is missing from depends_on still cannot race ahead, and so a slow GPU
# model load shows up as a bounded wait, not a mystery.
ORDER="$(python3 "$DANA_STATE_PY" order "${ORDER_ARGS[@]}" 2>/dev/null)"
if [ -z "$ORDER" ]; then
  # Fall back to the documented production order if the graph cannot be read.
  ORDER="postgres redis kb guardrails tracing orchestrator webui"
  warn "could not derive startup order from depends_on — using the documented order"
fi
log "startup order: $(echo "$ORDER" | tr '\n' ' ')"

rollout() {
  # Build once (if asked), then bring services up in dependency order with
  # readiness gates. Per-service `--build` would rebuild shared layers repeatedly.
  if [ "$DO_BUILD" = "1" ]; then
    log "building images (this can take several minutes on the GPU host)"
    if [ -n "$TAG" ]; then
      TAG="$TAG" docker compose "${DANA_COMPOSE_ARGS[@]}" build 2>&1 | tee -a "$RUN_LOG"
    else
      docker compose "${DANA_COMPOSE_ARGS[@]}" build 2>&1 | tee -a "$RUN_LOG"
    fi
    if [ "${PIPESTATUS[0]}" -ne 0 ]; then
      err "image build failed"
      return 1
    fi
  fi

  local services_in_profile
  services_in_profile="$(docker compose "${DANA_COMPOSE_ARGS[@]}" config --services 2>/dev/null)"

  # Walk the derived dependency order, then append anything the graph missed so a
  # new service can never be silently left out of a deploy.
  local walk="$ORDER"
  local svc_in
  for svc_in in $services_in_profile; do
    printf '%s\n' "$walk" | grep -qx "$svc_in" || walk="$walk $svc_in"
  done

  for svc in $walk; do
    printf '%s\n' "$services_in_profile" | grep -qx "$svc" || { log "skip $svc (not in this profile)"; continue; }

    log "up $svc"
    docker compose "${DANA_COMPOSE_ARGS[@]}" up -d --no-build "$svc" >>"$RUN_LOG" 2>&1
    local rc=$?
    if [ "$rc" -ne 0 ]; then
      if dana_is_optional "$svc"; then
        warn "$svc failed to start (optional) — continuing"
        continue
      fi
      err "compose up failed for $svc (rc=$rc) — see $RUN_LOG"
      return 1
    fi

    # Readiness gate: the service's own healthcheck must go healthy, bounded.
    #
    # `compose ps {{.Health}}` renders EMPTY for a container that is still
    # starting (and for one with no healthcheck at all), so the old loop broke
    # out immediately and reported "health=none", then health.sh failed minutes
    # later on `container health=starting` (seen in sim scenario c). Ask docker
    # directly whether a healthcheck exists, so "not ready yet" waits and
    # "genuinely no healthcheck" does not.
    local deadline=$((SECONDS + HEALTH_TIMEOUT)) health=""
    while [ "$SECONDS" -lt "$deadline" ]; do
      health="$(dana_service_health "$svc")"
      case "$health" in
        healthy) break ;;
        none) break ;;      # no healthcheck defined; the port gate below covers it
      esac
      sleep 2
    done
    # A container that never registered at all is a real failure.
    if [ "$health" = "missing" ]; then
      if dana_is_optional "$svc"; then
        warn "$svc container missing (optional) — continuing"
        continue
      fi
      err "$svc container never appeared (see $RUN_LOG)"
      return 1
    fi
    case "$health" in
      healthy|none|"")
        log "  $svc health=${health:-none}" ;;
      *)
        if dana_is_optional "$svc"; then
          warn "$svc did not become healthy (${health}) — optional, continuing"
          continue
        fi
        err "$svc did not become healthy within ${HEALTH_TIMEOUT}s (last=${health})"
        return 1 ;;
    esac

    # Port gate: never proceed to the next tier until this one is host-reachable.
    local port
    port="$(for t in $SPEC; do [ "${t%%:*}" = "$svc" ] && echo "$t" | cut -d: -f2; done | head -1)"
    if [ -n "$port" ]; then
      if ! dana_wait_port "$port" 60; then
        if dana_is_optional "$svc"; then
          warn "  $svc host port $port not listening (optional)"
          continue
        fi
        err "  $svc published port $port never started listening"
        return 1
      fi
      log "  $svc host port $port listening"
    fi
  done
  return 0
}

if ! rollout; then
  err "rollout failed"
  ROLLOUT_FAILED=1
else
  ROLLOUT_FAILED=0
fi

# ---------------------------------------------------------------------------
# 4. Full host-side health gate
# ---------------------------------------------------------------------------
HEALTH_JSON="$DANA_STATE_DIR/health-$RUN_ID.json"
HEALTH_RC=1
if [ "$ROLLOUT_FAILED" = "0" ]; then
  log "health gate (host-published ports)"
  bash "$HERE/health.sh" --profile "$PROFILE" --json "$HEALTH_JSON" 2>&1 | tee -a "$RUN_LOG"
  HEALTH_RC=${PIPESTATUS[0]}
else
  err "skipping health gate details — rollout already failed"
  bash "$HERE/health.sh" --profile "$PROFILE" --json "$HEALTH_JSON" 2>&1 | tee -a "$RUN_LOG" || true
fi

if [ "$HEALTH_RC" -ne 0 ]; then
  err "HEALTH GATE FAILED (exit $HEALTH_RC) — deploy NOT promoted to last-known-good"
  if [ "$DO_ROLLBACK" = "1" ] && dana_state_healthy; then
    warn "rolling back to last-known-good"
    if bash "$HERE/rollback.sh" --profile "$PROFILE" --reason "deploy $RUN_ID failed health gate"; then
      err "deploy failed; rollback restored the previous known-good stack"
      exit 1
    fi
    err "deploy failed AND rollback failed — manual intervention required"
    exit 3
  fi
  if [ "$DO_ROLLBACK" = "1" ]; then
    warn "no healthy last-known-good on record — nothing to roll back to"
  fi
  exit 1
fi

# ---------------------------------------------------------------------------
# 5. Promote to last-known-good (ONLY if every gate passed)
# ---------------------------------------------------------------------------
if [ "$DO_PROMOTE" != "1" ]; then
  warn "health green but --no-promote set: last-known-good left unchanged"
  exit 0
fi

log "collecting deploy facts"
COLLECT_ARGS=(
  --project "$PROJECT"
  --out "$CANDIDATE"
  --git-root "$DANA_ROOT"
  --profile "$PROFILE"
  --recorded-by "deploy/gpu/deploy.sh run=$RUN_ID"
  --stamp "$RUN_ID"
  --health-json "$HEALTH_JSON"
  --spec "$SPEC"
)
for f in "${COMPOSE_FILES[@]}"; do COLLECT_ARGS+=(-f "$f"); done
[ -n "$ENV_FILE" ] && COLLECT_ARGS+=(--env-file "$ENV_FILE")

if ! python3 "$DANA_STATE_PY" collect "${COLLECT_ARGS[@]}" 2>&1 | tee -a "$RUN_LOG"; then
  warn "could not collect deploy facts — check the candidate file: $CANDIDATE"
  exit 1
fi

if python3 "$DANA_STATE_PY" record --state "$DANA_STATE_FILE" --input "$CANDIDATE" \
    --source "deploy.sh:${RUN_ID}" 2>&1 | tee -a "$RUN_LOG"; then
  ok "PROMOTED to last-known-good"
  python3 "$DANA_STATE_PY" show --state "$DANA_STATE_FILE" | tee -a "$RUN_LOG"
  ok "deploy complete in $((SECONDS))s"
  exit 0
fi

err "promotion failed — last-known-good NOT updated"
exit 1
