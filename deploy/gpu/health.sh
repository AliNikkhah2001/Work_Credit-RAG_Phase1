#!/usr/bin/env bash
# =============================================================================
# deploy/gpu/health.sh — authoritative health gate for the Dana GPU deploy.
#
# This is the SINGLE SOURCE OF TRUTH for "is production actually serving?".
# Every other script (deploy.sh, rollback.sh, reconcile.sh, auto-heal, CI) calls
# it and trusts its exit code. Do not re-implement health probing elsewhere.
#
# WHY THIS EXISTS (2026-11 incident)
#   deploy/compose/compose.base.yml declares NO `ports:` mappings — every reachable
#   port lives in an overlay (compose.gpu.yml for prod, compose.local.yml for dev).
#   A restart that used compose.base.yml alone recreated containers with ZERO
#   published ports. Containers stayed `healthy` (their internal healthchecks probe
#   127.0.0.1 INSIDE the container) while the gateway pointed at a dead host port
#   and the site went dark for ~2 days with no alert.
#
#   Therefore this script NEVER trusts container health alone. For every service it
#   verifies, from the HOST:
#     1. the resolved compose config publishes the expected loopback port,
#     2. the live container really has that port binding,
#     3. the host port is actually listening,
#     4. the host-side HTTP probe returns 2xx/3xx/401/403,
#   and it names the `healthy-but-unpublished` condition explicitly.
#
# Usage:
#   bash deploy/gpu/health.sh                       # prod (gpu) profile
#   bash deploy/gpu/health.sh --profile stage        # dana-stage (13100/18100/...)
#   bash deploy/gpu/health.sh --profile prod-sim
#   bash deploy/gpu/health.sh --json /tmp/h.json     # machine-readable verdicts
#   bash deploy/gpu/health.sh --quiet                # exit code only (no table)
#   bash deploy/gpu/health.sh --no-compose           # host-venv mode (no docker)
#   bash deploy/gpu/health.sh --list                 # print the port contract
#
# Exit codes:
#   0 all critical services OK
#   1 DEPLOY/LAYERING BUG   (no published port, wrong bind, port owned by a
#                            foreign container, config publishes nothing)
#   2 CONTAINER DOWN        (not running / unhealthy / missing)
#   3 ENDPOINT DOWN         (port listening but HTTP probe failed)
#   4 STATE DRIFT           (--state-check: live stack != last-good record)
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$HERE/lib/common.sh"

PROFILE="gpu"
QUIET=0
JSON_OUT=""
NO_COMPOSE=0
LIST_ONLY=0
STATE_CHECK=0
SETTLE_SECONDS=0
REQUIRE_OVERRIDE=""
EXPLICIT_FILES=()
PROJECT_OVERRIDE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --profile=*) PROFILE="${1#*=}"; shift ;;
    --json) JSON_OUT="$2"; shift 2 ;;
    --json=*) JSON_OUT="${1#*=}"; shift ;;
    --quiet|-q) QUIET=1; shift ;;
    --no-compose) NO_COMPOSE=1; shift ;;
    --list) LIST_ONLY=1; shift ;;
    --state-check) STATE_CHECK=1; shift ;;
    --settle) SETTLE_SECONDS="$2"; shift 2 ;;
    --require) REQUIRE_OVERRIDE="$2"; shift 2 ;;
    --project) PROJECT_OVERRIDE="$2"; shift 2 ;;
    -f|--file) EXPLICIT_FILES+=("$2"); shift 2 ;;
    -h|--help) sed -n '1,45p' "$0"; exit 0 ;;
    *) echo "health.sh: unknown arg: $1" >&2; exit 2 ;;
  esac
done

case "$PROFILE" in
  gpu|prod-sim|stage|local|host) ;;
  *) err "unknown --profile '$PROFILE' (gpu|prod-sim|stage|local|host)"; exit 2 ;;
esac

