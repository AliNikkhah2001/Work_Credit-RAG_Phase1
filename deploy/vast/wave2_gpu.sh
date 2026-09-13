#!/usr/bin/env bash
# Wave-2 GPU benchmark: Qwen3-0.6B -> Qwen3-4B -> BGE-Gemma-2B on full remapped 800.
# Run on the BIGGER GPU machine (see docs/WAVE2_GPU_RUNBOOK.md for VRAM sizing).
# Each run: pool=15, top_k=5, same remapped golds as wave 1 -> directly comparable.
set -euo pipefail

export KB_DB_URL="${KB_DB_URL:-postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/kb_manager}"
export HF_HOME="${HF_HOME:-/tmp/hf_clean}" HF_HUB_CACHE="${HF_HUB_CACHE:-/tmp/hf_clean}"
export HF_HUB_OFFLINE=1
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
# Force GPU for reranker + dense encoder (needs CUDA torch in kb-venv):
export KB_RERANKER_DEVICE=cuda KB_EMBED_DEVICE=cuda

KBVENV="${KBVENV:-/tmp/kb-venv/bin/python}"
DS="${DS:-/tmp/opencode/eval_remapped.json}"
OUTDIR="${OUTDIR:-/tmp/opencode}"

"$KBVENV" -c "import torch; assert torch.cuda.is_available(), 'CUDA torch required'; print('cuda:', torch.cuda.get_device_name(0))"
nvidia-smi --query-gpu=memory.free --format=csv | head -2

run_one() {
  local name="$1" model="$2" pool="${3:-15}"
  echo "===== [$name] model=$model pool=$pool ====="
  date -u
  "$KBVENV" -u /tmp/opencode/bench_backbone.py "$name" "$model" "$pool" "$DS" "$OUTDIR/bench_$name.json" 5 2>&1 | tail -3
  echo "===== DONE $name ====="
  date -u
}

# Order requested: 0.6B first, then 4B, then Gemma-2B.
run_one qwen06-gpu  "Qwen/Qwen3-Reranker-0.6B"  15
run_one qwen4b-gpu  "Qwen/Qwen3-Reranker-4B"    15
run_one bgemma-gpu  "BAAI/bge-reranker-v2-gemma" 15

echo "WAVE 2 GPU DONE — aggregate with: /tmp/kb-venv/bin/python /tmp/opencode/aggregate_bench.py"
