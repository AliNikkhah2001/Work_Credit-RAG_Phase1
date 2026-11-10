# Appendix

## Section summary

This appendix indexes libraries by role, lists primary source files, and records the published defaults for the H200 lab server.

## Library and tooling index

| Library | Role |
|---|---|
| FastAPI | HTTP services |
| LangGraph | Orchestrator graph |
| SQLAlchemy | Async ORM |
| pgvector | Vector storage/index |
| tantivy | BM25 engine |
| sentence-transformers | Embeddings |
| FlagEmbedding / BGE | Reranker family |
| Redis | Result cache |
| httpx | Async HTTP client |
| Langfuse | Tracing UI/API |
| llama.cpp | GGUF serving |
| TensorRT-LLM | High-throughput serve |
| LiteLLM | Optional gateway |
| Docker | Containers |
| PyTorch | Training/inference deps |
| Prometheus | Metrics |

## Primary source map

| Concern | Path |
|---|---|
| Graph wiring | `orchestrator/graph.py` |
| Retrieve + trim | `orchestrator/nodes/retrieve.py` |
| Context budgets | `orchestrator/nodes/build_context.py` |
| Orch settings | `orchestrator/config.py` |
| KB search | `kb/search.py` |
| Dense index | `kb/dense.py` |
| EntityList model | `kb/database.py` |
| Guard service | `guardrails/service.py` |
| Judge | `guardrails/judge.py` |
| Signals | `guardrails/signals.py` |
| Manager | `manager/app.py` |
| Docker compose | `deploy/docker/` |
| Trace collector | `tracing/app.py` |
| Eval store | `tracing/eval_store.py` |
| Orch tracing | `orchestrator/tracing.py` |

## Glossary

| Term | Meaning in this stack |
|---|---|
| Hit@5 | Fraction of eval queries whose relevant chunk appears in the top 5. Published v11 value is **0.9306**. |
| Warm search | Hybrid retrieve after indexes and CUDA kernels are resident. Quote **~55 ms** (v13 README total); a later tune measured 39.6 ms p50. |
| Sticky subspace | Orchestrator memory that keeps cheque / facilities / general across follow-up turns, keyed by `request_id`, with decay. |
| `request_id` | Required on Studio run inputs and on rails checks. Joins sticky memory, Langfuse `:3001`, and the collector `:3000`. |
| AuditTrail | Pydantic record of timings, chunks, and guard signals on the buffered chat path. |
| PII-IR | Output-rail validators: national ID mod-11, Sheba / IR-IBAN mod-97, plus phone patterns. Valid hits mask; secrets hard-block. |
| HurtLex allowlist | **28** exact lemmas in `kb/hurtlex_allowlist.json` that must not fire hate. Profanity, PII, and secrets are not on it. |
| Champion | TensorRT-LLM Gemma on `:8010`. The llama.cpp pool `8080–8084` is the fallback. DeepSeek `:9001` is outside `MODEL_REGISTRY`. |
| `trust_env=False` | httpx flag that stops localhost calls from inheriting Squid at `192.168.203.2:3128`. |
| Finish mismatch | Bench turn whose `finish_reason` disagreed with the expected stop / length / content_filter outcome. 6/41 before, 0/41 after. |

## Environment variables

Values below are the published defaults for the H200 lab server from the parent configuration table, plus the guard and cache flags the pages call out. Secrets are omitted on purpose.

| Variable | Typical value | Why it matters |
|---|---|---|
| `ORCHESTRATOR_PORT` | 8100 | Public chat API |
| `KB_BASE_URL` | `localhost:8000` | Search URL is `{KB}/search/api` |
| `GUARDRAILS_BASE_URL` | `localhost:8200` | Rails check and guarded generate |
| `retrieval_top_k` | 20 | Raised from the early MVP of 5 |
| `subspace_threshold` | 0.8 | Clarify gate |
| `evidence_min_score` | 0.15 | Global hallucination floor; cheque 0.05, facilities_person 0.10, facilities_legal and general 0.15 |
| `MAX_CHUNKS` / `MAX_CONTEXT` | 20 / 9000 | Context budget (was 5 / 6000) |
| `LANGFUSE_HOST` | `localhost:3001` | Langfuse v2; collector fallback is `:3000` |
| `KB_DB_URL` | `postgresql+asyncpg://…:5432/kb_manager` | pgvector HNSW. Set explicitly so the vector index is the store in use |
| `KB_EMBED_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | 384-d dense leg |
| `KB_RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | MiniLM mmarco is the lightweight fallback |
| `KB_RERANK_POOL` | 15 CPU / 30 GPU | Cross-encoder candidate cap |
| `UPSTREAM_LLM_BASE_URL` | `localhost:9000/v1` | Guardrails dials Gemma through the H200 manager |
| `UPSTREAM_LLM_MODEL` | `gemma-4-31b` or the unsloth UD-Q4_K_XL id | Match the process actually listening |
| `CTX_SIZE` | 8192 | Gemma context window |
| `GUARD_JUDGE_BACKEND` | `gemma` (default), `mizan`, or `hybrid` | Adjudicator |
| `GUARD_JUDGE_MODE` | `on-signal` (default) or `always` | Skip the LLM judge on clean text when on-signal |
| `GUARD_NEMO_SELFCHECK` | `on` / `shadow` / `off` | Selects the direct-LLM yes/no self-check |
| `HF_HOME` and `HF_HUB_CACHE` | both set, same cache directory | Hub 1.x reads `$HF_HOME/hub`. Setting only one misses weights |
| `WEBUI_AUTH` | `false` on the ICS Helper MVP | `true` when per-user ids are required |
| Studio run field `request_id` | required on every Studio input | Joins the `:2024` thread to traces |

`httpx` clients that call localhost also set `trust_env=False` in code. Exporting `no_proxy=localhost,127.0.0.1` does not replace that flag while Squid is at `192.168.203.2:3128`.

## Pages extract sources

Prose in sections 6–10 is synthesized from these extracts (original wording; not an HTML dump):

| Extract | What this report took from it |
|---|---|
| `server_setup` | H200 ports, Docker publish surface, Squid / `trust_env`, containerization phases 1–5, TRT champion |
| `guardrails` | Signals, judge, self-check, HurtLex **28**, PII-IR mod-11/mod-97, `policies/ics-credit-v1.0.0.yaml`, judge backends, SVG inventory |
| `parent` | 41-turn before/after bench, Ghadeer thresholds (0.80 / 0.80 / 0.90 / 0.85), Langfuse `:3001`, collector `:3000`, Studio `:2024`, env table |
| `agent_state` | Both HF cache vars, Studio `request_id`, `trust_env=False` |
| `kb` | v11 Hit@5 **0.9306**, warm search **~55 ms** |

Upstream HTML those extracts name: server-setup `docs/{index,technical,high-level}.html`, `guides/03-services-and-endpoints.md`, `gemma_endpoints.md`, `migration/containerization-report.md`; guardrails `docs/{index,technical,high-level}.html`; parent `docs/{index,technical,high-level}.html` and `docs/papers/benchmarks.html`; agent-state `docs/{index,high-level,technical}.html`; KB `docs/{index,technical,high-level}.html`.

## Build notes

Render diagrams: `bash docs/technical-report/scripts/render_diagrams.sh`  
Assemble: `bash docs/technical-report/scripts/build_pdf.sh`  
Sync HTML: `bash docs/technical-report/scripts/build_html.sh`
