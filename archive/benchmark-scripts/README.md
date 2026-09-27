# Archived Benchmark Scripts

Two near-duplicate reranker benchmark scripts archived from `scripts/` — canonical is `scripts/cross_encoder_benchmark.py`.

| Script | Lines | Purpose | Difference |
|--------|-------|---------|------------|
| `direct_cross_encoder_benchmark.py` | 322 | Direct Python API (`kb_manager` import) | Imports `kb_manager` directly, no HTTP |
| `api_cross_encoder_benchmark.py` | 318 | HTTP API (`KB_URL=http://127.0.0.1:8000`) | Hits running KB via `httpx` |

**Canonical:** `scripts/cross_encoder_benchmark.py` (501 lines) — comprehensive suite with `RERANKER_MODELS` table, `dataclass` results, `argparse`, full logging. Covers both modes via its `ROOT` path logic.

**To restore:** `git mv archive/benchmark-scripts/<file> scripts/`
