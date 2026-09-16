# Long prompt + truth block (@general subagent)

Session: `ses_f5f4b89f3ffegx0pIzAf5yqfaz`
Messages: 17


## [USER]

Upgrade orchestrator generation: 20-chunk context, long detailed Persian answers, ground-truth block appended. Repo: `/workspace/Work_Credit-RAG_Phase1/components/orchestrator`, branch `main`. Work ONLY in: `src/work_rag_orchestrator/nodes/build_context.py`, `src/work_rag_orchestrator/nodes/guarded_generate.py`, `src/work_rag_orchestrator/nodes/format_response.py`. Do NOT touch retrieve.py, clients/, schemas.py, config.py (another agent owns the retrieval side).

CONTRACT (guaranteed by the retrieval agent): each `state["retrieved_chunks"]` item has keys chunk_id, document_id, title, heading, content, score, source ("rrf"/"ce"/"both"), rank_rrf, rank_ce, hybrid_score, rerank_score (None where N/A). Up to 20 items. Code defensively with .get() anyway.

TASKS:
1. `build_context.py`: MAX_CHUNKS 5→20, MAX_CONTEXT_CHARS 6000→9000, history cap HISTORY_MAX_CHARS→1000 (import the constant, pass max_chars=1000 explicitly to last_exchanges_text). Label sections `[RRF-i]` for source rrf, `[CE-i]` for ce, `[BOTH-i]` for both, using rank_rrf/rank_ce numbers. Keep truncation logic + is_new_chat greeting logic.
2. System prompt: rewrite for LONGER, MORE DETAILED Persian answers — multi-paragraph, cover all relevant aspects from the 20 sources (state which source-set each fact comes from in prose, e.g. "در منابع رتبه‌بندی معنایی آمده…"), definitions + procedures + examples where present. KEEP: plain-text-only rule (no markdown, no [n] markers in body), Persian-only, no cliché intro, self-harm rule, "answer from sources, say یافت نشد only if truly nothing relevant". Update the metadata max_chunks/max_chars in the trace_span.
3. `guarded_generate.py`: max_tokens 512→1024 (find both the request construction ~line 36 and the span_input log ~line 67; keep temperature 0.2).
4. `format_response.py`: after the answer, append a plain-text ground-truth block so Open WebUI users see what was retrieved:
   `\n\nمنابع بازیابی‌شده:\n` then one line per chunk (up to 20): `[RRF-3/BOTH-1] <title> — <heading> — امتیاز <score>` (use source label + the relevant rank + rounded score; skip empty titles gracefully). Do NOT let _to_plain_text strip this block (append AFTER cleaning the answer; the block itself contains no markdown). Raise MAX_CITATIONS 2→5. Citations metadata: prefer "both" chunks, then ce, then rrf.
5. `python -m py_compile` every edited file. Do NOT commit (coordinator commits).

RETURN: exact edits per file, py_compile result, and the final system prompt text (full).


## [ASSISTANT]

(step-start: {"snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: read)

(tool: read)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-finish", "tokens": {"total": 9846, "input": 7794, "output": 255, "reasoning": 20, "cache": {"write": 0, "read": 1777}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-start"})

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-finish", "tokens": {"total": 14457, "input": 4858, "output": 130, "reasoning": 12, "cache": {"write": 0, "read": 9457}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-start"})

(reasoning: )

(reasoning: )

(reasoning: )

(reasoning: )

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-finish", "tokens": {"total": 16785, "input": 386, "output": 293, "reasoning": 1913, "cache": {"write": 0, "read": 14193}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-finish", "tokens": {"total": 17187, "input": 2160, "output": 450, "reasoning": 0, "cache": {"write": 0, "read": 14577}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-finish", "tokens": {"total": 17424, "input": 586, "output": 213, "reasoning": 0, "cache": {"write": 0, "read": 16625}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-start"})

(reasoning: )

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-finish", "tokens": {"total": 18953, "input": 311, "output": 1487, "reasoning": 18, "cache": {"write": 0, "read": 17137}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-start"})

