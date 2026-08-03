<div align="center">

# 🧠 RAG Agent Platform
### *Production-Ready, Self-Hosted Agentic AI with Native Data Sovereignty*

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2%2B-FF6F00?style=for-the-badge&logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%2B%20%2B%20pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![vLLM](https://img.shields.io/badge/vLLM-Inference-76B900?style=for-the-badge&logo=nvidia&logoColor=white)](https://vllm.ai)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)

[![GitHub Stars](https://img.shields.io/github/stars/your-org/rag-agent-platform?style=social)](https://github.com/your-org/rag-agent-platform/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/your-org/rag-agent-platform?style=social)](https://github.com/your-org/rag-agent-platform/network/members)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=flat-square)](LICENSE)
[![CI Build](https://img.shields.io/github/actions/workflow/status/your-org/rag-agent-platform/ci.yml?branch=main&style=flat-square&logo=github)](https://github.com/your-org/rag-agent-platform/actions)
[![Coverage](https://img.shields.io/badge/Coverage-88%25-brightgreen?style=flat-square&logo=pytest)](https://pytest.org)

<br />

---

## ⚡ Tech Stack & Libraries Matrix

*(GitHub renders this table natively)*

<table>
  <tr>
    <td align="center" width="160">
      <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/python/python-original.svg" width="48" height="48" alt="Python" />
      <br><b>Python 3.11+</b>
      <br><sub>Core Runtime</sub>
    </td>
    <td align="center" width="160">
      <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/fastapi/fastapi-original.svg" width="48" height="48" alt="FastAPI" />
      <br><b>FastAPI</b>
      <br><sub>Async API Layer</sub>
    </td>
    <td align="center" width="160">
      <img src="https://raw.githubusercontent.com/github/explore/80688e429a7d4ef2fca1e82350fe8e3517d3494d/topics/langchain/langchain.png" width="48" height="48" alt="LangGraph" />
      <br><b>LangGraph</b>
      <br><sub>Agent Loop</sub>
    </td>
    <td align="center" width="160">
      <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/postgresql/postgresql-original.svg" width="48" height="48" alt="PostgreSQL" />
      <br><b>pgvector</b>
      <br><sub>Vector Search</sub>
    </td>
  </tr>
  <tr>
    <td align="center" width="160">
      <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/redis/redis-original.svg" width="48" height="48" alt="Redis" />
      <br><b>Redis</b>
      <br><sub>Caching & State</sub>
    </td>
    <td align="center" width="160">
      <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/prometheus/prometheus-original.svg" width="48" height="48" alt="Prometheus" />
      <br><b>Prometheus</b>
      <br><sub>Metrics Stack</sub>
    </td>
    <td align="center" width="160">
      <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/grafana/grafana-original.svg" width="48" height="48" alt="Grafana" />
      <br><b>Grafana</b>
      <br><sub>Observability</sub>
    </td>
    <td align="center" width="160">
      <img src="https://langfuse.com/langfuse-icon.png" width="48" height="48" alt="Langfuse" />
      <br><b>Langfuse</b>
      <br><sub>LLM Tracing</sub>
    </td>
  </tr>
  <tr>
    <td align="center" width="160">
      <img src="https://dvc.org/img/dvc-with-name-base.svg" width="48" height="48" alt="DVC" />
      <br><b>DVC</b>
      <br><sub>Data Versioning</sub>
    </td>
    <td align="center" width="160">
      <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/apache/apache-original.svg" width="48" height="48" alt="MLflow" />
      <br><b>MLflow</b>
      <br><sub>Model Registry</sub>
    </td>
    <td align="center" width="160">
      <img src="https://astral.sh/uv/assets/uv-logo-raw.svg" width="48" height="48" alt="uv" />
      <br><b>uv</b>
      <br><sub>Package Manager</sub>
    </td>
    <td align="center" width="160">
      <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/docker/docker-original.svg" width="48" height="48" alt="Docker" />
      <br><b>Docker</b>
      <br><sub>Orchestration</sub>
    </td>
  </tr>
</table>

</div>

<br />

> [!IMPORTANT]
> **Production-Ready RAG Blueprint:** This repository houses a clean, scalable, and fully deterministic RAG agent baseline built with **LangGraph**, **pgvector**, **FastAPI**, and enterprise observability hooks.

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

---

## 2. 🛠 Tool Architecture Decisions

<details>
<summary><b>🔍 Click to Expand Architecture Decisions</b></summary>

<br />

### MLflow vs. DVC
| Scope | Decision | Purpose |
| :--- | :--- | :--- |
| **MLflow** | **Select** | Tracks **Experiments & Prompts**, parameters, and LLM evaluations. |
| **DVC** | **Select** | Versions **Raw Document Files & Vector Artifacts** natively in Git via remote storage. |

### Langfuse vs. Prometheus + Grafana
| Scope | Decision | Purpose |
| :--- | :--- | :--- |
| **Langfuse** | **Select** | Handles **LLM Tracing**, Token Costing, and RAG Scoring. |
| **Prometheus** | **Select** | Handles **System Metrics**, hardware health, RPS, and Latencies. |

</details>

---

## 3. 🏗️ Design Patterns

- 🏬 **Repository Pattern:** (`app/db/repositories/`) Isolates database access operations from business logic.
- ⚙️ **Service Layer Pattern:** (`app/services/`) Encapsulates application workflows and business rules.
- 🎯 **Strategy Pattern:** (`app/services/retrieval/strategies/`) Enables runtime swapping between vector, keyword, and hybrid search pipelines.
- 🏭 **Factory Pattern:** (`app/services/llm/factory.py`) Instantiates LLM providers dynamically based on context.
- 🔌 **Dependency Injection:** (`app/api/deps.py`) Injects database sessions safely into FastAPI routes.

---

## 4. 📂 Project File Structure

*(Compiled Visual Hierarchy)*

* 📁 **`rag-agent-platform/`**
  * 📄 `.env.example` — *Environment variable templates*
  * 📄 `.pre-commit-config.yaml` — *Code quality verification suite*
  * 📄 `docker-compose.yml` — *Local infrastructure stack*
  * 📄 `pyproject.toml` — *Project metadata & tool configs*
  * 📄 `uv.lock` — *Locked dependency state*
  * 📁 **`data/`** *(Managed via DVC)*
    * 📁 **`raw_documents/`** — *Source document repository*
    * 📁 **`embeddings/`** — *Local embedding index cache*
  * 📁 **`scripts/`**
    * 📄 `seed_data.py` — *Database seed routines*
  * 📁 **`tests/`**
    * 📄 `conftest.py` — *Pytest fixtures and mocks*
    * 📁 **`unit/`** & 📁 **`integration/`**
  * 📁 **`src/`**
    * 📁 **`app/`**
      * 📄 `main.py` — *Application lifecycle & entrypoint*
      * 📁 **`core/`**
        * 📄 `config.py` — *Pydantic Settings*
        * 📄 `logging.py` — *Structlog setup*
      * 📁 **`api/`**
        * 📄 `deps.py` — *FastApi Dependency Injection*
        * 📁 **`v1/`**
          * 📄 `chat.py` & 📄 `conv.py` — *Endpoints*
      * 📁 **`services/`**
        * 📁 **`agent/`**
          * 📄 `graph.py` — *LangGraph compiler & engine*
          * 📄 `state.py` — *Graph state definitions*
        * 📁 **`retrieval/`** — *Search strategies & vector drivers*
        * 📁 **`llm/`** — *LLM provider factory and routers*
      * 📁 **`db/`**
        * 📄 `session.py` — *Async SQLAlchemy engine*
        * 📁 **`models/`** — *ORM Models*
        * 📁 **`repositories/`** — *Data access abstractions*
      * 📁 **`monitoring/`**
        * 📄 `metrics.py` & 📄 `tracer.py` — *Prometheus & Langfuse bindings*

---

## 5. 🗄️ Database Schema

*(GitHub will automatically compile this Mermaid block into a visual Entity-Relationship Diagram)*

```mermaid
erDiagram
    CONVERSATION {
        uuid id PK
        string title
        timestamp created_at
    }

    MESSAGE {
        uuid id PK
        uuid conversation_id FK
        string role
        text content
        jsonb metadata
    }

    DOCUMENT {
        uuid id PK
        string name
        string hash
    }

    CHUNK {
        uuid id PK
        uuid document_id FK
        text content
        vector embedding
    }

    FEEDBACK {
        uuid id PK
        uuid message_id FK
        integer score
    }

    CONVERSATION ||--o{ MESSAGE : "has"
    MESSAGE ||--o{ FEEDBACK : "receives"
    DOCUMENT ||--o{ CHUNK : "contains"
