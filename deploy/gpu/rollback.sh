#!/usr/bin/env bash
# =============================================================================
# deploy/gpu/rollback.sh — restore the recorded last-known-good stack.
#
# WHY NOT `git checkout <sha> && compose up`: a git SHA does not pin what was
# actually serving. The image could be rebuilt from a different working tree, a
# different env file, or (the Nov 2026 incident) a DIFFERENT COMPOSE LAYERING with
# no `ports:` at all. So rollback restores the recorded facts instead:
#
#   * the same compose files + env file + project name,
#   * the same resolved config hash (verified before and after),
#   * the exact image IDs that were running,
#   * and then re-verifies host-published ports via health.sh before declaring
#     success.
#
# Image restoration does not depend on a registry: before switching, the recorded
# image IDs are re-tagged into stable rollback tags
# (dana-lastgood/<service>:<stamp>-<sha>), which `deploy.sh` records at promotion
# time. `docker tag` is local-only, so rollback works offline on the GPU host even
# if the registry is unreachable or the images were rebuilt since.
#
# Usage:
#   bash deploy/gpu/rollback.sh                     # roll back to last_good.json
#   bash deploy/gpu/rollback.sh --dry-run
#   bash deploy/gpu/rollback.sh --from-state deploy/gpu/state/last_good.prev.json
#   bash deploy/gpu/rollback.sh --profile stage
#   bash deploy/gpu/rollback.sh --reason "deploy 20261114T... failed health gate"
#   bash deploy/gpu/rollback.sh --force             # proceed even if state looks odd
#
# Exit codes: 0 restored + verified healthy, 1 restore failed, 2 usage,
#             3 restored but health gate still red (do not paper over it).
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$HERE/lib/common.sh"

PROFILE=""
STATE_OVERRIDE=""
DRY_RUN=0
REASON="manual"
FORCE=0
TIMEOUT=420

while [ $# -gt 0 ]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --profile=*) PROFILE="${1#*=}"; shift ;;
    --from-state) STATE_OVERRIDE="$2"; shift 2 ;;
    --reason) REASON="$2"; shift 2 ;;
    --dry-run|-n) DRY_RUN=1; shift ;;
    --force) FORCE=1; shift ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    -h|--help) sed -n '1,36p' "$0"; exit 0 ;;
    *) die "rollback.sh: unknown arg: $1" ;;
  esac
done

STATE_FILE="${STATE_OVERRIDE:-$DANA_STATE_FILE}"
[ -f "$STATE_FILE" ] || die "no state file at $STATE_FILE — nothing to roll back to"

# ---------------------------------------------------------------------------
# 1. Read + validate the recorded facts
# ---------------------------------------------------------------------------
if ! python3 "$DANA_STATE_PY" validate --state "$STATE_FILE" >/dev/null 2>&1; then
  if [ "$FORCE" = "1" ]; then
    warn "state file failed validation — continuing because --force"
  else
    err "state file $STATE_FILE is invalid/corrupt:"
    python3 "$DANA_STATE_PY" validate --state "$STATE_FILE" || true
    die "refusing to roll back to an unverifiable state (use --force to override)"
  fi
fi

python3 "$DANA_STATE_PY" show --state "$STATE_FILE"

REC_PROFILE="$(python3 "$DANA_STATE_PY" get --state "$STATE_FILE" --field profile --default gpu)"
REC_PROJECT="$(python3 "$DANA_STATE_PY" get --state "$STATE_FILE" --field project --default "")"
REC_SHA="$(python3 "$DANA_STATE_PY" get --state "$STATE_FILE" --field compose.config_sha256 --default "")"
REC_ENV="$(python3 "$DANA_STATE_PY" get --state "$STATE_FILE" --field compose.env_file --default "")"
REC_STATUS="$(python3 "$DANA_STATE_PY" get --state "$STATE_FILE" --field status --default "")"

[ -n "$PROFILE" ] || PROFILE="$REC_PROFILE"
[ -n "$REC_PROJECT" ] || REC_PROJECT="$(dana_profile_project "$PROFILE")"

