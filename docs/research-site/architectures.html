---
layout: default
title: "Architectures - Multi-Turn RAG Research"
description: "Mermaid diagrams of paper architectures: SPLIT-RAG, PC-RAG, RAC, ICR, CPP, CALMem, H-RAG, 5ting, GUIR, DUTIR, CoRAG, IM-RAG"
---

<div class="page-header">
  <h1>Architectures</h1>
  <p class="lead">Mermaid diagrams of paper architectures: SPLIT-RAG, PC-RAG, RAC, ICR, CPP, CALMem, H-RAG, 5ting, GUIR, DUTIR, CoRAG, IM-RAG</p>
</div>

## System Architectures

### Our Current Architecture (Post T1-T7 Fixes)

```mermaid
flowchart TD
    subgraph Client["Client Layer"]
        Browser["🌐 Browser"]
        WebUI["💬 Open WebUI :13000\nICS Helper (Arena OFF)\nFilters: rag_trace_capture\nActions: ⭐ rate / 🐛 report / 📄 view / ✅ truth"]
    end

    subgraph Orchestration["Orchestration — :8100"]
        Orch["🎯 Orchestrator\nLangGraph (MemorySaver)\nOpenAI-compatible /v1/chat/completions\nX-Request-ID sticky thread"]
        Classify["classify\n(greeting/spec/question)"]
        InferSpec["infer_specification\n+ LLM subspace judge"]
        Clarify["generate_clarification"]
    end

    subgraph Retrieval["Retrieval — :8000"]
        KB["📚 KB Manager\nBM25(tantivy) + Dense MiniLM-384\n+ RRF k=60 + CE BGE-v2-m3\npgvector HNSW (1123 chunks)"]
        Filter["filter_path\nfolder_hierarchy tag"]
        Suppl["supplement\nentity_lists (MiniLM cos>0.4)\n+ injected_entities (>0.6)"]
    end

    subgraph Safety["Safety — :8200"]
        GR["🛡️ Guardrails\nPOST /v1/rails/check (input)\nPOST /v1/chat/completions (guarded_generate)\nRisk + semantic + HurtLex"]
    end

    subgraph Generation["Generation"]
        Gemma["🤖 Gemma :18000\nllama-server UD-Q4_K_XL\n--no-mmproj --jinja\ntemp 0.2 ctx 8192"]
        Manager["🧩 LLM Manager :9000\n(H200: 5× Gemma 8080-84 + embed 8001-8003)"]
        Embed["🔢 Embed :8001-8003\nE5-small/BGE-m3/MiniLM"]
    end

    subgraph Observability["Observability"]
        Collector["📝 Collector :3000\nPOST /api/observability/*\nSQLite observability.db"]
        Dashboard["📊 Dashboard :3000/dashboard/observability\n8-stage chunk cards"]
        LF2["📊 Langfuse v2 :3001\nPostgres + ClickHouse"]
        Studio["🔍 Studio :2024\nLangGraph API"]
        TraceApp["🔎 /observe + /studio"]
    end

    Browser --> WebUI
    WebUI -- "OPENAI_API_BASE_URL=8100/v1\n+ X-Request-ID" --> Orch
    Orch --> Classify
    Classify --> InferSpec
    InferSpec -- "should_clarify?" --> Clarify
    Clarify -- "clarify finish" --> WebUI
    InferSpec -- "allowed" --> KB
    KB --> Filter
    KB --> Suppl
    Suppl -- "MAX_CHUNKS=20\nMAX_CONTEXT=9000" --> Orch
    Orch -- "guarded_generate" --> GR
    GR --> Gemma
    Gemma -.-> Manager
    Embed -.-> KB
    Orch -.-> Collector
    Collector --> Dashboard
    Orch -.-> LF2
    Orch -.-> Studio
    Collector --> TraceApp
```

---

### SPLIT-RAG Architecture

```mermaid
flowchart TD
    subgraph Training["Training Phase"]
        TrainQ[Training Questions] --> QPP[Question Preprocessing]
        QPP --> QTC[Question-Type Clustering]
        QTC --> KGPart[KG Partitioning]
        KGPart --> AgentAssign[Agent-Subgraph Assignment]
    end

    subgraph Inference["Inference Phase"]
        Query[User Query] --> Planner[Query-Specific Planner]
        Planner --> AgentSelect[Relevant Agent Selection]
        AgentSelect --> ParallelRet[Parallel Subgraph Retrieval]
        ParallelRet --> EvidenceFilter[Compatibility Filtering]
        EvidenceFilter --> HeadAgent[Head Agent Generation]
    end

    KG[(Knowledge Graph)] --> KGPart
    KGPart --> Agent1[Agent 1: Subgraph 1]
    KGPart --> Agent2[Agent 2: Subgraph 2]
    KGPart --> AgentN[Agent N: Subgraph N]
    Agent1 --> ParallelRet
    Agent2 --> ParallelRet
    AgentN --> ParallelRet
    ParallelRet --> EvidenceFilter
    EvidenceFilter --> HeadAgent
```

