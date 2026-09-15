# Cross-Encoder Reranker API Benchmark Results

*Generated: 2026-09-15T08:18:53.735850+00:00*

*KB URL: http://127.0.0.1:8000*

*Test Queries: 20 diverse Persian credit queries*

## Latency Comparison

| Model | Params | Loader | Avg Rerank (ms) | Avg Total (ms) | Avg Search (ms) |
|-------|--------|--------|-----------------|----------------|-----------------|
| mmarco (baseline) | 118M | crossencoder | 0.0 | 1405.5 | 4039.7 |
| bge-reranker-v2-m3 | 568M | crossencoder | 0.0 | 1387.1 | 3953.2 |

## Stage Latencies


### mmarco (baseline)

| Stage | Avg Latency (ms) |
|-------|------------------|
| search_without_rerank | 4039.7 |
| search_with_rerank | 1405.5 |
| rerank_only | 0.0 |

### bge-reranker-v2-m3

| Stage | Avg Latency (ms) |
|-------|------------------|
| search_without_rerank | 3953.2 |
| search_with_rerank | 1387.1 |
| rerank_only | 0.0 |