# AGENTS.md — Agent Operating Manual (umbrella repo)

## 1. Repo map + ownership

Umbrella repo; implementation lives in submodules. Do NOT duplicate component code in parent.

| Path | Repo / branch | Owns |
|---|---|---|
| `components/server-setup` | Work_RAG-Server-Setup `main` | hardware, model lifecycle, infra |
| `components/knowledgebase` | Work_RAG-KB `master` | ingestion, retrieval, reranking (kb-manager) |
| `components/guardrails` | Work_RAG-Guardrails `main` | policy, guarded Gemma |
| `components/orchestrator` | Work_RAG-Orchestrator `main` | graph state, adapters, public API |
| `components/tracing` | parent (not a submodule) | fallback trace collector `:3000` |
| parent root | this repo | pins, integrated startup (`deploy/vast/`), E2E |

`.gitmodules` pins each submodule to `branch = main` except knowledgebase (`master`).

## 2. Service table (instance 50713720, 2026-09-12, 1x RTX 3090)

| Svc | Dir / module | venv | Port | Key env |
|---|---|---|---|---|
| llama-server | `/workspace/llama.cpp-src/build-cuda/bin/llama-server` | — | 18000 (127.0.0.1 only) | `--ctx-size 8192 --temp 0.2 --no-mmproj --jinja -ngl 999`, `MODEL=.../gemma-4-31B-it-UD-Q4_K_XL.gguf` |
| KB | `components/knowledgebase/kb-manager`, `kb_manager.web.app:app` | `/tmp/kb-venv` (py3.11) | 8000 (0.0.0.0) | `KB_DB_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/kb_manager` |
| guardrails | `components/guardrails`, `work_rag_guardrails.api:create_app --factory` | `/tmp/guard-venv` | 8200 (0.0.0.0) | `UPSTREAM_LLM_BASE_URL=http://127.0.0.1:18000/v1`, `MODEL=unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL` |
| orchestrator | `components/orchestrator`, `work_rag_orchestrator.api:create_app --factory` | `/tmp/orch-venv` | 8100 (0.0.0.0) | `KB_BASE_URL=http://127.0.0.1:8000`, `GUARDRAILS_BASE_URL=http://127.0.0.1:8200`, `LANGFUSE_HOST=http://127.0.0.1:3001` + keys from `/tmp/opencode/langfuse.env` |
| WebUI | `open-webui serve` | `/tmp/webui-venv` | 13000 (0.0.0.0) | `OPENAI_API_BASE_URL=http://127.0.0.1:8100/v1`, `OPENAI_API_KEY=sk-local-dev`, `WEBUI_AUTH=false`, `DATA_DIR=/tmp/webui-data` |
| collector (fallback) | `components/tracing/app.py`, `app:app` | `/tmp/orch-venv` | 3000 (0.0.0.0) | JSONL `/tmp/langfuse_traces.jsonl` |
| Langfuse v2 UI (real) | `/tmp/langfuse-src` (`bash deploy/vast/langfuse-v2.sh`) | node 22 | 3001 (0.0.0.0) | seeded admin + keys in `/tmp/opencode/langfuse.env` (mode 600) |
| Studio API | `components/orchestrator` (`bash deploy/vast/studio.sh`) | `/tmp/orch-venv` | 2024 (0.0.0.0) | panel `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024` |
| postgres 14 + pgvector | system cluster | — | 5432 | DBs `kb_manager`, `langfuse`; `KB_DB_URL` must be set explicitly or KB silently falls back to SQLite |

Models cache: `/tmp/hf_clean`. `HF_HOME` AND `HF_HUB_CACHE` must BOTH point there (hub 1.x reads `$HF_HOME/hub`). `HF_HUB_OFFLINE=1`.

Full startup order: postgres → Gemma → KB → guardrails → collector → orchestrator → WebUI = `bash deploy/vast/start.sh`.

## 3. Standard workflows

Health check (or `bash deploy/vast/health.sh`):

```bash
for p in 18000 8000 8200 8100; do printf "%s: " "$p"; curl -s --max-time 8 http://127.0.0.1:$p/health | head -c 120; echo; done
curl -s --max-time 8 http://127.0.0.1:8100/ready | head -c 300; echo
curl -s --max-time 8 http://127.0.0.1:8200/ready | head -c 300; echo
curl -s --max-time 8 http://127.0.0.1:3000/api/public/health; echo
curl -s --max-time 10 http://127.0.0.1:2024/ok; echo
curl -s --max-time 10 http://127.0.0.1:3001/api/public/health; echo
PGPASSWORD=postgres psql -h 127.0.0.1 -U postgres -d kb_manager -tAc "SELECT count(*) FROM chunks;"
```

Restart ONE service (example: guardrails):

