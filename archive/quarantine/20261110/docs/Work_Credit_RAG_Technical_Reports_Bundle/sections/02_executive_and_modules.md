# Executive summary and module overview

## Section summary

Work Credit RAG is a Persian-first, self-hosted conversational system that answers credit-reporting questions from a versioned ICS knowledge base. A LangGraph orchestrator retrieves evidence, and a fail-closed guardrails gateway stands in front of Gemma. Production code lives in Git submodules. The umbrella repository owns pins, contracts, evaluation, and host startup scripts.

The current knowledge-base release, `v13_1405-07-06`, holds **18 documents** and **1,123 chunks**. Guardrails suppresses credit-domain HurtLex false positives with an allowlist of **28** lemmas. Subspace ambiguity is computed on every eligible turn; by default `subspace_ambiguity_enabled` is **true** and `subspace_ambiguity_route` is **false**, so the score is recorded for audit while graph routing continues to use the established clarify and retrieve edges.

## Hosts in production practice

Production runs on the **H200** lab host. The LLM Inference Manager on `:9000` fronts an 11-model registry whose champion is `gemma-4-31b`. Embedding servers and the Gemma pool are host processes. Redis, pgvector, and Open WebUI sit on a Docker data plane. The orchestrator’s published upstream model name on this host is `gemma-4-31b-triton-trt`.

The MVP path is a fixed hop list. Open WebUI (`:13000`) calls the orchestrator’s OpenAI-compatible API (`:8100`). The orchestrator validates input through guardrails (`:8200`), retrieves from the knowledge base (`:8000`), builds a bounded prompt, and generates through the same guardrails service. Gemma is reached from guardrails via the LLM manager on `:9000`. Citations return to WebUI. Traces land in Langfuse (`:3001`) or the JSONL fallback collector (`:3000`).

### H200 port overview

| Port | Service |
|---|---|
| 13000 | Open WebUI (ICS Helper) |
| 8100 | Orchestrator (LangGraph chat API) |
| 8000 | Knowledge base |
| 8200 | Guardrails |
| 8001 | multilingual-e5-small embeddings (384-d) |
| 8002 | bge-m3 embeddings (1024-d) |
| 8003 | MiniLM embeddings (384-d); orchestrator ambiguity client |
| 8010 | TensorRT-LLM Gemma-4-31B champion |
| 8080–8084 | Five llama.cpp Gemma-4-31B backends |
| 9000 | LLM Inference Manager |
| 9001 | DeepSeek-V4-Flash wrapper (standalone; outside `MODEL_REGISTRY`) |
| 3000 / 3001 / 2024 | Trace collector, Langfuse, LangGraph Studio |

Docker publishes the data plane beside those host ports: pgvector on **15432**, Redis on **16379**, Grafana on **13001**, and Prometheus on **19090**. Chapter 6 expands the Squid proxy rule, the container cutover, and the GPU placement behind `:8010` and `:8080`–`:8084`.

## Module ownership

| Module | Port | Responsibility |
|---|---|---|
| Knowledge base | 8000 | Ingest, hybrid search, EntityList supplements, KB UI |
| Orchestrator | 8100 | LangGraph RAG graph, chat API, sticky subspaces |
| Guardrails | 8200 | Input/output rails, guarded generate |
| Server setup | 9000 (+ backends) | Model lifecycle, embeds, H200 infra |
| Tracing | 3000 | Fallback collector, observability DB/UI |
| Parent ops | — | Startup, E2E, schemas, thin entry wrappers |

Thin wrappers under `api/` only adjust `PYTHONPATH` and re-export factory apps. Implementation changes belong in the owning submodule, then the parent gitlink advances.
