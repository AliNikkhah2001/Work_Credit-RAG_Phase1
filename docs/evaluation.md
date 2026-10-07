# Evaluation — Work Credit RAG Phase 1

> All evaluations are self-hosted, reproducible, and versioned with the KB.
> **Canonical:** `eval/README.md` + `eval/FINDINGS.md` + `README.md#evaluation` — this file is a pointer.

## Quick Links

| Report | Location | Content |
|--------|----------|---------|
| **Retrieval quality (v5-v8)** | `eval/README.md` §1 | Hit@5, MRR, latency per variant (verbatim/paraphrase/typo/keyword_only) |
| **RAG E2E (120 Q)** | `eval/FINDINGS.md` | Guardrail blocks, citations, finish reasons |
| **LLM-as-Judge (v4)** | `README.md#evaluation` | Cosine 0.620, pass 45%, faithfulness 3.65 |
| **Reranker shootout (800 Q)** | `README.md#evaluation` + `docs/cross_encoder_benchmark_results.md` | BGE-m3 MRR 0.496 vs MiniLM 0.493, latency s/q |
| **Full metrics** | `eval/results/` (canonical) + `archive/benchmark-history/` (archived GH Pages) | JSON + plots |

## Reproduction

```bash
python eval/run_llm_answer_benchmark.py --out eval/results/llm_answer_benchmark_v4.json
python eval/run_llm_judge.py eval/results/llm_answer_benchmark_v4.json --out eval/results/llm_judge_v4.json
python eval/make_plots.py
python eval/build_report_site.py  # generates docs/benchmark-report/ (gitignored; see archive/benchmark-history/)
```

> **Note on `docs/benchmark-report/`**: The HTML report directory `docs/benchmark-report/` is generated at runtime by `eval/build_report_site.py` and is gitignored. Historical benchmark reports may be found in `archive/benchmark-history/`.

## Archive

Historical per-version tables (v5 baseline, v7 IVA 15, v8 HNSW) were moved to `archive/migration-history/` and `eval/results/`. See `README.md#evaluation` for the current verified numbers.