---

### PC-RAG Architecture

```mermaid
flowchart TD
    Query[User Query] --> Decompose[Query Decomposition]
    Decompose --> SubTask1[Sub-task 1: HR]
    Decompose --> SubTask2[Sub-task 2: Legal]
    Decompose --> SubTask3[Sub-task 3: Compliance]
    
    SubTask1 --> Ret1[Retrieval: HR Partition]
    SubTask2 --> Ret2[Retrieval: Legal Partition]
    SubTask3 --> Ret3[Retrieval: Compliance Partition]
    
    Ret1 --> Gen1[Generation 1]
    Ret2 --> Gen2[Generation 2]
    Ret3 --> Gen3[Generation 3]
    
    Gen1 --> Synth[Synthesis]
    Gen2 --> Synth
    Gen3 --> Synth
    Synth --> Answer[Final Answer]
    
    classDef domain fill:#dbeafe,stroke:#1e40af;
    class Ret1,Ret2,Ret3,Gen1,Gen2,Gen3 domain;
```

---

### RAC Architecture

```mermaid
flowchart TD
    Query[Ambiguous Query] --> Retrieve[Retrieve Top-K Passages]
    Retrieve --> LLM[LLM Generates Clarification\nGrounded in Retrieved Facets]
    LLM --> Clarify[Clarifying Question]
    Clarify --> User[User Response]
    User --> Rewrite[Rewrite Query with Clarification]
    Rewrite --> Retrieve2[Retrieve with Rewritten Query]
    Retrieve2 --> Generate[Generate Answer]
    
    style Retrieve fill:#dcfce7,stroke:#166534
    style LLM fill:#fef3e0,stroke:#f57f17
    style Clarify fill:#fef3e0,stroke:#f57f17
```

---

### ICR Architecture

```mermaid
flowchart TD
    Query[Initial Query] --> Loop[Iteration Loop]
    Loop --> Clarify[Generate Clarification c_i]
    Clarify --> Rewrite[Rewrite Query r_i]
    Rewrite --> Retrieve[Retrieve with r_i]
    Retrieve --> Confident{Confident?}
    Confident -->|No| Loop
    Confident -->|Yes| Generate[Generate Final Answer]
    
    style Loop fill:#fef3e0,stroke:#f57f17
    style Generate fill:#dcfce7,stroke:#166534
```

---

### CPP Architecture

```mermaid
flowchart TD
    Turns[Raw Turns] --> Seg[Segmentation\nCosine δ threshold]
    Seg --> Segments[Segments: 3-10 turns]
    Segments --> DualIdx[Dual Indexing\nLexical + Semantic]
    DualIdx --> Budget[Budgeted Retrieval\nHard storage budget]
    Budget --> Highlight[Evidence Highlighting\nTop sentence per segment]
    Highlight --> Gen[Generation]
    
    classDef cpp fill:#e0e7ff,stroke:#3730a3;
    class Seg,Segments,DualIdx,Budget,Highlight cpp;
```

---

### CALMem Architecture

```mermaid
flowchart TD
    subgraph CALMem["CALMem Dual Memory"]
        Episodic[Episodic Memory\nSliding window vector embeddings\nIntra-session retrieval]
        Semantic[Semantic Memory\nAgent-writable structured facts\nCross-session persistence]
        MOIM[MOIM Injector\nToken-budget adaptive\nAuto-retrieves context]
    end
    
    Session[Session] --> Hook[Hook in persistence path]
    Hook --> Episodic
    Hook --> Semantic
    Episodic --> MOIM
    Semantic --> MOIM
    MOIM --> SystemPrompt[Prepend to System Prompt]
    SystemPrompt --> LLM[LLM Generation]
```

---

### H-RAG Architecture

