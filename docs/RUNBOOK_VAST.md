# Vast.ai Runbook — Work Credit RAG Phase 1

This is the single-host runbook for the Vast.ai VM where **Gemma 4 31B is already running** at `http://127.0.0.1:18000/v1` (llama.cpp, `unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL`). Do not launch another Gemma.

## Architecture (Vast)

```
Open WebUI :13000  →  Orchestrator :8100  →  Guardrails :8200  →  KB :8004 → (BM25+dense+RRF+reranker)
                          ↓                     ↓
                    Guardrails :8200  →  Gemma :18000 (external llama-server)
```

KB uses SQLite `kb-manager/data/kb_test.db` (69 docs, 2399 chunks, 977 MiB) — no Postgres required for Vast smoke test. For prod Postgres, use `docker-compose.vast.yml`.

## Prerequisites

```bash
# Vast VM (2× RTX 6000 Ada, 49 GiB each, CUDA 13.2, driver 595.58.03)
python3 --version   # 3.12.13
pip --version       # 26.x
git --version       # 2.43.0
# Docker optional — only for pgvector/qdrant/milvus/webui
# Check Gemma already running:
curl -s http://127.0.0.1:18000/v1/models | jq .data[0].id
curl -s http://127.0.0.1:18000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL","messages":[{"role":"user","content":"Hello"}],"max_tokens":5}' | jq .
```

## Clone (recursive, pinned)

```bash
git clone --recurse-submodules https://github.com/AliNikkhah2001/Work_Credit-RAG_Phase1.git
cd Work_Credit-RAG_Phase1
git switch -c vast-gemma4-migration  # or your working branch
git submodule sync --recursive && git submodule update --init --recursive
git submodule status --recursive
# expects:
#  +3ae7b1e knowledgebase (vast) + 9a519f6 fix
#  +29ceb7b guardrails (vast) + 8152132 fix
#  +bb88557 orchestrator (vast) + bcdaeea fix
#  +e080a81 server-setup (vast) + 5d5a7e4
```

## Install (host venvs, no Docker required for RAG)

```bash
# KB
python3 -m venv /tmp/kb-venv
/tmp/kb-venv/bin/pip install -e components/knowledgebase/kb-manager[dev]
/tmp/kb-venv/bin/pip install aiosqlite matplotlib
# first run ingests 78 XLSX → data/kb_test.db (if missing)
KB_DB_URL="sqlite+aiosqlite:///./data/kb_test.db" KB_SOURCE_DIR="$PWD/components/knowledgebase/kb-source/clean_files" \
  /tmp/kb-venv/bin/python -m kb_manager.cli ingest --full   # ~5 min, needs HF model download first search
# Guardrails
python3 -m venv /tmp/guard-venv
/tmp/guard-venv/bin/pip install -e components/guardrails
# Orchestrator
python3 -m venv /tmp/orch-venv
/tmp/orch-venv/bin/pip install -e components/orchestrator
```

## Startup Order (dependency-first)

```bash
# 1. KB (SQLite, 8004 — 8000 is taken by caddy on this Vast)
KB_DB_URL="sqlite+aiosqlite://$PWD/components/knowledgebase/kb-manager/data/kb_test.db" \
  KB_WEB_HOST=127.0.0.1 KB_WEB_PORT=8004 \
  /tmp/kb-venv/bin/python -m uvicorn kb_manager.web.app:app --host 127.0.0.1 --port 8004 &

# 2. Guardrails → Gemma 18000 (env-driven, no proxy)
PYTHONPATH=components/guardrails/src \
  UPSTREAM_LLM_BASE_URL=http://127.0.0.1:18000/v1 \
  UPSTREAM_LLM_MODEL=unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL \
  /tmp/guard-venv/bin/python -m uvicorn work_rag_guardrails.api:create_app --factory --host 127.0.0.1 --port 8200 &

# 3. Orchestrator (KB 8004 + Guardrails 8200)
PYTHONPATH=components/orchestrator/src \
  KB_BASE_URL=http://127.0.0.1:8004 GUARDRAILS_BASE_URL=http://127.0.0.1:8200 \
  UPSTREAM_LLM_MODEL=unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL \
  /tmp/orch-venv/bin/python -m uvicorn work_rag_orchestrator.api:create_app --factory --host 127.0.0.1 --port 8100 &

# Wait for readiness (no sleep loops — poll)
for p in 8004 8200 8100; do until curl -s http://127.0.0.1:$p/health | grep ok; do sleep 2; done; echo "$p ok"; done
curl -s http://127.0.0.1:8100/ready | jq .  # both deps ready
```

## Health Checks

```bash
curl -s http://127.0.0.1:8004/search/api -H "Content-Type: application/json" -d '{"query":"اعتبارسنجی چیست؟","top_k":3}' | jq .final_results[0].content_preview
curl -s http://127.0.0.1:8200/health; curl -s http://127.0.0.1:8200/ready | jq .
curl -s http://127.0.0.1:8100/health; curl -s http://127.0.0.1:8100/ready | jq .
curl -s http://127.0.0.1:18000/v1/models | jq .data[0].id
```

