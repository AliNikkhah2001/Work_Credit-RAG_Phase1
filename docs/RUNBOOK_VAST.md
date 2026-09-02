# Vast.ai Runbook — Work Credit RAG Phase 1 (Public)

**Target browser path:** `browser → PUBLIC_IP:13000 → Open WebUI → Orchestrator :8100 → Guardrails :8200 + KB :8000 → Gemma :18000 → citations`

Existing Gemma is **external** `http://127.0.0.1:18000/v1` (`unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL`, llama-server pid 676). Do NOT launch gemma-manager, do NOT download another GGUF. Docker containers reach it via `http://host.docker.internal:18000/v1` (`extra_hosts: host-gateway`).

## Instance (this Vast VM)

- **ID:** 49624249 (ssh9.vast.ai:24248), **Public IP:** 91.108.80.253 (static_ip true)
- **Ports mapped by Vast:** 22→24044, 8000→32221, 8080→22341, 1111→17547 (see `vastai show instance 49624249 --raw` `ports`). **13000 is not in Vast's `ports` map** — host `0.0.0.0:13000` is still reachable via `91.108.80.253:13000` if host binds `0.0.0.0:13000` (host firewall allows high ports). Verified `ss -tlnp | grep 13000` shows `0.0.0.0:13000`. If your Vast UI blocks 13000, add `-p 13000:8080` to instance or use mapped 8080→22341: run Open WebUI on 8080 and open `http://91.108.80.253:22341`.
- **GPU:** 2× RTX 6000 Ada 49 Gi (595.58.03, CUDA 13.2), CPU 96× EPYC 7443, RAM 503 Gi, disk 100 Gi
- **Gemma:** `curl -s http://127.0.0.1:18000/v1/models | jq .data[0].id` → `unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL`

## Prerequisites

```bash
python3 --version # 3.12.13
pip --version
git --version     # 2.43.0
docker --version  # 29.7.2 (installed, but Vast unprivileged → build/run needs --storage-driver=vfs --iptables=false or host fallback; see Docker section)
curl -s http://127.0.0.1:18000/v1/models | jq .
```

## Clone (recursive, pinned)

```bash
git clone --recurse-submodules https://github.com/AliNikkhah2001/Work_Credit-RAG_Phase1.git
cd Work_Credit-RAG_Phase1
git switch vast-gemma4-migration
git submodule sync --recursive && git submodule update --init --recursive
git submodule status --recursive  # +fde5e25 KB +8015eda guardrails +e7872b9 orchestrator +5d5a7e4 server-setup
```

## Install — Host venvs (no Docker required for RAG smoke)

```bash
python3 -m venv /tmp/kb-venv && /tmp/kb-venv/bin/pip install -e components/knowledgebase/kb-manager[dev] && /tmp/kb-venv/bin/pip install aiosqlite matplotlib
python3 -m venv /tmp/guard-venv && /tmp/guard-venv/bin/pip install -e components/guardrails
python3 -m venv /tmp/orch-venv && /tmp/orch-venv/bin/pip install -e components/orchestrator
# KB DB (if data/kb_test.db missing, ingest 78 XLSX):
KB_DB_URL="sqlite+aiosqlite:///./data/kb_test.db" KB_SOURCE_DIR="$PWD/components/knowledgebase/kb-source/clean_files" \
  /tmp/kb-venv/bin/python -m kb_manager.cli ingest --full  # 69 docs 2399 chunks, ~5 min
python3 -m venv /tmp/webui-venv && /tmp/webui-venv/bin/pip install open-webui  # for host Open WebUI on 13000 (optional if Docker works)
```

## Install — Docker (host is unprivileged; use vfs + no-iptables for hello-world)

```bash
apt update && apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
# Vast host is unprivileged: default overlayfs/iptables fails with "operation not permitted"
dockerd --storage-driver=vfs --iptables=false --bridge=none &  # or: service docker start may fail
docker --version; docker compose version
docker run --rm --network host hello-world  # with vfs should show "Hello from Docker!" if host allows unshare
# For this Vast instance, `unshare: operation not permitted` persists — Docker cannot run containers.
# Fallback is host venvs (above) + host Open WebUI on 0.0.0.0:13000. Keep compose.mvp.yml for a privileged host.
```

## Startup — Host (current Vast, Docker not functional)

