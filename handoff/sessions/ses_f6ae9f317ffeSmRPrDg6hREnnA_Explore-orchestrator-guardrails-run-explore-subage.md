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

(step-start: {"snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-start"})

(reasoning: )

I'll explore both submodules and the docs in parallel.

(tool: bash)

(tool: bash)

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-finish", "tokens": {"total": 4646, "input": 771, "output": 291, "reasoning": 0, "cache": {"write": 0, "read": 3584}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-start"})

(reasoning: )

(tool: bash)

(tool: bash)

(tool: read)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-finish", "tokens": {"total": 6159, "input": 1249, "output": 302, "reasoning": 0, "cache": {"write": 0, "read": 4608}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-start"})

(reasoning: )

Now let me read the orchestrator's config, API, graph, clients, pyproject, env.example, and tracing.



(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-finish", "tokens": {"total": 10769, "input": 4133, "output": 492, "reasoning": 0, "cache": {"write": 0, "read": 6144}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-start"})

(reasoning: )

Now let me read the orchestrator's graph, nodes, clients, tracing, state, and schemas.

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-finish", "tokens": {"total": 16527, "input": 5845, "output": 442, "reasoning": 0, "cache": {"write": 0, "read": 10240}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-start"})

(reasoning: )

Now let me read the orchestrator nodes and search for MAX_CHUNKS/MAX_CHARS/UPSTREAM_LLM env usage.

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: grep)

(step-finish: {"reason": "tool-calls", "snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-finish", "tokens": {"total": 22232, "input": 5365, "output": 483, "reasoning": 0, "cache": {"write": 0, "read": 16384}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-start"})

(reasoning: )

Now let me read the guardrails component files.

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-finish", "tokens": {"total": 27522, "input": 4996, "output": 510, "reasoning": 0, "cache": {"write": 0, "read": 22016}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-start"})

(reasoning: )

Now let me read the guardrails' remaining modules and check the observability/langfuse usage.

(tool: read)

(tool: read)

(tool: grep)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-finish", "tokens": {"total": 36580, "input": 8454, "output": 734, "reasoning": 0, "cache": {"write": 0, "read": 27392}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-start"})

(reasoning: )

Now let me examine the docs and parent repo README, plus search for langfuse mentions across the repo.

(tool: read)

(tool: read)

(tool: grep)

(step-finish: {"reason": "tool-calls", "snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-finish", "tokens": {"total": 42258, "input": 5569, "output": 337, "reasoning": 0, "cache": {"write": 0, "read": 36352}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-start"})

(reasoning: )

Let me read the compose file, tracing fallback app, and search the docs for langfuse details.

(tool: read)

(tool: read)

(tool: grep)

(step-finish: {"reason": "tool-calls", "snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-finish", "tokens": {"total": 58399, "input": 15820, "output": 339, "reasoning": 0, "cache": {"write": 0, "read": 42240}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-start"})

(reasoning: )

Let me search the migration doc and MVP plan for langfuse specifics, and check for LANGCHAIN/LANGFUSE tracing env docs.

(tool: grep)

(tool: grep)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-finish", "tokens": {"total": 68563, "input": 9829, "output": 366, "reasoning": 0, "cache": {"write": 0, "read": 58368}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-start"})

(reasoning: )

Let me read the orchestrator schemas.py, guardrails kb README and tests, and search for the tracing collector documentation.

(tool: read)

(tool: read)

(tool: grep)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-finish", "tokens": {"total": 73121, "input": 3910, "output": 859, "reasoning": 0, "cache": {"write": 0, "read": 68352}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-start"})

(reasoning: )

Let me do final verification checks on LANGCHAIN trace env and any remaining details.



(tool: grep)

(tool: read)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-finish", "tokens": {"total": 80451, "input": 6901, "output": 590, "reasoning": 0, "cache": {"write": 0, "read": 72960}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-start"})

(reasoning: )

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
  - **Langfuse tracing env** (read directly via `os.getenv` in `src/work_rag_orchestrator/tracing.py`): `LANGFUSE_HOST` (default `http://127.0.0.1:3000`), `LANGFUSE_PUBLIC_KEY` (default `REDACTED`), `LANGFUSE_SECRET_KEY` (default `REDACTED`), `TRACE_ENABLED` (default `"true"`; any of `0/false/no` disables). No `LANGCHAIN_TRACING_V2`, `LANGFUSE_BASE_URL`, `LANGFUSE_SELF_HOSTED`, or `LANGFUSE_DEBUG` anywhere in the repo. `LANGCHAIN*` is referenced nowhere.

### 2. Langfuse tracing wiring

- File: `src/work_rag_orchestrator/tracing.py`. Two paths, both **non-blocking / best-effort** (failures are logged warnings only):
  1. **Direct HTTP fallback (always fires):** fire-and-forget background thread (`timeout=2.0`) POSTs to `{LANGFUSE_HOST}/api/public/ingestion` with Langfuse SDK-style batches `{"type":"trace-create",...}` (at request start, via `start_trace`) and `{"type":"trace-update",...}` (at response, via `update_trace`).
  2. **SDK (best-effort):** `from langfuse import Langfuse` is tried; the client is constructed with `host=LANGFUSE_HOST`, `public_key=LANGFUSE_PUBLIC_KEY`, `secret_key=LANGFUSE_SECRET_KEY`. No SDK auth handshake required for the fallback collector.
- Call sites: `api.py:122-126` (`start_trace` on `POST /v1/chat/completions`, `request_id` is used as the trace id, honored from optional `X-Request-ID` header) and `api.py:217-232` (`update_trace`). Request id also flows as `thread_id` in the graph config (`api.py:155`).
- **Collector location / port:** `:3000`.
  - Docker (privileged): `compose.mvp.yml` runs `ghcr.io/langfuse/langfuse:2` as service `langfuse`, published `ports: 0.0.0.0:3000:3000`; orchestrator env inside compose is `LANGFUSE_HOST=http://langfuse:3000`. Backed by `langfuse-db` (postgres:15) + `clickhouse`. Project initialized with `REDACTED` / `REDACTED` (lines 148-149).
  - Host fallback (unprivileged Vast): `components/tracing/app.py` — a tiny FastAPI "Langfuse-compatible collector" that implements `POST /api/public/ingestion` (du
…[truncated]…

(step-finish: {"reason": "stop", "snapshot": "152702dee6e4141b3119f30d651be1ccbc7351af", "type": "step-finish", "tokens": {"total": 92115, "input": 3247, "output": 8740, "reasoning": 0, "cache": {"write": 0, "read": 80128}}, "cost": 0})
