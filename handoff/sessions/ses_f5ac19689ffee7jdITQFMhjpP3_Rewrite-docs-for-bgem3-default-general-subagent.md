# Rewrite docs for bgem3 default (@general subagent)

Session: `ses_f5ac19689ffee7jdITQFMhjpP3`
Messages: 21


## [USER]

Rewrite reranker docs to declare BAAI/bge-reranker-v2-m3 the default model. Repos: `/workspace/Work_Credit-RAG_Phase1` (parent, `main`) and `components/knowledgebase` (`master`). HARD RULES: never force-push, never commit secrets/*.npz/*.log/venvs; stage only intended files; scan diff for tokens.

VERIFIED FACTS (use these):
- Default reranker is now `BAAI/bge-reranker-v2-m3` in code (`reranker.py _DEFAULT_MODEL`, `config.py RerankerConfig`, `search.py _RERANKER_MODEL` fallback; commit `8d0c506` on KB master) and live on production KB `:8000` via `KB_RERANKER_MODEL` + `KB_RERANK_POOL=15`.
- Persian support (researched 2026-09-15): backbone is BGE-M3 (Multi-linguality: 100+ languages, incl. Persian; SOTA on MIRACL multilingual which includes Persian `fa`, and MKQA cross-lingual); vendor BGE docs explicitly recommend v2-m3 "for multilingual"; 568M params, 2.27GB, XLM-RoBERTa-Large base, Apache-2.0, plain cross-encoder loader (no trust_remote_code).
- Measured on our Persian credit KB (800 remapped queries, top-5): hit 0.536, top1 0.474, MRR 0.496 — the best measured MRR (MiniLM pool15: 0.493; pool30: 0.495; Qwen4B think-disabled: 0.233; bgemma-2B 25-slice: 0.44 tied with MiniLM at 10x latency).
- Production note: 568M on CPU → set `KB_RERANK_POOL=15` to bound latency (~5-15s rerank solo); GPU hosts can raise to 30.

TASKS:
1. `components/knowledgebase/kb-manager/README.md`: update the reranker section — default model callout, Persian-support subsection (backbone, MIRACL-fa, vendor recommendation), refreshed decision (BGE-m3 default with measured justification; MiniLM as lightweight fallback via `KB_RERANKER_MODEL=cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`).
2. Parent `README.md` "Retrieval quality" section: update decision to BGE-m3 default + Persian paragraph.
3. `docs/WAVE2_GPU_RUNBOOK.md`: update the decision/recommendation lines to BGE-m3 default (keep historical numbers intact).
4. Commit KB README on `master`, parent README+runbook on `main`, push both. Non-fast-forward → report, never force. Auth failure → report PUSH_BLOCKED_AUTH with error text.

RETURN: files changed, commit hashes, push status.


## [ASSISTANT]

(step-start: {"snapshot": "63e429060018d70804dc500e133c1812dd70122e", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: read)

(tool: read)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "63e429060018d70804dc500e133c1812dd70122e", "type": "step-finish", "tokens": {"total": 9768, "input": 8277, "output": 216, "reasoning": 10, "cache": {"write": 0, "read": 1265}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "63e429060018d70804dc500e133c1812dd70122e", "type": "step-start"})

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "63e429060018d70804dc500e133c1812dd70122e", "type": "step-finish", "tokens": {"total": 29145, "input": 19525, "output": 112, "reasoning": 51, "cache": {"write": 0, "read": 9457}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "63e429060018d70804dc500e133c1812dd70122e", "type": "step-start"})

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "63e429060018d70804dc500e133c1812dd70122e", "type": "step-finish", "tokens": {"total": 29596, "input": 578, "output": 105, "reasoning": 0, "cache": {"write": 0, "read": 28913}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "63e429060018d70804dc500e133c1812dd70122e", "type": "step-start"})

(reasoning: )

(tool: bash)

(tool: grep)

(step-finish: {"reason": "tool-calls", "snapshot": "63e429060018d70804dc500e133c1812dd70122e", "type": "step-finish", "tokens": {"total": 30119, "input": 415, "output": 237, "reasoning": 42, "cache": {"write": 0, "read": 29425}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "63e429060018d70804dc500e133c1812dd70122e", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "63e429060018d70804dc500e133c1812dd70122e", "type": "step-finish", "tokens": {"total": 32566, "input": 2161, "output": 312, "reasoning": 284, "cache": {"write": 0, "read": 29809}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "63e429060018d70804dc500e133c1812dd70122e", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "63e429060018d70804dc500e133c1812dd70122e", "type": "step-finish", "tokens": {"total": 33960, "input": 733, "output": 1370, "reasoning": 0, "cache": {"write": 0, "read": 31857}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "63e429060018d70804dc500e133c1812dd70122e", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "63e429060018d70804dc500e133c1812dd70122e", "type": "step-finish", "tokens": {"total": 34895, "input": 1487, "output": 911, "reasoning": 0, "cache": {"write": 0, "read": 32497}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "63e429060018d70804dc500e133c1812dd70122e", "type": "step-start"})

(reasoning: )

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "63e429060018d70804dc500e133c1812dd70122e", "type": "step-finish", "tokens": {"total": 35181, "input": 1014, "output": 147, "reasoning": 115, "cache": {"write": 0, "read": 33905}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "63e429060018d70804dc500e133c1812dd70122e", "type": "step-start"})

(reasoning: )

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "2c99c5a0b64f8056f6a986a3926de1789c1d8003", "type": "step-finish", "tokens": {"total": 36428, "input": 404, "output": 1111, "reasoning": 112, "cache": {"write": 0, "read": 34801}}, "cost": 0})

(patch: {"type": "patch", "hash": "63e429060018d70804dc500e133c1812dd70122e", "files": ["/workspace/Work_Credit-RAG_Phase1/README.md"]})


## [ASSISTANT]

(step-start: {"snapshot": "2c99c5a0b64f8056f6a986a3926de1789c1d8003", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "9992b9f0be7a1d40f206724d217e53c2c4b4b2a2", "type": "step-finish", "tokens": {"total": 36822, "input": 1267, "output": 219, "reasoning": 151, "cache": {"write": 0, "read": 35185}}, "cost": 0})

(patch: {"type": "patch", "hash": "2c99c5a0b64f8056f6a986a3926de1789c1d8003", "files": ["/workspace/Work_Credit-RAG_Phase1/docs/WAVE2_GPU_RUNBOOK.md"]})


## [ASSISTANT]

(step-start: {"snapshot": "9992b9f0be7a1d40f206724d217e53c2c4b4b2a2", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "0dd93c8719e1c341d17ef29dbb1cde7f0b97677c", "type": "step-finish", "tokens": {"total": 37112, "input": 509, "output": 266, "reasoning": 0, "cache": {"write": 0, "read": 36337}}, "cost": 0})

(patch: {"type": "patch", "hash": "9992b9f0be7a1d40f206724d217e53c2c4b4b2a2", "files": ["/workspace/Work_Credit-RAG_Phase1/docs/WAVE2_GPU_RUNBOOK.md"]})


## [ASSISTANT]

(step-start: {"snapshot": "0dd93c8719e1c341d17ef29dbb1cde7f0b97677c", "type": "step-start"})

(reasoning: )

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "d338ff8fffec38bbe9146dc7d23e722cda7c54ad", "type": "step-finish", "tokens": {"total": 37441, "input": 415, "output": 202, "reasoning": 103, "cache": {"write": 0, "read": 36721}}, "cost": 0})

(patch: {"type": "patch", "hash": "0dd93c8719e1c341d17ef29dbb1cde7f0b97677c", "files": ["/workspace/Work_Credit-RAG_Phase1/docs/WAVE2_GPU_RUNBOOK.md"]})


## [ASSISTANT]

(step-start: {"snapshot": "d338ff8fffec38bbe9146dc7d23e722cda7c54ad", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: bash)

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "d338ff8fffec38bbe9146dc7d23e722cda7c54ad", "type": "step-finish", "tokens": {"total": 37710, "input": 360, "output": 217, "reasoning": 28, "cache": {"write": 0, "read": 37105}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "d338ff8fffec38bbe9146dc7d23e722cda7c54ad", "type": "step-start"})

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "d338ff8fffec38bbe9146dc7d23e722cda7c54ad", "type": "step-finish", "tokens": {"total": 42426, "input": 4425, "output": 204, "reasoning": 436, "cache": {"write": 0, "read": 37361}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "d338ff8fffec38bbe9146dc7d23e722cda7c54ad", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "2fb1804adc7c79d834f219eba2073d4003f2262f", "type": "step-finish", "tokens": {"total": 42909, "input": 954, "output": 175, "reasoning": 67, "cache": {"write": 0, "read": 41713}}, "cost": 0})

(patch: {"type": "patch", "hash": "d338ff8fffec38bbe9146dc7d23e722cda7c54ad", "files": ["/workspace/Work_Credit-RAG_Phase1/components/knowledgebase"]})


## [ASSISTANT]

(step-start: {"snapshot": "2fb1804adc7c79d834f219eba2073d4003f2262f", "type": "step-start"})

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "2fb1804adc7c79d834f219eba2073d4003f2262f", "type": "step-finish", "tokens": {"total": 43249, "input": 518, "output": 91, "reasoning": 31, "cache": {"write": 0, "read": 42609}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "2fb1804adc7c79d834f219eba2073d4003f2262f", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "2fb1804adc7c79d834f219eba2073d4003f2262f", "type": "step-finish", "tokens": {"total": 43518, "input": 191, "output": 168, "reasoning": 38, "cache": {"write": 0, "read": 43121}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "2fb1804adc7c79d834f219eba2073d4003f2262f", "type": "step-start"})

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "2fb1804adc7c79d834f219eba2073d4003f2262f", "type": "step-finish", "tokens": {"total": 43845, "input": 471, "output": 87, "reasoning": 38, "cache": {"write": 0, "read": 43249}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "2fb1804adc7c79d834f219eba2073d4003f2262f", "type": "step-start"})

(reasoning: )

(tool: bash)

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "2fb1804adc7c79d834f219eba2073d4003f2262f", "type": "step-finish", "tokens": {"total": 44106, "input": 277, "output": 174, "reasoning": 22, "cache": {"write": 0, "read": 43633}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "2fb1804adc7c79d834f219eba2073d4003f2262f", "type": "step-start"})

(reasoning: )

Done. `BAAI/bge-reranker-v2-m3` is now declared the default reranker in all three docs, both pushed fast-forward (no force).

**Files changed**
- `components/knowledgebase/kb-manager/README.md` — reranker bullet now names v2-m3 default with `KB_RERANK_POOL=15` CPU / 30 GPU note; backbone table flipped (v2-m3 production default, MiniLM lightweight fallback via `KB_RERANKER_MODEL=...`); new "Persian support" subsection (BGE-M3 backbone, 100+ langs incl. Persian, MIRACL-`fa`, MKQA, vendor "for multilingual", 568M/2.27GB/XLM-R-Large/Apache-2.0/plain CrossEncoder loader); benchmark table + decision rewritten (MRR 0.496, hit 0.536, top1 0.474; MiniLM 0.493/0.495 fallback; Qwen4B 0.233; bgemma-2B 0.44 @10x). Historical numbers intact.
- Parent `README.md` "Retrieval quality" — same decision flip + new Persian-support paragraph (code refs + `8d0c506` + `:8000` live env).
- `docs/WAVE2_GPU_RUNBOOK.md` — wave-1 ref line tagged "(default since 2026-09-15)", §§8–9 decisions rewritten to v2-m3 default / MiniLM fallback. All benchmark numbers untouched.

**Commits / push status**
- KB (`master`): `fb779e5` — pushed `8d0c506..fb779e5`, fast-forward OK.
- Parent (`main`): `a27673e` — pushed `1937bb5..a27673e`, fast-forward OK.
- No non-fast-forward, no auth failure.

**Hygiene:** staged only the 3 intended files (1 KB + 2 parent). Diff scanned for secrets — clean (only benign "tokenizer/tokenization" matches). Left untouched and uncommitted per hard rules: `kb-manager/data/dense_embeddings.npz` (modified), `kb-source` (modified), `kb-manager/data/reranker_benchmarks/` (untracked), and the parent's pre-existing `components/knowledgebase` gitlink modification (now one commit further behind after the KB push — say the word if you want a follow-up pin-advance commit).

(step-finish: {"reason": "stop", "snapshot": "2fb1804adc7c79d834f219eba2073d4003f2262f", "type": "step-finish", "tokens": {"total": 44836, "input": 372, "output": 531, "reasoning": 44, "cache": {"write": 0, "read": 43889}}, "cost": 0})
