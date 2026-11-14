#!/usr/bin/env bash
# =============================================================================
# ci_github_status.sh — Report Jenkins build/deploy status to GitHub commits.
#
# Gives you visibility on GitHub: every commit shows whether its Jenkins build
# (stage/prod) passed or failed, plus which machine (laptop vs gpu-server) it
# originated from (via the Machine-origin commit trailer).
#
# Requires a GitHub PAT with `repo:status` scope: GITHUB_TOKEN env var.
#
# Usage (called from Jenkinsfile post-build):
#   GITHUB_TOKEN=... bash scripts/ci_github_status.sh \
#       --sha <commit> --state success|failure|pending \
#       --context "ci/dana-stage" --description "..." --target-url <jenkins run url>
# =============================================================================
set -uo pipefail

SHA=""
STATE="pending"
CONTEXT="ci/dana"
DESCRIPTION="Jenkins build"
TARGET_URL=""
REPO="AliNikkhah2001/Work_Credit-RAG_Phase1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sha) SHA="$2"; shift 2 ;;
    --state) STATE="$2"; shift 2 ;;
    --context) CONTEXT="$2"; shift 2 ;;
    --description) DESCRIPTION="$2"; shift 2 ;;
    --target-url) TARGET_URL="$2"; shift 2 ;;
    --repo) REPO="$2"; shift 2 ;;
    -h|--help) sed -n '1,40p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$SHA" ]]; then
  echo "ci_github_status: --sha required" >&2; exit 2
fi
if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "ci_github_status: GITHUB_TOKEN not set — skipping GitHub status" >&2
  exit 0
fi

# Build JSON payload (avoid jq dependency on minimal agent)
# Escape description for JSON
esc_desc="$(printf '%s' "$DESCRIPTION" | sed 's/"/\\"/g')"
payload=$(printf '{"state":"%s","target_url":"%s","description":"%s","context":"%s"}' \
  "$STATE" "$TARGET_URL" "$esc_desc" "$CONTEXT")

code="$(curl -s -o /tmp/ci_gh_status.out -w '%{http_code}' \
  -X POST "https://api.github.com/repos/${REPO}/statuses/${SHA}" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -H "User-Agent: dana-ci" \
  -d "$payload" 2>/dev/null || echo 000)"

if [[ "$code" == "201" ]]; then
  echo "ci_github_status: reported $STATE for $SHA ($CONTEXT)"
else
  echo "ci_github_status: failed http=$code — $(cat /tmp/ci_gh_status.out 2>/dev/null | head -c 200)" >&2
  exit 1
fi
