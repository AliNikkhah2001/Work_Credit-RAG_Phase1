# Work Credit RAG Integration Plan

This plan converts `Work_Credit-RAG_Phase1` from a monolithic prototype into the composition and release repository for four independently maintained components.

The order is dependency-driven. Phase 1 is the only immediate product goal: a minimum viable, end-to-end RAG request through all four modules and the self-hosted Gemma model.

## 0. Baseline discovered in the repositories

| Component | Existing usable capability | Gap that blocks the integrated MVP |
|---|---|---|
| Server Setup | Gemma manager at `:9000`; OpenAI-compatible `/v1/chat/completions`; Open WebUI at `:13000`; pgvector/Redis and model/embedding services | Open WebUI is not yet pointed at the orchestrator; current chat manager does not provide the RAG workflow; the documented `stream` field is not an end-to-end streaming implementation |
| Knowledgebase | KB Manager at `:8000`; ingestion/maintenance UI; current `POST /search/api`; BM25 + dense retrieval + RRF + cross-encoder reranking | The route is UI-shaped and returns only `content_preview` (300 characters); errors are JSON bodies rather than reliable HTTP error statuses; a stable versioned retrieval contract is missing |
| Guardrails | Empty repository before this integration | Implement NeMo configuration, policy API, guarded OpenAI-compatible gateway, tests, and upstream Gemma client |
| Orchestrator | Empty repository before this integration | Implement LangGraph state/nodes, KB and Guardrails clients, public OpenAI-compatible API, tests, and dependency health |
| Parent repository | Detailed monolithic architecture and prototype files | Replace duplicated implementation with submodule pins; own cross-component contracts, startup, release pins, and end-to-end verification |

## 1. MVP — one deterministic request through every module

### 1.1 Goal

From Open WebUI, send one question whose answer exists in the seeded KB and receive a grounded answer from self-hosted Gemma, with source metadata, after both input and output policy enforcement.

The successful request must traverse:

```text
Open WebUI (:13000)
  -> Work RAG Orchestrator (:8100)
  -> Work RAG Guardrails /v1/rails/check (:8200)
  -> Work RAG KB /search/api (:8000)
  -> Work RAG Guardrails /v1/chat/completions (:8200)
  -> Server Setup Gemma manager /v1/chat/completions (:9000)
  -> Orchestrator response shaping
  -> Open WebUI
```

### 1.2 Freeze the MVP ports and environment contract

| Service | Port | Required variables |
|---|---:|---|
| KB Manager | `8000` | `KB_DB_URL`, `KB_SOURCE_DIR`, `KB_WEB_HOST`, `KB_WEB_PORT=8000` |
| Orchestrator | `8100` | `KB_BASE_URL`, `GUARDRAILS_BASE_URL`, `REQUEST_TIMEOUT_SECONDS`, `RETRIEVAL_TOP_K` |
| Guardrails | `8200` | `UPSTREAM_LLM_BASE_URL`, `UPSTREAM_LLM_MODEL=gemma-4-31b`, `UPSTREAM_LLM_API_KEY` |
| Gemma manager | `9000` | existing Server Setup model registry and local token configuration |
| Open WebUI | `13000` | OpenAI base URL pointing to Orchestrator `:8100/v1`, not directly to `:9000/v1` |

On the GPU host, include `localhost`, `127.0.0.1`, Docker service names, and `host.docker.internal` in `NO_PROXY`/`no_proxy`; otherwise local calls may be sent through the corporate Squid proxy.

### 1.3 Define minimal cross-component schemas

Keep a versioned contract fixture in the parent repository and duplicate only generated client types in components.

#### Input rail check

```json
{
  "stage": "input",
  "text": "user question",
  "request_id": "uuid"
}
```

```json
{
  "allowed": true,
  "action": "allow",
  "categories": [],
  "reason": null,
  "policy_version": "mvp-1"
}
```

#### Retrieval request

Use the existing KB route for the first vertical slice:

```json
{
  "query": "standalone user question",
  "top_k": 5
}
```

The Orchestrator adapter reads `final_results`. It must tolerate the current score fields but normalize them to:

```json
{
  "chunk_id": "string",
  "document_id": "string",
  "title": "string",
  "heading": "string",
  "content": "current content_preview during MVP",
  "score": 0.0
}
```

