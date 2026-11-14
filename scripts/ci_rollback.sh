#!/usr/bin/env bash
# =============================================================================
# ci_rollback.sh — restore the last-known-good app stack.
#
# Two modes:
#   1. Manifest restore (preferred): .last_good.json records the exact image
#      tags AND digests that were healthy. Rollback re-tags those digests and
#      brings the stack up with --no-build. No rebuilding an arbitrary SHA and
#      hoping its Dockerfile still resolves.
#   2. SHA restore (fallback): old behaviour, used only when no manifest exists
#      or --sha is given explicitly — checks out the SHA in a scratch clone and
#      builds.
#
# Never touches Gemma / Manager / TRT (host-managed by server-setup).
#
# Usage:
#   bash scripts/ci_rollback.sh --dry-run
#   bash scripts/ci_rollback.sh                  # restore .last_good.json.prev
#   bash scripts/ci_rollback.sh --target current # restore .last_good.json
#   bash scripts/ci_rollback.sh --sha abcdef1    # legacy SHA rebuild
#
# Exit: 0 restored (or dry-run ok), 1 nothing to restore / restore failed
# =============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST_REPO="${DANA_HOST_REPO:-$ROOT}"
DIR="$HOST_REPO/deploy/compose"

DRY=0
SHA=""
TARGET="prev"   # prev | current

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --sha) SHA="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    -h|--help) sed -n '1,26p' "$0"; exit 0 ;;
    *) echo "ci_rollback: unknown arg: $1" >&2; exit 2 ;;
  esac
done

MANIFEST=""
case "$TARGET" in
  prev)    MANIFEST="$DIR/.last_good.json.prev" ;;
  current) MANIFEST="$DIR/.last_good.json" ;;
  *) echo "ci_rollback: --target must be prev|current" >&2; exit 2 ;;
esac

# Small JSON field reader (no jq dependency on minimal hosts).
json_field() { # $1=file $2=key → raw string value
  sed -n "s/.*\"$2\"[[:space:]]*:[[:space:]]*\"\\([^\"]*\\)\".*/\\1/p" "$1" 2>/dev/null | head -1
}

echo "ci_rollback: host=$HOST_REPO role=${DANA_ROLE:-?} host_env=${DANA_HOST:-?}"

