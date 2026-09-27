# System Architecture — Work Credit RAG Phase 1

> **Scope:** This document describes the production Vast.ai deployment architecture (host venvs, unprivileged). The H200 `server-setup` stack and Docker privileged stack are separate — see respective READMEs.

---

## 1. System Overview

```mermaid
flowchart TB
    subgraph Client["Client Layer"]
        Browser["🌐 Browser"]
        WebUI["💬 Open WebUI :13000"]
    end

    subgraph API["API Gateway"]
        Orch["🎯 Orchestrator :8100\nLangGraph + OpenAI-compatible"]
    end

    subgraph Retrieval["Retrieval Layer"]
        KB["📚 KB Manager :8000\nBM25 + Dense + RRF + Rerank"]
    end

    subgraph Safety["Safety Layer"]
        GR["🛡️ Guardrails :8200\nDeterministic Persian rails\nRisk scoring + Semantic"]
    end

    subgraph Generation["Generation Layer"]
        Gemma["🤖 Gemma :18000\nllama.cpp GGUF UD-Q4_K_XL\n--no-mmproj --jinja"]
    end

    subgraph Observability["Observability"]
        LF2["📊 Langfuse v2 :3001\nPostgres-backed traces"]
        LF1["📝 Fallback Collector :3000\nJSONL /tmp/langfuse_traces.jsonl"]
        Studio["🔍 LangGraph Studio :2024\nAPI for Smith panel"]
        TraceApp["🔎 Tracing App :3000\n/observe, /studio, /api/observe/*"]
    end

    subgraph Data["Data Layer"]
        PG["🐘 PostgreSQL 14 + pgvector :5432\nkb_manager, langfuse DBs"]
        Redis["🔴 Redis (not used in MVP)"]
    end

    Browser --> WebUI
    WebUI -->|POST /v1/chat/completions| Orch
    Orch -->|retrieve| KB
    Orch -->|validate_input| GR
    Orch -->|guarded_generate| GR
    GR -->|chat/completions| Gemma
    Orch -->|response| WebUI
    Orch -.->|traces| LF2
    Orch -.->|fallback traces| LF1
    Orch -.->|Studio API| Studio
    KB -.-> PG
    LF2 -.-> PG
    Studio -.->|panel| Smith["https://smith.langchain.com/studio"]
    Orch -.-> TraceApp
    GR -.-> TraceApp
    KB -.-> TraceApp

    style Orch fill:#e8f5e9,stroke:#2e7d32
    style KB fill:#e3f2fd,stroke:#1565c0
    style GR fill:#fff3e0,stroke:#ef6c00
    style Gemma fill:#fce4ec,stroke:#c2185b
    style LF2 fill:#f3e5f5,stroke:#7b1fa2
    style TraceApp fill:#f1f8e9,stroke:#558b2f
```

---

## 2. Request Flow (MVP)

```mermaid
sequenceDiagram
    participant U as User
    participant W as Open WebUI :13000
    participant O as Orchestrator :8100
    participant K as KB Manager :8000
    participant G as Guardrails :8200
    participant M as Gemma :18000
    participant L as Langfuse v2 :3001

    U->>W: Types Persian question
    W->>O: POST /v1/chat/completions\n{X-Request-ID, messages[]}
    O->>L: trace-create(input, metadata)
    
    O->>O: validate_input node
    O->>G: POST /v1/rails/check {stage:input, text}
    G-->>O: {allowed, categories, reason}
    O->>L: span validate_input
    
    alt Input blocked
        O->>O: format_refusal
        O->>L: span format_response
        O-->>W: {content: refusal, citations: []}
    else Input allowed
        O->>O: retrieve node
        O->>K: POST /search/api {query, top_k:5}
        K-->>O: {final_results: [chunks...]}
        O->>L: span retrieve (chunks with scores)
        
        O->>O: build_context node
        O->>L: span build_context (prompt_messages, metadata)
        
        O->>O: guarded_generate node
        O->>G: POST /v1/chat/completions {messages...}
        G->>G: output rails check
        G->>M: POST /v1/chat/completions\n{chat_template_kwargs:{enable_thinking:false}}
        M-->>G: {choices:[{message:{content}}]}
        G-->>O: {answer, finish_reason}
        O->>L: span guarded_generate
        
        O->>O: format_response node
        O->>L: span format_response (citations)
        
        O->>L: trace-create upsert(output, metadata{citations,latency})
        O-->>W: {choices:[{message,finish_reason}],rag:{citations:N}}
    end
    W-->>U: Renders answer with [1][2] citations
```

