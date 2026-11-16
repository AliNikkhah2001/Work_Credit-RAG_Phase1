#!/usr/bin/env bash
# Resolve a working docker CLI (+ compose plugin) for Jenkins agents.
#
# GPU pitfall: bind-mounting the host `/usr/bin/docker` into the container often
# yields `docker: command not found` because the host binary is dynamically
# linked (ENOENT on the dynamic linker). Prefer the static CLI at
# `/usr/local/bin/docker` from `deploy/jenkins/Dockerfile.docker-cli`.
#
# Second pitfall: a bare static `docker` without the compose *plugin* makes
# `docker compose -f …` fail with: unknown shorthand flag: 'f' in -f
# (the CLI treats `compose` as an unknown top-level command).
#
# Usage (bash):
#   # shellcheck disable=SC1091
#   source scripts/ci_resolve_docker.sh
#   "$DOCKER_BIN" compose ...
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
_print=0
_allow_fetch="${CI_DOCKER_CLI_FETCH:-1}"
[ "${1:-}" = "--print-exports" ] && _print=1

_COMPOSE_VER="${CI_DOCKER_COMPOSE_VER:-v2.39.2}"
_DOCKER_STATIC_VER="${CI_DOCKER_STATIC_VER:-28.3.3}"

_is_working_docker() {
  local bin="$1"
  [ -n "$bin" ] && [ -x "$bin" ] || return 1
  # Host glibc-mismatched binaries fail with "not found" even when -x is true.
  "$bin" version >/dev/null 2>&1 || "$bin" --version >/dev/null 2>&1
}

_arch_pair() {
  local arch
  arch="$(uname -m)"
  case "$arch" in
    x86_64|amd64) echo "x86_64 x86_64" ;;
    aarch64|arm64) echo "aarch64 aarch64" ;;
    *) echo "$arch $arch" ;;
  esac
}

_ensure_compose_plugin() {
  # Prefer an already-working plugin visible to DOCKER_BIN.
  if "$DOCKER_BIN" compose version >/dev/null 2>&1; then
    return 0
  fi

  local darch carch plug_dir plug
  read -r darch carch < <(_arch_pair)
  plug_dir="${ROOT}/.ci-bin/cli-plugins"
  plug="${plug_dir}/docker-compose"
  mkdir -p "$plug_dir"

  if [ ! -x "$plug" ] && [ "$_allow_fetch" = "1" ]; then
    echo "ci_resolve_docker: fetching compose plugin ${_COMPOSE_VER} into .ci-bin/cli-plugins/" >&2
    if curl -fsSL --connect-timeout 30 --max-time 180 \
        ${HTTP_PROXY:+--proxy "$HTTP_PROXY"} \
        "https://github.com/docker/compose/releases/download/${_COMPOSE_VER}/docker-compose-linux-${carch}" \
        -o "$plug"
    then
      chmod +x "$plug"
    else
      echo "ci_resolve_docker: compose plugin download failed" >&2
      rm -f "$plug"
      return 1
    fi
  fi

  [ -x "$plug" ] || return 1

  # Wire DOCKER_CONFIG so the CLI discovers our plugin (not only system paths).
  export DOCKER_CONFIG="${DOCKER_CONFIG:-${ROOT}/.ci-docker-config}"
  mkdir -p "$DOCKER_CONFIG/cli-plugins"
  ln -sfn "$plug" "$DOCKER_CONFIG/cli-plugins/docker-compose"

  # Also expose under .ci-bin for tools that scan fixed paths.
  mkdir -p /usr/local/lib/docker/cli-plugins 2>/dev/null || true
  if [ -w /usr/local/lib/docker/cli-plugins ] 2>/dev/null; then
    ln -sfn "$plug" /usr/local/lib/docker/cli-plugins/docker-compose 2>/dev/null || true
  fi

  if "$DOCKER_BIN" compose version >/dev/null 2>&1; then
    return 0
  fi
  echo "ci_resolve_docker: compose plugin present but not discovered by CLI" >&2
  return 1
}

_candidates=(
  "${DOCKER_BIN:-}"
  "$(command -v docker 2>/dev/null || true)"
  /usr/local/bin/docker
  /usr/bin/docker
  /bin/docker
  "${ROOT}/.ci-bin/docker"
)

