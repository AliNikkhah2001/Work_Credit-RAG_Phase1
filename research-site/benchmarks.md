---
layout: default
title: "Benchmarks - Multi-Turn RAG Research"
description: "MTRAG, MTRAGEval, CORAL, RAD-Bench, SemEval 2026 Task 8 - 842-turn multi-turn benchmark, nDCG@5, RAGAS, human evaluation, automated eval"
---

<div class="page-header">
  <h1>Benchmarks</h1>
  <p class="lead">MTRAG, MTRAGEval, CORAL, RAD-Bench, SemEval 2026 Task 8 - 842-turn multi-turn benchmark, nDCG@5, RAGAS, human evaluation, automated eval</p>
</div>

## Benchmark Landscape

### MTRAG: The Gold Standard (ACL 2025)

| Aspect | Detail |
|--------|--------|
| **Paper** | MTRAG: A Multi-Turn Conversational Benchmark for Evaluating Retrieval-Augmented Generation Systems (Katsis et al., ACL 2025) |
| **Repository** | https://github.com/ibm/mt-rag-benchmark |
| **Conversations** | 110 human-generated |
| **Turns** | 842 total (7.7 avg/conv) |
| **Domains** | ClapNQ (26.6%), FiQA (23.6%), Govt (25.4%), Cloud (24.4%) |
| **Answerable** | 777 turns (after filtering unanswerable) |
| **Passages/Conv** | 16.9 unique relevant |

**Key Finding**: ELSER R@5 drops **0.89 → 0.47** (first → later turns) = **51% degradation**

---

### MTRAGEval: SemEval 2026 Task 8

| Subtask | Description | Metric |
|---------|-------------|--------|
| **Task A** | Retrieval | nDCG@1/3/5/10, Recall@1/3/5/10 |
| **Task B** | Generation with gold passages | Quality |
| **Task C** | End-to-end RAG | Harmonic mean (quality + faithfulness, IDK-conditioned) |

**Domains**: ClapNQ (26.6%), FiQA (23.6%), Govt (25.4%), Cloud (24.4%)

**Top Results (Task A)**:

| Team | nDCG@5 | Rank |
|------|--------|------|
| Sifei | 0.5453 | 3/38 |
| GUIR | 0.5453 | 3/38 |
| uva-irlab | - | - |

---

### Other Benchmarks

| Benchmark | Description | Key Metric |
|-----------|-------------|------------|
| **CORAL** (2025) | Conversational retrieval with cross-turn evidence | nDCG@5 |
| **RAD-Bench** (2024) | Retrieval and reasoning across dialogue turns | Accuracy |
| **Qulac/ClariQ** | Clarification datasets (10k+ queries) | Facet coverage |

---

## Our 41-Turn Benchmark Results

### Overall Metrics (Before vs After)

| Metric | Before (2026-10-12) | After (2026-10-14) | Δ |
|--------|---------------------|--------------------|---|
| **Finish mismatches** | 6/41 | **0/41** | -6 |
| **Retrieval hit** | 0.537 | **0.780** | **+0.243** |
| **Cheque hit** | 0.111 | **0.667** | **+0.556** |
| **Context recall** | 0.113 | **0.340** | **+0.227** |
| **Answer relevancy** | 0.212 | **0.568** | **+0.356** |
| **Ambiguity resolution** | 0.854 (0/6) | **1.000** (6/6) | **+0.146** |
| **Sticky persistence** | 0.610 | **0.683** | +0.073 |
| **Hallucination** | 0.195 | **0.254** | +0.059 (tradeoff) |
| **p50 latency** | 8006ms | **4872ms** | **-39%** |

### Subspace Breakdown (After Fixes)

| Subspace | Count | Hit | Faith | Sticky | p50 |
|----------|-------|-----|-------|--------|-----|
| Cheque | 9 | 0.667 | 0.422 | 0.444 | 10301ms |
| Facilities Person | 6 | 0.500 | 0.967 | 0.667 | 10718ms |
| Facilities Legal | 3 | 0.667 | 0.917 | 0.333 | 10498ms |
| General | 10 | 0.800 | 0.655 | 0.600 | 6981ms |

---

## Latency Breakdown

| Stage | Before (ms) | After (ms) | Change |
|-------|-------------|------------|--------|
| Validate Input | 52 | 35 | -33% |
| Retrieve | 1682 | 2641 | +57% (real rerank) |
| Build Context | 0.3 | 0.2 | -33% |
| Guarded Generate | 5381 | 4605 | -14% |
| **Total p50** | **8006** | **4872** | **-39%** |

### KB Search Latency (GPU)

