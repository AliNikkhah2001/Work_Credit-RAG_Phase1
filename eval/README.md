# KB RAG Evaluation — 2026-09-02

This directory contains end-to-end evaluation of the RAG agent against KB ground truth on Vast VM.

## Dataset

- Source: `components/knowledgebase/kb-manager/data/test_questions.json` (120 questions, updated to `b1bb648`)
- Sample: 20 diverse (first 15 + 5 with known allowlisted terms like حذف, پستی, etc.)
- Ground truth: `expected_answer`, `expected_chunk_ids`, `keywords`, `category`, `difficulty`

## Method

For each question:
1. Check guardrails input via `POST /v1/rails/check` (stage input)
2. Ask RAG via `POST /v1/chat/completions` on orchestrator `8100` (model `gemma-4-31b`, temp 0, max_tokens 500)
3. Check for `has_unused` (`<unused`), `is_english` (`The provided context...`), `is_fallback` (`متأسفم، مدل...`), `finish_reason`, `citations`
4. Tag: `ok` if `finish==stop && citations>0 && !has_unused && !is_english && !is_fallback && !blocked`; else `guardrail_blocked`, `hate:lemma`, `profanity_blocked`, `no_citations`, `english_fallback`, etc.
5. Derivation: `citation_hit` if any `citations` chunk_id in `expected_chunk_ids`

## Results (2026-09-02, after fixes)

- **20 samples:** `20/20 ok`, `0 wrong`, `0 terminated by guardrails` (was `18/20 ok`, 2 blocked as `hate:مهم` and `profanity:ان` before fix)
- **120 questions input check:** `0/120 blocked` (was `2/120` before allowlist)
- **120 expected answers output check:** `0/120 blocked` (was `6/120` with `hate:ضعیف` before adding ضعیف)
- **Rerun after fixes:** All 20 now `stop` with 5 citations, Persian only, no `<unused>`, no English fallback.

## Before fix (for comparison)

- `hate:حذف` blocked `چگونه می‌توانم گزارش اعتباری خود را دریافت کنم؟` at input (KB context `درخواست حذف سابقه منفی قدیمی`) → 0 citations
- `hate:مهم` blocked `جدول نوع تماس` (KB chunk `مهم است`)
- `profanity:ان` blocked `تفاوت شرکت شما با رقبایتان...` (KB chunk `اثر ان را`)
- `hate:ضعیف` blocked 6 expected answers with `رتبه اعتباری ضعیف`

## After fix

- HurtLex allowlist now 11 lemmas: `حذف, بخشی, تامین مالی, اشتغال, پست, پستی, مصرف, هدف, نادرست, مهم, ضعیف` (all normalized, logged)
- Profanity now requires `len(w)>2`, so `ان` (len 2) no longer flags
- 19 regression tests in `components/guardrails/tests/test_hurtlex_allowlist.py` + 6 in `test_input_rails.py` + 9 in orchestrator
- 6 user samples + 6 credit samples all `stop` with 5 citations, Persian only

## Wrong samples

Before fix, wrong samples were tagged and saved in `kb_wrong_samples.json` (2 samples). After fix, `kb_rag_evaluation_20samples.json` contains `tags: ["ok"]` for all, and `kb_wrong_samples.json` is empty (or not generated). To reproduce, run:

```bash
PYTHONPATH=components/guardrails/src /tmp/guard-venv/bin/python /tmp/eval_kb_rag2.py
# or for full 120 (takes ~10 min):
timeout 600 python3 /tmp/full_eval.py
```

## Files

- `kb_rag_evaluation_20samples.json` — 20 RAG results with `query`, `expected_answer`, `rag_content`, `finish_reason`, `citations`, `tags`, `guardrails_input`
- `kb_guardrails_blocked_input_120.json` — 0 entries after fix (before fix had 2)
- `kb_full_evaluation.json` (if generated) — full 120 with derivation

## Next tweaks

- If a new KB question is terminated by guardrails, add its lemma to `components/guardrails/kb/hurtlex_allowlist.json` (with evidence) and add a test in `test_hurtlex_allowlist.py`, then restart guardrails.
- If retrieval is wrong (citation miss), check `components/knowledgebase/kb-manager/data/test_questions.json` `expected_chunk_ids` vs `final_results` and tune `build_context` MAX_CHUNKS / MAX_CHARS or reranker.
- If answer is English, check `components/orchestrator/src/.../nodes/build_context.py` system prompt is Persian-only.
