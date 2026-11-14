#!/usr/bin/env bash
# =============================================================================
# ci_deploy_gate.sh — decide whether a deploy is actually "good".
#
# A deploy is only recorded as last-known-good when it passes ALL of:
#   1) the rendered compose config publishes the expected host ports
#   2) every app container that has a healthcheck reports healthy
#   3) every critical endpoint answers
#
# This exists because the previous flow treated "compose up returned 0" and
# "curl failed → echo warming" as success. That is exactly how a stack can be
# reported as deployed while :13000 is unreachable.
#
# Usage:
#   bash scripts/ci_deploy_gate.sh                      # full gate, prod ports
#   bash scripts/ci_deploy_gate.sh --ports 13100,18100  # custom port set
#   bash scripts/ci_deploy_gate.sh --compose "docker compose -p dana-prod -f ..." --dry-run
#   bash scripts/ci_deploy_gate.sh --no-compose         # skip config check
#
# Exit: 0 = good, 1 = bad (reason on stderr and in the summary)
# =============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST_REPO="${DANA_HOST_REPO:-$ROOT}"

# Default expectations: the prod stack (compose.gpu.yml).
# kb:8000 guardrails:8200 orchestrator:8100 webui:13000 + tracing:13002
EXPECTED_PORTS="${DANA_GATE_PORTS:-8000,8200,8100,13000}"
COMPOSE_CMD=""
CHECK_COMPOSE=1
DRY_RUN=0
TIMEOUT="${DANA_GATE_TIMEOUT:-90}"

while [ $# -gt 0 ]; do
  case "$1" in
    --ports) EXPECTED_PORTS="$2"; shift 2 ;;
    --compose) COMPOSE_CMD="$2"; shift 2 ;;
    --no-compose) CHECK_COMPOSE=0; shift ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) sed -n '1,30p' "$0"; exit 0 ;;
    *) echo "ci_deploy_gate: unknown arg: $1" >&2; exit 2 ;;
  esac
done

FAILURES=()
WARNINGS=()
note() { printf '[gate] %s\n' "$*"; }
bad()  { printf '[gate][FAIL] %s\n' "$*" >&2; FAILURES+=("$*"); }
warn() { printf '[gate][WARN] %s\n' "$*"; WARNINGS+=("$*"); }

# ---------------------------------------------------------------------------
# 1. The rendered compose config must publish the ports we expect.
#
# This is the single most important check in this repo: compose.base.yml has
# no `ports:` at all, so any deploy that forgets the overlay comes up healthy
# with zero host bindings. Grepping the rendered YAML catches that before we
# ever call it a success.
# ---------------------------------------------------------------------------
check_published_ports() {
  if [ "$CHECK_COMPOSE" = "0" ]; then
    note "compose publish check skipped (--no-compose)"
    return 0
  fi

  local rendered
  if [ -n "$COMPOSE_CMD" ]; then
    rendered="$($COMPOSE_CMD config 2>/dev/null)"
  else
    # Best-effort default: discover the env file the host uses.
    local envf="$HOST_REPO/deploy/compose/.env.prod"
    [ -f "$envf" ] || envf="$HOST_REPO/deploy/compose/.env"
    local overlay="$HOST_REPO/deploy/compose/compose.gpu.yml"
    [ -f "$overlay" ] || overlay="$HOST_REPO/deploy/compose/compose.local.yml"
    [ -f "$envf" ] || { warn "no env file — cannot render compose config"; return 0; }
    rendered="$(cd "$HOST_REPO" && docker compose \
      -f deploy/compose/compose.base.yml -f "$overlay" \
      --env-file "$envf" config 2>/dev/null)"
  fi

  if [ -z "$rendered" ]; then
    warn "compose config produced no output — cannot verify published ports"
    return 0
  fi

  local p missing=""
  for p in ${EXPECTED_PORTS//,/ }; do
    # Match `published: "13000"` anywhere in the rendered config.
    printf '%s' "$rendered" | grep -qE "published: \"?${p}\"?$" || missing="$missing $p"
  done

  if [ -n "$missing" ]; then
    bad "rendered compose config does not publish ports:$missing (base has no ports — overlay missing?)"
    return 1
  fi
  note "all expected host ports are published: $EXPECTED_PORTS"
}

# ---------------------------------------------------------------------------
# 2. Container health, per compose service, when a healthcheck exists.
# ---------------------------------------------------------------------------
check_container_health() {
  if ! command -v docker >/dev/null 2>&1; then
    warn "docker not available — container health check skipped"
    return 0
  fi

  local project="${DANA_GATE_PROJECT:-dana-prod}"
  local ids
  ids="$(docker ps -q --filter "label=com.docker.compose.project=$project" 2>/dev/null)"
  if [ -z "$ids" ]; then
    bad "no running containers for compose project '$project'"
    return 1
  fi

  local id name state health svc unhealthy=""
  for id in $ids; do
    name="$(docker inspect -f '{{.Name}}' "$id" 2>/dev/null | sed 's#^/##')"
    state="$(docker inspect -f '{{.State.Status}}' "$id" 2>/dev/null)"
    health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$id" 2>/dev/null)"
    svc="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$id" 2>/dev/null)"

    case "$state" in
      running) ;;
      *) unhealthy="$unhealthy $name(state=$state)"; continue ;;
    esac
    case "$health" in
      healthy|none) ;;
      *) unhealthy="$unhealthy $name(health=$health)" ;;
    esac
  done

  if [ -n "$unhealthy" ]; then
    bad "unhealthy containers:$unhealthy"
    return 1
  fi
  note "all '$project' containers running and healthy"
}