PROJECT="${PROJECT_OVERRIDE:-${DANA_PROJECT:-$(dana_profile_project "$PROFILE")}}"
# Refuse to act on production with leaked overrides (see common.sh).
dana_guard_overrides "$PROFILE" || exit 2
ENV_FILE="${DANA_ENV_FILE:-$(dana_profile_env "$PROFILE")}"
SPEC="$(dana_port_spec "$PROFILE")"
[ -n "$REQUIRE_OVERRIDE" ] && SPEC="$REQUIRE_OVERRIDE"

if [ "$LIST_ONLY" = "1" ]; then
  echo "profile=$PROFILE project=$PROJECT env_file=${ENV_FILE:-<none>}"
  echo "layering:"
  if [ "${#EXPLICIT_FILES[@]}" -gt 0 ]; then
    printf '  %s\n' "${EXPLICIT_FILES[@]}"
  else
    dana_profile_files "$PROFILE" | sed 's/^/  /'
  fi
  echo "port contract (svc published target path):"
  for t in $SPEC; do
    echo "  ${t%%:*}: $(echo "$t" | cut -d: -f2-)"
  done
  exit 0
fi

[ "$SETTLE_SECONDS" -gt 0 ] && sleep "$SETTLE_SECONDS"

# ---------------------------------------------------------------------------
# Collect evidence
# ---------------------------------------------------------------------------
USE_COMPOSE=1
if [ "$NO_COMPOSE" = "1" ] || [ "$PROFILE" = "host" ] || ! dana_have_compose; then
  USE_COMPOSE=0
fi

TMPDIR_H=$(mktemp -d "${TMPDIR:-/tmp}/dana-health.XXXXXX")
trap 'rm -rf "$TMPDIR_H"' EXIT

CONFIG_PORTS_JSON="$TMPDIR_H/ports.json"
CONFIG_OK=1
CONFIG_ERR=""

if [ "$USE_COMPOSE" = "1" ]; then
  COMPOSE_FILES=()
  if [ "${#EXPLICIT_FILES[@]}" -gt 0 ]; then
    COMPOSE_FILES=("${EXPLICIT_FILES[@]}")
  else
    while IFS= read -r f; do [ -n "$f" ] && COMPOSE_FILES+=("$f"); done < <(dana_profile_files "$PROFILE")
  fi
  if [ "${#COMPOSE_FILES[@]}" -eq 0 ]; then
    USE_COMPOSE=0
  else
    dana_compose_args "$PROFILE" "$PROJECT" "$ENV_FILE" "${COMPOSE_FILES[@]}"
    ARGS=(--project "$PROJECT")
    for f in "${COMPOSE_FILES[@]}"; do ARGS+=(-f "$f"); done
    [ -n "$ENV_FILE" ] && ARGS+=(--env-file "$ENV_FILE")
    ARGS+=(--spec "$SPEC" --json-out "$CONFIG_PORTS_JSON")
    if python3 "$DANA_STATE_PY" check-ports "${ARGS[@]}" >"$TMPDIR_H/ports.log" 2>&1; then
      CONFIG_OK=1
    else
      CONFIG_OK=0
      CONFIG_ERR="$(tail -6 "$TMPDIR_H/ports.log" | tr '\n' ' ' | sed 's/  */ /g')"
    fi
  fi
fi

CFG_PUBLISHED=""
CFG_IMAGE=""
if [ -f "$CONFIG_PORTS_JSON" ]; then
  CFG_PUBLISHED="$(python3 - "$CONFIG_PORTS_JSON" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(0)
print("\n".join("%s=%d" % (r["service"], r["expected_published"]) for r in d.get("rows", [])))
PY
)"
fi

