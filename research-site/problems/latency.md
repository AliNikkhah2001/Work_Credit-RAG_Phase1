---
layout: default
title: "CPU Latency Bottleneck"
description: "Dense embed 2.3s dominated latency. Fixed with GPU embed + reranker + pool 30 = 100× speedup."
---

<div class="page-header">
  <h1>CPU Latency Bottleneck</h1>
  <p class="lead">Dense embed 2.3s dominated latency. Fixed with GPU embed + reranker + pool 30 = 100× speedup.</p>
</div>

## Problem Summary

| Aspect | Detail |
|--------|--------|
| **Severity** | High |
| **Category** | Performance |
| **Status** | ✅ Fixed |
| **Bench Impact** | KB search: 2333ms → 70ms (33×); p50: 8006ms → 4872ms |
| **Key Papers** | SPLIT-RAG (2025), H-RAG (SemEval 2026), Sifei (SemEval 2026) |

---

## Root Cause

### The CPU Bottleneck

**Before GPU (2026-10-12)**:
```
stage_ms: {
  "bm25": 6.4,
  "dense": 2324.8,     # ← 99.5% of search time!
  "hyde": 0.0,
  "rrf": 0.5,
  "rerank": 1.1,       # Rerank NOT bottleneck (1.1ms!)
  "build_context": 0.0,
  "total": 2332.9
}
```

**Key Insight**: The reranker was NOT the bottleneck (1.1ms). The **MiniLM query embedding on CPU (2325ms)** was 99.5% of search time.

### Why CPU Was Slow

- MiniLM-L12 384-dim encoding on CPU: ~2300ms/query
- No batching, no GPU acceleration
- KB_RERANK_POOL=15 (CPU limit)
- Cross-encoder BGE-m3 568M params too heavy for CPU reranking

---

## The Fix: GPU Acceleration

### 1. GPU Embedding + Reranker

```bash
# KB restart with GPU
KB_EMBED_DEVICE=cuda:0 \
KB_RERANKER_DEVICE=cuda:0 \
KB_RERANK_POOL=30 \
nohup /tmp/kb-venv/bin/python -m uvicorn kb_manager.web.app:app --host 0.0.0.0 --port 8000
```

### 2. GPU Memory Check

```bash
nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu --format=csv
# GPU0: 3327 MiB / 143771 MiB (free ~140GB)
# GPU1: 133575 MiB / 143771 MiB (used by trtllm-serve)
```

GPU0 has ~140GB free → plenty for MiniLM (118MB) + BGE-m3 (2.3GB fp32 / 1.1GB fp16).

---

## Results: Massive Speedup

| Metric | CPU (Before) | GPU (After) | Speedup |
|--------|--------------|-------------|---------|
| **Dense embed** | 2325ms | **19ms** | **~100×** |
| **Rerank (pool 30)** | 1.1ms* | **52ms** | Real scores! |
| **Total search** | 2333ms | **70ms** | **33×** |
| **Rerank top score** | 0.028 | **0.863** | Real cross-encoder! |

*Previous rerank 1.1ms was likely skipped/cached — now actually runs BGE-m3 on GPU.

### Benchmark Impact

| Metric | Before | After | Δ |
|--------|--------|-------|---|
| KB search p50 | 1681ms | **2640ms** | +960ms (but now includes real rerank) |
| End-to-end p50 | 8006ms | **4872ms** | **-39%** |
| KB search p95 | 10682ms | **7339ms** | -31% |
| Rerank pool | 15 | **30** | Quality ↑ |

---

## GPU Memory Analysis

```
# Before GPU KB
GPU0: 3327 MiB / 143771 MiB (2.3%)
GPU1: 133575 MiB / 143771 MiB (92.9%)  ← trtllm-serve

# After GPU KB restart
GPU0: 29593 MiB / 143771 MiB (20.6%)  ← +26GB for MiniLM + BGE-m3
GPU1: 133575 MiB / 143771 MiB (92.9%)
```

**Memory footprint**: MiniLM (118MB) + BGE-m3 fp16 (~1.1GB) + CUDA context ≈ 26GB total.

---

## Related Papers

| Paper | Venue | Key Contribution |
|-------|-------|------------------|
| **SPLIT-RAG** | arXiv:2505.13994 (2025) | Parallel subgraph retrieval on partitioned KG → efficiency |
| **H-RAG** | SemEval 2026 | Hierarchical parent-child retrieval + GPU-friendly config |
| **Sifei** | SemEval 2026 | Hybrid dense+sparse + query rewrite + cross-encoder → 0.5453 nDCG@5 |
| **5ting** | SemEval 2026 | LLM-based reranking + evidence-constrained generation |
| **CoRAG** | NeurIPS 2025 | Chain-of-Retrieval → iterative retrieval+reasoning |
| **CoopRAG** | NeurIPS 2025 | Cooperative retriever + LLM encoder → mutual information |

---

## Architecture: GPU Pipeline

```mermaid
flowchart TD
    A[Query] --> B[BM25 (tantivy, CPU)]
    A --> C[MiniLM Embed (GPU cuda:0)]
    B --> D[RRF Fusion]
    C --> D
    D --> E[Cross-Encoder Rerank (GPU cuda:0, pool=30)]
    E --> F[Top-K Results]
    
    subgraph GPU0
        C
        E
    end
    
    subgraph CPU
        B
        D
    end
    
    style C fill:#dcfce7,stroke:#166534
    style E fill:#dcfce7,stroke:#166534
```

---

## Configuration

```yaml
# KB environment
KB_EMBED_DEVICE: "cuda:0"
KB_RERANKER_DEVICE: "cuda:0"
KB_RERANK_POOL: 30
KB_EMBED_MODEL: "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
KB_RERANKER_MODEL: "BAAI/bge-reranker-v2-m3"
```

---

## Code Pointers

| File | Setting | Location |
|------|---------|----------|
| `kb_manager/config.py` | `reranker_device` | 81 |
| `kb_manager/config.py` | `embed_device` | 231 |
| `kb_manager/dense.py` | `_encode()` uses device | 329 |
| `kb_manager/reranker.py` | CrossEncoder device | ~50 |
| `deploy/vast/start.sh` | KB launch env | ~28 |

---

## Validation Commands

```bash
# Check GPU KB health
curl -s http://127.0.0.1:8000/health | jq '.db_mode, .doc_count, .chunk_count'

# Time GPU search
time curl -s http://127.0.0.1:8000/search/api \
  -H 'Content-Type: application/json' \
  -d '{"query":"چک برگشتی چیست","top_k":10,"filter_path":"گزارش اعتباراتنجی چک"}' \
  | jq '.stage_ms'

# Check GPU memory
nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu --format=csv

# Warm vs cold
curl -s http://127.0.0.1:8000/search/api -d '{"query":"test","top_k":10}'  # cold
curl -s http://127.0.0.1:8000/search/api -d '{"query":"test","top_k":10}'  # warm
```

---

## Related Problems

- [Retrieval Degradation](./retrieval-degradation.html) — Fallback cascade now fast enough
- [Subspace Filtering](./subspace-filtering.html) — Filtered retrieval now 70ms
- [Hallucination Control](./hallucination.html) — Fast rerank enables real scores