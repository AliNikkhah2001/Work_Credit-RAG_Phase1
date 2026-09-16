# Orchestrator memory code (@general subagent)

Session: `ses_f6a575eeaffeM2uwbOgHGye6ef`
Messages: 28


## [USER]

Implement stateless conversation memory in the orchestrator repo. Work ONLY in /workspace/Work_Credit-RAG_Phase1/components/orchestrator (branch `feat/reranker-memory`, base cee7a54). Do NOT touch other repos. Do NOT restart services. Commit on the branch when done (identity configured globally); do NOT push.

First READ: src/work_rag_orchestrator/state.py, nodes/validate_input.py, nodes/retrieve.py, nodes/build_context.py, nodes/guarded_generate.py, tracing.py (trace_span helper exists), api.py initial_state (~line 134), graph.py.

Implement (stateless: no DB, no checkpointer changes; WebUI already sends full history in messages):
1. state.py: add `rewritten_query: str` to RAGState; api.py: initialize it to `""`.
2. New helper `src/work_rag_orchestrator/rewrite.py`: `async def rewrite_query(messages, httpx_client=None) -> str` — if 0-1 user turns, return last user message unchanged; else POST to http://127.0.0.1:18000/v1/chat/completions (direct llama-server, model `unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL`, temperature 0, max_tokens 128, `chat_template_kwargs: {"enable_thinking": false}`, timeout 60s) with a Persian system prompt + last 2 exchanges, instructing: output ONLY the standalone rewritten question, no greeting, no explanation. Strip quotes/whitespace from output; on ANY error/timeout fall back to the raw last message (never raise).
3. nodes/retrieve.py: call rewrite_query with state["messages"], store result in state["rewritten_query"], run existing normalization on the REWRITTEN query for KB search (keep original in state["query"] for audit). Add `query-rewrite` span via trace_span(request_id, "query-rewrite", input=last-2-turns, output=rewritten) and include history excerpt in the retrieve span input.
4. nodes/build_context.py: after the system message, append last 2 exchanges (user+assistant pairs, plain text, truncated so history ≤1500 chars total) as a `[Conversation history]` block BEFORE the context question; keep everything within MAX_CONTEXT_CHARS (truncate context first if needed). Keep the existing is_new_chat greeting logic.
5. tests/test_memory_coref.py: regression test with the 3-turn example (turn1 «مدیر شرکت اعتبارسنجی کیه», turn2 «رضا قاسم بور کیه» + assistant answer naming Reza Ghasempour, turn3 «دکتری کجا بوده حالا») asserting rewrite output contains the name (mock the LLM call — do NOT hit :18000 in tests; test the prompt-building + fallback paths). Keep tests runnable offline: `pytest tests/test_memory_coref.py`.
6. Verify: import check (`python -c "import work_rag_orchestrator.rewrite, work_rag_orchestrator.nodes.retrieve"` with PYTHONPATH=src) + run the new test file. Do NOT run live E2E (services are shared).

Guardrails/client code untouched. Commit message: `feat(orch): stateless memory — history rewrite + last-2-turns prompt + spans`. Report: files changed, test results, anything deferred.


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 9756, "input": 3632, "output": 86, "reasoning": 37, "cache": {"write": 0, "read": 6001}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 10456, "input": 279, "output": 587, "reasoning": 5, "cache": {"write": 0, "read": 9585}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 20768, "input": 10772, "output": 142, "reasoning": 13, "cache": {"write": 0, "read": 9841}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(tool: read)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 21039, "input": 305, "output": 141, "reasoning": 0, "cache": {"write": 0, "read": 20593}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 24469, "input": 3480, "output": 68, "reasoning": 72, "cache": {"write": 0, "read": 20849}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(reasoning: )

(reasoning: )