```bash
fuser -k 8200/tcp; sleep 3
cd /workspace/Work_Credit-RAG_Phase1
PYTHONPATH=$PWD/components/guardrails/src GUARDRAILS_HOST=0.0.0.0 GUARDRAILS_PORT=8200 \
  UPSTREAM_LLM_BASE_URL=http://127.0.0.1:18000/v1 UPSTREAM_LLM_MODEL=unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL \
  nohup /tmp/guard-venv/bin/python -m uvicorn work_rag_guardrails.api:create_app --factory \
  --host 0.0.0.0 --port 8200 > /tmp/guard.log 2>&1 &
curl -s http://127.0.0.1:8200/health
```

Full restart:

```bash
bash deploy/vast/stop.sh
bash deploy/vast/start.sh
bash deploy/vast/health.sh
```

E2E smoke:

```bash
curl -s http://127.0.0.1:8100/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"سلام"}]}' | head -c 400; echo
curl -s http://127.0.0.1:8100/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"اعتبارسنجی چیست؟"}]}' | jq -c '{finish:.choices[0].finish_reason, citations:(.rag.citations|length)}'
curl -s http://127.0.0.1:8200/v1/rails/check -H 'Content-Type: application/json' \
  -d '{"stage":"input","text":"سلام","request_id":"t"}' | jq .
curl -s http://127.0.0.1:8000/search/api -H 'Content-Type: application/json' \
  -d '{"query":"اعتبارسنجی چیست","top_k":3}' | jq -c '.final_results[0].content_preview[0:120]'
```

View traces:

```bash
tail -5 /tmp/langfuse_traces.jsonl   # fallback collector :3000
set -a; . /tmp/opencode/langfuse.env; set +a  # real v2 UI :3001 keys
curl -s -u "$LANGFUSE_INIT_PROJECT_PUBLIC_KEY:$LANGFUSE_INIT_PROJECT_SECRET_KEY" \
  "http://127.0.0.1:3001/api/public/traces?limit=5" | head -c 600; echo
# or browser via tunnel: http://localhost:3001 (login admin@local.test)
```

Studio run:

```bash
bash deploy/vast/studio.sh  # API :2024
# panel: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
# run input MUST include request_id: {"request_id":"studio-001","messages":[{"role":"user","content":"سلام"}]}
```

## 4. Git rules

- Parent pins submodules to exact commits (gitlinks). Check: `git submodule status --recursive`.
- Component fix → commit+push on that repo's `vast-gemma4-migration`, then advance the pin with a parent commit.
- Deployment-only material (deploy/, docs/, eval/) → parent `vast-deploy` / `release` branches.
- Never force-push. Never commit secrets (`*.env`, tokens, passwords, `/tmp/opencode/langfuse.env`) or generated artifacts (`*.npz`, `__pycache__`, `*.log`, venvs).

## 5. Vast gotchas

- Unprivileged container: NO docker. Host venvs only; `compose.mvp.yml` is for privileged hosts.
- NAT ports fixed at creation: new direct mappings impossible. Public access = SSH tunnels: `ssh -p <ssh_port> root@<ssh_host> -L 13000:localhost:13000 -L 8100:localhost:8100 -L 3000:localhost:3000 -L 3001:localhost:3001 -L 2024:localhost:2024`.
- Gemma `:18000` stays loopback-only (127.0.0.1) by design; never expose publicly.
- Phantom overlay dentries: `/workspace/.hf_home` looks populated but is empty phantom dentries — real cache is `/tmp/hf_clean`.
- HF cache layout: set BOTH `HF_HOME=/tmp/hf_clean` and `HF_HUB_CACHE=/tmp/hf_clean`.
- asyncpg loop bug (fixed in KB working tree): `search_api` must `await search_knowledge_base` directly, NOT via `asyncio.to_thread(...)` (thread-hop breaks the pool: "attached to a different loop"). Empty search + that error → check the fix is present.
- Langfuse v2 envelope: top-level `id` + ISO `timestamp`; updates via same-id `trace-create` (no `trace-update` in v2). SDK v4 pydantic shape is incompatible — direct-HTTP path in orchestrator `tracing.py` is authoritative.
- Gemma needs `chat_template_kwargs:{"enable_thinking":false}` + `--no-mmproj --jinja` or `<unused*>` leaks return.
- VRAM 22.7/24 GB at ctx 8192; OOM under load → restart llama-server with `--ctx-size 4096`.

## 6. Never do

- Never `pkill python` (kills everything). Use `bash deploy/vast/stop.sh` (port-scoped `fuser -k`).
- Never launch gemma-manager or download another GGUF (Gemma is external `:18000`).
- Never expose `:18000`, postgres, or redis publicly.
- Never commit `.env` / secrets / `*.npz` / logs / venvs.
- Never force-push any repo.
- Never run Docker on this unprivileged host (fails on `unshare`/iptables).
- Never set only one of `HF_HOME`/`HF_HUB_CACHE`.
- Never omit `request_id` in Studio run inputs.
