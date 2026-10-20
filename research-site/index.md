---
layout: default
title: "Overview"
description: "Comprehensive research on multi-turn RAG challenges: subspace filtering, ambiguity resolution, sticky context, and their 2025-2026 state-of-the-art solutions from ACL, EMNLP, SIGIR, SIGDIAL, SemEval, NeurIPS, ICML"
---

<div class="page-header">
  <h1>Multi-Turn RAG Research</h1>
  <p class="lead">Problems, Solutions & State-of-the-Art (2025-2026)</p>
</div>

<div class="alert alert-info">
  <strong>Status:</strong> Active Research — Last updated {{ site.time | date: "%B %d, %Y" }} · Based on 40+ papers from ACL 2025, EMNLP 2025, SIGIR 2024/2025, SIGDIAL 2025/2026, SemEval 2026, NeurIPS 2025, ICML 2025, ICML 2024
</div>

## Executive Summary

This research documents the **five core problems** we encountered in our production multi-turn RAG system (Work Credit RAG Phase 1) and maps each to **2025-2026 state-of-the-art solutions** from top-tier venues (ACL 2025, EMNLP 2025, SIGIR 2024/2025, SIGDIAL 2025/2026, SemEval 2026, NeurIPS 2025, ICML 2025).

Our production system serves Persian credit-scoring QA across **4 subspaces** (cheque, facilities_person, facilities_legal, general) with **1123 chunks** over **18 documents**. We ran a **41-turn multi-agent benchmark** (12 multi-turn conversations + 12 single-turn baselines) that revealed critical degradation patterns in multi-turn scenarios.

<div class="card-grid">
  <div class="card">
    <h3>🔍 Subspace Filtering</h3>
    <p>Static <code>subspace_map</code> mismatch caused 0-chunk retrieval despite relevant content existing. Fixed: map correction + RRF fusion.</p>
    <div class="meta">Hit: 0.111 → 0.667 (+499%)</div>
    <div class="tags"><span class="tag primary">Fixed</span><span class="tag">PC-RAG</span><span class="tag">SPLIT-RAG</span></div>
    <a href="{{ '/problems/subspace-filtering.html' | relative_url }}" class="tag" style="margin-top: var(--spacing-md); display: inline-block;">Details →</a>
  </div>
  
  <div class="card">
    <h3>❓ Ambiguity Resolution</h3>
    <p>6/6 scattered queries failed to clarify. Fixed: retrieval-grounded clarification gate + iterative rewrite loop.</p>
    <div class="meta">Ambiguity: 0.854 → 1.000 (6/6)</div>
    <div class="tags"><span class="tag primary">Fixed</span><span class="tag">RAC</span><span class="tag">ICR</span></div>
    <a href="{{ '/problems/ambiguity-resolution.html' | relative_url }}" class="tag" style="margin-top: var(--spacing-md); display: inline-block;">Details →</a>
  </div>
  
  <div class="card">
    <h3>🔗 Sticky Context</h3>
    <p>Context lost after 3-4 generic turns. Fixed: sticky carry + decay after 3 generic turns + semantic segmentation.</p>
    <div class="meta">Sticky: 0.610 → 0.683</div>
    <div class="tags"><span class="tag primary">Fixed</span><span class="tag">CPP</span><span class="tag">CALMem</span></div>
    <a href="{{ '/problems/sticky-context.html' | relative_url }}" class="tag" style="margin-top: var(--spacing-md); display: inline-block;">Details →</a>
  </div>
  
  <div class="card">
    <h3>📉 Retrieval Degradation</h3>
    <p>Filtered retrieval had no fallback. Fixed: RRF fusion (filtered + whole-KB) + broadened retry + GPU acceleration.</p>
    <div class="meta">Hit: 0.537 → 0.780; Latency 8s → 4.9s</div>
    <div class="tags"><span class="tag primary">Fixed</span><span class="tag">GUIR</span><span class="tag">GPU KB</span></div>
    <a href="{{ '/problems/retrieval-degradation.html' | relative_url }}" class="tag" style="margin-top: var(--spacing-md); display: inline-block;">Details →</a>
  </div>
  
  <div class="card">
    <h3>🛡️ Hallucination Control</h3>
    <p>Weak-evidence answers hallucinated. Fixed: coverage+score guard + lexical evidence bypass + per-subspace thresholds.</p>
    <div class="meta">Hallucination: 0.195 → 0.254 (tradeoff for recall)</div>
    <div class="tags"><span class="tag primary">Improved</span><span class="tag">Faith Guard</span><span class="tag">DUTIR</span></div>
    <a href="{{ '/problems/hallucination.html' | relative_url }}" class="tag" style="margin-top: var(--spacing-md); display: inline-block;">Details →</a>
  </div>
  
  <div class="card">
    <h3>⚡ Latency & Scale</h3>
    <p>CPU KB search dominated (2.3s). Fixed: GPU embed + rerank pool 30 = 100× speedup.</p>
    <div class="meta">Dense: 2325ms → 19ms (100×)</div>
    <div class="tags"><span class="tag primary">Fixed</span><span class="tag">GPU KB</span><span class="tag">BGE-m3</span></div>
    <a href="{{ '/problems/latency.html' | relative_url }}" class="tag" style="margin-top: var(--spacing-md); display: inline-block;">Details →</a>
  </div>