```mermaid
flowchart TD
    Query[Query] --> Parent[Parent-Level Retrieval\nSummary chunks]
    Parent --> Child[Child-Level Retrieval\nDetail chunks]
    Child --> Reconstruct[Parent-Level Context Reconstruction]
    Reconstruct --> Rerank[Cross-Encoder Rerank]
    Rerank --> Generate[Generation]
    
    classDef hrag fill:#fef3e0,stroke:#f57f17;
    class Parent,Child,Reconstruct,Rerank hrag;
```

---

### 5ting Architecture

```mermaid
flowchart TD
    Query[Query] --> Rewrite[Query Rewrite\nwith History]
    Rewrite --> Dense[Dense Retrieval\nFAISS + BGE-M3]
    Rewrite --> Sparse[Sparse Retrieval\nBM25]
    Dense --> RRF[RRF Fusion]
    Sparse --> RRF
    RRF --> Rerank[LLM Reranking\nListwise]
    Rerank --> Generate[Evidence-Constrained\nGeneration]
    
    classDef sting fill:#fef3e0,stroke:#f57f17;
    class Dense,Sparse,RRF,Rerank,Generate sting;
```

---

### GUIR Architecture

```mermaid
flowchart TD
    Query[Query] --> LT[LT: Last Turn\nRaw input]
    Query --> RW[RW: Rewritten\nLLM + context]
    Query --> QS[QS: Query-Specific\nCorpus-adapted]
    
    LT --> Ret1[Retrieval]
    RW --> Ret2[Retrieval]
    QS --> Ret3[Retrieval]
    
    Ret1 --> RRF[RRF Fusion]
    Ret2 --> RRF
    QS --> Ret3
    Ret3 --> RRF
    RRF --> Rerank[Cross-Encoder Rerank]
    Rerank --> Generate[Generation]
    
    classDef guir fill:#e0e7ff,stroke:#3730a3;
    class LT,RW,QS,Ret1,Ret2,Ret3,RRF guir;
```

---

### DUTIR Architecture

```mermaid
flowchart TD
    Query[Query] --> Rewrite[LLM Rewrite\nGPT-5.2]
    Rewrite --> Hybrid[Hybrid Retrieval\nBGE-M3 + BM25 → RRF]
    Hybrid --> Gate[Confidence Gate\nAnswerability check]
    Gate -->|Low| Refuse[Refuse: IDK]
    Gate -->|High| Generate[Faithful Generation]
    
    classDef dutir fill:#fef3e0,stroke:#f57f17;
    class Rewrite,Hybrid,Gate,Refuse,Generate dutir;
```

---

### CoRAG Architecture

```mermaid
flowchart TD
    Query[Query] --> Reasoner[Reasoner: Questioner]
    Reasoner --> Retrieve[Retrieve]
    Retrieve --> Refine[Refiner]
    Refine --> Reasoner2[Reasoner: Answerer]
    Reasoner2 -->|More needed| Reasoner
    Reasoner2 -->|Enough| Answer[Final Answer]
    
    classDef corag fill:#e0e7ff,stroke:#3730a3;
    class Reasoner,Retrieve,Refine,Reasoner2 corag;
```

---

### IM-RAG Architecture

```mermaid
flowchart TD
    subgraph IM["IM-RAG"]
        Reasoner[Reasoner\nQuestioner / Answerer]
        Retriever[Retriever]
        Refiner[Refiner]
        Progress[Progress Tracker]
    end
    
    Query[Query] --> Reasoner
    Reasoner -->|Propose query| Retriever
    Retriever -->|Documents| Refiner
    Refiner -->|Refined| Reasoner
    Reasoner -->|Enough| Answer[Answer]
    
    classDef imrag fill:#e0e7ff,stroke:#3730a3;
    class Reasoner,Retriever,Refiner,Progress imrag;
```

---

## Navigation

| Architecture | Link |
|--------------|------|
| Our Current System | [Above](#our-current-architecture-post-t1-t7-fixes) |
| SPLIT-RAG | [Above](#split-rag-architecture) |
| PC-RAG | [Above](#pc-rag-architecture) |
| RAC | [Above](#rac-architecture) |
| ICR | [Above](#icr-architecture) |
| CPP | [Above](#cpp-architecture) |
| CALMem | [Above](#calmem-architecture) |
| H-RAG | [Above](#h-rag-architecture) |
| 5ting | [Above](#5ting-architecture) |
| GUIR | [Above](#guir-architecture) |
| DUTIR | [Above](#dutir-architecture) |
| CoRAG | [Above](#corag-architecture) |
| IM-RAG | [Above](#im-rag-architecture) |