# ---------------------------------------------------------------------------
# Evaluate one service
# ---------------------------------------------------------------------------
# Verdict codes ordered by severity for the exit code mapping.
sev_of() {
  case "$1" in
    OK) echo 0 ;;
    NO_PUBLISHED_PORT|EXPECTED_PORT_MISSING|PORT_OWNED_BY_FOREIGN|WRONG_BIND|CONFIG_NO_PORTS|PORT_COLLISION) echo 1 ;;
    NOT_RUNNING|NO_CONTAINER|UNHEALTHY|MISSING_CONTAINER) echo 2 ;;
    ENDPOINT_DOWN) echo 3 ;;
    STATE_DRIFT) echo 4 ;;
    *) echo 9 ;;
  esac
}

ROWS=()
WORST=0
CRIT_FAIL=0
OPT_WARN=0

add_row() { # svc port container chealth published hostprobe verdict detail optional
  ROWS+=("$1|$2|$3|$4|$5|$6|$7|$8|$9")
  local s
  s="$(sev_of "$7")"
  if [ "$9" = "1" ]; then
    [ "$s" -ne 0 ] && OPT_WARN=1
  else
    [ "$s" -gt "$WORST" ] && WORST="$s"
    [ "$s" -ne 0 ] && CRIT_FAIL=1
  fi
}

