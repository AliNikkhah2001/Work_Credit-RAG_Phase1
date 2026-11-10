## 8. Logging, Telemetry, Documentation & Latency

**Section summary.** Work Credit RAG treats observability as a *layered* contract: KB returns per-stage `stage_ms` (also Redis-cached); the orchestrator rolls node timings into `stage_timing_ms` and an optional `AuditTrail`; Langfuse v2 (or host JSONL) records spans; `components/tracing` persists SQLite + JSONL pipeline cards; guardrails and the inference manager keep their own stores. Operators read that stack at three ports: Langfuse v2 on **:3001**, the parent fallback collector on **:3000**, and LangGraph Studio on **:2024**. Studio run inputs must include `request_id`; without it, sticky memory and trace envelopes have nothing to join on. E2E latency is dominated by **generation**, not retrieval—warm KB search is tens of milliseconds while chat turns sit near five seconds—so optimizations favor RAM-first retrieval, context trim, and TRT-LLM serving over further BM25 micro-cuts.

### 8.1 Multi-layer telemetry map

| Layer | What is recorded | Primary sink |
|---|---|---|
| KB search | `bm25` / `dense` / `rrf` / `rerank` / `total` (+ `hyde`, `build_context`) | Response JSON + Redis TTL 600s |
| Orchestrator | Node wall times → `stage_timing_ms` | `AuditTrail` on non-streaming chat |
| Distributed traces | Trace + span envelopes (Langfuse v2 HTTP) | Langfuse UI `:3001` or collector `:3000` |
| Pipeline store | Enriched request/response cards | `/tmp/observability.db` + `/tmp/pipeline_traces.jsonl` |
| Guardrails | Decision events (PII-masked) | `/tmp/guard_events.jsonl` + dashboard `:8200` |
| Manager | Session / latency / backend metrics | `manager.db` (SQLite) |
| Retrieval DLQ | Empty filtered retrieval | `/tmp/dlq_retrieval.jsonl` |

![Figure 15 — Observability wiring](../assets/diagrams/15_observability.png)

*Figure 15. Observability wiring for the production stack. The orchestrator emits `stage_timing_ms` into AuditTrail and posts Langfuse v2 `trace-create` / `span-create` envelopes (fire-and-forget HTTP also feeds `/tmp/langfuse_traces.jsonl` when the collector on `:3000` is the active sink). KB returns `stage_ms` to callers and Redis (TTL 600s) so Search UI can replay timing. Guardrails append masked decisions to `guard_events.jsonl` for the `:8200` dashboard; the manager plane keeps `manager.db` metrics for Prometheus/Grafana. “Where did the time go?” requires joining these stores, not a single APM.*

![Figure 16 — Observability high-level](../assets/diagrams/16_obs_hl.png)

*Figure 16. High-level view: RAG services emit traces and timings into SQLite, JSONL, and Langfuse; operators read them via `:3000` observe/observability, `:8200` guard, Langfuse `:3001`, and manager/Prometheus. Collapses detail so incidents start from *Stores → Dashboards* rather than code paths.*

### 8.2 Knowledge-base `stage_ms` and Redis

Every successful `POST /search/api` response includes a `stage_ms` object written in `kb_manager/web/routes/search.py` as each leg finishes: BM25 (tantivy RAM index), dense MiniLM encode + HNSW/pgvector lookup, Reciprocal Rank Fusion (`k=60`), BGE-m3 cross-encoder rerank, and `total`. The same object is stored with the cached SearchSteps payload under Redis (`KB_REDIS_TTL`, default **600s**) or an in-memory fallback when Redis is down; exact-cache hits typically return in **2–7 ms** and never cache error responses. Operators can therefore diagnose “dense vs rerank” without attaching a profiler—`jq '.stage_ms'` on a warm curl is the day-to-day tool.

### 8.3 Orchestrator timings, AuditTrail, and `ORCH_DEBUG`

Graph nodes call `record_timing(state, stage, elapsed_ms)` (`state.py`) so retrieve, clarify, `build_context`, `guarded_generate`, format, and retry/broaden paths accumulate into `state["stage_timing_ms"]`. On the buffered OpenAI chat path, `api.py` builds a Pydantic `AuditTrail` that copies those timings together with retrieved chunks, guard signals, context preview, subspace ambiguity fields, and wall `latency_ms`. Setting `ORCH_DEBUG=1` turns on app-level INFO logging and enables opt-in context diagnostics inside `build_context` so engineers can see what reached Gemma.

The buffered path stores that `AuditTrail`. The SSE path streams tokens from Guardrails, finalizes citations and metadata, and keeps traces updating.

### 8.4 Langfuse v2 HTTP and host fallbacks

