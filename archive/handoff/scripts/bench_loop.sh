#!/bin/bash
# Reranker screening: restart KB per variant, run hard subset, save results.
cd /workspace/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager
export HF_HOME=/tmp/hf_clean HF_HUB_CACHE=/tmp/hf_clean HF_HUB_OFFLINE=1
export KB_DB_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/kb_manager"

run_variant() {
  local name="$1" model="$2" pool="$3"
  echo "===== VARIANT $name ($model pool=$pool) ====="
  pkill -f 'kb_manager.web.app' 2>/dev/null; sleep 5
  export KB_RERANKER_MODEL="$model" KB_RERANK_POOL="$pool"
  setsid nohup /tmp/kb-venv/bin/python -m uvicorn kb_manager.web.app:app \
    --host 0.0.0.0 --port 8000 > /tmp/kb.log 2>&1 < /dev/null &
  # wait for ready (pre-warm loads reranker; big models take minutes)
  for i in $(seq 1 40); do
    sleep 15
    if curl -s --max-time 8 http://127.0.0.1:8000/ready | grep -q '"ready"'; then
      echo "KB ready after ~$((i*15))s"; break
    fi
  done
  curl -s --max-time 8 http://127.0.0.1:8000/ready; echo
  /tmp/kb-venv/bin/python /tmp/opencode/screen_rerank.py "$name" "/tmp/opencode/screen_$name.json"
  echo "===== DONE $name ====="
}

run_variant baseline "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1" 0
run_variant minilm-p30 "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1" 30
run_variant bgem3-p30 "BAAI/bge-reranker-v2-m3" 30
run_variant jina-p30 "jinaai/jina-reranker-v3" 30
run_variant qwen06-p30 "Qwen/Qwen3-Reranker-0.6B" 30
run_variant qwen4b-p30 "Qwen/Qwen3-Reranker-4B" 30
run_variant gemma-p30 "BAAI/bge-reranker-v2-gemma" 30
echo "ALL VARIANTS DONE"
