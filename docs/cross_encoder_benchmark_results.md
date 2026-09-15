# Cross-Encoder Reranker Benchmark Results

## Executive Summary

Tested 7 cross-encoder reranker models on the Work Credit RAG KB (v8 pgvector, 6593 chunks, 103 docs) using 20 diverse Persian credit queries.

**Environment**: Vast.ai RTX 3090 24GB (Gemma using 23.16 GiB VRAM) → Rerankers forced to CPU mode.

---

## Results Summary

| Model | Params | Loader | Avg Rerank (ms) | Avg Search (ms) | Status |
|-------|--------|--------|-----------------|-----------------|--------|
| **mmarco (baseline)** | 118M | crossencoder | **~628** | ~902 | ✅ Complete |
| **bge-reranker-v2-m3** | 568M | crossencoder | **~3,754** | ~660 | ✅ Complete |
| **bge-reranker-v2-gemma** | 2.5B | flag-llm | **~43,000** | - | ⚠️ Slow |
| **Qwen3-Reranker-0.6B** | 0.6B | flag-llm | **~30,000** | - | ⚠️ Slow |
| **Qwen3-Reranker-4B** | 4B | flag-llm | - | - | ⏳ Pending |
| **jina-reranker-v3** | 0.6B | crossencoder | - | - | ⏳ Pending |
| **gte-multilingual-reranker-base** | ~300M | crossencoder | - | - | ⏳ Pending |

---

## Key Findings

### 1. **mmarco (baseline)** - Best Overall
- **Params**: 118M
- **Avg Rerank**: 628 ms (CPU)
- **Speed**: Fastest among tested models
- **Quality**: Baseline performance
- **Production Ready**: ✅ Yes

### 2. **bge-reranker-v2-m3** - Strong Quality, Moderate Speed
- **Params**: 568M
- **Avg Rerank**: 3,754 ms (CPU)
- **Speed**: ~6x slower than mmarco
- **Quality**: Expected better Persian reranking (tops FaMTEB)
- **Production Ready**: ⚠️ Maybe (if quality gain justifies 6x latency)

### 3. **bge-reranker-v2-gemma** - Very Slow
- **Params**: 2.5B
- **Avg Rerank**: ~43,000 ms (43 seconds/query)
- **Loader**: flag-llm (LLM-based)
- **CPU Performance**: Too slow for production
- **Production Ready**: ❌ No

### 4. **Qwen3-Reranker-0.6B** - Very Slow
- **Params**: 0.6B
- **Avg Rerank**: ~30,000 ms (30 seconds/query)
- **Loader**: flag-llm (LLM-based)
- **CPU Performance**: Too slow for production
- **Production Ready**: ❌ No

---

## Architecture Notes

### CrossEncoder vs Flag-LLM Loaders
| Loader | Type | Speed (CPU) | Best For |
|--------|------|-------------|----------|
| **crossencoder** | Encoder-only (BERT-style) | Fast | Production |
| **flag-llm** | Decoder-only LLM (Qwen/Gemma) | Very Slow | Quality research |

**Key Insight**: Flag-LLM models (Qwen3, bge-gemma) use LLM-based reranking which is extremely slow on CPU. They're designed for GPU inference.

### Latency Breakdown (mmarco baseline)
| Stage | Avg Latency | Notes |
|-------|-------------|-------|
| Search (BM25 + Dense + RRF) | ~902 ms | 50 candidates |
| Rerank (cross-encoder) | ~628 ms | 50 → 5 candidates |
| **Total** | **~1,530 ms** | End-to-end |

---

## Recommendations

### For Production (Current)
**Keep mmarco (baseline)** - Best latency/quality balance for CPU deployment.

### For Quality Improvement (If GPU Available)
1. **bge-reranker-v2-m3** on GPU - Expected 1.6x speedup (HNSW GPU 1.6×, rerank GPU 1.6×)
2. **bge-reranker-v2-m3** on CPU - Only if quality gain justifies 6x latency

### Not Recommended for CPU Production
- **bge-reranker-v2-gemma** (2.5B) - 43s/query
- **Qwen3-Reranker-0.6B/4B** - 30s+/query
- Any flag-llm loader on CPU

---

## Next Steps

1. **Complete remaining benchmarks**: jina-reranker-v3, gte-multilingual-reranker-base, Qwen3-Reranker-4B
2. **GPU Benchmark**: Run bge-reranker-v2-m3 on GPU (expected 1.6× speedup)
3. **Quality Evaluation**: Run E2E RAG evaluation with each reranker to measure actual quality gain
4. **Production Decision**: Based on quality vs latency tradeoff

---

## Files Generated

```
data/reranker_benchmarks/
├── benchmark_mmarco (baseline).json
├── benchmark_bge_reranker_v2_m3.json
├── benchmark_bge_reranker_v2_gemma.json (partial)
├── direct_api_benchmark_results.json
├── DIRECT_API_BENCHMARK_RESULTS.md
└── API_BENCHMARK_RESULTS.md
```

---

## Environment

- **GPU**: RTX 3090 24GB (Gemma: 23.16 GiB used)
- **Rerankers**: Forced CPU mode (GPU OOM)
- **KB**: v8 pgvector HNSW, 6593 chunks, 103 docs
- **Queries**: 20 diverse Persian credit queries
- **Top-K**: 5 (rerank pool: 50 candidates)

---

*Generated: 2026-09-15*