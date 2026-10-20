---
layout: default
title: "Faithfulness & Hallucination Papers"
description: "DUTIR, Reflective RAG, 5ting, CoRAG, CoopRAG, CalibRAG - Faithfulness guards, self-evaluation, evidence-constrained generation, calibration"
---

<div class="page-header">
  <h1>Faithfulness & Hallucination Papers</h1>
  <p class="lead">DUTIR, Reflective RAG, 5ting, CoRAG, CoopRAG, CalibRAG - Faithfulness guards, self-evaluation, evidence-constrained generation, calibration</p>
</div>

## Paper Summaries

### DUTIR: Hybrid Retrieval + Faithfulness Guard

| Field | Detail |
|-------|--------|
| **Title** | DUTIR at SemEval-2026 Task 8: A Hybrid Retrieval and Faithfulness-Guarded Framework for Multi-Turn RAG |
| **Venue** | SemEval 2026 (ACL Anthology: 2026.semeval-1.48) |
| **Key Innovation** | Confidence-based answerability gating + hybrid retrieval (BGE-M3 + BM25 + RRF) |

**Key Claims**:
- **Pipeline**: 
  1. LLM query rewriting (GPT-5.2) → resolve conversational dependencies
  2. Hybrid retrieval: BGE-M3 + BM25 → RRF
  3. **Confidence-based answerability gating** → minimizes hallucination
  4. Faithfulness-guarded generation
- **Trade-off**: Over-conservative → unwarranted "I Don't Know" for partially answerable queries

**Relevance to Our Fix**:
- Our `get_evidence_threshold()` = per-subspace confidence gating
- DUTIR validates: **confidence-based gating reduces hallucination**
- Our `FAITH_GUARD_MIN_SCORE = 0.5` = similar to confidence gating

---

### Reflective RAG: Self-Evaluation Driven Strategy

| Field | Detail |
|-------|--------|
| **Title** | Reflective RAG: Self-Evaluation Driven Strategy Optimization in Agentic Retrieval-Augmented Generation |
| **Venue** | ACL 2026 Findings (ACL Anthology: 2026.findings-acl.648) |
| **Key Innovation** | Self-evaluation tagging → RL strategy optimization |

**Key Claims**:
- **Problem**: Agentic RAG lacks capacity to evaluate retrieved info utility → brittle reasoning
- **Solution**: 
  1. **Reflection tagging**: Model critiques relevance of retrieved content
  2. **Two-stage training**: SFT (reflection signals) → RL (strategy optimization with dynamic KL)
- **Results**: Outperforms strong agentic baselines on 5 knowledge-intensive QA benchmarks

**Relevance**: Our faith guard = simplified reflection (coverage + score check). Reflective RAG shows **explicit self-evaluation** improves robustness.

---

### 5ting: Evidence-Constrained Generation + IDK-Conditioned Scoring

| Field | Detail |
|-------|--------|
| **Title** | 5ting at SemEval-2026 Task 8: Strong End-to-End Multi-Turn RAG via LLM-Based Reranking and Faithfulness Control |
| **Venue** | SemEval 2026 |
| **Key Innovation** | Evidence-constrained generation + IDK-conditioned harmonic mean |

**Key Claims**:
- **Evidence-constrained generation**: Only generate if evidence supports
- **IDK-conditioned harmonic mean**: Harmonic mean of quality and faithfulness, conditioned on "I Don't Know" rate
- **Pipeline**: Dense retrieval → FAISS → LLM reranking → Evidence-constrained generation

**Relevance**: Our `FAITH_GUARD_MIN_SCORE = 0.5` + `FAITH_GUARD_MIN_COVERAGE = 0.20` = simplified evidence constraint.

---

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

**Relevance**: Our T1+T2 fallback cascade = simplified multi-step retrieval. CoRAG shows **iterative retrieval+reasoning** for complex queries.

---

### CoopRAG: Cooperative Retrieval + LLM Encoder

| Field | Detail |
|-------|--------|
| **Title** | Cooperative Retrieval-Augmented Generation for Question Answering |
| **Venue** | NeurIPS 2025 |
| **Key Innovation** | Retriever + LLM fine-tuned encoder → mutual information exchange + contrastive ranking |

**Key Claims**:
- **CoopRAG**: Retriever + LLM fine-tuned encoder cooperate
- **Mechanism**: Unrolling-augmented retrieval (UAR) + token-level embeddings
- **Results**: +5.3% on multi-hop QA, +35.2% on simple QA vs SOTA

