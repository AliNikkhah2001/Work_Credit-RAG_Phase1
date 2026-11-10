# System architecture and request-to-response

## Section summary

Retrieval, policy, orchestration, and generation are separate processes with stable ports. The high-level figures show the boxes a new engineer needs. The detailed figures map those boxes onto LangGraph nodes, KB routes, and the Gemma gateway. The walkthrough below follows one chat completion from WebUI to citations, with the published budgets for sticky memory, context, evidence, and ambiguity.

## Request path

A production turn uses one hop list. The browser talks only to Open WebUI on `:13000`. WebUI posts an OpenAI-shaped chat completion to the orchestrator on `:8100`. The orchestrator calls guardrails on `:8200` for the input rail (`POST /v1/rails/check`), then the knowledge base on `:8000` (`POST /search/api` with `top_k=20`, and `POST /search/supplement` at threshold **0.4**). `build_context` packs at most **`MAX_CHUNKS` = 20** chunks inside a context budget of **`MAX_CONTEXT` = 9000**. Generation returns through guardrails `POST /v1/chat/completions`. Guardrails is the only service that calls Gemma, through the H200 LLM Inference Manager on `:9000`. Citations and `finish_reason` go back through the orchestrator to WebUI. Traces go to Langfuse on `:3001` or the JSONL collector on `:3000`. LangGraph Studio listens on `:2024` and requires `request_id` on every run input.

Sticky subspace memory is checkpointed with `MemorySaver`. `STICKY_DECAY_TURNS` defaults to **3**: after three consecutive generic follow-ups the sticky subspace is dropped. If the best evidence score is below **0.15**, the turn abstains. Per-subspace floors can be lower than that global `EVIDENCE_MIN_SCORE`; chapter 5 lists them.

`AmbiguityResult` is computed in `subspaces.py` with three defaults that define the current product behavior. `subspace_ambiguity_enabled` is **true** (compute the score and keep it for audit). `subspace_ambiguity_route` is **false** (instrument only: the score does not route and does not by itself clarify). `subspace_ambiguity_margin` is **0.08**. The scattered-query check can still open a clarification, and an entity supplement still short-circuits that branch. The remaining thresholds (minimum top-1, entropy cap, softmax temperature) are in chapter 5.

## High-level system overview

![High-level system overview](../assets/diagrams/01_system_overview_hl.png)

**Figure 1. High-level system overview.** The browser reaches Open WebUI on `:13000`, which forwards OpenAI-shaped chat calls to the orchestrator on `:8100`. The orchestrator coordinates the knowledge base (`:8000`) for evidence and guardrails (`:8200`) for both input adjudication and generation. Observability collectors sit beside the path rather than inside the user loop. This view hides LangGraph node names so a reader can see ownership boundaries before opening Python modules.

## Detailed system overview

![Detailed system overview](../assets/diagrams/02_system_overview_detail.png)

**Figure 2. Detailed system overview.** Expanding the orchestrator box shows `validate_input`, `classify`, `retrieve`, `build_context`, `guarded_generate`, and `format_response` as wired in `components/orchestrator/src/work_rag_orchestrator/graph.py`. The knowledge base exposes `POST /search/api` (BM25, dense retrieval, RRF, cross-encoder rerank) and `POST /search/supplement` for EntityList rows. Guardrails exposes `POST /v1/rails/check` and `POST /v1/chat/completions`, proxying Gemma through the manager on `:9000` only when generation is allowed. Embedding traffic for the ambiguity head targets MiniLM on `:8003`. This diagram recreates the parent technical-page “Variant A” overview for the report template.

## Request flow (high level)

![High-level request sequence](../assets/diagrams/03_request_flow_hl.png)

**Figure 3. Sticky filtered RAG — high-level sequence.** A user question becomes a chat completion. Input rails may refuse before any retrieval. Otherwise hybrid search returns chunks and, when entity lists match, supplemental rows. Guarded generation calls the model through guardrails and returns through output rails. Citations are assembled before the answer reaches WebUI. Sticky decay (three generic turns), the 0.15 evidence floor, and the 20-chunk / 9000 context budget are omitted from this black-box picture and appear in the detailed sequence.

