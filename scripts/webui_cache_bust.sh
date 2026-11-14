#!/usr/bin/env bash
# =============================================================================
# webui_cache_bust.sh — Force WebUI frontend cache invalidation + rebuild.
#
# Problem: Open WebUI (port 13000) sits behind a middleware/gateway router
# (chat.ics24.ir) that caches static assets + frontend theme/build data. After a
# docker compose rebuild, the browser/middleware serves stale theme/build
# assets, so visual/config changes don't take effect immediately.
#
# A second, purely local cause: the WebUI frontend is built ON THE HOST andCOPYed
# into Dockerfile.local. Recreating the container (`compose up` without a build)
# reuses the old image forever. Bumping a token in .env does NOT change the
# image — the token only reaches the image through --build-arg BUILD_HASH.
# So --restart always rebuilds the webui image via dana-local-image.sh, then
# recreates the container from the new image.
#
# Fix steps:
#   1) Bump WEBUI_BUILD_VERSION (cache-bust token) in the target env file
#   2) Rebuild the frontend image (script wipes build/, stamps BUILD_HASH)
#   3) Recreate the webui compose service so the new image is used
#   4) Emit cache-busting header guidance for the middleware (nginx)
#
# Run on the GPU server after a WebUI/theme change:
#   DANA_HOST_REPO=/path bash scripts/webui_cache_bust.sh --bump --restart
# On this laptop:
#   bash scripts/webui_cache_bust.sh --bump --profile local --restart
# =============================================================================
set -uo pipefail

ROOT="${DANA_HOST_REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT" || exit 1

BUMP=0
RESTART=0
DRY=0
PROFILE="${DANA_PROFILE:-gpu}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bump) BUMP=1; shift ;;
    --restart) RESTART=1; shift ;;
    --dry-run) DRY=1; shift ;;
    --profile) PROFILE="${2:-}"; shift 2 ;;
    -h|--help)
      sed -n '1,40p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# profile -> project + env file + compose layering (mirrors deploy/gpu/lib/common.sh)
case "$PROFILE" in
  gpu)      PROJECT="dana-prod";     ENV_FILE="$ROOT/deploy/compose/.env.prod"
            COMPOSE=(-f "$ROOT/deploy/compose/compose.base.yml" -f "$ROOT/deploy/compose/compose.gpu.yml") ;;
  local)    PROJECT="dana-local";    ENV_FILE="$ROOT/deploy/compose/.env"
            COMPOSE=(-f "$ROOT/deploy/compose/compose.base.yml" -f "$ROOT/deploy/compose/compose.local.yml") ;;
  stage)    PROJECT="dana-stage";    ENV_FILE="$ROOT/deploy/compose/.env"
            COMPOSE=(-f "$ROOT/deploy/compose/compose.base.yml" -f "$ROOT/deploy/compose/compose.local.yml" -f "$ROOT/deploy/compose/compose.stage.yml") ;;
  prod-sim) PROJECT="dana-prod-sim"; ENV_FILE="$ROOT/deploy/compose/.env"
            COMPOSE=(-f "$ROOT/deploy/compose/compose.base.yml" -f "$ROOT/deploy/compose/compose.local.yml" -f "$ROOT/deploy/compose/compose.prod-sim.yml") ;;
  *) echo "unknown profile '$PROFILE' (gpu|local|stage|prod-sim)" >&2; exit 2 ;;
esac

# gpu falls back to .env when .env.prod is absent (same rule as compose.gpu callers)
[[ -f "$ENV_FILE" ]] || ENV_FILE="$ROOT/deploy/compose/.env"

log() { printf '[webui-cache-bust] %s\n' "$*"; }

current_version() {
  grep -hE '^WEBUI_BUILD_VERSION=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '[:space:]'
}

bump_version() {
  local f="$1"
  [[ -f "$f" ]] || { log "no env file at $f — cannot bump"; return 1; }
  local cur next
  cur="$(current_version)"; cur="${cur:-0}"
  next=$((cur + 1))
  # Portable in-place edit: BSD sed (-i '') and GNU sed (-i) disagree, so
  # rewrite via a temp file. macOS `sed -i` without a backup suffix fails hard.
  local tmp
  tmp="$(mktemp "${TMPDIR:-/tmp}/webui-env.XXXXXX")" || return 1
  if grep -qE '^WEBUI_BUILD_VERSION=' "$f"; then
    awk -v v="$next" '/^WEBUI_BUILD_VERSION=/{print "WEBUI_BUILD_VERSION=" v; next} {print}' "$f" >"$tmp"
  else
    cat "$f" >"$tmp"
    printf 'WEBUI_BUILD_VERSION=%s\n' "$next" >>"$tmp"
  fi
  cat "$tmp" >"$f" && rm -f "$tmp"
  log "$f: WEBUI_BUILD_VERSION $cur -> $next"
}

if [[ "$BUMP" == "1" ]]; then
  if [[ "$DRY" == "1" ]]; then
    log "dry-run: would bump WEBUI_BUILD_VERSION in $ENV_FILE"
  else
    bump_version "$ENV_FILE" || exit 1
  fi
fi

NEW_VER="$(current_version)"
log "effective WEBUI_BUILD_VERSION=${NEW_VER:-unset} (profile=$PROFILE project=$PROJECT)"

if [[ "$RESTART" == "1" ]]; then
  if [[ "$DRY" == "1" ]]; then
    log "dry-run: would rebuild rag-webui and recreate webui in $PROJECT"
  else
    if [[ ! -f "$ENV_FILE" ]]; then
      log "no env file ($ENV_FILE) — skipping restart"
    else
      # Rebuild is required: --no-build would recreate the container from the
      # SAME stale image, which is exactly the bug this script exists to fix.
      log "rebuilding webui frontend image…"
      if ! WEBUI_BUILD_VERSION="$NEW_VER" bash "$ROOT/components/webui/scripts/dana-local-image.sh"; then
        log "webui image build failed — aborting restart"; exit 1
      fi
      log "recreating webui in $PROJECT…"
      if docker compose -p "$PROJECT" "${COMPOSE[@]}" --env-file "$ENV_FILE" \
          up -d --no-deps --force-recreate webui >>"$ROOT/scripts/webui_cache_bust.log" 2>&1; then
        log "webui restarted (version=$NEW_VER)"
      else
        log "webui restart failed — see webui_cache_bust.log"; exit 1
      fi
    fi
  fi
fi

cat <<EOF

=== WebUI cache-bust ready ===
Profile:          $PROFILE (project $PROJECT)
Cache-bust token: WEBUI_BUILD_VERSION=$NEW_VER

To make the middleware (chat.ics24.ir gateway) stop serving stale WebUI assets,
add cache-busting headers on the GPU-side reverse proxy / middleware for port 13000:

  location / {
    proxy_pass http://127.0.0.1:13000;
    # Force revalidation on every deploy — middleware must not cache HTML/JS/CSS
    add_header Cache-Control "no-cache, must-revalidate" always;
    add_header X-WebUI-Version "$NEW_VER" always;
  }

Or, if the middleware supports cache keys, include WEBUI_BUILD_VERSION in the key
so a bump invalidates the entire cached WebUI frontend.

Then reload the middleware and hard-refresh the browser (Ctrl+F5) at chat.ics24.ir.

EOF
