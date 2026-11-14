#!/usr/bin/env bash
# docker_build_offline.sh — build a component image on a host where Docker Hub
# is unreachable (ISP DNS sinkholing) but every base image is already cached.
#
# Why this exists
# ---------------
# Every component Dockerfile starts with
#     # syntax=docker/dockerfile:1
# That directive makes BuildKit fetch the `docker/dockerfile:1` frontend image
# from Docker Hub *before* it even parses the file. When Hub is blocked the
# build dies with a TLS/EOF error that says nothing about the real cause.
# Nothing else in those Dockerfiles needs the forward frontend: plain classic
# Dockerfile syntax plus `RUN --mount=type=cache,...` is handled by the built-in
# frontend that ships with BuildKit.
#
# So: if Hub is reachable, build the Dockerfile untouched (this is the correct
# path on the GPU server). If Hub is blocked, copy the Dockerfile to a temp file,
# drop ONLY that directive line, and build that copy while keeping the ORIGINAL
# build context. The submodule Dockerfiles are never modified.
#
# Base images are NOT download-able offline. Every FROM image is resolved and
# checked with `docker image inspect` first, so a missing base fails with an
# actionable message instead of an opaque BuildKit pull error.
#
# Usage:
#   bash scripts/docker_build_offline.sh \
#     --image rag-guardrails:local \
#     --context components/guardrails \
#     --dockerfile components/guardrails/Dockerfile
#
# Flags:
#   --image <name:tag>        Image ref to build (required)
#   --context <dir>           Build context (required; may be relative to CWD)
#   --dockerfile <path>       Dockerfile path (default: <context>/Dockerfile)
#   --build-arg K=V           Pass a build arg (repeatable, matches compose args)
#   --no-cache                Build without the layer cache
#   --dry-run                 Resolve + check everything, print the command, build nothing
#   --self-test               Exercise detection/strip/parse logic offline, build nothing
#   -h, --help                This text
#
# Environment:
#   HUB_PROBE_URL      override probe URL (default https://registry-1.docker.io/v2/)
#   HUB_PROBE_TIMEOUT  probe timeout seconds (default 5)
#
# Exit codes: 0 ok · 1 usage/build error · 2 missing base image · 3 probe/parse error
set -euo pipefail

PROG="$(basename "$0")"

IMAGE=""
CONTEXT=""
DOCKERFILE=""
NO_CACHE=0
DRY_RUN=0
SELF_TEST=0

HUB_PROBE_URL="${HUB_PROBE_URL:-https://registry-1.docker.io/v2/}"
HUB_PROBE_TIMEOUT="${HUB_PROBE_TIMEOUT:-5}"

BUILD_ARGS=()
ARG_DEFAULTS=()

log()  { printf '[%s] %s\n' "$PROG" "$*"; }
warn() { printf '[%s] WARN: %s\n' "$PROG" "$*" >&2; }
err()  { printf '[%s] ERROR: %s\n' "$PROG" "$*" >&2; }

usage() {
  sed -n '2,/^# Exit codes/p' "$0" | sed -E 's/^# ?//'
}

# ---------------------------------------------------------------------------
# Hub reachability
# ---------------------------------------------------------------------------
# 200/401/403 all mean the registry answered us. Anything else (000 from a dead
# TLS handshake, a timeout, a DNS result pointing at a sinkhole) means blocked.
hub_reachable() {
  local code
  if ! command -v curl >/dev/null 2>&1; then
    warn "curl not found; assuming Docker Hub is NOT reachable"
    return 1
  fi
  code="$(curl -s -o /dev/null -w '%{http_code}' \
            --connect-timeout "$HUB_PROBE_TIMEOUT" \
            --max-time "$HUB_PROBE_TIMEOUT" \
            "$HUB_PROBE_URL" 2>/dev/null || true)"
  case "$code" in
    200|401|403) return 0 ;;
    *)           return 1 ;;
  esac
}

# ---------------------------------------------------------------------------
# Dockerfile parsing
# ---------------------------------------------------------------------------

# Print the Dockerfile without its `# syntax=...` directive line. Every other
# byte (comments, blank lines, ARGs, stages) is preserved.
strip_syntax_directive() {
  local df="$1"
  grep -vE '^[[:space:]]*#[[:space:]]*syntax[[:space:]]*=' "$df" || true
}

_apply_var() {
  # _apply_var <name> <value> <string>
  local name="$1" value="$2" str="$3"
  str="${str//"\${$name}"/$value}"
  str="${str//"\$$name"/$value}"
  printf '%s' "$str"
}

