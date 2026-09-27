# Write docker stack files (@general subagent)

Session: `ses_f6a7738f9ffe6RAZA5rnjuvxBe`
Messages: 13


## [USER]

Author a complete Dockerized version of the RAG platform under /workspace/Work_Credit-RAG_Phase1/deploy/docker/ (you are on branch `release/v1`; files WILL be committed by someone else — just write them).

First READ for ground truth: /workspace/Work_Credit-RAG_Phase1/compose.mvp.yml (full), the three Dockerfiles (components/orchestrator/Dockerfile, components/guardrails/Dockerfile, components/knowledgebase/kb-manager/Dockerfile), /workspace/Work_Credit-RAG_Phase1/deploy/vast/start.sh (for env vars/ports/args), /workspace/Work_Credit-RAG_Phase1/components/tracing/app.py (first 30 lines, for the collector).

Architecture (mirror start.sh, privileged host with NVIDIA Container Toolkit):
- `llama-server`: CUDA image (nvidia/cuda:12.4.1-runtime-ubuntu22.04), builds llama.cpp from submodule/source or copies a prebuilt binary via build-arg LLAMA_SERVER_BIN, runs Gemma GGUF (mount model via volume, model path via env MODEL_PATH), port 18000, args: --ctx-size 8192 --temp 0.2 --no-mmproj --jinja -ngl 999. deploy.resources + gpus: all.
- `kb`: build components/knowledgebase/kb-manager/Dockerfile, env KB_DB_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/kb_manager (+ HF_HOME/HF_HUB_CACHE with models volume), port 8000, depends_on postgres healthy.
- `postgres`: pgvector/pgvector:pg16, volume pgdata, healthcheck pg_isready, init via components/knowledgebase/kb-manager/scripts/init_db.sql (check it exists first; if missing, skip the mount).
- `guardrails`: build components/guardrails/Dockerfile, env UPSTREAM_LLM_BASE_URL=http://llama-server:18000/v1 + UPSTREAM_LLM_MODEL, port 8200, depends_on llama-server.
- `orchestrator`: build components/orchestrator/Dockerfile, env KB_BASE_URL=http://kb:8000 GUARDRAILS_BASE_URL=http://guardrails:8200 LANGFUSE_HOST=http://langfuse:3000 (+ key placeholders), port 8100.
- `langfuse` + `langfuse-db` (postgres:15) + `clickhouse`: follow compose.mvp.yml's existing langfuse stack if present there (read it!), else standard langfuse:2 service with CLICKHOUSE_URL, project seeded keys as placeholders.
- `tracing-fallback`: lightweight python:3.11-slim running components/tracing/app.py on :3000 (profile/off by default? keep simple: include, port 3000).
- `webui`: ghcr.io/open-webui/open-webui:main (or open-webui 0.11.x pin), env OPENAI_API_BASE_URL=http://orchestrator:8100/v1, port 13000 (the ONLY published port by default; publish others only via --profile debug).
- Top-level network `rag`, named volumes (pgdata, models, webui-data). No secrets committed: use ${VAR:-default} with .env.example.

Write these files under /workspace/Work_Credit-RAG_Phase1/deploy/docker/:
1. `Dockerfile.llama` — CUDA runtime + llama-server (supports prebuilt binary copy via LLAMA_SERVER_BIN build-arg, fallback: apt build-deps + cmake build from /workspace/llama.cpp-src? NO — must be self-contained: clone llama.cpp at build (ARG LLAMA_REF) and build with GGML_CUDA. Keep it working without the local tree).
2. `docker-compose.yml` — full stack as 
…[truncated]…


## [ASSISTANT]

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)


## [ASSISTANT]

(tool: bash)

(tool: read)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: grep)


## [ASSISTANT]

(tool: grep)

(tool: bash)


## [ASSISTANT]

(tool: read)


## [ASSISTANT]

(tool: write)


## [ASSISTANT]

(tool: write)


## [ASSISTANT]

(tool: write)


## [ASSISTANT]

(tool: write)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

Done. Four files written under `deploy/docker/`, nothing else modified.

**Files**
- `deploy/docker/Dockerfile.llama` — CUDA 12.4.1 runtime; builder stage clones llama.cpp (`ARG LLAMA_REF`, GGML_CUDA) so it's self-contained; `LLAMA_SERVER_BIN` build-arg COPYs a prebuilt binary, entrypoint picks it via ELF-magic check, else compiled binary. Env: `MODEL_PATH`, `CTX_SIZE` (8192), `LLAMA_TEMP`, `LLAMA_NGL`, `LLAMA_EXTRA_ARGS`; always passes `--no-mmproj --jinja`.
- `deploy/docker/docker-compose.yml` — 10 services mirroring `start.sh` order/ports/env with Docker-DNS URLs (`llama-server:18000`, `kb:8000`, `guardrails:8200`, `langfuse:3000`); langfuse trio mirrors `compose.mvp.yml`; `init_db.sql` mount kept (verified it exists); GPU reservation on llama-server; only `webui` has `ports:` (`${WEBUI_PORT:-13000}:8080`), rest `expose` + commented loopback `ports:` for debug.
- `deploy/docker/.env.example` — all tunables (`MODEL_FILE`, `LLM_MODEL`, `CTX_SIZE`, passwords, Langfuse keys, ports), dev-only placeholder defaults, no real secrets.
- `deploy/docker/README.md` — privileged-host prereqs, quickstart, ports/debug via `docker-compose.override.yml`, KB ingest (`kb_manager.cli ingest`), health checks mirroring `health.sh`, Vast-unprivileged note, OOM/`CTX_SIZE=4096` troubleshooting.

**Validation** (no `docker` binary on this host, so no `docker compose config`): parsed with pyyaml and asserted — exact 10-service set; `ports:` present only on `webui`; all build `context`/`dockerfile` paths and the `init_db.sql` mount resolve to real files; nvidia `devices` reservation intact; required volumes (`pgdata`, `models`, `webui-data`) + `rag` network present; `.env.example` lines all valid `KEY=` form. All checks passed. `git status` confirms only new files under `deploy/docker/` (plus other untracked files I did not touch) — left uncommitted per instructions.

One honest deviation to flag: `--profile debug` port publishing isn't expressible in Compose (profiles are service-level, can't gate individual `ports:`), so debug publishing is done via the standard auto-loaded `docker-compose.override.yml` + commented blocks, documented in the README port matrix.
