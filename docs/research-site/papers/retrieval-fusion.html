---
layout: default
title: "Retrieval Fusion & RRF Papers - Multi-Turn RAG Research"
description: "GUIR, 5ting, H-RAG, Sifei, IITKanBDone, AILS-NTUA, uva-irlab - Multi-query fusion, dual-query merge, nested-RRF, hybrid dense+sparse, parent-child retrieval"
---

<div class="page-header">
  <h1>Retrieval Fusion & RRF Papers</h1>
  <p class="lead">GUIR, 5ting, H-RAG, Sifei, IITKanBDone, AILS-NTUA, uva-irlab - Multi-query fusion, dual-query merge, nested-RRF, hybrid dense+sparse, parent-child retrieval</p>
</div>

## Paper Summaries

### GUIR: Multi-Query Fusion for Conversational Retrieval

| Field | Detail |
|-------|--------|
| **Title** | GUIR at SemEval-2026 Task 8: Training-Free Multi-Query Fusion for Robust Conversational Retrieval |
| **Authors** | Pasha Abrishamchian, Ophir Frieder, Nazli Goharian |
| **Venue** | SemEval 2026 (ACL Anthology: 2026.semeval-1.32) |
| **Code** | Not specified |

**Key Claims**:
- **Three query representations**:
  1. **LT (Last-Turn)**: Raw user input, preserves original terminology
  2. **RW (Rewritten)**: LLM rewrite with context
  3. **QS (Query-Specific)**: Corpus-adapted terminology
- **Fusion**: Pool-then-rerank → RRF across all three
- **Results**: 0.5453 nDCG@5 (Rank 3/38) vs baseline 0.4795 (+12.3%)

**Key Insight**: "Optimal retrieval strategies vary significantly at the query level, making a single universal strategy inherently suboptimal."

**Relevance to Our Fix**: Our T1 RRF fusion = simplified GUIR (filtered + whole-KB instead of LT+RW+QS).

---

### 5ting: LLM Reranking + Faithfulness Control

| Field | Detail |
|-------|--------|
| **Title** | 5ting at SemEval-2026 Task 8: Strong End-to-End Multi-Turn RAG via LLM-Based Reranking and Faithfulness Control |
| **Venue** | SemEval 2026 (ACL Anthology: 2026.semeval-1.145) |
| **Key Innovation** | LLM-based reranking + evidence-constrained generation |

**Key Claims**:
- **Pipeline**: Dense retrieval → FAISS → LLM reranking (listwise) → Evidence-constrained generation
- **Dual-query strategy**: Last-turn + rewrite → merge → captures both entity matching and semantic relevance
- **Faithfulness**: IDK-conditioned harmonic mean scoring

**Results**: MTRAGEval Task A/C participant

---

### H-RAG: Hierarchical Parent-Child Retrieval

| Field | Detail |
|-------|--------|
| **Title** | H-RAG at SemEval-2026 Task 8: Hierarchical Parent–Child Retrieval for Multi-Turn RAG Conversations |
| **Venue** | SemEval 2026 (ACL Anthology: 2026.semeval-1.155) |
| **Key Innovation** | Parent-child document hierarchy + hybrid retrieval + parent-level context reconstruction |

**Key Claims**:
- **Parent-child hierarchy**: Documents → parent chunks (summary) → child chunks (details)
- **Retrieval**: Hybrid (BM25 + dense) → cross-encoder rerank → parent-level context reconstruction
- **Results**: nDCG@5 0.4271 (Task A), harmonic mean 0.3241 (Task C)

**Relevance**: Our KB could benefit from parent-child chunking (current: flat chunks).

---

### Sifei: Hybrid Retrieval + Query Rewriting

| Field | Detail |
|-------|--------|
| **Title** | Sifei at SemEval-2026 Task 8: Hybrid Retrieval and Query Rewriting for Multi-Turn RAG |
| **Authors** | Sifei Meng, Dmitry Ilvovsky |
| **Venue** | SemEval 2026 (ACL Anthology: 2026.semeval-1.32) |
| **Code** | https://github.com/mengsifei/MultiturnRAG |

**Key Claims**:
- **Pipeline**: Dense (BGE-M3) + Sparse (BM25) → RRF → Cross-encoder rerank (BGE-reranker-large)
- **Query Rewriting**: Controlled LLM rewrite
- **Results**: 0.5453 nDCG@5 (Rank 3/38) vs baseline 0.4795 (+12.3%)

---

### IITKanBDone: ELSER + Mistral

