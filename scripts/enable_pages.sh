#!/usr/bin/env bash
# =============================================================================
# enable_pages.sh — Idempotently enable GitHub Pages (branch → / root) for the
# monitoring repo, and verify the published URL responds 200.
#
# Pages deploys straight from the `main` branch root — no Actions workflow, no
# build step. That keeps the HealthCheck repo free of any CI config, so report
# pushes can never trigger Jenkins (which is a multibranch job on a different
# repo anyway).
#
# Usage:
#   bash scripts/enable_pages.sh                  # enable + verify
#   bash scripts/enable_pages.sh --check          # verify only, exit 1 if dead
#   bash scripts/enable_pages.sh --branch main    # override source branch
#   bash scripts/enable_pages.sh --repo owner/name
#
# Requires: gh CLI authenticated with `repo` scope (and `pages` write).
# =============================================================================
set -uo pipefail

REPO="${HEALTH_REPO_SLUG:-AliNikkhah2001/Work_RAG_HealthCheck}"
BRANCH="${HEALTH_PAGES_BRANCH:-main}"
MODE="enable"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { printf "%b[OK]%b   %s\n" "$GREEN" "$NC" "$*"; }
warn() { printf "%b[WARN]%b %s\n" "$YELLOW" "$NC" "$*"; }
fail() { printf "%b[FAIL]%b %s\n" "$RED" "$NC" "$*"; }
info() { printf "%b[INFO]%b %s\n" "$CYAN" "$NC" "$*"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)  MODE="check"; shift ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --repo)   REPO="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

if ! command -v gh >/dev/null 2>&1; then
  fail "gh CLI not installed — install from https://cli.github.com"
  exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
  fail "gh is not authenticated — run: gh auth login"
  exit 1
fi

# --- Resolve the expected Pages URL -----------------------------------------
OWNER="${REPO%%/*}"
NAME="${REPO##*/}"
# Lowercase without ${var,,} — macOS ships bash 3.2, which has no ${var,,}.
OWNER_LC="$(printf '%s' "$OWNER" | tr '[:upper:]' '[:lower:]')"
NAME_LC="$(printf '%s' "$NAME" | tr '[:upper:]' '[:lower:]')"
if [[ "$NAME_LC" == "${OWNER_LC}.github.io" ]]; then
  DEFAULT_URL="https://${OWNER_LC}.github.io/"
else
  DEFAULT_URL="https://${OWNER_LC}.github.io/${NAME_LC}/"
fi
PAGES_URL="${HEALTH_PAGES_URL:-$DEFAULT_URL}"

info "repo:    $REPO"
info "branch:  $BRANCH (served from repo root)"
info "url:     $PAGES_URL"
# `gh api` prints the JSON error body on stdout for a 404, so `--jq` failures
# must be judged by exit status, not by the presence of output.
pages_field() {
  local field="$1" raw
  raw="$(gh api "repos/$REPO/pages" 2>/dev/null)" || { printf ''; return 1; }
  printf '%s' "$raw" | python3 -c '
import json, sys
path = sys.argv[1].split(".")
try:
    node = json.load(sys.stdin)
    for key in path:
        node = node[key] if isinstance(node, dict) else None
    print("" if node is None else node)
except Exception:
    print("")
' "$field" 2>/dev/null
}

if current_status="$(pages_field status)" && [[ -n "$current_status" ]]; then
  current_branch="$(pages_field source.branch)"
  current_path="$(pages_field source.path)"
  info "Pages already enabled (status=$current_status branch=${current_branch:-unknown} path=${current_path:-unknown})"
else
  current_status="404"
  current_branch=""
  current_path=""
  info "Pages is not enabled yet"
fi

# --- Enable / repair --------------------------------------------------------
# GitHub accepts both this legacy body and source{}. Sending the source object
# explicitly is what makes the call idempotent when Pages exists on the wrong
# branch.
enable_pages() {
  gh api -X POST "repos/$REPO/pages" \
    -f "source[branch]=$BRANCH" \
    -f "source[path]=/" \
    -H "Accept: application/vnd.github+json" >/dev/null 2>&1
}

if [[ "$MODE" == "enable" ]]; then
  if [[ "$current_status" == "404" || -z "$current_status" ]]; then
    if enable_pages; then
      ok "enabled Pages from $BRANCH/"
    else
      # A 409 means it exists already (race with a previous run) — fall through
      # to the update path rather than failing the script.
      warn "create returned non-zero — attempting update instead"
      gh api -X PUT "repos/$REPO/pages" \
        -f "source[branch]=$BRANCH" -f "source[path]=/" >/dev/null 2>&1 \
        && ok "updated Pages source to $BRANCH/" \
        || { fail "could not enable Pages (needs 'repo' + pages permission)"; exit 1; }
    fi
  elif [[ "$current_branch" != "$BRANCH" || "$current_path" != "/" ]]; then
    if gh api -X PUT "repos/$REPO/pages" \
        -f "source[branch]=$BRANCH" -f "source[path]=/" >/dev/null 2>&1; then
      ok "repointed Pages source to $BRANCH/"
    else
      fail "could not update Pages source"
      exit 1
    fi
  else
    ok "Pages already points at $BRANCH/ — nothing to change"
  fi

  # Custom domain / HTTPS: leave untouched unless explicitly requested, so this
  # script never fights a manual configuration.
  if [[ -n "${HEALTH_PAGES_CNAME:-}" ]]; then
    gh api -X PUT "repos/$REPO/pages" -f "cname=$HEALTH_PAGES_CNAME" >/dev/null 2>&1 \
      && ok "set custom domain $HEALTH_PAGES_CNAME" \
      || warn "could not set custom domain"
  fi
fi

# --- Verify ----------------------------------------------------------------
# GitHub Pages paths are case-sensitive: the repo name in the URL keeps its
# original casing, so a lowercased guess 404s even on a healthy deployment.
# Trust the API's html_url once Pages exists.
api_url="$(pages_field html_url)"
if [[ -n "$api_url" ]]; then
  PAGES_URL="${HEALTH_PAGES_URL:-$api_url}"
  info "url:     $PAGES_URL (from Pages API)"
fi

# Pages builds asynchronously. .nojekyll must be committed on the source branch
# first; if it is missing the build still succeeds but paths with underscores
# 404. Probe for up to ~2 minutes.
info "waiting for $PAGES_URL to answer 200 (up to 120s)"
code="000"
for attempt in $(seq 1 24); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 12 "$PAGES_URL" 2>/dev/null || echo 000)"
  if [[ "$code" == "200" ]]; then
    ok "published: $PAGES_URL (HTTP 200)"
    break
  fi
  [[ "$attempt" -eq 1 ]] && info "first probe: HTTP $code (build in progress is normal)"
  sleep 5
done

if [[ "$code" != "200" ]]; then
  warn "site not live yet (last HTTP $code)"
  echo "  Pages builds can take a few minutes on the first deploy."
  echo "  Check:  gh api repos/$REPO/pages --jq '.status, .html_url'"
  echo "  Re-run: bash scripts/enable_pages.sh --check"
  [[ "$MODE" == "check" ]] && exit 1
fi

echo ""
echo "Dashboard: $PAGES_URL"
echo "Repo:      https://github.com/$REPO"
exit 0
