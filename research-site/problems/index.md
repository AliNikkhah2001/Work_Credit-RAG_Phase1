---
layout: default
title: "Problems - Multi-Turn RAG Research"
description: "Detailed breakdown of each multi-turn RAG problem: root cause, production impact, and our fixes"
---

<div class="page-header">
  <h1>Problems</h1>
  <p class="lead">Detailed breakdown of each multi-turn RAG problem with root cause analysis</p>
</div>

<div class="alert alert-info">
  <strong>Context:</strong> Production system serving Persian credit-scoring QA across 4 subspaces (cheque, facilities_person, facilities_legal, general) with 1123 chunks over 18 documents. Benchmark: 41 turns (12 multi-turn + 12 single) across 4 subspaces.
</div>

<div class="card-grid">
  <a href="{{ '/problems/subspace-filtering.html' | relative_url }}" class="card" style="text-decoration: none; color: inherit;">
    <h3>🔍 Subspace Filtering Failure</h3>
    <p class="meta"><strong>Impact:</strong> 0-chunk retrieval despite relevant content | <strong>Fix:</strong> Map correction + RRF fusion</p>
    <p>Static <code>subspace_map</code> had <code>"cheque": "چک"</code> but KB folders used <code>"گزارش اعتباراتنجی چک"</code>. The filter <code>"چک"</code> matched zero chunks because KB filter checks exact element membership in <code>folder_hierarchy</code>, not substring.</p>
    <div class="tags"><span class="tag primary">Root Cause</span><span class="tag">Map Mismatch</span><span class="tag">PC-RAG</span></div>
  </a>
  
  <a href="{{ '/problems/ambiguity-resolution.html' | relative_url }}" class="card" style="text-decoration: none; color: inherit;">
    <h3>❓ Ambiguity Resolution Failure</h3>
    <p class="meta"><strong>Impact:</strong> 6/6 scattered queries answered instead of clarifying | <strong>Fix:</strong> Retrieval-grounded clarification + iterative loop</p>
    <p>Queries like <code>"وضعیت اعتباری چطور است"</code> (credit status how is it) and <code>"بدهکار شدم چیکار کنم"</code> (I became debtor what to do) are scattered across subspaces. System answered <code>"پاسخی یافت نشد"</code> instead of clarifying with <code>"چک / تسهیلات / شرکت"</code> pills.</p>
    <div class="tags"><span class="tag primary">Root Cause</span><span class="tag">Keyword Gate</span><span class="tag">RAC</span></div>
  </a>
  
  <a href="{{ '/problems/sticky-context.html' | relative_url }}" class="card" style="text-decoration: none; color: inherit;">
    <h3>🔗 Sticky Context Decay</h3>
    <p class="meta"><strong>Impact:</strong> Context lost after 3-4 generic turns | <strong>Fix:</strong> Sticky carry + decay after 3 generic turns</p>
    <p>After explicit subspace selection <code>"چک"</code> → <code>applied_subspace=cheque</code>, follow-up <code>"تاثیر چک برگشتی..."</code> lost sticky (became <code>None</code>). Generic follow-ups like <code>"آیا درآمد..."</code> didn't carry <code>filter_path</code>.</p>
    <div class="tags"><span class="tag primary">Root Cause</span><span class="tag">Decay</span><span class="tag">CPP</span></div>
  </a>
  
  <a href="{{ '/problems/retrieval-degradation.html' | relative_url }}" class="card" style="text-decoration: none; color: inherit;">
    <h3>📉 Retrieval Degradation</h3>
    <p class="meta"><strong>Impact:</strong> Filtered retrieval = hard filter, no fallback | <strong>Fix:</strong> RRF fusion + broadened retry + GPU</p>
    <p>Filtered retrieval was treated as authoritative with NO fallback. When <code>filter_path</code> returned weak scores (<0.15), chunks cleared → abstention. No whole-KB fallback, no broadened params, no GPU.</p>
    <div class="tags"><span class="tag primary">Root Cause</span><span class="tag">No Fallback</span><span class="tag">GUIR</span></div>
  </a>
  
  <a href="{{ '/problems/hallucination.html' | relative_url }}" class="card" style="text-decoration: none; color: inherit;">
    <h3>🛡️ Hallucination Control</h3>
    <p class="meta"><strong>Impact:</strong> Weak-evidence answers hallucinated | <strong>Fix:</strong> Coverage+score guard + lexical bypass</p>
    <p>Answers on weak evidence (fallback/broadened paths) hallucinated. G5 fake grade was correctly refused, but other weak-evidence answers invented facts. Hallucination rate 0.195 → 0.254 (tradeoff for recall).</p>
    <div class="tags"><span class="tag primary">Root Cause</span><span class="tag">DUTIR</span><span class="tag">Faith Guard</span></div>
  </a>
  
  <a href="{{ '/problems/latency.html' | relative_url }}" class="card" style="text-decoration: none; color: inherit;">
    <h3>⚡ CPU Latency Bottleneck</h3>
    <p class="meta"><strong>Impact:</strong> Dense embed 2.3s dominated latency | <strong>Fix:</strong> GPU embed + rerank pool 30</p>
    <p>KB search: <code>dense 2325ms</code> (99.5% of search time). Rerank was <code>1.1ms</code> (not bottleneck!). GPU: <code>dense 19ms</code> (100×), <code>rerank 52ms</code> (real BGE-m3 scores), total <code>2333ms → 70ms</code>.</p>
    <div class="tags"><span class="tag primary">Root Cause</span><span class="tag">CPU Embed</span><span class="tag">GPU KB</span></div>
  </a>