## Request flow (detailed)

![Detailed request sequence](../assets/diagrams/04_request_flow_detail.png)

**Figure 4. Sticky filtered RAG — detailed sequence.** After `start_trace`, the orchestrator calls the guardrails input check. Classification routes greetings and specifications away from retrieval. Questions call `KnowledgebaseClient.retrieve` (`clients/knowledgebase.py`), which posts to `/search/api` with optional `filter_path` and a per-subspace `keyword_boost`. When entity keywords match, `supplementary_search` posts to `/search/supplement` at threshold 0.4. `should_clarify` in `graph.py` skips clarification when `supplemental` or `injected_entities` are present. Continuing turns run `build_context` under `MAX_CHUNKS=20` and `MAX_CONTEXT=9000`, abstain when evidence is below 0.15, then call guarded generate and `format_response`. Sticky `applied_subspace` is restored from the `MemorySaver` checkpoint and decays after three generic turns.

## End-to-end walkthrough

1. **Ingress.** WebUI sets `OPENAI_API_BASE_URL=http://127.0.0.1:8100/v1`. Sticky threads use `X-Request-ID` / `request_id`. Studio runs must include `request_id`. When WebUI sends no request id, the API mines sticky scope from user-only chat history: interrogatives are skipped and declarations set scope.
2. **Validate.** `nodes/validate_input.py` calls Guardrails `POST /v1/rails/check` with `stage=input`. A block sets `blocked` and routes to `format_refusal`.
3. **Classify.** `nodes/classify.py` labels greeting, specification, or question. Specifications lock subspace language that later becomes `filter_path`. Optional `hybrid_classify` stays off unless `HYBRID_CLASSIFIER_ENABLED` is set.
4. **Retrieve.** `nodes/retrieve.py` may rewrite coreference, apply sticky subspace with decay 3, search the KB, merge the RRF and cross-encoder pools (`RETRIEVAL_TOP_K=20`), fire the entity supplement, and score evidence. A filtered miss can retry once over the whole KB.
5. **Clarify or build.** `should_clarify` asks a question via `generate_clarification` for scattered ambiguity when no subspace is applied. The ambiguity *score* is recorded (`enabled=true`) and does not drive this edge while `subspace_ambiguity_route` remains false and the margin stays 0.08. Entity hits skip clarification. Otherwise `build_context.py` assembles the Persian system prompt, at most 20 chunks, history, and trimmed entity JSON inside the 9000 context budget.
6. **Generate.** `guarded_generate` posts to Guardrails. It never opens a socket to Gemma. Upstream cleanup strips leaked special tokens (`enable_thinking` stays false on the server).
7. **Format.** Citations and finish reasons match the OpenAI response schema. Audit fields and timings attach on non-streaming responses.

## Orchestrator graph figures

![Orchestrator graph high level](../assets/diagrams/05_orch_graph_hl.png)

**Figure 5. Orchestrator graph — high level.** Validate, classify, retrieve, optional clarify, generate, and format form one directed path with refusal and clarification exits. Operators can read latency off this picture: once the KB is warm, most wall time sits in retrieve-plus-generate, not in classify. Sticky bookkeeping and the instrument-only ambiguity score are state on the edges, not extra nodes.

![Orchestrator graph detailed](../assets/diagrams/06_orch_graph_detail.png)

**Figure 6. Orchestrator graph — detailed.** Node names match `create_graph()` in `graph.py`. The conditional edges are `should_continue_after_validation` (`graph.py:24`), `should_route_after_classify` (`graph.py:31`), and `should_clarify` (`graph.py:45`). `should_clarify` short-circuits when an entity supplement is present, consults `subspace_ambiguity_route` together with `ambiguity_ambiguous` (a no-op for routing while the route flag is false), and falls back to the scattered-query check. File and line anchors for every node are tabulated in chapter 5.