evaluate_service() {
  local svc="$1" port="$2" target="$3" path="$4"
  local optional=0
  dana_is_optional "$svc" && optional=1

  local container="" chealth="none" cstate="missing" cimage="" published="" hostprobe="-" verdict="OK" detail=""

  if [ "$USE_COMPOSE" = "1" ]; then
    local line
    line="$(dana_compose_ps_field "$svc")"
    if [ -n "$line" ]; then
      container="$(echo "$line" | cut -d'|' -f2)"
      chealth="$(echo "$line" | cut -d'|' -f3)"
      cstate="$(echo "$line" | cut -d'|' -f4)"
      cimage="$(echo "$line" | cut -d'|' -f5)"
    fi
  fi

  # ---- live published ports from docker itself -----------------------------
  if [ -n "$container" ]; then
    published="$(dana_live_publishers "$container" | tr '\n' ',' | sed 's/,$//')"
  fi

  # ---- 1. container presence / liveness -----------------------------------
  if [ "$USE_COMPOSE" = "1" ]; then
    if [ -z "$container" ]; then
      verdict="NO_CONTAINER"
      detail="no container for service '$svc' in project $PROJECT (never started, or a different -p)"
      add_row "$svc" "$port" "-" "$chealth" "-" "-" "$verdict" "$detail" "$optional"
      return
    fi
    if [ "$cstate" != "running" ]; then
      verdict="NOT_RUNNING"
      detail="container state=$cstate ($container)"
      add_row "$svc" "$port" "$container" "$chealth" "${published:--}" "-" "$verdict" "$detail" "$optional"
      return
    fi
  fi

  # ---- 2. THE PRODUCTION FAILURE: healthy container, zero published ports --
  # This is the exact check that would have caught the Nov 2026 outage.
  if [ "$USE_COMPOSE" = "1" ] && [ -z "$published" ]; then
    verdict="NO_PUBLISHED_PORT"
    detail="container '$container' is ${chealth} but publishes NO host port; expected ${port}->${target}. compose.base.yml alone has no ports: — overlay missing from the deploy."
    add_row "$svc" "$port" "$container" "$chealth" "NONE" "-" "$verdict" "$detail" "$optional"
    return
  fi

  # ---- 3. expected host port actually bound to this container --------------
  if [ "$USE_COMPOSE" = "1" ]; then
    if ! dana_published_port_match "$container" "$port"; then
      verdict="EXPECTED_PORT_MISSING"
      detail="container publishes [${published}] but not ${port}; expected ${port}->${target}"
      add_row "$svc" "$port" "$container" "$chealth" "${published:--}" "-" "$verdict" "$detail" "$optional"
      return
    fi
    # Bind must stay loopback for anything sensitive (never 0.0.0.0).
    local badbind
    badbind="$(dana_live_publishers "$container" | awk -F: -v p="$port" '$NF==p && $1!="127.0.0.1" && $1!="::1" {print $1}')"
    if [ -n "$badbind" ]; then
      verdict="WRONG_BIND"
      detail="port ${port} bound to ${badbind} — must be 127.0.0.1 only"
      add_row "$svc" "$port" "$container" "$chealth" "${published:--}" "-" "$verdict" "$detail" "$optional"
      return
    fi

    # ---- 4. port must not be owned by some other container ---------------
    local owner
    owner="$(docker ps --filter "publish=${port}" --format '{{.Names}}' 2>/dev/null | head -1)"
    if [ -n "$owner" ] && [ "$owner" != "$container" ]; then
      verdict="PORT_OWNED_BY_FOREIGN"
      detail="host port ${port} is owned by '$owner', not '$container' (stale/duplicate stack)"
      add_row "$svc" "$port" "$container" "$chealth" "${published:--}" "-" "$verdict" "$detail" "$optional"
      return
    fi
  fi

  # ---- 5. host-side reachability ------------------------------------------
  if ! dana_port_listening "$port"; then
    verdict="ENDPOINT_DOWN"
    detail="nothing is listening on 127.0.0.1:${port} from the host"
    add_row "$svc" "$port" "${container:--}" "$chealth" "${published:--}" "refused" "$verdict" "$detail" "$optional"
    return
  fi

  # ---- 6. host-side HTTP probe --------------------------------------------
  if [ "$path" != "-" ]; then
    local body code
    body="$(dana_probe_body "$port" "$path" 6)"
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 6 "http://127.0.0.1:${port}${path}" 2>/dev/null)"
    case "$code" in
      200|204|301|302|307|401|403) hostprobe="$code" ;;
      000|"") hostprobe="refused" ;;
      *) hostprobe="$code" ;;
    esac
    if [ "$hostprobe" = "refused" ] || [ "$hostprobe" != "200" -a "$hostprobe" != "204" -a "$hostprobe" != "301" -a "$hostprobe" != "302" -a "$hostprobe" != "307" -a "$hostprobe" != "401" -a "$hostprobe" != "403" ]; then
      verdict="ENDPOINT_DOWN"
      detail="host probe http://127.0.0.1:${port}${path} -> ${hostprobe}"
      add_row "$svc" "$port" "${container:--}" "$chealth" "${published:--}" "$hostprobe" "$verdict" "$detail" "$optional"
      return
    fi
    detail="$(printf '%s' "$body" | head -c 90 | tr -d '\n')"
  else
    hostprobe="tcp-ok"
    detail="tcp accept only"
  fi

  # ---- 7. container health as a secondary signal (never primary) ----------
  if [ "$USE_COMPOSE" = "1" ] && [ "$chealth" != "healthy" ] && [ "$chealth" != "none" ] && [ -n "$chealth" ]; then
    verdict="UNHEALTHY"
    detail="host probe ok but container health=${chealth} (upstream dependency flapping?)"
    add_row "$svc" "$port" "$container" "$chealth" "${published:--}" "$hostprobe" "$verdict" "$detail" "$optional"
    return
  fi

  add_row "$svc" "$port" "${container:--}" "$chealth" "${published:--}" "$hostprobe" "OK" "$detail" "$optional"
}

for token in $SPEC; do
  svc="${token%%:*}"
  rest="${token#*:}"
  port="$(echo "$rest" | cut -d: -f1)"
  rest2="$(echo "$rest" | cut -d: -f2-)"
  target="$(echo "$rest2" | cut -d: -f1)"
  path="$(echo "$rest2" | cut -d: -f2- | cut -d: -f1)"
  [ -z "$path" ] && path="-"
  evaluate_service "$svc" "$port" "$target" "$path"
done