| Field | Detail |
|-------|--------|
| **Title** | IITKanBDone at SemEval-2026 Task 8: MTRAGEval |
| **Venue** | SemEval 2026 |
| **Key Claims** | ELSER (learned sparse) + Mistral-7B-Instruct → nDCG@5 0.4018 (Rank 24/38) |

---

### AILS-NTUA: Nested-RRF Multi-Strategy Rewriting

| Field | Detail |
|-------|--------|
| **Title** | AILS-NTUA at SemEval-2026 Task 8: Evaluating Multi-Turn RAG Conversations |
| **Venue** | SemEval 2026 |
| **Key Claims** | 4 rewriting strategies → Nested-RRF fusion |

**Rewriting Strategies**:
1. **Minimal**: Coreference resolution
2. **Corpus-Specific**: Domain terminology adaptation
3. **HyDE**: Hypothetical document embedding
4. **Chain-of-Thought**: Multi-faceted inference

**Fusion**: Nested-RRF (RRF of RRFs) → ensemble gains

---

### uva-irlab: Learned Sparse + Listwise Reranking

| Field | Detail |
|-------|--------|
| **Title** | uva-irlab-conv at SemEval-2026 Task 8: Multi-Turn RAG with Learned Sparse Retrieval and Listwise Reranking |
| **Venue** | SemEval 2026 |
| **Key Claims** | Learned sparse retrieval (LSR) + LLM listwise reranking |

---

## Fusion Techniques Comparison

| Paper | Fusion Method | Query Variants | Reranking | Score |
|-------|---------------|----------------|-----------|-------|
| **Our T1** | RRF Fusion (filtered + whole-KB) | 2 (filtered + whole) | BGE-m3 | Hit 0.78 |
| **GUIR** | RRF Fusion | 3 (LT + RW + QS) | Cross-encoder | 0.545 nDCG@5 |
| **Sifei** | RRF (dense + sparse) | 1 (rewritten) | BGE-reranker-large | 0.545 nDCG@5 |
| **5ting** | Dual-query merge + LLM rerank | 2 (last + rewrite) | LLM listwise | MTRAGEval |
| **AILS-NTUA** | Nested-RRF | 4 (Minimal, Corpus, HyDE, CoT) | RRF ensemble | MTRAGEval |
| **uva-irlab** | LSR + listwise rerank | 1 (rewritten) | LLM listwise | MTRAGEval |

---

## Our RRF Fusion Implementation

```python
# retrieve.py - _fuse_subspace_rrf()
def _fuse_subspace_rrf(filtered, whole, filtered_weight=1.3):
    """
    Reciprocal Rank Fusion with filtered boost
    score = 1/(60 + rank) * weight
    """
    merged = {}
    # Filtered leg: weight 1.3x (boosted)
    for rank, chunk in enumerate(filtered):
        key = chunk.chunk_id
        score = filtered_weight / (60 + rank + 1)
        merged[key] = max(merged.get(key, 0), score)
    
    # Whole-KB leg: weight 1.0
    for rank, chunk in enumerate(whole):
        key = chunk.chunk_id
        score = 1.0 / (60 + rank + 1)
        merged[key] = max(merged.get(key, 0), score)
    
    # Sort by fused score, take top 20
    return sorted(merged.values(), key=lambda x: x.fused_score, reverse=True)[:20]
```

---

## Architecture: Our Fusion vs Papers

```mermaid
flowchart TD
    A[Query] --> B[Filtered Retrieval<br/>(subspace filter)]
    A --> C[Whole-KB Retrieval<br/>(no filter)]
    B --> D{Strong?}
    C --> D
    D -->|Weak| E[RRF Fusion<br/>filtered 1.3x + whole 1.0x]
    E --> F[Top 20 Results]
    
    subgraph GUIR [GUIR: 3 queries]
        G1[LT: Last Turn]
        G2[RW: Rewritten]
        G3[QS: Query-Specific]
        G1 --> H[RRF Fusion]
        G2 --> H
        G3 --> H
    end
    
    subgraph GUIR2 [GUIR: 3 queries]
        I1[Minimal Rewrite]
        I2[Corpus-Specific]
        I3[HyDE]
        I4[CoT]
        I1 --> J[Nested-RRF]
        I2 --> J
        I3 --> J
        I4 --> J
    end
```

---

## Related Pages

- [Problem: Retrieval Degradation](../problems/retrieval-degradation.html)
- [Paper: Subspace Filtering](./subspace-filtering.html)
- [Paper: Hallucination Control](./faithfulness.html)
- [Architecture: RRF Fusion](../architectures.html#rrf-fusion)