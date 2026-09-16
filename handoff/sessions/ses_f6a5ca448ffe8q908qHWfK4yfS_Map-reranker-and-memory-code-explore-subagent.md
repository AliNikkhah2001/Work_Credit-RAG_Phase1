# Map reranker and memory code (@explore subagent)

Session: `ses_f6a5ca448ffe8q908qHWfK4yfS`
Messages: 7


## [USER]

Read-only research in two repos. DO NOT write, edit, restart, or modify anything. Only read files and report.

REPO 1 — /workspace/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager:
1. Read kb_manager/reranker.py fully: class names, model loading (which model id, revision pin?), rerank() signature, batching, device handling (CPU/CUDA?), max length/truncation.
2. In kb_manager/web/routes/search.py: how many candidates go to the reranker (top-K?), how rerank scores fuse with BM25/dense (RRF? weights?), what `final_results` contains (score fields), and any latency measurement/logging around reranking.
3. Check for any other rankers/scorers (e.g. dense.py model, BM25 params) and config knobs (env vars) controlling rerank depth.

REPO 2 — /workspace/Work_Credit-RAG_Phase1/components/orchestrator/src/work_rag_orchestrator:
1. Trace exactly how conversation history flows: api.py initial_state `messages`, what validate_input/retrieve/build_context each consume (last message only? full history?). Quote the relevant lines.
2. Confirm whether ANY node passes prior turns to the LLM prompt or to KB search. Check graph.py edges for loops/memory.
3. Check Studio/prompt: does prompt_messages include history?

Return a concise structured report: (A) reranker model id + candidate depth + fusion + device + latency notes; (B) memory verdict with file:line evidence for statelessness (what happens to turn 1 when turn 2 arrives).


## [ASSISTANT]