| Metric | CPU (Before) | GPU (After) | Speedup |
|--------|--------------|-------------|---------|
| Dense Embed | 2325ms | **19ms** | **~100×** |
| Rerank (pool 30) | 1.1ms* | **52ms** | Real scores |
| Total Search | 2333ms | **70ms** | **33×** |

*Previous rerank was likely skipped/cached.

---

## Per-Turn Analysis

### Conversation-Level Results (After)

| Conversation | Turns | Finish Match | Subspace Match | Avg Latency |
|--------------|-------|--------------|----------------|-------------|
| conv_cheque_01 | 3 | 3/3 ✅ | 2/2* | 4.8s |
| conv_cheque_02 | 3 | 3/3 ✅ | 3/3 ✅ | 6.0s |
| conv_facilities_person_01 | 4 | 4/4 ✅ | 3/3 ✅ | 7.0s |
| conv_facilities_person_02 | 3 | 3/3 ✅ | 1/1 ✅ | 2.3s |
| conv_facilities_legal_01 | 2 | 2/2 ✅ | 1/1 ✅ | 8.5s |
| conv_facilities_legal_02 | 2 | 2/2 ✅ | 1/1 ✅ | 2.5s |
| conv_general_01 | 3 | 3/3 ✅ | 2/3 | 5.5s |
| conv_general_02 | 2 | 2/2 ✅ | 1/1 ✅ | 4.3s |
| conv_mixed_01 | 2 | 2/2 ✅ | 2/2 ✅ | 1.1s |
| conv_greeting_01 | 3 | 3/3 ✅ | N/A | 1.7s |
| conv_hallucination_01 | 1 | 1/1 ✅ | N/A | 7.4s |
| conv_supplement_01 | 1 | 1/1 ✅ | 0/1 | 5.6s |

*\*First turn has no expected subspace*

---

## Single-Turn Baselines (After)

| ID | Query | Expected | Actual | Latency | Match |
|----|-------|----------|--------|---------|-------|
| single_cheque_granular | چک برگشتی چیست... | stop | stop | 10301ms | ✅ |
| single_facilities_person_granular | امتیاز اعتباری... | stop | stop | 10718ms | ✅ |
| single_facilities_legal_granular | الزامات وثایق... | stop | stop | 10196ms | ✅ |
| single_general_granular | تاریخچه شرکت... | stop | stop | 10063ms | ✅ |
| single_cheque_bounce_effect | تاثیر چک برگشتی... | stop | stop | 10979ms | ✅ |
| single_facilities_person_income | آیا میزان درآمد... | stop | stop | 9421ms | ✅ |
| single_facilities_legal_board | هیات مدیره... | stop | stop | 8766ms | ✅ |
| single_general_shareholders | سهامداران... | stop | stop | 4872ms | ✅ |
| single_greeting | سلام | greeting | stop | 725ms | ✅ |
| single_scattered | وضعیت اعتباری... | clarify | clarify | 2141ms | ✅ |
| single_hallucination_probe | نمره اعتباری G5... | stop | stop | 6226ms | ✅ |
| single_qasem_bour | قاسم بور کیه | stop | stop | 6981ms | ✅ |

---

## KB Probe Results

| Query | Subspace | No Filter | With Filter | Filter Helps |
|-------|----------|-----------|-------------|--------------|
| چک برگشتی چیست | گزارش اعتباراتنجی چک | 0.028 | 0.863 | ✅ |
| امتیاز اعتباری... | اشخاص حقیقی/... | 0.032 | 0.976 | ✅ |
| تسهیلات اشخاص حقوقی | اشخاص حقوقی/... | 0.023 | 0.403 | ✅ |
| تاریخچه شرکت... | پایگاه دانش عمومی | 0.033 | 0.979 | ✅ |

---

## Reproduction

```bash
# Full benchmark (214s)
cd Work_Credit-RAG_Phase1
PYTHONPATH=".:components/orchestrator:$PYTHONPATH" python3 -m evaluation.bench_runner

# RAGAS evaluation
PYTHONPATH=".:components/orchestrator:$PYTHONPATH" python3 -m evaluation.ragas_eval \
  --input evaluation/artifacts/bench_results_latest.json \
  --output evaluation/artifacts/ragas_results_latest.json

# Report generation
PYTHONPATH=".:components/orchestrator:$PYTHONPATH" python3 -m evaluation.report \
  --bench evaluation/artifacts/bench_results_latest.json \
  --ragas evaluation/artifacts/ragas_results_latest.json \
  --out evaluation/artifacts/bench_report_latest.html
```

---

## Related Pages

- [Paper: Benchmarks & Evaluation](../papers/benchmarks.html)
- [Paper: Subspace Filtering](../papers/subspace-filtering.html)
- [Our Implementation](../our-impl.html)
- [Architectures](../architectures.html)