# Evaluation — Work Credit RAG Phase 1

> All evaluations are self-hosted, reproducible, and versioned with the KB.

---

## 1. KB Retrieval Evaluation

### v5 — Baseline (120 queries, 6208 chunks, `aa5c576`)

| Format | Hit@5 | Top-1 | MRR | Avg Latency |
|--------|-------|-------|-----|-------------|
| verbatim | 95.0% | 80.0% | 0.867 | 3.3s |
| paraphrase | 90.0% | 80.0% | 0.842 | 3.6s |
| typo | 95.0% | 90.0% | 0.917 | 3.3s |
| reworded | 75.0% | 70.0% | 0.725 | 3.6s |
| conversational | 85.0% | 75.0% | 0.792 | 7.5s |
| keyword_only | 65.0% | 15.0% | 0.367 | 3.5s |
| **Overall** | **84.2%** | **68.3%** | **0.751** | **4.2s** |

**Dataset:** `data/test_questions.json` (20 topics × 6 formats)
**Gold:** `expected_chunk_ids` per question

---

### v7 — IVA 15 Questions (1405-05-31 KB, verbatim, CPU)

| Metric | Doc-level | Answer-grounded (≥70% tokens in top-5) |
|--------|-----------|---------------------------------------|
| Hit@5 | **11/15 (73.3%)** | 3/15 (20%) |
| MRR | 0.466 | — |
| Avg Latency | ~22.7s | — |

**Misses:** Q11/Q12 (reason-code "guaranteed loan"), Q14 (rank-vs-score), Q15 (negative-contract details)
**Root cause:** Golden chunks in RRF pool but cross-encoder demotes them
**Remediation:** `RERANKER_TOP_K 50→100` or per-domain rerank

---

### v8 — HNSW pgvector (6593 chunks, RTX 6000 Ada)

| Variant | Device | HNSW | Avg Latency | p95 | Hit@5 (5q verbatim) | Rerank 50 | Dense 10 |
|---------|--------|------|-------------|-----|---------------------|-----------|----------|
| File-based before | CPU | file `npz` | ~22.7s | ~34s | 0.00* | 439ms | 144ms |
| **HNSW pgvector CPU** | CPU | `m16` `13ms` | **23.1s** | 34.8s | 0.00 | 439ms | 144ms |
| **HNSW pgvector GPU** | **cuda:0** | `m16` `13ms` | **18.4s** | 28.8s | 0.00 | **279ms 1.6×** | **180ms 0.8×** |
| **Speedup GPU vs CPU** | — | — | **1.3×** | — | — | 1.6× | — |

*Hit 0/5 on 5q verbatim after re-ingest (mismatched expected IDs after Persian fix). IVA 15 still 73.3% baseline.

**Bottleneck:** Cross-encoder 50-pool (CPU 439ms → GPU 279ms). HNSW 13ms vs file dense ~5ms similar.
**On H200:** expect ~4s (v5-era baseline).

---

## 2. RAG End-to-End Evaluation

### Dataset
- **Source:** `components/knowledgebase/kb-manager/data/test_questions.json` (120 questions)
- **Ground truth:** `expected_answer`, `expected_chunk_ids`, `keywords`, `category`, `difficulty`
- **Updated:** `b1bb648` (v7 KB)

### Method (per question)
1. Guardrails input check: `POST /v1/rails/check {stage:"input", text}`
2. RAG call: `POST /v1/chat/completions` on orchestrator :8100 (model `gemma-4-31b`, temp 0, max_tokens 500)
3. Check: `has_unused` (`<unused`), `is_english` (`The provided context...`), `is_fallback` (`متأسفم، مدل...`), `finish_reason`, `citations`
4. Tag: `ok` if `finish==stop && citations>0 && !has_unused && !is_english && !is_fallback && !blocked`
5. Derivation: `citation_hit` if any `citations` chunk_id in `expected_chunk_ids`

### Results (2026-09-02, after fixes)

| Sample Set | OK | Guardrail Blocked | English Fallback | No Citations | Other |
|------------|-----|-------------------|------------------|--------------|-------|
| **20 diverse** | **20/20** | 0 | 0 | 0 | 0 |
| **120 input check** | **0/120 blocked** | — | — | — | — |
| **120 output check** | **0/120 blocked** | — | — | — | — |

