# Handoff — Bench & Scripts

| Path | Content | Relation |
|------|---------|----------|
| `bench/` (20 files, 4.6MB) | Reranker shootouts (`bench_minilm.json`, `bench_bgem3.json`, `eval_remapped.json` 921KB), smoke tests | **Supplement** to `eval/results/` — raw 800Q bench data before aggregation |
| `scripts/` (17 scripts) | `bench_backbone.py`, `aggregate_bench.py`, `remap_gold.py`, `verify_*.py` | Evaluation tooling, duplicates `scripts/` at root (see `scripts/cross_encoder_benchmark.py` canonical) |
| `CONTINUE.md` | Wave-2 GPU runbook continuation | Pointer to `docs/WAVE2_GPU_RUNBOOK.md` |

**Canonical:** `eval/results/` (aggregated) + `README.md#evaluation`. `handoff/bench/` is raw supplement — keep for reproducibility, not for API.
**Sessions:** `handoff/sessions/` (36 transcripts) archived to `archive/handoff-sessions/` on `main`.
