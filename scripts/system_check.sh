#!/usr/bin/env bash
# System Check & Verification Script — Work Credit RAG Phase 1
# Checks: drivers, CUDA, venvs, services, ports, LLM manager, IP exposure, health endpoints
# Run: bash scripts/system_check.sh [--fix] [--verbose]

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

FIX_MODE=false
VERBOSE=false
for arg in "$@"; do
    case $arg in
        --fix) FIX_MODE=true ;;
        --verbose) VERBOSE=true ;;
    esac
done

log() { echo -e "${BLUE}[INFO]${NC} $*"; }
ok() { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; }

ROOT="/workspace/Work_Credit-RAG_Phase1"
cd "$ROOT"

echo "=========================================="
echo "Work Credit RAG Phase 1 — System Check"
echo "=========================================="
date
echo

# ──────────────────────────────────────────────
# 1. HARDWARE & DRIVERS
# ──────────────────────────────────────────────
log "1. Hardware & NVIDIA Drivers"
echo "------------------------------"

if command -v nvidia-smi >/dev/null; then
    ok "nvidia-smi found"
    nvidia-smi --query-gpu=index,name,memory.total,memory.used,driver_version --format=csv,noheader | while IFS=',' read -r idx name mem_total mem_used driver; do
        ok "GPU $idx: $name | VRAM: $mem_used / $mem_total | Driver: $driver"
    done
    CUDA_VERSION=$(nvidia-smi | grep "CUDA Version" | sed 's/.*CUDA Version: \([0-9.]*\).*/\1/')
    ok "CUDA Runtime: $CUDA_VERSION"
else
    fail "nvidia-smi NOT found — install NVIDIA drivers"
    if $FIX_MODE; then
        log "Attempting driver install (requires sudo)..."
        # This would need proper repo setup
        warn "Manual install required: https://docs.nvidia.com/datacenter/tesla/tesla-installation-notes/index.html"
    fi
fi

# ──────────────────────────────────────────────
# 2. CUDA TOOLKIT & LIBRARIES
# ──────────────────────────────────────────────
log ""
log "2. CUDA Toolkit & Libraries"
echo "------------------------------"

if command -v nvcc >/dev/null; then
    NVCC_VER=$(nvcc --version | grep "release" | sed 's/.*release \([0-9.]*\).*/\1/')
    ok "nvcc found: $NVCC_VER"
else
    warn "nvcc not in PATH (CUDA toolkit may not be installed)"
fi

# Check key libraries
for lib in libcudart.so libcublas.so libcufft.so libcurand.so; do
    if ldconfig -p | grep -q "$lib"; then
        ok "Library $lib: found"
    else
        warn "Library $lib: NOT found"
    fi
done

# ──────────────────────────────────────────────
# 3. PYTHON VENVS
# ──────────────────────────────────────────────
log ""
log "3. Python Virtual Environments"
echo "------------------------------"

declare -A VENVS=(
    ["/tmp/orch-venv"]="Orchestrator (py3.11)"
    ["/tmp/kb-venv"]="KB Manager (py3.11)"
    ["/tmp/guard-venv"]="Guardrails (py3.11)"
    ["/tmp/webui-venv"]="Open WebUI"
)

for venv in "${!VENVS[@]}"; do
    if [[ -f "$venv/bin/python" ]]; then
        PY_VER=$("$venv/bin/python" --version 2>&1)
        ok "${VENVS[$venv]}: $PY_VER at $venv"
        if $VERBOSE; then
            "$venv/bin/python" -m pip list 2>/dev/null | grep -E "torch|llama|fastapi|uvicorn|sentence" | head -5 | while read line; do
                echo "    $line"
            done
        fi
    else
        fail "${VENVS[$venv]}: MISSING at $venv"
        if $FIX_MODE; then
            log "Creating $venv..."
            python3 -m venv "$venv"
            "$venv/bin/python" -m pip install --upgrade pip
        fi
    fi
done

# ──────────────────────────────────────────────
# 4. HF CACHE
# ──────────────────────────────────────────────
log ""
log "4. HuggingFace Cache"
echo "------------------------------"