---

## 3. Orchestrator Graph (LangGraph)

```mermaid
flowchart TD
    START([START]) --> VI[validate_input]
    
    VI -->|blocked| FR[format_refusal]
    VI -->|allowed| RET[retrieve]
    
    RET --> BC[build_context]
    BC --> GG[guarded_generate]
    GG --> FRMT[format_response]
    FRMT --> END([END])
    FR --> END
    
    subgraph Observability["Per-node tracing"]
        TI[validate_input span]
        TR[retrieve span]
        TB[build_context span]
        TG[guarded_generate span]
        TF[format_response span]
    end
    
    VI -.-> TI
    RET -.-> TR
    BC -.-> TB
    GG -.-> TG
    FRMT -.-> TF
    
    style VI fill:#fff9c4,stroke:#fbc02d
    style RET fill:#bbdefb,stroke:#1976d2
    style BC fill:#c8e6c9,stroke:#388e3c
    style GG fill:#ffe0b2,stroke:#f57c00
    style FRMT fill:#d1c4e9,stroke:#7b1fa2
```

---

## 4. KB Retrieval Pipeline

```mermaid
flowchart LR
    Q[Query] --> PN[Persian Normalization\n+ Char 3-grams]
    PN --> BM25[BM25 Lexical\nkeyword 3× boost]
    PN --> DS[Dense Semantic\nMiniLM-L12 384-dim\ncontextual embeddings]
    BM25 --> RRF[RRF Fusion\nk=60]
    DS --> RRF
    RRF --> CE[Cross-encoder Rerank\nmmarco-mMiniLMv2-L12-H384-v1\ntop-50 pool]
    CE --> TOPK[Final Top-K\nmax_chunks=5]
    
    subgraph Config["Tunable via env"]
        KB[KB_KEYWORD_BOOST=3.0]
        RP[KB_RERANK_POOL=50]
        RM[KB_RERANKER_MODEL]
        RD[KB_RERANKER_DEVICE]
    end
    
    KB -.-> BM25
    RP -.-> CE
    RM -.-> CE
    RD -.-> CE
```

---

## 5. Guardrails Pipeline

```mermaid
flowchart TD
    subgraph Input["Input Rails (stage=input)"]
        I1[Empty/Oversize Check]
        I2[Prompt Injection/Jailbreak\n(Colang + deterministic)]
        I3[HurtLex Persian\n+ 19-lemma allowlist]
        I4[Profanity Persian\nlen>2]
        I5[Out-of-Scope]
        I6[PII Detection\nthreshold 0.90]
        I7[Injection Risk\nthreshold 0.85]
    end
    
    subgraph Gen["Guarded Generation"]
        GC[Chat Completions\nvia Guardrails gateway]
        GC --> M[Gemma :18000\nenable_thinking:false]
    end
    
    subgraph Output["Output Rails (stage=output)"]
        O1[HurtLex + allowlist]
        O2[Profanity len>2]
        O3[Toxicity\nthreshold 0.80\nGhadeer mmBERT F1 0.94]
        O4[Hate Speech\nthreshold 0.80\nGhadeer mmBERT]
        O5[Intent Classification]
        O6[Secret/PII Leak\nthreshold 0.90]
    end
    
    Input --> GC
    GC --> Output
    
    style I3 fill:#fff3e0,stroke:#ef6c00
    style I4 fill:#fff3e0,stroke:#ef6c00
    style O1 fill:#fff3e0,stroke:#ef6c00
    style O3 fill:#e8eaf6,stroke:#3f51b5
    style O4 fill:#e8eaf6,stroke:#3f51b5
```

---

## 6. Data Flow & State

```mermaid
flowchart TB
    subgraph Request["Per-Request State (RAGState)"]
        RID[request_id: str]
        MSG[messages: list[dict]]
        QRY[query: str]
        GD[guardrail_decision: dict]
        CHNKS[retrieved_chunks: list[dict]]
        PROMPT[prompt_messages: list[dict]]
        ANS[answer: str]
        CITE[citations: list[dict]]
        ERR[error: str | None]
        BLK[blocked: bool]
    end
    
    subgraph Persistent["Persistent Stores"]
        PGKB[(PostgreSQL: kb_manager\ndocuments, chunks, versions,\ningestion_jobs, retrieval_logs)]
        PGLF[(PostgreSQL: langfuse\ntraces, observations, scores)]
        SQLITE[(SQLite: guardrails\nchat_sessions, messages,\nmetrics - legacy)]
        JSONL[(JSONL: /tmp/langfuse_traces.jsonl\nfallback traces)]
        WEBUI_DB[(SQLite: /tmp/webui-data/webui.db\nchat sessions)]
    end
    
    Request -.->|ephemeral| PGKB
    Request -.->|traces| PGLF
    Request -.->|fallback| JSONL
    Request -.->|WebUI history| WEBUI_DB
```