# Resolve ${VAR} / $VAR inside a FROM image reference against --build-arg
# values first (they win) and then in-file ARG defaults.
_resolve_image_vars() {
  local img="$1" kv name val
  for kv in ${BUILD_ARGS[@]+"${BUILD_ARGS[@]}"}; do
    name="${kv%%=*}"
    val="${kv#*=}"
    img="$(_apply_var "$name" "$val" "$img")"
  done
  for kv in ${ARG_DEFAULTS[@]+"${ARG_DEFAULTS[@]}"}; do
    name="${kv%%=*}"
    val="${kv#*=}"
    img="$(_apply_var "$name" "$val" "$img")"
  done
  printf '%s' "$img"
}

# Emit every base image that actually needs to exist locally.
# Skips: `scratch`, stage aliases (`FROM builder AS final`), and unresolvable refs.
parse_base_images() {
  local df="$1"
  local line trimmed from_body ref stage_alias lower seen_from=0 aliases=" " rest

  while IFS= read -r line || [ -n "$line" ]; do
    trimmed="$(printf '%s' "$line" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')"

    if ! printf '%s' "$trimmed" | grep -qiE '^FROM[[:space:]]'; then
      # ARG defaults declared before the first FROM may feed later FROM refs.
      if [ "$seen_from" -eq 0 ] && printf '%s' "$trimmed" | grep -qiE '^ARG[[:space:]]'; then
        rest="$(printf '%s' "$trimmed" | sed -E 's/^[Aa][Rr][Gg][[:space:]]+//')"
        case "$rest" in
          *=*) ARG_DEFAULTS+=("$rest") ;;
        esac
      fi
      continue
    fi

    seen_from=1
    from_body="$(printf '%s' "$trimmed" \
                  | sed -E 's/^[Ff][Rr][Oo][Mm][[:space:]]+//' \
                  | sed -E 's/[[:space:]]+#.*$//')"

    ref=""
    stage_alias=""
    # shellcheck disable=SC2086 # deliberate word splitting on whitespace
    set -- $from_body
    while [ $# -gt 0 ]; do
      case "$1" in
        --platform=*) shift ;;
        *[Aa][Ss])    shift; stage_alias="${1:-}"; [ $# -gt 0 ] && shift ;;
        *)            [ -z "$ref" ] && ref="$1"; shift ;;
      esac
    done

    [ -z "$ref" ] && continue

    ref="$(_resolve_image_vars "$ref")"
    lower="$(printf '%s' "$ref" | tr '[:upper:]' '[:lower:]')"

    if [ -n "$stage_alias" ]; then
      aliases="$aliases$stage_alias "
    fi

    # A FROM pointing at an earlier stage alias is not a registry image.
    case " $aliases " in
      *" $lower "*) continue ;;
    esac
    [ "$lower" = "scratch" ] && continue

    case "$ref" in
      *'$'*)
        warn "cannot resolve FROM reference '$ref' (no ARG default or --build-arg); skipping base-image check"
        continue
        ;;
    esac

    printf '%s\n' "$ref"
  done < "$df"
}

# Exit 2 with a message naming exactly which base images are unavailable.
check_base_images() {
  local df="$1"
  local img missing=""

  log "resolving base images from $df"
  while IFS= read -r img; do
    [ -z "$img" ] && continue
    if docker image inspect "$img" >/dev/null 2>&1; then
      printf '  present  %s\n' "$img"
    else
      printf '  MISSING  %s\n' "$img"
      missing="$missing $img"
    fi
  done < <(parse_base_images "$df")

  if [ -n "$missing" ]; then
    err "base image(s) not available locally:$missing"
    cat >&2 <<EOF
        Docker Hub is unreachable on this host, so these cannot be pulled.
        Options:
          * run this build on a Hub-reachable host (the GPU server) and ship the
            image, or
          * obtain the image out of band, e.g. 'docker load -i <tarball>' from a
            machine that can pull it, then re-run this script.
        Nothing was built.
EOF
    return 2
  fi
  return 0
}