if [[ -d "/tmp/hf_clean" ]]; then
    ok "HF cache dir exists: /tmp/hf_clean"
    GEMMA_PATH="/tmp/hf_clean/models--unsloth--gemma-4-31B-it-GGUF/snapshots/c1ac76e99d5513b141e8adde7288b85c3f9c32ec/gemma-4-31B-it-UD-Q4_K_XL.gguf"
    if [[ -f "$GEMMA_PATH" ]]; then
        SIZE=$(du -h "$GEMMA_PATH" | cut -f1)
        ok "Gemma GGUF found: $SIZE"
    else
        fail "Gemma GGUF NOT found at expected path"
    fi
else
    fail "HF cache dir MISSING: /tmp/hf_clean"
fi

# ──────────────────────────────────────────────
# 5. RUNNING SERVICES & PORTS
# ──────────────────────────────────────────────
log ""
log "5. Running Services & Port Exposure"
echo "------------------------------"

# Expected services (Vast production ports)
declare -A SERVICES=(
    [18000]="Gemma (llama-server, 127.0.0.1 only)"
    [8000]="KB Manager (0.0.0.0)"
    [8200]="Guardrails (0.0.0.0)"
    [8100]="Orchestrator (0.0.0.0)"
    [13000]="Open WebUI (0.0.0.0)"
    [3000]="Tracing Fallback (0.0.0.0)"
    [3001]="Langfuse v2 (0.0.0.0)"
    [2024]="LangGraph Studio (0.0.0.0)"
    [5432]="PostgreSQL (127.0.0.1)"
)

for port in "${!SERVICES[@]}"; do
    if ss -tlnp 2>/dev/null | grep -q ":$port "; then
        PROC=$(ss -tlnp 2>/dev/null | grep ":$port " | awk '{print $NF}' | head -1)
        ok "Port $port: LISTEN (${SERVICES[$port]}) — $PROC"
        # Check bind address
        BIND=$(ss -tlnp 2>/dev/null | grep ":$port " | awk '{print $4}')
        if [[ "$BIND" == "127.0.0.1:$port" ]]; then
            ok "  → Bound to LOOPBACK only (secure)"
        elif [[ "$BIND" == "0.0.0.0:$port" ]]; then
            ok "  → Bound to ALL INTERFACES (public)"
        fi
    else
        warn "Port $port: NOT LISTENING (${SERVICES[$port]})"
    fi
done

# Check for unexpected public ports
log ""
log "Checking for unexpected public ports..."
UNEXPECTED=$(ss -tlnp 2>/dev/null | awk '$4 ~ /^0\.0\.0\.0:/ && $4 !~ /:(13000|8100|8200|8000|3000|3001|2024)$/ {print $4}' | sort -u)
if [[ -n "$UNEXPECTED" ]]; then
    warn "Unexpected public ports:"
    echo "$UNEXPECTED" | while read p; do warn "  $p"; done
else
    ok "No unexpected public ports"
fi

# ──────────────────────────────────────────────
# 6. HEALTH ENDPOINTS
# ──────────────────────────────────────────────
log ""
log "6. Health Endpoints"
echo "------------------------------"

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

for url in "${!HEALTH[@]}"; do
    if curl -s --max-time 5 "$url" >/dev/null 2>&1; then
        RESP=$(curl -s --max-time 5 "$url" | head -c 100)
        ok "${HEALTH[$url]}: $url → $RESP"
    else
        warn "${HEALTH[$url]}: $url → UNREACHABLE"
    fi
done

# ──────────────────────────────────────────────
# 7. LLM MANAGER (server-setup)
# ──────────────────────────────────────────────
log ""
log "7. LLM Inference Manager (server-setup)"
echo "------------------------------"