# Same guard deploy/health/reconcile run. Rollback is the most destructive path
# we have (it force-replaces every service's image), so a leaked DANA_PROJECT /
# DANA_COMPOSE_FILES / DANA_ENV_FILE must not silently redirect it at another
# stack. For a production profile this is fatal unless DANA_ALLOW_OVERRIDE=1.
dana_guard_overrides "$PROFILE" || die "refusing to roll back with uncontrolled overrides"

ENV_FILE="${DANA_ENV_FILE:-$REC_ENV}"
[ -n "$ENV_FILE" ] && [ ! -f "$ENV_FILE" ] && die "recorded env file is missing: $ENV_FILE"

if [ "$REC_STATUS" != "healthy" ] && [ "$FORCE" != "1" ]; then
  die "state file status=$REC_STATUS (not 'healthy') — refusing to call this last-known-good"
fi

SPEC="$(dana_port_spec "$PROFILE")" || die "unknown profile '$PROFILE' in state"
log "rollback reason: $REASON"
log "target: profile=$PROFILE project=$REC_PROJECT config=${REC_SHA:0:12}"

COMPOSE_FILES=()
while IFS= read -r f; do [ -n "$f" ] && COMPOSE_FILES+=("$f"); done < <(dana_profile_files "$PROFILE")
[ "${#COMPOSE_FILES[@]}" -gt 0 ] || die "profile '$PROFILE' has no compose layering"
for f in "${COMPOSE_FILES[@]}"; do [ -f "$f" ] || die "compose file missing: $f"; done

# ---------------------------------------------------------------------------
# 2. Verify the layering still reproduces the recorded config hash
# ---------------------------------------------------------------------------
CUR_SHA="$(dana_config_sha "$PROFILE" "$REC_PROJECT" "$ENV_FILE" || true)"
if [ -n "$REC_SHA" ] && [ -n "$CUR_SHA" ] && [ "$REC_SHA" != "$CUR_SHA" ]; then
  warn "current config (${CUR_SHA:0:12}) differs from recorded (${REC_SHA:0:12})"
  warn "the compose files/env have changed since the good deploy — restoring images"
  warn "alone may not reproduce it exactly. Continuing; health gate is authoritative."
fi

# ---------------------------------------------------------------------------
# 3. Resolve the images to restore
# ---------------------------------------------------------------------------
# Prefer the recorded rollback tag (local, always present after promotion).
# Fall back to the recorded image ID, then to the image ref.
SERVICES=""
for t in $SPEC; do SERVICES="$SERVICES ${t%%:*}"; done

resolve_image() {
  local svc="$1"
  python3 - "$STATE_FILE" "$svc" <<'PY'
import json, sys
state, svc = sys.argv[1], sys.argv[2]
data = json.load(open(state))
for img in data.get("images") or []:
    if img.get("service") != svc:
        continue
    for key in ("image_id", "rollback_tag", "image"):
        val = img.get(key)
        if val:
            print(val)
            sys.exit(0)
sys.exit(1)
PY
}

state_image_field() { # <service> <field>
  python3 - "$STATE_FILE" "$1" "$2" <<'PY'
import json, sys
state, svc, field = sys.argv[1], sys.argv[2], sys.argv[3]
data = json.load(open(state))
for img in data.get("images") or []:
    if img.get("service") == svc:
        print(img.get(field) or "")
        sys.exit(0)
sys.exit(0)
PY
}

# Resolved images are stored in a plain file (bash 3.2 on macOS/some hosts has no
# associative arrays, and this must run on any host the deploy runs on).
RESTORE_PLAN="$DANA_STATE_DIR/restore-plan.txt"
: >"$RESTORE_PLAN"
MISSING=0
for svc in $SERVICES; do
  img="$(resolve_image "$svc" 2>/dev/null || true)"
  if [ -z "$img" ]; then
    if dana_is_optional "$svc"; then
      warn "$svc: no recorded image (optional) — skipping"
      continue
    fi
    err "$svc: no recorded image in $STATE_FILE"
    MISSING=1
    continue
  fi
  if ! docker image inspect "$img" >/dev/null 2>&1; then
    warn "$svc: recorded image '$img' is not present locally (pruned?) — will reuse current image ref"
    img=""
  fi
  printf '%s|%s|%s|%s\n' "$svc" "$img" "$(state_image_field "$svc" rollback_tag)" "$(state_image_field "$svc" image)" >>"$RESTORE_PLAN"
