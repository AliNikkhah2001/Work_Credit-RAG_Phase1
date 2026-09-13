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

(tool: read)


## [ASSISTANT]

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: read)

(tool: read)


## [ASSISTANT]

(tool: read)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: write)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: write)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

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
