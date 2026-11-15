#!/usr/bin/env bash
# Freeze currently-running / LKG production images into
# /splunk-data/production/snapshots/<STAMP>/ and retag as snapshot-<stamp>.
#
# Triggered by Jenkins when the commit message contains [ci snapshot]
# (see Jenkinsfile + scripts/ci_message_gate.py).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SNAP_ROOT="${SNAP_ROOT:-/splunk-data/production/snapshots}"
STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
DIR="$SNAP_ROOT/$STAMP"
DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1

IMAGES=(
  rag-kb:local
  rag-orchestrator:local
  rag-guardrails:local
  rag-webui:dana
  rag-tracing:local
  dana-jenkins:lts
)

echo "[snapshot] stamp=$STAMP dir=$DIR dry=$DRY"
mkdir -p "$DIR/images" "$DIR/meta" "$DIR/kb" "$DIR/db"

PRESENT=()
for ref in "${IMAGES[@]}"; do
  if docker image inspect "$ref" >/dev/null 2>&1; then
    PRESENT+=("$ref")
    short="${ref%%:*}"
    tag="snapshot-${STAMP:0:8}"
    # Prefer full stamp tag when short; also write snapshot-YYYYMMDD for restore compat
    echo "  tag $ref -> ${short}:snapshot-$STAMP"
    if [[ "$DRY" -eq 0 ]]; then
      docker tag "$ref" "${short}:snapshot-$STAMP"
      docker tag "$ref" "${short}:$tag" 2>/dev/null || true
    fi
  else
    echo "  WARN missing image $ref"
  fi
done

if [[ ${#PRESENT[@]} -eq 0 ]]; then
  echo "ERROR: no production images present to snapshot" >&2
  exit 1
fi

TGZ="$DIR/images/dana-prod-images.tgz"
if [[ "$DRY" -eq 0 ]]; then
  echo "[snapshot] docker save → $TGZ"
  docker save "${PRESENT[@]}" | gzip -c >"$TGZ"
  sha256sum "$TGZ" | awk '{print $1}' >"$TGZ.sha256"
  # pin metadata
  {
    echo "{"
    echo "  \"stamp\": \"$STAMP\","
    echo "  \"created_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
    echo "  \"images\": ["
    for i in "${!PRESENT[@]}"; do
      ref="${PRESENT[$i]}"
      id="$(docker image inspect -f '{{.Id}}' "$ref" 2>/dev/null || true)"
      comma=","; [[ "$i" -eq $((${#PRESENT[@]} - 1)) ]] && comma=""
      printf '    {"ref":"%s","id":"%s"}%s\n' "$ref" "$id" "$comma"
    done
    echo "  ],"
    echo "  \"git_head\": \"$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)\","
    echo "  \"host\": \"$(hostname -s 2>/dev/null || hostname)\""
    echo "}"
  } >"$DIR/meta/PRODUCTION_PIN.json"
  cp -a "$ROOT/deploy/PRODUCTION_PIN.json" "$DIR/meta/PRODUCTION_PIN.repo.json" 2>/dev/null || true
  # lightweight KB pin copy
  if [[ -d "$ROOT/components/knowledgebase/kb-source/.dvc_pins" ]]; then
    cp -a "$ROOT/components/knowledgebase/kb-source/.dvc_pins/." "$DIR/kb/" 2>/dev/null || true
  fi
  # registry for the reporting tool / Pages
  REG="/var/lib/dana-health/snapshots.json"
  mkdir -p "$(dirname "$REG")"
  IMAGES_JSON="$(printf '%s\n' "${PRESENT[@]}" | python3 -c 'import json,sys; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')"
  STAMP="$STAMP" DIR="$DIR" TGZ="$TGZ" REG="$REG" IMAGES_JSON="$IMAGES_JSON" python3 - <<'PY'
import json, os, time
from pathlib import Path
reg = Path(os.environ["REG"])
items = []
if reg.is_file():
    try:
        items = json.loads(reg.read_text()).get("snapshots") or []
    except Exception:
        items = []
stamp = os.environ["STAMP"]
items = [x for x in items if x.get("stamp") != stamp]
items.append({
    "stamp": stamp,
    "dir": os.environ["DIR"],
    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "tarball": os.environ["TGZ"],
    "images": json.loads(os.environ["IMAGES_JSON"]),
})
reg.write_text(json.dumps({"schema_version": "snapshots-index/v1", "snapshots": items}, indent=2) + "\n")
print(f"[snapshot] registry {reg} count={len(items)}")
PY
  echo "[snapshot] OK $DIR"
else
  echo "[snapshot] dry-run: would save ${#PRESENT[@]} images to $TGZ"
fi