MANAGER_DIR="$ROOT/components/server-setup/llm_inference_manager"
if [[ -f "$MANAGER_DIR/app.py" ]]; then
    ok "Manager code found: $MANAGER_DIR/app.py"
    
    # Check if manager is running on :9000
    if ss -tlnp 2>/dev/null | grep -q ":9000 "; then
        ok "Manager running on :9000"
        if curl -s --max-time 5 "http://127.0.0.1:9000/health" >/dev/null; then
            HEALTH_JSON=$(curl -s "http://127.0.0.1:9000/health")
            ok "Manager health: $HEALTH_JSON"
            
            # Get loaded models
            MODELS_JSON=$(curl -s "http://127.0.0.1:9000/v1/models" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); [print('  - ' + m['id'] + ' (' + m['meta']['status'] + ')') for m in d['data']]" 2>/dev/null || echo "  (parse failed)")
            echo "Loaded models:"
            echo "$MODELS_JSON"
        else
            warn "Manager on :9000 not responding to /health"
        fi
    else
        warn "Manager NOT running on :9000 (this is the H200 stack manager, not used in Vast MVP)"
        log "Vast MVP uses Gemma directly on :18000, not via manager"
    fi
    
    # Check registry models exist on disk
    log "Checking registered model files..."
    python3 -c "
import json, sys
sys.path.insert(0, '$MANAGER_DIR')
from app import MODEL_REGISTRY
import os
for mid, m in MODEL_REGISTRY.items():
    path = os.path.join('$ROOT/components/server-setup', m['path'])
    status = 'FOUND' if os.path.exists(path) else 'MISSING'
    print(f'  {mid}: {status} ({m[\"size_gb\"]}GB, {m[\"quant\"]})')
" 2>/dev/null || warn "Could not check model files (run from server-setup dir)"
else
    warn "Manager code NOT found at $MANAGER_DIR"
fi

# ──────────────────────────────────────────────
# 8. GEMMA DIRECT (Vast MVP path)
# ──────────────────────────────────────────────
log ""
log "8. Gemma Direct (Vast MVP :18000)"
echo "------------------------------"

if curl -s --max-time 5 "http://127.0.0.1:18000/v1/models" >/dev/null; then
    MODEL_ID=$(curl -s "http://127.0.0.1:18000/v1/models" | python3 -c "import sys,json; print(json.load(sys.stdin)['data'][0]['id'])")
    ok "Gemma model: $MODEL_ID"
    
    # Test generation with enable_thinking:false
    TEST=$(curl -s --max-time 30 "http://127.0.0.1:18000/v1/chat/completions" \
        -H 'Content-Type: application/json' \
        -d '{"model":"'"$MODEL_ID"'","messages":[{"role":"user","content":"سلام"}],"temperature":0,"max_tokens":20,"chat_template_kwargs":{"enable_thinking":false}}' \
        | python3 -c "import sys,json; j=json.load(sys.stdin); c=j['choices'][0]['message']['content']; print('has_unused:', '<unused' in c, 'len:', len(c), 'preview:', c[:40])")
    ok "Generation test: $TEST"
else
    fail "Gemma NOT reachable on :18000"
fi

# ──────────────────────────────────────────────
# 9. E2E RAG TEST
# ──────────────────────────────────────────────
log ""
log "9. End-to-End RAG Test"
echo "------------------------------"

