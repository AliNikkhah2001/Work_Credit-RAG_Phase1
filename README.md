# Work Credit RAG — Phase 1

Umbrella repository for a **self-hosted, Persian-capable conversational RAG platform** for ICS credit scoring. The implementation is split into independently maintained Git submodules so hardware/model operations, knowledge-base lifecycle, safety policy, and LangGraph orchestration can evolve without returning to a monolith.

---

## 1. Summary

**What this is:** a four-component RAG system that answers Persian questions about credit scoring / credit reporting (ICS domain) grounded strictly in a private knowledge base, with guardrails on both the input and the generated output, orchestrated by a deterministic LangGraph workflow, and exposed through an OpenAI-compatible chat API consumed by Open WebUI.

**Why it is split into submodules:** each component owns a disjoint concern and a separate repository. This lets the H200 inference infrastructure, the KB ingestion pipeline, the safety policy, and the graph orchestration be versioned, tested, and scaled independently. Each gitlink is pinned to an exact commit.

---

## 2. Repository composition

| Path | Repository | Responsibility | Default branch | Port |
|---|---|---|---|---|
| `components/server-setup` | [Work_RAG-Server-Setup](https://github.com/AliNikkhah2001/Work_RAG-Server-Setup) | H200 provisioning, local model & embedding services, Gemma manager, Open WebUI, infrastructure | `main` | 9000, 8001–8003, ... |
| `components/knowledgebase` | [Work_RAG-KB](https://github.com/AliNikkhah2001/Work_RAG-KB) | KB ingestion, maintenance, versioning, hybrid retrieval, reranking, KB web UI | `master` | 8000 |
| `components/guardrails` | [Work_RAG-Guardrails](https://github.com/AliNikkhah2001/Work_RAG-Guardrails) | Persian safety rails (input/output) + guarded Gemma gateway | `main` | 8200 |
| `components/orchestrator` | [Work_RAG-Orchestrator](https://github.com/AliNikkhah2001/Work_RAG-Orchestrator) | LangGraph workflow + public OpenAI-compatible chat API | `main` | 8100 |
| — (this repo) | [Work_Credit-RAG_Phase1](https://github.com/AliNikkhah2001/Work_Credit-RAG_Phase1) | Cross-repo contracts, pinned revisions, integrated startup, E2E acceptance | `main` | — |

> Each gitlink points at an exact commit. Updating a component = a commit in the component repo, then a commit here that advances its gitlink.

---

## 3. High-level architecture

```mermaid
flowchart LR
    UI["Open WebUI :13000<br/>browser chat"] -->|POST /v1/chat/completions| ORCH["Orchestrator :8100<br/>LangGraph RAG graph"]
    ORCH -->|"input rail check"| GR["Guardrails :8200<br/>Persian deterministic rails"]
    ORCH -->|"hybrid retrieval"| KB["KB Manager :8000<br/>BM25 + dense + RRF + rerank"]
    ORCH -->|"guarded generation"| GR
    GR -->|"OpenAI-compatible"| GEMMA["Gemma manager :9000<br/>self-hosted LLM"]
    KB -->|"chunks + citations"| ORCH
    ORCH -->|"citation-shaped response"| UI
```

### Request order (MVP path)

```text
browser
  └─▶ Orchestrator  (POST /v1/chat/completions)
        ├─▶ Guardrails: input rail check   (reject injections / jailbreak / hate / out-of-scope)
        ├─▶ KB Manager:  hybrid retrieval  (top-5 chunks)
        ├─▶ build context (numbered sources [1]..[n])
        ├─▶ Guardrails  : guarded Gemma generation (input→generation→output rails)
        │      └─▶ Gemma Manager :9000  (extractive/mock or real GGUF on H200)
        └─▶ format response (citations, finish_reason) → frontend
```

### Component hand-off contract

| Step | Sender → Receiver | Endpoint | Request body |
|---|---|---|---|
| Input rail | Orchestrator → Guardrails | `POST /v1/rails/check` | `{"stage":"input","text":"...","request_id":"..."}` |
| Retrieval | Orchestrator → KB | `POST /search/api` | `{"query":"...","top_k":5}` |
| Generation | Orchestrator → Guardrails | `POST /v1/chat/completions` | OpenAI chat body + `X-Request-ID` |
| Upstream | Guardrails → Gemma | `POST /v1/chat/completions` | OpenAI chat body + Bearer auth |

All cross-component request/response shapes are versioned in [`contracts/`](contracts/README.md).

---

## 4. Detailed component diagrams

### 4.1 Orchestrator — LangGraph workflow

```mermaid
flowchart TD
    START([START]) --> VI[validate_input]
    VI -->|"blocked ?"| COND{guardrail_decision.allowed?}
    COND -->|"yes"| RET[retrieve: KB /search/api]
    COND -->|"no"| REF[format_refusal<br/>reuses format_response]
    RET --> BC[build_context<br/>numbered [1..5], ≤8000 chars]
    BC --> GG[guarded_generate<br/>→ Guardrails chat gateway]
    GG --> FR[format_response<br/>citations + finish_reason]
    FR --> STOP
    REF --> STOP([END])
```

### 4.2 Knowledgebase — hybrid retrieval pipeline

```mermaid
flowchart LR
    Q[User query] --> N[Persian normalization<br/>Arabic→Persian chars, ZWNJ, digits]
    N --> BM[BM25 lexical<br/>char 3-grams, keyword ×3]
    N --> DE[Dense semantic<br/>MiniLM-L12 384-dim, cosine]
    BM --> RRF[RRF fusion<br/>k=60]
    DE --> RRF
    RRF --> CE[Cross-encoder rerank<br/>mmarco-mMiniLMv2, top-50]
    CE --> TOP[Top-K chunks + citations]
```

### 4.3 Guardrails — input and output stages

```mermaid
flowchart LR
    IN[user text] --> S1[check_input_persian]
    S1 --> A[prompt_injection]
    S1 --> B[jailbreak]
    S1 --> C[hurtlex hate]
    S1 --> D[profanity]
    S1 --> E[out_of_scope]
    GEN[LLM output] --> S2[check_output_persian]
    S2 --> F[profanity]
    S2 --> G[hurtlex hate]
    S2 --> H[PII IR: national-id/Sheba/phone]
    S2 --> I[secret markers]
```

### 4.4 Deployment topology

```mermaid
flowchart LR
    subgraph H200[On-prem GPU host]
        GE[Gemma manager :9000]
        E1[Embed e5-small :8001]
        E2[Embed bge-m3 :8002]
    end
    subgraph App[Application host / Docker]
        KB[KB Manager :8000]
        GR[Guardrails :8200]
        OR[Orchestrator :8100]
        UI[Open WebUI :13000]
        PG[(pgvector)]
        RD[(Redis)]
    end
    UI --> OR --> GR --> GE
    OR --> KB --> E1
    OR --> KB --> E2
    KB --> PG
```

---

## 5. Modules at a glance

| Module | Language/Stack | What it does | Key files |
|---|---|---|---|
| **server-setup** | Python, FastAPI, Docker, llama.cpp | Provisions the H200 box behind a proxy; runs embedding services (8001–8003), a Gemma inference manager gateway (9000, 11 GGUF models), a data plane (Milvus/Qdrant/pgvector/Redis/Open WebUI) and a monitoring stack (Prometheus/Grafana/OTel) | `offline_prepare_cli.py`, `start.sh`, `scripts/services/*.py`, `llm_inference_manager/app.py`, `deploy/docker-compose.yml` |
| **knowledgebase** | Python, FastAPI, SQLAlchemy, sentence-transformers | Ingests Persian XLSX/PDF/DOCX into a versioned KB, chunks (semantic: QA-pairs, reason-codes, articles), embeds (MiniLM‑L12), hybrid search (BM25+dense+RRF+cross-encoder), web UI + benchmark harness | `kb-manager/kb_manager/*`, `kb-manager/web/routes/*.py`, `kb-manager/run_server.py` |
| **guardrails** | Python, FastAPI (NeMo ready) | Persian deterministic input/output rails: prompt-injection, jailbreak, HurtLex hate, profanity, out-of-scope, PII (national-id/Sheba/phone), secret markers; guarded chat gateway to Gemma; **fail-closed** | `src/work_rag_guardrails/{actions,service,config}.py`, `kb/*.json`, `config/{config.yml,rails.co}` |
| **orchestrator** | Python, LangGraph, FastAPI | Deterministic RAG graph: validate_input → retrieve → build_context → guarded_generate → format_response; OpenAI-compatible `/v1/chat/completions`; citations; `/health` + `/ready`; LangGraph Studio integration | `src/work_rag_orchestrator/*`, `nodes/*.py`, `clients/*.py`, `graph.py`, `studio_graph.py` |

---

## 6. Running the system

### 6.1 Option A — Local (no Docker), step by step

Prereqs: Python ≥ 3.11, the Gemma manager (or the mock in [`scripts/mock_gemma_manager.py`](scripts/mock_gemma_manager.py)) on `:9000`, and KB source files in `components/knowledgebase/kb-source`.

```bash
# 1. Embedding + Gemma services come from server-setup (H200/prod) or run the mock:
python scripts/mock_gemma_manager.py          # port 9000 (extractive grounding, no GPU)

# 2. KB Manager
cd components/knowledgebase/kb-manager
pip install -e ".[dev]"
python run_server.py                          # port 8000 (pre-warms BM25/dense/reranker)

# 3. Guardrails
cd ../guardrails
cp .env.example .env
pip install -e ".[dev]"
python -m work_rag_guardrails.api             # port 8200

# 4. Orchestrator
cd ../orchestrator
cp .env.example .env
pip install -e ".[dev]"
python -m work_rag_orchestrator.api           # port 8100
```

### 6.2 Option B — One-command local orchestration

```powershell
.\scripts\run_mvp.ps1          # starts KB, Guardrails, Orchestrator in dependency order with health checks
# or on Linux/Mac
./scripts/run_mvp.sh
```

### 6.3 Option C — Full Docker stack (`compose.mvp.yml`)

```bash
docker compose -f compose.mvp.yml up -d
# brings up: pgvector, Redis, embed services, KB Manager:8000,
#            Gemma Manager:9000, Guardrails:8200, Orchestrator:8100, Open WebUI:13000
```

Open the browser at **http://localhost:13000** and start asking Persian credit-scoring questions.

### 6.4 Hand-testing the API without a browser

```bash
curl -s http://127.0.0.1:8100/v1/chat/completions -X POST \
  -H "Content-Type: application/json" \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"چگونه می‌توانم گزارش اعتباری خود را دریافت کنم؟"}],"max_tokens":500,"temperature":0}'
```

### 6.5 End-to-end acceptance test

```bash
python scripts/test_mvp.py         # runs health/readiness + E2E Persian question + injection block tests
```

---

## 7. Cross-component contracts

Versioned JSON Schemas in [`contracts/`](contracts/README.md):

| File | Purpose | Direction |
|---|---|---|
| `rail_check_request.json` | Input/output rail check request | Orchestrator → Guardrails |
| `rail_check_response.json` | Rail check response | Guardrails → Orchestrator |
| `kb_retrieval_request.json` | KB search request | Orchestrator → KB |
| `kb_retrieval_result.json` | Normalized KB result | KB → Orchestrator |
| `orchestrator_chat_response.json` | Public chat API response | Orchestrator → Open WebUI |

---

## 8. Clone & submodule workflow

```bash
git clone --recurse-submodules https://github.com/AliNikkhah2001/Work_Credit-RAG_Phase1.git
cd Work_Credit-RAG_Phase1
# or, if already cloned:
git submodule sync --recursive
git submodule update --init --recursive
git submodule status --recursive
```

### Updating one submodule

```bash
cd components/orchestrator
git switch main
git pull --ff-only
cd ../..
git add components/orchestrator
git commit -m "chore: advance orchestrator submodule"
```

Always run contract + E2E tests before advancing a production pin.

---

## 9. Ownership rule

| Concern | Repo |
|---|---|
| hardware, model lifecycle, container infra, frontend wiring | **server-setup** |
| source docs, ingestion, indexing, retrieval, reranking, KB evaluation | **knowledgebase** |
| Colang/policy config, guarded model access | **guardrails** |
| graph state, node order, dependency adapters, public chat API | **orchestrator** |
| cross-repo contracts, pins, integrated startup, E2E acceptance | **this parent repo** |

Do not duplicate component implementation in the parent repository.

---

## 10. Planning & progress checklist

Hierarchical status of the Phase-1 work. `[x]` = complete, `[ ]` = open/next.

### 10.1 Phase 1 — Deterministic MVP (current)

- [x] **KB Manager**
  - [x] Persian normalization + extraction (XLSX/PDF/DOCX)
  - [x] Semantic chunking (QA pairs, reason codes, articles; parent chunks)
  - [x] Embedding (paraphrase-multilingual-MiniLM-L12-v2, 384-d)
  - [x] Hybrid retrieval: BM25 + dense + RRF(k=60) + cross-encoder rerank
  - [x] `/search/api` normalized response + Web UI (port 8000)
  - [x] Benchmark harness (v5: 120 queries, Hit@5 84.2%, MRR 0.751)
  - [x] Dockerfile + docker-compose (SQLite runtime / pgvector target)
  - [ ] pgvector production migration & indexing (vector + pg_trgm)
  - [ ] Hybrid / contextual retrieval live toggle wiring
- [x] **Guardrails**
  - [x] Deterministic Persian rails (works without NeMo on py≤3.13)
  - [x] Input: prompt-injection, jailbreak, HurtLex hate, profanity, out-of-scope
  - [x] Output: profanity, hate, PII-IR (national-id/Sheba/phone), secret markers
  - [x] Guarded chat gateway to Gemma + fail-closed policy-engine errors
  - [x] **HurtLex conservative filter** (833 lemmas) — removes `اثر` false positive
  - [x] NeMo Colang config + `rails.co` flows (for GPU hosts)
  - [x] Dockerfile + env example + tests
  - [ ] Wire Python `*_action` names used by Colang into `actions.py`
  - [ ] Optional Parsoff-BERT classifier for higher recall hate detection
- [x] **Orchestrator**
  - [x] LangGraph deterministic RAG graph + conditional refusal branch
  - [x] Clients: KB (`/search/api`) and Guardrails (`/v1/rails/check`, chat)
  - [x] Bounded context build (max 5 sources, 8000 chars)
  - [x] OpenAI-compatible `/v1/chat/completions` + citations
  - [x] `/health` + `/ready` dependency checks
  - [x] LangGraph Studio integration (`studio_graph.py` + `langgraph.json`)
  - [x] Dockerfile + env example + node unit tests
  - [ ] API-level tests for `/health` `/ready` `/v1/chat/completions`
  - [ ] PostgreSQL checkpointing (AsyncPostgresSaver) for thread memory
- [x] **Server setup**
  - [x] Embedding services (e5-small 8001, bge-m3 8002, MiniLM 8003)
  - [x] Gemma manager gateway (9000, 11-model registry, round-robin, sessions)
  - [x] Dockerfiles: `Dockerfile.embed`, `llm_inference_manager/Dockerfile`
  - [x] Data plane compose (Milvus/Qdrant/pgvector/Redis/Open WebUI)
  - [x] Monitoring stack (Prometheus/Grafana/OTel)
  - [x] Offline-prep tooling behind Squid proxy
  - [ ] Re-render runbook to the live `/splunk-data/v1/...` paths (stale `/ai-gpu1/...` refs)
- [x] **Parent integration**
  - [x] `compose.mvp.yml` one-command stack wiring all four components + Open WebUI
  - [x] `contracts/` JSON Schemas for cross-component hand-offs
  - [x] `scripts/` run_mvp.ps1/.sh + mock Gemma + test_mvp.py acceptance
  - [x] `tests/e2e/mvp_golden_fixture.json`
  - [x] Submodule pins advanced to implementation commits

### 10.2 Phase 2 — Reliability & observability (next)

- [ ] Retrieval retry loop with graded chunks (`grade_docs`)
- [ ] Hallucination span detection on output (`ISSUP`/`ISUSE` style)
- [ ] `query` rewrite / multi-query generation wired end-to-end
- [ ] Nuanced refusal messages API (non-generic, per-category Persian)
- [ ] Request tracing (X-Request-ID) surfaced in logs & dashboards
- [ ] Contract tests in every component validating schemas

### 10.3 Phase 3 — Production hardening (later)

- [ ] PostgreSQL checkpoints + thread memory (PostgresStore)
- [ ] Open WebUI auth + multi-user sessions
- [ ] Streaming responses (`stream=true`)
- [ ] Kubernetes deployment (instead of single compose stack)
- [ ] PII redaction pipeline and compliance audit
- [ ] GraphRAG / multi-agent routing evaluation

---

## 11. Security notes

- Guardrails **fail closed** on policy-engine errors (blocked by default).
- Secrets are never committed — only `.env.example` is tracked in every component.
- PII detectors validate checksums (national-id mod-11, Sheba mod-97) so only *valid* PII is flagged.
- HurtLex is restricted to the **conservative** 833 terms to avoid false positives on benign Persian words while still catching genuine offensive language.

---

## License

See [LICENSE](LICENSE). Each submodule may also declare its own license and dependency obligations.