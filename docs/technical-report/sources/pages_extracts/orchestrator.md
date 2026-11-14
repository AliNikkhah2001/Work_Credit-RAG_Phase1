# Orchestrator — GitHub Pages extract

Sources: `components/orchestrator/docs/{index,technical,high-level}.html`, `SUBSPACE_AMBIGUITY.md`.

## Role

LangGraph orchestration + OpenAI-compatible chat API (`:8100`). Never calls Gemma directly — generation goes through Guardrails (`POST /v1/chat/completions` → Gemma). Compiled with `MemorySaver`; exports `rag_graph` and Studio `graph` (`langgraph.json` → `studio_graph.py:graph`).

## Graph node file anchors

| Node | File / line | External call |
|---|---|---|
| validate_input | `nodes/validate_input.py:13` | Guardrails `POST /v1/rails/check` (`clients/guardrails.py:91`) |
| classify | `nodes/classify.py:67` | Guardrails `/v1/chat/completions` (`clients/guardrails.py:135`) |
| hybrid_classify | `nodes/hybrid_classify.py:67` | Guardrails `/v1/chat/completions` (SVM→Gemma escalation) |
| retrieve | `nodes/retrieve.py:851` | KB `POST /search/api` (`clients/knowledgebase.py:61`) |
| generate_clarification | `nodes/generate_clarification.py:24` | Guardrails `/v1/chat/completions` |
| build_context | `nodes/build_context.py:53` | — (numbered sources + system prompt) |
| guarded_generate | `nodes/guarded_generate.py:16` | Guardrails `/v1/chat/completions` → Gemma |
| format_response | `nodes/format_response.py:492` | — (citations + `finish_reason`) |
| format_refusal | `graph.py:109` | alias of `format_response` |

Conditional edges: `should_continue_after_validation` (`graph.py:24`), `should_route_after_classify` (`graph.py:31`), `should_clarify` (`graph.py:45`). Entity supplement short-circuits clarify. `should_clarify` also checks `subspace_ambiguity_route` + `ambiguity_ambiguous` and falls back to T5 `is_scattered_ambiguous`.

## Keyword boosts

`SUBSPACE_KEYWORD_BOOST` defaults (per-subspace BM25 bias on scoped calls):

| Subspace | Boost |
|---|---|
| cheque | 3.5 |
| facilities_person | 3.0 |
| facilities_legal | 3.0 |
| general | 2.5 |

Per-subspace evidence thresholds (T3): cheque `0.05`, facilities_person `0.10`, facilities_legal `0.15`, general `0.15`. Global `EVIDENCE_MIN_SCORE` = `0.15`.

## Sticky decay

- `STICKY_DECAY_TURNS` default **3** — consecutive generic turns before sticky subspace is dropped (B sticky decay).
- API restores sticky `applied_subspace` from MemorySaver checkpoint; when Open WebUI sends no `X-Request-ID`, mines sticky from user-only chat history (interrogatives skipped; declarations set scope).
- T4 injection applies sticky `filter_path` for generic follow-ups.

## AmbiguityResult defaults (`SUBSPACE_AMBIGUITY.md`)

Frozen interface in `src/work_rag_orchestrator/subspaces.py`. Subspaces: `cheque`, `facilities_person`, `facilities_legal`, `general`.

| Setting | Default |
|---|---|
| `subspace_ambiguity_enabled` | **True** (compute + audit) |
| `subspace_ambiguity_route` | **False** (instrument-only; does not route/clarify from score) |
| `subspace_ambiguity_margin` | **0.08** |
| `subspace_ambiguity_min_top1` | **0.30** |
| `subspace_ambiguity_entropy_max` | **0.85** |
| `subspace_softmax_temp` | 0.05 |
| `subspace_score_cache_size` | 512 |
| `subspace_protos_path` | `data/subspace_protos.npz` |
| `subspace_clf_path` | `data/subspace_clf.joblib` |

Decision: `ambiguous = (top1 < min_top1) or (margin < margin) or (entropy > entropy_max)`. Score ∈ [0,1]; higher = more ambiguous. Sources: `protos` | `classifier` | `fallback` | `disabled`.

## Embed `:8003`

- `embed_base_url` default: `http://127.0.0.1:8003`
- `embed_model`: `paraphrase-multilingual-MiniLM-L12-v2` (384-d)
- Fetched via injected embedder or `POST {embed_base_url}/v1/embeddings` (httpx, `trust_env=False`); failure → `source="fallback"`, `ambiguous=False`.

## Other config / clients

- Port `8100`; `KB_BASE_URL=http://127.0.0.1:8000`; `GUARDRAILS_BASE_URL=http://127.0.0.1:8200`
- `RETRIEVAL_TOP_K=20` (10 RRF + 10 cross-encoder union)
- `HYBRID_CLASSIFIER_ENABLED=false`; `UPSTREAM_LLM_MODEL=gemma-4-31b-triton-trt`
- Both HTTP clients use `httpx.AsyncClient(trust_env=False)` (bypass Squid for localhost)
- Tracing: Langfuse `:3001` with fallback JSONL collector `:3000`
