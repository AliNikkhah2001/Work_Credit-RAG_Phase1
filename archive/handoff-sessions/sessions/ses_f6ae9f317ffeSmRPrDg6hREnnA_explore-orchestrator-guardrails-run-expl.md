# Explore orchestrator+guardrails run (@explore subagent)

Session: `ses_f6ae9f317ffeSmRPrDg6hREnnA`
Messages: 14


## [USER]

Explore two submodules of a RAG project:
- /workspace/Work_Credit-RAG_Phase1/components/orchestrator (HEAD at 058ac21)
- /workspace/Work_Credit-RAG_Phase1/components/guardrails (HEAD at 730b634)

I need the exact way to run these services and how they connect. Report precisely:

ORCHESTRATOR (/workspace/Work_Credit-RAG_Phase1/components/orchestrator):
1. Web app module path (e.g. `work_rag_orchestrator.api:create_app --factory`), host/port defaults, env vars: KB_BASE_URL, GUARDRAILS_BASE_URL, UPSTREAM_LLM_BASE_URL, UPSTREAM_LLM_MODEL, MAX_CHUNKS, MAX_CHARS, LANGCHAIN/LANGFUSE tracing env.
2. How Langfuse tracing is wired: look for `langfuse`, `langsmith`, `tracing`, `trace` in src. What env vars control it (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST, LANGFUSE_BASE_URL, LANGFUSE_SELF_HOSTED...)? Is the tracing collector at some port? Read the parent repo docs /workspace/Work_Credit-RAG_Phase1/docs for "langfuse" mentions too.
3. The LangGraph graph structure: nodes (validate_input, retrieve, build_context, guarded_generate, format_response) and where they call KB/guardrails.
4. What teardown is needed: any postgres checkpointer? (README says checkpoints are excluded from MVP — confirm no postgres needed.)
5. Python version + requirements.

GUARDRAILS (/workspace/Work_Credit-RAG_Phase1/components/guardrails):
1. Web app module path (e.g. `work_rag_guardrails.api:create_app --factory`), host/port, env vars: GUARDRAILS_HOST, GUARDRAILS_PORT, UPSTREAM_LLM_BASE_URL, LLM_BASE_URL alias.
2. Endpoints: /v1/rails/check, /health, /ready — request/response shapes.
3. Does it need internet/LLM to start, or only to run semantic checks? Confirm it can start with upstream LLM unreachable.
4. Python version + requirements.

Also check /workspace/Work_Credit-RAG_Phase1/docs/ (RUNBOOK_VAST.md, VAST_GEMMA4_MIGRATION.md, MVP_INTEGRATION_PLAN.md) and the parent README for the documented startup sequence and ports (KB :8000/8004, guardrails :8200, orchestrator :8100, open-webui :13000, langfuse :3000).

Do NOT write or modify any files. Read-only. Return a concise structured report: exact uvicorn commands, all env vars, endpoint shapes, and any langfuse config details (URLs/ports/keys from docs or defaults).


## [ASSISTANT]

I'll explore both submodules and the docs in parallel.

(tool: bash)

(tool: bash)

(tool: bash)


## [ASSISTANT]

(tool: bash)

(tool: bash)

(tool: read)

(tool: read)


## [ASSISTANT]

Now let me read the orchestrator's config, API, graph, clients, pyproject, env.example, and tracing.



(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)


## [ASSISTANT]

Now let me read the orchestrator's graph, nodes, clients, tracing, state, and schemas.

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)


## [ASSISTANT]

Now let me read the orchestrator nodes and search for MAX_CHUNKS/MAX_CHARS/UPSTREAM_LLM env usage.

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: grep)


## [ASSISTANT]

Now let me read the guardrails component files.

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)


## [ASSISTANT]

Now let me read the guardrails' remaining modules and check the observability/langfuse usage.

(tool: read)

(tool: read)

(tool: grep)

(tool: read)


## [ASSISTANT]

Now let me examine the docs and parent repo README, plus search for langfuse mentions across the repo.

(tool: read)

(tool: read)

(tool: grep)


## [ASSISTANT]

Let me read the compose file, tracing fallback app, and search the docs for langfuse details.

(tool: read)

(tool: read)

(tool: grep)


## [ASSISTANT]

Let me search the migration doc and MVP plan for langfuse specifics, and check for LANGCHAIN/LANGFUSE tracing env docs.