</div>

---

## Quick Navigation

<div class="card-grid">
  <a href="{{ '/problems/index.html' | relative_url }}" class="card" style="text-decoration:none;color:inherit">
    <h3>📋 All Problems</h3>
    <p>Detailed breakdown of each problem with root cause analysis, production impact, and our fixes.</p>
  </a>
  <a href="{{ '/papers/index.html' | relative_url }}" class="card" style="text-decoration:none;color:inherit">
    <h3>📚 Papers &amp; Solutions</h3>
    <p>40+ papers from ACL 2025, EMNLP 2025, SIGIR 2024/25, SIGDIAL 2025/26, SemEval 2026, NeurIPS 2025, ICML 2025.</p>
  </a>
  <a href="{{ '/architectures.html' | relative_url }}" class="card" style="text-decoration:none;color:inherit">
    <h3>🏗️ Architectures</h3>
    <p>Mermaid diagrams of paper architectures: SPLIT-RAG, PC-RAG, RAC, ICR, CPP, CALMem, H-RAG, 5ting, GUIR, DUTIR.</p>
  </a>
  <a href="{{ '/relevance.html' | relative_url }}" class="card" style="text-decoration:none;color:inherit">
    <h3>🔗 Relevance Mapping</h3>
    <p>Detailed table mapping each of our fixes to the specific paper, section, and mechanism that validates it.</p>
  </a>
  <a href="{{ '/benchmarks.html' | relative_url }}" class="card" style="text-decoration:none;color:inherit">
    <h3>📊 Benchmarks</h3>
    <p>MTRAG (842 turns), MTRAGEval (SemEval 2026), CORAL, RAD-Bench. Our 41-turn benchmark results with RAGAS.</p>
  </a>
  <a href="{{ '/our-impl.html' | relative_url }}" class="card" style="text-decoration:none;color:inherit">
    <h3>⚙️ Our Implementation</h3>
    <p>T1-T8 fixes, code pointers, benchmark deltas, deployment notes, and remaining gaps.</p>
  </a>
</div>

---

## Key Metrics: Before vs After

| Metric | Before (2026-10-12) | After (2026-10-14) | Δ |
|--------|---------------------|--------------------|---|
| **Finish mismatches** | 6/41 | **0/41** | -6 |
| **Retrieval hit** | 0.537 | **0.780** | **+0.243** |
| **Cheque hit** | 0.111 | **0.667** | **+0.556** |
| **Context recall** | 0.113 | **0.340** | **+0.227** |
| **Answer relevancy** | 0.212 | **0.568** | **+0.356** |
| **Ambiguity resolution** | 0.854 (0/6) | **1.000** (6/6) | +0.146 |
| **Sticky persistence** | 0.610 | **0.683** | +0.073 |
| **p50 latency** | 8006ms | **4872ms** | **-39%** |
| **KB dense embed** | 2325ms | **19ms** | **100×** |

---

## Repository & Artifacts

| Artifact | Location |
|----------|----------|
| **Parent Repo** | [Work_Credit-RAG_Phase1](https://github.com/AliNikkhah2001/Work_Credit-RAG_Phase1) |
| **Orchestrator** | [Work_RAG-Orchestrator](https://github.com/AliNikkhah2001/Work_RAG-Orchestrator) |
| **KB Manager** | [Work_RAG-KB](https://github.com/AliNikkhah2001/Work_RAG-KB) |
| **Bench Report** | [benchmark-report-2026-10-12.md](../benchmark-report-2026-10-12.md) |
| **Bench Artifacts** | `evaluation/artifacts/` (bench_results, ragas_results, HTML report) |
| **Git Commits** | Parent `b1d9148`, Orchestrator `56048fc`, KB `6ad47c6` |

---

## Citation

If you use this research, please cite:

```bibtex
@misc{work-credit-rag-2026,
  title = {Multi-Turn RAG Research: Problems, Solutions \& State-of-the-Art (2025-2026)},
  author = {Work Credit RAG Team},
  year = {2026},
  url = {https://github.com/AliNikkhah2001/Work_Credit-RAG_Phase1},
  note = {Based on 40+ papers from ACL 2025, EMNLP 2025, SIGIR 2024/25, SIGDIAL 2025/26, SemEval 2026, NeurIPS 2025, ICML 2025}
}
```