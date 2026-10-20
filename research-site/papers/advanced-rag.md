---
layout: default
title: "Advanced RAG Paradigms Papers"
description: "CoRAG, IM-RAG, CoopRAG, MMOA-RAG, Reflective RAG, CalibRAG - Chain-of-Retrieval, Inner Monologues, Cooperative RAG, Multi-agent RL, Self-evaluation"
---

<div class="page-header">
  <h1>Advanced RAG Paradigms Papers</h1>
  <p class="lead">CoRAG, IM-RAG, CoopRAG, MMOA-RAG, Reflective RAG, CalibRAG - Chain-of-Retrieval, Inner Monologues, Cooperative RAG, Multi-agent RL, Self-evaluation</p>
</div>

## Paper Summaries

### CoRAG: Chain-of-Retrieval Augmented Generation

| Field | Detail |
|-------|--------|
| **Title** | CoRAG: Chain-of-Retrieval Augmented Generation |
| **Venue** | NeurIPS 2025 (Poster) |
| **Key Innovation** | Iterative retrieval + reasoning chains (o1-like RAG) |

**Key Claims**:
- **CoRAG**: Teaches LLMs to conduct iterative retrieval + reasoning step-by-step
- **Mechanism**: Dynamic query reformulation based on evolving state
- **Training**: Rejection sampling to generate intermediate retrieval chains
- **Results**: > SOTA on multi-hop QA, KILT benchmark

**Architecture**:
```
Query → Reasoner (Questioner) → Retriever → Refiner → Reasoner (Answerer)
                     ↑_____________|
                    (multi-round retrieval)
```

**Relevance**: Our T1+T2 fallback cascade = simplified multi-step retrieval. CoRAG shows **iterative retrieval+reasoning** for complex queries.

---

### IM-RAG: Inner Monologues for Multi-Round Retrieval

| Field | Detail |
|-------|--------|
| **Title** | IM-RAG: Multi-Round Retrieval-Augmented Generation Through Learning Inner Monologues |
| **Venue** | SIGIR 2024 (ACM DL: 3626772.3657760) |
| **Key Innovation** | LLM inner monologue → multi-round retrieval via prompting + RL |

**Key Claims**:
- **IM-RAG**: LLM serves as Reasoner → proposes queries to Retriever
- **Components**: Reasoner (Questioner/Answerer), Retriever, Refiner, Progress Tracker
- **Training**: PPO (Proximal Policy Optimization) on answer correctness
- **Results**: 82.5% vs 41.2% F1 (IM-RAG vs RAG baseline) on HotPotQA

**Architecture**:
```
Reasoner (Questioner) → Retriever → Refiner → Reasoner (Answerer)
         ↑______________| (multi-round)
```

**Relevance**: Our T1+T2 cascade = fixed 2-step. IM-RAG shows **learned multi-round** via RL.

---

### CoopRAG: Cooperative Retrieval + LLM Encoder

| Field | Detail |
|-------|--------|
| **Title** | Cooperative Retrieval-Augmented Generation for Question Answering |
| **Venue** | NeurIPS 2025 |
| **Key Innovation** | Retriever + LLM fine-tuned encoder → mutual information + contrastive ranking |

**Key Claims**:
- **CoopRAG**: Retriever + LLM fine-tuned encoder cooperate
- **Mechanism**: Unrolling-augmented retrieval (UAR) + token-level embeddings
- **Results**: +5.3% multi-hop QA, +35.2% simple QA vs SOTA

**Relevance**: Our KB retrieval + Gemma = separate. CoopRAG shows **tight coupling** helps.

---

### MMOA-RAG: Multi-Agent RL for RAG

| Field | Detail |
|-------|--------|
| **Title** | Improving Retrieval-Augmented Generation through Multi-Agent Reinforcement Learning |
| **Venue** | NeurIPS 2025 |
| **Key Innovation** | Multi-agent RL: Query Writer, Selector, Generator + joint optimization |

**Key Claims**:
- **MMOA-RAG**: Four modules as agents → joint optimization via MARL
- **Modules**: Query Writer, Selector, Generator + fixed Retriever
- **Results**: Outperforms baselines on QA benchmarks