This adapter is temporary. Phase 2 replaces it with `POST /api/v1/retrieve`, returning full bounded chunk content rather than a 300-character UI preview.

#### Public chat response

Expose `POST /v1/chat/completions` from Orchestrator so Open WebUI can use it. Preserve the OpenAI response shape and add non-breaking metadata:

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "model": "gemma-4-31b",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "answer"},
      "finish_reason": "stop"
    }
  ],
  "rag": {
    "request_id": "uuid",
    "citations": [
      {"chunk_id": "...", "document_id": "...", "title": "...", "heading": "..."}
    ]
  }
}
```

### 1.4 Implement Guardrails first

Repository: `Work_RAG-Guardrails`.

- Create a Python 3.11+ package with pinned `nemoguardrails`, FastAPI, Uvicorn, HTTPX, and Pydantic dependencies.
- Add `.env.example`; never commit the API token or internal prompts.
- Load NeMo configuration once during application lifespan; fail readiness if it cannot load.
- Implement `GET /health`, `GET /ready`, and `POST /v1/rails/check`.
- Implement `POST /v1/chat/completions` as an OpenAI-compatible guarded gateway.
- Configure the upstream OpenAI-compatible provider as Server Setup `http://127.0.0.1:9000/v1`, model `gemma-4-31b`.
- Use deterministic rails for the first slice: size/shape validation, a versioned prompt-injection regression set, internal-prompt disclosure, stable refusal text, and output secret-marker filtering.
- Return structured policy decisions in logs without logging blocked sensitive text.
- Use explicit connect/read timeouts. Do not retry blocked input. Permit at most one retry for a transient upstream connection failure.
- Fail closed on policy-engine errors. Return `502` or `503` for upstream Gemma/readiness failures rather than converting failures into normal assistant messages.

Unit tests:

- an ordinary Persian question is allowed;
- a known injection fixture is refused without calling Gemma;
- an output containing a configured secret marker is refused;
- an upstream timeout produces the documented error;
- the OpenAI-compatible response shape remains valid.

### 1.5 Implement the deterministic LangGraph orchestrator

Repository: `Work_RAG-Orchestrator`.

Use one typed state and five nodes:

1. `validate_input` — extract the latest user message and call Guardrails `/v1/rails/check`;
2. `retrieve` — call KB `POST /search/api` with `top_k=5`, normalize `final_results`;
3. `build_context` — create a bounded system/context message with numbered source IDs;
4. `guarded_generate` — call Guardrails `POST /v1/chat/completions`, which calls Gemma;
5. `format_response` — return OpenAI-compatible output with citation metadata.

Implementation constraints:

- no graph loops or LLM-decided routing;
- no query rewriting in the MVP—the latest user message is the retrieval query;
- no conversation persistence or LangGraph checkpointer yet;
- no direct Gemma call from Orchestrator;
- no direct KB database imports—the KB adapter uses HTTP;
- one request/trace ID propagated to every dependency and log entry;
- bounded prompt size and bounded retrieved chunk count;
- explicit dependency timeout and error mapping;
- non-streaming response only until correctness tests pass.

Conditional edges are limited to policy decisions:

```text
validate_input -- blocked --> format_refusal --> END
validate_input -- allowed --> retrieve --> build_context --> guarded_generate --> format_response --> END
```

Contract and integration tests:

- mock KB + mock Guardrails prove node order and request bodies;
- a blocked input never calls KB or guarded generation;
- an empty KB result still produces an explicit "insufficient evidence" answer policy;
- KB, Guardrails, and Gemma failures map to distinct status codes and logs;
- `/ready` reports dependency-by-dependency state.

### 1.6 Make the KB usable by the adapter

Repository: `Work_RAG-KB`.

For the first vertical slice, avoid rewriting the retriever. Make the current service predictable:

- add `GET /health` and `GET /ready` if absent;
- document `POST /search/api` as the temporary MVP integration route;
- seed a small deterministic corpus and record the expected `chunk_id`/question pairs;
- ensure startup pre-warm completion is represented by readiness, not only logs;
- convert invalid body, empty query, index-not-ready, and internal failures into correct `4xx`/`5xx` responses;
- add a contract test for `final_results` and its score/source fields;
- keep `top_k <= 50`, with the orchestrator default at `5`.

