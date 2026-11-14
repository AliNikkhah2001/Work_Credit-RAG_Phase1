#!/usr/bin/env bash
# =============================================================================
# scripts/test_openwebui_api.sh — end-to-end API test against OpenWebUI
#
# Verifies the full chain: signin -> model list -> chat completion -> RAG
# citations, using only curl + python3. Works identically on the laptop
# (127.0.0.1:13000), the stage stack (13100), or the GPU production host.
#
# Usage:
#   bash scripts/test_openwebui_api.sh
#   bash scripts/test_openwebui_api.sh --url http://127.0.0.1:13100
#   bash scripts/test_openwebui_api.sh --url https://chat.ics24.ir \
#        --email admin@localhost --password admin
#   bash scripts/test_openwebui_api.sh --question "طرح کفیل چیه؟" --json
#
# Exit codes: 0 all checks passed, 1 a check failed, 2 usage/connection error.
#
# NOTE ON PATHS (learned the hard way):
#   OpenWebUI serves its own API under /api/... . The bare /v1 prefix collides
#   with the SPA, so /v1/models returns HTML, not JSON. Use /api/v1/models and
#   /api/v1/chat/completions for the OpenAI-compatible surface, and
#   /api/chat/completions for the full RAG pipeline surface (returns `rag`).
# =============================================================================
set -uo pipefail

BASE_URL="${WEBUI_URL:-http://127.0.0.1:13000}"
EMAIL="${WEBUI_EMAIL:-admin@localhost}"
PASSWORD="${WEBUI_PASSWORD:-admin}"
MODEL="${WEBUI_MODEL:-ics-helper-agent}"
QUESTION="${WEBUI_QUESTION:-اعتبارسنجی چیست؟}"
JSON_OUT=0
TIMEOUT=180

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)       BASE_URL="$2"; shift 2 ;;
    --email)     EMAIL="$2"; shift 2 ;;
    --password)  PASSWORD="$2"; shift 2 ;;
    --model)     MODEL="$2"; shift 2 ;;
    --question)  QUESTION="$2"; shift 2 ;;
    --timeout)   TIMEOUT="$2"; shift 2 ;;
    --json)      JSON_OUT=1; shift ;;
    -h|--help)   sed -n '2,26p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

BASE_URL="${BASE_URL%/}"
C_OK=$'\033[32m'; C_BAD=$'\033[31m'; C_WARN=$'\033[33m'; C_OFF=$'\033[0m'
FAIL=0
declare -a RESULTS=()

pass() { RESULTS+=("PASS|$1|${2:-}"); printf '%s  PASS%s  %s %s\n' "$C_OK" "$C_OFF" "$1" "${2:-}"; }
fail() { RESULTS+=("FAIL|$1|${2:-}"); FAIL=1;       printf '%s  FAIL%s  %s %s\n' "$C_BAD" "$C_OFF" "$1" "${2:-}"; }

json_field() {  # json_field <python-expr over d>
  python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
except Exception as e:
    print(''); sys.exit(0)
print($1)
" 2>/dev/null
}

printf '=== OpenWebUI API end-to-end test ===\n'
printf '  url      : %s\n' "$BASE_URL"
printf '  email    : %s\n' "$EMAIL"
printf '  model    : %s\n' "$MODEL"
printf '  question : %s\n\n' "$QUESTION"

# --- 0. reachability ---------------------------------------------------------
code="$(curl -s -m 10 -o /dev/null -w '%{http_code}' "$BASE_URL/health" 2>/dev/null)"
if [[ "$code" == "200" ]]; then
  pass "reachable: $BASE_URL/health" "-> 200"
elif [[ "$code" == "000" ]]; then
  fail "unreachable: $BASE_URL" "no TCP/HTTP response (DNS? firewall? port not published?)"
  printf '\n%sAborting: the host is not reachable, later checks would only mislead.%s\n' "$C_WARN" "$C_OFF"
  exit 2
else
  # Some deployments do not implement /health but still serve the API.
  printf '%s  WARN%s  /health -> %s (continuing)\n' "$C_WARN" "$C_OFF" "$code"
fi

# --- 1. signin ---------------------------------------------------------------
SIGNIN_BODY="$(curl -s -m 25 -X POST "$BASE_URL/api/v1/auths/signin" \
  -H 'Content-Type: application/json' \
  -d "$(printf '{"email":"%s","password":"%s"}' "$EMAIL" "$PASSWORD")" 2>/dev/null)"
