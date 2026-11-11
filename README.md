# Work Credit RAG — Phase 1

[![Python](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/downloads/release/python-3110/)
[![License](https://img.shields.io/github/license/AliNikkhah2001/Work_Credit-RAG_Phase1)](LICENSE)
[![Branch](https://img.shields.io/badge/branch-main-blue)]()

Self-hosted, Persian-capable conversational RAG platform. Production code lives in independently maintained Git submodules (orchestrator, knowledgebase, guardrails, server-setup) pinned to exact commits; the parent repo owns pins, integrated startup (`deploy/vast/`), and E2E evaluation.

> **Status:** Active on `main`. Deployed on Vast.ai (RTX 3090) and H200 host via `Work_RAG-Server-Setup` LLM manager `:9000`. Current KB `v13` — 18 docs / 1123 chunks · pgvector HNSW · `MAX_CHUNKS=20`.

<details>
<summary>Repository composition &amp; layers</summary>

Production implementation is split into Git submodules. Each gitlink is pinned to an exact commit; advancing a component requires a component-repo commit followed by a parent-repo commit that advances the gitlink.

| Path | Repository | Branch | Current pin | Responsibility |
|------|------------|--------|-------------|----------------|
| `components/server-setup` | Work_RAG-Server-Setup | `main` | `ff8c5a8` | Hardware, LLM manager `:9000`, embed `:8001-8003`, infra |
| `components/knowledgebase` | Work_RAG-KB | `master` | `92503e5` | Ingestion, `folder_hierarchy` tagging, `filter_path`, `supplement` tool, retrieval `:8000` |
| `components/guardrails` | Work_RAG-Guardrails | `main` | `1002ea8` | Persian safety policy, guarded Gemma `:8200` |
| `components/orchestrator` | Work_RAG-Orchestrator | `main` | `75cf970` | LangGraph API `:8100`, sticky `MemorySaver`, `filter_path`, evidence guard |
| `components/tracing` | parent (not a submodule) | — | — | Fallback trace collector `:3000`, `observability.db` |
| `agent-state` | ICS_ChatBot_agent-state | `main` | `a0d454e` | Agent context/history/skills — agent only, not production |

Run `git submodule status --recursive` for live pins.

Layer separation:

| Layer | Directory | Production? | Purpose |
|-------|-----------|-------------|---------|
| Entry points | `api/` | Yes | Thin wrappers → `components/` submodules |
| Implementation | `components/` | Yes | Production code (submodules, pinned commits) |
| Contracts | `contracts/` | Yes | API request/response JSON schemas |
| Deployment | `deploy/` | Yes | Start/stop/health scripts per host (Vast/H200/Docker) |
| Testing | `eval/` | Yes | E2E, guardrails, LLM-judge evaluation |
| Utilities | `scripts/` | Yes | README TOC generation, system checks |
| Agent context | `agent-state/` | Agent only | Agent mission, history, skills, standards |
| Development | `dev/` | No | Patches, ad-hoc tests, investigation scripts |
| Archive | `archive/`, `deprecated/` | No | Historical reference, read-only |

</details>

<details>
<summary>Architecture — production diagrams</summary>

### System overview

```mermaid
flowchart TB
    subgraph Client["Client layer"]
        Browser["Browser"]
        WebUI["Open WebUI :13000\nICS Helper · rag_trace_capture filter"]
    end

    subgraph Orch["Orchestration :8100"]
        Orch["Orchestrator\nLangGraph · MemorySaver · X-Request-ID sticky thread"]
    end

    subgraph KB["Retrieval :8000"]
        KBMgr["KB Manager\nBM25 tantivy + dense MiniLM-384\n+ RRF k=60 + BGE-m3 rerank\npgvector HNSW · 1123 chunks"]
        Filter["filter_path · folder_hierarchy"]
        Suppl["supplement tool\nPOST /search/supplement · entity lists"]
    end

    subgraph GR["Safety :8200"]
        Guard["Guardrails\nPOST /v1/rails/check input\nPOST /v1/chat/completions guarded_generate\nPersian signals + LLM judge"]
    end

    subgraph Gen["Generation"]
        Gemma["Gemma 4 31B\nunsloth/gemma-4-31B-it-GGUF UD-Q4_K_XL\n:18000 Vast · :9000 Manager H200"]
        Embed["Embed trio :8001-8003\ne5-small · bge-m3 · MiniLM"]
    end

    subgraph Obs["Observability"]
        Coll["Collector :3000\nobservability.db SQLite"]
        LF2["Langfuse v2 :3001"]
        Studio["Studio :2024\nLangGraph API"]
    end

    Browser --> WebUI
    WebUI -- "OPENAI_API_BASE_URL=8100/v1\n+ X-Request-ID" --> Orch
    Orch --> Guard
    Guard -- "blocked" --> WebUI
    Guard -- "allowed" --> KBMgr
    KBMgr --> Filter
    KBMgr --> Suppl
    Suppl -- "merged into context" --> Orch
    Orch -- "guarded_generate" --> Guard
    Guard --> Gemma
    Embed -.-> KBMgr
    Orch -.-> Coll
    Coll --> LF2
    Coll -.-> Studio
```

### Caption: System overview — Variant A: Detailed Technical (validated against production code)

Shows every production component with its real port, code file, and function. Validated against `components/orchestrator/src/work_rag_orchestrator/graph.py`, `components/guardrails/src/work_rag_guardrails/`, `components/knowledgebase/kb-manager/kb_manager/web/routes/search.py`, and `components/server-setup/llm_inference_manager/app.py`.

```mermaid
flowchart TB
    subgraph Client["Client layer"]
        Browser[Browser]
        WebUI[Open WebUI :13000\nrag_trace_capture filter\nX-Request-ID sticky thread]
    end

    subgraph Orch["Orchestration :8100\nwork_rag_orchestrator"]
        API[api.py:create_app\nPOST /v1/chat/completions]
        GRAPH[graph.py:rag_graph\nMemorySaver checkpointer]
        VI[validate_input]
        CL[classify]
        HC[hybrid_classify]
        RET[retrieve]
        BC[build_context]
        GG[guarded_generate]
        FR[format_response]
        RF[format_refusal]
        GC[generate_clarification]
    end

    subgraph KB["Knowledgebase :8000\nkb_manager"]
        KBAPI[web/app.py:app\nPOST /search/api\nPOST /search/supplement]
        SEARCH[web/routes/search.py\nBM25 tantivy + dense MiniLM-384\nRRF k=60 bge-rerank\npgvector HNSW 1123 chunks]
        FILTER[filter_path · folder_hierarchy]
    end

    subgraph GR["Guardrails :8200\nwork_rag_guardrails"]
        GRAPI[api.py → service.py:create_app\nPOST /v1/rails/check\nPOST /v1/chat/completions]
        GJUDGE[service.py:judge\nsignals + LLM judge\nUPSTREAM Gemma :18000/:9000]
    end

    subgraph LLM["LLM Manager :9000\nllm_inference_manager/app.py"]
        MR[MODEL_REGISTRY\n11 models\ngemma-4-31b champion]
        GW[uvicorn :9000\nproxy_chat backends 8080-8084]
    end

    subgraph Obs["Observability"]
        Coll[Collector :3000\nobservability.db SQLite]
        LF2[Langfuse v2 :3001]
        Studio[Studio :2024\nLangGraph API]
    end

    Browser --> WebUI
    WebUI --> API
    API --> GRAPH
    GRAPH --> VI
    VI -->|blocked| RF
    VI -->|allowed| CL
    CL -->|greeting / spec| FR
    CL -->|question| RET
    RET --> SEARCH
    SEARCH --> FILTER
    RET -->|continue| BC
    BC --> GG
    GG --> GJUDGE
    GJUDGE --> MR
    GRAPH -.-> Coll
    Coll --> LF2
    Coll -.-> Studio
```

### Caption: System overview — Variant B: High-Level Black Box (executives / new team members)

Treats each major component as a black box and shows only the high-level data flow. No internal implementation details, file paths, or function names.

```mermaid
flowchart TB
    subgraph Client["Client layer"]
        User[User / Browser]
        WebUI[Open WebUI :13000]
    end

    subgraph Platform["RAG platform"]
        Orch[Orchestrator :8100\nLangGraph RAG graph]
        KB[Knowledgebase :8000\nHybrid retrieval]
        Guard[Guardrails :8200\nSafety + guarded generation]
        LLM[LLM Manager :9000\nModel registry]
    end

    subgraph Obs["Observability"]
        Coll[Collector :3000\nTraces + metrics]
        Langfuse[Langfuse :3001]
    end

    User --> WebUI
    WebUI --> Orch
    Orch --> KB
    Orch --> Guard
    Guard --> LLM
    Orch -.-> Coll
    Coll --> Langfuse
```

### Request flow — sticky + filtered RAG

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant W as WebUI :13000
    participant O as Orchestrator :8100
    participant K as KB :8000
    participant G as Guardrails :8200
    participant M as Gemma :18000
    participant Obs as Collector :3000

    U->>W: Persian message
    W->>W: rag_trace_capture: filter_path + X-Request-ID
    W->>O: POST /v1/chat/completions {messages, filter_path?, X-Request-ID}
    O->>Obs: trace-create(input)

    O->>G: validate_input (input rails)
    G-->>O: {allowed, action}

    alt blocked
        O->>O: format_refusal
        O-->>W: refusal (finish=content_filter)
    else allowed
        O->>O: classify (greeting/spec/question)
        alt greeting/spec
            O-->>W: format_response (no retrieval)
        else question
            alt should_clarify (scattered / threshold)
                O->>O: generate_clarification {question, available_subspaces}
                O-->>W: clarify (finish=clarify, no KB call)
            else retrieve
                O->>K: POST /search/api {query, top_k=20, filter_path?}
                K-->>O: SearchSteps {final_results, injected_entities}
                O->>K: POST /search/supplement {query, threshold=0.4}
                K-->>O: supplemental entity lists
                O->>O: build_context (MAX_CHUNKS=20, MAX_CONTEXT=9000)
                alt no evidence (<0.15)
                    O-->>W: abstain "پاسخی یافت نشد" (0 citations)
                else has evidence
                    O->>G: POST /v1/chat/completions (guarded_generate)
                    G->>M: llama-server chat
                    M-->>G: raw answer
                    G-->>O: {answer, guardrail_output}
                    O->>O: format_response (citations, grounded follow_ups, supplemental)
                    O->>Obs: trace-create upsert(output, audit)
                    O-->>W: {choices[0].message.content, rag:{citations, supplemental, follow_ups}, audit}
                end
            end
        end
    end
```

### Caption: Request flow — Variant A: Detailed Technical (validated against production code)

End-to-end sticky + filtered RAG request flow with real endpoints, ports, and node functions. Validated against `graph.py` (validate_input → classify → hybrid_classify → retrieve → build_context → guarded_generate → format_response), guardrails `POST /v1/rails/check` + `POST /v1/chat/completions`, KB `POST /search/api` + `POST /search/supplement`, and LLM Manager `:9000`.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant W as WebUI :13000
    participant O as Orchestrator :8100
    participant K as KB :8000
    participant G as Guardrails :8200
    participant M as LLM Manager :9000
    participant Obs as Collector :3000

    U->>W: Persian message
    W->>W: rag_trace_capture filter_path + X-Request-ID
    W->>O: POST /v1/chat/completions {messages, filter_path?, X-Request-ID}
    O->>Obs: trace-create input

    O->>G: POST /v1/rails/check validate_input input rails
    G-->>O: {allowed, action}

    alt blocked
        O->>O: format_refusal reuses format_response
        O-->>W: refusal finish=content_filter
    else allowed
        O->>O: classify greeting / spec / question
        alt greeting / spec
            O-->>W: format_response no retrieval
        else question
            alt should_clarify scattered / threshold
                O->>O: generate_clarification {question, available_subspaces}
                O-->>W: clarify finish=clarify no KB call
            else retrieve
                O->>K: POST /search/api {query, top_k=20, filter_path?}
                K-->>O: SearchSteps final_results injected_entities
                O->>K: POST /search/supplement {query, threshold=0.4}
                K-->>O: supplemental entity lists
                O->>O: build_context MAX_CHUNKS=20 MAX_CONTEXT=9000
                alt no evidence below 0.15
                    O-->>W: abstain no citations
                else has evidence
                    O->>G: POST /v1/chat/completions guarded_generate
                    G->>M: llama-server /v1/chat/completions
                    M-->>G: raw answer
                    G-->>O: {answer, guardrail_output}
                    O->>O: format_response citations grounded follow_ups
                    O->>Obs: trace-create upsert output audit
                    O-->>W: {choices[0].message.content, rag:{citations, supplemental, follow_ups}, audit}
                end
            end
        end
    end
```

### Caption: Request flow — Variant B: High-Level Black Box (executives / new team members)

Simplified sticky + filtered RAG flow. Major components are black boxes; only high-level data flow is shown. No internal implementation details.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant W as WebUI
    participant O as Orchestrator
    participant K as Knowledgebase
    participant G as Guardrails
    participant M as LLM
    participant Obs as Observability

    U->>W: Message
    W->>O: Request + request ID
    O->>G: Input safety check
    alt blocked
        O-->>W: Refusal
    else allowed
        O->>K: Retrieve context
        K-->>O: Results
        O->>G: Generate guarded answer
        G->>M: LLM completion
        M-->>G: Answer
        G-->>O: Guarded answer
        O-->>W: Response with citations
    end
    O->>Obs: Trace
```

### Orchestrator LangGraph graph

```mermaid
flowchart TD
    Start((Start))
    VI[validate_input]
    Cl[classify]
    HC[hybrid_classify]
    Ret[retrieve]
    Dec{{needs clarification?}}
    GC[generate_clarification]
    BC[build_context]
    GG[guarded_generate]
    FR[format_response]
    Ref[format_refusal]
    End((End))

    Start --> VI
    VI -->|blocked| Ref
    VI -->|allowed| Cl
    Cl -->|greeting / specification| FR
    Cl -->|question| HC
    HC --> Ret
    Ret --> Dec
    Dec -->|yes| GC
    Dec -->|no| BC
    GC --> End
    BC --> GG
    GG --> FR
    Ref --> End
    FR --> End
```

Graph nodes match `components/orchestrator/src/work_rag_orchestrator/graph.py`: `validate_input → classify → hybrid_classify → retrieve`, then conditional `should_clarify` branches to `generate_clarification` (ends) or `build_context → guarded_generate → format_response` (ends). Blocked input short-circuits to `format_refusal` (ends). Greeting/specification queries bypass retrieval and go straight to `format_response`.



### Caption: Orchestrator LangGraph — Variant A: Detailed Technical (validated against production code)

LangGraph state graph with real node names, file paths, ports, and conditional edge labels. Validated against `components/orchestrator/src/work_rag_orchestrator/graph.py`: nodes `validate_input`, `classify`, `hybrid_classify`, `retrieve`, `build_context`, `guarded_generate`, `format_response`, `format_refusal`, `generate_clarification`; conditional edges `should_continue_after_validation`, `should_route_after_classify`, `should_clarify`. Entry point is `validate_input`. `format_refusal` reuses the `format_response` function. `hybrid_classify` is reached only when `hybrid_classifier_enabled` is true.

```mermaid
flowchart TD
    Start((Start))
    VI[validate_input\nnodes/validate_input.py]
    Cl[classify\nnodes/classify.py]
    HC[hybrid_classify\nnodes/hybrid_classify_node.py]
    Ret[retrieve\nnodes/retrieve.py\nPOST /search/api :8000]
    Dec{should_clarify\nscattered / threshold}
    GC[generate_clarification\nnodes/generate_clarification.py]
    BC[build_context\nMAX_CHUNKS=20 MAX_CONTEXT=9000]
    GG[guarded_generate\nnodes/guarded_generate.py\nPOST /v1/chat/completions :8200]
    FR[format_response\nnodes/format_response.py]
    RF[format_refusal\nreuses format_response]
    End((End))

    Start --> VI
    VI -->|should_continue_after_validation blocked| RF
    VI -->|allowed| Cl
    Cl -->|should_route_after_classify greeting / spec| FR
    Cl -->|question direct retrieve| Ret
    Cl -->|question hybrid_classify| HC
    HC --> Ret
    Ret --> Dec
    Dec -->|clarify| GC
    Dec -->|continue| BC
    GC --> End
    BC --> GG
    GG --> FR
    RF --> End
    FR --> End
```

### Caption: Orchestrator LangGraph — Variant B: High-Level Black Box (executives / new team members)

Simplified LangGraph graph. Major nodes are black boxes; only the high-level control flow is shown. No internal implementation details, file paths, or function names.

```mermaid
flowchart TD
    Start((Start))
    Validate[Validate input]
    Classify[Classify query]
    Retrieve[Retrieve context]
    Clarify[Clarify if ambiguous]
    Build[Build context]
    Generate[Guarded generate]
    Format[Format response]
    Refuse[Format refusal]
    End((End))

    Start --> Validate
    Validate -->|blocked| Refuse
    Validate -->|allowed| Classify
    Classify -->|greeting / spec| Format
    Classify -->|question| Retrieve
    Retrieve -->|ambiguous| Clarify
    Retrieve -->|clear| Build
    Clarify --> End
    Build --> Generate
    Generate --> Format
    Refuse --> End
    Format --> End
```

</details>

<details>
<summary>Request lifecycle</summary>

1. **WebUI filter** (`components/openwebui-filters/rag_trace_capture.py`) — captures `filter_path` from scope/`[چک]` prefix, injects `X-Request-ID`, records trace start.
2. **`validate_input`** — Guardrails input rails; short-circuits to refusal if blocked.
3. **`classify` + `infer_specification`** — classifies `greeting/spec/question`; maps query to `applied_subspace` via `subspace_map`; `general` exempt from clarify gate.
4. **`should_clarify?`** — scattered/ambiguous query with no resolved subspace → `generate_clarification` returns `finish=clarify` with available subspaces, **no KB call**.
5. **`retrieve`** — `POST /search/api` with rewritten query, `top_k=20`, `filter_path` (explicit or sticky). KB returns `SearchSteps` + `injected_entities`. Parallel `POST /search/supplement` (threshold 0.4) for entity lists.
6. **`build_context`** — `MAX_CHUNKS=20`, `MAX_CONTEXT_CHARS=9000`; evidence guard per-subspace (`cheque 0.05`, `facilities_person 0.10`, `facilities_legal 0.15`, `general 0.15`) — below threshold → abstain.
7. **`guarded_generate`** — `Guardrails :8200 → Gemma :18000` (`enable_thinking:false`, `--no-mmproj --jinja`).
8. **`format_response`** — citations ≤20, `rag.supplemental`, grounded `follow_ups`, `stage_timing_ms`.
9. **Observability** — async trace to `:3000` (`observability.db`) + Langfuse `:3001`; DLQ `/tmp/dlq_retrieval.jsonl` on empty filtered retrieval.

`subspace_map`: `cheque → گزارش اعتبارسنجی چک`, `facilities_person → اشخاص حقیقی/اعتبارسنجی تسهیلات`, `facilities_legal → اشخاص حقوقی/اعتبارسنجی تسهیلات`, `general → پایگاه دانش عمومی`.

`filter_path` travels WebUI filter → Orchestrator → KB and sticks via `X-Request-ID` thread until re-specified (`چک` re-spec switches subspace).

</details>

<details>
<summary>Models &amp; libraries</summary>

| Role | Model | Version | Size | Key config |
|------|-------|---------|------|------------|
| Generation | Gemma 4 31B Instruct | `unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL` | 18.8 GiB | `--no-mmproj --jinja --ctx-size 8192 --temp 0.2` + `enable_thinking:false` |
| Embedding | paraphrase-multilingual-MiniLM-L12-v2 | `sentence-transformers/...` | 384-dim | `KB_EMBED_DEVICE=cpu/cuda` |
| Reranker | BGE-m3 `BAAI/bge-reranker-v2-m3` | default | 568M | `KB_RERANK_POOL=15` CPU / `30` GPU |
| Reranker fallback | MiniLM `mmarco-mMiniLMv2-L12-H384-v1` | — | 118M | lightweight fallback |
| Guardrails | Ghadeer mmBERT | toxicity/hate/intent | — | thresholds: toxicity 0.80, hate 0.80, PII 0.90, injection 0.85 |
| Judge (bench) | gemma-4-31b | via `:9000` | — | RAGAS LLM-as-judge |

Key production libraries (+ versions):

| Library | Version | Used by |
|---------|---------|---------|
| Python | 3.11 | all components |
| FastAPI | >=0.115.0 | orchestrator, guardrails, KB |
| uvicorn[standard] | >=0.30.0 | orchestrator, guardrails |
| pydantic / pydantic-settings | >=2.10.0 / >=2.5.0 | orchestrator, guardrails |
| httpx | >=0.27.0 | orchestrator, guardrails |
| langgraph | >=0.2.0 | orchestrator |
| langchain-core | >=0.3.0 | orchestrator |
| langfuse | >=2.60.0 | orchestrator, guardrails, tracing |
| opentelemetry-* | >=1.24.0 | orchestrator |
| sentence-transformers | — | KB, embed servers |
| scikit-learn | — | ambiguity SVM-RBF classifier |

</details>

<details>
<summary>Configuration — key environment variables</summary>

| Component | Variable | Default | Production (Vast) | Notes |
|-----------|----------|---------|-------------------|-------|
| Orchestrator | `ORCHESTRATOR_PORT` | 8100 | 8100 | public API |
| | `KB_BASE_URL` | `http://127.0.0.1:8000` | same | `kb_search_url = {KB}/search/api` |
| | `GUARDRAILS_BASE_URL` | `http://127.0.0.1:8200` | same | guarded generate + rails |
| | `retrieval_top_k` | 20 | 20 | up from 5 (MVP) |
| | `subspace_threshold` | 0.8 | 0.8 | clarify gate |
| | `evidence_min_score` | 0.15 | 0.15 | G5 hallucination guard |
| | `evidence_min_score_cheque` | 0.05 | 0.05 | per-subspace (T3) |
| | `evidence_min_score_facilities_person` | 0.10 | 0.10 | per-subspace (T3) |
| | `evidence_min_score_facilities_legal` | 0.15 | 0.15 | per-subspace (T3) |
| | `evidence_min_score_general` | 0.15 | 0.15 | per-subspace (T3) |
| | `MAX_CHUNKS` / `MAX_CONTEXT` | 20 / 9000 | 20 / 9000 | up from 5 / 6000 |
| | `hybrid_classifier_enabled` | false | false | SVM-RBF + Gemma escalation |
| | `hybrid_classifier_confidence_threshold` | 0.60 | 0.60 | escalate to Gemma when < |
| | `sticky_decay_turns` | 3 | 3 | generic-turn stale subspace |
| | `response_detail` | production | production | hides GT block |
| | `LANGFUSE_HOST` | `http://127.0.0.1:3001` | `http://127.0.0.1:3001` | `TRACE_ENABLED=true` |
| KB | `KB_WEB_PORT` | 8000 | 8000 | |
| | `KB_DB_URL` | `sqlite+aiosqlite:///./data/kb_test.db` | `postgresql+asyncpg://...:5432/kb_manager` | `mode=pgvector` → HNSW |
| | `KB_EMBED_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | same | 384-d |
| | `KB_RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | same | or MiniLM fallback |
| | `KB_RERANK_POOL` | 15 | 15 CPU / 30 GPU | |
| Guardrails | `GUARDRAILS_PORT` | 8200 | 8200 | |
| | `UPSTREAM_LLM_BASE_URL` | `http://127.0.0.1:9000/v1` | `http://127.0.0.1:18000/v1` | Vast bare Gemma |
| | `UPSTREAM_LLM_MODEL` | `gemma-4-31b` | `unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL` | |
| Gemma | `MODEL` | — | `/tmp/hf_clean/...UD-Q4_K_XL.gguf` | H200 uses manager `:9000` |
| | `CTX_SIZE` | 8192 | 8192 (4096 if OOM) | |
| WebUI | `OPENAI_API_BASE_URL` | — | `http://127.0.0.1:8100/v1` | ICS Helper |
| | `WEBUI_AUTH` | false | false | `true` for per-user `user_id` |

Full reference: `AGENTS.md` §1–4 and `components/orchestrator/src/work_rag_orchestrator/config.py`.

</details>

<details>
<summary>Observability &amp; services</summary>

| Tool | URL | Purpose |
|------|-----|---------|
| Unified Dashboard | `http://localhost:3000/dashboard/observability` | 8-stage chunk cards, subspace badge, export JSONL/CSV |
| Langfuse v2 | `http://localhost:3001` | Full trace UI (Postgres+ClickHouse) |
| Fallback Collector | `http://localhost:3000` | `POST /api/observability/traces` → `observability.db` + JSONL |
| Local Timeline | `http://localhost:3000/observe` | Request → validate → classify → retrieve → generate → format |
| Graph Debugger / Studio | `http://localhost:3000/studio` + `:2024` | LangGraph API threads/runs/state |
| KB dashboard & search tester | `http://localhost:8000` + `/search` | doc/chunk counts, pipeline transparency (`SearchSteps`) |
| Guardrails dashboard | `http://localhost:8200/dashboard` | decision counts, block rate, per-category bars |
| LLM Manager | `http://localhost:9000` | 11-model registry, health, load/unload (H200) |

Health check:
```bash
for p in 18000 8000 8200 8100 3000 9000 13000; do
  printf "%s: " "$p"; curl -s --max-time 8 http://127.0.0.1:$p/health | head -c 100; echo
done
curl -s --max-time 8 http://127.0.0.1:8100/ready | head -c 300; echo
```

</details>

<details>
<summary>Quick start</summary>

```bash
# 1. Clone with submodules
git clone --recurse-submodules https://github.com/AliNikkhah2001/Work_Credit-RAG_Phase1.git
cd Work_Credit-RAG_Phase1
git switch main
git submodule sync --recursive && git submodule update --init --recursive

# 2. Full startup (postgres → Gemma → KB → guardrails → collector → orchestrator → WebUI)
bash deploy/vast/start.sh

# 3. Health check
bash deploy/vast/health.sh

# 4. Access via SSH tunnel
ssh -p <ssh_port> root@<ssh_host> \
  -L 13000:localhost:13000 -L 8100:localhost:8100 \
  -L 3000:localhost:3000 -L 3001:localhost:3001 -L 2024:localhost:2024
# Open http://localhost:13000 (WebUI → ICS Helper)
# Open http://localhost:3000/dashboard/observability (unified trace dashboard)
# Open http://localhost:3001 (Langfuse)
```

H200 host: LLM manager `:9000` + Gemma backends `8080-8084` + embed `8001-8003` managed by `Work_RAG-Server-Setup`; Orchestrator points `GUARDRAILS` at `:9000` there.

Docker (privileged host only):
```bash
cd deploy/docker
cp .env.example .env   # Set MODEL_FILE to your Gemma GGUF path
docker compose up -d --build
# WebUI at http://<host>:13000
```

</details>

<details>
<summary>Changelog — summary by version</summary>

| Version | Date | Summary |
|---------|------|---------|
| v13 | 2026-10-28 | KB `1405-07-06`: 18 docs / 1123 chunks · `folder_hierarchy` + `filter_path` + `supplement` tool (cos 0.4/0.6) · pgvector HNSW |
| v13 | 2026-10-24 | Orchestrator LangGraph conditional clarify (`should_clarify` → `generate_clarification`), sticky `MemorySaver` (`X-Request-ID`), `MAX_CHUNKS=20/9000`, evidence `0.15` G5 guard, grounded `follow_ups`, DLQ; ambiguity resolver (SVM-RBF, 1000-sample dataset) |
| v12 | 2026-10-12 | Guardrails `:8200` Persian rails, HurtLex 19 lemmas, `enable_thinking:false` / `--no-mmproj --jinja` clean Persian; Generation Gemma 4 31B via `:18000` (Vast) / `:9000` manager (H200); embed trio `:8001-8003` |
| v11 | 2026-10-12 | WebUI `:13000` ICS Helper (Arena OFF) · `rag_trace_capture` filter + 4 actions (`rate`/`report`/`view`/`truth`) · `WEBUI_AUTH=false` |
| v10 | 2026-10-12 | Observability `:3000/dashboard/observability` (unified `observability.db`, chunk cards, subspace badge, export) + Langfuse `:3001` + Studio `:2024` |
| v9 | 2026-10-12 | Benchmark: multi-agent conversational 41 turns · RAGAS per-subspace · `docs/benchmark-report-2026-10-12.md` |

Pins: `main d1c9b33` + submodules `c3c7476`/`d040c63`/`14c5f97`/`d615f66` (historical); current live pins via `git submodule status --recursive`.

</details>

<details>
<summary>Done vs pending</summary>

Done:
- KB v13 with `filter_path`, `supplement` tool, pgvector HNSW
- Orchestrator LangGraph conditional clarify, sticky `MemorySaver`, evidence guard, grounded follow-ups
- Guardrails Persian rails, guarded Gemma `:8200`
- Generation Gemma 4 31B via `:18000`/`:9000`; embed trio `:8001-8003`
- WebUI ICS Helper with trace capture + 4 actions
- Observability unified dashboard + Langfuse + Studio
- 41-turn conversational benchmark with RAGAS per-subspace

Pending:
- Clarify gate: `0/6` scattered failures — lower `subspace_threshold` / explicit `ambiguous` classifier
- Evidence threshold per-subspace tuning (cheque `0.028` starves hits)
- Sticky carry: generic follow-ups lose `applied_subspace`
- Generation faithfulness — citation gate too strict on 2 abstains
- Latency — generation `5.3s` dominates; batch Gemma / reranker on GPU
- Supervision — `llama-server` nohup → supervisor

</details>

## CI/CD & Jenkins (dev / stage / prod)

Full operator guide: [`deploy/jenkins/README.md`](deploy/jenkins/README.md). Compose overlays: [`deploy/compose/README.md`](deploy/compose/README.md).  
GPU first-time Jenkins: [`components/server-setup/README.md`](components/server-setup/README.md) § Jenkins / CI on H200.

### Design (no paid webhook)

Jenkins **polls GitHub every hour** (`pollSCM` in root [`Jenkinsfile`](Jenkinsfile)). No Cloudflare tunnel required. After you push, either wait for the hourly scan or click **Scan Multibranch Pipeline Now** / **Build Now**.

| Space | Branch | What runs | LLM |
|-------|--------|-----------|-----|
| **dev** | `feature/*` / PR | lint + optional image build | — |
| **stage** | `develop` | build → `dana-stage` compose (alt ports) + E2E | OpenRouter (`LLM_UPSTREAM_MODE=openrouter`) on laptop |
| **prod** | `main` | build → `dana-prod` (laptop sim) or GPU self-hosted | OpenRouter on laptop; Gemma/Manager/TRT on H200 |

Self-hosted Gemma / TRT paths (`deploy/vast/`, `deploy/docker/`, server-setup manager) are **unchanged**. Laptop OpenRouter is used **only** when `DANA_ENV=test` and `LLM_UPSTREAM_MODE=openrouter` with `compose.local.yml`.

### Commit-message triggers (bold + red)

These tokens are case-insensitive and may appear anywhere in the commit subject/body:

| Token | Effect |
|-------|--------|
| $\textcolor{red}{\textbf{[ci skip]}}$ / $\textcolor{red}{\textbf{[skip ci]}}$ | Skip pipeline work |
| $\textcolor{red}{\textbf{[ci build]}}$ | Build Docker images |
| $\textcolor{red}{\textbf{[ci stage]}}$ | Build + **stage** deploy on `develop` — **no human approval** |
| $\textcolor{red}{\textbf{[ci prod]}}$ | Build + **prod** deploy on `main` — **no human approval** |
| $\textcolor{red}{\textbf{[ci auto]}}$ | Unattended: stage on `develop`, prod on `main` |

Without $\textcolor{red}{\textbf{[ci prod]}}$ / $\textcolor{red}{\textbf{[ci auto]}}$ on `main`, Jenkins still asks for a manual **Deploy** confirmation if a build was requested.

```bash
# Stage (develop) — unattended after poll/scan
git commit -m "feat: retrieval tweak [ci stage]"
git push origin develop

# Prod (main) — unattended (laptop prod-sim or H200 when DANA_HOST=gpu)
git commit -m "chore: release pins [ci prod]"
git push origin main

# Skip noise
git commit -m "docs: fix typo [ci skip]"
```

Gate logic (local test): `python3 scripts/ci_message_gate.py --self-test`

### CI architecture

```mermaid
flowchart LR
  subgraph gh [GitHub]
    feat[feature branches]
    develop[develop]
    main[main]
  end
  subgraph jen [Jenkins pollSCM hourly]
    gate[ci_message_gate keys]
    build[docker compose build]
    stage[dana-stage]
    prod[dana-prod / GPU]
  end
  feat -->|PR or ci build| gate
  develop -->|ci stage / ci auto| gate
  main -->|ci prod / ci auto| gate
  gate --> build
  build --> stage
  build --> prod
```

### Docker containers (laptop test stack)

| Service | Port (local) | Image |
|---------|--------------|-------|
| Open WebUI | `13000` | `ghcr.io/open-webui/open-webui` |
| Orchestrator | `8100` | `rag-orchestrator` |
| Guardrails | `8200` | `rag-guardrails` |
| KB | `8000` | `rag-kb` |
| LiteLLM | `4000` | LiteLLM (OpenRouter) |
| Postgres pgvector | `15432` | `pgvector/pgvector` |
| Redis | `16379` | `redis:7` |
| Tracing | `13002` | `rag-tracing` |
| Jenkins | `8085` | `jenkins/jenkins:lts` |

Stage uses alt ports (`18100`, `18200`, …) via `compose.stage.yml`.

### Server first-boot checklist (GPU / production host)

Laptop Jenkins and GPU Jenkins are **two separate controllers**. Same GitHub repo and commit keys; **different** `jenkins_home` (admin password, jobs, credentials). The `dana-jenkins:lts` image is reusable software — it does **not** carry your laptop password or job history unless you explicitly migrate the volume.

Do this **once** on the production GPU server (H200 / Vast with GPU):

| Step | Action | Notes |
|------|--------|-------|
| 0 | **Prereqs** | Docker Engine, NVIDIA Container Toolkit, `nvidia-smi` OK, GitHub PAT (repo read), disk for images + HF cache |
| 1 | **Clone umbrella** | `git clone --recurse-submodules https://github.com/AliNikkhah2001/Work_Credit-RAG_Phase1.git` then `cd Work_Credit-RAG_Phase1` |
| 2 | **Bring up LLMs first** | Manager `:9000` / TRT / `deploy/vast/start.sh` Gemma `:18000` — CI only rebuilds **app** containers (KB, guardrails, orchestrator, webui, …), not the model servers |
| 3 | **Prod env file** | Create gitignored `deploy/compose/.env.prod` with `DANA_ENV=prod`, `DANA_HOST=gpu`, `LLM_UPSTREAM_MODE=self_hosted`, `UPSTREAM_LLM_BASE_URL=…`, `KB_EMBED_DEVICE=cuda`, `KB_RERANKER_DEVICE=cuda`. **No OpenRouter keys** on this host |
| 4 | **Fix Jenkins host path** | Edit `deploy/jenkins/docker-compose.yml`: replace the Mac absolute bind with **this server’s** clone path (same path inside the container and on the host so `docker.sock` bind mounts work). Set `DANA_HOST_REPO` to that path |
| 5 | **Start Jenkins** | `docker compose -f deploy/jenkins/docker-compose.yml up -d --build` → UI `:8085` |
| 6 | **Wizard / admin** | Fresh volume → new admin password (`docker exec dana-jenkins cat /var/jenkins_home/secrets/initialAdminPassword`). Optional: `docker load` a saved `dana-jenkins:lts` image to skip rebuild; still a **new** Jenkins unless you restore `jenkins_home` |
| 7 | **Plugins** | Pipeline, Git, GitHub Branch Source, Docker Pipeline / docker-workflow (image already aims to include CLI tools) |
| 8 | **Credentials** | System credential `github-pat` only (username + PAT). Do **not** copy laptop OpenRouter secrets |
| 9 | **Multibranch job** | Name `dana-rag` → GitHub `AliNikkhah2001/Work_Credit-RAG_Phase1` → branches `main` (required), optionally `develop` → Jenkinsfile at repo root. Prefer **prod-only** on GPU (`main`); keep stage on laptop |
| 10 | **Agent env** | Controller/agent env: `DANA_HOST=gpu` so Jenkinsfile uses `compose.gpu.yml` for prod |
| 11 | **Smoke** | From laptop: `git push origin main` with $\textcolor{red}{\textbf{[ci prod]}}$ → on server **Scan Multibranch** / wait for hourly poll → confirm `:8100` chat and `LLM_UPSTREAM_MODE=self_hosted` |
| 12 | **Ops** | Never `pkill python`; use `bash deploy/vast/stop.sh`. Keep Gemma/postgres loopback-only. Backup `jenkins_home` volume if you care about job history |

Detailed twin of this list: [`deploy/jenkins/README.md`](deploy/jenkins/README.md) and [`components/server-setup/README.md`](components/server-setup/README.md) § Jenkins / CI on H200.

```mermaid
flowchart TB
  subgraph laptop [Laptop Jenkins]
    stageKey["develop + ci stage"]
    danaStage[dana-stage OpenRouter]
  end
  subgraph gpu [GPU Jenkins]
    prodKey["main + ci prod"]
    danaProd[compose.gpu self_hosted]
  end
  gh[GitHub Work_Credit-RAG_Phase1] --> laptop
  gh --> gpu
  stageKey --> danaStage
  prodKey --> danaProd
  models[Manager / TRT / Gemma already up] --> danaProd
```

### Promote stage → prod — how it works & how to use (Sprint C)

**Promotion is not automatic.** Stage (`develop` + laptop Jenkins) and prod (`main` + GPU Jenkins) are separate controllers. Moving a known-good stage tip into prod means: merge `develop` → `main` with an explicit $\textcolor{red}{\textbf{[ci prod]}}$ key so the **prod** controller rebuilds/restarts app containers. Models (Gemma / Manager / TRT) are **not** part of promote or rollback.

```mermaid
flowchart LR
  feat[feature/*] -->|PR / merge| develop
  develop -->|laptop Jenkins + ci stage| stageOK[dana-stage green]
  stageOK -->|promote script or PR| main
  main -->|GPU Jenkins + ci prod| prodOK[dana-prod up]
  prodOK --> lastGood[".last_good_sha"]
  lastGood -.->|ci rollback| prodOK
```

| Step | What you do | What happens |
|------|-------------|--------------|
| 1. Land work on stage | Merge to `develop` with $\textcolor{red}{\textbf{[ci stage]}}$ (or $\textcolor{red}{\textbf{[ci auto]}}$) | Laptop Jenkins builds changed services (`CI_SERVICES`), deploys `dana-stage`, runs E2E curl |
| 2. Confirm stage | Check Multibranch green + chat on stage ports | Do **not** promote a red build |
| 3. Dry-run promote | `bash scripts/promote_stage_to_main.sh` | Prints `develop`/`main` SHAs, submodule pins, suggested PR title/body — **no merge** |
| 4. Promote | Prefer PR `develop` → `main` (template: `.github/pull_request_template_promote.md`) with title containing $\textcolor{red}{\textbf{[ci prod]}}$; or `bash scripts/promote_stage_to_main.sh --execute --push` | `main` advances; GPU Jenkins polls (or Scan Now) and runs Deploy prod |
| 5. Record last-good | Automatic after successful Deploy prod | `scripts/ci_record_last_good.sh` writes host-local `deploy/compose/.last_good_sha` (gitignored); previous tip → `.last_good_sha.prev` |
| 6. Break-glass rollback | On `main`, empty commit with $\textcolor{red}{\textbf{[ci rollback]}}$ (prod controller only), or `bash scripts/ci_rollback.sh [--dry-run] [--sha …]` | Restores **app** compose stack to previous good SHA; Gemma/TRT untouched |

**Rules of thumb**

- Docs-only / no deploy → $\textcolor{red}{\textbf{[ci skip]}}$ on the merge commit so prod does not redeploy.
- Wrong controller cannot promote: laptop has `CI_MAY_DEPLOY_PROD=0`; GPU has `CI_MAY_DEPLOY_STAGE=0`.
- Rollback prefers `.last_good_sha.prev` (the SHA from *before* the bad deploy). If neither file exists, rollback fails until a successful prod has recorded one.
- More operator examples: [`deploy/jenkins/README.md`](deploy/jenkins/README.md).

### CI/CD roadmap checklist (gate each sprint)

Work proceeds **one sprint at a time**: implement → test on laptop Jenkins → **your approval** → next sprint.

**Done so far (2026-11-10)**

| Sprint | IDs | What shipped |
|--------|-----|--------------|
| **A** | #8 | Separate stage/prod Jenkins controllers (`DANA_ROLE` / `DANA_HOST`); wrong host cannot deploy the other space |
| **B** | #1 · #2 | Path → `CI_SERVICES` builds; `ci_submodule_sync.sh` with retries / loud missing-SHA fail |
| **C** | #3 · #10 | Promote dry-run/execute script + PR template; last-good recording; $\textcolor{red}{\textbf{[ci rollback]}}$ |

**Next up:** Sprint **D** (#4 GHCR). Pending: **E** eval smoke · **F** notifications · **G** JCasC.

| Sprint | ID | Deliverable | Test / acceptance | Status |
|--------|-----|-------------|-------------------|--------|
| **A** | **#8** Separate jobs | Laptop Multibranch = stage (`develop` / `feature/*`); GPU Multibranch = prod (`main` only). Jenkinsfile respects `DANA_HOST` / `DANA_ROLE` so the wrong controller cannot deploy the other space. Docs updated. | Laptop: `[ci stage]` still deploys `dana-stage`. Confirm GPU job config docs say `main` only + no OpenRouter. | ✅ done 2026-11-10 |
| **B** | **#1** Path / per-service builds | Gate emits which services to build (`kb`, `guardrails`, `orchestrator`, … or `all`). Compose builds/restarts only those (full stack if compose/Jenkinsfile/`all`). | Path→service unit tests; Jenkins shows `SERVICES=…`; `[ci all]` forces full set. | ✅ done 2026-11-10 |
| **B** | **#2** Submodule-aware checkout | Retries on fetch/submodule update; clear error if gitlink SHA missing on remote. | `ci_submodule_sync` OK on stage builds; loud fail on missing SHA. | ✅ done 2026-11-10 |
| **C** | **#3** Promote path | `scripts/promote_stage_to_main.sh` + `.github/pull_request_template_promote.md`: stage green + pin SHAs → `main` + $\textcolor{red}{\textbf{[ci prod]}}$. | Dry-run prints pins; `--execute` merges locally (no silent prod without key). | ✅ done 2026-11-10 |
| **C** | **#10** Rollback | Prod success → `ci_record_last_good.sh` writes `.last_good_sha`. $\textcolor{red}{\textbf{[ci rollback]}}$ on `main` (prod controller) restores apps via `ci_rollback.sh`. Models (Gemma/TRT) not auto-rolled. | Gate self-test; dry-run rollback; record/restore SHA round-trip. | ✅ done 2026-11-10 |
| **D** | **#4** Registry (GHCR) | Stage builds push `rag-*:gitsha`; GPU prod prefers `pull` + `up`, build only as fallback. | GPU cold deploy with pull works for unchanged services. | ☐ pending |
| **E** | **Eval module / CI smoke** | Formalize CI entrypoint (e.g. `eval/ci_smoke.py`) over existing `eval/` scripts; fixed exit codes; Jenkins stage after deploy. Optional later: `components/evaluation` submodule — **design approval required before large move**. | Smoke suite fails the build on quality/infra fail; passes on known-good stage. | ☐ pending (design first) |
| **F** | **#6** Notifications | GitHub commit statuses / Checks (fastest; no SMTP). Statuses for stage and prod. | Commit page shows `dana-stage` / `dana-prod` success/failure. | ☐ pending |
| **G** | **#9** JCasC | Jenkins Configuration as Code YAML for Multibranch + credential **IDs** (PAT still injected as secret). Reproducible first-boot. | Fresh Jenkins + CasC recreates jobs without click-wizard (PAT via env). | ☐ pending |

**How we run this process**

1. Update this table’s **Status** when a sprint starts / finishes (`☐ pending` → `… in progress` → `✅ done` + date).
2. After each sprint: commit on `develop`, PR → `main` when you ask to merge, then wait for approval before the next sprint.
3. Commit keys stay authoritative for deploy: $\textcolor{red}{\textbf{[ci stage]}}$, $\textcolor{red}{\textbf{[ci prod]}}$, $\textcolor{red}{\textbf{[ci auto]}}$, $\textcolor{red}{\textbf{[ci skip]}}$, $\textcolor{red}{\textbf{[ci rollback]}}$.
4. Day-to-day **promote / rollback** usage is in the section above (not the pending D–G rows).

Operator detail for Jenkins bring-up remains above and in [`deploy/jenkins/README.md`](deploy/jenkins/README.md).

---

## Verification

```bash
# Health all services
for p in 18000 8000 8200 8100 3000 9000 13000; do
  printf "%s: " "$p"; curl -s --max-time 8 http://127.0.0.1:$p/health | head -c 100; echo
done

# RAG E2E (sticky + filter_path)
curl -s http://127.0.0.1:8100/v1/chat/completions -H 'Content-Type: application/json' -H 'X-Request-ID: test-001' \
  -d '{"model":"ics-helper-agent","messages":[{"role":"user","content":"چک"}],"filter_path":"گزارش اعتباری چک"}' | jq '.audit.applied_subspace'
curl -s http://127.0.0.1:8100/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"ics-helper-agent","messages":[{"role":"user","content":"اعتبارسنجی چیست؟"}]}' | jq -c '{finish:.choices[0].finish_reason, citations:(.rag.citations|length)}'

# KB filtered vs supplement
curl -s http://127.0.0.1:8000/search/api -H 'Content-Type: application/json' -d '{"query":"سهامداران","top_k":5}' | jq '.injected_entities|length'
curl -s http://127.0.0.1:8000/search/supplement -H 'Content-Type: application/json' -d '{"query":"سهامداران","threshold":0.4}' | jq '.results|length'
```

## Updating a submodule

```bash
cd components/orchestrator
git switch main && git pull --ff-only
cd ../..
git add components/orchestrator
git commit -m "chore: advance orchestrator submodule"
```

Always run health + `python3 -m evaluation.bench_runner --dry-run` before advancing a production pin.

---

## License

See [LICENSE](LICENSE). Each submodule may also declare its own license and dependency obligations.

## Links

- Runbook: [AGENTS.md](AGENTS.md) §2–3 + `deploy/vast/start.sh` + `deploy/vast/health.sh`
- CI/CD: [deploy/jenkins/README.md](deploy/jenkins/README.md) · Compose: [deploy/compose/README.md](deploy/compose/README.md)
- Bench report: [docs/benchmark-report-2026-10-12.md](docs/benchmark-report-2026-10-12.md) (also `evaluation/artifacts/bench_report_latest.html`)
- Compose: [compose.mvp.yml](compose.mvp.yml) + [deploy/docker/docker-compose.yml](deploy/docker/docker-compose.yml)
- Guardrails allowlist: `components/guardrails/kb/hurtlex_allowlist.json`
- Evaluation docs: [docs/evaluation.md](docs/evaluation.md) · [docs/cross_encoder_benchmark_results.md](docs/cross_encoder_benchmark_results.md)

<!-- docs-toc:start -->
## Documentation Index

> Auto-generated from this repository's tracked Markdown notes (**129** files). Refresh with `python scripts/gen_readme_toc.py` — the `docs-toc` workflow does this automatically on push.

### Repository root

- [AGENTS.md — Agent Operating Manual (umbrella repo)](AGENTS.md) — Umbrella repo; implementation lives in submodules. Do NOT duplicate component code in parent.
- [DevOps & Deployment Research Plan — Work Credit RAG Phase 1](DEVOPS_RESEARCH_PLAN.md) — 1. Multi-service Docker Compose for privileged hosts (H200, local dev)

### `.opencode/`

- [Plan: Fix 142 Code Audit Errors (2026-09-27)](.opencode/plans/audit-fix-2026-09-27.md) — 1. git switch -c chore/fix-critical-kb in components/knowledgebase

### `archive/`

- [Archive — Non-code artifacts](archive/README.md) — This directory holds artifacts moved off main during chore/cleanup-consolidated.
- [Documentation Audit — Work Credit RAG Phase 1](archive/audit-2026-09-12/documentation_audit.md) — Generated: 2026-09-12 | Auditor: Agent 1 (Repository Documentation Explorer)
- [Documentation Changes Summary](archive/audit-2026-09-12/documentation_changes.md) — Generated: 2026-09-12 | Agents 1-8 Documentation Upgrade
- [Final Documentation Review Checklist](archive/audit-2026-09-12/final_review_checklist.md) — Generated: 2026-09-12 | Agent 8 — Final Review
- [Archived Benchmark Scripts](archive/benchmark-scripts/README.md) — Two near-duplicate reranker benchmark scripts archived from scripts/ — canonical is scripts/cross_encoder_benchmark.py.
- [Opencode session export](archive/handoff-sessions/SESSION_WAVE1_HANDOFF.md) — Session: ses_f6b058c02ffej8lpFUThWHsld0
- [Session index](archive/handoff-sessions/sessions/INDEX.md)
- [Commit + push all repos (@general subagent)](archive/handoff-sessions/sessions/ses_f662eaa09ffek59tAqzqgrzmk3_commit-push-all-repos-general-subagent.md) — Session: ses_f662eaa09ffek59tAqzqgrzmk3
- [Validate stack + E2E smoke (@general subagent)](archive/handoff-sessions/sessions/ses_f662eaa2cffeqIf44RU7HD6lr5_validate-stack-e2e-smoke-general-subagen.md) — Session: ses_f662eaa2cffeqIf44RU7HD6lr5
- [Finish wave-1 bench + aggregate (@general subagent)](archive/handoff-sessions/sessions/ses_f662eaa64ffeVRZClGRfuksXF6_finish-wave-1-bench-aggregate-general-su.md) — Session: ses_f662eaa64ffeVRZClGRfuksXF6
- [Fact-check guardrails+setup (@general subagent)](archive/handoff-sessions/sessions/ses_f69bd0067ffeYkQj7BGbueJNdi_fact-check-guardrails-setup-general-suba.md) — Session: ses_f69bd0067ffeYkQj7BGbueJNdi
- [Fact-check KB submodule (@general subagent)](archive/handoff-sessions/sessions/ses_f69bd00e1ffeZpMuACZP7ACDqh_fact-check-kb-submodule-general-subagent.md) — Session: ses_f69bd00e1ffeZpMuACZP7ACDqh
- [Fact-check orchestrator (@general subagent)](archive/handoff-sessions/sessions/ses_f69bd0132ffe2p2YKzUyAoAX4g_fact-check-orchestrator-general-subagent.md) — Session: ses_f69bd0132ffe2p2YKzUyAoAX4g
- [Fact-check root+deploy (@general subagent)](archive/handoff-sessions/sessions/ses_f69bd0148ffeo0kdaWGrhDa6gn_fact-check-root-deploy-general-subagent.md) — Session: ses_f69bd0148ffeo0kdaWGrhDa6gn
- [Doc explorer inventory (@general subagent)](archive/handoff-sessions/sessions/ses_f69bd019cffe7w8mbt1Nvf53kO_doc-explorer-inventory-general-subagent.md) — Session: ses_f69bd019cffe7w8mbt1Nvf53kO
- [Audit mystery observe code (@general subagent)](archive/handoff-sessions/sessions/ses_f69fe249effefURDV1vv5x7Ttk_audit-mystery-observe-code-general-subag.md) — Session: ses_f69fe249effefURDV1vv5x7Ttk
- [Find observability tooling (@explore subagent)](archive/handoff-sessions/sessions/ses_f6a50d043ffe5vMowwTpZc2eul_find-observability-tooling-explore-subag.md) — Session: ses_f6a50d043ffe5vMowwTpZc2eul
- [Find conversation history (@explore subagent)](archive/handoff-sessions/sessions/ses_f6a50d05cffef0ThivrPDUeYeI_find-conversation-history-explore-subage.md) — Session: ses_f6a50d05cffef0ThivrPDUeYeI
- [RAG agent history location and observability](archive/handoff-sessions/sessions/ses_f6a50ebb5ffeHsJtLNMo7LEtg5_rag-agent-history-location-and-observabi.md) — Session: ses_f6a50ebb5ffeHsJtLNMo7LEtg5
- [FlagEmbedding big-model loaders (@general subagent)](archive/handoff-sessions/sessions/ses_f6a52d486ffeKuQPQG2ppRetTT_flagembedding-big-model-loaders-general.md) — Session: ses_f6a52d486ffeKuQPQG2ppRetTT
- [Orchestrator memory code (@general subagent)](archive/handoff-sessions/sessions/ses_f6a575eeaffeM2uwbOgHGye6ef_orchestrator-memory-code-general-subagen.md) — Session: ses_f6a575eeaffeM2uwbOgHGye6ef
- [KB reranker registry code (@general subagent)](archive/handoff-sessions/sessions/ses_f6a575ef9ffenaUjaoyJIMHrEG_kb-reranker-registry-code-general-subage.md) — Session: ses_f6a575ef9ffenaUjaoyJIMHrEG
- [Download rerankers set B (@general subagent)](archive/handoff-sessions/sessions/ses_f6a575f11fferEABLFMd57wGM6_download-rerankers-set-b-general-subagen.md) — Session: ses_f6a575f11fferEABLFMd57wGM6
- [Download 9B reranker (@general subagent)](archive/handoff-sessions/sessions/ses_f6a575f29ffecMT5puzXMjSxCv_download-9b-reranker-general-subagent.md) — Session: ses_f6a575f29ffecMT5puzXMjSxCv
- [Download rerankers set A (@general subagent)](archive/handoff-sessions/sessions/ses_f6a575f42ffe8YMbPSYvlfdqbA_download-rerankers-set-a-general-subagen.md) — Session: ses_f6a575f42ffe8YMbPSYvlfdqbA
- [Map reranker and memory code (@explore subagent)](archive/handoff-sessions/sessions/ses_f6a5ca448ffe8q908qHWfK4yfS_map-reranker-and-memory-code-explore-sub.md) — Session: ses_f6a5ca448ffe8q908qHWfK4yfS
- [Write docker stack files (@general subagent)](archive/handoff-sessions/sessions/ses_f6a7738f9ffe6RAZA5rnjuvxBe_write-docker-stack-files-general-subagen.md) — Session: ses_f6a7738f9ffe6RAZA5rnjuvxBe
- [Write AGENTS.md + commands (@general subagent)](archive/handoff-sessions/sessions/ses_f6a773916ffeTskweHocLEiRAC_write-agents-md-commands-general-subagen.md) — Session: ses_f6a773916ffeTskweHocLEiRAC
- [Build real Langfuse v2 UI (@general subagent)](archive/handoff-sessions/sessions/ses_f6a97a23affe977umsOKmNDWKm_build-real-langfuse-v2-ui-general-subage.md) — Session: ses_f6a97a23affe977umsOKmNDWKm
- [Setup LangGraph Studio (@general subagent)](archive/handoff-sessions/sessions/ses_f6a97a260ffeNWjOmUVpgAKRNd_setup-langgraph-studio-general-subagent.md) — Session: ses_f6a97a260ffeNWjOmUVpgAKRNd
- [Create py venvs install deps (@general subagent)](archive/handoff-sessions/sessions/ses_f6ad8e88effer0fXVBgn30KyXr_create-py-venvs-install-deps-general-sub.md) — Session: ses_f6ad8e88effer0fXVBgn30KyXr
- [Setup postgres pgvector DB (@general subagent)](archive/handoff-sessions/sessions/ses_f6ad8e89dffegpnjRGd8kSSLW1_setup-postgres-pgvector-db-general-subag.md) — Session: ses_f6ad8e89dffegpnjRGd8kSSLW1
- [Build llama.cpp CUDA (@general subagent)](archive/handoff-sessions/sessions/ses_f6ad8e8c3ffeKEoTAsrQxIu6Ya_build-llama-cpp-cuda-general-subagent.md) — Session: ses_f6ad8e8c3ffeKEoTAsrQxIu6Ya
- [Explore llama-server build/run docs (@explore subagent)](archive/handoff-sessions/sessions/ses_f6ae9b92dffeCirKJEEjVK2fdE_explore-llama-server-build-run-docs-expl.md) — Session: ses_f6ae9b92dffeCirKJEEjVK2fdE
- [Explore orchestrator+guardrails run (@explore subagent)](archive/handoff-sessions/sessions/ses_f6ae9f317ffeSmRPrDg6hREnnA_explore-orchestrator-guardrails-run-expl.md) — Session: ses_f6ae9f317ffeSmRPrDg6hREnnA
- [Explore KB pgvector setup (@explore subagent)](archive/handoff-sessions/sessions/ses_f6aea1199ffe0EIUQ3IBkDuBL2_explore-kb-pgvector-setup-explore-subage.md) — Session: ses_f6aea1199ffe0EIUQ3IBkDuBL2
- [Sync orchestrator git (@general subagent)](archive/handoff-sessions/sessions/ses_f6af2b3a1ffeqp0RpKmQCp9t0g_sync-orchestrator-git-general-subagent.md) — Session: ses_f6af2b3a1ffeqp0RpKmQCp9t0g
- [Sync guardrails git (@general subagent)](archive/handoff-sessions/sessions/ses_f6af2c18effebM96RGD21aMR6h_sync-guardrails-git-general-subagent.md) — Session: ses_f6af2c18effebM96RGD21aMR6h
- [Sync knowledgebase git (@general subagent)](archive/handoff-sessions/sessions/ses_f6af2da53ffeZAu3vFPZU39v3C_sync-knowledgebase-git-general-subagent.md) — Session: ses_f6af2da53ffeZAu3vFPZU39v3C
- [Sync server-setup git (@general subagent)](archive/handoff-sessions/sessions/ses_f6af303aaffe5bPJzZj0L31OED_sync-server-setup-git-general-subagent.md) — Session: ses_f6af303aaffe5bPJzZj0L31OED
- [Sync parent repo git (@general subagent)](archive/handoff-sessions/sessions/ses_f6af32e65ffe85ebRy2z0t20qB_sync-parent-repo-git-general-subagent.md) — Session: ses_f6af32e65ffe85ebRy2z0t20qB
- [Find chat history for RAG agent project](archive/handoff-sessions/sessions/ses_f6b058c02ffej8lpFUThWHsld0_find-chat-history-for-rag-agent-project.md) — Session: ses_f6b058c02ffej8lpFUThWHsld0
- [Handoff Archive](archive/handoff/README.md) — Raw evaluation artifacts moved from handoff/ on chore/cleanup-phase2.
- [Vast.ai Gemma-4 Migration — Execution Log](archive/migration-history/VAST_GEMMA4_MIGRATION.md) — Discovery report (architecture map, 14 inspection items, H/I/J/K/L findings) approved before this log.
- [Wave-2 GPU Runbook — heavy reranker shootout on a bigger machine](archive/migration-history/WAVE2_GPU_RUNBOOK.md) — Date: 2026-09-13. Wave 1 (CPU, 800 remapped queries) is done for
- [Guardrails v2 Plan — Risk Scoring + Semantic + Observability](archive/plans/GUARDRAILS_V2_PLAN.md) — Every POST /v1/rails/check and POST /v1/chat/completions will expose (in logs and optional response header X-Guardrails-Observability):
- [Task: reranker benchmark + conversation memory (branch feat/reranker-memory)](archive/plans/RERANKER_MEMORY_TASK.md) — 1. Compare cross-encoder rerankers (incl. biggest SOTA) on our Persian credit KB and pick the winner.
- [Vast.ai Runbook — Work Credit RAG Phase 1 (Public)](archive/plans/RUNBOOK_VAST.md) — Existing Gemma is external http://127.0.0.1:18000/v1 (unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL, llama-server pid 676). Do NOT launch gemma-manager, do…
- [System Architecture — Work Credit RAG Phase 1](archive/plans/architecture.md)
- [Model Cards — Work Credit RAG Phase 1](archive/plans/models.md)
- [Training & Pipeline — Work Credit RAG Phase 1](archive/plans/training.md) — 1. Fresh corpus from kb-source/1405-05-31/ (legal/individual/other/technical)
- [Quarantine](archive/quarantine/20261110/README.md) — Trees moved here pending confirmation E2E stays green, then safe-delete from main/develop history via archive branch.
- [Deprecated Files — Reconstruction Guide](archive/quarantine/20261110/deprecated/README.md) — These files were moved here on 2026-09-27 during a repository cleanup.
- [AGENTS — Fix Plan for 142 Audit Errors (2026-09-27)](archive/quarantine/20261110/deprecated/audits/AGENTS_FIX_PLAN.md) — This file is the agent operating manual for fixing the audit. Use with AGENTS.md (repo map, ports, workflows) and README.md (architecture). For how t…
- [Plan: Fix 142 Code Audit Errors (2026-09-27)](archive/quarantine/20261110/deprecated/audits/opencode_audit-fix-2026-09-27.md) — 1. git switch -c chore/fix-critical-kb in components/knowledgebase
- [GUARDRAILS_V2_PLAN — Archived](archive/quarantine/20261110/deprecated/plans/GUARDRAILS_V2_PLAN.md) — Historical content archived at archive/plans/GUARDRAILS_V2_PLAN.md (2026-09-27, chore/cleanup-phase2).
- [Work Credit RAG Integration Plan](archive/quarantine/20261110/deprecated/plans/MVP_INTEGRATION_PLAN.md) — This plan converts Work_Credit-RAG_Phase1 from a monolithic prototype into the composition and release repository for four independently maintained c…
- [Work Credit RAG — Full Project Hierarchy](archive/quarantine/20261110/deprecated/plans/PROJECT_HIERARCHY.md) — Generated: 2026-09-27 | Root: /splunk-data/v1/Work_Credit-RAG_Phase1 | Branch: main @ f402517
- [RERANKER_MEMORY_TASK — Archived](archive/quarantine/20261110/deprecated/plans/RERANKER_MEMORY_TASK.md) — Historical content archived at archive/plans/RERANKER_MEMORY_TASK.md (2026-09-27, chore/cleanup-phase2).
- [RUNBOOK_VAST — Archived](archive/quarantine/20261110/deprecated/plans/RUNBOOK_VAST.md) — Historical content archived at archive/plans/RUNBOOK_VAST.md (2026-09-27, chore/cleanup-phase2).
- [architecture — Archived](archive/quarantine/20261110/deprecated/plans/architecture.md) — Historical content archived at archive/plans/architecture.md (2026-09-27, chore/cleanup-phase2).
- [models — Archived](archive/quarantine/20261110/deprecated/plans/models.md) — Historical content archived at archive/plans/models.md (2026-09-27, chore/cleanup-phase2).
- [training — Archived](archive/quarantine/20261110/deprecated/plans/training.md) — Historical content archived at archive/plans/training.md (2026-09-27, chore/cleanup-phase2).
- [Continuation prompt — paste into a new opencode session on the bigger GPU machine](archive/quarantine/20261110/deprecated/session-artifacts/handoff_CONTINUE.md) — You are continuing the Persian Credit RAG Phase-1 project. Context files (read first):
- [Handoff — Archived](archive/quarantine/20261110/deprecated/session-artifacts/handoff_README.md)
- [COMMANDS.md — Vast.ai command reference (instance 50713720, 2026-09-12, 1x RTX 3090)](archive/quarantine/20261110/deprecated/session-artifacts/vast_COMMANDS.md) — Copy-pasteable. Root = /workspace/Work_Credit-RAG_Phase1. All RAG services bind 0.0.0.0 except Gemma (127.0.0.1:18000 by design).
- [Opencode session export](archive/quarantine/20261110/deprecated/session-artifacts/vast_SESSION_WAVE1_HANDOFF.md) — Session: ses_f6b058c02ffej8lpFUThWHsld0
- [Quarantined report materials](archive/quarantine/20261110/docs/README.md) — Large PDF/zip outputs were not committed (GitHub push size limits).
- [Work Credit RAG — Technical Report](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/README.md) — Classic KOMA-Script (scrreprt) documentation for شرکت اعتبارسنجی ایران / Work Credit RAG Phase 1.
- [نامهٔ فنی — معرفی سامانهٔ دانا و نیازمندی‌های زیر‌ساخت](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/docs/letters/dana_infra_needs_letter_fa.md) — با سلام و احترام،
- [Eval: 04_dive_kb.md](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/eval/04_dive_kb_eval.md)
- [Eval: 05_dive_orch.md](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/eval/05_dive_orch_eval.md)
- [Eval: 06_dive_server.md](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/eval/06_dive_server_eval.md)
- [Eval: 07_dive_guard.md](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/eval/07_dive_guard_eval.md)
- [Eval: 08_dive_telemetry.md](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/eval/08_dive_telemetry_eval.md)
- [Final coherence evaluation](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/eval/FINAL.md) — Date: 2026-11-09
- [Technical report dive sections — quality eval summary](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/eval/SUMMARY.md) — All five sections now meet the rubric after the above minimal edits.
- [Edit instructions — Dual report polish (from user prompt 2026-11-10)](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/eval/edit_instructions_2026-11-10.md) — Apply to both PDFs (full technical report + security/networking brief). Rebuild after all edits. Do not edit the Cursor plan file.
- [Final PDF Reviewer — 2026-11-10](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/eval/final_pdf_review_2026-11-10.md)
- [Front / architecture / benchmarks eval](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/eval/front_arch_eval.md) — Verdict: PASS
- [Technical report reviewer — 2026-11-10](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/eval/reviewer_pass_2026-11-10.md)
- [Work Credit RAG — Technical Documentation Report](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sections/01_front_matter.md)
- [Executive summary and module overview](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sections/02_executive_and_modules.md) — Work Credit RAG is a Persian-first, self-hosted conversational system that answers credit-reporting questions from a versioned ICS knowledge base. A…
- [System architecture and request-to-response](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sections/03_architecture_and_request.md) — Retrieval, policy, orchestration, and generation are separate processes with stable ports. The high-level figures show the boxes a new engineer needs…
- [Knowledge base](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sections/04_dive_kb.md) — The knowledge base (components/knowledgebase, kb-manager) is the retrieval substrate for Persian credit-scoring questions. It turns source files into…
- [Orchestrator](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sections/05_dive_orch.md) — The orchestrator is the public OpenAI-compatible face of the platform (:8100). It does not embed the corpus and it does not serve Gemma. A compiled L…
- [6. Deep Dive: Server Setup & Model Serving](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sections/06_dive_server.md) — Work Credit RAG runs on the self-hosted H200 lab server (ai-gpu1, 2× H200 NVL, about 281 GiB of VRAM) under /splunk-data/v1/Work_RAG-Server-Setup. Th…
- [Deep Dive: Guardrails & Security](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sections/07_dive_guard.md) — Guardrails (Work_RAG-Guardrails, port :8200) is the mandatory safety boundary between the LangGraph orchestrator and the Gemma inference plane. Every…
- [8. Logging, Telemetry, Documentation & Latency](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sections/08_dive_telemetry.md) — Every successful POST /search/api response includes a stage_ms object written in kb_manager/web/routes/search.py as each leg finishes: BM25 (tantivy…
- [Benchmarks and latency appendix](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sections/09_benchmarks.md) — Observed numbers frame how the stack performs. The headline comparison is the 41-turn multi-agent bench (12 October 2026 → 14 October 2026): finish-r…
- [Appendix](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sections/10_appendix.md) — This appendix indexes libraries by role, lists primary source files, and records the published defaults for the H200 lab server.
- [Security and Networking](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sections/11_security_networking.md) — Work Credit RAG separates safety into three planes that stay distinct in design reviews. Content safety decides whether a Persian turn may be answere…
- [Server Setup, Model Serving, and Scaling](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sections/standalone_server.md) — Work Credit RAG runs on the self-hosted H200 lab server (ai-gpu1, 2× H200 NVL, about 281 GiB of VRAM) under /splunk-data/v1/Work_RAG-Server-Setup. Th…
- [Work Credit RAG — Technical Summary](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sections/standalone_summary.md) — This summary describes the current platform structure and technical behavior. Diagrams match the deep-dive report; captions state what each figure sh…
- [Logging, Telemetry, and Monitoring](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sections/standalone_telemetry.md) — Every successful POST /search/api response includes a stage_ms object written in kb_manager/web/routes/search.py as each leg finishes: BM25 (tantivy…
- [Agent State — GitHub Pages extract (short)](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sources/pages_extracts/agent_state.md) — Sources: agent-state/docs/{index,high-level,technical}.html.
- [Guardrails — GitHub Pages extract](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sources/pages_extracts/guardrails.md) — Sources: components/guardrails/docs/{index,technical,high-level}.html.
- [Knowledgebase GitHub Pages — report extracts](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sources/pages_extracts/kb.md) — Sources: components/knowledgebase/docs/index.html, technical.html, high-level.html.
- [Orchestrator — GitHub Pages extract](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sources/pages_extracts/orchestrator.md) — Sources: components/orchestrator/docs/{index,technical,high-level}.html, SUBSPACE_AMBIGUITY.md.
- [Parent GitHub Pages — report extracts](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sources/pages_extracts/parent.md) — Sources: docs/index.html, docs/technical.html, docs/high-level.html, docs/papers/benchmarks.html (+ titles skim from docs/papers/index.html).
- [Server Setup — GitHub Pages extract](archive/quarantine/20261110/docs/Work_Credit_RAG_Technical_Reports_Bundle/sources/pages_extracts/server_setup.md) — Sources: components/server-setup/docs/{index,technical,high-level}.html, guides/03-services-and-endpoints.md, gemma_endpoints.md, migration/container…
- [Archived Scripts](archive/scripts/README.md) — Utilities moved from scripts/ — not in deploy/vast/start.sh hot path.
- [Windows Launchers (archived)](archive/windows-launchers/README.md) — Linux host uses deploy/vast/start.sh + scripts/run_mvp.sh. Windows artifacts archived:

### `components/`

- [Work Credit RAG — Benchmark Report](components/evaluation/artifacts/bench_report_latest.md) — Artifacts: bench_results_latest.json + ragas_results_latest.json → bench_report_latest.html / .md
- [OpenWebUI RAG Filters & Actions — Agent Testing UI (Phase 2 & 4)](components/openwebui-filters/README.md) — Three OpenWebUI Functions that connect the chat UI to the Work Credit RAG
- [Work RAG Tracing](components/tracing/README.md) — Fallback trace collector and local observation UI for the Work Credit RAG platform.

### `contracts/`

- [Cross-Component Contracts](contracts/README.md) — This directory contains versioned JSON Schema contracts for the MVP integration.

### `datasets/`

- [datasets](datasets/README.md) — Non-runtime assets relocated here during cleanup keep-graph pass.

### `deploy/`

- [Dana compose stack (laptop test ↔ GPU prod)](deploy/compose/README.md) — Self-hosted Gemma/TRT paths are unchanged:
- [Work Credit RAG — Docker deployment (privileged CUDA host)](deploy/docker/README.md) — Full-stack docker compose version of the platform. Mirrors
- [Jenkins CI/CD — Dana / Work Credit RAG](deploy/jenkins/README.md) — Laptop Jenkins (:8085) and the same pipeline on the H200 GPU server.

### `dev/`

- [Tester Credentials — ICS RAG Evaluation](dev/tests/tester-credentials.md) — 1. Open http://127.0.0.1:13000.

### `diagrams/`

- [diagrams](diagrams/README.md) — Non-runtime assets relocated here during cleanup keep-graph pass.

### `docs/`

- [Documentation Index](docs/README.md) — This directory contains project-wide documentation.
- [Benchmark Report — Multi-Agent Conversational RAG Evaluation (2026-10-12)](docs/benchmark-report-2026-10-12.md) — filter_path maps to components/knowledgebase/kb-manager doc_metadata.folder_hierarchy (گزارش اعتباری چک | اشخاص حقیقی/اعتبارسنجی تسهیلات | اشخاص حقوق…
- [Keep-graph summary](docs/cleanup/keep-graph-summary.md) — Generated: 2026-11-10T00:31:05.759190+00:00
- [Stale branch inventory](docs/cleanup/stale-branch-inventory.md) — Generated: 2026-11-10T00:25:47.364914Z
- [Cross-Encoder Reranker Benchmark Results](docs/cross_encoder_benchmark_results.md) — Tested 7 cross-encoder reranker models on the Work Credit RAG KB (v8 pgvector, 6593 chunks, 103 docs) using 20 diverse Persian credit queries.
- [Evaluation — Work Credit RAG Phase 1](docs/evaluation.md) — Historical per-version tables (v5 baseline, v7 IVA 15, v8 HNSW) were moved to archive/migration-history/ and eval/results/. See README.md#evaluation…
- [History — Code Audit 2026-09-27: 142 Errors & Anti-Patterns Found](docs/history/CODE_AUDIT_2026-09-27.md) — 1. components/knowledgebase/kb-manager — 7 Critical + 10 High (path traversal, unauth DB, unbounded disk, silent failures, ilike wildcard DoS, Vector…
- [Comprehensive Million-User Scaling Architecture Plan](docs/plans/million-user-scale-plan.md) — This document serves as the master architectural blueprint for scaling the Knowledge Base Retrieval system to support 1,000,000+ concurrent users.

### `eval/`

- [Wrong Samples Findings — Detailed Analysis (2026-09-02)](eval/FINDINGS.md) — This document details every RAG response that was wrong (blocked, fallback, English, or missing citations) when evaluated against KB ground truth, ho…
- [KB RAG Evaluation — 2026-09-02](eval/README.md) — This directory contains end-to-end evaluation of the RAG agent against KB ground truth on Vast VM.

### `evaluation/`

- [Work Credit RAG — Benchmark Report](evaluation/artifacts/bench_report_latest.md) — Artifacts: bench_results_latest.json + ragas_results_latest.json → bench_report_latest.html / .md

### `plots/`

- [plots](plots/README.md) — Non-runtime assets relocated here during cleanup keep-graph pass.

### `research/`

- [research](research/README.md) — Non-runtime assets relocated here during cleanup keep-graph pass.

<!-- docs-toc:end -->
