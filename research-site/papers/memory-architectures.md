---
layout: default
title: "Memory Architectures Papers"
description: "CALMem, CPP, Context Recycling, Rag.NET, OpenAI Sessions - Dual memory, segmented episodic memory, bounded hierarchical context"
---

<div class="page-header">
  <h1>Memory Architectures Papers</h1>
  <p class="lead">CALMem, CPP, Context Recycling, Rag.NET, OpenAI Sessions - Dual memory, segmented episodic memory, bounded hierarchical context</p>
</div>

## Paper Summaries

### CALMem: Dual Memory for Conversational AI

| Field | Detail |
|-------|--------|
| **Title** | Application-Layer Dual Memory for Conversational AI: Achieving Virtually Unbounded Context Without Model Modification |
| **Venue** | arXiv:2605.20724 (2026) |
| **Key Innovation** | Dual memory: Episodic (sliding-window vector embeddings) + Semantic (agent-writable structured facts) |

**Architecture**:
```
┌─────────────────────────────────────┐
│           CALMem Architecture       │
├─────────────────────────────────────┤
│  Episodic Memory (Vector Store)     │
│  - Sliding window embeddings        │
│  - Intra-session retrieval          │
├─────────────────────────────────────┤
│  Semantic Memory (Structured Facts) │
│  - Agent-writable facts             │
│  - Cross-session persistence        │
├─────────────────────────────────────┤
│  MOIM Injector                      │
│  - Token-budget adaptive injection  │
│  - Prepends relevant context        │
└─────────────────────────────────────┘
```

**Key Innovations**:
- **Episodic Memory**: Vector embeddings of conversation turns, sliding window
- **Semantic Memory**: Agent-writable structured facts (explicit knowledge)
- **MOIM (Message of Injected Memory)**: Auto-retrieves relevant context, scales with budget
- **Intra-session retrieval**: Recalls compacted-away turns from CURRENT session (novel!)

**Results**: ~750 tokens/turn injected vs 22K baseline; 1-2 orders magnitude cost reduction

---

### CPP: Context Persistence Protocol

| Field | Detail |
|-------|--------|
| **Title** | Bounded Conversational Memory with Hybrid Retrieval and Evidence Highlighting |
| **Venue** | SIGDIAL 2026 |
| **Key Innovation** | Context Persistence Protocol (CPP) — segmented episodic memory |

**Four Phases**:
1. **Segmentation**: 3-10 turns/segment, cosine δ boundary
2. **Dual-Indexing**: Lexical (BM25) + Semantic (embedding) per segment
3. **Budgeted Retrieval**: Top segments under hard storage budget
4. **Evidence Highlighting**: Single most informative sentence per segment

**Segmentation**: Cosine similarity drop below δ between turns → new segment

**Results**: Matches unbounded baseline on LoCoMo; better on multi-hop; marginal deficit on open-domain

---

### Context Recycling: Hierarchical Memory

| Field | Detail |
|-------|--------|
| **Title** | Context Recycling for Long-Horizon LLM Inference |
| **Venue** | arXiv:2606.26105 (2026) |
| **Key Innovation** | Hierarchical layers: L0 (500) + L1 (2-10K) + L2 (~1K) |

**Three Layers**:
- **L0 Permanent** (500 tokens): System prompt, core facts
- **L1 Loaded Branch** (2-10K): Active knowledge per turn
- **L2 Compacted History** (~1K): Compressed session history

**Results**:

| Turn | Baseline | Context Recycling |
|------|----------|-------------------|
| 1 | ~500 | ~850 |
| 50 | ~22,000 | ~850 |
| 1K | ~200,000 | ~850 |

---

### Rag.NET: Composable Memory Layers

| Field | Detail |
|-------|--------|
| **Source** | GitHub: MarcelRoozekrans/Rag.NET |
| **Key Innovation** | Two composable layers: In-session + Cross-session |

**Layer 1 - ConversationMemoryPipeline (In-session)**:
- Sliding window (MaxExchanges)
- Token budget (MaxTokens)
- Optional LLM summary (UseSummary)

**Layer 2 - PersistentConversationMemory**:
- Embeds each exchange → vector store
- Keyed by sessionId
- Injects relevant past exchanges as system prefix

---

### OpenAI Session Memory

| Field | Detail |
|-------|--------|
| **Source** | OpenAI Cookbook / Responses API |
| **Implementations** | TrimmingSession, SummarizingSession |

---

## Comparison Table

| System | Segmentation | Retrieval | Budget | Cross-Session | Novelty |
|--------|--------------|-----------|--------|---------------|---------|
| **CPP** | Cosine δ (3-10 turns) | Hybrid (lexical + semantic) | Hard budget | Yes (segments) | Segment evidence highlighting |
| **CALMem** | Sliding window + facts | Episodic + Semantic | Token-budget adaptive | Yes (semantic layer) | Dual memory + MOIM |
| **Context Recycling** | Hierarchical (L0/L1/L2) | Layer-based | Fixed budget | Yes (hierarchical) | Bounded context (850 tok) |
| **Rag.NET** | Sliding window + summary | Vector store | MaxExchanges/MaxTokens | Yes (vector store) | Composable layers |
| **OpenAI** | Trimming / Summarizing | Built-in | Max turns / summary | Yes (session object) | Built-in API |

---

## Our Implementation vs Papers

| Aspect | Our Fix (T4+T8) | CPP | CALMem | Context Recycling |
|--------|----------------|-----|--------|-------------------|
| **Segmentation** | Implicit (generic turn count) | Cosine δ threshold | Sliding window | Hierarchical L0/L1/L2 |
| **Sticky Carry** | Filter_path injection | Segment retrieval | Episodic recall | L1 branch loading |
| **Decay** | After 3 generic turns | Segment boundary | Sliding window | L2 compaction |
| **Budget** | Implicit (filter_path) | Hard storage budget | Token-budget adaptive | Fixed 850 tok/turn |
| **Cross-Session** | No (single session) | Yes (segment store) | Yes (semantic layer) | Yes (hierarchical) |

---

## Architecture: Our Sticky Flow vs Papers

```mermaid
flowchart TD
    A[User Query] --> B[Load Checkpoint]
    B --> C{Sticky Applied?}
    C -->|Yes| D[Count Generic Turns<br/>(our T8: simple count)]
    D --> E{> decay_threshold?}
    E -->|Yes| F[Decay: sticky=None<br/>(CPP: segment boundary)]
    E -->|No| G[Inject filter_path<br/>(CALMem: episodic recall)]
    C -->|No| H[Normal Classify/Infer]
    F --> H
    G --> I[Retrieve with filter_path]
    H --> I
    I --> J[Generate]
    J --> K[Save Checkpoint]
```

---

## Future: Toward CALMem/CPP

| Enhancement | Based On | Effort |
|-------------|----------|--------|
| Cosine-based segmentation | CPP | Medium |
| Semantic fact layer | CALMem | High |
| Hierarchical context (L0/L1/L2) | Context Recycling | High |
| Cross-session vector recall | Rag.NET / CALMem | Medium |
| Evidence highlighting per segment | CPP | Low |

---

## Related Pages

- [Problem: Sticky Context Decay](../problems/sticky-context.html)
- [Paper: Subspace Filtering](./subspace-filtering.html)
- [Paper: Retrieval Fusion & RRF](./retrieval-fusion.html)
- [Architecture: CPP/CALMem](../architectures.html#cpp-calmem)