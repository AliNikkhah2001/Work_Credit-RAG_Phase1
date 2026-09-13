# Wave-2 GPU Runbook — heavy reranker shootout on a bigger machine

Date: 2026-09-13. Wave 1 (CPU, 800 remapped queries) is done for
MiniLM / MiniLM-p30 / BGE-m3. Wave 2 scores the heavy backbones on the
**same** benchmark so results are directly comparable.

## 1. What wave 2 runs (in order)

`deploy/vast/wave2_gpu.sh` runs, sequentially, pool=15, top_k=5:

1. `qwen06-gpu` — `Qwen/Qwen3-Reranker-0.6B` (~1.5 GB fp16)
2. `qwen4b-gpu` — `Qwen/Qwen3-Reranker-4B` (~9 GB fp16)
3. `bgemma-gpu` — `BAAI/bge-reranker-v2-gemma` (~5 GB fp16)

Dataset: `/tmp/opencode/eval_remapped.json` (800 queries, answer-grounded
golds, ~7 gold/query, remapped to the 2077-chunk PG KB on 2026-09-12).
Output: `/tmp/opencode/bench_<name>.json`, then aggregate with
`/tmp/opencode/aggregate_bench.py` (copy it over — see §4).

Wave-1 reference numbers (same dataset, CPU): MiniLM MRR 0.493,
MiniLM-p30 0.495, BGE-m3 0.496. Beat 0.496 with acceptable latency to win.

## 2. VRAM math (measured 2026-09-13, RTX 3090 24 GB)

| Resident | VRAM |
|---|---|
| Gemma-4-31B Q4_K_XL + ctx 8192 (`llama-server -ngl 999`) | **22.7 GB** (measured `nvidia-smi`) |
| Qwen3-0.6B fp16 | ~1.5 GB |
| Qwen3-4B fp16 | ~9 GB |
| BGE-Gemma 2B fp16 | ~5 GB |
| MiniLM dense encoder + CUDA context overhead | ~1.5 GB |

Wave-2 workers are **in-process** — they never call `:18000`.
Peak = Gemma + one reranker + overhead:

| Scenario | Peak | Fits |
|---|---|---|
| Gemma running + qwen4b (worst wave-2 peak) | ~34 GB | 40 GB tight, **48 GB comfortable** |
| Gemma running + bgemma | ~30 GB | 40 GB OK |
| **llama-server STOPPED during bench** + qwen4b | ~11 GB | **any 24 GB card** |

## 3. Machine recommendation

- **Cheapest:** RTX 4090 24 GB — stop `llama-server` during bench runs,
  restart after. ~$0.40–0.60/hr on Vast.
- **No-downtime:** A100 40 GB — everything resident, ~$0.80–1.10/hr.
- **Ideal:** A100 80 GB / H100 — headroom for pool-30 reruns + Gemma ctx 8192.
- Avoid 2×GPU unless you enjoy `llama-server` tensor-split debugging.

## 4. Porting checklist (old → new machine)

1. Copy the workspace dir (`Work_Credit-RAG_Phase1`) — submodules included.
2. Copy `/tmp/opencode/` helpers: `bench_backbone.py`, `aggregate_bench.py`,
   `eval_remapped.json`, `remap_gold.py` (regenerate instead: needs PG + KB).
   Or re-clone repos at pins: parent `main` @ `29757a1`
   (kb `9ecb8ac`, orch `f922649`, guard `d9e67cd`, setup `5b030a3`).
3. Copy `/tmp/hf_clean` (58 GB incl. all rerankers) **or** re-download (§5).
4. Run `scripts/bootstrap_gpu_machine.sh` (apt, postgres+pgvector, venvs,
   **CUDA torch** in kb-venv, HF cache layout, DB migrate).
5. Start stack: `bash deploy/vast/start.sh` (or skip `llama-server` for bench-only).
6. `bash deploy/vast/wave2_gpu.sh` (takes hours on CPU, minutes–tens of minutes on GPU).

## 5. Model prefetch (if not copying `/tmp/hf_clean`)

```bash
export HF_HOME=/tmp/hf_clean HF_HUB_CACHE=/tmp/hf_clean
huggingface-cli download Qwen/Qwen3-Reranker-0.6B \
  Qwen/Qwen3-Reranker-4B BAAI/bge-reranker-v2-gemma \
  cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 \
  sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

Both `HF_HOME` **and** `HF_HUB_CACHE` must point at the cache (hub 1.x quirk).

### DB migration note (existing databases only)

Merged `master` selects the full `Chunk` entity, which includes the nullable
`chunks.embedding vector(384)` column from the v10 schema. Fresh `create_all`
databases already have it; migrated databases (like the 2077-chunk Vast PG)
need one statement:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS embedding vector(384);
```

Without it every query fails with
`UndefinedColumnError: column chunks.embedding does not exist`
(plus confusing follow-on pool errors). Fresh setups via
`scripts/bootstrap_gpu_machine.sh` are unaffected.

## 6. Smoke test (validates plumbing without GPUs or waiting)

```bash
KB_DB_URL=... /tmp/kb-venv/bin/python -u /tmp/opencode/bench_backbone.py \
  qwen06-smoke Qwen/Qwen3-Reranker-0.6B 15 /tmp/opencode/smoke5.json \
  /tmp/opencode/bench_qwen06_smoke.json 5
```

Expect: `queries: 5`, non-zero `hit_rate`, latency ≫ 30 ms/q
(CPU ~seconds/q, GPU ~100 ms/q). `RerankerConfig() takes no arguments`
= stale `config.py` (fixed on KB `master` ≥ merge `9ecb8ac` + decorator fix).

## 7. Session handoff

Full transcript of the session that produced wave 1 + this runbook:
`docs/SESSION_WAVE1_HANDOFF.md` (exported from opencode `session` table).
Recreate context on the new machine by opening that file alongside this runbook.