done
[ "$MISSING" = "0" ] || die "cannot roll back: recorded images missing for required services"

if [ "$DRY_RUN" = "1" ]; then
  echo
  log "dry-run — would restore:"
  while IFS='|' read -r svc img tag ref; do
    [ -n "$img" ] && printf '  %-13s %s\n' "$svc" "$img"
  done <"$RESTORE_PLAN"
  echo "  project   : $REC_PROJECT"
  echo "  layering  : ${COMPOSE_FILES[*]}"
  echo "  env file  : ${ENV_FILE:-<none>}"
  echo "  then      : deploy/gpu/health.sh --profile $PROFILE"
  exit 0
fi

dana_compose_args "$PROFILE" "$REC_PROJECT" "$ENV_FILE" "${COMPOSE_FILES[@]}"
ORDER_ARGS=(--project "$REC_PROJECT")
for f in "${COMPOSE_FILES[@]}"; do ORDER_ARGS+=(-f "$f"); done
[ -n "$ENV_FILE" ] && ORDER_ARGS+=(--env-file "$ENV_FILE")
dana_ensure_log_dir
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_LOG="$DANA_LOG_DIR/rollback-$RUN_ID.log"
echo "rollback $RUN_ID reason=$REASON" >>"$RUN_LOG"

# ---------------------------------------------------------------------------
# 4. Pin the recorded image IDs via a generated compose override
# ---------------------------------------------------------------------------
# Do NOT re-point the project's normal image tags: several services can share one
# ref (e.g. python:3.11-slim), and mutating a shared tag leaks the rollback into
# unrelated stacks. Instead we materialize the recorded IDs as stable local tags
# and then add a generated override LAST in the layering, so compose resolves
# `image:` to exactly the recorded bytes.
# Unique per process: RUN_ID is second-granular, and two heal paths (deploy.sh's
# auto-rollback and reconcile.sh's rollback) can land in the same second. Sharing
# one pin file made them interleave and produce a YAML with `services:` defined
# twice, which compose rejects — so the rollback "failed" without restoring.
PIN_FILE="$DANA_STATE_DIR/rollback-$RUN_ID-$$-${RANDOM:-0}.pin.yml"
printf '%s\n' \
  "# GENERATED by deploy/gpu/rollback.sh — do not edit." \
  "# Pins each service to the image ID recorded in the promoted last-known-good." \
  "services:" >"$PIN_FILE"

PINNED=0
while IFS='|' read -r svc img tag ref; do
  [ -n "$img" ] || continue
  [ -n "$tag" ] || continue
  if ! docker tag "$img" "$tag" 2>>"$RUN_LOG"; then
    warn "  $svc: could not tag ${img:0:19} -> $tag"
    continue
  fi
  log "  $svc -> $tag"
  {
    echo "  $svc:"
    echo "    image: $tag"
  } >>"$PIN_FILE"
  PINNED=$((PINNED + 1))
done <"$RESTORE_PLAN"

if [ "$PINNED" -gt 0 ]; then
  docker compose -p "$REC_PROJECT" \
    $(for f in "${COMPOSE_FILES[@]}"; do printf -- '-f %s ' "$f"; done) \
    -f "$PIN_FILE" ${ENV_FILE:+--env-file "$ENV_FILE"} config -q 2>>"$RUN_LOG" \
    || die "generated pin override is not a valid compose file: $PIN_FILE"
  # Append the pin override so it wins over every base/overlay image: value.
  DANA_COMPOSE_ARGS+=(-f "$PIN_FILE")
  ok "pinned $PINNED service(s) to recorded image IDs ($PIN_FILE)"