# ---------------------------------------------------------------------------
# Optional: compare live stack against the recorded last-known-good
# ---------------------------------------------------------------------------
STATE_NOTE=""
if [ "$STATE_CHECK" = "1" ]; then
  if ! dana_state_healthy; then
    add_row "last_good" "-" "-" "-" "-" "-" "STATE_DRIFT" "no healthy last_good.json at $DANA_STATE_FILE" "0"
    STATE_NOTE="no last-good state recorded"
  else
    LIVE_SHA="$(dana_state_field compose.config_sha256 "")"
    ARGS=(--project "$PROJECT")
    while IFS= read -r f; do [ -n "$f" ] && ARGS+=(-f "$f"); done < <(dana_profile_files "$PROFILE")
    [ -n "$ENV_FILE" ] && ARGS+=(--env-file "$ENV_FILE")
    NOW_SHA="$(python3 "$DANA_STATE_PY" config "${ARGS[@]}" 2>/dev/null \
      | python3 -c 'import json,sys,hashlib; print(hashlib.sha256(json.dumps(json.load(sys.stdin),sort_keys=True,separators=(",",":")).encode()).hexdigest())' 2>/dev/null)"
    if [ -n "$LIVE_SHA" ] && [ -n "$NOW_SHA" ] && [ "$LIVE_SHA" != "$NOW_SHA" ]; then
      add_row "last_good" "-" "-" "-" "-" "-" "STATE_DRIFT" "current config ${NOW_SHA:0:12} != last-good ${LIVE_SHA:0:12} — deploy not yet promoted" "0"
      STATE_NOTE="config differs from last-good"
    else
      STATE_NOTE="live config matches last-good (${LIVE_SHA:0:12})"
    fi
  fi
fi

# ---------------------------------------------------------------------------
# Render the verdict table
# ---------------------------------------------------------------------------
render() {
  printf '\n%sDana health — profile=%s project=%s%s\n' "$C_BOLD" "$PROFILE" "$PROJECT" "$C_OFF"
  if [ "$USE_COMPOSE" = "1" ]; then
    printf '%scompose: %s%s\n' "$C_DIM" "$(dana_profile_files "$PROFILE" | tr '\n' ' ')" "$C_OFF"
    [ -n "$ENV_FILE" ] && printf '%senv    : %s%s\n' "$C_DIM" "$ENV_FILE" "$C_OFF"
  else
    printf '%smode   : host-venv (no docker compose) — checking published host ports only%s\n' "$C_DIM" "$C_OFF"
  fi
  printf '\n'
  printf '%-13s %-6s %-23s %-9s %-24s %-9s %-25s %s\n' \
    "SERVICE" "PORT" "CONTAINER" "HEALTH" "PUBLISHED" "HOST" "VERDICT" "DETAIL"
  printf '%s\n' "---------------------------------------------------------------------------------------------------------------------------------------"
  local row svc port container chealth published hostprobe verdict detail optional color
  for row in "${ROWS[@]}"; do
    IFS='|' read -r svc port container chealth published hostprobe verdict detail optional <<<"$row"
    case "$(sev_of "$verdict")" in
      0) color="$C_GREEN" ;;
      *) if [ "$optional" = "1" ]; then color="$C_YELLOW"; else color="$C_RED"; fi ;;
    esac
    printf '%-13s %-6s %-23s %-9s %-24s %-9s %s%-25s%s %s\n' \
      "$svc" "$port" "$(printf '%s' "$container" | cut -c1-23)" \
      "$chealth" "$(printf '%s' "$published" | cut -c1-24)" "$hostprobe" \
      "$color" "$verdict" "$C_OFF" "$(printf '%s' "$detail" | cut -c1-150)"
  done
  printf '%s\n' "---------------------------------------------------------------------------------------------------------------------------------------"
}

if [ "$QUIET" != "1" ]; then
  render
fi

# ---------------------------------------------------------------------------
# Config-level warning (resolved config publishes nothing = deploy bug)
# ---------------------------------------------------------------------------
if [ "$USE_COMPOSE" = "1" ] && [ "$CONFIG_OK" = "0" ]; then
  err "resolved compose config FAILS the port contract: $CONFIG_ERR"
  CRIT_FAIL=1
  [ "$WORST" -lt 1 ] && WORST=1
