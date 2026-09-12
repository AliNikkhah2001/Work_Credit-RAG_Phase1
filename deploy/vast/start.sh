#!/bin/bash
# Vast.ai deployment startup — Work Credit RAG Phase 1 (unprivileged host, no Docker).
# Services run in host venvs. Tested on instance 50713720 (1x RTX 3090 24GB).
# Adjust MODEL path / ports as needed. All logs go to /tmp/*.log.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MODEL="${MODEL:-/tmp/hf_clean/models--unsloth--gemma-4-31B-it-GGUF/snapshots/c1ac76e99d5513b141e8adde7288b85c3f9c32ec/gemma-4-31B-it-UD-Q4_K_XL.gguf}"
LLAMA_SERVER="${LLAMA_SERVER:-/workspace/llama.cpp-src/build-cuda/bin/llama-server}"
KB_DB_URL="${KB_DB_URL:-postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/kb_manager}"
export HF_HOME="${HF_HOME:-/tmp/hf_clean}" HF_HUB_CACHE="${HF_HUB_CACHE:-/tmp/hf_clean}" HF_HUB_OFFLINE=1

echo "== 0. postgres (expects cluster running with kb_manager DB + vector ext) =="
pg_lsclusters || pg_ctlcluster 14 main start

echo "== 1. Gemma 4 :18000 =="
nohup "$LLAMA_SERVER" --model "$MODEL" --port 18000 --ctx-size 8192 \
  --temp 0.2 --no-mmproj --jinja -ngl 999 > /tmp/llama-server.log 2>&1 &
sleep 45
curl -s http://127.0.0.1:18000/health || { echo "gemma failed"; exit 1; }

echo "== 2. KB :8000 (pgvector) =="
cd "$ROOT/components/knowledgebase/kb-manager"
KB_DB_URL="$KB_DB_URL" KB_WEB_HOST=0.0.0.0 KB_WEB_PORT=8000 \
  nohup /tmp/kb-venv/bin/python -m uvicorn kb_manager.web.app:app \
  --host 0.0.0.0 --port 8000 > /tmp/kb.log 2>&1 &
sleep 20

echo "== 3. Guardrails :8200 =="
cd "$ROOT"
PYTHONPATH="$ROOT/components/guardrails/src" GUARDRAILS_HOST=0.0.0.0 GUARDRAILS_PORT=8200 \
  UPSTREAM_LLM_BASE_URL=http://127.0.0.1:18000/v1 \
  UPSTREAM_LLM_MODEL=unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL \
  nohup /tmp/guard-venv/bin/python -m uvicorn work_rag_guardrails.api:create_app --factory \
  --host 0.0.0.0 --port 8200 > /tmp/guard.log 2>&1 &
sleep 10

echo "== 4. Langfuse fallback collector :3000 =="
cd "$ROOT/components/tracing"
nohup /tmp/orch-venv/bin/python -m uvicorn app:app \
  --host 0.0.0.0 --port 3000 > /tmp/langfuse.log 2>&1 &
sleep 6

echo "== 5. Orchestrator :8100 =="
cd "$ROOT"
PYTHONPATH="$ROOT/components/orchestrator/src" KB_BASE_URL=http://127.0.0.1:8000 \
  GUARDRAILS_BASE_URL=http://127.0.0.1:8200 \
  UPSTREAM_LLM_MODEL=unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL \
  LANGFUSE_HOST=http://127.0.0.1:3000 \
  nohup /tmp/orch-venv/bin/python -m uvicorn work_rag_orchestrator.api:create_app --factory \
  --host 0.0.0.0 --port 8100 > /tmp/orch.log 2>&1 &
sleep 10

echo "== 6. Open WebUI :13000 =="
OPENAI_API_BASE_URL=http://127.0.0.1:8100/v1 OPENAI_API_KEY=sk-local-dev WEBUI_AUTH=false \
  DATA_DIR=/tmp/webui-data \
  nohup /tmp/webui-venv/bin/open-webui serve --host 0.0.0.0 --port 13000 > /tmp/webui.log 2>&1 &
sleep 15

echo "== health =="
for p in 18000 8000 8200 8100; do
  printf "%s: " "$p"; curl -s --max-time 8 "http://127.0.0.1:$p/health" | head -c 60; echo
done
curl -s --max-time 8 http://127.0.0.1:3000/api/public/health; echo
echo "done. Public access on Vast = SSH tunnels (ports are NAT-fixed at creation):"
echo "  ssh -p <ssh_port> root@<ssh_host> -L 13000:localhost:13000 -L 8100:localhost:8100"
