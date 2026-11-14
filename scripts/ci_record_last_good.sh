#!/usr/bin/env bash
# =============================================================================
# ci_record_last_good.sh — record the last-known-good deploy as a manifest.
#
# The manifest is the artifact of record: not just "which commit", but "which
# image tags/digests were running, against which rendered config, with which
# health result". Without the images, a rollback means rebuilding an arbitrary
# SHA and hoping the registry has it; with them, rollback is a re-tag.
#
# Writes:
#   deploy/compose/.last_good.json   full manifest (authoritative)
#   deploy/compose/.last_good_sha    sha only (compat with existing scripts)
#   deploy/compose/.last_good_sha.prev / .last_good.json.prev  (previous)
#
# Usage:
#   bash scripts/ci_record_last_good.sh              # sha from HEAD
#   bash scripts/ci_record_last_good.sh <sha>
#   bash scripts/ci_record_last_good.sh --if-gate-passes <sha>
#       → runs ci_deploy_gate.sh first; records nothing if the gate fails.
#
# Exit: 0 recorded/skipped-ok, 1 error, 3 gate failed (nothing recorded)
# =============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST_REPO="${DANA_HOST_REPO:-$ROOT}"
DIR="$HOST_REPO/deploy/compose"

GATE_FIRST=0
SHA=""

while [ $# -gt 0 ]; do
  case "$1" in
    --if-gate-passes) GATE_FIRST=1; shift ;;
    -h|--help) sed -n '1,28p' "$0"; exit 0 ;;
    *) SHA="$1"; shift ;;
  esac
done

if [ -z "$SHA" ]; then
  SHA="${GIT_COMMIT:-$(git -C "$HOST_REPO" rev-parse HEAD 2>/dev/null || true)}"
fi
if [ -z "$SHA" ]; then
  echo "ci_record_last_good: ERROR — no SHA (pass as \$1 or set GIT_COMMIT)" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Optional gate — never record a deploy that has not proven itself.
# ---------------------------------------------------------------------------
if [ "$GATE_FIRST" = "1" ]; then
  echo "ci_record_last_good: running deploy gate before recording…"
  if ! bash "$ROOT/scripts/ci_deploy_gate.sh"; then
    echo "ci_record_last_good: GATE FAILED — NOT recording last-known-good" >&2
    exit 3
  fi
fi

mkdir -p "$DIR"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
HOSTNAME_S="$(hostname -s 2>/dev/null || hostname 2>/dev/null || echo unknown)"

json_escape() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

# ---------------------------------------------------------------------------
# Image tags actually in use. TAG defaults to the CI tag; if unset the compose
# files fall back to `:local`, which is what a dev/stage host runs.
# ---------------------------------------------------------------------------
TAG="${TAG:-local}"
REGISTRY="${REGISTRY:-}"
detect_digest() { # $1=image ref → sha256:<digest> or ""
  docker image inspect --format '{{index .RepoDigests 0}}' "$1" 2>/dev/null \
    | sed -n 's/.*@//p'
}

IMAGES_JSON=""
DIGESTS_JSON=""
IDS_JSON=""
for svc in kb guardrails orchestrator tracing webui; do
  img="${REGISTRY}rag-${svc}:${TAG}"
  dig="$(detect_digest "$img")"
  iid="$(docker image inspect --format '{{.Id}}' "$img" 2>/dev/null || true)"
  IMAGES_JSON="${IMAGES_JSON}${IMAGES_JSON:+,}\"${svc}\":\"$(json_escape "$img")\""
  if [ -n "$dig" ]; then
    DIGESTS_JSON="${DIGESTS_JSON}${DIGESTS_JSON:+,}\"$(json_escape "$img")\":\"$(json_escape "$dig")\""
  fi
  # Locally built images (no registry push) have no RepoDigests, so their
  # content-addressed image ID is the only stable identity we can record and
  # later re-tag from.
  if [ -n "$iid" ]; then
    IDS_JSON="${IDS_JSON}${IDS_JSON:+,}\"$(json_escape "$img")\":\"$(json_escape "$iid")\""
  fi
done