(reasoning: )

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-finish", "tokens": {"total": 19124, "input": 1584, "output": 132, "reasoning": 15, "cache": {"write": 0, "read": 17393}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-finish", "tokens": {"total": 19298, "input": 219, "output": 150, "reasoning": 0, "cache": {"write": 0, "read": 18929}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-finish", "tokens": {"total": 20059, "input": 265, "output": 698, "reasoning": 39, "cache": {"write": 0, "read": 19057}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-finish", "tokens": {"total": 20636, "input": 770, "output": 553, "reasoning": 0, "cache": {"write": 0, "read": 19313}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-start"})

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-finish", "tokens": {"total": 20809, "input": 579, "output": 141, "reasoning": 8, "cache": {"write": 0, "read": 20081}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-start"})

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-finish", "tokens": {"total": 21491, "input": 464, "output": 390, "reasoning": 44, "cache": {"write": 0, "read": 20593}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-start"})

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-finish", "tokens": {"total": 22121, "input": 768, "output": 376, "reasoning": 0, "cache": {"write": 0, "read": 20977}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-start"})

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-finish", "tokens": {"total": 22562, "input": 436, "output": 381, "reasoning": 0, "cache": {"write": 0, "read": 21745}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "141b90c3f7611a48061864d6f53fe02e0bdce597", "type": "step-start"})

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "5bb6aeb6fbeb3d8115f961be2f62779f03eb0f63", "type": "step-finish", "tokens": {"total": 22806, "input": 529, "output": 126, "reasoning": 22, "cache": {"write": 0, "read": 22129}}, "cost": 0})

(patch: {"type": "patch", "hash": "141b90c3f7611a48061864d6f53fe02e0bdce597", "files": ["/workspace/Work_Credit-RAG_Phase1/README.md"]})


## [ASSISTANT]

(step-start: {"snapshot": "5bb6aeb6fbeb3d8115f961be2f62779f03eb0f63", "type": "step-start"})

(reasoning: )

Done. No commit (left for coordinator). Note: `config.py`, `schemas.py`, `clients/knowledgebase.py` show as modified in `git status` — those are the retrieval agent's changes; I did not touch them.

## 1. `build_context.py`

- `MAX_CONTEXT_CHARS 6000 → 9000`, `MAX_CHUNKS 5 → 20`
- Added `_section_label(chunk, fallback_idx)` helper: `source=="rrf"` → `[RRF-<rank_rrf>]`, `"ce"` → `[CE-<rank_ce>]`, `"both"` → `[BOTH-<rank_rrf or rank_ce>]`, all via `.get()` with `isinstance(int)` check and enumerate-index fallback; unknown source → `[i]`
- Context loop now uses `source_id = _section_label(chunk, i)` instead of `f"[{i}]"`; all `.get("title"/"heading"/"content")` defensive access kept
- History: `last_exchanges_text(messages, include_current=False, max_chars=1000)` (explicit 1000; `HISTORY_MAX_CHARS` import kept)
- Truncation logic and `is_new_chat` greeting logic untouched
- Trace metadata still `{"max_chunks": MAX_CHUNKS, "max_chars": MAX_CONTEXT_CHARS}` → now reports 20/9000 automatically
- System prompt rewritten (full text below)

## 2. `guarded_generate.py`

- Line ~36: `max_tokens=512 → 1024` (temperature stays 0.2)
- Line ~67 span log: `"max_tokens": 512 → 1024`

## 3. `format_response.py`

- `MAX_CITATIONS 2 → 5`
- Added `GROUND_TRUTH_HEADER = "\n\nمنابع بازیابی‌شده:\n"`, `MAX_GROUND_TRUTH_LINES = 20`, `_source_label()` (same rank logic as build_context), `_chunk_score()` (first non-None of `hybrid_score`/`rerank_score`/`score`, rounded to 3 decimals), `_ground_truth_block()` (up to 20 lines, `[LABEL-n] title — heading — امتیاز score`; skips chunks with both title+heading empty; title-only or heading-only lines handled), `_citation_priority()` (`both:0, ce:1, rrf:2, else:3`)
- Non-blocked path: default citation choice is now priority-sorted `both > ce > rrf` (stable within group), explicit `[n]` override kept; block appended **after** `_clean_answer`/`_to_plain_text` via `content = content + block` so cleaners never strip it; block contains no markdown
- Blocked/refusal path unchanged (no block appended)

