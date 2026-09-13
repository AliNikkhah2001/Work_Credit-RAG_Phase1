#!/bin/bash
# Wave 2: heavy rerankers on stratified-200 subset, SEQUENTIAL (RAM: qwen4b 23G).
# In-process workers (no server). Run AFTER wave 1 finishes.
export KB_DB_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/kb_manager"
export HF_HOME=/tmp/hf_clean HF_HUB_CACHE=/tmp/hf_clean HF_HUB_OFFLINE=1 OMP_NUM_THREADS=16
export BENCH_INDICES=/tmp/opencode/strat200.json
DS=/workspace/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager/kb_manager/evaluation/datasets/eval_clean.json
run_one() {
  local name="$1" model="$2" pool="$3"
  echo "===== $name ($model pool=$pool) ====="
  export KB_RERANKER_MODEL="$model" KB_RERANK_POOL="$pool"
  /tmp/kb-venv/bin/python -u /tmp/opencode/bench_backbone.py "$name" "$model" "$pool" "$DS" "/tmp/opencode/bench_$name.json" 5 2>&1 | tail -3
  echo "===== DONE $name ====="
}
run_one minilm-p15-200 DEFAULT 15
run_one qwen06-p15-200 "Qwen/Qwen3-Reranker-0.6B" 15
run_one gemma-p15-200 "BAAI/bge-reranker-v2-gemma" 15
run_one qwen4b-p15-200 "Qwen/Qwen3-Reranker-4B" 15
echo "WAVE 2 DONE"
