# COMMANDS.md — Vast.ai command reference (instance 50713720, 2026-09-12, 1x RTX 3090)

Copy-pasteable. Root = `/workspace/Work_Credit-RAG_Phase1`. All RAG services bind `0.0.0.0` except Gemma (`127.0.0.1:18000` by design).

## 0. Prerequisites

```bash
python3 --version            # 3.11 for /tmp/*-venv
git --version
curl --version
nvidia-smi                   # 1x RTX 3090 24GB
pg_lsclusters                # postgres 14 + pgvector expected
ls /tmp/kb-venv /tmp/guard-venv /tmp/orch-venv /tmp/webui-venv
ls /workspace/llama.cpp-src/build-cuda/bin/llama-server
ls /tmp/hf_clean             # real models cache (NOT /workspace/.hf_home)
```

Build venvs (if missing):

```bash
python3.11 -m venv /tmp/kb-venv && /tmp/kb-venv/bin/pip install -e components/knowledgebase/kb-manager
python3.11 -m venv /tmp/guard-venv && /tmp/guard-venv/bin/pip install -e components/guardrails
python3.11 -m venv /tmp/orch-venv && /tmp/orch-venv/bin/pip install -e components/orchestrator
python3.11 -m venv /tmp/webui-venv && /tmp/webui-venv/bin/pip install open-webui
```

Postgres + pgvector (system cluster, DBs `kb_manager` + `langfuse`):

```bash
pg_lsclusters || pg_ctlcluster 14 main start
PGPASSWORD=postgres psql -h 127.0.0.1 -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='kb_manager'" | grep -q 1 \
  || PGPASSWORD=postgres psql -h 127.0.0.1 -U postgres -c "CREATE DATABASE kb_manager"
PGPASSWORD=postgres psql -h 127.0.0.1 -U postgres -d kb_manager -c "CREATE EXTENSION IF NOT EXISTS vector;"
PGPASSWORD=postgres psql -h 127.0.0.1 -U postgres -d kb_manager -tAc "SELECT count(*) FROM chunks;"
```

Models (no download on this host — Gemma GGUF already cached):

```bash
ls -la /tmp/hf_clean/ | head
# expected: models--unsloth--gemma-4-31B-it-GGUF/.../gemma-4-31B-it-UD-Q4_K_XL.gguf (18.8 GB)
```

## 1. Env exports (every shell)

```bash
cd /workspace/Work_Credit-RAG_Phase1
export HF_HOME=/tmp/hf_clean HF_HUB_CACHE=/tmp/hf_clean HF_HUB_OFFLINE=1
export KB_DB_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/kb_manager"
export MODEL=/tmp/hf_clean/models--unsloth--gemma-4-31B-it-GGUF/snapshots/c1ac76e99d5513b141e8adde7288b85c3f9c32ec/gemma-4-31B-it-UD-Q4_K_XL.gguf
```

## 2. Per-service start (order matters; or just `bash deploy/vast/start.sh`)

