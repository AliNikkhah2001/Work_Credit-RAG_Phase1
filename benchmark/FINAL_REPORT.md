# FINAL REPORT — Massive Retrieval Benchmark & RAG Diagnostic
<!-- Status: DRAFT. Filled as evidence lands. -->

## Executive Summary
- **ROOT CAUSE:** `KB_KEYWORD_BOOST=3.0` score addition (`content + 3×keyword`,
  unnormalized scales) buries exact matches (verbatim query: content-BM25 #1/#2
  → combined #113/#118; keyword leg alone ranks them #2484/#760).
- **FIX:** _under test (boost ∈ {0, 1.0} ablation; rank-fusion alternative queued)_
- **BASELINE → FINAL:** _TBD_
- **DATASET:** `benchmark/datasets/eval_remapped.json` (796 Q/A, graded relevance)
- **BENCHMARK:** `benchmark/raw/massive_results.jsonl` (776 rows) + `raw_kb0` (ablation)
- **COMMIT:** _this branch_
- **REMAINING ISSUES:** dense leg weakness (hit@5 0.384); uncertain-primary half needs verbatim-suite validation

## System Architecture
BM25 (Okapi, Persian char-3-grams, content+keyword×3.0, synonym beam5) +
Dense (MiniLM-L12 384, pgvector/file) → RRF (k=60) → CrossEncoder
(`BAAI/bge-reranker-v2-m3`, pool=15, fusion α=0.7, pin protection) → top-k.

## Benchmark Methodology
- Dataset: eval_clean 800 → remapped to live 3330-chunk KB (coverage ≥0.6).
- 796 kept (4 empty-answer excluded); 20 zero-gold tracked separately.
- Metrics: Recall/Hit/NDCG @1,3,5,10,20,50,100 + MRR per stage; candidate recall; gain/loss.
- Validation: hand-computed unit tests + cross-check vs kb_manager impl.

## Baseline Results
_TBD (table)_

## Diagnostic Analysis
_TBD (gold positions, failure categories, candidate ceiling)_

## Root Cause
_TBD_

## Fixes
_TBD (hypothesis → experiment → before/after)_

## Before/After
_TBD_

## Hard Negative Dataset
_TBD (`benchmark/datasets/retrieval_pairs_*.jsonl`, stats)_

## Remaining Problems
_TBD_