else
  warn "no services pinned — rolling back on current image refs"
fi

log "bringing stack up on recorded images"
UP_ORDER="$(python3 "$DANA_STATE_PY" order "${ORDER_ARGS[@]}" 2>/dev/null | tr '\n' ' ')"
if [ -z "$UP_ORDER" ]; then
  UP_ORDER="postgres redis kb guardrails tracing orchestrator webui"
  warn "could not derive startup order — using the documented production order"
fi
log "startup order: $UP_ORDER"

# Bring the stack up one tier at a time so a slow dependency cannot be raced, and
# so a failure points at the tier that broke rather than "something went wrong".
UP_FAILED=0
for svc in $UP_ORDER; do
  docker compose "${DANA_COMPOSE_ARGS[@]}" up -d --no-build --force-recreate "$svc" >>"$RUN_LOG" 2>&1 \
    || { warn "ordered up: $svc returned non-zero"; UP_FAILED=1; }
done
if [ "$UP_FAILED" = "1" ]; then
  warn "some tiers returned non-zero — retrying once with all services"
  docker compose "${DANA_COMPOSE_ARGS[@]}" up -d --no-build --force-recreate >>"$RUN_LOG" 2>&1 \
    || die "compose up failed during rollback — see $RUN_LOG"
fi

# ---------------------------------------------------------------------------
# 5. Re-verify: published ports + host probes, bounded by TIMEOUT
# ---------------------------------------------------------------------------
log "re-verifying health (host-published ports) with ${TIMEOUT}s budget"
HEALTH_JSON="$DANA_STATE_DIR/health-rollback-$RUN_ID.json"
deadline=$((SECONDS + TIMEOUT))
RC=1
while [ "$SECONDS" -lt "$deadline" ]; do
  if bash "$HERE/health.sh" --profile "$PROFILE" --quiet --json "$HEALTH_JSON" >/dev/null 2>&1; then
    RC=0
    break
  fi
  sleep 5
done

echo
bash "$HERE/health.sh" --profile "$PROFILE" --json "$HEALTH_JSON" || RC=$?

if [ "$RC" -eq 0 ]; then
  ok "ROLLBACK VERIFIED: stack restored to last-known-good and healthy"

  # Pin files are kept on purpose: the running project still has the pin mounted
  # as its last compose layer, so deleting the newest one would break the next
  # `compose ps/up` for this project. Only old pins are pruned, and never the
  # one this run just created.
  if [ -n "${DANA_KEEP_PINS:-}" ]; then
    KEEP="$DANA_KEEP_PINS"
  else
    KEEP=5
  fi
  if [ "${KEEP:-0}" -gt 0 ] 2>/dev/null; then
    # shellcheck disable=SC2012
    ls -1t "$DANA_STATE_DIR"/rollback-*.pin.yml 2>/dev/null \
      | grep -vxF "$PIN_FILE" \
      | tail -n "+$((KEEP + 1))" \
      | while IFS= read -r old; do
          [ -n "$old" ] || continue
          rm -f "$old" && log "pruned old rollback pin $(basename "$old")"
        done
  fi

  # Keep last_good.json authoritative: do not overwrite it with the rollback
  # (it already describes precisely these images/config). Just annotate history.
  python3 - "$DANA_STATE_FILE" "$REASON" "$RUN_ID" <<'PY' 2>/dev/null || true
import json, sys, datetime, os
state, reason, run_id = sys.argv[1:4]
try:
    data = json.load(open(state))
except Exception:
    sys.exit(0)
sched = data.setdefault("schedule", {})
sched["last_rollback_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
sched["last_rollback_reason"] = reason
sched["last_rollback_run"] = run_id
tmp = state + ".tmp"
with open(tmp, "w") as fh:
    json.dump(data, fh, indent=2, sort_keys=True)
    fh.write("\n")
os.replace(tmp, state)
PY
  exit 0
fi

err "ROLLBACK DID NOT REACH HEALTHY — stack is up on recorded images but failing gates"
err "this needs a human: check $RUN_LOG and the verdict table above"
exit 3
