---
layout: default
title: "Our Implementation - Multi-Turn RAG Research"
description: "T1-T8 fixes, code pointers, benchmark deltas, deployment notes, and remaining gaps"
---

<div class="page-header">
  <h1>Our Implementation</h1>
  <p class="lead">T1-T8 fixes, code pointers, benchmark deltas, deployment notes, and remaining gaps</p>
</div>

## Overview

This page documents the complete implementation of fixes T1-T8 applied to the Work Credit RAG system, with code pointers, benchmark results, and deployment notes.

---

## Fix Summary

| Fix | Description | Status | Files Modified |
|-----|-------------|--------|----------------|
| **Map Fix** | `subspace_map["cheque"] = "گزارش اعتباراتنجی چک"` | ✅ | `config.py:34` |
| **T1: RRF Fusion** | Filtered + whole-KB RRF fusion (1.3x filtered weight) | ✅ | `retrieve.py:143` |
| **T2: Broadened Retry** | top_k=30, keyword_boost=1.5, fused | ✅ | `retrieve.py:220`, `clients/knowledgebase.py:61` |
| **T3: Per-Subspace Threshold** | cheque=0.05, person=0.10, legal/general=0.15 | ✅ | `config.py:44`, `format_response.py:247` |
| **T4: Sticky Carry** | Generic follow-ups inherit filter_path | ✅ | `api.py:386`, `retrieve.py:1125` |
| **T5: Scattered Gate** | `is_scattered_ambiguous()` → clarify | ✅ | `infer_specification.py:24`, `classify.py:86`, `graph.py:37` |
| **T6: Lexical Bypass** | `_has_lexical_evidence()` keeps chunks | ✅ | `format_response.py:279`, `retrieve.py:70` |
| **T7: Observability** | fallback_used, broaden_used, retry_stage_timing | ✅ | `dashboard_api.py`, `eval_store.py`, `observability.html` |
| **F: Faith Guard** | Coverage+score guard on weak evidence | ✅ | `format_response.py:483` |
| **C: GPU KB** | `cuda:0` embed + rerank, pool 30 | ✅ | KB env vars |

---

## Code Pointers

### Config (`config.py`)

```python
# Per-subspace evidence thresholds
evidence_min_score: float = 0.15
evidence_min_score_cheque: float = 0.05
evidence_min_score_facilities_person: float = 0.10
evidence_min_score_facilities_legal: float = 0.15
evidence_min_score_general: float = 0.15

def get_evidence_threshold(self, applied_subspace: str|None) -> float:
    s = (applied_subspace or "").strip()
    if not s: return 0.15
    if "چک" in s or s == "cheque": return 0.05
    if "حقیقی" in s or s == "facilities_person": return 0.10
    if "حقوقی" in s or s == "facilities_legal": return 0.15
    if "عمومی" in s or s == "general": return 0.15
    return 0.15

# Per-subspace keyword boost
subspace_keyword_boost: dict = {
    "cheque": 3.5,
    "facilities_person": 3.0,
    "facilities_legal": 3.0,
    "general": 2.5
}

# Sticky decay
sticky_decay_turns: int = 3
```

### Retrieve Node (`retrieve.py`)

```python
# RRF Fusion
def _fuse_subspace_rrf(filtered, whole, filtered_weight=1.3):
    merged = {}
    for rank, chunk in enumerate(filtered):
        key = chunk.chunk_id
        score = filtered_weight / (60 + rank + 1)
        merged[key] = max(merged.get(key, 0), score)
    for rank, chunk in enumerate(whole):
        key = chunk.chunk_id
        score = 1.0 / (60 + rank + 1)
        merged[key] = max(merged.get(key, 0), score)
    return sorted(merged.values(), key=lambda x: x.fused_score, reverse=True)[:20]

# T1: Whole-KB Fallback with Fusion
async def _t1_try_whole_kb_fallback(state, search_query, request_id, active_filter):
    fb_result = await fb_client.retrieve(search_query, top_k, request_id, filter_path=None)
    if fb_result:
        state["retrieved_chunks"] = _fuse_subspace_rrf(current, fb_result)[:20]
        state["fallback_used"] = True
        state["fallback_reason"] = f"low_score top={cur_top:.4f} < thr={thr:.3f} | fused rrf"

# T2: Broadened Retry
async def _t2_try_broadened_retry(state, search_query, request_id, top_k=30, keyword_boost=1.5):
    fb_result = await client.retrieve(search_query, 30, request_id, filter_path=None, keyword_boost=1.5)
    if fb_result:
        state["retrieved_chunks"] = _fuse_subspace_rrf(previous, fb_result)[:20]
        state["broaden_used"] = True

# T5: Scattered Gate
def is_scattered_ambiguous(query):
    has_vague = any(v in q for v in SCATTERED_VAGUE_PHRASES)
    has_subspace = any(kw in q for kw in SCATTERED_SUBSPACE_KWS)
    if has_vague and not has_subspace: return True
    if len(tokens) <= 6 and not has_subspace and any(w in q for w in SCATTERED_GENERIC_WORDS):
        return True
    return False
```

### API Sticky Logic (`api.py`)