---

## 7. Startup Dependency Order

```mermaid
flowchart TD
    PG[(PostgreSQL 14\n+ pgvector)] --> Gemma[Gemma :18000\nllama-server]
    Gemma --> KB[KB Manager :8000]
    KB --> GR[Guardrails :8200]
    GR --> COL[Collector :3000\nfallback]
    COL --> ORCH[Orchestrator :8100]
    ORCH --> WEBUI[Open WebUI :13000]
    PG -.-> LF2[Langfuse v2 :3001]
    
    style PG fill:#fce4ec,stroke:#c2185b
    style Gemma fill:#fce4ec,stroke:#c2185b
    style KB fill:#e3f2fd,stroke:#1565c0
    style GR fill:#fff3e0,stroke:#ef6c00
    style COL fill:#f1f8e9,stroke:#558b2f
    style ORCH fill:#e8f5e9,stroke:#2e7d32
    style WEBUI fill:#e0e0e0,stroke:#616161
    style LF2 fill:#f3e5f5,stroke:#7b1fa2
```

---

## 8. Network Ports (Vast Production)

| Port | Service | Bind | Protocol | Notes |
|------|---------|------|----------|-------|
| 18000 | Gemma (llama-server) | 127.0.0.1 | HTTP | Loopback-only by design |
| 8000 | KB Manager | 0.0.0.0 | HTTP | pgvector backend |
| 8200 | Guardrails | 0.0.0.0 | HTTP | NeMo + deterministic rails |
| 8100 | Orchestrator | 0.0.0.0 | HTTP | LangGraph API |
| 13000 | Open WebUI | 0.0.0.0 | HTTP | Public chat UI |
| 3000 | Tracing App | 0.0.0.0 | HTTP | /observe, /studio, ingestion |
| 3001 | Langfuse v2 | 0.0.0.0 | HTTP | Real trace UI, Postgres-backed |
| 2024 | LangGraph Studio | 0.0.0.0 | HTTP | API only (UI at smith.langchain.com) |
| 5432 | PostgreSQL | 127.0.0.1 | TCP | kb_manager + langfuse DBs |

**SSH Tunnels (Vast.ai):** `ssh -p <ssh_port> root@<ssh_host> -L 13000:localhost:13000 -L 8100:localhost:8100 -L 3000:localhost:3000 -L 3001:localhost:3001 -L 2024:localhost:2024`

---

## 9. Environment Variables (Cross-Component)

| Component | Variable | Default | Production Value |
|-----------|----------|---------|------------------|
| **Gemma** | MODEL | — | `/tmp/hf_clean/.../gemma-4-31B-it-UD-Q4_K_XL.gguf` |
| | CTX_SIZE | 8192 | 8192 (4096 if OOM) |
| **KB** | KB_DB_URL | sqlite+aiosqlite:///./data/kb_test.db | postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/kb_manager |
| | KB_WEB_HOST | 0.0.0.0 | 0.0.0.0 |
| | KB_WEB_PORT | 8000 | 8000 |
| | KB_EMBED_MODEL | paraphrase-multilingual-MiniLM-L12-v2 | same |
| | KB_EMBED_DEVICE | cpu | cuda (on GPU host) |
| | KB_RERANKER_MODEL | cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 | same |
| | KB_KEYWORD_BOOST | 3.0 | 3.0 |
| **Guardrails** | GUARDRAILS_HOST | 0.0.0.0 | 0.0.0.0 |
| | GUARDRAILS_PORT | 8200 | 8200 |
| | UPSTREAM_LLM_BASE_URL | http://127.0.0.1:9000/v1 | http://127.0.0.1:18000/v1 (via LLM_BASE_URL alias) |
| | UPSTREAM_LLM_MODEL | gemma-4-31b | unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL |
| | LLM_BASE_URL | (alias) | http://127.0.0.1:18000/v1 |
| **Orchestrator** | KB_BASE_URL | http://127.0.0.1:8000 | http://127.0.0.1:8000 |
| | GUARDRAILS_BASE_URL | http://127.0.0.1:8200 | http://127.0.0.1:8200 |
| | LANGFUSE_HOST | http://127.0.0.1:3000 | http://127.0.0.1:3001 |
| | LANGFUSE_PUBLIC_KEY | pk-lf-mvp-local | from /tmp/opencode/langfuse.env |
| | LANGFUSE_SECRET_KEY | sk-lf-mvp-local | from /tmp/opencode/langfuse.env |
| | TRACE_ENABLED | true | true |
| **WebUI** | OPENAI_API_BASE_URL | — | http://127.0.0.1:8100/v1 |
| | OPENAI_API_KEY | — | sk-local-dev |
| | WEBUI_AUTH | false | false |
| | DATA_DIR | — | /tmp/webui-data |