DOCKER_BIN=""
for c in "${_candidates[@]}"; do
  [ -n "$c" ] || continue
  if _is_working_docker "$c"; then
    DOCKER_BIN="$c"
    break
  fi
done

# Last resort: fetch the same static CLI the Jenkins Dockerfile vendors.
if [ -z "$DOCKER_BIN" ] && [ "$_allow_fetch" = "1" ]; then
  echo "ci_resolve_docker: no working docker CLI — fetching static binary into .ci-bin/" >&2
  mkdir -p "${ROOT}/.ci-bin"
  read -r darch _carch < <(_arch_pair)
  url="https://download.docker.com/linux/static/stable/${darch}/docker-${_DOCKER_STATIC_VER}.tgz"
  tmp="$(mktemp -d)"
  if curl -fsSL --connect-timeout 30 --max-time 180 \
      ${HTTP_PROXY:+--proxy "$HTTP_PROXY"} \
      "$url" -o "$tmp/docker.tgz"
  then
    tar -xz -C "$tmp" -f "$tmp/docker.tgz"
    if [ -x "$tmp/docker/docker" ]; then
      cp -f "$tmp/docker/docker" "${ROOT}/.ci-bin/docker"
      chmod +x "${ROOT}/.ci-bin/docker"
      if _is_working_docker "${ROOT}/.ci-bin/docker"; then
        DOCKER_BIN="${ROOT}/.ci-bin/docker"
      fi
    fi
  else
    echo "ci_resolve_docker: static CLI download failed" >&2
  fi
  rm -rf "$tmp"
fi

if [ -z "$DOCKER_BIN" ]; then
  echo "ci_resolve_docker: ERROR no working docker CLI" >&2
  echo "ci_resolve_docker: PATH=$PATH" >&2
  ls -la /usr/local/bin/docker /usr/bin/docker /bin/docker "${ROOT}/.ci-bin/docker" 2>&1 || true
  file /usr/local/bin/docker /usr/bin/docker 2>&1 || true
  if [ "$_print" = "1" ]; then
    exit 1
  fi
  return 1 2>/dev/null || exit 1
fi

export DOCKER_BIN
export PATH="$(dirname "$DOCKER_BIN"):/usr/local/bin:/usr/bin:/bin:${PATH:-}"
# Ensure `docker` on PATH resolves to the working binary (not a broken host mount).
if [ "$(command -v docker 2>/dev/null || true)" != "$DOCKER_BIN" ]; then
  mkdir -p "${ROOT}/.ci-bin"
  ln -sfn "$DOCKER_BIN" "${ROOT}/.ci-bin/docker"
  export PATH="${ROOT}/.ci-bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
fi

# Prefer system plugin dirs when present; otherwise fetch into .ci-bin.
_compose_ok=0
for plug in \
  /usr/local/lib/docker/cli-plugins \
  /usr/libexec/docker/cli-plugins \
  /usr/lib/docker/cli-plugins
do
  if [ -e "$plug/docker-compose" ]; then
    export DOCKER_CONFIG="${DOCKER_CONFIG:-${ROOT}/.ci-docker-config}"
    mkdir -p "$DOCKER_CONFIG/cli-plugins"
    ln -sfn "$plug/docker-compose" "$DOCKER_CONFIG/cli-plugins/docker-compose" 2>/dev/null || true
    if "$DOCKER_BIN" compose version >/dev/null 2>&1; then
      _compose_ok=1
      break
    fi
  fi
done

if [ "$_compose_ok" != "1" ]; then
  _ensure_compose_plugin || echo "ci_resolve_docker: WARN compose plugin unavailable — 'docker compose -f' may fail" >&2
fi

echo "ci_resolve_docker: DOCKER_BIN=$DOCKER_BIN"
"$DOCKER_BIN" version 2>&1 | head -8 || "$DOCKER_BIN" --version 2>&1 || true
"$DOCKER_BIN" compose version 2>&1 | head -3 || true

if [ "$_print" = "1" ]; then
  printf 'export DOCKER_BIN=%q\n' "$DOCKER_BIN"
  printf 'export PATH=%q\n' "$PATH"
  [ -n "${DOCKER_CONFIG:-}" ] && printf 'export DOCKER_CONFIG=%q\n' "$DOCKER_CONFIG"
  exit 0
fi