**Relevance**: Our modular pipeline (retrieve → build → generate) = separate modules. MMOA-RAG shows **joint optimization** helps.

---

### Reflective RAG: Self-Evaluation Driven Strategy

| Field | Detail |
|-------|--------|
| **Title** | Reflective RAG: Self-Evaluation Driven Strategy Optimization in Agentic RAG |
| **Venue** | ACL 2026 Findings (ACL Anthology: 2026.findings-acl.648) |
| **Key Innovation** | Self-evaluation tagging → RL strategy optimization |

**Key Claims**:
- **Problem**: Agentic RAG lacks self-evaluation of retrieved info
- **Solution**: 
  1. Reflection tagging: Model critiques relevance
  2. Two-stage: SFT (reflection signals) → RL (strategy + dynamic KL)
- **Results**: Outperforms agentic baselines on 5 QA benchmarks

**Relevance**: Our faith guard = simplified reflection. Reflective RAG shows **explicit self-evaluation** works.

---

### CalibRAG: Calibrated RAG

| Field | Detail |
|-------|--------|
| **Title** | Reliable Decision-Making via Calibration-Oriented Retrieval-Augmented Generation (CalibRAG) |
| **Venue** | NeurIPS 2025 |
| **Key Innovation** | Calibrated confidence scores for retrieved documents |

**Key Claims**:
- **Problem**: RAG decisions uncalibrated → unreliable
- **Solution**: Calibrated Retrieval → rerank by predicted confidence
- **Mechanism**: Sort by predicted confidence, not similarity score
- **Results**: Improves calibration + accuracy across datasets

**Relevance**: Our `_top_evidence_score()` = simplified confidence. CalibRAG shows **calibrated confidence** helps.

---

## Comparison Table

| Paradigm | Core Idea | Training | Key Component | Our Relevance |
|----------|-----------|----------|---------------|---------------|
| **CoRAG** | Iterative retrieval+reasoning | Rejection sampling | Chain-of-retrieval | T1+T2 cascade (fixed 2-step) |
| **IM-RAG** | Inner monologue + RL | PPO | Reasoner/Retriever loop | T1+T2 = fixed 2-step |
| **CoopRAG** | Cooperative retriever+encoder | Fine-tuned encoder | Mutual info + contrastive | Separate retriever/generator |
| **MMOA-RAG** | Multi-agent RL | MARL | 4 agents + joint opt | Modular pipeline (separate) |
| **Reflective RAG** | Self-evaluation + RL | SFT + RL | Reflection tags | Faith guard (simplified) |
| **CalibRAG** | Calibrated confidence | Calibration training | Confidence rerank | `_top_evidence_score()` |

---

## Evolution Path: Our System → Advanced Paradigms

```mermaid
flowchart LR
    A[Current: Fixed Pipeline<br/>Retrieve → Build → Generate] --> B[T1-T7 Fixes<br/>Fallback + Sticky + Faith]
    B --> C[Learned Routing<br/>(SPLIT-RAG)]
    C --> D[Iterative Retrieval<br/>(CoRAG/IM-RAG)]
    D --> E[Cooperative Components<br/>(CoopRAG/MMOA-RAG)]
    E --> F[Self-Evaluation<br/>(Reflective RAG)]
    F --> G[Calibrated Confidence<br/>(CalibRAG)]
```

---

## Migration Path

| Current | Target | Effort | Papers |
|---------|--------|--------|--------|
| Static `subspace_map` | Learned router (SPLIT-RAG) | Medium | SPLIT-RAG |
| Fixed 2-step fallback | Iterative retrieval (CoRAG) | High | CoRAG, IM-RAG |
| Separate retriever/generator | Cooperative (CoopRAG) | High | CoopRAG |
| Modular pipeline | Joint optimization (MMOA-RAG) | High | MMOA-RAG |
| Faith guard | Self-evaluation (Reflective RAG) | Medium | Reflective RAG |
| Evidence score | Calibrated confidence (CalibRAG) | Medium | CalibRAG |

---

## Related Pages

- [Paper: Retrieval Fusion & RRF](./retrieval-fusion.html)
- [Paper: Faithfulness & Hallucination](./faithfulness.html)
- [Paper: Memory Architectures](./memory-architectures.html)
- [Our Implementation](../our-impl.html)