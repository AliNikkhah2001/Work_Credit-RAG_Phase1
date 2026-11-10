#!/usr/bin/env bash
# Sprint C #10 — restore app compose stack to a previous SHA (not Gemma/TRT).
#
#   bash scripts/ci_rollback.sh --dry-run
#   bash scripts/ci_rollback.sh --sha abcdef1
#   bash scripts/ci_rollback.sh          # uses deploy/compose/.last_good_sha
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST_REPO="${DANA_HOST_REPO:-$ROOT}"
DRY=0
SHA=""

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --sha) SHA="$2"; shift 2 ;;
    -h|--help) sed -n '1,10p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

LAST_FILE="$HOST_REPO/deploy/compose/.last_good_sha"
PREV_FILE="$HOST_REPO/deploy/compose/.last_good_sha.prev"
if [ -z "$SHA" ]; then
  if [ -f "$PREV_FILE" ]; then
    # Prefer previous good when rolling back from a bad current deploy
    SHA="$(tr -d '[:space:]' <"$PREV_FILE")"
    echo "ci_rollback: using .last_good_sha.prev=$SHA"
  elif [ -f "$LAST_FILE" ]; then
    SHA="$(tr -d '[:space:]' <"$LAST_FILE")"
    echo "ci_rollback: using .last_good_sha=$SHA"
  else
    echo "ci_rollback: ERROR — no --sha and no $LAST_FILE" >&2
    exit 1
  fi
fi

echo "ci_rollback: target SHA=$SHA host=$HOST_REPO role=${DANA_ROLE:-?} host_env=${DANA_HOST:-?}"

if [ "$DRY" = "1" ]; then
  echo "Dry-run OK — would checkout $SHA and compose up dana-prod (apps only)."
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

ENV_FILE=deploy/compose/.env
ENV_FILE_PROD=deploy/compose/.env.prod
COMPOSE_BASE=deploy/compose/compose.base.yml
COMPOSE_LOCAL=deploy/compose/compose.local.yml
COMPOSE_PROD=deploy/compose/compose.prod-sim.yml
COMPOSE_GPU=deploy/compose/compose.gpu.yml

# Prefer host secrets
for src in "$HOST_REPO/deploy/compose/.env" "$HOST_REPO/deploy/compose/.env.prod"; do
  [ -f "$src" ] || continue
  base="$(basename "$src")"
  cp -f "$src" "deploy/compose/$base"
done

if [ "${DANA_HOST:-laptop}" = "gpu" ] || [ "${DANA_ROLE:-stage}" = "prod" ]; then
  test -f "$ENV_FILE_PROD" || cp deploy/compose/.env.example "$ENV_FILE_PROD"
  docker compose -p dana-prod -f "$COMPOSE_BASE" -f "$COMPOSE_GPU" --env-file "$ENV_FILE_PROD" up -d --build \
    kb guardrails orchestrator tracing webui 2>/dev/null \
    || docker compose -p dana-prod -f "$COMPOSE_BASE" -f "$COMPOSE_GPU" --env-file "$ENV_FILE_PROD" up -d --build
else
  test -f "$ENV_FILE" || cp deploy/compose/.env.example "$ENV_FILE"
  docker compose -p dana-prod -f "$COMPOSE_BASE" -f "$COMPOSE_LOCAL" -f "$COMPOSE_PROD" --env-file "$ENV_FILE" up -d --build \
    kb guardrails orchestrator tracing litellm 2>/dev/null \
    || docker compose -p dana-prod -f "$COMPOSE_BASE" -f "$COMPOSE_LOCAL" -f "$COMPOSE_PROD" --env-file "$ENV_FILE" up -d --build
fi

sleep 15
for p in 8100 8200 8000; do
  curl -sf --max-time 5 "http://127.0.0.1:$p/health" && echo " ok:$p" || echo " warming:$p"
done
echo "ci_rollback: done (models/Gemma/TRT untouched)"