(reasoning: )

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 28424, "input": 801, "output": 239, "reasoning": 3079, "cache": {"write": 0, "read": 24305}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 28563, "input": 3380, "output": 110, "reasoning": 0, "cache": {"write": 0, "read": 25073}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 28905, "input": 336, "output": 168, "reasoning": 0, "cache": {"write": 0, "read": 28401}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 29069, "input": 299, "output": 113, "reasoning": 0, "cache": {"write": 0, "read": 28657}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 29499, "input": 224, "output": 183, "reasoning": 179, "cache": {"write": 0, "read": 28913}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 29779, "input": 517, "output": 145, "reasoning": 76, "cache": {"write": 0, "read": 29041}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 30062, "input": 314, "output": 179, "reasoning": 16, "cache": {"write": 0, "read": 29553}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 30214, "input": 277, "output": 128, "reasoning": 0, "cache": {"write": 0, "read": 29809}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(tool: write)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 31863, "input": 173, "output": 1620, "reasoning": 5, "cache": {"write": 0, "read": 30065}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 32477, "input": 1695, "output": 584, "reasoning": 5, "cache": {"write": 0, "read": 30193}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 32721, "input": 644, "output": 220, "reasoning": 0, "cache": {"write": 0, "read": 31857}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 33047, "input": 248, "output": 177, "reasoning": 125, "cache": {"write": 0, "read": 32497}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 33481, "input": 446, "output": 410, "reasoning": 0, "cache": {"write": 0, "read": 32625}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 33741, "input": 496, "output": 236, "reasoning": 0, "cache": {"write": 0, "read": 33009}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 33970, "input": 372, "output": 164, "reasoning": 41, "cache": {"write": 0, "read": 33393}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(reasoning: )

(reasoning: )

(tool: write)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 37094, "input": 345, "output": 2394, "reasoning": 706, "cache": {"write": 0, "read": 33649}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 37221, "input": 3162, "output": 138, "reasoning": 16, "cache": {"write": 0, "read": 33905}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 37366, "input": 269, "output": 120, "reasoning": 0, "cache": {"write": 0, "read": 36977}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 38005, "input": 601, "output": 140, "reasoning": 31, "cache": {"write": 0, "read": 37233}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 38212, "input": 326, "output": 107, "reasoning": 34, "cache": {"write": 0, "read": 37745}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 38577, "input": 398, "output": 178, "reasoning": 0, "cache": {"write": 0, "read": 38001}}, "cost": 0})

(patch: {"type": "patch", "hash": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "files": ["/workspace/Work_Credit-RAG_Phase1/components/orchestrator"]})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(reasoning: )

Done. Committed `92130f6` on `feat/reranker-memory` (not pushed); no other repos touched, no services restarted.

**Files changed** (orchestrator repo only):
- `src/work_rag_orchestrator/state.py` — added `rewritten_query: str` to `RAGState`.
- `src/work_rag_orchestrator/api.py` — `initial_state` initializes `rewritten_query: ""`.
- `src/work_rag_orchestrator/rewrite.py` *(new)* — `rewrite_query(messages, httpx_client=None)`; 0–1 user turns → last message unchanged with no HTTP; 2+ turns → POST to `http://127.0.0.1:18000/v1/chat/completions` (model `unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL`, temp 0, max_tokens 128, `chat_template_kwargs: {"enable_thinking": false}`, 60s timeout) with Persian system prompt + last-2-exchanges; strips quotes/whitespace; any error/empty → raw last message, never raises. Helpers `last_exchanges_text`, `build_rewrite_prompt`, `clean_rewritten` shared by nodes/tests.
- `src/work_rag_orchestrator/nodes/retrieve.py` — calls `rewrite_query`, stores `state["rewritten_query"]`, runs existing normalization on the rewritten query for KB search (original kept in `state["query"]`); emits `query-rewrite` span plus history excerpt in the `retrieve` span input (using `span_input=`/`span_output=` per the actual `trace_span` signature).
- `src/work_rag_orchestrator/nodes/build_context.py` — appends `[Conversation history]` block (last 2 exchanges, prior turns only, ≤1500 chars) before `Question:`; truncates KB context first to stay within `MAX_CONTEXT_CHARS`; `is_new_chat` greeting logic untouched.
- `tests/test_memory_coref.py` *(new)* — 11 tests on the 3-turn coref scenario, LLM always mocked.

**Test results:** `pytest tests/` → **20 passed** (11 new + 9 existing), plus the `PYTHONPATH=src` import check passes. All offline — no `:18000` calls in tests.

**Deferred / notes:**
- No live E2E run (per instructions, services shared). Real rewrite quality against `:18000` still needs a live check later.
- `pip install pytest pytest-asyncio` into `/tmp/orch-venv` (test tooling only; no service touched or restarted).
- `build_context` keeps the original `state["query"]` in the `Question:` line; the rewritten form reaches generation only via the history block — deliberate, but flag if you want the rewritten question substituted there too.

(step-finish: {"reason": "stop", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 39384, "input": 364, "output": 618, "reasoning": 17, "cache": {"write": 0, "read": 38385}}, "cost": 0})
