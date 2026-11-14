#!/usr/bin/env bash
# Shared helpers for the GPU/production deploy path.
#
# Sourced by deploy/gpu/{health,deploy,rollback,reconcile}.sh. It exists so that
# project name, compose layering, env file, and the service/port contract are
# defined exactly once. Every historical incident in this layer came from one of
# those four things being re-typed slightly differently in a second script.
#
# Hard rule encoded here: the compose project name is ALWAYS passed with `-p`.
# An env file's COMPOSE_PROJECT_NAME (deploy/compose/.env says dana-local) will
# otherwise silently retarget a prod deploy onto the laptop stack.
set -uo pipefail

DANA_GPU_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # deploy/gpu
DANA_DEPLOY_DIR="$(cd "$DANA_GPU_DIR/.." && pwd)"                 # deploy
DANA_ROOT="$(cd "$DANA_DEPLOY_DIR/.." && pwd)"                    # repo root
DANA_COMPOSE_DIR="$DANA_DEPLOY_DIR/compose"
DANA_STATE_DIR="${DANA_STATE_DIR:-$DANA_GPU_DIR/state}"
# The state file must live inside the state dir. Deriving it from DANA_STATE_FILE
# alone let a stale exported value point state operations at a DIFFERENT stack
# than the directory being inspected (seen during testing: rollback wrote sim
# state while the caller read /tmp state). If DANA_STATE_FILE is set explicitly it
# must agree with DANA_STATE_DIR.
#
# A mismatch is a REFUSAL, not a warning: adopting the foreign path is exactly
# how rollback once wrote one stack's state while the caller read another. The
# only escape hatch is the deliberate DANA_ALLOW_OVERRIDE=1 used by the sim
# harness, which is opt-in and noisy.
if [ -n "${DANA_STATE_FILE:-}" ]; then
  case "$DANA_STATE_FILE" in
    "$DANA_STATE_DIR"/*) : ;;
    *)
      if [ "${DANA_ALLOW_OVERRIDE:-0}" = "1" ]; then
        printf '%s[warn]%s DANA_STATE_FILE=%s is outside DANA_STATE_DIR=%s — override armed (DANA_ALLOW_OVERRIDE=1)\n' \
          "${C_YELLOW:-\033[1;33m}" "${C_OFF:-\033[0m}" "$DANA_STATE_FILE" "$DANA_STATE_DIR" >&2
      else
        printf '%s[fatal]%s DANA_STATE_FILE=%s is outside DANA_STATE_DIR=%s\n' \
          "${C_RED:-\033[0;31m}" "${C_OFF:-\033[0m}" "$DANA_STATE_FILE" "$DANA_STATE_DIR" >&2
        printf '        refusing to operate: rollback/record would touch a different stack than the one inspected.\n' >&2
        printf '        unset DANA_STATE_FILE, or set DANA_ALLOW_OVERRIDE=1 if this is deliberate.\n' >&2
        # Callers run with `set -uo pipefail` (no -e), so `return 1` from a
        # sourced file does not stop them. This is a fatal config error: exit
        # the calling script rather than letting it operate on the wrong stack.
        # Exit 64 ("refused, nothing probed"), NOT 1: callers read 1 as
        # DEPLOY/LAYERING BUG and reconcile.sh would roll back a healthy stack
        # on what is really a stale env var.
        exit 64
      fi
      ;;
  esac
else
  DANA_STATE_FILE="$DANA_STATE_DIR/last_good.json"
fi
DANA_LOG_DIR="${DANA_LOG_DIR:-/var/log/dana-rag}"
DANA_STATE_PY="${DANA_STATE_PY:-$DANA_GPU_DIR/lib/state.py}"

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_RED=$'\033[0;31m'; C_GREEN=$'\033[0;32m'; C_YELLOW=$'\033[1;33m'
  C_BLUE=$'\033[0;34m'; C_DIM=$'\033[2m'; C_BOLD=$'\033[1m'; C_OFF=$'\033[0m'
else
  C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_DIM=""; C_BOLD=""; C_OFF=""
fi

log()  { printf '%s[%s]%s %s\n' "$C_BLUE" "$(date -u +%H:%M:%SZ)" "$C_OFF" "$*"; }
ok()   { printf '%s[OK]%s %s\n'   "$C_GREEN" "$C_OFF" "$*"; }
warn() { printf '%s[WARN]%s%s %s\n' "$C_YELLOW" "$C_OFF" "$C_BOLD" "$*"; }
err()  { printf '%s[FAIL]%s%s %s\n' "$C_RED" "$C_OFF" "$C_BOLD" "$*" >&2; }
die()  { err "$*"; exit 1; }
# Refusal: the script declined to act (bad args, override guard, missing input),
# as opposed to die() which means it tried and failed. Lets a timer/cron tell a
# misconfiguration apart from a real outage. Matches health.sh's exit code 64.
refuse() { err "$*"; exit 64; }

# --- profile -> compose layering + default env file -------------------------
# gpu        : production self-hosted GPU (compose.gpu.yml publishes the ports)
# prod-sim   : laptop rehearsal of the prod topology (base + local + prod-sim)
# stage      : Jenkins develop stack on alt ports
# local      : laptop dev stack
# host       : host-venv stack (deploy/gpu/start.sh); no compose at all
dana_profile_files() {
  # Escape hatch used by tests/other hosts to point the SAME scripts at a
  # different layering. It never bypasses the port gate: whatever files are used
  # must still pass `state.py check-ports` against the profile's port contract.
  if [ -n "${DANA_COMPOSE_FILES:-}" ]; then
    printf '%s\n' $DANA_COMPOSE_FILES
    return 0
  fi
  case "${1:-gpu}" in
    gpu)      printf '%s\n' "$DANA_COMPOSE_DIR/compose.base.yml" "$DANA_COMPOSE_DIR/compose.gpu.yml" ;;
    prod-sim) printf '%s\n' "$DANA_COMPOSE_DIR/compose.base.yml" "$DANA_COMPOSE_DIR/compose.local.yml" "$DANA_COMPOSE_DIR/compose.prod-sim.yml" ;;
    stage)    printf '%s\n' "$DANA_COMPOSE_DIR/compose.base.yml" "$DANA_COMPOSE_DIR/compose.local.yml" "$DANA_COMPOSE_DIR/compose.stage.yml" ;;
    local)    printf '%s\n' "$DANA_COMPOSE_DIR/compose.base.yml" "$DANA_COMPOSE_DIR/compose.local.yml" ;;
    host)     : ;;
    *)        return 2 ;;
  esac
}

dana_profile_project() {
  if [ -n "${DANA_PROJECT:-}" ]; then
    printf '%s\n' "$DANA_PROJECT"
    return 0
  fi
  case "${1:-gpu}" in
    gpu)      echo "dana-prod" ;;
    prod-sim) echo "dana-prod-sim" ;;
    stage)    echo "dana-stage" ;;
    local)    echo "dana-local" ;;
    host)     echo "dana-host" ;;
    *)        return 2 ;;
  esac
}

dana_profile_env() {
  case "${1:-gpu}" in
    gpu)      for f in "$DANA_COMPOSE_DIR/.env.prod" "$DANA_COMPOSE_DIR/env.gpu.example"; do [ -f "$f" ] && { echo "$f"; return; }; done ;;
    prod-sim|stage|local) [ -f "$DANA_COMPOSE_DIR/.env" ] && { echo "$DANA_COMPOSE_DIR/.env"; return; } ;;
    host)     : ;;
  esac
  echo ""
}

# --- service/port contract (single definition) ------------------------------
# svc:published:target:healthPath  ("-" = TCP reachable only, no HTTP path)
dana_port_spec() {
  if [ -n "${DANA_PORT_SPEC:-}" ]; then
    printf '%s\n' "$DANA_PORT_SPEC"
    return 0
  fi
  case "${1:-gpu}" in
    gpu|prod-sim)
      echo "postgres:15432:5432:- redis:16379:6379:- kb:8000:8000:/health guardrails:8200:8200:/health tracing:13002:3000:/api/public/health orchestrator:8100:8100:/health webui:13000:8080:/health"
      ;;
    stage)
      echo "postgres:25432:5432:- redis:26379:6379:- kb:18000:8000:/health guardrails:18200:8200:/health tracing:13001:3000:/api/public/health orchestrator:18100:8100:/health webui:13100:8080:/health"
      ;;
    local)
      echo "postgres:15432:5432:- redis:16379:6379:- kb:8000:8000:/health guardrails:8200:8200:/health tracing:13002:3000:/api/public/health orchestrator:8100:8100:/health webui:13000:8080:/health"
      ;;
    host)
      echo "postgres:5432:5432:- kb:8000:8000:/health guardrails:8200:8200:/health tracing:3000:3000:/api/public/health orchestrator:8100:8100:/health webui:13000:8080:/health gemma:18000:18000:/health"
      ;;
    *) return 2 ;;
  esac
}

# Critical services that must be up for the site to serve. Optional ones are
# reported (WARN) but never fail the gate.
dana_optional_services() { echo "tracing redis"; }

dana_is_optional() {
  local svc="$1" opt
  for opt in $(dana_optional_services); do [ "$svc" = "$opt" ] && return 0; done
  return 1
}

# Build the compose argument list into the global array DANA_COMPOSE_ARGS.
# Callers then use: docker compose "${DANA_COMPOSE_ARGS[@]}" up -d --wait
dana_compose_args() {
  local profile="$1" project="$2" env_file="$3"
  shift 3
  DANA_COMPOSE_ARGS=(-p "$project")
  local f
  if [ "$#" -gt 0 ]; then
    for f in "$@"; do DANA_COMPOSE_ARGS+=(-f "$f"); done
  else
    while IFS= read -r f; do [ -n "$f" ] && DANA_COMPOSE_ARGS+=(-f "$f"); done < <(dana_profile_files "$profile")
  fi
  [ -n "$env_file" ] && DANA_COMPOSE_ARGS+=(--env-file "$env_file")
  return 0
}

# Host-side loopback probe. Returns 0 only when the PUBLISHED host port answers.
dana_probe_http() {
  local port="$1" path="${2:-/health}" timeout="${3:-6}"
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$timeout" "http://127.0.0.1:${port}${path}" 2>/dev/null)"
  [ "$code" = "200" ] || [ "$code" = "204" ] || [ "$code" = "301" ] || [ "$code" = "302" ] || [ "$code" = "307" ] || [ "$code" = "401" ] || [ "$code" = "403" ]
}

dana_probe_body() {
  local port="$1" path="${2:-/health}" timeout="${3:-6}"
  curl -s --max-time "$timeout" "http://127.0.0.1:${port}${path}" 2>/dev/null
}

dana_port_listening() {
  local port="$1"
  python3 - "$port" <<'PY' 2>/dev/null
import socket, sys
port = int(sys.argv[1])
s = socket.socket()
s.settimeout(3)
try:
    s.connect(("127.0.0.1", port))
except OSError:
    sys.exit(1)
finally:
    s.close()
sys.exit(0)
PY
}

dana_have_compose() { command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; }

# docker compose ps as a lookup: given service name, print "container|health|state|image|id".
dana_compose_ps_field() {
  local svc="$1"
  docker compose "${DANA_COMPOSE_ARGS[@]}" ps --format \
    '{{.Service}}|{{.Name}}|{{.Health}}|{{.State}}|{{.Image}}|{{.ID}}' 2>/dev/null \
    | awk -F'|' -v s="$svc" '$1==s {print; exit}'
}

# Authoritative health of one service, straight from docker inspect:
#   healthy | unhealthy | starting | none | missing
# `compose ps` is not usable for gating: it prints an EMPTY health column both
# for "no healthcheck defined" and for "container not registered yet", which
# makes a wait loop break out instantly and claim success too early.
dana_service_health() {
  local svc="$1" cid
  cid="$(docker compose "${DANA_COMPOSE_ARGS[@]}" ps -q "$svc" 2>/dev/null | head -1)"
  if [ -z "$cid" ]; then
    # Fall back to the project's container naming before declaring it missing.
    # The project name comes from the -p already present in DANA_COMPOSE_ARGS.
    local proj
    proj="$(printf '%s\n' "${DANA_COMPOSE_ARGS[@]}" | grep -A1 '^-p$' | tail -1)"
    [ -n "$proj" ] || proj="${DANA_PROJECT:-dana-prod}"
    cid="$(docker ps -aq --filter "label=com.docker.compose.service=$svc" \
             --filter "label=com.docker.compose.project=$proj" 2>/dev/null | head -1)"
  fi
  [ -n "$cid" ] || { echo missing; return 0; }
  local h
  h="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null)"
  echo "${h:-missing}"
}

# Live publisher check straight from docker: prints "HOSTIP:HOSTPORT" lines for a
# container, or nothing when the container publishes no ports at all.
dana_live_publishers() {
  local container="$1"
  [ -n "$container" ] || return 0
  docker inspect --format '{{json .NetworkSettings.Ports}}' "$container" 2>/dev/null \
    | python3 -c '
import json, sys
try:
    ports = json.load(sys.stdin) or {}
except Exception:
    sys.exit(0)
seen = []
for bindings in ports.values():
    for b in bindings or []:
        hp = b.get("HostPort")
        if hp:
            seen.append("%s:%s" % (b.get("HostIp") or "0.0.0.0", hp))
print("\n".join(seen))
'
}

dana_published_port_match() {
  local container="$1" want="$2"
  dana_live_publishers "$container" | awk -F: -v w="$want" '$NF==w {found=1} END {exit !found}'
}

dana_state() { python3 "$DANA_STATE_PY" "$@"; }

# sha256 of the resolved compose config for a profile. Single implementation —
# deploy.sh, rollback.sh and health.sh must agree on this exact value or drift
# detection produces false positives.
dana_config_sha() {
  local profile="$1" project="$2" env_file="$3"
  local files=() args=() f
  while IFS= read -r f; do [ -n "$f" ] && files+=("$f"); done < <(dana_profile_files "$profile")
  [ "${#files[@]}" -gt 0 ] || return 1
  args=(--project "$project")
  for f in "${files[@]}"; do args+=(-f "$f"); done
  [ -n "$env_file" ] && args+=(--env-file "$env_file")
  python3 "$DANA_STATE_PY" config "${args[@]}" 2>/dev/null \
    | python3 -c 'import json,sys,hashlib; print(hashlib.sha256(json.dumps(json.load(sys.stdin),sort_keys=True,separators=(",",":")).encode()).hexdigest())' 2>/dev/null
}

dana_state_field() {
  local field="$1" default="${2:-}"
  python3 "$DANA_STATE_PY" get --state "$DANA_STATE_FILE" --field "$field" --default "$default" 2>/dev/null || printf '%s\n' "$default"
}

dana_state_healthy() {
  [ -f "$DANA_STATE_FILE" ] || return 1
  local status
  status="$(dana_state_field status "")"
  [ "$status" = "healthy" ]
}

dana_state_age_seconds() {
  [ -f "$DANA_STATE_FILE" ] || { echo ""; return; }
  local ts
  ts="$(dana_state_field promoted_at "")"
  [ -n "$ts" ] || { echo ""; return; }
  python3 - "$ts" <<'PY'
import datetime, sys
try:
    then = datetime.datetime.strptime(sys.argv[1], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
except ValueError:
    print("")
    sys.exit(0)
now = datetime.datetime.now(datetime.timezone.utc)
print(int((now - then).total_seconds()))
PY
}

dana_zh_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

dana_iso_plus_seconds() {
  python3 - "$1" <<'PY'
import datetime, sys
now = datetime.datetime.now(datetime.timezone.utc)
print((now + datetime.timedelta(seconds=int(sys.argv[1]))).strftime("%Y-%m-%dT%H:%M:%SZ"))
PY
}

# Compare two UTC stamps; exit 0 when now >= stamp (i.e. the wait has elapsed).
dana_due() {
  python3 - "$1" <<'PY'
import datetime, sys
raw = (sys.argv[1] or "").strip()
if not raw:
    sys.exit(0)
try:
    due = datetime.datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
except ValueError:
    sys.exit(0)
now = datetime.datetime.now(datetime.timezone.utc)
sys.exit(0 if now >= due else 1)
PY
}

dana_ensure_log_dir() {
  if ! mkdir -p "$DANA_LOG_DIR" 2>/dev/null; then
    DANA_LOG_DIR="$DANA_GPU_DIR/state/logs"
    mkdir -p "$DANA_LOG_DIR"
  fi
}

# Remove a container that occupies the name compose wants for $1 but is NOT a
# member of this project (or is orphaned by a different file set/label).
#
# Why this is needed: `docker compose up` keys off its own project labels. A
# container created from a DIFFERENT file set (base-only restart, edited overlay,
# generated rollback pin) can hold the name while being invisible to the current
# invocation, so compose aborts with
#   Conflict. The container name "..." is already in use by container "..."
# and the rollout dies half-way, leaving a partially upgraded stack. Removing the
# stale container first makes deploys idempotent and safe to re-run.
#
# Safety: only ever touches a container whose compose PROJECT label matches the
# project we are deploying (or has no compose label at all AND matches the exact
# expected container name for this project). Never matches other stacks.
dana_remove_stale_container() {
  local svc="$1" project="$2"
  local cid proj expected
  expected="${project}-${svc}-1"

  cid="$(docker ps -aq --filter "name=^/${expected}$" 2>/dev/null | head -1)"
  [ -n "$cid" ] || return 0

  proj="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$cid" 2>/dev/null)"

  # Only reclaim when it really is our own project's leftover, or when the name
  # is exactly the one this project would create and it carries no other
  # project's ownership.
  if [ -n "$proj" ] && [ "$proj" != "$project" ]; then
    printf 'stale-check: %s owned by project %s (not %s) — leaving it alone\n' "$expected" "$proj" "$project"
    return 0
  fi

  printf 'stale-check: removing leftover container %s (%s) so compose can recreate it\n' "$expected" "${cid:0:12}"
  docker rm -f "$cid" >/dev/null 2>&1 || true
  return 0
}

# Guard against a leaked override pointing a production operation at a disposable
# stack. Environment overrides are legitimate (tests, alternate hosts), but they
# must be explicit: if an override is active and the caller is operating on a real
# production profile, require DANA_ALLOW_OVERRIDE=1.
dana_guard_overrides() {
  local profile="$1"
  local active=""
  [ -n "${DANA_COMPOSE_FILES:-}" ] && active="$active DANA_COMPOSE_FILES"
  [ -n "${DANA_PROJECT:-}" ] && active="$active DANA_PROJECT"
  [ -n "${DANA_PORT_SPEC:-}" ] && active="$active DANA_PORT_SPEC"
  [ -n "${DANA_ENV_FILE:-}" ] && active="$active DANA_ENV_FILE"
  [ -z "$active" ] && return 0

  case "$profile" in
    gpu|prod-sim)
      if [ "${DANA_ALLOW_OVERRIDE:-0}" != "1" ]; then
        printf '%s[FAIL]%s override(s) active for a production profile:%s\n' \
          "$C_RED" "$C_OFF" "$active" >&2
        printf '  This would act on a DIFFERENT stack than production.\n' >&2
        printf '  Unset them, or set DANA_ALLOW_OVERRIDE=1 if this is deliberate.\n' >&2
        return 1
      fi
      ;;
  esac
  # Surface the override so it can never be invisible in a log.
  printf '%s[warn] overrides active:%s%s\n' "$C_YELLOW" "$active" "$C_OFF" >&2
  return 0
}

# Wait for a TCP port to accept connections, with a bounded deadline. This is a
# readiness gate, not a sleep: it returns as soon as the port answers.
dana_wait_port() {
  local port="$1" timeout="${2:-60}" started=$SECONDS
  while [ $((SECONDS - started)) -lt "$timeout" ]; do
    dana_port_listening "$port" && return 0
    sleep 1
  done
  return 1
}