`work_rag_orchestrator/tracing.py` posts direct HTTP to Langfuse v2 on **:3001**: envelopes carry top-level `id` + ISO `timestamp`, and updates re-`trace-create` the same id (v2 uses `trace-create` for updates). Posts are submitted on a small thread pool with short timeouts so tracing stays off the request loop. The same path can target the parent `components/tracing` collector on **:3000**, which appends to `/tmp/langfuse_traces.jsonl` and exposes a Langfuse-compatible ingestion surface plus the `/observe` timeline. LangGraph Studio is the third pane, on **:2024** (panel `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`). A Studio run carries `request_id` alongside `messages`—the same id sticky MemorySaver, Langfuse, and the collector use—so the graph thread joins the chat trace.

Separately, `eval_store.py` persists enriched pipeline cards to **`/tmp/observability.db`** (WAL SQLite, `EVAL_DB_PATH`) and mirrors them to **`/tmp/pipeline_traces.jsonl`** (`TRACE_JSONL`). The observability dashboard router under `/api/observability` is how Studio/WebUI-side tooling can push ratings and stage cards into that store.

### 8.5 Guard events, manager metrics, and retrieval DLQ

Guardrails write terminated/allowed decisions to `/tmp/guard_events.jsonl` (`GUARD_EVENTS_FILE`) with digit-run PII masking, and serve aggregates on the Persian dashboard at `http://127.0.0.1:8200/dashboard`. On the model plane, `llm_inference_manager` keeps session, message, and latency rows in `manager.db` and surfaces KB `stage_ms` breakdowns when a manager-side search probe is used. When filtered retrieval returns empty, orchestrator `retrieve.py` appends a record to `/tmp/dlq_retrieval.jsonl` so those turns stay greppable.

### 8.6 Latency evidence

Warm KB retrieval (v13.1 optimization pass, 30 fresh queries, `top_k=5`) sits well under a tenth of a second:

| Config | BM25 | Dense | Rerank | Total (p50) |
|---|---:|---:|---:|---:|
| v13 README (2026-10-07) | 4.0 | 24.0 | 24.0 | **55.0 ms** |
| Pre-opt (2026-10-13) | 3.8 | 20.5 | 20.9 | 44.4 ms |
| Post-opt (2026-10-13) | 2.6 | 13.5 | 22.0 | **39.6 ms** |

End-to-end chat from `bench_report_latest` (41 turns, model `ics-helper-agent`, 2026-10-14) reports **p50 4872 ms** and **average 4938 ms** at 0% transport error rate. After GPU MiniLM/BGE and RAM-first indexes, **`guarded_generate` accounts for most of the wall time**—classify/retrieve/build_context are tens to low hundreds of milliseconds, while Gemma decode at context 8192 accounts for the multi-second remainder. Greeting and specification shortcuts that skip the LLM land near ~0.8–1.1 s, so generation is the large slice of an end-to-end turn and hybrid search is the small one.

![Latency breakdown bars](../assets/plots/latency_breakdown.png)

*Figure — Latency breakdown (bars). Stacked/grouped stage bars contrast historical CPU-bound dense encode (~2.3 s) against the post-GPU, RAM-first profile where BM25, dense, RRF, and rerank together fit inside a ~40–70 ms envelope. Redis hits and warm indexes set the retrieval timing; end-to-end chat p50 follows generation.*

![Latency breakdown pie (after)](../assets/plots/latency_breakdown_pie_after.png)

*Figure — Latency breakdown pie (after optimizations). The post-optimization pie makes the same point compositionally: once dense leaves the CPU, rerank and residual orchestration slices are visible and remain small beside the generate slice on full RAG turns. The figure pairs with the TRT champion and the context budget as the levers on that generate slice.*

### 8.7 Optimizations that moved the numbers

- **RAM-first tantivy + HNSW.** Rust tantivy BM25 (≈50 MB heap, RAMDirectory) and RAM-pinned dense/pgvector HNSW remove cold disk seeks from the hot path; startup pre-warm loads indexes and CUDA kernels before the first user query.
- **RRF then selective rerank.** Fusion at `k=60` keeps candidate quality high while the cross-encoder scores a bounded pool (GPU, pool 30)—cheap legs stay cheap.
- **Entity / context trim.** Orchestrator supplemental injection is capped (top-3 × ~4 KB) and `prompt_char_budget≈20k` / `MAX_CHUNKS=20` hold the Gemma **8192** context window. Upstream overflow is surfaced as `finish_reason=length`.
- **TRT champion serving.** On the H200, TensorRT-LLM Gemma is the throughput champion versus llama.cpp Q4 for concurrent decode. Latency planning treats generate cost as a function of tokens and concurrency, read beside KB `stage_ms`.

### 8.8 Tooling

| Tool | Role in telemetry / docs |
|---|---|
| Langfuse | v2 trace/span UI (`:3001`); orchestrator posts envelopes via direct HTTP |
| Prometheus | Manager/infra metrics scrape target referenced beside `manager.db` |
| FastAPI | Tracing collector + observability dashboard routers |
| httpx | Fire-and-forget Langfuse/collector posts from `tracing.py` |
