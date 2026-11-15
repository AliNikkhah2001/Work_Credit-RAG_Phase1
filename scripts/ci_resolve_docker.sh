#!/usr/bin/env bash
# Resolve a working docker CLI for Jenkins agents.
#
# GPU pitfall: bind-mounting the host `/usr/bin/docker` into the container often
# yields `docker: command not found` because the host binary is dynamically
# linked (ENOENT on the dynamic linker). Prefer the static CLI at
# `/usr/local/bin/docker` from `deploy/jenkins/Dockerfile`.
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

_is_working_docker() {
  local bin="$1"
  [ -n "$bin" ] && [ -x "$bin" ] || return 1
  # Host glibc-mismatched binaries fail with "not found" even when -x is true.
  "$bin" version >/dev/null 2>&1
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
  arch="$(uname -m)"
  case "$arch" in
    x86_64|amd64) arch=x86_64 ;;
    aarch64|arm64) arch=aarch64 ;;
  esac
  url="https://download.docker.com/linux/static/stable/${arch}/docker-28.3.3.tgz"
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

for plug in \
  /usr/local/lib/docker/cli-plugins \
  /usr/libexec/docker/cli-plugins \
  /usr/lib/docker/cli-plugins
 do
  if [ -e "$plug/docker-compose" ]; then
    export DOCKER_CONFIG="${DOCKER_CONFIG:-${ROOT}/.ci-docker-config}"
    mkdir -p "$DOCKER_CONFIG"
    # cli-plugins discovery uses ~/.docker/cli-plugins or /usr/local/lib/...
    break
  fi
done

echo "ci_resolve_docker: DOCKER_BIN=$DOCKER_BIN"
"$DOCKER_BIN" version 2>&1 | head -8 || true

if [ "$_print" = "1" ]; then
  printf 'export DOCKER_BIN=%q\n' "$DOCKER_BIN"
  printf 'export PATH=%q\n' "$PATH"
  exit 0
fi