**Relevance**: Our KB retrieval + Gemma generation = separate components. CoopRAG shows **tight coupling** improves performance.

---

### CalibRAG: Calibrated Retrieval-Augmented Generation

| Field | Detail |
|-------|--------|
| **Title** | Reliable Decision-Making via Calibration-Oriented Retrieval-Augmented Generation (CalibRAG) |
| **Venue** | NeurIPS 2025 |
| **Key Innovation** | Calibrated confidence scores for retrieved documents |

**Key Claims**:
- **Problem**: RAG decisions uncalibrated → unreliable
- **Solution**: Calibrated Retrieval → rerank by predicted confidence
- **Mechanism**: Sort documents by predicted confidence, not similarity score
- **Results**: Improves calibration + accuracy across datasets

**Relevance**: Our `_top_evidence_score()` = simplified confidence. CalibRAG shows **calibrated confidence** improves decision-making.

---

## Faithfulness Approaches Comparison

| Paper | Mechanism | Guard Type | Training | Our Equivalent |
|-------|-----------|------------|----------|----------------|
| **DUTIR** | Confidence gating | Answerability gate | GPT-5.2 rewrite | `get_evidence_threshold()` |
| **Reflective RAG** | Self-evaluation tags | Reflection + RL | SFT + RL | Faith guard (simplified) |
| **5ting** | Evidence constraint + IDK | IDK-conditioned harmonic mean | LLM rerank | `FAITH_GUARD_MIN_SCORE` |
| **CoRAG** | Iterative retrieval-reasoning | Chain-of-retrieval | Rejection sampling | T1+T2 cascade (simplified) |
| **CoopRAG** | Cooperative retriever+encoder | Mutual info + contrastive | Fine-tuned encoder | Separate retriever/generator |
| **CalibRAG** | Calibrated confidence | Confidence rerank | Calibration training | `_top_evidence_score()` |

---

## Our Faith Guard Implementation

```python
# format_response.py
FAITH_GUARD_MIN_SCORE = 0.5
FAITH_GUARD_MIN_COVERAGE = 0.20

async def format_response(state):
    # ... generation ...
    
    # F: Faith/Hall guard on weak-evidence answers
    if (state.get("fallback_used") or state.get("broaden_used")) and ABSTENTION_PHRASE not in content:
        used_top = _top_evidence_score(chosen_chunks)
        coverage = _token_coverage(content, chosen_chunks)
        
        if used_top < FAITH_GUARD_MIN_SCORE and coverage < FAITH_GUARD_MIN_COVERAGE:
            log.info(f"Faith guard fired: coverage={coverage:.3f} top={used_top:.3f}")
            content = NO_EVIDENCE_MSG
            citations = []
            faith_refused = True
```

### Coverage Metric

```python
def _token_coverage(answer, chunks):
    a_tokens = set(answer.split())
    if not a_tokens: return 1.0
    corpus = " ".join(c.get("content", "") for c in chunks)
    c_tokens = set(corpus.split())
    return len(a_tokens & c_tokens) / len(a_tokens) if c_tokens else 0.0
```

---

## Benchmark Delta

| Metric | Before | After | Note |
|--------|--------|-------|------|
| Hallucination | 0.195 | **0.254** | +0.059 (tradeoff) |
| Non-hallucination | 0.805 | **0.746** | Tradeoff for recall |
| G5 refusal | ✅ | ✅ | Maintained |
| Cheque T3 citations | 0 | **5** | Fixed (lexical guard) |
| Facilities T3 citations | 0 | **5** | Fixed (lexical guard) |

---

## Architecture: Faith Guard Flow

```mermaid
flowchart TD
    A[Retrieved Chunks] --> B{Strong Evidence?}
    B -->|No| C{fallback_used or broaden_used?}
    C -->|Yes| D[Compute top_score + coverage]
    C -->|No| E[Normal Generation]
    D --> F{top_score < 0.5 AND coverage < 0.20?}
    F -->|Yes| G[REPLACE with NO_EVIDENCE_MSG<br/>citations=[]]
    F -->|No| E
    E --> H[Generate Answer]
    H --> I[Return]
    G --> I
    
    style G fill:#fef2f2,stroke:#ef4444
    style C fill:#fef3e0,stroke:#f57f17
```

---

## Related Pages

- [Problem: Hallucination Control](../problems/hallucination.html)
- [Paper: Retrieval Fusion & RRF](./retrieval-fusion.html)
- [Paper: Subspace Filtering](./subspace-filtering.html)
- [Architecture: Faith Guard](../architectures.html#faith-guard)