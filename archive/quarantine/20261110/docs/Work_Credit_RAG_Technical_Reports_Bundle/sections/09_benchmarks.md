# Benchmarks and latency appendix

## Section summary

Observed numbers frame how the stack performs. The headline comparison is the 41-turn multi-agent bench (12 October 2026 → 14 October 2026): finish-reason mismatches fell from 6/41 to 0/41, retrieval hit rose from 0.537 to 0.780, and p50 latency fell 39% from 8006 ms to 4872 ms. Published knowledge-base quality on the frozen v11 export is **Hit@5 0.9306**. The current corpus is v13 (`1405-07-06`), and warm hybrid search stays near **55 ms**. End-to-end chat latency is led by guarded generation on Gemma.

## Knowledge-base IR quality

**Sources:** KB pages corpus table; `components/knowledgebase/kb-manager/artifacts/retrieval_training/report_metrics.json` (`hit5_rate` 0.9306, `mrr` 0.8281, `N` 663). The pages also describe a frozen 120-query, six-format set that carries the same v11 Hit@5. The checked-in rate is the 663-query export. v13 (`1405-07-06`, 18 documents / 1,123 chunks) is the RAM-first corpus whose warm latency is reported below.

| Snapshot | Corpus | Hit@5 | MRR |
|---|---|---:|---:|
| v11 | 35 docs / 2,227 chunks; `dense use_context=False` | **0.9306** | 0.8281 |

## Knowledge-base stage latency (ms)

**Source:** `artifacts/retrieval_training/latency_v13_1.json`

| Stage | README v13 (10-07) | Before tune (10-13) | After tune (10-13) |
|---|---:|---:|---:|
| BM25 | 4.0 | 3.8 | 2.6 |
| Dense | 24.0 | 20.5 | 13.5 |
| Rerank | 24.0 | 20.9 | 22.0 |
| **Total** | **55.0** | **44.4** | **39.6** |

The v13 README figure of **55.0 ms** is the warm-search number to quote for the RAM-first stack (~55 ms). The 13 October tune later measured 39.6 ms p50 on 30 fresh queries; both describe retrieval, not chat. Cold starts remain multi-second when models and indexes load. Redis cache hits for identical queries fall to the low single-digit milliseconds once warm.

![KB latency RAM/tantivy plot](../assets/plots/latency_breakdown_ram_tantivy.png)

**Figure B1. KB latency breakdown (RAM / tantivy era).** The plot visualizes how lexical and dense legs plus rerank compose wall time after memory-resident indexes replaced slower disk-bound paths. Read it with the table above: the README warm total is about 55 ms, and the 13 October tune sits under 50 ms. Either figure is retrieval time, not chat generation.

## End-to-end orchestrator bench (41 turns)

**Source:** parent pages `docs/papers/benchmarks.html` (before 2026-10-12 → after 2026-10-14). Reproduce with `evaluation.bench_runner` → `evaluation.ragas_eval` → `evaluation.report`, which writes `bench_report_latest`. The after column’s overall p50 (4872 ms) matches that artifact’s headline; the before column and the per-metric deltas below are the published comparison, not a re-fit.

| Metric | Before (2026-10-12) | After (2026-10-14) | Δ |
|---|---:|---:|---|
| Finish mismatches | 6/41 | 0/41 | −6 |
| Retrieval hit | 0.537 | 0.780 | +0.243 |
| Cheque hit | 0.111 | 0.667 | +0.556 |
| Context recall | 0.113 | 0.340 | +0.227 |
| Answer relevancy | 0.212 | 0.568 | +0.356 |
| Ambiguity resolution | 0.854 | 1.000 | +0.146 |
| Sticky persistence | 0.610 | 0.683 | +0.073 |
| p50 latency | 8006 ms | 4872 ms | **−39%** |

The same after cut, by subspace:

| Subspace | n | Hit | Faith | Sticky | p50 |
|---|---:|---:|---:|---:|---:|
| Cheque | 9 | 0.667 | 0.422 | 0.444 | 10301 ms |
| Facilities person | 6 | 0.500 | 0.967 | 0.667 | 10718 ms |
| Facilities legal | 3 | 0.667 | 0.917 | 0.333 | 10498 ms |
| General | 10 | 0.800 | 0.655 | 0.600 | 6981 ms |

`bench_report_latest` (41 turns, 12 conversations, model `ics-helper-agent`, 2026-10-14) adds figures the delta table does not carry: average latency **4938 ms**, transport error rate **0%**, faithfulness **0.461**, context relevancy **0.283**, hallucination inverted **0.746**. Where a per-subspace p50 in an earlier export disagrees with the table above, the benchmarks page is the comparison this report uses.

Generation through guardrails accounts for most of the multi-second p50; warm KB search (~55 ms, and 39.6 ms after the 13 October tune) is two orders of magnitude smaller. The −39% p50 move (8006 → 4872) places chat near five seconds. Throughput work centers on TRT-LLM on the H200, prompt and entity trimming, and the clarify path, beside the warm BM25 leg.

## Model serving concurrency (H200)

**Source:** `components/server-setup/docs/history/013_2026-10-13_trtllm_champion_concurrency.md` (as summarized in ops notes)

| Backend | Approx. aggregate throughput | Notes |
|---|---|---|
| llama.cpp Q4 Gemma pool | ~58 tok/s class | Multi-process supervisor |
| TRT-LLM BF16 champion | ~3874 tok/s @ concurrency 128 | Large aggregate gain vs llama.cpp |

Exact reproduction depends on engine build and GPU partitioning. The ratio (~67× aggregate in that experiment) is the published evidence that **scale-up on the H200 prefers TRT-LLM for generation**, with the llama.cpp pool on `8080–8084` as the resilience path.