# ---------------------------------------------------------------------------
# Config hash: the rendered compose config + the identity of the env file.
# If the hash differs, the same SHA does NOT mean the same deployment.
# ---------------------------------------------------------------------------
ENVF="$DIR/.env.prod"
[ -f "$ENVF" ] || ENVF="$DIR/.env"
OVERLAY="$HOST_REPO/deploy/compose/compose.gpu.yml"
[ -f "$OVERLAY" ] || OVERLAY="$HOST_REPO/deploy/compose/compose.local.yml"
CONFIG_HASH=""
if command -v docker >/dev/null 2>&1 && [ -f "$ENVF" ] && [ -f "$OVERLAY" ]; then
  CONFIG_HASH="$( (cd "$HOST_REPO" && docker compose \
      -f deploy/compose/compose.base.yml -f "$OVERLAY" \
      --env-file "$ENVF" config 2>/dev/null) \
    | (command -v sha256sum >/dev/null 2>&1 && sha256sum || shasum -a 256) \
    | awk '{print $1}')"
fi
[ -z "$CONFIG_HASH" ] && CONFIG_HASH="unavailable"

# ---------------------------------------------------------------------------
# Health snapshot (informational — the gate already decided pass/fail)
# ---------------------------------------------------------------------------
HEALTH_JSON=""
for p in 8000 8200 8100 13000; do
  if curl -sf --max-time 3 "http://127.0.0.1:$p/health" >/dev/null 2>&1 \
     || { [ "$p" = "13000" ] && curl -sf --max-time 3 "http://127.0.0.1:$p/" >/dev/null 2>&1; }; then
    HEALTH_JSON="${HEALTH_JSON}${HEALTH_JSON:+,}\"$p\":\"ok\""
  else
    HEALTH_JSON="${HEALTH_JSON}${HEALTH_JSON:+,}\"$p\":\"down\""
  fi
done

# ---------------------------------------------------------------------------
# Rotate previous manifest, then write the new one.
# ---------------------------------------------------------------------------
if [ -f "$DIR/.last_good.json" ]; then
  cp -f "$DIR/.last_good.json" "$DIR/.last_good.json.prev" 2>/dev/null || true
  echo "ci_record_last_good: previous manifest kept as .last_good.json.prev"
fi
if [ -f "$DIR/.last_good_sha" ]; then
  cp -f "$DIR/.last_good_sha" "$DIR/.last_good_sha.prev" 2>/dev/null || true
fi

cat >"$DIR/.last_good.json" <<JSON
{
  "sha": "$(json_escape "$SHA")",
  "tag": "$(json_escape "$TAG")",
  "images": { $IMAGES_JSON },
  "digests": { $DIGESTS_JSON },
  "image_ids": { $IDS_JSON },
  "config_hash": "$CONFIG_HASH",
  "health": { $HEALTH_JSON },
  "recorded_at": "$TS",
  "host": "$(json_escape "$HOSTNAME_S")",
  "project": "$(json_escape "${DANA_GATE_PROJECT:-dana-prod}")"
}
JSON

printf '%s\n' "$SHA" >"$DIR/.last_good_sha"

echo "ci_record_last_good: wrote $DIR/.last_good.json"
echo "  sha=$SHA  tag=$TAG  config_hash=${CONFIG_HASH:0:12}…  host=$HOSTNAME_S"
echo "  health={ $HEALTH_JSON }"

# ---------------------------------------------------------------------------
# Bounded retention for dana-lastgood/* tags.
#
# Runs HERE, right after a new record is written, because this is the only place
# that creates new last-known-good state and therefore the only place that can
# make the previous rollback tags genuinely obsolete. The prune protects every
# tag referenced by a state file — including the one just written — so it cannot
# remove the tag rollback would use. Never fatal: retention must not be able to
# fail a deploy (a full disk is a problem, a failed deploy is an outage).
#
# Opt-in apply: set DANA_LASTGOOD_PRUNE_APPLY=1 (and DANA_LASTGOOD_KEEP=N) to
# retire old tags here. Default is a silent no-op so recording stays fast.
# ---------------------------------------------------------------------------
if [ "${DANA_LASTGOOD_PRUNE_APPLY:-0}" = "1" ]; then
  if [ -x "$ROOT/scripts/dana_lastgood_prune.sh" ]; then
    DANA_HOST_REPO="$HOST_REPO" bash "$ROOT/scripts/dana_lastgood_prune.sh" --apply --quiet \
      || echo "ci_record_last_good: WARN — lastgood retention prune failed (ignored)" >&2
  fi
fi
