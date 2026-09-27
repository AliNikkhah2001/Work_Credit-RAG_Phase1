#!/usr/bin/env bash
# Work Credit RAG Phase 1 — Full Project Test Runner (Simple TUI)
# Runs comprehensive tests with progress bars, stats, and live TUI dashboard

set -euo pipefail

# ─── Colors & Styling ──────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'
MAGENTA='\033[0;35m'; CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

# ─── Config ────────────────────────────────────────────────────────
ROOT="/workspace/Work_Credit-RAG_Phase1"
cd "$ROOT"
START_TIME=$(date +%s)
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

# Test results array: name|status|details|duration
declare -a TEST_RESULTS=()

# ─── UI Helpers ────────────────────────────────────────────────────
draw_box() {
    local title="$1" width="${2:-70}"
    printf "${CYAN}┌%*s┐${NC}\n" "$((width-1))" | sed 's/ /─/g'
    printf "${CYAN}│${BOLD} %-*s ${CYAN}│${NC}\n" "$((width-4))" "$title"
    printf "${CYAN}└%*s┘${NC}\n" "$((width-1))" | sed 's/ /─/g'
}

progress_bar() {
    local current=$1 total=$2 width=40 label="$3"
    local pct=0 filled=0
    [[ $total -gt 0 ]] && pct=$((current * 100 / total))
    filled=$((pct * width / 100))
    local bar=$(printf "%${filled}s" | tr ' ' '#')
    local empty=$(printf "%$((width-filled))s" | tr ' ' '-')
    printf "\r${CYAN}[${GREEN}%s${CYAN}%s${CYAN}] ${BOLD}%3d%%${NC} %s" "$bar" "$empty" "$pct" "$label"
}

log_test() {
    local name="$1" status="$2" details="$3" duration="$4"
    TEST_RESULTS+=("$name|$status|$details|$duration")
    if [[ "$status" == "PASS" ]]; then
        ((PASSED_TESTS++))
    elif [[ "$status" == "FAIL" ]]; then
        ((FAILED_TESTS++))
    else
        ((SKIPPED_TESTS++))
    fi
    ((TOTAL_TESTS++))
}

run_test() {
    local name="$1" cmd="$2" timeout="${3:-30}"
    local start end dur output err=0
    start=$(date +%s)
    output=$(timeout "$timeout" bash -c "$cmd" 2>&1) || err=$?
    end=$(date +%s)
    dur=$((end-start))
    if [[ $err -eq 0 ]]; then
        log_test "$name" "PASS" "$output" "${dur}s"
    else
        log_test "$name" "FAIL" "$output" "${dur}s"
    fi
    # Clear progress bar line
    printf "\r\033[K"
}

# ─── Header ────────────────────────────────────────────────────────
echo -e "${BOLD}${MAGENTA}"
cat << 'EOF'
╔═══════════════════════════════════════════════════════════════════════════════╗
║        ██████╗ ███████╗███████╗███╗   ██╗    ██████╗ ███████╗██████╗       ║
║        ██╔══██╗██╔════╝██╔════╝████╗  ██║    ██╔══██╗██╔════╝██╔══██╗      ║
║        ██████╔╝█████╗  █████╗  ██╔██╗ ██║    ██████╔╝█████╗  ██████╔╝      ║
║        ██╔══██╗██╔═══╝ ██╔══╝  ██║╚██╗██║    ██╔══██╗██╔════╝██╔══██╗      ║
║        ██║  ██║███████╗███████╗██║ ╚████║    ██║  ██║███████╗██║  ██║      ║
║        ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═══╝    ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝      ║
║                                                                              ║
║           R A G   P H A S E  1  —  F U L L  S Y S T E M  T E S T           ║
╚══════════════════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"
echo -e "${DIM}Instance: Vast.ai 50713720 | GPU: RTX 3090 24GB | $(date)${NC}"
echo

# ─── Phase 1: Prerequisites ────────────────────────────────────────
draw_box "PHASE 1: PREREQUISITES & INFRASTRUCTURE" 70

