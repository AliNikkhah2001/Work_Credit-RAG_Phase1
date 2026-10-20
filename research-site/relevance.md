---
layout: default
title: "Relevance Mapping"
description: "Detailed table mapping each of our fixes to the specific paper, section, and mechanism that validates it"
---

<div class="page-header">
  <h1>Relevance Mapping</h1>
  <p class="lead">Detailed table mapping each of our fixes to the specific paper, section, and mechanism that validates it</p>
</div>

## Fix-to-Paper Mapping

| Our Fix | Problem Solved | Paper | Section/Mechanism | Validation |
|---------|----------------|-------|-------------------|------------|
| **Map Fix** | Cheque filter matched 0 chunks | **PC-RAG** | Domain-partitioned retrieval | 51% false-positive reduction |
| | | **SPLIT-RAG** | Question-driven partitioning | Learned routing from training Qs |
| | | **DSRAG** | Hierarchical KG | Concept/Instance KG hierarchy |
| **T1: RRF Fusion** | Hard filter replace → fusion | **GUIR** | Dual-query merged retrieval | +12.3% nDCG@5 |
| | | **5ting** | Dual-query strategy | Last-turn + rewrite merge |
| | | **Sifei** | Hybrid dense+sparse + RRF | 0.5453 nDCG@5 (Rank 3/38) |
| | | **AILS-NTUA** | Nested-RRF | Multi-strategy rewriting |
| **T2: Broadened Retry** | Filtered weak → whole-KB + broadened | **GUIR** | Multi-query generation + fusion | LT + RW + QS fusion |
| | | **Sifei** | Hybrid dense+sparse + beam | keyword_boost + beam |
| | | **5ting** | Dual-query + rerank | Last-turn + rewrite |
| **T3: Per-Subspace Threshold** | Global 0.15 starved cheque | **PC-RAG** | Domain-specific thresholds | Domain-specific evidence |
| | | **DUTIR** | Confidence-based gating | Per-domain confidence |
| **T4: Sticky Carry** | Generic follow-ups lost context | **CALMem** | Episodic memory carry | Intra-session retrieval |
| | | **CPP** | Segment persistence | Segment-based recall |
| | | **Context Recycling** | L1 branch loading | Hierarchical context |
| **T5: Scattered Gate** | 6/6 scattered failed to clarify | **RAC** | Retrieval-grounded clarify | Corpus-grounded clarification |
| | | **ICR** | Iterative clarify-rewrite | Clarify→rewrite loop |
| | | **Qulac/ClariQ** | Facet-based datasets | 10k+ ambiguous queries |
| | | **CLARITY** | Multi-facet ambiguity | Multi-turn resolution |
| **T6: Lexical Bypass** | Rerank 0.0 but text relevant | **5ting** | Corpus-specific rewrite | Preserves terminology |
| | | **AILS-NTUA** | Corpus-specific rewrite | Domain terminology |
| | | **H-RAG** | Parent-child retrieval | Context reconstruction |
| **T3+F: Faith Guard** | Weak-evidence hallucination | **DUTIR** | Confidence gating | Answerability gate |
| | | **Reflective RAG** | Self-evaluation + RL | Reflection + RL |
| | | **5ting** | Evidence constraint | IDK-conditioned harmonic mean |
| | | **CoRAG** | Iterative retrieval | Chain-of-retrieval |
| | | **CoopRAG** | Cooperative retriever | Mutual information |
| | | **CalibRAG** | Calibrated confidence | Calibrated rerank |
| **C: GPU KB** | Dense 2325ms → 19ms | **SPLIT-RAG** | Parallel subgraph retrieval | Parallel retrieval |
| | | **H-RAG** | Hierarchical retrieval | GPU-friendly config |
| | | **Sifei** | Hybrid dense+sparse | GPU cross-encoder |
| | | **CoRAG** | Chain-of-retrieval | Iterative retrieval |

---

## Per-Fix Deep Dive

### Fix 1: Subspace Map Correction → PC-RAG + SPLIT-RAG

**Our Issue**: `subspace_map["cheque"] = "چک"` matched 0 chunks. KB folder = `"گزارش اعتباراتنجی چک"`.

**PC-RAG Validation**: "Domain-partitioned retrieval: decompose query into domain-isolated sub-tasks, independent retrieval per partition."

**SPLIT-RAG Validation**: "Question-driven graph partitioning: partitions KG by reasoning paths from training questions, assigns specialized agents."

**Our Fix**: Map correction + future learned routing.

---

### Fix 2: RRF Fusion (T1) → GUIR + Sifei + AILS-NTUA

**Our Issue**: Hard filter replace lost relevant chunks when filtered weak.

**GUIR**: "Dual-query merged retrieval: last-turn + rewrite → merge captures both entity matching and semantic relevance."

**Sifei**: "Hybrid dense+sparse + RRF → 0.5453 nDCG@5 (Rank 3/38)."

**AILS-NTUA**: "Nested-RRF: Minimal + Corpus-Specific + HyDE + CoT → RRF ensemble."

