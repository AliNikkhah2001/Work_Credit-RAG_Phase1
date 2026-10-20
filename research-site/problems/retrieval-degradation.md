---
layout: default
title: "Retrieval Degradation"
description: "Filtered retrieval = hard filter, no fallback. Fixed with RRF fusion + broadened retry + GPU acceleration."
---

<div class="page-header">
  <h1>Retrieval Degradation</h1>
  <p class="lead">Filtered retrieval = hard filter, no fallback. Fixed with RRF fusion + broadened retry + GPU acceleration.</p>
</div>

## Problem Summary

| Aspect | Detail |
|--------|--------|
| **Severity** | Critical |
| **Category** | Retrieval / Fallback |
| **Status** | ✅ Fixed |
| **Bench Impact** | Hit: 0.537 → 0.780; p50: 8006ms → 4872ms |
| **Key Papers** | GUIR (SemEval 2026), 5ting (SemEval 2026), H-RAG (SemEval 2026), Sifei (SemEval 2026) |

---

## Root Cause

### The Hard Filter Problem

Our retrieval pipeline:
```python
# retrieve.py - primary path
result = await client.retrieve(search_query, top_k, request_id, filter_path=sticky_filter)

# If weak (0 chunks or max_score < threshold):
# ❌ OLD: Clear chunks → abstention
# ✅ NEW: Whole-KB fallback → RRF fusion → broadened retry
```

### The Degradation Pattern

| Turn Type | Filter | Chunks | Score | Outcome |
|-----------|--------|--------|-------|---------|
| New chat | None | 10 | 0.032 | Answer ✅ |
| After sticky | `گزارش اعتباراتنجی چک` | 0 | — | Abstain ❌ |
| Whole-KB | None | 10 | 0.028 | Answer (but weak) |

The filter **removed** relevant chunks because KB filter checks exact element membership.

---

## The Fix: Multi-Stage Fallback Cascade

### Stage 1: Primary Filtered Retrieval
```python
# retrieve.py - explicit scope
result = await client.retrieve(
    search_query, primary_top_k, request_id,
    filter_path=explicit_filter,
    keyword_boost=_subspace_keyword_boost(subspace)
)
```

### Stage 2: RRF Fusion Fallback (T1)
```python
# If weak → whole-KB retry → RRF FUSION (not replace)
async def _t1_try_whole_kb_fallback(state, search_query, request_id, active_filter):
    fb_result = await fb_client.retrieve(search_query, top_k, request_id, filter_path=None)
    if fb_result:
        # RRF FUSION instead of hard replace
        state["retrieved_chunks"] = _fuse_subspace_rrf(current, fb_result)[:20]
        state["fallback_used"] = True
        state["fallback_reason"] = f"low_score top={cur_top:.4f} < thr={thr:.3f} | fused rrf(cur=N,fb=M -> K)"
```

### Stage 3: Broadened Retry (T2)
```python
# If still weak → broadened params
async def _t2_try_broadened_retry(state, search_query, request_id, top_k=30, keyword_boost=1.5):
    # top_k=30, keyword_boost=1.5, beam=5
    fb_result = await client.retrieve(search_query, 30, request_id, filter_path=None, keyword_boost=1.5)
    # FUSE with previous
    state["retrieved_chunks"] = _fuse_subspace_rrf(previous, fb_result)[:20]
    state["broaden_used"] = True
```

### Stage 4: LLM-Judge Broadening (F5)
```python
# If still weak → LLM infers subspace → filtered re-retrieve
llm_choice = await infer_subspace_llm(query, history, request_id)
if llm_choice and llm_choice != sticky:
    # Explicit re-spec → switch subspace
    new_filter = subspace_map[llm_choice]
    result = await client.retrieve(search_query, top_k, request_id, filter_path=new_filter)
```

---

## RRF Fusion Algorithm

```python
def _fuse_subspace_rrf(filtered, whole, filtered_weight=1.3):
    """
    Reciprocal Rank Fusion with filtered boost
    score = 1/(60 + rank) * weight
    """
    merged = {}
    # Filtered leg: weight 1.3x
    for rank, chunk in enumerate(filtered):
        key = chunk.chunk_id
        score = filtered_weight / (60 + rank + 1)
        merged[key] = max(merged.get(key, 0), score)
    
    # Whole-KB leg: weight 1.0
    for rank, chunk in enumerate(whole):
        key = chunk.chunk_id
        score = 1.0 / (60 + rank + 1)
        merged[key] = max(merged.get(key, 0), score)
    
    # Sort by fused score, take top 20
    return sorted(merged.values(), key=lambda x: x.fused_score, reverse=True)[:20]
```