fi

# ---------------------------------------------------------------------------
# Machine-readable output
# ---------------------------------------------------------------------------
if [ -n "$JSON_OUT" ]; then
  ROWS_FILE="$TMPDIR_H/rows.txt"
  : >"$ROWS_FILE"
  for row in "${ROWS[@]}"; do printf '%s\n' "$row" >>"$ROWS_FILE"; done
  ALL_HEALTHY=1; [ "$CRIT_FAIL" = "1" ] && ALL_HEALTHY=0
  python3 - "$ROWS_FILE" "$JSON_OUT" "$PROFILE" "$PROJECT" "$ALL_HEALTHY" "$WORST" "$STATE_NOTE" <<'PY'
import json, sys, datetime, os
rows_file, out, profile, project, all_healthy, worst, state_note = sys.argv[1:8]
rows = []
verdicts = {}
with open(rows_file) as fh:
    for line in fh:
        line = line.rstrip("\n")
        if not line:
            continue
        parts = line.split("|")
        if len(parts) < 9:
            continue
        svc, port, container, chealth, published, hostprobe, verdict, detail, optional = parts[:9]
        row = {
            "service": svc,
            "port": None if port in ("-", "") else int(port),
            "container": None if container in ("-", "") else container,
            "container_health": chealth,
            "published": None if published in ("-", "") else published,
            "host_probe": hostprobe,
            "verdict": verdict,
            "detail": detail,
            "optional": optional == "1",
        }
        rows.append(row)
        verdicts[svc] = verdict
payload = {
    "checked_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "profile": profile,
    "project": project,
    "all_healthy": all_healthy == "1",
    "worst_severity": int(worst),
    "state_note": state_note,
    "verdicts": verdicts,
    "rows": rows,
}
os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
tmp = out + ".tmp"
with open(tmp, "w") as fh:
    json.dump(payload, fh, indent=2, sort_keys=True)
    fh.write("\n")
os.replace(tmp, out)
PY
  [ "$QUIET" != "1" ] && printf '%sverdicts written to %s%s\n' "$C_DIM" "$JSON_OUT" "$C_OFF"
fi

# ---------------------------------------------------------------------------
# Final verdict
# ---------------------------------------------------------------------------
if [ "$CRIT_FAIL" = "0" ] && [ "$OPT_WARN" = "0" ]; then
  [ "$QUIET" != "1" ] && ok "ALL CRITICAL SERVICES HEALTHY (ports published + host probes OK)"
  exit 0
fi

if [ "$CRIT_FAIL" = "0" ] && [ "$OPT_WARN" = "1" ]; then
  [ "$QUIET" != "1" ] && warn "critical services healthy; optional services degraded (see WARN rows)"
  exit 0
fi

case "$WORST" in
  1) [ "$QUIET" != "1" ] && err "UNHEALTHY — deploy/layering bug: a port that must be published is not (see NO_PUBLISHED_PORT / EXPECTED_PORT_MISSING rows)" ;;
  2) [ "$QUIET" != "1" ] && err "UNHEALTHY — container down/unhealthy" ;;
  3) [ "$QUIET" != "1" ] && err "UNHEALTHY — endpoint not answering on its published host port" ;;
  4) [ "$QUIET" != "1" ] && err "DRIFT — live stack does not match recorded last-known-good" ;;
  *) [ "$QUIET" != "1" ] && err "UNHEALTHY" ;;
esac
[ "$QUIET" != "1" ] && printf '%sremedy: bash deploy/gpu/deploy.sh --profile %s   (or: bash deploy/gpu/rollback.sh --profile %s)%s\n' \
  "$C_DIM" "$PROFILE" "$PROFILE" "$C_OFF"
exit "$WORST"