**Our Implementation**: `_fuse_subspace_rrf(filtered, whole, filtered_weight=1.3)` — filtered leg gets 1.3x boost.

---

### Fix 3: Broadened Retry (T2) → GUIR + Sifei

**Our Issue**: Filtered retrieval weak → no fallback.

**GUIR**: "Multi-query generation and fusion: LT + RW + QS → RRF fusion."

**Sifei**: "Hybrid dense+sparse + controlled query rewriting + cross-encoder reranking."

**Our Implementation**: `_t2_try_broadened_retry(top_k=30, keyword_boost=1.5)` with RRF fusion.

---

### Fix 4: Per-Subspace Threshold (T3) → PC-RAG + DUTIR

**Our Issue**: Global `evidence_min_score=0.15` starved cheque (scores 0.028).

**PC-RAG**: "Domain-partitioned retrieval with domain-specific evidence thresholds."

**DUTIR**: "Confidence-based answerability gating minimizes hallucination."

**Our Implementation**: `get_evidence_threshold(cheque)=0.05, person=0.10, legal=0.15, general=0.15`.

---

### Fix 5: Sticky Carry + Decay (T4+T8) → CALMem + CPP

**Our Issue**: Generic follow-ups lost sticky context; no decay mechanism.

**CALMem**: "Episodic memory (intra-session) + Semantic memory (cross-session). MOIM injector auto-retrieves relevant context."

**CPP**: "Segmentation (cosine δ) → dual-indexing → budgeted retrieval → evidence highlighting."

**Our Implementation**: Sticky carry for generic follow-ups + decay after 3 generic turns.

---

### Fix 6: Scattered Clarify Gate (T5) → RAC + ICR

**Our Issue**: 6/6 scattered queries failed to clarify.

**RAC**: "Retrieval-augmented clarification: retrieve top-k passages → LLM generates facet-grounded clarifying question."

**ICR**: "Iterative clarification-rewriting: c_i ∼ M(r_{i-1}), r_i ∼ M(c_i, H, r_{i-1}) until confident."

**Our Implementation**: `is_scattered_ambiguous(query)` detects vague terms without subspace keywords → forces clarify.

---

### Fix 7: Lexical Evidence Bypass (T6) → 5ting + AILS-NTUA

**Our Issue**: Rerank 0.0 but text relevant → abstained despite evidence.

**5ting**: "Corpus-specific rewrite preserves terminology gaps."

**AILS-NTUA**: "Corpus-specific rewriting addresses terminology gaps."

**Our Implementation**: `_has_lexical_evidence(query, chunks, subspace)` checks subspace keywords + query tokens in chunk content.

---

### Fix 8: Faith/Hall Guard (F) → DUTIR + Reflective RAG + 5ting

**Our Issue**: Weak-evidence answers hallucinated (hall 0.195 → 0.254).

**DUTIR**: "Confidence-based answerability gating minimizes hallucination."

**Reflective RAG**: "Reflection tagging → RL strategy optimization. Two-stage: SFT (reflection) → RL (strategy + dynamic KL)."

**5ting**: "Evidence-constrained generation + IDK-conditioned harmonic mean."

**Our Implementation**: Coverage+score guard on weak-evidence paths replaces answer with refusal.

---

### Fix 9: GPU KB (C) → SPLIT-RAG + H-RAG

**Our Issue**: Dense embed 2325ms on CPU dominated latency.

**SPLIT-RAG**: "Parallel subgraph retrieval on partitioned KG → efficiency."

**H-RAG**: "Hierarchical parent-child retrieval + GPU-friendly configuration."

**Our Implementation**: `KB_EMBED_DEVICE=cuda:0 KB_RERANKER_DEVICE=cuda:0 KB_RERANK_POOL=30`.

---

## Summary Table

| Fix | Papers | Key Mechanism | Our Code Location |
|-----|--------|---------------|-------------------|
| Map Fix | PC-RAG, SPLIT-RAG | Domain partitioning | `config.py:34` |
| T1 RRF Fusion | GUIR, Sifei, AILS-NTUA | RRF fusion (1.3x filtered) | `retrieve.py:143` |
| T2 Broaden | GUIR, Sifei | Multi-query fusion | `retrieve.py:220` |
| T3 Threshold | PC-RAG, DUTIR | Per-subspace evidence | `config.py:44` |
| T4 Sticky | CALMem, CPP | Episodic memory | `api.py:386` |
| T5 Clarify | RAC, ICR | Retrieval-grounded clarify | `infer_specification.py:24` |
| T6 Lexical | 5ting, AILS-NTUA | Corpus-specific rewrite | `format_response.py:279` |
| F Faith Guard | DUTIR, Reflective RAG, 5ting | Evidence constraint | `format_response.py:483` |
| C GPU KB | SPLIT-RAG, H-RAG | Parallel retrieval | `KB_EMBED_DEVICE=cuda:0` |

---

## Related Pages

- [Problems](../problems/index.html) — Root causes and fixes
- [Papers & Solutions](../papers/index.html) — Paper summaries
- [Architectures](../architectures.html) — Architecture diagrams
- [Our Implementation](../our-impl.html) — Code pointers and benchmarks