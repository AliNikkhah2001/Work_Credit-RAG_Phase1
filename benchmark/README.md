# Massive Retrieval Benchmark

Stage-level audit of `BM25 → Dense → RRF → CrossEncoder (BAAI/bge-reranker-v2-m3)`.

## Layout

```
benchmark/
├── README.md                    # this file
├── configs/massive_benchmark.yaml
├── datasets/eval_remapped.json  # 796 Q/A, answer-grounded golds, graded relevance
├── raw/massive_results.jsonl    # one row/query: full stage rankings + scores
├── raw/massive_config.json      # git SHA, models, env, pool, top_k, depth
├── metrics/overall_metrics.json # per-stage means at all K + MRR
├── metrics/metrics_by_query.jsonl
├── diagnostics/failure_analysis.jsonl
├── diagnostics/gold_ranks.jsonl
├── datasets/retrieval_pairs_*.jsonl  # train/val/test (generated later)
├── plots/*.png
└── FINAL_REPORT.md              # (generated at completion)
```

## Scripts (`scripts/`)

| Script | Purpose |
|---|---|
| `remap_gold.py` | answer-coverage remap of stale chunk IDs → live KB golds |
| `run_massive.py` | stage-capture harness (production code path) |
| `analyze.py` | per-stage metrics, candidate recall, failures, gain/loss |
| `plots.py` | 10 diagnostic plots |
| `test_metrics.py` (in `benchmark/`) | hand-computed metric validation |

## Production extension

`search_knowledge_base(..., stage_depth=None)` — diagnostic stage-list depth;
rerank pool and final top-k unaffected (backward compatible).

## Ground truth

`relevance_scores = {chunk_id: answer_token_coverage}` (threshold 0.6).
Queries with no golds raise in metrics and are excluded from means (counted).
