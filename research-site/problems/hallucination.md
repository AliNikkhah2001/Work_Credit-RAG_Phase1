---
layout: default
title: "Hallucination Control"
description: "Weak-evidence answers hallucinated. Fixed with coverage+score guard + lexical evidence bypass + per-subspace thresholds."
---

<div class="page-header">
  <h1>Hallucination Control</h1>
  <p class="lead">Weak-evidence answers hallucinated. Fixed with coverage+score guard + lexical evidence bypass + per-subspace thresholds.</p>
</div>

## Problem Summary

| Aspect | Detail |
|--------|--------|
| **Severity** | Medium |
| **Category** | Safety / Generation |
| **Status** | ✅ Improved |
| **Bench Impact** | Hallucination: 0.195 → 0.254 (tradeoff for recall) |
| **Key Papers** | DUTIR (SemEval 2026), Reflective RAG (ACL 2026), Faith Guard (our impl) |

---

## Root Cause

### The Hallucination Pattern

When retrieval was weak (fallback/broadened paths), generation still produced answers:

| Scenario | Retrieval | Generation | Issue |
|----------|-----------|------------|-------|
| G5 fake grade | 0 chunks | "پاسخی یافت نشد" ✅ | Correct refusal |
| Cheque T3 (before fix) | 10 chunks, rerank 0.0 | "پاسخی یافت نشد" ❌ | Had evidence but abstained |
| Facilities T3 (before fix) | 10 chunks, rerank 0.0 | "پاسخی یافت نشد" ❌ | Had evidence but abstained |
| Weak fallback | 10 chunks, rerank 0.03 | Invented facts ❌ | Hallucinated |

### The Evidence Threshold Problem

Global `evidence_min_score: 0.15` starved cheque (scores 0.028) but passed general (0.033).

---

## The Fix

### 1. Per-Subspace Evidence Thresholds (T3)

```python
# config.py
def get_evidence_threshold(self, applied_subspace):
    if "چک" in subspace or subspace == "cheque": return 0.05
    if "حقیقی" in subspace or subspace == "facilities_person": return 0.10
    if "حقوقی" in subspace or subspace == "facilities_legal": return 0.15
    if "عمومی" in subspace or subspace == "general": return 0.15
    return 0.15
```

### 2. Lexical Evidence Bypass (T6)

```python
# format_response.py
def _has_lexical_evidence(query, chunks, applied_subspace):
    """Does any chunk contain query/subspace keywords?"""
    keywords = set()
    if "چک" in applied_subspace: keywords.update(["چک"])
    elif "حقیقی" in applied_subspace: keywords.update(["تسهیلات", "وام", "قسط", "حقیقی"])
    # ... add query tokens len>=2
    
    corpus = " ".join(c.get("content", "") for c in chunks[:10])
    return any(kw in corpus for kw in keywords)

# In no-evidence guard:
if (not chunks or top_score < threshold) and not supplement and not _has_lexical_evidence(...):
    return NO_EVIDENCE_MSG  # Refuse
# Else: KEEP chunks, let generation proceed
```

### 3. Faith/Hall Guard on Weak Evidence (F)

```python
# format_response.py - post-generation
if (fallback_used or broaden_used) and ABSTENTION_PHRASE not in content:
    used_top = _top_evidence_score(chosen_chunks)
    coverage = _token_coverage(answer, chosen_chunks)
    
    if used_top < 0.5 and coverage < 0.20:
        # Hallucination detected → refuse
        content = NO_EVIDENCE_MSG
        citations = []
        log.info(f"Faith guard fired: coverage={coverage:.3f} top={used_top:.3f}")
```

### 4. Token Coverage Metric

```python
def _token_coverage(answer, chunks):
    a_tokens = set(answer.split())
    c_tokens = set(" ".join(c.get("content","") for c in chunks).split())
    return len(a_tokens & c_tokens) / len(a_tokens) if a_tokens else 1.0
```

---

## Benchmark Delta

| Metric | Before | After | Note |
|--------|--------|-------|------|
| Hallucination rate | 0.195 | **0.254** | +0.059 (tradeoff) |
| Non-hallucination | 0.805 | **0.746** | -0.059 |
| G5 refusal | ✅ | ✅ | Maintained |
| Cheque T3 citations | 0 | **5** | Fixed |
| Facilities T3 citations | 0 | **5** | Fixed |

---

## Related Papers

| Paper | Venue | Key Contribution |
|-------|-------|------------------|
| **DUTIR** | SemEval 2026 | Hybrid retrieval + confidence-based answerability → faithfulness guard |
| **Reflective RAG** | ACL 2026 Findings | Self-evaluation tagging → RL strategy optimization → robust learning |
| **5ting** | SemEval 2026 | Evidence-constrained generation + IDK-conditioned harmonic mean |
| **CoopRAG** | NeurIPS 2025 | Cooperative retriever + LLM fine-tuned encoder → mutual information exchange |
| **CoRAG** | NeurIPS 2025 | Chain-of-Retrieval → iterative retrieval+reasoning for multi-hop QA |

---

## Architecture: Faith Guard Flow

```mermaid
flowchart TD
    A[Retrieved Chunks] --> B{Strong Evidence?}
    B -->|No| C{fallback_used or broaden_used?}
    C -->|Yes| D[Compute top_score + coverage]
    C -->|No| E[Normal Generation]
    D --> F{top_score < 0.5 AND coverage < 0.20?}
    F -->|Yes| G[REPLACE with NO_EVIDENCE_MSG<br/>citations=[]]
    F -->|No| E
    E --> H[Generate Answer]
    H --> I[Return]
    G --> I
    
    style G fill:#fef2f2,stroke:#ef4444
    style C fill:#fef3e0,stroke:#f57f17
```

---

## Code Pointers

| File | Function | Line |
|------|----------|------|
| `format_response.py` | `_has_lexical_evidence` | 279 |
| `format_response.py` | `_token_coverage` | 336 |
| `format_response.py` | faith guard block | 483 |
| `format_response.py` | `_top_evidence_score` | 261 |
| `config.py` | `get_evidence_threshold` | 44 |
| `retrieve.py` | lexical evidence check | 70 |

---

## Validation Commands

```bash
# Test G5 refusal
curl -s http://127.0.0.1:8100/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"ics-helper-agent","messages":[{"role":"user","content":"نمره اعتباری من G5 است چه امتیازی میگیرم"}]}' \
  | jq '.choices[0].finish_reason, .choices[0].message.content'

# Test cheque T3 (should now answer with citations)
curl -s http://127.0.0.1:8100/v1/chat/completions \
  -H 'Content-Type: application/json' -H 'X-Request-ID: faith-test' \
  -d '{"model":"ics-helper-agent","messages":[{"role":"user","content":"چک"},{"role":"assistant","content":"..."},{"role":"user","content":"تاثیر چک برگشتی بر امتیاز چقدر است؟"}]}' \
  | jq '.rag.citations|length, .choices[0].message.content[:200]'
```

---

## Related Problems

- [Retrieval Degradation](./retrieval-degradation.html) — No fallback when filtered weak
- [Subspace Filtering](./subspace-filtering.html) — Map mismatch caused 0 chunks
- [Sticky Context](./sticky-context.html) — Context loss on generic follow-ups