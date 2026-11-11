#!/usr/bin/env bash
# Bundle / restore Dana compose images so laptop↔server skips PyPI re-downloads.
#
# Usage:
#   bash scripts/ci_image_bundle.sh save  [out.tgz]   # default: /tmp/dana-rag-images.tgz
#   bash scripts/ci_image_bundle.sh load  [in.tgz]
#   bash scripts/ci_image_bundle.sh list
#
# Typical laptop → GPU server:
#   bash scripts/ci_image_bundle.sh save /tmp/dana-rag-images.tgz
#   scp -P <ssh_port> /tmp/dana-rag-images.tgz root@<host>:/tmp/
#   ssh … 'bash -s' < scripts/ci_image_bundle.sh   # or run load on server
#   # on server:
#   bash scripts/ci_image_bundle.sh load /tmp/dana-rag-images.tgz
set -euo pipefail

CMD="${1:-list}"
ARCHIVE="${2:-/tmp/dana-rag-images.tgz}"

IMAGES=(
  rag-kb:local
  rag-guardrails:local
  rag-orchestrator:local
  rag-tracing:local
)

existing_images() {
  local out=()
  local img
  for img in "${IMAGES[@]}"; do
    if docker image inspect "$img" >/dev/null 2>&1; then
      out+=("$img")
    else
      echo "skip missing: $img" >&2
    fi
  done
  printf '%s\n' "${out[@]}"
}

case "$CMD" in
  list)
    for img in "${IMAGES[@]}"; do
      if docker image inspect "$img" >/dev/null 2>&1; then
        docker image ls --format '{{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.Size}}\t{{.CreatedSince}}' "$img"
      else
        echo "MISSING  $img"
      fi
    done
    ;;
  save)
    mapfile -t HAVE < <(existing_images)
    if [ "${#HAVE[@]}" -eq 0 ]; then
      echo "no images to save" >&2
      exit 1
    fi
    echo "saving ${#HAVE[@]} images → $ARCHIVE"
    docker save "${HAVE[@]}" | gzip -c >"$ARCHIVE"
    ls -lh "$ARCHIVE"
    ;;
  load)
    test -f "$ARCHIVE" || { echo "missing archive: $ARCHIVE" >&2; exit 1; }
    echo "loading $ARCHIVE"
    gzip -dc "$ARCHIVE" | docker load
    docker image ls --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}' | grep -E 'rag-(kb|guardrails|orchestrator|tracing)|REPOSITORY' || true
    ;;
  *)
    echo "usage: $0 {list|save|load} [archive.tgz]" >&2
    exit 2
    ;;
esac