(step-start: {"snapshot": "7046ff37a2f2e446834298a4c4e842f4e729b8f6", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: read)

(tool: read)

(tool: glob)

(step-finish: {"reason": "tool-calls", "snapshot": "7046ff37a2f2e446834298a4c4e842f4e729b8f6", "type": "step-finish", "tokens": {"total": 7092, "input": 5239, "output": 253, "reasoning": 207, "cache": {"write": 0, "read": 1393}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "7046ff37a2f2e446834298a4c4e842f4e729b8f6", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "7046ff37a2f2e446834298a4c4e842f4e729b8f6", "type": "step-finish", "tokens": {"total": 15628, "input": 8527, "output": 539, "reasoning": 49, "cache": {"write": 0, "read": 6513}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "7046ff37a2f2e446834298a4c4e842f4e729b8f6", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: grep)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "7046ff37a2f2e446834298a4c4e842f4e729b8f6", "type": "step-finish", "tokens": {"total": 24154, "input": 8686, "output": 441, "reasoning": 66, "cache": {"write": 0, "read": 14961}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "7046ff37a2f2e446834298a4c4e842f4e729b8f6", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: grep)

(tool: grep)

(tool: read)

(tool: glob)

(step-finish: {"reason": "tool-calls", "snapshot": "7046ff37a2f2e446834298a4c4e842f4e729b8f6", "type": "step-finish", "tokens": {"total": 33172, "input": 9115, "output": 435, "reasoning": 85, "cache": {"write": 0, "read": 23537}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "7046ff37a2f2e446834298a4c4e842f4e729b8f6", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: read)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "7046ff37a2f2e446834298a4c4e842f4e729b8f6", "type": "step-finish", "tokens": {"total": 35643, "input": 2851, "output": 150, "reasoning": 17, "cache": {"write": 0, "read": 32625}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "7046ff37a2f2e446834298a4c4e842f4e729b8f6", "type": "step-start"})

(reasoning: )

(reasoning: )

## (A) Reranker — KB (`kb-manager`)

**Model ID:** `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
- `kb_manager/reranker.py:16` (`_DEFAULT_MODEL`), `kb_manager/web/routes/search.py:27` (`_RERANKER_MODEL`).
- Docstring at `reranker.py:3` claims `mDeBERTa-v3-base-xsmall` — stale/wrong, code uses MiniLM.
- **No revision pin:** `AutoTokenizer/Model.from_pretrained(model_name)` at `reranker.py:63-66` passes no `revision=`.

**Class/API:** `CrossEncoderReranker` (`reranker.py:20`), factory `get_reranker()` (`:173`). Signature `rerank(self, query: str, candidates: List[dict], top_k=10, score_key="hybrid_score")` (`:86-92`). Returns top-k sorted by `rerank_score` desc, mutating dicts with `cand["rerank_score"]=float(score)` (`:128-132`).

**Candidate depth (two caps):**
1. `search.py:28`: `_RERANKER_TOP_K = 50`; `search.py:396`: `rerank_input = candidates[:50]`.
2. `reranker.py:112-116`: `rerank_pool = sorted(candidates, key=hybrid_score)[:min(top_k*3, len)]`. Effective scored pool = `min(50, top_k*3)` → 15 when orchestrator `top_k=5`, 30 when KB default `top_k=10`. BM25 and dense legs each fetch `top_k*3` (`search.py:318,340`).

**Fusion:** RRF over 2 legs, **no weights**. `search.py:359-371`: `ranked_lists=[bm25_raw, dense_raw]`, `rrf_score=1.0/(60+rank+1)` (`k=60`), summed into `hybrid_score`. Cross-encoder then **discards** hybrid — pure re-sort by `rerank_score` (`reranker.py:131`). Short-query fallback `search.py:402-410`: if `max(rerank_score)<0.2 and tokens<=4 and bm25 non-empty` → replace with `bm25_results[:top_k]`, `rerank_score=bm25_score`.

**`final_results` (`search.py:185-196`):** `chunk_id, doc_id, doc_title, heading_path, content_preview ([:300]), bm25_score, semantic_score (=dense copy), dense_score, hybrid_score (RRF, 6dp), rerank_score, ordinal`. Orchestrator keeps only `content_preview` as `content` and `score=rerank_score or hybrid_score` (`orchestrator/clients/knowledgebase.py:83-92`).

**Device/batching/truncation:** `device: Optional[str]=None`, `batch_size=32`, `max_length=512` (`reranker.py:28-33`). `_ensure_model (:47-75)`: `float16` unless `device=="cpu"`, `.to(device)` or auto `cuda if available else cpu`; same auto-move for inputs (`:151-155`). Tokenizer `padding+truncation, max_length=512` (`:142-149`). Lazy load on first `rerank()` (`:108`), then cached in `_index_cache` with BM25+dense (`search.py:260,264`).

**Latency:** No rerank-specific timer/log. Only full-pipeline `start=time.monotonic()` (`search.py:311`) → `elapsed=(monotonic-start)*1000` (`:416`) → `SearchSteps.elapsed_ms` (`:428`).

**Other scorers / knobs:**
- Dense: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (`dense.py:21`, `search.py:26`), batch 64, L2-norm cosine, Anthropic-style `Title/Heading/Content` prefix, disk cache `data/dense_embeddings.npz` + fingerprint.
- BM25: custom `BM25(k1=1.5, b=0.75)` (`search.py:101`), Persian normalize + 3-grams + stopwords (`:72-91`), keyword 3× boost (`:238`).
- **No env knobs for rerank depth:** `_RERANKER_TOP_K/_RERANKER_MODEL/_DENSE_MODEL` are hardcoded constants; grep finds no `getenv` for them. Only orchestrator-side `retrieval_top_k=5` (`orchestrator/config.py:30`, used `nodes/retrieve.py:45`).

## (B) Memory verdict: STATELESS (no conversation memory)

| Stage | Evidence |
|---|---|
| Ingress | `api.py:134-136`: `initial_state={"messages": request.messages, ...}` passes full list through, but `api.py:123`: tracing takes only `request.messages[-1]`; `api.py:155`: `config={"thread_id": request_id}` with fresh `uuid4` per request (`:118`) → `MemorySaver` checkpoint (`graph.py:65`) never reused across turns. |
| `validate_input` | `nodes/validate_input.py:23,30-31`: `user_messages=[m ... if role=="user"]; query=user_messages[-1]["content"]; state["query"]=query` — all prior turns dropped. Guardrails check gets only `query` (`:36`). |
| `retrieve` | `nodes/retrieve.py:21,43,48`: `query=state["query"]` → `search_query=norm_query` → `client.retrieve(search_query,...)` — KB sees singl
…[truncated]…

(step-finish: {"reason": "stop", "snapshot": "7046ff37a2f2e446834298a4c4e842f4e729b8f6", "type": "step-finish", "tokens": {"total": 38972, "input": 491, "output": 1734, "reasoning": 1306, "cache": {"write": 0, "read": 35441}}, "cost": 0})
