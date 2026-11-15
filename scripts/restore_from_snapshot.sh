#!/usr/bin/env bash
# Restore Dana production images from a dated freeze under
# /splunk-data/production/snapshots/<STAMP>/ (or --dir).
#
# Safe path for H200 hybrid (host uvicorn KB/orch/guard + Docker WebUI/Jenkins):
#   1) load or retag snapshot images
#   2) retag to :production / :working / :local / :dana
#   3) recreate WebUI + Jenkins from those tags (does NOT touch Gemma/TRT)
#
# Usage:
#   bash scripts/restore_from_snapshot.sh --list
#   bash scripts/restore_from_snapshot.sh --dry-run
#   bash scripts/restore_from_snapshot.sh --stamp 20261115T124350Z
#   bash scripts/restore_from_snapshot.sh --stamp 20261115T124350Z --apply
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SNAP_ROOT="/splunk-data/production/snapshots"
STAMP=""
DIR=""
DRY=1
APPLY=0
LIST=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stamp) STAMP="$2"; shift 2 ;;
    --dir) DIR="$2"; shift 2 ;;
    --dry-run) DRY=1; APPLY=0; shift ;;
    --apply) APPLY=1; DRY=0; shift ;;
    --list) LIST=1; shift ;;
    -h|--help) sed -n '1,20p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ "$LIST" -eq 1 ]]; then
  ls -1 "$SNAP_ROOT" 2>/dev/null || echo "(no snapshots)"
  exit 0
fi

if [[ -z "$DIR" ]]; then
  [[ -n "$STAMP" ]] || STAMP="$(ls -1 "$SNAP_ROOT" | sort | tail -1)"
  DIR="$SNAP_ROOT/$STAMP"
fi
[[ -d "$DIR" ]] || { echo "missing snapshot dir: $DIR" >&2; exit 1; }

echo "restore_from_snapshot: dir=$DIR apply=$APPLY"

TGZ="$DIR/images/dana-prod-images.tgz"
TAGS=(
  rag-kb:snapshot-20261115
  rag-orchestrator:snapshot-20261115
  rag-guardrails:snapshot-20261115
  rag-webui:snapshot-20261115
  rag-tracing:snapshot-20261115
  dana-jenkins:snapshot-20261115
)

have_snapshot_tags=1
for t in "${TAGS[@]}"; do
  docker image inspect "$t" >/dev/null 2>&1 || have_snapshot_tags=0
done

if [[ "$have_snapshot_tags" -eq 0 ]]; then
  [[ -f "$TGZ" ]] || { echo "no snapshot tags and no $TGZ" >&2; exit 1; }
  echo "loading $TGZ (large)…"
  if [[ "$APPLY" -eq 1 ]]; then
    gzip -dc "$TGZ" | docker load
  else
    echo "dry-run: would docker load $TGZ"
  fi
fi

retag() {
  local src="$1" dst="$2"
  echo "  docker tag $src -> $dst"
  [[ "$APPLY" -eq 1 ]] && docker tag "$src" "$dst"
}

echo "retagging freeze aliases → production/working/local"
# Prefer explicit snapshot-* tags; fall back to :production already in tarball
if docker image inspect rag-webui:snapshot-20261115 >/dev/null 2>&1; then
  retag rag-webui:snapshot-20261115 rag-webui:production
  retag rag-webui:snapshot-20261115 rag-webui:working
  retag rag-webui:snapshot-20261115 rag-webui:dana
  retag rag-webui:snapshot-20261115 rag-webui:local
  retag rag-orchestrator:snapshot-20261115 rag-orchestrator:production
  retag rag-orchestrator:snapshot-20261115 rag-orchestrator:working
  retag rag-orchestrator:snapshot-20261115 rag-orchestrator:local
  retag rag-guardrails:snapshot-20261115 rag-guardrails:production
  retag rag-guardrails:snapshot-20261115 rag-guardrails:working
  retag rag-guardrails:snapshot-20261115 rag-guardrails:local
  retag rag-kb:snapshot-20261115 rag-kb:local
  retag rag-tracing:snapshot-20261115 rag-tracing:local
  retag dana-jenkins:snapshot-20261115 dana-jenkins:production
  retag dana-jenkins:snapshot-20261115 dana-jenkins:working
  retag dana-jenkins:snapshot-20261115 dana-jenkins:lts
fi

if [[ "$APPLY" -eq 1 ]]; then
  echo "recreating Jenkins on pinned CIDR + production image…"
  (cd "$ROOT/deploy/jenkins" && docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --no-build --force-recreate)
  if [[ -x "$ROOT/components/server-setup/deploy/recreate_dana_webui.sh" ]]; then
    echo "recreating WebUI via recreate_dana_webui.sh…"
    bash "$ROOT/components/server-setup/deploy/recreate_dana_webui.sh" || true
  else
    echo "WARN: recreate_dana_webui.sh missing — restart dana-webui-prod manually with rag-webui:dana"
  fi
  echo "recording compose LKG tip from freeze metadata if present…"
  if [[ -f "$DIR/meta/.last_good.json" ]]; then
    cp -a "$DIR/meta/.last_good.json" "$ROOT/deploy/compose/.last_good.json"
  fi
  echo "health (hybrid host profile):"
  bash "$ROOT/deploy/gpu/health.sh" --profile host || true
else
  echo "dry-run complete — re-run with --apply to load/retag/recreate"
fi

echo "KB/pgvector dump restore (optional, destructive):"
echo "  docker exec -i pgvector-kb-prod pg_restore -U postgres -d kb_manager --clean --if-exists < $DIR/db/kb_manager_pgvector-kb-prod.dump"
