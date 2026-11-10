# Work Credit RAG — Technical Summary

**Organization:** Iranian Credit Scoring Company (ICS)  
**Platform:** Dana / Work Credit RAG Phase 1  
**Date:** 2026-11-10  
**Host:** Self-hosted H200 lab server (2× NVIDIA H200)

This summary describes the **current** platform structure and technical behavior. Diagrams match the deep-dive report; captions state what each figure shows.

## Platform at a glance

Persian conversational RAG for credit-reporting questions. Production code lives in Git submodules; the umbrella owns pins, deploy scripts, contracts, and evaluation. Release `v13_1405-07-06` indexes **18 documents / 1,123 chunks**. Guardrails uses a HurtLex allowlist of **28** lemmas. Subspace ambiguity is computed (`enabled=true`) and does not route by default (`route=false`).

| Module | Port | Role |
|---|---|---|
| Open WebUI | 13000 | Browser UI (ICS Helper) |
| Orchestrator | 8100 | LangGraph chat API |
| Knowledge base | 8000 | Hybrid retrieval |
| Guardrails | 8200 | Input/output rails + gated generate |
| LLM Manager | 9000 | OpenAI gateway to Gemma fleet |
| Embeds | 8001–8003 | e5 / bge-m3 / MiniLM |
| TRT / llama.cpp | 8010 / 8080–8084 | Champion + replica pool |
| Collector / Langfuse / Studio | 3000 / 3001 / 2024 | Observability |

## Architecture and request path

Browser → WebUI `:13000` → Orchestrator `:8100` → Guardrails input → KB retrieve → `build_context` (≤20 chunks, context 9000) → Guardrails generate → Manager `:9000` → citations back to WebUI. Sticky subspace decays after **3** generic turns. Evidence floor **0.15**. Ambiguity margin **0.08**.

![High-level system overview](../assets/diagrams/01_system_overview_hl.png)

*Figure — High-level overview. WebUI talks only to the orchestrator. Guardrails gates both input and generation. The KB supplies evidence. Observability sits beside the user path.*

![Detailed system overview](../assets/diagrams/02_system_overview_detail.png)

*Figure — Detailed overview. Orchestrator nodes (validate, classify, retrieve, build_context, guarded_generate, format) call KB search/supplement and Guardrails rails/chat. Embeddings for ambiguity use MiniLM `:8003`. Gemma is reached only through the manager.*

![High-level request sequence](../assets/diagrams/03_request_flow_hl.png)

*Figure — Sticky filtered RAG (high level). Input rails may refuse before retrieval. Hybrid search returns chunks and optional entity rows. Guarded generation and output rails produce the cited answer.*

![Detailed request sequence](../assets/diagrams/04_request_flow_detail.png)

*Figure — Detailed sequence. Sticky `filter_path`, keyword boosts, supplement threshold 0.4, clarify short-circuit on entities, and context budgets are applied inside the orchestrator before generation.*

![Orchestrator graph high level](../assets/diagrams/05_orch_graph_hl.png)

*Figure — Graph high level. Validate → classify → retrieve → optional clarify → generate → format, with refusal exits.*

![Orchestrator graph detailed](../assets/diagrams/06_orch_graph_detail.png)

*Figure — Graph detailed. Conditional edges after validation, classify, and clarify. Ambiguity score is instrumented; scattered-query clarify remains available.*

## Knowledge base

Hybrid stack: tantivy BM25 (k1=1.5, b=0.75, keyword boost ×3, synonym beam 5) + MiniLM 384-d HNSW (m=16, ef=64) → RRF k=60 → BGE-m3 rerank (fusion α=0.7) → EntityList inject (≥0.6). Redis cache TTL 600 s. Warm hybrid search ~**55 ms**. Published Hit@5 on the prior corpus (v11): **0.9306**.

![KB ingest](../assets/diagrams/07_kb_ingest_hl.png)

*Figure — Ingest. Sources become versioned chunks and entity lists with embeddings in pgvector.*

![KB retrieval](../assets/diagrams/09_kb_retrieval_hl.png)

*Figure — Retrieval. Normalize → beam → BM25∥dense → RRF → rerank → fuse → entities → cache.*

## Orchestrator

Never dials Gemma directly. Keyword boosts: cheque 3.5; facilities 3.0; general 2.5. Clients use `trust_env=False` so Squid does not capture localhost. Checkpoint sticky scope with `MemorySaver` / `request_id`.

## Guardrails

Deterministic signals → policy judge (`gemma` / `mizan` / `hybrid`) → LLM self-check. Fail-closed on errors. PII-IR (mod-11 / mod-97) masks; secrets hard-block. Policy pin `ics-credit-v1.0.0`. Thresholds published with the stack: toxicity/hate 0.80, PII 0.90, injection 0.85.

![Guardrails black-box](../assets/diagrams/security_guard_blackbox.png)

*Figure — Guardrails box. Callers see rails/check and chat/completions; upstream is the H200 manager only.*

## Server, serving, and scale

![Server topology high level](../assets/diagrams/13_server_topology_hl.png)

*Figure — H200 topology (high level). Manager fronts GPU backends; Docker hosts WebUI and data stores.*

![Server topology detail](../assets/diagrams/14_server_topology_detail.png)

*Figure — Port map. TRT `:8010` champion; llama.cpp `8080–8084`; embeds `8001–8003`; apps on 8000/8100/8200/13000.*

![Scale-out](../assets/diagrams/17_scale_out.png)

*Figure — Scale-out pattern. Ingress + HPA for CPU services; KEDA/queue depth for GPU replicas; dedicated vector tier.*

![Scale-up](../assets/diagrams/18_scale_up.png)

*Figure — Scale-up pattern. Saturate 2×H200 on one chassis with dense continuous batching.*

Measured TRT BF16 aggregate ~**3874 tok/s** at concurrency 128 versus ~58 tok/s flat llama.cpp Q4 single-slot (~67×). Container cutover uses five phases; production ports stay fixed through phase 4.

## Telemetry

KB returns `stage_ms`; orchestrator `stage_timing_ms` / AuditTrail; Langfuse `:3001` or collector `:3000`; Studio `:2024` requires `request_id`. Guard events and manager metrics complement the path. E2E chat p50 ~**4872 ms** (generation-dominated); warm search tens of ms.

![Observability wiring](../assets/diagrams/15_observability.png)

*Figure — Observability stores and dashboards join on `request_id`.*

## Benchmarks (published)

41-turn bench (12→14 Oct 2026): finish mismatches 6→0; retrieval hit 0.537→0.780; cheque hit 0.111→0.667; context recall 0.113→0.340; answer relevancy 0.212→0.568; ambiguity 0.854→1.0; sticky 0.610→0.683; p50 8006→4872 ms (−39%).

## Networking (H200)

Application and Docker publish surfaces as in the deep-dive port tables. Squid `192.168.203.2:3128`; localhost clients set `trust_env=False`. Compose MVP publishes WebUI `:13000` and Langfuse `:3000` on the host; other services stay on the Docker network for discovery.