```bash
# 0. postgres
pg_lsclusters || pg_ctlcluster 14 main start

# 1. Gemma :18000 (loopback only, ~45s warmup)
nohup /workspace/llama.cpp-src/build-cuda/bin/llama-server --model "$MODEL" \
  --port 18000 --ctx-size 8192 --temp 0.2 --no-mmproj --jinja -ngl 999 \
  > /tmp/llama-server.log 2>&1 &
sleep 45; curl -s http://127.0.0.1:18000/health || tail -20 /tmp/llama-server.log

# 2. KB :8000
cd /workspace/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager
KB_DB_URL="$KB_DB_URL" KB_WEB_HOST=0.0.0.0 KB_WEB_PORT=8000 \
  nohup /tmp/kb-venv/bin/python -m uvicorn kb_manager.web.app:app \
  --host 0.0.0.0 --port 8000 > /tmp/kb.log 2>&1 &
sleep 20; curl -s http://127.0.0.1:8000/health

# 3. Guardrails :8200
cd /workspace/Work_Credit-RAG_Phase1
PYTHONPATH=$PWD/components/guardrails/src GUARDRAILS_HOST=0.0.0.0 GUARDRAILS_PORT=8200 \
  UPSTREAM_LLM_BASE_URL=http://127.0.0.1:18000/v1 \
  UPSTREAM_LLM_MODEL=unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL \
  nohup /tmp/guard-venv/bin/python -m uvicorn work_rag_guardrails.api:create_app --factory \
  --host 0.0.0.0 --port 8200 > /tmp/guard.log 2>&1 &
sleep 10; curl -s http://127.0.0.1:8200/health

# 4. Fallback collector :3000
cd /workspace/Work_Credit-RAG_Phase1/components/tracing
nohup /tmp/orch-venv/bin/python -m uvicorn app:app \
  --host 0.0.0.0 --port 3000 > /tmp/langfuse.log 2>&1 &
sleep 6; curl -s http://127.0.0.1:3000/api/public/health; echo

# 5. Orchestrator :8100 (real Langfuse v2 :3001 keys if present)
cd /workspace/Work_Credit-RAG_Phase1
[ -f /tmp/opencode/langfuse.env ] && { set -a; . /tmp/opencode/langfuse.env; set +a; }
PYTHONPATH=$PWD/components/orchestrator/src KB_BASE_URL=http://127.0.0.1:8000 \
  GUARDRAILS_BASE_URL=http://127.0.0.1:8200 \
  UPSTREAM_LLM_MODEL=unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL \
  LANGFUSE_HOST="${LANGFUSE_HOST:-http://127.0.0.1:3001}" \
  LANGFUSE_PUBLIC_KEY="${LANGFUSE_INIT_PROJECT_PUBLIC_KEY:-}" \
  LANGFUSE_SECRET_KEY="${LANGFUSE_INIT_PROJECT_SECRET_KEY:-}" \
  nohup /tmp/orch-venv/bin/python -m uvicorn work_rag_orchestrator.api:create_app --factory \
  --host 0.0.0.0 --port 8100 > /tmp/orch.log 2>&1 &
sleep 10; curl -s http://127.0.0.1:8100/health

# 6. WebUI :13000
OPENAI_API_BASE_URL=http://127.0.0.1:8100/v1 OPENAI_API_KEY=sk-local-dev WEBUI_AUTH=false \
  DATA_DIR=/tmp/webui-data \
  nohup /tmp/webui-venv/bin/open-webui serve --host 0.0.0.0 --port 13000 > /tmp/webui.log 2>&1 &
sleep 15; curl -s http://127.0.0.1:13000 | head -c 100; echo

# Optional panels
bash deploy/vast/langfuse-v2.sh   # real Langfuse v2 UI :3001
bash deploy/vast/studio.sh        # LangGraph Studio API :2024
```

## 3. Health / ready checks

```bash
bash deploy/vast/health.sh
# manual:
for p in 18000 8000 8200 8100; do printf "%s: " "$p"; curl -s --max-time 8 http://127.0.0.1:$p/health | head -c 120; echo; done
curl -s --max-time 8 http://127.0.0.1:8100/ready | head -c 300; echo
curl -s --max-time 8 http://127.0.0.1:8200/ready | head -c 300; echo
curl -s --max-time 8 http://127.0.0.1:3000/api/public/health; echo
curl -s --max-time 10 http://127.0.0.1:2024/ok; echo
curl -s --max-time 10 http://127.0.0.1:3001/api/public/health; echo
curl -s --max-time 8 http://127.0.0.1:18000/v1/models | head -c 200; echo
PGPASSWORD=postgres psql -h 127.0.0.1 -U postgres -d kb_manager -tAc "SELECT count(*) FROM chunks;"
```

## 4. E2E curls

```bash
# greeting (RAG)
curl -s http://127.0.0.1:8100/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"سلام"}]}' | jq -c '{finish:.choices[0].finish_reason, text:.choices[0].message.content[0:120], citations:(.rag.citations|length)}'

# credit question (RAG + citations)
curl -s http://127.0.0.1:8100/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"اعتبارسنجی چیست؟"}]}' | jq -c '{finish:.choices[0].finish_reason, citations:(.rag.citations|length)}'

# rails check
curl -s http://127.0.0.1:8200/v1/rails/check -H 'Content-Type: application/json' \
  -d '{"stage":"input","text":"سلام","request_id":"t"}' | jq .

# KB search
curl -s http://127.0.0.1:8000/search/api -H 'Content-Type: application/json' \
  -d '{"query":"اعتبارسنجی چیست","top_k":3}' | jq -c '.final_results[0].content_preview[0:120]'

# raw Gemma (must be clean Persian, enable_thinking:false)
curl -s http://127.0.0.1:18000/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL","messages":[{"role":"user","content":"سلام"}],"temperature":0,"max_tokens":50,"chat_template_kwargs":{"enable_thinking":false}}' | jq .choices[0].message.content
```