## Tests

```bash
# KB (32 passed, 5 known failures: cli version, ragas missing, parser schema)
KB_DB_URL=sqlite+aiosqlite:///./data/kb_test.db /tmp/kb-venv/bin/python -m pytest components/knowledgebase/kb-manager/tests -v

# Guardrails (6 passed before fix, 5 pre-existing failures; after fix 8+)
/tmp/guard-venv/bin/python -m pytest components/guardrails/tests -v

# Orchestrator (9 passed)
PYTHONPATH=components/orchestrator/src /tmp/orch-venv/bin/python -m pytest components/orchestrator/tests -v

# E2E (orchestrator chat)
/tmp/e2e.sh  # or:
curl -s http://127.0.0.1:8100/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL","messages":[{"role":"user","content":"سلام، امتیاز اعتباری چیست؟"}],"max_tokens":80}' | jq .rag.citations
```

## Ports (Vast)

| Service | Host:Port | Container | Notes |
|---|---|---|---|
| Gemma (existing) | 127.0.0.1:18000 | llama-server pid 676 | `GET /v1/models`, `POST /v1/chat` |
| KB | 127.0.0.1:8004 | host uvicorn | `POST /search/api` (8000 taken by caddy) |
| Guardrails | 127.0.0.1:8200 | host uvicorn | `POST /v1/rails/check`, `POST /v1/chat` |
| Orchestrator | 127.0.0.1:8100 | host uvicorn | `POST /v1/chat/completions` public |
| Open WebUI | 127.0.0.1:13000 | optional `ghcr.io/open-webui` | `OPENAI_API_BASE_URL=http://host.docker.internal:8100/v1` |

## Environment Variables (Vast)

```
# KB
KB_DB_URL=sqlite+aiosqlite:///./data/kb_test.db
KB_SOURCE_DIR=components/knowledgebase/kb-source/clean_files
KB_WEB_HOST=127.0.0.1 KB_WEB_PORT=8004
KB_EMBED_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

# Guardrails
UPSTREAM_LLM_BASE_URL=http://127.0.0.1:18000/v1
UPSTREAM_LLM_MODEL=unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL
UPSTREAM_LLM_API_KEY=sk-local-dev  # ignored by llama.cpp
GUARDRAILS_PORT=8200

# Orchestrator
KB_BASE_URL=http://127.0.0.1:8004
GUARDRAILS_BASE_URL=http://127.0.0.1:8200
UPSTREAM_LLM_MODEL=unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL
ORCHESTRATOR_PORT=8100
REQUEST_TIMEOUT_SECONDS=120
RETRIEVAL_TOP_K=5
```

## tmux Workflow

```bash
tmux new -s rag
# pane 0: KB 8004
# pane 1: guardrails 8200
# pane 2: orchestrator 8100
# pane 3: logs / tests
```

## Troubleshooting

- **8000 busy** → KB uses 8004 on Vast (caddy on *:8000). Set `KB_WEB_PORT=8004` and `KB_BASE_URL=http://127.0.0.1:8004`.
- **Guardrails blocks Persian** → fixed `actions.py` jailbreak `دان` word-boundary (was substring). Re-pip install guardrails after pull.
- **Orchestrator timeout** → was `max_tokens 4000` → now 512, `MAX_CHUNKS 3/4000` chars. Increase timeout if RTX 6000 slower.
- **Gemma <unused> tokens** → model returns control tokens for system-heavy prompts; try shorter context or different temp. Pipeline still returns citations.
- **DB missing** → `kb_test.db` is gitignored; run `kb_manager.cli ingest --full` or restore from `versions/v1/kb_export.json` (compact).
- **Dense cache** → `dense_embeddings.npz` regenerated per DB; ignore diff.

## Git / Submodule Workflow

Per `README.md:88-96`: change in owning repo → PR → bump parent gitlink one repo at a time → run `tests/e2e`.

Branch for Vast: `vast-gemma4-migration` in parent + 4 submodules. Push with:

```bash
cd components/knowledgebase && git push origin vast-gemma4-migration
cd ../guardrails && git push origin vast-gemma4-migration
cd ../orchestrator && git push origin vast-gemma4-migration
cd ../server-setup && git push origin vast-gemma4-migration
cd ../.. && git add components/* docs/* && git push origin vast-gemma4-migration
```

## Known Limitations (Vast)

- KB DB is SQLite 977 MiB (2399 chunks) — smaller than prod 8291 chunks (some XLSX failed schema).
- Gemma output quality: returns `<unused*>` for some Persian prompts (llama.cpp chat template mismatch) — RAG citations still prove retrieval.
- No Docker required for MVP; pgvector/qdrant/milvus not started (setups via `docker-compose.vast.yml` if needed).
- Open WebUI not started on this Vast (optional).