---

## Benchmark Delta

| Metric | Before | After | Δ |
|--------|--------|-------|---|
| Retrieval hit | 0.537 | **0.780** | +0.243 |
| Cheque hit | 0.111 | **0.667** | +0.556 |
| Fallback usage | 0% | 32% | +32% |
| Broaden usage | 0% | 18% | +18% |
| p50 latency | 8006ms | **4872ms** | -39% |

---

## Related Papers

| Paper | Venue | Key Contribution |
|-------|-------|------------------|
| **GUIR** | SemEval 2026 | Multi-query fusion (LT + RW + QS) → RRF → +12.3% nDCG@5 |
| **5ting** | SemEval 2026 | Dual-query merged retrieval + LLM reranking + faithfulness control |
| **H-RAG** | SemEval 2026 | Hierarchical parent-child retrieval + hybrid retrieval + parent-level context |
| **Sifei** | SemEval 2026 | Hybrid dense+sparse + query rewrite + cross-encoder → 0.5453 nDCG@5 (Rank 3/38) |
| **Sifei** | SemEval 2026 | Hybrid dense+sparse + query rewrite + cross-encoder → 0.5453 nDCG@5 (Rank 3/38) |
| **IITKanBDone** | SemEval 2026 | ELSER + Mistral-7B → end-to-end multi-turn RAG |
| **AILS-NTUA** | SemEval 2026 | Multi-strategy rewriting (Minimal + Corpus-Specific + CoT) + Nested-RRF |

---

## Architecture: Fallback Cascade

```mermaid
flowchart TD
    A[Query + Filter] --> B[Primary Filtered Retrieval]
    B --> C{Strong Evidence?}
    C -->|Yes| D[Build Context → Generate]
    C -->|No| E[T1: Whole-KB Fallback<br/>RRF Fusion (weight 1.3x)]
    E --> F{Strong Evidence?}
    F -->|Yes| D
    F -->|No| G[T2: Broadened Retry<br/>top_k=30, boost=1.5, beam=5]
    G --> H{Strong Evidence?}
    H -->|Yes| D
    H -->|No| I[F5: LLM-Judge Broadening<br/>infer_subspace_llm]
    I --> J{LLM Chooses Subspace?}
    J -->|Yes| K[Filtered Re-retrieve]
    J -->|No| L[Abstain: 'پاسخی یافت نشد']
    K --> F
    
    style E fill:#fef3e0,stroke:#f57f17
    style G fill:#fef3e0,stroke:#f57f17
    style I fill:#fef3e0,stroke:#f57f17
```

---

## Code Pointers

| File | Function | Line |
|------|----------|------|
| `retrieve.py` | `_fuse_subspace_rrf` | 143 |
| `retrieve.py` | `_t1_try_whole_kb_fallback` | 220 |
| `retrieve.py` | `_t2_try_broadened_retry` | 220 |
| `retrieve.py` | F5 LLM-judge | 1640 |
| `clients/knowledgebase.py` | `retrieve()` with boost | 61 |
| `config.py` | `subspace_keyword_boost` | 34 |

---

## Validation Commands

```bash
# Test fallback cascade
curl -s http://127.0.0.1:8100/v1/chat/completions \
  -H 'Content-Type: application/json' -H 'X-Request-ID: fallback-test' \
  -d '{"model":"ics-helper-agent","messages":[{"role":"user","content":"چک برگشتی چیست"}],"filter_path":"گزارش اعتباراتنجی چک"}' \
  | jq '.audit.fallback_used, .audit.broaden_used, .audit.retry_stage_timing, .audit.retrieved_chunks|length'

# Test broadened retry
curl -s http://127.0.0.1:8100/v1/chat/completions \
  -H 'Content-Type: application/json' -H 'X-Request-ID: broaden-test' \
  -d '{"model":"ics-helper-agent","messages":[{"role":"user","content":"سوال بسیار مبهم..."}]}' \
  | jq '.audit.broaden_used, .audit.retry_stage_timing.retrieve_broadened'
```

---

## Related Problems

- [Subspace Filtering](./subspace-filtering.html) — Map mismatch caused 0 chunks
- [Sticky Context Decay](./sticky-context.html) — Context loss on generic follow-ups
- [Hallucination Control](./hallucination.html) — Weak-evidence answers hallucinated