```bash
# 1. KB 0.0.0.0:8000 → but caddy occupies *:8000, so use 8004 on host; Docker uses 8000 internally
KB_DB_URL="sqlite+aiosqlite://$PWD/components/knowledgebase/kb-manager/data/kb_test.db" KB_WEB_HOST=127.0.0.1 KB_WEB_PORT=8004 \
  /tmp/kb-venv/bin/python -m uvicorn kb_manager.web.app:app --host 127.0.0.1 --port 8004 &
# 2. Guardrails 0.0.0.0:8200 (Docker) or 127.0.0.1:8200 (host) → host Gemma
PYTHONPATH=components/guardrails/src GUARDRAILS_HOST=127.0.0.1 GUARDRAILS_PORT=8200 UPSTREAM_LLM_BASE_URL=http://127.0.0.1:18000/v1 UPSTREAM_LLM_MODEL=unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL \
  /tmp/guard-venv/bin/python -m uvicorn work_rag_guardrails.api:create_app --factory --host 127.0.0.1 --port 8200 &
# 3. Orchestrator 0.0.0.0:8100 (Docker) or 127.0.0.1:8100 (host) → KB + Guardrails
PYTHONPATH=components/orchestrator/src KB_BASE_URL=http://127.0.0.1:8004 GUARDRAILS_BASE_URL=http://127.0.0.1:8200 UPSTREAM_LLM_MODEL=unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL ORCHESTRATOR_HOST=127.0.0.1 ORCHESTRATOR_PORT=8100 \
  /tmp/orch-venv/bin/python -m uvicorn work_rag_orchestrator.api:create_app --factory --host 127.0.0.1 --port 8100 &
for p in 8004 8200 8100; do until curl -s http://127.0.0.1:$p/health | grep ok; do sleep 2; done; echo "$p ok"; done
curl -s http://127.0.0.1:8100/ready | jq .

# 4. Open WebUI 0.0.0.0:13000 → Orchestrator (host)
OPENAI_API_BASE_URL=http://127.0.0.1:8100/v1 OPENAI_API_KEY=sk-local-dev WEBUI_AUTH=false \
  /tmp/webui-venv/bin/open-webui serve --host 0.0.0.0 --port 13000 &
ss -tlnp | grep 13000  # must show 0.0.0.0:13000, not 127.0.0.1
curl -s http://127.0.0.1:13000 | head -c 200  # html
curl -s http://91.108.80.253:13000 | head -c 200  # from inside VM hairpin may fail; test from your Windows browser: http://91.108.80.253:13000
```

## Startup — Docker (when host allows privileged Docker)

```bash
# LLM_* env is consumed by Guardrails (UPSTREAM_* alias)
LLM_BASE_URL=http://host.docker.internal:18000/v1 LLM_MODEL=unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL LLM_API_KEY=sk-local-dev \
  docker compose -f compose.mvp.yml up --build -d
docker compose -f compose.mvp.yml ps
docker compose -f compose.mvp.yml logs -f kb-manager guardrails orchestrator open-webui
# Only 13000 is public (0.0.0.0:13000:8080). Internal: kb 8000, guardrails 8200, orchestrator 8100 are expose (not ports), postgres not exposed.
```

`compose.mvp.yml` key points:
- **No gemma-manager** service.
- `LLM_BASE_URL/LLM_MODEL/LLM_API_KEY` env (no secrets hardcoded).
- `guardrails: UPSTREAM_LLM_BASE_URL=http://host.docker.internal:18000/v1` + `extra_hosts: ["host.docker.internal:host-gateway"]` (same for orchestrator).
- `open-webui: OPENAI_API_BASE_URL=http://orchestrator:8100/v1` (Docker DNS, not host.docker.internal, not :9000). Verify `GET /v1/models` exists on orchestrator.

## Health & Tests

```bash
curl -s http://127.0.0.1:18000/v1/models | jq .data[0].id
curl -s http://127.0.0.1:18000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL","messages":[{"role":"user","content":"Hello"}],"max_tokens":5}' | jq .

curl -s http://127.0.0.1:8004/health; curl -s http://127.0.0.1:8004/search/api -H "Content-Type: application/json" -d '{"query":"اعتبارسنجی چیست؟","top_k":3}' | jq .final_results[0].content_preview
curl -s http://127.0.0.1:8200/health; curl -s http://127.0.0.1:8200/ready | jq .; curl -s http://127.0.0.1:8200/v1/rails/check -H "Content-Type: application/json" -d '{"stage":"input","text":"سلام","request_id":"t"}' | jq .
curl -s http://127.0.0.1:8100/health; curl -s http://127.0.0.1:8100/ready | jq .; curl -s http://127.0.0.1:8100/v1/models | jq .; curl -s http://127.0.0.1:8100/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL","messages":[{"role":"user","content":"سلام، امتیاز اعتباری چیست؟"}],"max_tokens":80}' | jq .rag.citations
curl -s http://127.0.0.1:13000 | head

# Component unit tests (run before E2E)
KB_DB_URL=sqlite+aiosqlite:///./data/kb_test.db /tmp/kb-venv/bin/python -m pytest components/knowledgebase/kb-manager/tests -v  # 32 passed 5 known failed
PYTHONPATH=components/guardrails/src /tmp/guard-venv/bin/python -m pytest components/guardrails/tests -v  # 6 passed 5 known failed
PYTHONPATH=components/orchestrator/src /tmp/orch-venv/bin/python -m pytest components/orchestrator/tests -v  # 9 passed

# E2E: /tmp/e2e.sh covers direct Gemma, KB retrieval, guardrails, orchestrator, Persian RAG+citations, unknown, malformed, sequential, latency, GPU
```