## 5. WebUI chat

`WEBUI_AUTH=false` → no signup needed. Via tunnel open `http://localhost:13000`, type a Persian question (e.g. `اعتبارسنجی چیست؟`) → answer with `[1][2]` citations. Backend must be `OPENAI_API_BASE_URL=http://127.0.0.1:8100/v1`. If WebUI shows no models: `curl -s http://127.0.0.1:8100/v1/models | jq .`

## 6. Langfuse inspect

```bash
tail -5 /tmp/langfuse_traces.jsonl                                        # fallback collector :3000 history
set -a; . /tmp/opencode/langfuse.env; set +a                              # real v2 keys (mode 600, never commit)
curl -s -u "$LANGFUSE_INIT_PROJECT_PUBLIC_KEY:$LANGFUSE_INIT_PROJECT_SECRET_KEY" \
  "http://127.0.0.1:3001/api/public/traces?limit=5" | head -c 600; echo
# browser: tunnel -L 3001:localhost:3001, open http://localhost:3001, login admin@local.test (password in langfuse.env)
```

## 7. Studio run

```bash
bash deploy/vast/studio.sh
curl -s --max-time 10 http://127.0.0.1:2024/ok; echo
# panel: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
# run input MUST include request_id:
# {"request_id":"studio-001","messages":[{"role":"user","content":"سلام"}]}
```

## 8. SSH tunnels (NAT ports fixed — no new mappings)

```bash
ssh -p <ssh_port> root@<ssh_host> -L 13000:localhost:13000 -L 8100:localhost:8100 -L 3000:localhost:3000 -L 3001:localhost:3001 -L 2024:localhost:2024
# then: WebUI http://localhost:13000, Langfuse http://localhost:3001, Studio panel via http://127.0.0.1:2024
```

## 9. Stop

```bash
bash deploy/vast/stop.sh
# restart one service by port, e.g. guardrails:
fuser -k 8200/tcp; sleep 3
# (then re-run that service's start block from §2)
```

## 10. Troubleshooting

```bash
# VRAM OOM (22.7/24GB at ctx 8192) → restart Gemma at ctx 4096
fuser -k 18000/tcp; sleep 5
nohup /workspace/llama.cpp-src/build-cuda/bin/llama-server --model "$MODEL" \
  --port 18000 --ctx-size 4096 --temp 0.2 --no-mmproj --jinja -ngl 999 \
  > /tmp/llama-server.log 2>&1 &
sleep 45; curl -s http://127.0.0.1:18000/health

# HF offline / model miss → BOTH vars must point at /tmp/hf_clean (hub 1.x reads $HF_HOME/hub)
export HF_HOME=/tmp/hf_clean HF_HUB_CACHE=/tmp/hf_clean HF_HUB_OFFLINE=1
ls /tmp/hf_clean | head   # NOT /workspace/.hf_home (phantom dentries, looks full but empty)

# KB empty search + "attached to a different loop" → asyncpg loop bug: search_api must await
# search_knowledge_base directly, NOT via asyncio.to_thread(...)
grep -rn "to_thread" components/knowledgebase/kb-manager/kb_manager/web/ || echo "loop fix present (no to_thread)"
tail -30 /tmp/kb.log
curl -s http://127.0.0.1:8000/search/api -H 'Content-Type: application/json' \
  -d '{"query":"اعتبارسنجی چیست","top_k":1}' | head -c 300; echo

# KB silent SQLite fallback → KB_DB_URL was unset at KB start; restart KB with explicit pg URL
grep -i "sqlite\|asyncpg\|5432" /tmp/kb.log | head -5
PGPASSWORD=postgres psql -h 127.0.0.1 -U postgres -d kb_manager -tAc "SELECT count(*) FROM chunks;"

# <unused*> leak in Gemma output → wrong binary/flags: must be --no-mmproj --jinja + enable_thinking:false
ps aux | grep llama-server | grep -v grep
curl -s http://127.0.0.1:18000/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL","messages":[{"role":"user","content":"Hello"}],"max_tokens":20,"chat_template_kwargs":{"enable_thinking":false}}' | grep -c unused

# Logs
tail -30 /tmp/llama-server.log; tail -30 /tmp/kb.log; tail -30 /tmp/guard.log; tail -30 /tmp/orch.log
ps aux | grep -E "uvicorn|llama-server|open-webui" | grep -v grep
ss -tlnp | grep -E "18000|8000|8100|8200|13000|3000|3001|2024"
```