```python
# Sticky carry + decay
def build_initial_state(request):
    # Load checkpoint
    sticky_applied = checkpoint.get("applied_subspace")
    
    # Count generic turns
    generic_turns = count_generic_turns(request.messages)
    if generic_turns > settings.sticky_decay_turns:
        sticky_applied = None  # Decay!
    
    # Inject filter_path from sticky
    if not request.filter_path and sticky_applied and not is_explicit_respec(query):
        filter_path = settings.subspace_map.get(sticky_applied)
```

### Format Response (`format_response.py`)

```python
# T6: Lexical Evidence Bypass
def _has_lexical_evidence(query, chunks, applied_subspace):
    keywords = set()
    if "چک" in applied_subspace: keywords.update(["چک"])
    # ... add query tokens len>=2
    corpus = " ".join(c.get("content", "") for c in chunks[:10])
    return any(kw in corpus for kw in keywords)

# F: Faith Guard
if (fallback_used or broaden_used) and ABSTENTION_PHRASE not in content:
    used_top = _top_evidence_score(chosen_chunks)
    coverage = _token_coverage(content, chosen_chunks)
    if used_top < 0.5 and coverage < 0.20:
        content = NO_EVIDENCE_MSG
        citations = []
        log.info(f"Faith guard fired: coverage={coverage:.3f}")
```

---

## Deployment Notes

### Services

| Service | Port | Command |
|---------|------|---------|
| Gemma (llama-server) | 18000 | `llama-server -m /path/gemma-4-31B-it-UD-Q4_K_XL.gguf --port 18000 --ctx-size 8192 --temp 0.2 --no-mmproj --jinja -ngl 999` |
| KB Manager | 8000 | `KB_DB_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/kb_manager KB_EMBED_DEVICE=cuda:0 KB_RERANKER_DEVICE=cuda:0 KB_RERANK_POOL=30 python -m uvicorn kb_manager.web.app:app --host 0.0.0.0 --port 8000` |
| Guardrails | 8200 | `UPSTREAM_LLM_BASE_URL=http://127.0.0.1:9000/v1 UPSTREAM_LLM_MODEL=gemma-4-31b python -m uvicorn work_rag_guardrails.api:create_app --factory --host 0.0.0.0 --port 8200` |
| Orchestrator | 8100 | `UPSTREAM_LLM_MODEL=gemma-4-31b PYTHONPATH=components/orchestrator/src python -m uvicorn work_rag_orchestrator.api:create_app --factory --host 0.0.0.0 --port 8100` |
| WebUI | 13000 | `OPENAI_API_BASE_URL=http://127.0.0.1:8100/v1 OPENAI_API_KEY=sk-local-dev WEBUI_AUTH=false python -m open_webui.main --host 0.0.0.0 --port 13000` |
| Collector | 3000 | `python -m uvicorn app:app --host 0.0.0.0 --port 3000` |
| LLM Manager | 9000 | `uvicorn llm_inference_manager.app:app --host 0.0.0.0 --port 9000` |

### GPU KB Restart

```bash
fuser -k 8000/tcp
KB_DB_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/kb_manager" \
KB_EMBED_DEVICE=cuda:0 KB_RERANKER_DEVICE=cuda:0 KB_RERANK_POOL=30 \
nohup /tmp/kb-venv/bin/python -m uvicorn kb_manager.web.app:app --host 0.0.0.0 --port 8000 > /tmp/kb.log 2>&1 &
sleep 30
curl -s http://127.0.0.1:8000/health | jq '.db_mode, .doc_count, .chunk_count'
```

---

## Remaining Gaps & Future Work

| Priority | Gap | Proposed Solution | Effort |
|----------|-----|-------------------|--------|
| **1** | Static `subspace_map` | Learned router from training queries (SPLIT-RAG) | Medium |
| **2** | Single-shot clarify | Iterative clarify-rewrite loop (ICR) | Medium |
| **3** | No cross-session memory | CALMem semantic layer + CPP segmentation | High |
| **4** | Fixed 2-step fallback | Iterative retrieval (CoRAG/IM-RAG) | High |
| **5** | Separate retriever/generator | Cooperative components (CoopRAG) | High |
| **6** | Modular pipeline | Joint optimization (MMOA-RAG) | High |
| **7** | Faith guard | Self-evaluation (Reflective RAG) | Medium |
| **8** | Evidence score | Calibrated confidence (CalibRAG) | Medium |
| **9** | Bounded context | CALMem/CPP hierarchical context | High |

---

## Validation Checklist

- [x] Map fix: cheque filter returns 10 chunks @ 0.863 rerank
- [x] T1 RRF fusion: filtered + whole-KB fused
- [x] T2 broadened: top_k=30, boost=1.5
- [x] T3 thresholds: cheque 0.05, person 0.10
- [x] T4 sticky: generic follow-ups carry filter_path
- [x] T5 clarify: 6/6 scattered queries now clarify
- [x] T6 lexical: rerank 0.0 but text match → keep chunks
- [x] T7 observability: fallback/broaden badges on dashboard
- [x] F faith guard: coverage+score check on weak evidence
- [x] C GPU KB: dense 19ms, rerank 52ms, total 70ms
- [x] Benchmark: 41 turns, 0 finish mismatches, hit 0.78

---

## Related Pages

- [Benchmarks](../benchmarks.html) — Full benchmark results
- [Problems](../problems/index.html) — Root causes
- [Papers & Solutions](../papers/index.html) — Academic backing
- [Architectures](../architectures.html) — System diagrams