## py_compile

```
python3 -m py_compile src/work_rag_orchestrator/nodes/build_context.py src/work_rag_orchestrator/nodes/guarded_generate.py src/work_rag_orchestrator/nodes/format_response.py
→ PY_COMPILE_OK
```

Runtime sanity (venv, `PYTHONPATH=src`): `_ground_truth_block` on 4 mixed chunks → `'\n\nمنابع بازیابی‌شده:\n[RRF-3] T1 — H1 — امتیاز 0.91\n[CE-1] T2 — امتیاز 0.8\n[BOTH-2] T4 — H4 — امتیاز 0.7'` (empty-title chunk skipped, scores rounded). `MAX_CITATIONS=5` confirmed.

## Final system prompt (full)

```
شما دستیار هوشمند رسمی شرکت اعتبارسنجی ایران (Iranian Credit Scoring Company AI Agent) هستید — نمایندهٔ هوشمندِ پاسخگویی مشتریان شرکت اعتبارسنجی ایران می‌باشید و لحنی محترمانه، دقیق و کاربردی دارید. پاسخ را بر اساس بخش [Context from Knowledge Base] به صورت طولانی، مفصل و چندپاراگرافی بنویسید؛ همهٔ جنبه‌های مرتبط با پرسش را که در منابع آمده پوشش دهید و متن‌ها را کپی نکنید، بلکه آن‌ها را با زبان خودتان بازنویسی کنید. از میان حداکثر ۲۰ منبع ارائه‌شده، همهٔ منابع مرتبط را در نظر بگیرید و نکته‌ای را از قلم نیندازید؛ تعریف‌ها، مراحل و رویه‌ها، شرایط و مدارک لازم، و مثال‌های موجود در منابع را در پاسخ بیاورید. در متن پاسخ با زبان طبیعی مشخص کنید هر نکته از کدام دسته منابع آمده است؛ برای منابعی با برچسب CE بنویسید «در منابع رتبه‌بندی معنایی آمده…»، برای منابعی با برچسب RRF بنویسید «در منابع رتبه‌بندی اولیه آمده…» و برای منابعی با برچسب BOTH بنویسید «در منابعی که هر دو روش بازیابی تأیید کرده‌اند آمده…». مستقیم و دقیق به خودِ سوال پاسخ دهید؛ مقدمهٔ کلیشه‌ای (مثل «موارد زیر را یافتم») ننویسید و پاسخ را در چند پاراگراف منسجم و کاربردی سازمان دهید. قالب پاسخ متن سادهٔ فارسی است — از هیچ قالب‌بندی مارک‌داون استفاده نکنید: نه ستاره (*)، نه بولد (**)، نه هشتگ (#)، نه خط تیره در ابتدای خط، نه بک‌تیک؛ فقط جمله‌های ساده در قالب پاراگراف بنویسید. هیچ شمارهٔ ارجاعی مثل [1] یا [2] در متن پاسخ نیاورید. اگر پاسخ مستقیم در متن‌ها نیست، از میان نزدیک‌ترین اطلاعات مرتبط یک پاسخ مفید بسازید و تفاوت ظریف را توضیح دهید؛ جملهٔ «بر اساس اطلاعات
…[truncated]…

(step-finish: {"reason": "stop", "snapshot": "b6a0fae7f9350fe15068ad22cebce4e8c8b2e264", "type": "step-finish", "tokens": {"total": 27609, "input": 3523, "output": 1427, "reasoning": 18, "cache": {"write": 0, "read": 22641}}, "cost": 0})

(patch: {"type": "patch", "hash": "5bb6aeb6fbeb3d8115f961be2f62779f03eb0f63", "files": ["/workspace/Work_Credit-RAG_Phase1/README.md"]})
