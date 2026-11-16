#!/usr/bin/env bash
# Install a working *static* Docker CLI into a running Jenkins controller.
#
# Problem this solves
# -------------------
# dana-jenkins-prod on the H200 had no /usr/local/bin/docker, and the host
# bind-mount of /usr/bin/docker failed at exec time (dynamic linker ENOENT →
# bash prints `docker: command not found`). CI then cannot `docker compose build`.
#
# Usage (on the GPU host):
#   bash scripts/bootstrap_jenkins_docker_cli.sh
#   bash scripts/bootstrap_jenkins_docker_cli.sh --container dana-jenkins-prod --commit
#
# Options:
#   --container NAME   default: dana-jenkins-prod (fallback dana-jenkins)
#   --commit           docker commit + retag dana-jenkins:production / :lts
#   --proxy URL        default: $HTTPS_PROXY / $HTTP_PROXY / http://192.168.203.2:3128
#   --dry-run          print actions only
set -euo pipefail

CONTAINER=""
DO_COMMIT=0
DRY=0
PROXY="${HTTPS_PROXY:-${HTTP_PROXY:-http://192.168.203.2:3128}}"
DOCKER_STATIC_VER=28.3.3
COMPOSE_VER=v2.39.2

while [ $# -gt 0 ]; do
  case "$1" in
    --container) CONTAINER="${2:-}"; shift 2 ;;
    --commit) DO_COMMIT=1; shift ;;
    --proxy) PROXY="${2:-}"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) sed -n '1,30p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$CONTAINER" ]; then
  if docker ps --format '{{.Names}}' | grep -qx 'dana-jenkins-prod'; then
    CONTAINER=dana-jenkins-prod
  elif docker ps --format '{{.Names}}' | grep -qx 'dana-jenkins'; then
    CONTAINER=dana-jenkins
  else
    echo "bootstrap_jenkins_docker_cli: no dana-jenkins[-prod] container running" >&2
    exit 1
  fi
fi

echo "bootstrap_jenkins_docker_cli: container=$CONTAINER proxy=${PROXY:-none}"

_run() {
  if [ "$DRY" = "1" ]; then
    echo "DRY: $*"
  else
    "$@"
  fi
}

# Already healthy?
if docker exec "$CONTAINER" /usr/local/bin/docker version >/dev/null 2>&1; then
  echo "bootstrap_jenkins_docker_cli: /usr/local/bin/docker already works — nothing to do"
  docker exec "$CONTAINER" /usr/local/bin/docker version | head -8
  exit 0
fi

arch="$(docker exec "$CONTAINER" uname -m)"
case "$arch" in
  x86_64|amd64) darch=x86_64; carch=x86_64 ;;
  aarch64|arm64) darch=aarch64; carch=aarch64 ;;
  *) echo "unsupported arch in container: $arch" >&2; exit 1 ;;
esac

echo "bootstrap_jenkins_docker_cli: installing static docker ${DOCKER_STATIC_VER} (${darch})"

_proxy_args=()
[ -n "$PROXY" ] && _proxy_args=(--proxy "$PROXY")

# Download on the host (has working curl/docker), then docker cp in.
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

curl -fsSL "${_proxy_args[@]}" \
  "https://download.docker.com/linux/static/stable/${darch}/docker-${DOCKER_STATIC_VER}.tgz" \
  -o "$tmp/docker.tgz"
tar -xz -C "$tmp" -f "$tmp/docker.tgz"
test -x "$tmp/docker/docker"

curl -fsSL "${_proxy_args[@]}" \
  "https://github.com/docker/compose/releases/download/${COMPOSE_VER}/docker-compose-linux-${carch}" \
  -o "$tmp/docker-compose"
chmod +x "$tmp/docker/docker" "$tmp/docker-compose"

_run docker cp "$tmp/docker/docker" "$CONTAINER:/usr/local/bin/docker"
_run docker exec "$CONTAINER" mkdir -p /usr/local/lib/docker/cli-plugins
_run docker cp "$tmp/docker-compose" "$CONTAINER:/usr/local/lib/docker/cli-plugins/docker-compose"
_run docker exec "$CONTAINER" chmod +x /usr/local/bin/docker /usr/local/lib/docker/cli-plugins/docker-compose

echo "bootstrap_jenkins_docker_cli: verifying inside container"
_run docker exec "$CONTAINER" /usr/local/bin/docker version

if [ "$DO_COMMIT" = "1" ]; then
  echo "bootstrap_jenkins_docker_cli: committing image → dana-jenkins:production (+ :lts alias)"
  _run docker commit "$CONTAINER" dana-jenkins:production
  _run docker tag dana-jenkins:production dana-jenkins:lts
  echo "bootstrap_jenkins_docker_cli: recreate recommended so mounts match h200.yml (no host docker bind):"
  echo "  docker compose -f deploy/jenkins/docker-compose.yml \\"
  echo "    -f deploy/jenkins/docker-compose.gpu.yml \\"
  echo "    -f deploy/jenkins/docker-compose.h200.yml up -d"
fi

echo "bootstrap_jenkins_docker_cli: done"