---

## 10. Component Repository Map

```
Work_Credit-RAG_Phase1/                 ← Parent (umbrella)
├── components/
│   ├── server-setup/                   ← Work_RAG-Server-Setup (git submodule, main)
│   │   └── H200 provisioning, model lifecycle, infra
│   ├── knowledgebase/                  ← Work_RAG-KB (git submodule, master)
│   │   ├── kb-manager/                 ← KB ingestion, retrieval, reranking
│   │   └── kb-source/                  ← Source XLSX files (submodule)
│   ├── guardrails/                     ← Work_RAG-Guardrails (git submodule, main)
│   │   └── Policy, guarded Gemma, risk/semantic
│   ├── orchestrator/                   ← Work_RAG-Orchestrator (git submodule, main)
│   │   └── LangGraph, adapters, public API
│   └── tracing/                        ← Parent-owned (not submodule)
│       └── Fallback collector + Observe UI
├── deploy/
│   ├── vast/                           ← Vast.ai host-venv startup scripts
│   └── docker/                         ← Privileged Docker Compose stack
├── contracts/                          ← JSON Schema contracts
├── eval/                               ← Benchmark scripts + results
└── docs/                               ← Runbook, migration log, MVP plan
```

---

## 11. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Stateless orchestrator** | WebUI sends full history; no PostgreSQL checkpointer needed for MVP |
| **Gemma external on :18000** | Loopback-only; single model process shared; avoids VRAM duplication |
| **Host venvs (no Docker)** | Vast instance unprivileged (`unshare` denied); `compose.mvp.yml` for privileged only |
| **Langfuse v2 from source** | v3 requires ClickHouse; v2 Postgres-only fits constrained host |
| **HurtLex allowlist (19 lemmas)** | Credit-domain false positives (حذف, ضعیف, پلیس, etc.) — evidence-based |
| **Persian-only system prompt** | Prevents English fallback (`The provided context...`) |
| **MAX_CHUNKS=5, MAX_CONTEXT_CHARS=6000** | Balanced for v7 KB (2077 chunks); v8 (6593) may need tuning |
| **RRF k=60 + cross-encoder pool 50** | Retrieval-bound pipeline; reranker is highest-leverage model change |
| **chat_template_kwargs:enable_thinking:false** | Eliminates `<unused*>` token leaks in Gemma 4 |
| **Single worker Studio (:2024)** | `active=1, max=1` — concurrent runs queue |

---

## 12. Failure Modes & Mitigations

```mermaid
flowchart TD
    subgraph Failures["Observed Failure Modes"]
        F1[KB :8000 wedged\n(hung accept queue)]
        F2[Gemma OOM\n(VRAM 22.7/24 GB at ctx 8192)]
        F3[Guardrails false positives\n(HurtLex credit terms)]
        F4[Langfuse SDK v4 incompatible\n(v2 envelope: id+timestamp, no trace-update)]
        F5[asyncpg loop bug\n(thread-hop breaks pool)]
        F6[Phantom HF dentries\n/workspace/.hf_home empty]
        F7[Studio run without request_id\nfails validation]
    end
    
    subgraph Mitigations["Mitigations"]
        M1[Restart KB: fuser -k 8000/tcp + relaunch]
        M2[Reduce CTX_SIZE to 4096]
        M3[Allowlist 19 lemmas + profanity len>2]
        M4[Direct-HTTP in tracing.py authoritative]
        M5[await search_knowledge_base directly]
        M6[Set BOTH HF_HOME and HF_HUB_CACHE=/tmp/hf_clean]
        M7[Enforce request_id in Studio inputs]
    end
    
    F1 --> M1
    F2 --> M2
    F3 --> M3
    F4 --> M4
    F5 --> M5
    F6 --> M6
    F7 --> M7
```