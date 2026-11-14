---
name: rag-orchestrator
description: >-
  Implements or debugs Work_RAG-Orchestrator LangGraph RAG flow: classify,
  retrieve, clarify, build_context, guarded_generate, sticky subspaces,
  entity supplements. Use when editing components/orchestrator.
---

# RAG Orchestrator skill

## Own only

`components/orchestrator` → `Work_RAG-Orchestrator` `main`.

## Graph

Defined in `src/work_rag_orchestrator/graph.py`:

1. `validate_input` → Guardrails rails check  
2. `classify` → greeting / specification / question  
3. optional `hybrid_classify` (SVM→Gemma; off by default)  
4. `retrieve` — rewrite, sticky subspace, `filter_path`, KB search, FAQ, entity tool  
5. `should_clarify` — **skips clarify if `supplemental` / `injected_entities`**  
6. `build_context` — MAX_CHUNKS=20, MAX_CONTEXT_CHARS=14000, `prompt_char_budget`, entity section ≤4000  
7. `guarded_generate` → Guardrails chat  
8. `format_response` — citations, evidence thresholds per subspace  

Never call Gemma directly from nodes — always Guardrails.

## Critical helpers

| Helper | Where | Role |
|---|---|---|
| `trim_supplemental` | `nodes/retrieve.py` | Cap entity JSON (top-3 lists × 4KB, code-token weighting) |
| `KnowledgebaseClient.supplementary_search` | `clients/knowledgebase.py` | Probe `/search/supplement` (+fallbacks) |
| `compact_history` | `context_compact.py` | Rolling summary when ~4500 tokens |
| `get_evidence_threshold` | `config.py` | Per-subspace min scores |

## Subspaces

`cheque` / `facilities_person` / `facilities_legal` / `general` — sticky + keyword boost + Persian `filter_path` mapping in `config.subspace_map`.

## Local HTTP

All clients: `trust_env=False`, timeout 120s. Studio runs **must** include `request_id`.

## Verify

```bash
curl -s http://127.0.0.1:8100/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"اعتبارسنجی چیست؟"}]}' \
  | jq -c '{finish:.choices[0].finish_reason, citations:(.rag.citations|length)}'
```
