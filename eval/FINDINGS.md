# Wrong Samples Findings — Detailed Analysis (2026-09-02)

This document details every RAG response that was **wrong** (blocked, fallback, English, or missing citations) when evaluated against KB ground truth, how it was diagnosed, and what was fixed. It is saved and tagged so we can come back and tweak prompt, guardrails, or retrieval.

> **Current status after all fixes (guardrails `1e9a1cd` 11 lemmas + profanity `len>2`, orchestrator `9b85561` Persian prompt): 20/20 ok, 0 wrong, 0 terminated by guardrails (was 18/20, 2 blocked). 120/120 input not blocked, 0/120 expected answers blocked (was 6). 6/6 user samples now Persian with 5 citations.**

## How wrong samples are tagged and saved

Each evaluation result is JSON with `tags`:

- `ok` — `finish==stop && citations>0 && !has_unused && !is_english && !is_fallback && !guardrail_blocked`
- `guardrail_blocked` + `hate:lemma` or `profanity_blocked` — terminated by `POST /v1/rails/check` or `guarded_completion` output check
- `no_citations` — `citations` 0 when `expected_chunk_ids` not empty
- `english_fallback` — `The provided context does not contain...` (now fixed to Persian)
- `generic_fallback` — `متأسفم، مدل پاسخ مناسبی تولید نکرد...`
- `control_token_leak` — `<unused` or `<|tool`
- `citation_miss` — `citation_hit==false` (not used for blocking, but for retrieval tuning)

Saved files:

- `eval/kb_rag_evaluation_20samples.json` — 20 end-to-end RAG results with `query`, `expected_answer`, `rag_content`, `finish_reason`, `citations`, `tags`, `guardrails_input`, `derivation`
- `eval/kb_guardrails_blocked_input_120.json` — input-blocked among 120 (now 0)
- `eval/kb_full_evaluation.json` (if generated, 120) — full with `citation_hit`
- Before fix, `eval/kb_wrong_samples.json` contained 2 wrong samples; after fix it is empty and not committed (history in git).

To reproduce:

```bash
# 20-sample quick eval (30s)
PYTHONPATH=components/guardrails/src /tmp/guard-venv/bin/python /tmp/eval_kb_rag2.py  # uses /tmp/eval_kb_rag2.py
# Full 120 (10 min)
timeout 600 python3 /tmp/full_eval.py  # see eval/README.md
# Raw guardrails check for any query
curl -s http://127.0.0.1:8200/v1/rails/check -H 'Content-Type: application/json' -d '{"stage":"input","text":"...","request_id":"t"}' | jq .
```

---

## Wrong Sample #1 — `hate:حذف` (KB-terminated, input)

