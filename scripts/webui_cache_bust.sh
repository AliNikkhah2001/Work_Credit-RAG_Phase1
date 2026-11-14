#!/usr/bin/env bash
# =============================================================================
# webui_cache_bust.sh — Force WebUI frontend cache invalidation + full rebuild.
#
# Problem: Open WebUI (port 13000) sits behind a middleware/gateway router
# (chat.ics24.ir) that caches static assets + frontend theme data. After a
# docker compose rebuild, the browser/middleware serves stale theme/build
# assets, so visual/config changes don't take effect immediately.
#
# Fix:
#   1) Bump WEBUI_BUILD_VERSION (cache-bust token) in deploy/compose/.env.prod
#   2) Force a clean frontend rebuild (rm -rf build .svelte-kit, npm ci --force)
#   3) Restart the webui compose service so the new version tag lands
#   4) Emit cache-busting headers guidance for the middleware (nginx)
#
# Run on the GPU server after a WebUI/theme change:
#   DANA_HOST_REPO=/path bash scripts/webui_cache_bust.sh --bump --restart
# =============================================================================
set -uo pipefail

ROOT="${DANA_HOST_REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"

BUMP=0
RESTART=0
DRY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bump) BUMP=1; shift ;;
    --restart) RESTART=1; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help)
      sed -n '1,40p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

ENV_PROD="$ROOT/deploy/compose/.env.prod"
ENV_FILE="$ROOT/deploy/compose/.env"

log() { printf '[webui-cache-bust] %s\n' "$*"; }

current_version() {
  grep -E '^WEBUI_BUILD_VERSION=' "$ENV_PROD" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '[:space:]'
}

bump_version() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  local cur
  cur="$(current_version)"
  cur="${cur:-0}"
  local next=$((cur + 1))
  if grep -qE '^WEBUI_BUILD_VERSION=' "$f"; then
    sed -i "s/^WEBUI_BUILD_VERSION=.*/WEBUI_BUILD_VERSION=$next/" "$f"
  else
    echo "WEBUI_BUILD_VERSION=$next" >>"$f"
  fi
  log "$f: WEBUI_BUILD_VERSION $cur -> $next"
}

if [[ "$BUMP" == "1" ]]; then
  [[ "$DRY" == "1" ]] && { log "dry-run: would bump WEBUI_BUILD_VERSION"; } || bump_version "$ENV_PROD"
fi

NEW_VER="$(current_version)"
log "effective WEBUI_BUILD_VERSION=${NEW_VER:-unset}"

if [[ "$RESTART" == "1" ]]; then
  if [[ "$DRY" == "1" ]]; then
    log "dry-run: would restart webui compose service"
  else
    log "restarting webui (dana-prod)…"
    if [[ -f "$ENV_PROD" ]]; then
      docker compose -p dana-prod \
        -f "$ROOT/deploy/compose/compose.base.yml" \
        -f "$ROOT/deploy/compose/compose.gpu.yml" \
        --env-file "$ENV_PROD" \
        up -d --no-build --force-recreate webui >>"$ROOT/scripts/webui_cache_bust.log" 2>&1 \
        && log "webui restarted (version=$NEW_VER)" \
        || { log "webui restart failed — see webui_cache_bust.log"; exit 1; }
    else
      log "no .env.prod — skipping restart"
    fi
  fi
fi

cat <<EOF

=== WebUI cache-bust ready ===
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