# ---------------------------------------------------------------------------
# Self-test: detection + strip + parse, no builds, no network dependency
# ---------------------------------------------------------------------------
run_self_test() {
  local failures=0 tmp dir
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"; trap - RETURN' RETURN

  _t_ok()   { printf '  PASS  %s\n' "$1"; }
  _t_fail() { printf '  FAIL  %s\n' "$1"; failures=$((failures + 1)); }

  # --- detection ---------------------------------------------------------
  if hub_reachable; then
    _t_ok "detection: Docker Hub reachable (normal path would be used)"
  else
    _t_ok "detection: Docker Hub blocked (offline path would be used)"
  fi

  # --- strip -------------------------------------------------------------
  printf '# syntax=docker/dockerfile:1\nFROM python:3.11-slim\nRUN echo hi\n' > "$tmp/a.Dockerfile"
  strip_syntax_directive "$tmp/a.Dockerfile" > "$tmp/a.stripped"
  if grep -qE 'syntax=' "$tmp/a.stripped"; then
    _t_fail "strip: directive still present"
  elif [ "$(wc -l < "$tmp/a.stripped" | tr -d ' ')" -ne 2 ]; then
    _t_fail "strip: expected 2 lines, got $(wc -l < "$tmp/a.stripped" | tr -d ' ')"
  elif ! grep -q 'FROM python:3.11-slim' "$tmp/a.stripped"; then
    _t_fail "strip: FROM line lost"
  else
    _t_ok "strip: '# syntax=' removed, body preserved"
  fi

  printf '# syntax = docker/dockerfile:1\nFROM node:22-alpine\n' > "$tmp/b.Dockerfile"
  strip_syntax_directive "$tmp/b.Dockerfile" > "$tmp/b.stripped"
  if grep -qE 'syntax' "$tmp/b.stripped"; then
    _t_fail "strip: spaced '# syntax =' form not removed"
  else
    _t_ok "strip: spaced '# syntax = ...' form removed"
  fi

  printf '# see docs about syntax=docker/dockerfile:1 before editing\nFROM python:3.11-slim\n' > "$tmp/c.Dockerfile"
  strip_syntax_directive "$tmp/c.Dockerfile" > "$tmp/c.stripped"
  if grep -q 'see docs about' "$tmp/c.stripped"; then
    _t_ok "strip: prose comment that merely mentions syntax= is kept"
  else
    _t_fail "strip: prose comment removed by mistake"
  fi

  printf 'FROM python:3.11-slim\nRUN true\n' > "$tmp/d.Dockerfile"
  strip_syntax_directive "$tmp/d.Dockerfile" > "$tmp/d.stripped"
  if cmp -s "$tmp/d.Dockerfile" "$tmp/d.stripped"; then
    _t_ok "strip: idempotent when no directive is present"
  else
    _t_fail "strip: modified a Dockerfile that had no directive"
  fi

  # --- base-image parse --------------------------------------------------
  cat > "$tmp/e.Dockerfile" <<'DOCKERFILE'
# syntax=docker/dockerfile:1
ARG TORCH_CHANNEL=cpu
ARG BASE=python:3.11-slim

FROM ${BASE} AS builder
RUN echo "${TORCH_CHANNEL}"

FROM --platform=linux/amd64 nginx:alpine AS web
RUN true

FROM builder
RUN true
DOCKERFILE
  BUILD_ARGS=()
  ARG_DEFAULTS=()
  dir="$(parse_base_images "$tmp/e.Dockerfile" | tr '\n' ' ')"
  if [ "$dir" = "python:3.11-slim nginx:alpine " ]; then
    _t_ok "parse: ARG-substituted + platform flag handled + stage alias skipped"
  else
    _t_fail "parse: unexpected base list [$dir]"
  fi

  BUILD_ARGS=("BASE=docker.io/library/python:3.9-slim")
  ARG_DEFAULTS=()
  # No `| head -1` here: under `set -o pipefail` the SIGPIPE would abort the test.
  dir="$(parse_base_images "$tmp/e.Dockerfile")"
  dir="${dir%%$'\n'*}"
  if [ "$dir" = "docker.io/library/python:3.9-slim" ]; then
    _t_ok "parse: --build-arg overrides in-file ARG default"
  else
    _t_fail "parse: --build-arg override ignored (got [$dir])"
  fi
  BUILD_ARGS=()
  ARG_DEFAULTS=()

  # --- unresolved ref is reported, not silently checked ------------------
  printf 'FROM ${UNDECLARED}\n' > "$tmp/f.Dockerfile"
  if parse_base_images "$tmp/f.Dockerfile" 2>/dev/null | grep -q .; then
    _t_fail "parse: unresolved FROM ref emitted as a base image"
  else
    _t_ok "parse: unresolved FROM ref skipped with a warning"
  fi

  echo
  if [ "$failures" -eq 0 ]; then
    log "self-test OK"
    return 0
  fi
  err "self-test FAILED ($failures case(s))"
  return 1
}