# ---------------------------------------------------------------------------
# Preferred path: restore recorded images from the manifest.
# ---------------------------------------------------------------------------
if [ -z "$SHA" ] && [ -f "$MANIFEST" ]; then
  M_SHA="$(json_field "$MANIFEST" sha)"
  M_TAG="$(json_field "$MANIFEST" tag)"
  M_AT="$(json_field "$MANIFEST" recorded_at)"
  echo "ci_rollback: manifest $MANIFEST"
  echo "  sha=$M_SHA tag=$M_TAG recorded_at=$M_AT"

  # Collect recorded image→digest pairs. Locally built images have no
  # RepoDigests, so fall back to the recorded content-addressed image ID.
  DIGEST_PAIRS="$(sed -n 's/.*"digests"[[:space:]]*:[[:space:]]*{\(.*\)}.*/\1/p' "$MANIFEST" | head -1 | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  ID_PAIRS="$(sed -n 's/.*"image_ids"[[:space:]]*:[[:space:]]*{\(.*\)}.*/\1/p' "$MANIFEST" | head -1 | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  if [ -z "$DIGEST_PAIRS" ]; then
    if [ -n "$ID_PAIRS" ]; then
      echo "ci_rollback: no registry digests — using recorded local image IDs"
      DIGEST_PAIRS="$ID_PAIRS"
    else
      echo "ci_rollback: WARN — manifest has no images recorded; falling back to tag-only restore"
    fi
  fi

  if [ "$DRY" = "1" ]; then
    n_pairs="$(printf '%s\n' "$DIGEST_PAIRS" | tr ',' '\n' | grep -c . || true)"
    if [ "$n_pairs" -eq 0 ]; then
      echo "Dry-run: WARN — this manifest records no images (older format)."
      echo "         A real rollback would fall back to tag-only compose up."
    else
      echo "Dry-run OK — would restore $n_pairs image(s) and \`compose up -d --no-build\`:"
      printf '%s\n' "$DIGEST_PAIRS" | tr ',' '\n' \
        | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' | sed 's/^/  /'
    fi
    exit 0
  fi

  # Re-tag each recorded digest back onto its tag so compose resolves the exact
  # bits that were healthy, even if the tag has since moved.
  restored=0
  # One `img":"digest` pair per line, so we never fight word-splitting.
  PAIR_FILE="$(mktemp)"
  printf '%s\n' "$DIGEST_PAIRS" | tr ',' '\n' \
    | sed -n 's/^[[:space:]]*"\([^"]*\)"[[:space:]]*:[[:space:]]*"\([^"]*\)"[[:space:]]*$/\1 \2/p' \
    >"$PAIR_FILE"

  while read -r img dig; do
    [ -n "$img" ] && [ -n "$dig" ] || continue
    # Recorded value is either a registry digest (sha256:… from a push) or a
    # local image ID (sha256:… from a build) — both are content-addressed and
    # both can be re-tagged onto the recorded image reference.
    cur="$(docker image inspect --format '{{index .RepoDigests 0}}' "$img" 2>/dev/null | sed -n 's/.*@//p')"
    if [ "$cur" = "$dig" ]; then
      echo "ci_rollback: $img already at recorded digest ${dig:0:19}…"
      restored=$((restored+1)); continue
    fi
    if docker image inspect "$dig" >/dev/null 2>&1; then
      docker tag "$dig" "$img" && restored=$((restored+1)) \
        && echo "ci_rollback: re-tagged $img → recorded image ${dig:0:19}…"
    elif docker pull "${img%:*}@${dig}" >/dev/null 2>&1; then
      docker tag "${img%:*}@${dig}" "$img" && restored=$((restored+1)) \
        && echo "ci_rollback: pulled + re-tagged $img → ${dig:0:19}…"
    else
      echo "ci_rollback: WARN — recorded image ${dig:0:19}… for $img is not available locally or in a registry" >&2
    fi
  done <"$PAIR_FILE"
  rm -f "$PAIR_FILE"

  echo "ci_rollback: restored $restored image(s) from manifest"

  ENVF="$DIR/.env.prod"; [ -f "$ENVF" ] || ENVF="$DIR/.env"
  OVERLAY="$HOST_REPO/deploy/compose/compose.gpu.yml"
  [ -f "$OVERLAY" ] || OVERLAY="$HOST_REPO/deploy/compose/compose.local.yml"
  PROJECT="${DANA_GATE_PROJECT:-dana-prod}"

  echo "ci_rollback: compose up -d --no-build (project=$PROJECT)"
  if ! TAG="$M_TAG" docker compose -p "$PROJECT" \
        -f "$HOST_REPO/deploy/compose/compose.base.yml" \
        -f "$OVERLAY" \
        --env-file "$ENVF" up -d --no-build kb guardrails orchestrator tracing webui; then
    echo "ci_rollback: ERROR — compose up failed" >&2
    exit 1
  fi

  echo "ci_rollback: running deploy gate on the restored stack…"
  if TAG="$M_TAG" bash "$ROOT/scripts/ci_deploy_gate.sh"; then
    echo "ci_rollback: OK — restored stack is healthy (sha=$M_SHA)"
    exit 0
  fi
  echo "ci_rollback: ERROR — restored stack failed the deploy gate" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Legacy path: rebuild a SHA.
# ---------------------------------------------------------------------------
if [ -z "$SHA" ]; then
  if [ -f "$DIR/.last_good_sha.prev" ]; then
    SHA="$(tr -d '[:space:]' <"$DIR/.last_good_sha.prev")"
    echo "ci_rollback: legacy — using .last_good_sha.prev=$SHA"
  elif [ -f "$DIR/.last_good_sha" ]; then
    SHA="$(tr -d '[:space:]' <"$DIR/.last_good_sha")"
    echo "ci_rollback: legacy — using .last_good_sha=$SHA"
  else
    echo "ci_rollback: ERROR — no manifest, no --sha, no .last_good_sha" >&2
    exit 1
  fi
fi

if [ "$DRY" = "1" ]; then
  echo "Dry-run OK — would checkout $SHA in a scratch clone and rebuild (legacy path)."
  exit 0
fi

WORK="${HOST_REPO}/.ci-rollback-work"
mkdir -p "$WORK"
if [ ! -d "$WORK/.git" ]; then
  git clone --no-checkout "$HOST_REPO" "$WORK" 2>/dev/null \
    || git clone --no-checkout "$(git -C "$HOST_REPO" remote get-url origin)" "$WORK"
fi
cd "$WORK"
git fetch --all --tags 2>/dev/null || true
git checkout -f "$SHA"
bash scripts/ci_submodule_sync.sh || git submodule update --init --recursive

ENVF=deploy/compose/.env
ENVF_PROD=deploy/compose/.env.prod
for src in "$HOST_REPO/deploy/compose/.env" "$HOST_REPO/deploy/compose/.env.prod"; do
  [ -f "$src" ] || continue
  cp -f "$src" "deploy/compose/$(basename "$src")"
done

PROJECT="${DANA_GATE_PROJECT:-dana-prod}"
if [ "${DANA_HOST:-laptop}" = "gpu" ] || [ "${DANA_ROLE:-stage}" = "prod" ]; then
  [ -f "$ENVF_PROD" ] || cp deploy/compose/.env.example "$ENVF_PROD"
  docker compose -p "$PROJECT" -f deploy/compose/compose.base.yml \
    -f deploy/compose/compose.gpu.yml --env-file "$ENVF_PROD" \
    up -d --build kb guardrails orchestrator tracing webui
else
  [ -f "$ENVF" ] || cp deploy/compose/.env.example "$ENVF"
  docker compose -p "$PROJECT" -f deploy/compose/compose.base.yml \
    -f deploy/compose/compose.local.yml -f deploy/compose/compose.prod-sim.yml \
    --env-file "$ENVF" up -d --build kb guardrails orchestrator tracing
fi

echo "ci_rollback: legacy rebuild done for $SHA (models/Gemma/TRT untouched)"
