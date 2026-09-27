# Create py venvs install deps (@general subagent)

Session: `ses_f6ad8e88effer0fXVBgn30KyXr`
Messages: 18


## [USER]

Create Python virtualenvs and install the RAG service dependencies. You must actually create venvs and pip-install (not just research).

State: python3.11 available at /usr/bin/python3.11. HF model cache at /workspace/.hf_home (contains sentence-transformers paraphrase-multilingual-MiniLM-L12-v2 and cross-encoder mmarco — set HF_HOME=/workspace/.hf_home and HF_HUB_OFFLINE=1 for pip-era downloads to reuse cache where possible). No proxy env needed. Plenty of disk.

Components (all `requires-python >=3.11`, install with `python3.11 -m venv`):
1. KB: /workspace/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager (pyproject, package `kb_manager`). Service module `kb_manager.web.app:app`. Needs sentence-transformers + torch. To keep it small use CPU torch: FIRST install CPU torch into the venv via `pip install --index-url https://download.pytorch.org/whl/cpu torch` then install the package with `pip install -e .` (sentence-transformers will reuse the torch). Create venv at /tmp/kb-venv.
2. Guardrails: /workspace/Work_Credit-RAG_Phase1/components/guardrails (package `work_rag_guardrails`, module `work_rag_guardrails.api:create_app --factory`). `pip install -e .` into /tmp/guard-venv. If `nemoguardrails` fails to install, SKIP it (service runs in deterministic mode without it: `pip install -e . --no-deps` then add fastapi/uvicorn/httpx/pydantic/pydantic-settings/python-dotenv manually) — report which path you took.
3. Orchestrator: /workspace/Work_Credit-RAG_Phase1/components/orchestrator (package `work_rag_orchestrator`, module `work_rag_orchestrator.api:create_app --factory`). `pip install -e .` into /tmp/orch-venv.

For each venv, after install verify the service module imports:
- KB: `/tmp/kb-venv/bin/python -c "import kb_manager.web.app; print('kb ok')"` (run with cwd=/workspace/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager)
- Guard: `/tmp/guard-venv/bin/python -c "from work_rag_guardrails.api import create_app; print('guard ok')"`
- Orch: `/tmp/orch-venv/bin/python -c "from work_rag_orchestrator.api import create_app; print('orch ok')"`

Constraints: do NOT modify any repo files. If a full `pip install -e .` fails on a heavy dep (torch CUDA pull, nemoguardrails), fall back to minimal runtime deps as described and report exactly what was installed/skipped. Set `HF_HOME=/workspace/.hf_home` and `HF_HUB_OFFLINE=1` in the shell when importing sentence-transformers, so it uses the cache.

Report per component: venv path, python version, install outcome, import check result, and anything skipped. Keep concise.


## [ASSISTANT]

(tool: read)

(tool: read)

(tool: read)


## [ASSISTANT]

(tool: read)

(tool: read)

(tool: read)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)

(tool: bash)

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: read)

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: grep)


## [ASSISTANT]

(tool: read)

(tool: read)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)

(tool: bash)

(tool: bash)


## [ASSISTANT]

(tool: bash)

(tool: read)


## [ASSISTANT]

(tool: bash)