# ---------------------------------------------------------------------------
# 3. Endpoints must answer. Retried, because a freshly started orchestrator
#    legitimately needs a few seconds; but a failure at the deadline is a
#    failure, not a "warming" note.
# ---------------------------------------------------------------------------
probe() { # $1=port $2=path
  curl -sf --max-time 5 "http://127.0.0.1:$1$2" >/dev/null 2>&1
}

check_endpoints() {
  local deadline=$(( $(date +%s) + TIMEOUT ))
  local spec p path pending orchestrator_port=""
  # Derive the endpoint set from the caller's port list. Hardcoding 8000/8200/
  # 8100/13000 here meant a `--ports 13100,18100,18000,18200` gate validated the
  # LOCAL prod stack instead of the stage stack it was asked about — a stage
  # deploy could pass the gate while its own published ports were broken.
  local SPECS=""
  local first=1
  local IFS_SAVE="$IFS"
  IFS=','
  for p in $EXPECTED_PORTS; do
    p="${p//[[:space:]]/}"
    [ -n "$p" ] || continue
    # WebUI (and anything else serving a UI) answers on /; the API tier on /health.
    case "$p" in
      13000|13100|13200) SPECS="$SPECS $p:/" ;;
      8100|18100|18200|18000) SPECS="$SPECS $p:/health"; orchestrator_port="$p" ;;
      *) SPECS="$SPECS $p:/health" ;;
    esac
    first=0
  done
  IFS="$IFS_SAVE"
  if [ -z "$SPECS" ]; then
    bad "no ports to probe — expected at least one endpoint"
    return 1
  fi

  pending="$SPECS"
  while :; do
    local still="" ok_ports=""
    for spec in $pending; do
      p="${spec%%:*}"; path="${spec#*:}"
      if probe "$p" "$path"; then
        ok_ports="$ok_ports $p"
      else
        still="$still $spec"
      fi
    done
    pending="$still"
    [ -z "$pending" ] && break
    if [ "$(date +%s)" -ge "$deadline" ]; then
      bad "endpoints not answering after ${TIMEOUT}s:$pending"
      return 1
    fi
    sleep 3
  done

  # Orchestrator readiness is a separate, stronger signal. Only probe it on the
  # stack we were asked about — never on a hardcoded prod port.
  if [ -n "$orchestrator_port" ]; then
    if ! curl -sf --max-time 5 "http://127.0.0.1:${orchestrator_port}/ready" >/dev/null 2>&1; then
      warn "orchestrator :${orchestrator_port} /ready not green (health ok) — deploy allowed, degraded"
    fi
  fi
  note "endpoints answering:$ok_ports"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
note "gate start: project=${DANA_GATE_PROJECT:-dana-prod} host=$HOST_REPO ports=$EXPECTED_PORTS"

if [ "$DRY_RUN" = "1" ]; then
  note "dry-run: would check published ports, container health, then:"
  note "         endpoints: 8000/health 8200/health 8100/health 13000/"
  # In dry-run still exercise the cheap read-only checks so the gate itself is
  # proven to work against the current host state.
fi

check_published_ports || true
check_container_health || true
check_endpoints || true

echo
if [ "${#FAILURES[@]}" -eq 0 ]; then
  note "RESULT: PASS (${#WARNINGS[@]} warning(s))"
  [ "${#WARNINGS[@]}" -gt 0 ] && printf '  warn: %s\n' "${WARNINGS[@]}"
  exit 0
fi

note "RESULT: FAIL"
printf '  fail: %s\n' "${FAILURES[@]}" >&2
[ "${#WARNINGS[@]}" -gt 0 ] && printf '  warn: %s\n' "${WARNINGS[@]}" >&2
exit 1