### Before Fix (for comparison)
| Failure Type | Count | Example |
|--------------|-------|---------|
| `hate:حذف` | 1 | `چگونه می‌توانم گزارش اعتباری خود را دریافت کنم؟` (KB context `درخواست حذف`) |
| `hate:مهم` | 1 | `جدول نوع تماس` (KB chunk `مهم است`) |
| `profanity:ان` | 1 | `تفاوت شرکت...` (KB chunk `اثر ان را`) |
| `hate:ضعیف` | 6 | Expected answers with `رتبه اعتباری ضعیف` |

### After Fix
- HurtLex allowlist: **19 lemmas** (was 11 in eval README, 15 in root README)
- Profanity: `len(w)>2` (fixes `ان` len 2)
- Tests: 26 in `test_hurtlex_allowlist.py` + 6 in `test_input_rails.py` + 9 orchestrator = 41
- 6 user samples + 6 credit samples: all `stop`, 5 citations, Persian only

---

## 3. LLM-as-Judge Evaluation

### Method
- 120 questions → agent answers → Gemma judges (question + ground truth + agent answer)
- Scores 1–5: faithfulness, correctness, tone, citation + pass/fail
- Three parallel analysis agents: faithfulness, citations/tone, wording robustness

### Results (120 questions, 0 errors)

| Metric | v2 Q4 pre-tweak | v3 Q4 tweaked prompt | v4 Q8 tweaked prompt |
|--------|-----------------|----------------------|----------------------|
| Mean similarity | 0.602 | 0.621 | 0.620 |
| Median similarity | 0.685 | 0.691 | 0.675 |
| Sim > 0.5 | 76% | 79% | 78% |
| Sim > 0.7 | 43% | 44% | 43% |
| Mean / Max citations | 1.44 / 2 | 1.62 / 2 | 1.62 / 2 |
| Answers citing ≤ 2 | 100% | 100% | 100% |
| Finish `stop` | 120/120 | 120/120 | 120/120 |
| Judge pass rate | 49% | 47% | 45% |
| Faithfulness | 4.08 | 3.77 | 3.65 |
| Correctness | 3.21 | 3.24 | 3.14 |
| Tone | 4.86 | 4.83 | 4.90 |
| Citation | 4.98 | 4.94 | 4.95 |

### Key Findings
1. **False abstention** dominant (~18% pre-tweak): `پاسخی یافت نشد` despite 5 retrieved chunks
2. **No polarity flips** — failures are omission, not inversion
3. **Citations:** 100% cite ≤ 2; only chunks actually referenced `[n]` in text
4. **Tone:** Persian-only, professional, intro + 1–3 points + closing
5. **Wording robustness:** `reworded` weakest (mean ~0.55), `keyword_only` strongest (~0.65)
6. **Guardrails:** 2 FPs fixed (profanity:کردن, hate:پلیس); 0/120 blocked after
7. **Q8 vs Q4:** No measurable difference (0.621 → 0.620) — pipeline is retrieval-bound
8. **Memory:** Agent is **stateless** — verified `اسم من علی است…` → `اسم من چیست؟` → `پاسخی یافت نشد`

### Reproduction
```bash
# Benchmark agent answers
python eval/run_llm_answer_benchmark.py --out eval/results/llm_answer_benchmark_v4.json

# LLM judge
python eval/run_llm_judge.py eval/results/llm_answer_benchmark_v4.json --out eval/results/llm_judge_v4.json

# Plots
python eval/make_plots.py eval/results/llm_answer_benchmark_v4.json eval/results/llm_judge_v4.json --out eval/results/plots/

# Report site (GitHub Pages)
python eval/build_report_site.py
```

---

## 4. Benchmark Scripts Inventory