Known temporary limitation: `content_preview` is capped at 300 characters. The selected MVP question and seed chunk must fit that bound so the end-to-end test is valid while Phase 2 builds the proper retrieval API.

### 1.7 Wire Server Setup and the frontend

Repository: `Work_RAG-Server-Setup`.

- Keep the current Gemma manager on `:9000` as the only model-serving boundary.
- Confirm `gemma-4-31b` is loaded and `GET /health` plus a direct completion pass before starting dependent services.
- Configure Open WebUI at `:13000` to use Orchestrator `http://host.docker.internal:8100/v1` and a development key understood by Orchestrator.
- Add `extra_hosts: ["host.docker.internal:host-gateway"]` for Linux Docker when required.
- Do not point Open WebUI directly at the Gemma manager in the integrated profile; that would bypass retrieval, LangGraph, and Guardrails.
- Add an integrated/MVP compose override or profile without disturbing the existing verified server runbook.
- Retain the manager dashboard for model operations; label its playground as a direct-model diagnostic path, not the integrated RAG path.

### 1.8 Add parent-level startup and acceptance harness

Repository: `Work_Credit-RAG_Phase1`.

After component implementations exist, add:

- `compose.mvp.yml` or a clearly ordered `scripts/run-mvp.sh`;
- `contracts/` JSON schemas and golden fixtures;
- `tests/e2e/test_mvp.py`;
- a readiness wait with a bounded timeout for each service;
- one command that prints the exact component SHAs before running tests.

Startup order:

1. Server Setup infrastructure and Gemma manager;
2. KB Manager and index readiness;
3. Guardrails and upstream readiness;
4. Orchestrator and dependency readiness;
5. Open WebUI;
6. end-to-end acceptance suite.

Do not use blind sleeps. Poll readiness with deadlines and print the failing dependency.

### 1.9 MVP acceptance criteria

The MVP is complete only when all of these pass from a clean recursive clone:

- `git submodule status --recursive` reports all pinned modules initialized and clean;
- all five service health endpoints respond;
- the orchestrator readiness endpoint confirms KB and Guardrails, while Guardrails confirms Gemma;
- a known Persian KB question returns HTTP `200`, a non-empty answer, and at least one citation matching the seeded expected document;
- server logs prove the request reached Orchestrator, KB, Guardrails, and Gemma with the same request ID;
- a known prompt-injection fixture is refused and produces no KB or Gemma call;
- stopping KB yields a documented dependency error rather than an ungrounded model answer;
- stopping Gemma yields a documented Guardrails/upstream error rather than a fake success;
- Open WebUI reaches Orchestrator, not the direct model manager;
- no credentials, raw internal prompts, or complete blocked user text appear in logs;
- one command produces a red/green end-to-end result and exits non-zero on failure.

## 2. Stable contracts and retrieval correctness

Begin only after Phase 1 is green.

### 2.1 Version the KB retrieval API

Add `POST /api/v1/retrieve` with typed request/response models. Return full bounded chunk text, not UI previews, plus:

- stable document/chunk IDs;
- title, heading path, and source URI;
- document and index version;
- BM25, dense, fusion, and reranker scores;
- language/domain/access metadata;
- latency breakdown and retrieval configuration version.

Remove the synchronous event-loop wrapper from the service path and keep retrieval async. Use proper exception handlers and status codes. Keep `/search/api` for the KB UI until it can migrate.

### 2.2 Freeze generated clients and compatibility tests

- Publish OpenAPI documents or JSON Schema from KB, Guardrails, and Orchestrator.
- Generate or hand-maintain small typed clients only at repository boundaries.
- Add provider tests in each component and consumer contract tests in Orchestrator.
- Introduce a compatibility matrix in the parent repository before advancing submodule pins.

### 2.3 Grounding and citation enforcement

- Pass full source IDs into the prompt with unambiguous delimiters.
- Require the answer to reference only supplied source IDs.
- Validate cited IDs deterministically after generation.
- Separate "no evidence" from service failure.
- Add answer/citation fixtures for Persian and English.

## 3. Streaming, persistence, and conversation continuity

### 3.1 Streaming

- Verify actual upstream streaming support from the Gemma manager.
- Implement SSE in Guardrails without skipping output policy semantics.
- Stream structured events from Orchestrator: metadata, token deltas, citations, completion, and error.
- Test client disconnect/cancellation and ensure abandoned generation is cancelled upstream.