PHASE1_TESTS=(
    "nvidia-smi|command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null"
    "CUDA Toolkit|command -v nvcc >/dev/null && nvcc --version 2>/dev/null | grep release"
    "cuDNN|ldconfig -p 2>/dev/null | grep -q libcudnn"
    "Python 3.11|python3.11 --version 2>/dev/null"
    "HF Cache /tmp/hf_clean|[[ -d /tmp/hf_clean ]] && du -sh /tmp/hf_clean 2>/dev/null"
    "Gemma GGUF|[[ -f /tmp/hf_clean/models--unsloth--gemma-4-31B-it-GGUF/snapshots/c1ac76e99d5513b141e8adde7288b85c3f9c32ec/gemma-4-31B-it-UD-Q4_K_XL.gguf ]] && echo OK"
    "llama-server binary|[[ -f /workspace/llama.cpp-src/build-cuda/bin/llama-server ]] && echo OK"
    "PostgreSQL|pg_isready -h 127.0.0.1 -U postgres -d kb_manager 2>/dev/null"
)

echo -e "${BOLD}Checking infrastructure...${NC}\n"
for i in "${!PHASE1_TESTS[@]}"; do
    IFS='|' read -r name cmd <<< "${PHASE1_TESTS[i]}"
    progress_bar $((i+1)) ${#PHASE1_TESTS[@]} "$name"
    run_test "$name" "$cmd" 10
done
echo; echo

# ─── Phase 2: Python Venvs ─────────────────────────────────────────
draw_box "PHASE 2: PYTHON ENVIRONMENTS" 70

declare -A VENVS=(
    ["/tmp/orch-venv"]="Orchestrator"
    ["/tmp/kb-venv"]="KB Manager"
    ["/tmp/guard-venv"]="Guardrails"
    ["/tmp/webui-venv"]="Open WebUI"
)

echo -e "${BOLD}Validating virtual environments...${NC}\n"
i=0
for venv in "${!VENVS[@]}"; do
    name="${VENVS[$venv]}"
    progress_bar $((++i)) ${#VENVS[@]} "$name"
    run_test "$name venv" "[[ -f $venv/bin/python ]] && $venv/bin/python -c 'import fastapi, uvicorn; print(f\"fastapi {fastapi.__version__}, uvicorn {uvicorn.__version__}\")' 2>/dev/null" 10
done
echo; echo

# ─── Phase 3: Port Binding ─────────────────────────────────────────
draw_box "PHASE 3: PORT BINDING & PROCESS VERIFICATION" 70

declare -A PORTS=(
    [18000]="Gemma (llama-server)"
    [8000]="KB Manager"
    [8200]="Guardrails"
    [8100]="Orchestrator"
    [13000]="Open WebUI"
    [3000]="Tracing Fallback"
    [3001]="Langfuse v2"
    [2024]="LangGraph Studio"
    [5432]="PostgreSQL"
)

echo -e "${BOLD}Verifying all service ports...${NC}\n"
i=0
for port in "${!PORTS[@]}"; do
    name="${PORTS[$port]}"
    progress_bar $((++i)) ${#PORTS[@]} "$name"
    run_test "Port $port" "ss -tlnp 2>/dev/null | grep -q \":$port \"" 5
done
echo; echo

# ─── Phase 4: Health Endpoints ─────────────────────────────────────
draw_box "PHASE 4: HEALTH ENDPOINTS" 70

declare -A HEALTH=(
    ["http://127.0.0.1:18000/health"]="Gemma"
    ["http://127.0.0.1:8000/health"]="KB Manager"
    ["http://127.0.0.1:8200/health"]="Guardrails"
    ["http://127.0.0.1:8100/health"]="Orchestrator"
    ["http://127.0.0.1:13000/health"]="Open WebUI"
    ["http://127.0.0.1:3000/health"]="Tracing Fallback"
    ["http://127.0.0.1:3001/api/public/health"]="Langfuse v2"
    ["http://127.0.0.1:2024/ok"]="LangGraph Studio"
)

echo -e "${BOLD}Testing all health endpoints...${NC}\n"
i=0
for url in "${!HEALTH[@]}"; do
    name="${HEALTH[$url]}"
    progress_bar $((++i)) ${#HEALTH[@]} "$name"
    run_test "$name health" "curl -sf --max-time 5 '$url' >/dev/null" 10
done
echo; echo

# ─── Phase 5: Functional Tests ─────────────────────────────────────
draw_box "PHASE 5: FUNCTIONAL TESTS (E2E)" 70

echo -e "${BOLD}Running functional tests...${NC}\n"

# 5.1 Gemma clean generation
progress_bar 1 7 "Gemma clean generation"
run_test "Gemma clean" 'curl -sf --max-time 30 "http://127.0.0.1:18000/v1/chat/completions" -H "Content-Type: application/json" -d '"'"'{"model":"unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL","messages":[{"role":"user","content":"سلام"}],"temperature":0,"max_tokens":20,"chat_template_kwargs":{"enable_thinking":false}}'"'"' | python3 -c "import sys,json; j=json.load(sys.stdin); c=j[\"choices\"][0][\"message\"][\"content\"]; assert \"<unused\" not in c; print(f\"OK: {c[:40]}\")" 2>/dev/null' 30

# 5.2 KB Search
progress_bar 2 7 "KB search"
run_test "KB search" 'curl -sf --max-time 15 "http://127.0.0.1:8000/search/api" -H "Content-Type: application/json" -d '"'"'{"query":"اعتبارسنجی چیست","top_k":3}'"'"' | python3 -c "import sys,json; j=json.load(sys.stdin); assert len(j.get(\"final_results\",[]))>0; print(f\"OK: {len(j[\"final_results\"])} results\")" 2>/dev/null' 15

# 5.3 Guardrails allowlist
progress_bar 3 7 "Guardrails allowlist"
run_test "Guardrails allowlist" 'curl -sf --max-time 5 "http://127.0.0.1:8200/v1/rails/check" -H "Content-Type: application/json" -d '"'"'{"stage":"input","text":"درخواست حذف سابقه منفی قدیمی","request_id":"t"}'"'"' | python3 -c "import sys,json; assert json.load(sys.stdin)[\"allowed\"]==True; print(\"OK: allowed\")" 2>/dev/null' 5

# 5.4 Guardrails block
progress_bar 4 7 "Guardrails block hate"
run_test "Guardrails block" 'curl -sf --max-time 5 "http://127.0.0.1:8200/v1/rails/check" -H "Content-Type: application/json" -d '"'"'{"stage":"output","text":"این فرد حرامزاده است","request_id":"t"}'"'"' | python3 -c "import sys,json; assert json.load(sys.stdin)[\"allowed\"]==False; print(\"OK: blocked\")" 2>/dev/null' 5

# 5.5 E2E RAG
progress_bar 5 7 "E2E RAG request"
RID="tui-test-$(date +%s)"
run_test "E2E RAG" "curl -sf --max-time 60 'http://127.0.0.1:8100/v1/chat/completions' -H 'Content-Type: application/json' -H 'X-Request-ID: $RID' -d '{\"model\":\"gemma-4-31b\",\"messages\":[{\"role\":\"user\",\"content\":\"اعتبارسنجی چیست؟\"}],\"temperature\":0,\"max_tokens\":200}' | python3 -c 'import sys,json; j=json.load(sys.stdin); assert j[\"choices\"][0][\"finish_reason\"]==\"stop\"; c=len(j.get(\"rag\",{}).get(\"citations\",[])); assert c>0; print(f\"OK: finish=stop, citations={c}\")" 2>/dev/null" 60

# 5.6 Langfuse traces
progress_bar 6 7 "Langfuse traces"
run_test "Langfuse traces" 'curl -sf --max-time 5 -u "pk-lf-seeded-public-001:sk-lf-seeded-secret-001" "http://127.0.0.1:3001/api/public/traces?limit=1" | python3 -c "import sys,json; d=json.load(sys.stdin); total=d.get(\"meta\",{}).get(\"totalItems\",0); assert total>0; print(f\"OK: {total} traces\")" 2>/dev/null' 10

# 5.7 Observe UI
progress_bar 7 7 "Observe UI"
run_test "Observe UI" 'curl -sf --max-time 5 "http://127.0.0.1:3000/api/observe/requests?limit=1" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d.get(\"data\"),list); print(f\"OK: {len(d[\"data\"])} requests\")" 2>/dev/null' 5

echo; echo

# ─── Phase 6: Observability & Tracing ──────────────────────────────
draw_box "PHASE 6: OBSERVABILITY & TRACING" 70

echo -e "${BOLD}Checking tracing stack...${NC}\n"

run_test "Fallback JSONL" "[[ -f /tmp/langfuse_traces.jsonl ]] && wc -l /tmp/langfuse_traces.jsonl 2>/dev/null" 5
run_test "Observe /observe" 'curl -sf --max-time 5 "http://127.0.0.1:3000/observe" | grep -q "RAG Observer" 2>/dev/null' 5
run_test "Studio UI" 'curl -sf --max-time 5 "http://127.0.0.1:3000/studio" | grep -q "Local Studio" 2>/dev/null' 5
run_test "Studio API" 'curl -sf --max-time 5 "http://127.0.0.1:2024/ok" | grep -q "ok" 2>/dev/null' 5

echo; echo

# ─── Summary Dashboard ─────────────────────────────────────────────
END_TIME=$(date +%s)
TOTAL_DUR=$((END_TIME - START_TIME))

draw_box "TEST SUMMARY DASHBOARD" 80

echo -e "${BOLD}════════════════════════════════════════════════════════════════════════${NC}"
printf "${BOLD}%-30s${NC} ${GREEN}%4d${NC}  ${RED}%4d${NC}  ${YELLOW}%4d${NC}  ${CYAN}%4d${NC}\n" "Results:" "$PASSED_TESTS" "$FAILED_TESTS" "$SKIPPED_TESTS" "$TOTAL_TESTS"
printf "${BOLD}%-30s${NC} %ds\n" "Total Duration:" "$TOTAL_DUR"
printf "${BOLD}%-30s${NC} %s\n" "Timestamp:" "$(date)"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════════════${NC}\n"

# Detailed results table
printf "${BOLD}%-3s │ %-28s │ %-6s │ %-8s │ %s${NC}\n" "#" "TEST NAME" "STATUS" "DURATION" "DETAILS"
echo -e "${DIM}────┼────────────────────────────┼────────┼──────────┼────────────────────────────────────────${NC}"

idx=0
for result in "${TEST_RESULTS[@]}"; do
    ((idx++))
    IFS='|' read -r name status details duration <<< "$result"
    details_short="${details:0:50}"
    [[ ${#details} -gt 50 ]] && details_short+="…"
    case "$status" in
        PASS) status_col="${GREEN}PASS${NC}" ;;
        FAIL) status_col="${RED}FAIL${NC}" ;;
        *)    status_col="${YELLOW}SKIP${NC}" ;;
    esac
    printf "%3d │ %-28.28s │ %-6b │ %8s │ %s\n" "$idx" "$name" "$status_col" "$duration" "$details_short"
done

echo

# Failed details
if [[ $FAILED_TESTS -gt 0 ]]; then
    echo -e "${RED}${BOLD}FAILED TESTS DETAIL:${NC}"
    for result in "${TEST_RESULTS[@]}"; do
        IFS='|' read -r name status details duration <<< "$result"
        [[ "$status" == "FAIL" ]] && echo -e "  ${RED}▸ $name${NC}: $details"
    done
    echo
fi

# ─── Access Info ───────────────────────────────────────────────────
draw_box "ACCESS URLS (via SSH tunnel)" 70
cat << 'EOF'
Run locally:
  ssh -p <ssh_port> root@<ssh_host> \
    -L 13000:localhost:13000 -L 8100:localhost:8100 \
    -L 3000:localhost:3000 -L 3001:localhost:3001 -L 2024:localhost:2024

Then open:
  🌐 WebUI:        http://localhost:13000
  🔧 Orchestrator: http://localhost:8100
  📊 Observe:      http://localhost:3000/observe
  🔍 Studio:       http://localhost:3000/studio
  📈 Langfuse:     http://localhost:3001 (admin@local.test / Langfuse-Admin-139b81ba)
  🎯 Smith Studio: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
EOF

echo
if [[ $FAILED_TESTS -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}✓ ALL TESTS PASSED — SYSTEM READY${NC}"
    exit 0
else
    echo -e "${RED}${BOLD}✗ $FAILED_TESTS TEST(S) FAILED — REVIEW ABOVE${NC}"
    exit 1
fi