| Script | LOC | Purpose |
|--------|-----|---------|
| `eval/run_llm_answer_benchmark.py` | — | 120 questions → agent → cosine similarity + citations |
| `eval/run_llm_judge.py` | — | Gemma judges answers (faithfulness/correctness/tone/citation) |
| `eval/make_plots.py` | — | Histograms, wording robustness, citations, v3-vs-v4 |
| `eval/build_report_site.py` | — | GitHub Pages site from results |
| `components/knowledgebase/kb-manager/kb_manager/evaluation/benchmark.py` | — | KB retrieval benchmark runner |
| `components/knowledgebase/kb-manager/kb_manager/evaluation/metrics.py` | — | IR metrics (ranx + pure-Python fallback) |
| `components/knowledgebase/kb-manager/kb_manager/evaluation/query_formats.py` | — | 6 query format transformations |
| `components/knowledgebase/kb-manager/scripts/cleanup_incomplete_qa.py` | — | CLI cleanup tool |
| `components/server-setup/scripts/eval_persian.py` | 17433 | Persian 7-task eval harness |
| `components/server-setup/scripts/bench_speed.py` | 3183 | tok/s benchmark |
| `components/server-setup/scripts/gen_eval_report.py` | 41428 | Rebuild 10 PNG + Plotly + report |

---

## 5. Evaluation Datasets

| Dataset | Questions | Source | Formats | Gold |
|---------|-----------|--------|---------|------|
| `test_questions.json` | 120 | KB Manager | 6 × 20 | `expected_answer`, `expected_chunk_ids` |
| `eval_clean.json` | 800 | KB Manager v8 | — | `expected_chunk_ids` |
| `TestQuestions_IVA/InitialTestQuestion.xlsx` | 15 | KB Source | verbatim | Doc-level (golden document) |
| Persian 7-task | 350 (50×7) | HF datasets (ParsBench, MatinaAI) | — | Exact match / Jaccard |
| MMLU/GSM8K | — | HF datasets | — | Exact match |

---

## 6. Metrics Definitions

| Metric | Definition |
|--------|------------|
| **Hit@K** | Fraction of queries where ≥1 gold chunk in top-K |
| **MRR** | Mean Reciprocal Rank of first gold chunk |
| **Cosine Similarity** | Embedding cosine sim (agent answer vs ground truth) using KB embedding model |
| **Citation Count** | Number of `[n]` markers in agent response (max 2 enforced) |
| **Citation Hit** | Any cited chunk_id ∈ `expected_chunk_ids` |
| **Finish `stop`** | Model stopped naturally (not length/blocked) |
| **LLM-Judge Pass** | Gemma scores ≥ threshold on all 4 dimensions |

---

## 7. Reproducibility Checklist

- [x] All scripts in repo (`eval/`, `components/*/kb_manager/evaluation/`)
- [x] Frozen test set: `data/test_questions.sha256` + `data/versions.lock`
- [x] Fixed random seeds (temp 0.0 for generation)
- [x] Versioned KB (v5-v8 with git tags)
- [x] Results saved as JSON + plots
- [x] GitHub Pages report site (enable Pages from `/docs`)

---

## 8. Known Gaps (Next)

| Priority | Task |
|----------|------|
| P0 | IVA ranking: raise doc-hit@5 73.3%→85%+ (RERANKER_TOP_K 50→100, per-domain rerank) |
| P1 | Full IVA answer-grounded RAGAS eval (faithfulness/relevancy) with Gemini/Ollama |
| P1 | Performance: RERANKER_TOP_K 50→30 GPU, batch 64→128, float16 on H200, BM25 cache |
| P2 | FaMTEB live 600q smoke + leaderboard publish |
| P2 | Corpus dedup: 2074→~1700 chunks + re-benchmark |
| P2 | Multi-query rewriting (beam5 RRF with LLM) |
| P2 | HyDE A/B controlled (hit@5/MRR/p50/p95) |
| P3 | Documentation: implementation plan status, v6/v7 comparison plots |

---

## 9. Files

```
eval/
├── README.md                           # This evaluation summary
├── run_llm_answer_benchmark.py
├── run_llm_judge.py
├── make_plots.py
├── build_report_site.py
├── kb_rag_evaluation_20samples.json    # 20 RAG results with tags
├── kb_guardrails_blocked_input_120.json
├── kb_full_evaluation.json             # If generated
├── baseline.json                       # 76/82 correct, 0 FP, 6 FN, 25ms
└── results/
    ├── llm_answer_benchmark_v4.json
    ├── llm_judge_v4.json
    ├── reranker_benchmark_*.json
    ├── plots/                          # PNG + Plotly HTML
    │   ├── similarity_hist_v4.png
    │   ├── format_means_v4.png
    │   ├── citations_v4.png
    │   └── v3-vs-v4.png
    └── hnsw_benchmark_detailed.json
```