(tool: grep)

(tool: grep)

(tool: read)


## [ASSISTANT]

Let me read the orchestrator schemas.py, guardrails kb README and tests, and search for the tracing collector documentation.

(tool: read)

(tool: read)

(tool: grep)

(tool: read)


## [ASSISTANT]

Let me do final verification checks on LANGCHAIN trace env and any remaining details.



(tool: grep)

(tool: read)

(tool: read)


## [ASSISTANT]

I have everything needed. Here is the structured report.

---

# RAG Components — Run & Connect Report

All paths verified against working tree at the two HEADs (orchestrator `058ac21`, guardrails `730b634`) plus parent repo docs and `compose.mvp.yml`.

---

## ORCHESTRATOR — `/workspace/Work_Credit-RAG_Phase1/components/orchestrator` (HEAD `058ac21`)

### 1. Web app / run commands / ports / env

- **Module path:** `work_rag_orchestrator.api:create_app` with `--factory` (this is what `main()` in `api.py:263-274` passes to uvicorn, and what the docs use). Also runnable via `python -m work_rag_orchestrator.api` (Dockerfile `CMD`) or console script `orchestrator`.
- **Defaults (from `src/work_rag_orchestrator/config.py`):**
  - `ORCHESTRATOR_HOST` default `0.0.0.0`, `ORCHESTRATOR_PORT` default `8100`
  - `KB_BASE_URL` default `http://127.0.0.1:8000`
  - `GUARDRAILS_BASE_URL` default `http://127.0.0.1:8200`
  - `REQUEST_TIMEOUT_SECONDS` default `120`, `RETRIEVAL_TOP_K` default `5`
  - `UPSTREAM_LLM_MODEL` default `unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL`
- **Env vars requested — what actually exists:**
  - `KB_BASE_URL`, `GUARDRAILS_BASE_URL`, `ORCHESTRATOR_HOST/PORT`, `REQUEST_TIMEOUT_SECONDS`, `RETRIEVAL_TOP_K`, `UPSTREAM_LLM_MODEL` ✓
  - **`UPSTREAM_LLM_BASE_URL`: does NOT exist in the orchestrator.** The orchestrator never calls the LLM directly — it calls guardrails (`/v1/chat/completions`), which owns the upstream LLM. Only `UPSTREAM_LLM_MODEL` is read, and is passed as `request.model` to guardrails (`guarded_generate.py:27-32`).
  - **`MAX_CHUNKS` / `MAX_CHARS`: NOT env vars.** They are **hardcoded module constants** in `src/work_rag_orchestrator/nodes/build_context.py`: `MAX_CHUNKS = 5`, `MAX_CONTEXT_CHARS = 6000` (lines 11-12, 27, 48-49). Older docs mention `MAX_CHUNKS 3, MAX_CHARS 4000` (historical tuning; parent README still says "MAX_CHUNKS 3, MAX_CHARS 4000" but the code at HEAD is 5/6000 — the 6000-char Persian prompt is current).
  - **Langfuse tracing env** (read directly via `os.getenv` in `src/work_rag_orchestrator/tracing.py`): `LANGFUSE_HOST` (default `http://127.0.0.1:3000`), `LANGFUSE_PUBLIC_KEY` (default `pk-lf-mvp-local`), `LANGFUSE_SECRET_KEY` (default `sk-lf-mvp-local`), `TRACE_ENABLED` (default `"true"`; any of `0/false/no` disables). No `LANGCHAIN_TRACING_V2`, `LANGFUSE_BASE_URL`, `LANGFUSE_SELF_HOSTED`, or `LANGFUSE_DEBUG` anywhere in the repo. `LANGCHAIN*` is referenced nowhere.

### 2. Langfuse tracing wiring

- File: `src/work_rag_orchestrator/tracing.py`. Two paths, both **non-blocking / best-effort** (failures are logged warnings only):
  1. **Direct HTTP fallback (always fires):** fire-and-forget background thread (`timeout=2.0`) POSTs to `{LANGFUSE_HOST}/api/public/ingestion` with Langfuse SDK-style batches `{"type":"trace-create",...}` (at request start, via `start_trace`) and `{"type":"trace-update",...}` (at response, via `update_trace`).
  2. **SDK (best-effort):** `from langfuse import Langfuse` is tried; the c
…[truncated]…
