#!/bin/bash
# Git commit-msg hook: tag every commit with the machine it originated from.
#
# Install (on EACH machine — laptop and GPU server):
#   cp scripts/commit-machine-hook.sh .git/hooks/commit-msg
#   chmod +x .git/hooks/commit-msg
#
# Behavior:
#   - Appends a machine-origin trailer to every commit message body:
#       Machine-origin: laptop | gpu-server
#   - Detects machine via DANA_HOST env (set on GPU server) or hostname.
#   - Never duplicates: if trailer already present, leaves message unchanged.
#
# This lets Jenkins / you see at a glance whether a commit came from the dev
# laptop or the production GPU server, and guarantees [ci prod] commits on main
# came from the intended promotion path.

set -euo pipefail

MSG_FILE="${1:-}"
if [[ -z "$MSG_FILE" || ! -f "$MSG_FILE" ]]; then
  exit 0
fi

# Determine machine origin.
# GPU server sets DANA_HOST=gpu in its Jenkins compose env; laptop leaves it unset.
DANA_HOST="${DANA_HOST:-}"
if [[ -n "$DANA_HOST" && "$DANA_HOST" == "gpu" ]]; then
  ORIGIN="gpu-server"
else
  # Fallback: heuristic on hostname.
  H="$(hostname -s 2>/dev/null || hostname || echo unknown)"
  case "$H" in
    *gpu*|*h200*|*ai-gpu*|*splunk*) ORIGIN="gpu-server" ;;
    *) ORIGIN="laptop" ;;
  esac
fi

TRAILER="Machine-origin: ${ORIGIN}"

# If already present, do nothing (idempotent across rebases/amends).
if grep -qiE "^Machine-origin:" "$MSG_FILE"; then
  exit 0
fi

# Append trailer after the body (before any existing git-cut/conflict markers).
{
  echo ""
  echo "$TRAILER"
} >>"$MSG_FILE"
