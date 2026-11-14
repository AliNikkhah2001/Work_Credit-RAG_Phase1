#!/usr/bin/env bash
# =============================================================================
# ci_github_status.sh — Report a Jenkins result to a GitHub commit status.
#
# This is the explicit, per-stage channel. Jenkins' own GitHub Branch Source
# plugin also posts one coarse status (`continuous-integration/jenkins/branch`)
# but it only knows SUCCESS/UNSTABLE/FAILURE for the whole run, so it cannot say
# *which* verification happened. Use this script to publish named contexts
# (`dana/validate`, `dana/stage-deploy`, `dana/prod-deploy`, ...) that branch
# protection can require individually.
#
# Requires a credential with `repo:status`. Never hardcode it:
#   Jenkins credential id  github-pat  (username + PAT)
#   exposed to the pipeline as GITHUB_TOKEN
#
# Usage:
#   GITHUB_TOKEN=... bash scripts/ci_github_status.sh \
#       --sha <commit> --state success|failure|pending|error \
#       --context "dana/validate" --description "..." --target-url <build url>
#
# Exit status: 0 unless --strict and the API call failed. Reporting a status is
# observability; it must not turn a good build red because GitHub hiccuped.
# =============================================================================
set -uo pipefail

SHA=""
STATE="pending"
CONTEXT="dana/ci"
DESCRIPTION="Jenkins build"
TARGET_URL=""
REPO="${GITHUB_REPO:-AliNikkhah2001/Work_Credit-RAG_Phase1}"
STRICT=0
TIMEOUT=15

# GitHub caps the description at 140 characters.
DESC_MAX=140

usage() { sed -n '1,26p' "$0"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sha) SHA="${2:-}"; shift 2 ;;
    --state) STATE="${2:-}"; shift 2 ;;
    --context) CONTEXT="${2:-}"; shift 2 ;;
    --description) DESCRIPTION="${2:-}"; shift 2 ;;
    --target-url) TARGET_URL="${2:-}"; shift 2 ;;
    --repo) REPO="${2:-}"; shift 2 ;;
    --strict) STRICT=1; shift ;;
    --timeout) TIMEOUT="${2:-15}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ci_github_status: unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$SHA" ]]; then
  echo "ci_github_status: --sha required" >&2; exit 2
fi
case "$STATE" in
  success|failure|pending|error) ;;
  *) echo "ci_github_status: --state must be success|failure|pending|error (got '$STATE')" >&2; exit 2 ;;
esac
if [[ ${#DESCRIPTION} -gt $DESC_MAX ]]; then
  DESCRIPTION="${DESCRIPTION:0:$DESC_MAX}"
fi
if [[ -z "$CONTEXT" ]]; then
  echo "ci_github_status: --context must not be empty" >&2; exit 2
fi

# Opt-in: no credential / not enabled means "stay quiet", not "fail the build".
if [[ "${GITHUB_STATUS_ENABLED:-0}" != "1" ]]; then
  echo "ci_github_status: GITHUB_STATUS_ENABLED!=1 — skipping ${CONTEXT} for ${SHA}"
  exit 0
fi
if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "ci_github_status: GITHUB_TOKEN not set — skipping ${CONTEXT} for ${SHA}" >&2
  exit 0
fi

write_payload() {
  # Prefer python3 for correct JSON escaping; fall back to a conservative sed
  # path so a minimal agent image can still report ASCII-only descriptions.
  local out="$1"
  if command -v python3 >/dev/null 2>&1; then
    SHA="$SHA" STATE="$STATE" CONTEXT="$CONTEXT" DESCRIPTION="$DESCRIPTION" \
      TARGET_URL="$TARGET_URL" python3 - "$out" <<'PY'
import json
import os
import sys

payload = {
    "state": os.environ["STATE"],
    "context": os.environ["CONTEXT"],
    "description": os.environ["DESCRIPTION"],
}
url = os.environ.get("TARGET_URL") or ""
if url:
    payload["target_url"] = url

with open(sys.argv[1], "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False)
PY
    return
  fi
  local esc_desc esc_ctx esc_url
  esc_desc="$(printf '%s' "$DESCRIPTION" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/\t/ /g')"
  esc_ctx="$(printf '%s' "$CONTEXT" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')"
  esc_url="$(printf '%s' "$TARGET_URL" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')"
  printf '{"state":"%s","target_url":"%s","description":"%s","context":"%s"}' \
    "$STATE" "$esc_url" "$esc_desc" "$esc_ctx" > "$out"
}

payload_file="$(mktemp "${TMPDIR:-/tmp}/ci_gh_status.XXXXXX")"
response_file="$(mktemp "${TMPDIR:-/tmp}/ci_gh_resp.XXXXXX")"
trap 'rm -f "$payload_file" "$response_file"' EXIT

if ! write_payload "$payload_file"; then
  echo "ci_github_status: could not build JSON payload" >&2
  [[ "$STRICT" == "1" ]] && exit 1
  exit 0
fi

code="$(curl -s -o "$response_file" -w '%{http_code}' \
  --max-time "$TIMEOUT" \
  -X POST "https://api.github.com/repos/${REPO}/statuses/${SHA}" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  -H "User-Agent: dana-ci" \
  --data-binary "@${payload_file}" 2>/dev/null || echo 000)"

if [[ "$code" == "201" ]]; then
  echo "ci_github_status: reported ${STATE} for ${SHA} (${CONTEXT})"
  exit 0
fi

echo "ci_github_status: failed http=${code} context=${CONTEXT} — $(head -c 200 "$response_file" 2>/dev/null)" >&2
if [[ "$STRICT" == "1" ]]; then
  exit 1
fi
exit 0