RID="syscheck-$(date +%s)"
RAG_TEST=$(curl -s --max-time 60 "http://127.0.0.1:8100/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -H "X-Request-ID: $RID" \
    -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"اعتبارسنجی چیست؟"}],"temperature":0,"max_tokens":200}' \
    | python3 -c "
import sys,json
j=json.load(sys.stdin)
finish=j['choices'][0]['finish_reason']
citations=len(j.get('rag',{}).get('citations',[]))
content=j['choices'][0]['message']['content'][:80]
print(f'finish={finish} citations={citations} preview={content}')
" 2>/dev/null || echo "FAILED")

if [[ "$RAG_TEST" == *"finish=stop"* ]]; then
    ok "E2E RAG: $RAG_TEST"
else
    fail "E2E RAG failed: $RAG_TEST"
fi

# ──────────────────────────────────────────────
# 10. GUARDRAILS TEST
# ──────────────────────────────────────────────
log ""
log "10. Guardrails Quick Test"
echo "------------------------------"

# Input allowed (HurtLex allowlist)
ALLOWED=$(curl -s --max-time 5 "http://127.0.0.1:8200/v1/rails/check" \
    -H 'Content-Type: application/json' \
    -d '{"stage":"input","text":"درخواست حذف سابقه منفی قدیمی","request_id":"t"}' \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('allowed','?'))" 2>/dev/null)

# Output blocked (true hate)
BLOCKED=$(curl -s --max-time 5 "http://127.0.0.1:8200/v1/rails/check" \
    -H 'Content-Type: application/json' \
    -d '{"stage":"output","text":"این فرد حرامزاده است","request_id":"t"}' \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('allowed','?'))" 2>/dev/null)

if [[ "$ALLOWED" == "True" && "$BLOCKED" == "False" ]]; then
    ok "Guardrails: allowlist works (allowed=$ALLOWED, blocked=$BLOCKED)"
else
    warn "Guardrails unexpected: allowed=$ALLOWED, blocked=$BLOCKED"
fi

# ──────────────────────────────────────────────
# 11. OBSERVABILITY
# ──────────────────────────────────────────────
log ""
log "11. Observability Stack"
echo "------------------------------"

# Langfuse v2 traces
TRACES=$(curl -s --max-time 5 -u "pk-lf-seeded-public-001:sk-lf-seeded-secret-001" \
    "http://127.0.0.1:3001/api/public/traces?limit=1" 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('meta',{}).get('totalItems',0))" 2>/dev/null || echo "0")
ok "Langfuse v2 traces: $TRACES total"

# Tracing fallback
FALLBACK_LINES=$(wc -l < /tmp/langfuse_traces.jsonl 2>/dev/null || echo 0)
ok "Fallback collector lines: $FALLBACK_LINES"

# Local observe
if curl -s --max-time 5 "http://127.0.0.1:3000/api/observe/requests?limit=1" >/dev/null; then
    ok "Local Observe UI: http://127.0.0.1:3000/observe"
else
    warn "Local Observe UI not responding"
fi

# ──────────────────────────────────────────────
# 12. SSH TUNNEL GUIDANCE
# ──────────────────────────────────────────────
log ""
log "12. SSH Tunnel Required for External Access"
echo "------------------------------"
echo "Run on YOUR LOCAL MACHINE:"
SSH_PORT=$(grep -oP 'ssh_port.*?\K\d+' /workspace/Work_Credit-RAG_Phase1/deploy/vast/start.sh 2>/dev/null || echo "<ssh_port>")
SSH_HOST=$(grep -oP 'ssh_host.*?\K\S+' /workspace/Work_Credit-RAG_Phase1/deploy/vast/start.sh 2>/dev/null || echo "<ssh_host>")
cat << EOF
ssh -p $SSH_PORT root@$SSH_HOST \\
  -L 13000:localhost:13000 \\
  -L 8100:localhost:8100 \\
  -L 3000:localhost:3000 \\
  -L 3001:localhost:3001 \\
  -L 2024:localhost:2024

Then open:
  • WebUI:        http://localhost:13000
  • Orchestrator: http://localhost:8100
  • Observe:      http://localhost:3000/observe
  • Studio:       http://localhost:3000/studio
  • Langfuse:     http://localhost:3001 (admin@local.test / Langfuse-Admin-139b81ba)
  • Smith Studio: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
EOF

# ──────────────────────────────────────────────
# 13. MACHINE & DEPLOYMENT OPTIONS SUMMARY
# ──────────────────────────────────────────────
log ""
log "13. Deployment Machine Summary"
echo "------------------------------"

cat << 'EOF'
┌─────────────────────────────────────────────────────────────────────────────┐
│ CURRENT MACHINE (this Vast instance)                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ Instance: 50713720 (ssh9.vast.ai:24044)                                     │
│ GPU: 1× RTX 3090 24GB (22.7GB used at ctx 8192)                             │
│ CPU: EPYC 7443 (96 core)                                                    │
│ RAM: 503 GiB                                                                │
│ Disk: 100 GiB                                                               │
│ OS: Linux, unprivileged container (NO Docker)                               │
│ Deployment: Host venvs only (bash deploy/vast/start.sh)                     │
│                                                                             │
│ Services running HERE:                                                      │
│   • Gemma :18000 (llama-server, GGUF, --no-mmproj --jinja)                 │
│   • KB :8000 (pgvector HNSW, 6593 chunks)                                  │
│   • Guardrails :8200 (deterministic Persian + risk + semantic)             │
│   • Orchestrator :8100 (LangGraph, 5 nodes)                                │
│   • WebUI :13000 (Open WebUI)                                               │
│   • Langfuse v2 :3001 (Postgres-backed, real UI)                           │
│   • Tracing Fallback :3000 (JSONL + Observe UI + Studio UI)                │
│   • Studio API :2024 (LangGraph API for Smith panel)                       │
│   • PostgreSQL :5432 (kb_manager + langfuse DBs)                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ H200 MACHINE (server-setup repo) — SEPARATE PHYSICAL BOX                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ Hostname: ai-gpu1                                                           │
│ GPUs: 2× H200 NVL 143GB each (281 GiB total)                               │
│ VRAM: ~240GB free (runs 5× Gemma + Qwen + embeddings simultaneously)       │
│ Deployment: Docker Compose (9 containers) + Host venvs                     │
│                                                                             │
│ Services on H200:                                                           │
│   • LLM Manager :9000 (OpenAI gateway, 11 models registered)               │
│   • 5× Gemma-4-31B :8080-8084 (GPU split 3/2)                             │
│   • Qwen2.5-7B :8090                                                        │
│   • Embeddings :8001 (e5-small), :8002 (bge-m3), :8003 (MiniLM)            │
│   • Milvus :19530, pgvector :15432, Qdrant :16333, Redis :16379            │
│   • Open WebUI :13000 (via Docker)                                          │
│   • Monitoring: Grafana :13001, Prometheus :19090, OTEL :14317             │
│                                                                             │
│ Manager tracks: models, sessions, messages, metrics in SQLite              │
│ Repo: components/server-setup (git submodule, main branch)                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ DOCKER OPTION (Privileged Host Required)                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ Use: deploy/docker/docker-compose.yml                                       │
│ Prereqs: Docker Engine + NVIDIA Container Toolkit                          │
│ Exposes: ONLY 13000 by default (others via docker-compose.override.yml)    │
│ Services containerized: llama-server, postgres, kb, guardrails,            │
│   orchestrator, langfuse stack, tracing-fallback, webui                    │
│ NOT for this Vast instance (unprivileged)                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ MODEL OPTIONS AVAILABLE                                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│ Current (Vast): unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL (18.8GB, 0.663)    │
│                                                                             │
│ On H200 (via Manager :9000):                                               │
│   Loaded:  gemma-4-31b (5× :8080-8084), qwen2.5-7b (:8090)                │
│   Available (on disk): gemma-3-27b, qwen3.8-27b, qwen3-30b-a3b,           │
│     nemotron-49b, llama-3.2-3b, mistral-7b, phi-3-mini, deepseek-v4-flash, │
│     qwen2.5-72b (partial)                                                  │
│                                                                             │
│ Embedding models (H200 :8001-8003):                                        │
│   multilingual-e5-small (384), bge-m3 (1024), paraphrase-multilingual-     │
│   MiniLM-L12-v2 (384), bge-small-en-v1.5 (384), all-MiniLM-L6-v2 (384)    │
│                                                                             │
│ Reranker candidates (KB shootout running):                                 │
│   mmarco-mMiniLMv2 (118M, baseline), bge-reranker-v2-m3 (568M),           │
│   jina-reranker-v3 (0.6B), Qwen3-Reranker-0.6B/4B, bge-reranker-v2-gemma  │
│   (2.5B), minicpm-layerwise (blocked), gte-multilingual (blocked)          │
└─────────────────────────────────────────────────────────────────────────────┘
EOF

echo ""
echo "=========================================="
echo "System Check Complete"
echo "=========================================="