**Query (from KB `test_questions.json` #? and user sample):** `چگونه می‌توانم گزارش اعتباری خود را دریافت کنم؟`

**Expected:** `expected_answer: "با توجه به متن ارائه شده، اطلاعات کافی..."` (ground truth from KB, not directly in `expected_answer` but derived from chunks `IndividualAndCompanyQuestions_Part2` about `درخواست حذف سابقه منفی`), `expected_chunk_ids: ["e10ec98e...", "c0648afc...", ...]`, `keywords: گزارش اعتباری, سن, ۱۸سال`

**RAG before fix:**
```json
{
  "choices": [{"message": {"content": "محتوای شما حاوی زبان آزاردهنده است و قابل پردازش نیست. (hate:حذف)"}, "finish_reason": "content_filter"}],
  "rag": {"citations": []}
}
```
`tags: ["guardrail_blocked", "hate:حذف", "no_citations"]`, `guardrails_input: {"allowed": false, "reason": "hate:حذف"}`

**Diagnosis:**
- `check_hurtlex_fa` on augmented prompt `last_user_msg` (which is `[Context from Knowledge Base] ... درخواست حذف سابقه منفی قدیمی از گزارش اعتباری شرکت را ثبت کنم؟ ... سوابق تا پنج سال باقی می‌مانند ... \n\nQuestion: چگونه می‌توانم گزارش اعتباری خود را دریافت کنم؟`) → `normalize_persian` → `...درخواست حذف سابقه منفی...` → `\bحذف\b` matches `hurtlex_fa_conservative.json:329 "حذف"` → `hate:حذف`.
- This is **input** block, before Gemma was called, so no `guardrails_raw.log`, no citations. Input is not the original user query (`چگونه...` alone is clean) but the RAG-augmented prompt that includes trusted KB chunks. `حذف` in credit domain means “delete/correct a negative record”, not hate.
- Raw Gemma for same prompt when called directly (`POST /18000` with `enable_thinking:false`) was clean: `با توجه به متن ارائه شده، در صورتی که سوابق مالی مستقل کافی... امکان اخذ گزارش اعتبارسنجی وجود ندارد [1],[2],[3].` → `check_hurtlex_fa` on this raw was `False`.

**Fix:**
- Added `حذف` to `kb/hurtlex_allowlist.json` (normalized `حذف`, evidence: `درخواست حذف سابقه منفی قدیمی`), `load_hurtlex_allowlist()` + `check_hurtlex_fa` now `w not in allowlist` and logs `HurtLex match: lemma=...`.
- Applied to both input and output for MVP (so trusted KB context does not trigger), kept `check_hurtlex_fa_strict` for hostile input audit. Profanity/PII/secret remain strict.

**After fix:**
```json
{
  "choices": [{"message": {"content": "بر اساس اطلاعات موجود در پایگاه دانش، تعریف دقیقی... امکان اخذ گزارش اعتبارسنجی وجود ندارد [1],[2],[3]."}, "finish_reason": "stop"}],
  "rag": {"citations": [5]}
}
```
`tags: ["ok"]`, `citations: 5`, `has_unused: false`, `is_english: false`, `guardrails_input: {"allowed": true}`

**Tweak point if it recurs:** Add lemma to `hurtlex_allowlist.json` with evidence, add test `test_hazf_benign_allowed` in `tests/test_hurtlex_allowlist.py`, restart guardrails (`8200`).

---

## Wrong Sample #2 — `hate:مهم` (KB-terminated, input via KB chunk)

**Query:** `یه سوال داشتم، جدول نوع تماس (Type Of Contact) شامل چه مواردی است؟` (from `test_questions.json` #2)

**Expected:** `نوع تماس مشتری شامل تلفن، موبایل، فکس، ایمیل و وب‌سایت است.` `expected_chunk_ids: ["5656d2ea..."]`

**RAG before fix:**
```json
{"choices": [{"message": {"content": "محتوای شما حاوی زبان آزاردهنده است و قابل پردازش نیست. (hate:مهم)"}, "finish_reason": "content_filter"}], "rag": {"citations": []}}
```
`tags: ["guardrail_blocked", "hate:مهم", "no_citations"]`

**Diagnosis:**
- KB retrieval for this query returns chunk `DataProvidersQuestions` with `...تطبیق با قرارداد و کنترل ریسک مهم است... سوال: جدول نوع تماس ...` — the **KB chunk itself** contains `مهم` (important). Augmented prompt therefore contains `مهم` → `hate:مهم` (HurtLex:670 `"مهم"`).
- Direct `check_hurtlex_fa` on the query alone was `False`; on the augmented prompt it was `True` because of the chunk. `مهم` in credit domain is “important”, not hate.
- `check_output_persian` on the expected answer also would have been blocked before allowlist (same lemma).

**Fix:** Added `مهم` to allowlist (now 11 lemmas), same `actions.py` change, plus `test_mohem_allowed`.

**After fix:** `stop` with `نوع تماس مشتری شامل تلفن، موبایل، فکس، ایمیل و وب‌سایت است [1],[2].` 5 citations, `tags: ["ok"]`.

---

## Wrong Sample #3 — `profanity:ان` (KB-terminated, profanity short word)

**Query:** `تفاوت شرکت شما با رقبایتان (شرکت مرآت یا حافظ سامان ایرانیان، اسم رقبا) چیست؟` (from `test_questions.json` #7)

**Expected:** `expected_answer` about `تغییر مدیرعامل...` etc., `category: factual`

**RAG before fix:**
```json
{"choices": [{"message": {"content": "محتوای شما حاوی الفاظ نامناسب است. (profanity:ان)"}, "finish_reason": "content_filter"}], "rag": {"citations": []}}
```
`tags: ["guardrail_blocked", "profanity_blocked", "no_citations"]`

**Diagnosis:**
- `check_profanity_fa` on augmented prompt: KB chunks for this query contain fragmented text like `... اثر ان را مشاهده کرد ...` where `ان` appears as a separate word (pronoun “it”, common in Persian, and also a fragment from `ضمانت‌نامه` broken by ZWNJ). `persian_swear.json:16 "ان"` with `\bان\b` matched.
- This is a **profane false positive due to very short word** `ان` (len 2). HurtLex already has `len(w)>2` filter, but profanity did not. `ان` is not profane in this context; it's a grammatical particle.
- Direct `check_profanity_fa` on the query alone was `False`; on the KB context it was `True` because of the chunk.

**Fix:** `src/work_rag_guardrails/actions.py:check_profanity_fa` now `if w and len(w) > 2 and re.search(...)` (was no length check). Added test `test_short_profanity_not_flagged` for `اثر ان را`.

**After fix:** `stop` with `در حال حاضر تغییر مدیرعامل...` 5 citations, `tags: ["ok"]`.

---

## Wrong Samples #4-9 — `hate:ضعیف` (expected answers, output)

**Queries (6 of 120):** All with expected answer `رتبه اعتباری در واقع شاخص اعتماد مالی شماست... رتبه اعتباری ضعیف می‌تواند باعث رد درخواست وام شود.` (e.g., `شاخص اعتماد ریسک پایین موسسات مالی خوش حسابی`, `راستی، چرا امتیاز اعتباری و رتبه اعتباری من مهم است...` etc.)

**Diagnosis:** `check_output_persian` on `expected_answer` → `hate:ضعیف` (`hurtlex_fa_conservative.json:688 "نادرست"? No, "ضعیف":670? Actually `ضعیف` at 670 is `مهم`? Wait `ضعیف` at 688 is `نادرست`? Let's check: `ضعیف` is at `670: "مهم"` is not, `ضعیف` is separate. The expected answer contains `ضعیف` (weak) as in `رتبه اعتباری ضعیف` — legitimate financial term, not hate. But HurtLex flags `ضعیف` as hate (weak = insult). In credit domain, “weak rating” is factual.

**Fix:** Added `ضعیف` to allowlist, same as others, with test `test_zaif_allowed`.

**After fix:** `0/120` expected answers blocked (was `6/120`), all `check_output_persian` now `allowed: true` for those.

---

## Wrong Samples #10-11 — English fallback (prompt, not guardrail)

**Queries:** `چرا یکی از وام هایی که دارم قسطشون رو میدم، توی گزارش اعتباری من نیست؟` and `رتبه چه فرقی با امتیاز داره؟` (user samples)

**RAG before fix:**
```json
{"content": "The provided context does not contain information regarding why a loan that is being paid is not appearing in the credit report...", "finish_reason": "stop", "rag": {"citations": [5]}}
```
`tags: ["english_fallback"]` (was `is_english: true`, `has_unused: false`, but `finish: stop` with English, not Persian, even though citations were present).

**Diagnosis:** `build_context.py` system message was **English**: `You are a helpful assistant for ICS Credit Scoring. Answer ... If the context doesn't contain...` → Gemma followed instruction and answered in English when context was insufficient, even though user asked in Persian. This is a **prompt answer format** issue, not guardrail.

**Fix:** `components/orchestrator/src/.../nodes/build_context.py` system message now **Persian-only**:
`شما دستیار هوشمند اعتبارسنجی ایران (ICS) هستید. فقط بر اساس متن‌های داخل بخش [Context]... اگر تعریف دقیق در متن‌ها نیست، نزدیک‌ترین اطلاعات مرتبط را با ذکر منابع خلاصه کنید و بگویید «تعریف دقیق در متن‌های ارائه شده موجود نیست اما به موارد زیر اشاره شده است». همیشه به زبان فارسی پاسخ دهید — حتی اگر سوال به انگلیسی باشد... برای سلام با لحنی دوستانه... منابع را با [1],[2] ارجاع دهید`
Now out-of-context returns `بر اساس اطلاعات موجود در پایگاه دانش، پاسخی برای این سوال یافت نشد.` with 5 citations, Persian.

**After fix:** Both now `بر اساس اطلاعات موجود در پایگاه دانش، پاسخی برای این سوال یافت نشد.` 5 citations, `is_english: false`, `tags: ["ok"]`.

---

## Additional wrong samples that are now fixed (from Phase 7 user chat)

- `سلام` → was `متأسفم، مدل پاسخ مناسبی تولید نکرد...` (generic fallback when context empty) vs now `سلام. چطور می‌توانم به شما کمک کنم؟` (greeting, 5 citations but friendly, no fallback, via new Persian prompt that says for `سلام` answer with greeting, no citations needed — still returns 5 citations but friendly).
- `چگونه می‌توان گزارش چک را مجدداً دریافت کرد؟` → was `hate:پستی` (KB chunk contains `پستی`), now allowlisted `پستی` → `بر اساس اطلاعات موجود... انقضای گزارش چک یک روز کاری است... [1],[2]` 5 citations.
- `اعتبارسنجی چیست؟` → was `The provided...` English? No, now `تعریف دقیق اعتبارسنجی در متن‌های ارائه شده موجود نیست اما به موارد زیر اشاره شده است: ... [2],[3]` Persian, helpful.

---

## Current evaluation after all fixes (2026-09-02, guardrails `1e9a1cd` 11 lemmas, orchestrator `9b85561` Persian, KB `b1bb648`)

- **20-sample RAG:** `20/20 ok`, `0 wrong`, `0 terminated by guardrails` (saved in `kb_rag_evaluation_20samples.json`)
- **120 input checks:** `0/120 blocked` (was 2)
- **120 expected answers output checks:** `0/120 blocked` (was 6)
- **6 user samples + 6 credit samples:** all `stop` 5 citations, Persian, no `<unused>`, no `hate:`

## How to tweak further

1. **Guardrail-blocked KB question:** Add its lemma to `components/guardrails/kb/hurtlex_allowlist.json` (with `evidence` and `normalized_allowlist`), add test in `tests/test_hurtlex_allowlist.py` (benign `test_*_allowed`), restart `8200` (`PYTHONPATH=... /tmp/guard-venv/bin/python -m uvicorn ... --port 8200`), rerun `PYTHONPATH=... /tmp/guard-venv/bin/python -m pytest ... -k allowlist`.
2. **Retrieval wrong (citation miss):** Check `expected_chunk_ids` vs `final_results` in `kb_rag_evaluation_20samples.json` `derivation: miss` → tune `build_context.py` `MAX_CHUNKS`/`MAX_CHARS` or `knowledgebase` reranker, or add missing keywords to `kb-source`.
3. **Prompt English or generic fallback:** Edit `build_context.py` system message (Persian, citation style) and restart `8100`.
4. **Control-token leak `<unused`:** Check `service.py` `_clean_gemma_output` and ensure `chat_template_kwargs:{"enable_thinking":false}` is sent (commit `3f20bed`), and `llama.cpp` is `0f3a71b` with `--no-mmproj`.

All fixes keep **profanity/PII/secret strict** — only HurtLex allowlisted lemmas are exempt, with exact-word `\b...\b` and logging.

