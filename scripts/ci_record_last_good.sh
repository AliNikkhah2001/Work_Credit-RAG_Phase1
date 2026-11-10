#!/usr/bin/env bash
# Sprint C #10 — record last-known-good prod SHA (host-persistent).
# Writes: $HOST_REPO/deploy/compose/.last_good_sha
set -euo pipefail

HOST_REPO="${DANA_HOST_REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
SHA="${1:-${GIT_COMMIT:-}}"
if [ -z "$SHA" ]; then
  SHA="$(git -C "$HOST_REPO" rev-parse HEAD 2>/dev/null || true)"
fi
if [ -z "$SHA" ]; then
  echo "ci_record_last_good: ERROR — no SHA (pass as \$1 or set GIT_COMMIT)" >&2
  exit 1
fi

DIR="$HOST_REPO/deploy/compose"
mkdir -p "$DIR"
TARGET="$DIR/.last_good_sha"
if [ -f "$TARGET" ]; then
  cp -f "$TARGET" "$DIR/.last_good_sha.prev"
  echo "ci_record_last_good: previous=$(cat "$DIR/.last_good_sha.prev")"
fi
printf '%s\n' "$SHA" >"$TARGET"
echo "ci_record_last_good: wrote $TARGET -> $SHA"