</div>

---

## Problem Taxonomy

| # | Problem | Category | Severity | Status | Key Paper |
|---|---------|----------|----------|--------|-----------|
| 1 | Subspace map mismatch | Retrieval | Critical | ✅ Fixed | PC-RAG, SPLIT-RAG |
| 2 | No filtered fallback | Retrieval | Critical | ✅ Fixed | GUIR, 5ting |
| 3 | Global evidence threshold | Generation | High | ✅ Fixed | PC-RAG, DUTIR |
| 4 | Sticky decay | Context | High | ✅ Fixed | CPP, CALMem |
| 5 | No clarification gate | Safety | Critical | ✅ Fixed | RAC, ICR, Qulac |
| 6 | No retrieval fallback | Retrieval | Critical | ✅ Fixed | GUIR, 5ting |
| 7 | No per-subspace boost | Retrieval | Medium | ✅ Fixed | GUIR, SPLIT-RAG |
| 7 | No faith guard | Safety | Medium | ✅ Fixed | DUTIR, Reflective RAG |
| 8 | CPU-only embed | Performance | High | ✅ Fixed | SPLIT-RAG, GPU KB |
| 9 | No decay mechanism | Context | Medium | ✅ Fixed | CPP, CALMem |

---

## Root Cause Analysis Diagram

```mermaid
flowchart TD
    A[User Query] --> B{Subspace Map Match?}
    B -->|No Match| C[Zero Chunks Retrieved]
    B -->|Match| D[Filtered Retrieval]
    C --> E[Abstention: 'پاسخی یافت نشد']
    D --> F{Scores > Threshold?}
    F -->|No| G[Chunks Cleared]
    F -->|Yes| H[Build Context]
    G --> E
    H --> I{Generation}
    I --> J[Answer]
    I --> K[Hallucination?]
    K -->|Yes| L[Hallucinated Answer]
    K -->|No| J
    
    style C fill:#fef2f2,stroke:#ef4444
    style E fill:#fef2f2,stroke:#ef4444
    style G fill:#fef2f2,stroke:#ef4444
    style L fill:#fef2f2,stroke:#ef4444
    
    M[Fixes] --> N[T1: RRF Fusion]
    M --> O[T2: Broaden Retry]
    M --> P[T3: Per-Subspace Threshold]
    M --> Q[T4: Sticky Carry]
    M --> R[T5: Clarify Gate]
    M --> S[T6: Lexical Guard]
    M --> T[T7: Observability]
```

---

## Production Impact Quantification

| Metric | Before Fix | After Fix | Business Impact |
|--------|------------|-----------|-----------------|
| **Cheque hit rate** | 11.1% | 66.7% | 5x more cheque queries answered |
| **Clarification accuracy** | 0% (0/6) | 100% (6/6) | Users guided instead of dead ends |
| **Sticky persistence** | 61% | 68% | Fewer re-specifications needed |
| **Answer relevancy** | 21% | 57% | 2.7x more relevant answers |
| **p50 latency** | 8.0s | 4.9s | 39% faster responses |
| **KB search time** | 2.3s | 70ms | 33× faster retrieval |

---

## Next Steps

1. **Read individual problem pages** for deep technical details
2. **Explore Papers & Solutions** for academic backing
3. **Review Architectures** for implementation patterns
4. **Check Relevance Mapping** for direct fix-to-paper links
4. **Run Benchmarks** with `evaluation/bench_runner.py`