TOKEN="$(printf '%s' "$SIGNIN_BODY" | json_field 'd.get("token","")')"
if [[ -n "$TOKEN" ]]; then
  pass "signin" "token ${#TOKEN} chars"
else
  fail "signin" "$(printf '%s' "$SIGNIN_BODY" | head -c 160)"
  printf '\n%sCannot proceed without a token.%s\n' "$C_BAD" "$C_OFF"
  exit 1
fi

AUTH=(-H "Authorization: Bearer $TOKEN")

# --- 2. model listing --------------------------------------------------------
MODELS_JSON="$(curl -s -m 20 "$BASE_URL/api/v1/models" "${AUTH[@]}" 2>/dev/null)"
MODEL_IDS="$(printf '%s' "$MODELS_JSON" | json_field '",".join(m.get("id","") for m in (d.get("data") or []))')"
if [[ -n "$MODEL_IDS" ]]; then
  pass "model list" "$MODEL_IDS"
else
  fail "model list" "$(printf '%s' "$MODELS_JSON" | head -c 160)"
fi

if [[ -n "$MODEL_IDS" && ",$MODEL_IDS," != *",$MODEL,"* ]]; then
  fail "model '$MODEL' is served" "available: $MODEL_IDS"
else
  pass "model '$MODEL' is served"
fi

# --- 3. auth is actually enforced -------------------------------------------
code="$(curl -s -m 15 -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/api/chat/completions" \
  -H 'Content-Type: application/json' \
  -d "$(printf '{"model":"%s","messages":[{"role":"user","content":"x"}]}' "$MODEL")" 2>/dev/null)"
if [[ "$code" == "401" || "$code" == "403" ]]; then
  pass "unauthenticated request is rejected" "-> $code"
else
  printf '%s  WARN%s  unauthenticated chat -> %s (expected 401/403)\n' "$C_WARN" "$C_OFF" "$code"
fi

# --- 4. RAG chat completion (full pipeline) ---------------------------------
START=$(date +%s)
CHAT_JSON="$(curl -s -m "$TIMEOUT" -X POST "$BASE_URL/api/chat/completions" \
  -H 'Content-Type: application/json' "${AUTH[@]}" \
  -d "$(python3 -c '
import json,sys
print(json.dumps({"model":sys.argv[1],"stream":False,
                  "messages":[{"role":"user","content":sys.argv[2]}]}, ensure_ascii=False))
' "$MODEL" "$QUESTION")" 2>/dev/null)"
ELAPSED=$(( $(date +%s) - START ))

FINISH="$(printf '%s' "$CHAT_JSON" | json_field 'd["choices"][0].get("finish_reason")')"
CONTENT="$(printf '%s' "$CHAT_JSON" | json_field 'd["choices"][0]["message"]["content"]')"
NCITES="$(printf '%s' "$CHAT_JSON" | json_field 'len((d.get("rag") or {}).get("citations") or [])')"

if [[ -n "$FINISH" && "$FINISH" != "content_filter" ]]; then
  pass "chat completion" "finish=$FINISH, ${#CONTENT} chars, ${ELAPSED}s"
else
  fail "chat completion" "finish=${FINISH:-<none>} (content_filter means a rail blocked the answer)"
fi

if [[ "${NCITES:-0}" -gt 0 ]] 2>/dev/null; then
  pass "RAG citations" "$NCITES"
else
  printf '%s  WARN%s  RAG citations -> %s (retrieval returned nothing?)\n' "$C_WARN" "$C_OFF" "${NCITES:-0}"
fi

# --- output ------------------------------------------------------------------
if [[ "$JSON_OUT" -eq 1 ]]; then
  printf '\n=== answer ===\n%s\n' "$CONTENT"
elif [[ -n "$CONTENT" ]]; then
  printf '\n=== answer (first 400 chars) ===\n%s\n' "$(printf '%s' "$CONTENT" | head -c 400)"
fi

printf '\n=== summary ===\n'
for r in "${RESULTS[@]}"; do
  IFS='|' read -r st name detail <<<"$r"
  [[ "$st" == "FAIL" ]] && printf '  %sFAIL%s %s %s\n' "$C_BAD" "$C_OFF" "$name" "$detail"
done
if [[ "$FAIL" -eq 0 ]]; then
  printf '  %sALL CHECKS PASSED%s\n' "$C_OK" "$C_OFF"
else
  printf '  %sFAILURES PRESENT%s\n' "$C_BAD" "$C_OFF"
fi
exit "$FAIL"