## Public URL

- **Host Open WebUI (current):** `http://91.108.80.253:13000` (host `0.0.0.0:13000` → Open WebUI :8080, `ss -tlnp | grep 13000` must show `0.0.0.0:13000`). If Vast blocks 13000 (not in `vastai show instance 49624249 --raw` `ports`), use SSH tunnel or rebind Open WebUI to a mapped port:
  ```bash
  ssh -p 24044 -L 13000:localhost:13000 root@ssh9.vast.ai  # then open http://localhost:13000
  # or: run Open WebUI on 8080 → public http://91.108.80.253:22341 (8080→22341)
  ```
- **Docker compose:** `http://91.108.80.253:13000` (same host port, container `13000:8080`).

Verify: `curl http://127.0.0.1:13000` → html; `ss -lntp | grep 13000` → `0.0.0.0:13000`; `curl http://91.108.80.253:13000` from **external** Windows browser.

## Ports

| Public | Container | Service | Exposure |
|---|---|---|---|
| `0.0.0.0:13000→8080` | `rag-open-webui` | Open WebUI | **public** |
| `127.0.0.1:8004` or `expose 8000` | `rag-kb` | KB | internal (host 8004 due caddy *:8000) |
| `127.0.0.1:8200` / `expose 8200` | `rag-guardrails` | Guardrails | internal |
| `127.0.0.1:8100` / `expose 8100` | `rag-orchestrator` | Orchestrator | internal (expose 8100 only for debug) |
| `127.0.0.1:18000` | `llama-server` | Gemma | **never public** |
| not exposed | `pgdata` | Postgres | internal only |
| not exposed | `redis` | Redis | internal only |

## Env (Vast)

```
LLM_BASE_URL=http://host.docker.internal:18000/v1  # alias for UPSTREAM_LLM_BASE_URL
LLM_MODEL=unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL
LLM_API_KEY=sk-local-dev  # ignored by llama.cpp
KB_WEB_HOST=0.0.0.0 KB_WEB_PORT=8000 (Docker) / 127.0.0.1:8004 (host)
GUARDRAILS_HOST=0.0.0.0 GUARDRAILS_PORT=8200
ORCHESTRATOR_HOST=0.0.0.0 ORCHESTRATOR_PORT=8100
KB_BASE_URL=http://kb-manager:8000 (Docker) / http://127.0.0.1:8004 (host)
GUARDRAILS_BASE_URL=http://guardrails:8200 (Docker) / http://127.0.0.1:8200 (host)
OPENAI_API_BASE_URL=http://orchestrator:8100/v1 (Docker) / http://127.0.0.1:8100/v1 (host)
```

## Security Warning

`WEBUI_AUTH=false` is for controlled smoke test only. Public `91.108.80.253:13000` is world-readable. For production: set `WEBUI_AUTH=true` + strong password or firewall `ufw allow from <your IP> to any port 13000`, and never expose Redis/Postgres/llama-server (18000) publicly.

## Known Issues (Vast)

- Docker on this host is unprivileged (`unshare: operation not permitted`, `iptables: Permission denied`) → `docker run` fails even with `--storage-driver=vfs`. Host venvs are used; `compose.mvp.yml` is ready for a privileged host.
- KB SQLite 977 MiB 2399 chunks < prod 8291 (5 XLSX fail `No valid sheets`).
- **Gemma — fixed at source 2026-09-02:** was leaking `<unused*>` on old `llama.cpp b1-ff5ef82` + `mmproj` auto-load. Now on `0.3.0-dev 0f3a71b` (`/opt/llama-new`, `--no-mmproj --jinja`) and `chat_template_kwargs:{"enable_thinking":false}` (guardrails `3f20bed`) raw returns clean Persian (`has_unused False` on 5 prompts). With `enable_thinking:true` thinking goes to `reasoning_content` (model behavior). Guardrails `_clean_gemma_output` is now defensive only. If you see `<unused>`, ensure you are hitting `127.0.0.1:18000` with the new binary (`LD_LIBRARY_PATH=/opt/llama-new/lib`) and that guardrails was reinstalled.
- HurtLex conservative still flags "بخشی" for English queries — allowlist tuning pending.

## Logs / Troubleshooting

```bash
ps aux | grep uvicorn
cat /tmp/kb.log /tmp/guard.log /tmp/orch.log /tmp/webui.log
# Docker when functional:
docker compose -f compose.mvp.yml logs -f
curl -s http://127.0.0.1:8100/v1/models | jq .  # Open WebUI uses this
```

