
# 🧠 RAG Agent Platform

### *Production-Ready, Self-Hosted Agentic AI with Native Data Sovereignty*

![License](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2%2B-1C3C3C?logo=langchain&logoColor=white)
![Status](https://img.shields.io/badge/Status-Planning_%26_Blueprint-yellow)

---

## ⚡ Tech Stack & Libraries Matrix

| Layer | Technology | Badge |
| :--- | :--- | :--- |
| **Runtime** | Python 3.11+ | ![Python](https://raw.githubusercontent.com/devicons/devicon/master/icons/python/python-original.svg) |
| **API Layer** | FastAPI | ![FastAPI](https://raw.githubusercontent.com/devicons/devicon/master/icons/fastapi/fastapi-original.svg) |
| **Agent Loop** | LangGraph | ![LangGraph](https://raw.githubusercontent.com/github/explore/80688e429a7d4ef2fca1e82350fe8e3517d3494d/topics/langchain/langchain.png) |
| **Vector DB** | PostgreSQL + pgvector | ![PostgreSQL](https://raw.githubusercontent.com/devicons/devicon/master/icons/postgresql/postgresql-original.svg) |
| **Caching** | Redis | ![Redis](https://raw.githubusercontent.com/devicons/devicon/master/icons/redis/redis-original.svg) |
| **LLM Serving** | vLLM / Ollama | ![vLLM](https://img.shields.io/badge/vLLM-0.6%2B-00C7B7) |
| **Metrics** | Prometheus + Grafana | ![Prometheus](https://raw.githubusercontent.com/devicons/devicon/master/icons/prometheus/prometheus-original.svg) |
| **LLM Tracing** | Langfuse | ![Langfuse](https://langfuse.com/langfuse-icon.png) |
| **Data Versioning** | DVC | ![DVC](https://dvc.org/img/dvc-with-name-base.svg) |
| **Model Registry** | MLflow | ![MLflow](https://raw.githubusercontent.com/devicons/devicon/master/icons/apache/apache-original.svg) |
| **Package Manager** | uv (Astral) | ![uv](https://astral.sh/assets/uv-logo-raw.svg) |
| **Orchestration** | Docker + K8s | ![Docker](https://raw.githubusercontent.com/devicons/devicon/master/icons/docker/docker-original.svg) |

---

> [!IMPORTANT]
> **Production-Ready RAG Blueprint:** This repository houses a clean, scalable, and fully deterministic RAG agent baseline built with **LangGraph**, **pgvector**, **FastAPI**, and enterprise observability hooks.

---

## 📸 System In Action

```text
+-----------------------------------------------------------------------+
| [User Query] -> (LangGraph Agent) -> [Hybrid Search (Vector + BM25)]  |
|                                                                       |
| [Streamed Response] <- (vLLM Engine) <- [Reranked Context Blocks]     |
+-----------------------------------------------------------------------+
```

---

## 📌 Table of Contents

- [📖 1. Introduction](#1-introduction)
- [🛠 2. Tool Architecture Decisions](#2-tool-architecture-decisions)
- [🏗️ 3. Design Patterns](#3-design-patterns)
- [📂 4. Project File Structure](#4-project-file-structure)
- [🗄️ 5. Database Schema](#5-database-schema)
- [🔄 6. Data Flow & System Diagrams](#6-data-flow--system-diagrams)
- [🧪 7. Technology Stack Reference](#7-technology-stack-reference)
- [🚀 8. Step-by-Step Setup & CI/CD Workflow](#8-step-by-step-setup--cicd-workflow)
- [🗺️ 9. Project Roadmap](#9-project-roadmap)
- [👤 10. Author & Maintainer](#10-author--maintainer)

---

## 1. 📖 Introduction

This repository is a **production-ready, self-hosted Retrieval-Augmented Generation (RAG) Agent platform**. It bridges the gap between simple semantic search and production autonomy by using a **LangGraph-driven agentic feedback loop** with hybrid search, streaming dynamic memory, and end-to-end data control.

### Key Highlights

- **Deterministic Deployment**: Locked dependencies via `uv` and enforced pre-commit validation.
- **Deep Observability**: Out-of-the-box infrastructure metrics with Prometheus/Grafana, paired with LLM call tracing via Langfuse.
- **Modularity First**: Loose coupling via repository, strategy, and factory patterns for easy component swapping.

---

## 2. 🛠 Tool Architecture Decisions

<details>
<summary><b>🔍 Expand Tool Comparisons & Decisions</b></summary>

### Model Versioning: MLflow vs. DVC

| Aspect | **MLflow** | **DVC** |
| :--- | :--- | :--- |
| **Scope** | Full ML Lifecycle (Tracking, Registry, Serving) | Data Version Control + Pipeline Orchestration |
| **Strengths** | Tracks LLM prompts, parameters, metrics. Native LangChain/LangGraph integration. | Versions massive datasets (PDFs, embeddings) without storing blobs in Git. |
| **Weaknesses** | Heavy for simple model storage. Does not handle large data files efficiently. | No built-in experiment tracking. |
| **Decision** | **Use Both.** MLflow handles **Experiment Tracking** (prompts, token costs) and **Model Registry**. DVC handles **Data Versioning** (raw documents, chunked text, and embedding indices). |

### Observability: Langfuse vs. Prometheus vs. Grafana

| Aspect | **Langfuse** | **Prometheus + Grafana** |
| :--- | :--- | :--- |
| **Scope** | LLM-specific Observability (Traces, Costs, Scoring) | System Infrastructure Metrics (CPU, Memory, Request Latency) |
| **Strengths** | Tracks prompt templates, generation latency, token usage per user. | Industry standard for collecting time-series metrics and visualizing dashboards. |
| **Decision** | **Use Both.** Langfuse handles the **Tracing** (What did the LLM see?). Prometheus+Grafana handles the **System** (How much load can the API take?) for SLOs. |

### Data Migration: Alembic vs. DVC

| Aspect | **Alembic** | **DVC** |
| :--- | :--- | :--- |
| **Scope** | Relational Database Schema Migrations (SQLAlchemy). | Versioning large binary/text files outside Git. |
| **Decision** | **Use Both.** Alembic tracks **Table Structures**. DVC tracks **Data Files**. They serve entirely different purposes.
</details>

---

## 3. 🏗️ Design Patterns

- 🏬 **Repository Pattern** (`app/db/repositories/`): Isolates database access operations from business logic.
- ⚙️ **Service Layer Pattern** (`app/services/`): Encapsulates application workflows and business rules.
- 🎯 **Strategy Pattern** (`app/services/retrieval/strategies/`): Enables runtime swapping between vector, keyword, and hybrid search pipelines.
- 🏭 **Factory Pattern** (`app/services/llm/factory.py`): Instantiates and configures LLM providers dynamically based on context.
- 🔌 **Dependency Injection** (`app/api/deps.py`): Injects database sessions and service layers cleanly into FastAPI routes.

---

## 4. 📂 Project File Structure

```text
.
├── .env.example                 # Template for required env vars
├── .gitignore                   # Standard Python + OS + IDE
├── .pre-commit-config.yaml      # Ruff, mypy, trailing-whitespace checks
├── README.md                    # This file
├── Makefile                     # Shortcuts: dev, docker-up, test, migrate
├── pyproject.toml               # Build system, dependencies, ruff/mypy configs
├── uv.lock                      # Exact dependency versions
├── docker-compose.yml           # Postgres+pgvector, Redis, (optional) Grafana
├── data/                        # Managed by DVC (gitignored)
│   ├── raw_documents/
│   └── embeddings/
├── models/                      # Managed by MLflow (gitignored)
│   └── model_registry/
├── scripts/                     # One-off scripts
│   ├── seed_data.py
│   └── run_ragas_eval.py
├── src/                         # Main application source
│   └── app/
│       ├── __init__.py
│       ├── main.py              # FastAPI app creation & lifespan
│       ├── core/                # Cross-cutting concerns
│       │   ├── config.py        # Pydantic Settings
│       │   ├── logging.py       # Structlog configuration
│       │   └── exceptions.py
│       ├── api/                 # HTTP Layer
│       │   ├── deps.py          # Depends (DB session, current user)
│       │   ├── router.py        # Routes aggregator
│       │   └── v1/              # Version 1 endpoints
│       │       ├── chat.py      # POST /chat/stream
│       │       └── conv.py      # CRUD for conversations
│       ├── services/            # Business Logic Layer
│       │   ├── agent/           # LangGraph integration
│       │   │   ├── graph.py
│       │   │   └── state.py
│       │   ├── retrieval/       # RAG logic
│       │   │   ├── vector_store.py
│       │   │   └── strategies/  # Strategy Pattern
│       │   └── llm/             # LLM clients
│       │       ├── router.py
│       │       └── factory.py
│       ├── db/                  # Data Access Layer
│       │   ├── session.py
│       │   ├── models/          # SQLAlchemy ORM models
│       │   │   ├── conversation.py
│       │   │   └── message.py
│       │   └── repositories/    # Repository Pattern
│       │       └── conversation_repo.py
│       ├── schemas/             # Pydantic v2 DTOs
│       │   ├── chat.py
│       │   └── conversation.py
│       └── monitoring/          # Prometheus/Langfuse instrumentation
│           ├── metrics.py
│           └── tracer.py
├── tests/                       # Testing
│   ├── conftest.py
│   ├── unit/
│   └── integration/
└── frontend/                    # Minimal Streamlit UI
    ├── app.py
    └── requirements.txt
```

---

## 5. 🗄️ Database Schema

Below is the entity-relationship model for conversation history, documents, chunks, and user feedback.

```mermaid
erDiagram
    conversations {
        uuid id PK
        string title "Auto-generated title"
        timestamp created_at
        timestamp updated_at
    }

    messages {
        uuid id PK
        uuid conversation_id FK "CASCADE"
        string role "user, assistant, system"
        text content
        jsonb metadata "Tokens, citations"
        timestamp created_at
    }

    documents {
        uuid id PK
        string name
        string source_path
        string hash "SHA-256 Content Hash"
        timestamp ingested_at
    }

    chunks {
        uuid id PK
        uuid document_id FK "CASCADE"
        integer chunk_index
        text content
        vector embedding "(1536) pgvector"
        jsonb metadata
    }

    feedback {
        uuid id PK
        uuid message_id FK "CASCADE"
        integer score "1 to 5, or -1/1"
        text comment
        timestamp created_at
    }

    conversations ||--o{ messages : "has"
    messages ||--o{ feedback : "receives"
    documents ||--o{ chunks : "contains"
```

---

## 6. 🔄 Data Flow & System Diagrams

### 6.1 High-Level Architecture

```mermaid
flowchart LR
    subgraph Presentation["Client Layer"]
        UI["Streamlit / React UI"]
    end

    subgraph Backend["FastAPI Backend Container"]
        direction TB
        API["FastAPI Handlers"]
        SVC["Service Layer"]
        AG["LangGraph Agent"]
        RET["Retrieval Engine"]
        VDB[("pgvector Store")]
    end

    subgraph Observability["Telemetry Stack"]
        PROM["Prometheus"]
        GRAFANA["Grafana"]
        LANGFUSE["Langfuse Tracing"]
    end

    UI --> API
    API --> SVC
    SVC --> AG
    AG --> RET
    RET --> VDB
    
    SVC -.->|System Metrics| PROM
    SVC -.->|Execution Traces| LANGFUSE
    PROM -.-> GRAFANA
```

### 6.2 Agent Sequence & Request Lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant Client as Client Application
    participant API as FastAPI Router
    participant SVC as Agent Service
    participant LG as LangGraph Engine
    participant VDB as pgvector Store
    participant LLM as Inference API / vLLM

    Client->>API: POST /api/v1/chat/stream
    API->>SVC: stream_chat(payload)
    SVC->>LG: execute_graph(state)
    
    loop Agentic Retrieval Iteration
        LG->>VDB: hybrid_search(query, top_k)
        VDB-->>LG: return relevant chunks
        LG->>LLM: evaluate context & generate
        LLM-->>LG: return token stream / tool calls
    end
    
    LG-->>SVC: stream response tokens
    SVC-->>API: yield NDJSON frame
    API-->>Client: stream response chunk to UI
```

```mermaid

sequenceDiagram
    participant User
    participant FE as Frontend
    participant API as FastAPI
    participant Agent as LangGraph
    participant Retriever as Retrieval
    participant VS as Vector Store
    participant LLM as LLM Router
    participant DB as PostgreSQL

    User->>FE: Send message
    FE->>API: POST chat stream
    API->>Agent: Process request
    
    alt Need Context
        Agent->>Retriever: Query documents
        Retriever->>VS: Similarity search
        VS-->>Retriever: Relevant chunks
        Retriever-->>Agent: Context
    end
    
    Agent->>LLM: Generate response
    LLM-->>Agent: LLM output
    
    Agent->>DB: Save conversation
    DB-->>Agent: Confirmation
    
    Agent-->>API: Stream response
    API-->>FE: Stream tokens
    FE-->>User: Display response
    
```

### 6.3 High level state flow

```mermaid
flowchart LR
    User[User] --> FE[Streamlit Frontend]
    FE --> API[FastAPI /v1/chat]
    API --> Agent[LangGraph Agent]
    Agent --> Retriever[Retrieval Service]
    Retriever --> VS[(Vector Store\npgvector)]
    Retriever --> LLM[LLM Router]
    LLM --> LLMProvider[LLM Provider\n(e.g., OpenAI)]
    Agent --> ConvRepo[Conversation Repository]
    ConvRepo --> DB[(PostgreSQL)]
    API --> ConvRepo
    API --> Schemas[Pydantic Schemas]
    FE --> Metrics[Prometheus]
    API --> Metrics
    Agent -.-> Tracer[Langfuse Tracer]
```
### 6.4 High level project directory structure 

```mermaid
flowchart TD
    Root[Project Root] --> Env[env.example]
    Root --> Gitignore[gitignore]
    Root --> Precommit[pre-commit-config.yaml]
    Root --> Readme[README.md]
    Root --> Makefile[Makefile]
    Root --> Pyproject[pyproject.toml]
    Root --> Uvlock[uv.lock]
    Root --> Docker[docker-compose.yml]
    
    Root --> Data[data]
    Data --> Raw[raw_documents]
    Data --> Embeddings[embeddings]
    
    Root --> Models[models]
    Models --> Registry[model_registry]
    
    Root --> Scripts[scripts]
    Scripts --> Seed[seed_data.py]
    Scripts --> Eval[run_ragas_eval.py]
    
    Root --> Src[src]
    Src --> App[app]
    App --> Main[main.py]
    
    App --> Core[core]
    Core --> Config[config.py]
    Core --> Logging[logging.py]
    Core --> Exceptions[exceptions.py]
    
    App --> Api[api]
    Api --> Deps[deps.py]
    Api --> ApiRouter[router.py]
    Api --> V1[v1]
    V1 --> Chat[chat.py]
    V1 --> Conv[conv.py]
    
    App --> Services[services]
    Services --> Agent[agent]
    Agent --> Graph[graph.py]
    Agent --> State[state.py]
    Services --> Retrieval[retrieval]
    Retrieval --> VectorStore[vector_store.py]
    Retrieval --> Strategies[strategies]
    Services --> Llm[llm]
    Llm --> LlmRouter[router.py]
    Llm --> Factory[factory.py]
    
    App --> Db[db]
    Db --> Session[session.py]
    Db --> DbModels[models]
    DbModels --> Conversation[conversation.py]
    DbModels --> Message[message.py]
    Db --> Repositories[repositories]
    Repositories --> ConvRepo[conversation_repo.py]
    
    App --> Schemas[schemas]
    Schemas --> ChatSchema[chat.py]
    Schemas --> ConvSchema[conversation.py]
    
    App --> Monitoring[monitoring]
    Monitoring --> Metrics[metrics.py]
    Monitoring --> Tracer[tracer.py]
    
    Root --> Tests[tests]
    Tests --> Conftest[conftest.py]
    Tests --> Unit[unit]
    Tests --> Integration[integration]
    
    Root --> Frontend[frontend]
    Frontend --> AppFront[app.py]
    Frontend --> ReqFront[requirements.txt]
```


---

## 7. 🧪 Technology Stack Reference

> [!TIP]
> The platform is built using modern Python practices, leveraging `uv` for fast dependency management and full async compatibility.

- **Application Server**: FastAPI 0.115+
- **Orchestration**: LangGraph 0.2+ & LangChain
- **Storage & Vector Engine**: PostgreSQL 16+ with `pgvector` extension
- **Caching**: Redis 7+
- **Model Inference**: vLLM / Ollama / OpenAI Async Client
- **Observability**: Prometheus, Grafana, & Langfuse
- **Package Management**: `uv` by Astral

---

## 8. 🚀 Step-by-Step Setup & CI/CD Workflow

### Quick Start (Local Environment)

1. **Clone the Repository**
   ```bash
   git clone https://github.com/your-org/rag-agent-platform.git
   cd rag-agent-platform
   ```

2. **Initialize Python Environment with `uv`**
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv sync --extra dev --extra monitoring
   ```

3. **Configure Pre-Commit Hooks**
   ```bash
   pre-commit install
   ```

4. **Launch Local Services Stack**
   ```bash
   make docker-up
   ```

5. **Apply Database Schema Migrations**
   ```bash
   alembic upgrade head
   ```

6. **Start Application Server**
   ```bash
   make dev
   ```
   > Server running at `http://localhost:8000`. OpenAPI docs available at `http://localhost:8000/docs`.

---

## 9. 🗺️ Project Roadmap

```mermaid
gantt
    title RAG Agent Platform Development Plan
    dateFormat  YYYY-MM-DD
    section Phase 0
    System Blueprint & Foundation      :done, p0, 2026-07-01, 2026-07-15
    section Phase 1 (Current)
    Core LangGraph + pgvector + FastAPI :active, p1, 2026-07-16, 2026-08-15
    section Phase 2
    GraphRAG (Neo4j) + Hybrid Reranking :p2, 2026-08-16, 2028-09-30
    section Phase 3
    Auto-scaling KEDA + MCP Protocol    :p3, 2026-10-01, 2029-11-15
```

---

## 10. 👤 Author & Maintainer

<img src="https://github.com/github.png" width="100;" alt="Author Avatar"/>

**Project Author**  
👋 Hi, I'm the Lead Architect behind this RAG Platform!  
Building high-performance, agentic, enterprise-grade AI systems with clean code, data sovereignty, and robust telemetry.

<p>
    <a href="https://github.com/your-username"><img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white" alt="GitHub" /></a>
    <a href="https://linkedin.com/in/your-profile"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white" alt="LinkedIn" /></a>
    <a href="https://twitter.com/your-handle"><img src="https://img.shields.io/badge/X-000000?style=for-the-badge&logo=x&logoColor=white" alt="X / Twitter" /></a>
    <a href="mailto:you@domain.com"><img src="https://img.shields.io/badge/Email-D14836?style=for-the-badge&logo=gmail&logoColor=white" alt="Email" /></a>
</p>

### ⭐ Don't forget to star this repository if you find it helpful!

[Back to top](#-rag-agent-platform)
```