# ---------------------------------------------------------------------------
# Arg parsing
# ---------------------------------------------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    --image)       IMAGE="${2:-}"; shift 2 ;;
    --image=*)     IMAGE="${1#*=}"; shift ;;
    --context)     CONTEXT="${2:-}"; shift 2 ;;
    --context=*)   CONTEXT="${1#*=}"; shift ;;
    --dockerfile)  DOCKERFILE="${2:-}"; shift 2 ;;
    --dockerfile=*) DOCKERFILE="${1#*=}"; shift ;;
    --build-arg)   BUILD_ARGS+=("${2:-}"); shift 2 ;;
    --build-arg=*) BUILD_ARGS+=("${1#*=}"); shift ;;
    --no-cache)    NO_CACHE=1; shift ;;
    --dry-run)     DRY_RUN=1; shift ;;
    --self-test)   SELF_TEST=1; shift ;;
    -h|--help)     usage; exit 0 ;;
    *) err "unknown argument: $1"; usage >&2; exit 1 ;;
  esac
done

if [ "$SELF_TEST" -eq 1 ]; then
  echo "== docker_build_offline.sh self-test =="
  run_self_test
  exit $?
fi

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
[ -n "$IMAGE" ]   || { err "--image is required"; usage >&2; exit 1; }
[ -n "$CONTEXT" ] || { err "--context is required"; usage >&2; exit 1; }
[ -d "$CONTEXT" ] || { err "build context is not a directory: $CONTEXT"; exit 1; }

CONTEXT="$(cd "$CONTEXT" && pwd)"

if [ -z "$DOCKERFILE" ]; then
  DOCKERFILE="$CONTEXT/Dockerfile"
fi
[ -f "$DOCKERFILE" ] || { err "Dockerfile not found: $DOCKERFILE"; exit 1; }
DOCKERFILE="$(cd "$(dirname "$DOCKERFILE")" && pwd)/$(basename "$DOCKERFILE")"

log "image:      $IMAGE"
log "context:    $CONTEXT"
log "dockerfile: $DOCKERFILE"
[ "${#BUILD_ARGS[@]}" -gt 0 ] && log "build args: ${BUILD_ARGS[*]}"

# Base images must exist locally regardless of mode: the normal path would pull
# them if it could, but offline it must fail here, not inside BuildKit.
check_base_images "$DOCKERFILE" || exit 2

# ---------------------------------------------------------------------------
# Decide the path
# ---------------------------------------------------------------------------
TMPDIR_BUILD=""
cleanup() { [ -n "$TMPDIR_BUILD" ] && rm -rf "$TMPDIR_BUILD"; }
trap cleanup EXIT

BUILD_DOCKERFILE="$DOCKERFILE"
STRIPPED=0

if hub_reachable; then
  log "Docker Hub is reachable -> building with the original Dockerfile (syntax directive preserved)"
else
  STRIPPED=1
  TMPDIR_BUILD="$(mktemp -d)"
  BUILD_DOCKERFILE="$TMPDIR_BUILD/Dockerfile.offline"
  strip_syntax_directive "$DOCKERFILE" > "$BUILD_DOCKERFILE"
  if grep -qE '^[[:space:]]*#[[:space:]]*syntax[[:space:]]*=' "$BUILD_DOCKERFILE"; then
    err "failed to strip the '# syntax=' directive"; exit 3
  fi
  warn "Docker Hub is UNREACHABLE: stripped '# syntax=docker/dockerfile:1' for this build only"
  warn "  /!\\ this is an offline workaround. On a Hub-reachable host (the GPU server)"
  warn "  /!\\ the normal path is preferred: the original Dockerfile is used untouched."
  warn "  generated: $BUILD_DOCKERFILE (source Dockerfile not modified)"
fi

cmd=(docker build -f "$BUILD_DOCKERFILE" -t "$IMAGE")
for kv in ${BUILD_ARGS[@]+"${BUILD_ARGS[@]}"}; do
  cmd+=(--build-arg "$kv")
done
[ "$NO_CACHE" -eq 1 ] && cmd+=(--no-cache)
cmd+=("$CONTEXT")

log "command: DOCKER_BUILDKIT=1 ${cmd[*]}"

if [ "$DRY_RUN" -eq 1 ]; then
  log "dry-run: not building"
  exit 0
fi

DOCKER_BUILDKIT=1 "${cmd[@]}"

log "built $IMAGE (syntax_stripped=$STRIPPED)"