### 3.2 Durable conversation state

- Make PostgreSQL the canonical user-visible transcript store.
- Map `conversation_id` to LangGraph `thread_id`.
- Add `langgraph-checkpoint-postgres` for graph execution state.
- Keep Redis ephemeral: cache, rate limit, locks, and transient stream state only.
- Verify continuation after Orchestrator restart.
- Add deletion/export paths without exposing LangGraph checkpoint tables to the frontend.

### 3.3 Context management

- exact recent-message window;
- rolling summary with provenance;
- token-aware context allocation across instructions, history, retrieval, and output reserve;
- same-conversation recall before cross-conversation memory;
- explicit source priority for "what did I say earlier?" questions.

## 4. Controlled retrieval intelligence

- Add query rewriting while keeping original and retrieval queries separate.
- Add deterministic context sufficiency checks before any LLM grader.
- Permit at most two retrieval attempts with recorded retry reasons.
- Introduce metadata filtering and access-control filters before retrieval.
- Compare hybrid/reranker configurations with the KB golden dataset.
- Add an "insufficient evidence" terminal path instead of forcing Gemma to answer.

No unbounded loops or open-ended tool selection are allowed.

## 5. Evaluation and observability

### 5.1 End-to-end metrics

Measure each boundary separately:

- input/output rail decision, category, policy version, and latency;
- KB BM25/dense/rerank latency, candidate counts, hit rate, MRR, and nDCG;
- Orchestrator node duration, transitions, failure category, and total latency;
- Gemma time to first token, generation latency, model ID, and backend;
- answer faithfulness, citation precision/recall, refusal correctness, and no-evidence correctness.

### 5.2 Trace correlation

- propagate `request_id`, `conversation_id`, and trace context across HTTP calls;
- emit structured logs without secret or prompt leakage;
- connect LangGraph/LLM traces to Langfuse;
- expose Prometheus metrics and build a Grafana cross-service dashboard;
- retain the exact four submodule SHAs with every evaluation run.

### 5.3 Regression gates

- retrieval golden set in KB;
- safe/unsafe policy set in Guardrails;
- graph route/error fixtures in Orchestrator;
- Persian grounded QA and adversarial end-to-end set in the parent repository;
- latency and quality thresholds that block a submodule-pin update when they regress.

## 6. Production hardening

- require authentication at the public Orchestrator boundary;
- use service-to-service credentials and rotate the current development token;
- add authorization metadata filters to KB retrieval;
- define fail-open/fail-closed behavior per rail and dependency explicitly;
- set request-size, rate, concurrency, and token limits;
- add idempotency keys where a retry could duplicate persistence;
- use circuit breakers and bounded retries, never nested retry storms;
- pin container images and Python dependencies; generate SBOMs and scan them;
- add backup/restore tests for PostgreSQL and KB artifacts;
- document degraded modes and recovery order;
- validate cold restart on the actual H200 host behind the proxy;
- add Kubernetes only after the single-host integrated profile is reliable.

## 7. Submodule delivery workflow

For every cross-component change:

1. change and test the owning component repository;
2. merge the component PR;
3. update exactly one parent gitlink;
4. run contract tests and the parent end-to-end suite against all pinned SHAs;
5. merge the parent PR only when the compatibility matrix is green;
6. tag the parent repository as the integrated release manifest.

Avoid branch-tracking automation in production. `.gitmodules` records the intended branch for maintainers, but the parent gitlink SHA is the reproducible source of truth.

## 8. Definition of done by phase

| Phase | Exit condition |
|---|---|
| 0 — Composition | Four valid gitlinks, recursive clone works, duplicated monolith removed, ownership documented |
| 1 — MVP | One safe, grounded, cited question and one blocked attack pass end-to-end through all modules |
| 2 — Contracts | Versioned retrieval API, full chunks, typed compatibility tests, validated citations |
| 3 — Conversation | Streaming and restart-safe conversation continuity pass |
| 4 — Retrieval intelligence | Bounded rewrite/retry behavior improves measured retrieval without unsafe loops |
| 5 — Evaluation | Cross-service traces and quality/security gates protect every release-pin update |
| 6 — Production | Auth, authorization, limits, backups, recovery, and clean H200 cold restart are verified |
