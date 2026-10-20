---
layout: default
title: "Subspace Filtering Failure"
description: "Root cause: subspace_map mismatch ('چک' vs KB folder 'گزارش اعتباراتنجی چک'). Fixed with map correction + RRF fusion."
---

<div class="page-header">
  <h1>Subspace Filtering Failure</h1>
  <p class="lead">Root cause: <code>subspace_map</code> mismatch (<code>"چک"</code> vs KB folder <code>"گزارش اعتباراتنجی چک"</code>). Fixed with map correction + RRF fusion.</p>
</div>

## Problem Summary

| Aspect | Detail |
|--------|--------|
| **Severity** | Critical |
| **Category** | Retrieval / Routing |
| **Status** | ✅ Fixed |
| **Bench Impact** | Cheque hit: 0.111 → 0.667 (+499%) |
| **Key Papers** | PC-RAG (2026), SPLIT-RAG (2025), GUIR (SemEval 2026) |

---

## Root Cause

### The Mismatch

Our `subspace_map` in `config.py`:
```python
subspace_map: dict = {
    "cheque": "چک",  # ❌ WRONG - doesn't match KB folder
    "facilities_person": "اشخاص حقیقی/اعتبارسنجی تسهیلات",  # ✅ CORRECT
    "facilities_legal": "اشخاص حقوقی/اعتبارسنجی تسهیلات",  # ✅ CORRECT
    "general": "پایگاه دانش عمومی"  # ✅ CORRECT
}
```

KB actual folder hierarchy (from `search.py`):
```python
# Cheque docs live under:
['پایگاه دانش', 'اشخاص حقیقی', 'گزارش اعتباراتنجی چک', ...]

# NOT under 'چک' as a standalone element
```

### KB Filter Logic (from `search.py:634`)

```python
def _filter_by_path(chunks, filter_path):
    if "/" in filter_path:
        # Match joined path: "/".join(folder_hierarchy)
        return [c for c in chunks if filter_path in "/".join(c.folder_hierarchy)]
    else:
        # Exact element membership
        return [c for c in chunks if filter_path in c.folder_hierarchy]
```

Since `"چک"` has no `/`, it checks exact membership: `"چک" in folder_hierarchy`.
But folder hierarchy contains `"گزارش اعتباراتنجی چک"`, not `"چک"`.

**Result**: Filter matched **zero chunks** for all cheque queries.

---

## Evidence from Benchmarks

### Before Fix (2026-10-12)

| Query | Filter Applied | Results | Rerank Score |
|-------|---------------|---------|--------------|
| `چک برگشتی چیست` | `گزارش اعتباری چک` | 0 chunks | — |
| `تاثیر چک برگشتی` | `گزارش اعتباری چک` | 0 chunks | — |

KB Probe (without filter): 10 chunks, top rerank 0.028

### After Fix (2026-10-14)

| Query | Filter Applied | Results | Rerank Score |
|-------|---------------|---------|--------------|
| `چک برگشتی چیست` | `گزارش اعتباراتنجی چک` | 10 chunks | 0.863 |
| `تاثیر چک برگشتی` | `گزارش اعتباراتنجی چک` | 10 chunks | 0.863 |

---

## The Fix

### 1. Map Correction (1-line change)

```python
# config.py
subspace_map: dict = {
    "cheque": "گزارش اعتباراتنجی چک",  # ✅ FIXED
    ...
}
```

### 2. RRF Fusion Fallback (T1)

Instead of hard-replacing weak filtered results, **fuse** filtered + whole-KB:

```python
# retrieve.py - _fuse_subspace_rrf()
def _fuse_subspace_rrf(filtered, whole, filtered_weight=1.3):
    """RRF fusion: score = 1/(60+rank) * weight"""
    # Filtered leg gets 1.3x boost
    # Both-list chunks win, filtered-only beats whole-KB noise
    # whole-KB-only enters tail
    return fused[:20]
```

### 3. Per-Subspace Evidence Threshold (T3)

```python
# config.py
def get_evidence_threshold(self, applied_subspace):
    if "چک" in subspace or subspace == "cheque": return 0.05
    if "حقیقی" in subspace or subspace == "facilities_person": return 0.10
    return 0.15  # legal, general
```

---

## Benchmark Delta

| Metric | Before | After | Δ |
|--------|--------|-------|---|
| Cheque hit | 0.111 | **0.667** | +0.556 |
| Cheque rerank top | 0.028 | **0.863** | +0.835 |
| Cheque citations | 0 | **5** | +5 |
| Fallback usage | 100% | 0% | -100% |

---

## Related Papers

| Paper | Venue | Relevance |
|-------|-------|-----------|
| **PC-RAG** (2026) | ResearchSquare | Domain-partitioned retrieval validated our map fix; 51% false-positive reduction |
| **SPLIT-RAG** (2025) | arXiv:2505.13994 | Question-driven graph partitioning → learned routing replaces static map |
| **GUIR** (2026) | SemEval 2026 | Multi-query fusion → our RRF fusion is simplified version |
| **SPLIT-RAG** (2025) | arXiv:2505.13994 | Question-driven partitioning → learned routing from training Qs |

---

## Code Pointers

| File | Function | Line |
|------|----------|------|
| `config.py` | `subspace_map` | 34 |
| `retrieve.py` | `_fuse_subspace_rrf` | ~143 |
| `retrieve.py` | `_t1_try_whole_kb_fallback` | ~220 |
| `api.py` | Sticky injection | ~386 |
| `search.py` | `_filter_by_path` | 634 |

---

## Validation Commands

```bash
# Test cheque filter directly
curl -s http://127.0.0.1:8000/search/api -H 'Content-Type: application/json' \
  -d '{"query":"چک برگشتی چیست","top_k":10,"filter_path":"گزارش اعتباراتنجی چک"}' \
  | jq '.final_results[0].rerank_score'

# Test E2E sticky cheque
curl -s http://127.0.0.1:8100/v1/chat/completions \
  -H 'Content-Type: application/json' -H 'X-Request-ID: test' \
  -d '{"model":"ics-helper-agent","messages":[{"role":"user","content":"چک"},{"role":"assistant","content":"حوزه گزارش اعتباراتنجی چک انتخاب شد."},{"role":"user","content":"تاثیر چک برگشتی بر امتیاز چقدر است؟"}]}' \
  | jq '.audit.applied_subspace, .audit.retrieved_chunks|length, .rag.citations|length'
```

---

## Related Problems

- [Ambiguity Resolution Failure](./ambiguity-resolution.html) — Clarify gate for scattered queries
- [Retrieval Degradation](./retrieval-degradation.html) — No fallback when filtered weak
- [Sticky Context Decay](./sticky-context.html) — Context loss on generic follow-ups