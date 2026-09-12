# Work Credit RAG — Docker deployment (privileged CUDA host)

Full-stack `docker compose` version of the platform. Mirrors
`deploy/vast/start.sh` (same services, ports, env vars, startup order) for hosts
where Docker **and** the NVIDIA Container Toolkit are available
(privileged host — real GPUs passed through to containers).

> **Vast.ai (this project's instance is unprivileged, no Docker): use
> `deploy/vast/*.sh` instead** (`start.sh` / `stop.sh` / `health.sh`).
> `compose.mvp.yml` (repo root) is the older Vast-MVP variant where Gemma stays
> an external host process; this stack containerizes everything instead.

## Services

| Service | Image / build | In-stack URL | Default host port |
|---|---|---|---|
| `llama-server` | `Dockerfile.llama` (CUDA 12.4.1, GGML_CUDA, GPU `all`) | `http://llama-server:18000` | none (debug only) |
| `postgres` | `pgvector/pgvector:pg16` (+ `init_db.sql`) | `postgres:5432` | none (debug only) |
| `kb` | `components/knowledgebase/kb-manager/Dockerfile` | `http://kb:8000` | none (debug only) |
| `guardrails` | `components/guardrails/Dockerfile` | `http://guardrails:8200` | none (debug only) |
| `orchestrator` | `components/orchestrator/Dockerfile` | `http://orchestrator:8100` | none (debug only) |
| `langfuse-db` | `postgres:15` | `langfuse-db:5432` | none |
| `clickhouse` | `clickhouse/clickhouse-server:24` | `clickhouse:9000/8123` | none |
| `langfuse` | `ghcr.io/langfuse/langfuse:2` | `http://langfuse:3000` | none (debug only) |
| `tracing-fallback` | `python:3.11-slim` + `components/tracing/app.py` | `http://tracing-fallback:3000` | none (debug only) |
| `webui` | `ghcr.io/open-webui/open-webui:main` | `http://orchestrator:8100/v1` (upstream) | **13000** (only published port) |

Named volumes: `pgdata`, `models` (HF hub cache: `HF_HOME`/`HF_HUB_CACHE=/models`
for `kb`), `webui-data`, `langfuse_pgdata`, `clickhouse_data`, `trace-data`
(fallback collector JSONL). Network: `rag` (bridge).

## Prereqs

- Docker Engine + Compose v2 (`docker compose version`) on a privileged host.
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/)
  installed and `nvidia-smi` working; `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi`
  must succeed.
- ~30 GB free disk (CUDA devel builder + images), Gemma GGUF on the host
  (e.g. `gemma-4-31B-it-UD-Q4_K_XL.gguf`, ≈ 18 GB), 24 GB VRAM at `CTX_SIZE=8192`.
- Clone including submodules (component Dockerfiles live in submodules).

## Quickstart

```bash
cd deploy/docker
cp .env.example .env
# Edit .env: set MODEL_FILE to the host path of your Gemma GGUF.
# Never commit .env with real secrets.

# Optional: use a prebuilt llama-server instead of compiling (path must be
# inside the repo = build context), then uncomment LLAMA_SERVER_BIN in .env:
#   cp /path/to/llama-server ../../build/llama-server

docker compose up -d --build
docker compose logs -f llama-server   # wait for "main: server is listening"
```

Model load takes minutes (GGUF → VRAM). `guardrails`/`kb`/`orchestrator` wait on
healthchecks (`depends_on: service_healthy`), so the stack orders itself:
postgres → llama-server → kb → guardrails → langfuse stack →
orchestrator → webui — same order as `start.sh`.

## Ports & debug access

Default `docker compose up`: **only WebUI is reachable from the host**
(`http://<host>:13000`). All other ports are container-internal (`expose`).
Compose profiles are service-level (they cannot gate individual `ports:`), so
debug publishing uses the standard auto-loaded override file instead: create
`docker-compose.override.yml` next to `docker-compose.yml` (git-ignored,
never commit) with whatever you need, e.g.:

```yaml
# docker-compose.override.yml — local debugging only, DO NOT COMMIT.
services:
  llama-server:      { ports: ["127.0.0.1:18000:18000"] }
  kb:                { ports: ["127.0.0.1:8000:8000"] }
  guardrails:        { ports: ["127.0.0.1:8200:8200"] }
  orchestrator:      { ports: ["127.0.0.1:8100:8100"] }
  langfuse:          { ports: ["127.0.0.1:3001:3000"] }
  tracing-fallback:  { ports: ["127.0.0.1:3002:3000"] }
```

(Equivalent commented `ports:` blocks sit in each service in
`docker-compose.yml`.) Never publish `18000`, postgres, or redis publicly;
Gemma stays loopback-only by design.

## KB ingest

`postgres` auto-applies `init_db.sql` on first boot (fresh `pgdata` volume).
Tables are also created by the pipeline itself. To (re)ingest documents:

```bash
# 1. Bind-mount your docs (add to docker-compose.override.yml):
#    services: { kb: { volumes: ["./kb-docs:/data/docs:ro"] } }
# 2. Run the click CLI inside the kb container (KB_DB_URL is already set):
docker compose exec kb python -m kb_manager.cli ingest --source-dir /data/docs
# Full rebuild:
docker compose exec kb python -m kb_manager.cli ingest --source-dir /data/docs --full
# Search sanity check (mirrors the start.sh E2E):
curl -s http://127.0.0.1:8000/search/api -H 'Content-Type: application/json' \
  -d '{"query":"اعتبارسنجی چیست","top_k":3}' | head -c 300; echo
```

First ingest downloads the embedding model into the `models` volume (needs
network; `HF_HUB_OFFLINE=0`). Once warm, you may set `HF_HUB_OFFLINE=1`
(mirrors `start.sh`).

## Health checks

```bash
# Container-level (mirrors deploy/vast/health.sh; needs the debug override above):
for p in 18000 8000 8200 8100; do printf "%s: " "$p"; curl -s --max-time 8 http://127.0.0.1:$p/health | head -c 120; echo; done
curl -s --max-time 8 http://127.0.0.1:8100/ready | head -c 300; echo
curl -s --max-time 8 http://127.0.0.1:8200/ready | head -c 300; echo
# Without the override, same checks via container DNS:
docker compose exec webui true 2>/dev/null  # (placeholder — use:)
docker compose exec orchestrator python -c "import urllib.request; print(urllib.request.urlopen('http://kb:8000/health').read())"
docker compose ps
# E2E through the orchestrator (works with default ports closed — run inside
# the net via exec, or open 8100 via the override):
docker compose exec orchestrator python -c "import urllib.request,json; print(urllib.request.urlopen('http://127.0.0.1:8100/health').read().decode()[:200])"
# Traces: Langfuse UI http://127.0.0.1:3001 (debug override) or fallback JSONL:
docker compose exec tracing-fallback tail -c 600 /tmp/langfuse_traces.jsonl
```

In-chat E2E (needs 8100 published via override, or run from a container):

```bash
curl -s http://127.0.0.1:8100/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"اعتبارسنجی چیست؟"}]}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['choices'][0]['finish_reason'], 'citations:', len(d.get('rag',{}).get('citations',[])))"
```

## Teardown / rebuild

```bash
docker compose down            # stop, keep volumes (DB, models cache, webui data)
docker compose down -v          # stop AND wipe all data (fresh init_db.sql import)
docker compose up -d --build llama-server   # rebuild one service (e.g. new LLAMA_REF)
```

## Troubleshooting

- **OOM / VRAM (22.7/24 GB at ctx 8192):** set `CTX_SIZE=4096` in `.env` and
  `docker compose up -d llama-server` (mirrors the `start.sh` fallback).
- **llama build slow:** the devel stage compiles all CUDA archs (~10–30 min,
  one time; layers cached). Skip with a prebuilt binary (`LLAMA_SERVER_BIN`).
- **`<unused*>` leaks in replies:** fixed in this stack — entrypoint always
  passes `--no-mmproj --jinja`; clients should send
  `chat_template_kwargs:{"enable_thinking":false}`.
- **KB empty / SQLite fallback:** `KB_DB_URL` is set in compose; if search is
  empty, check `docker compose logs kb` and that `postgres` is healthy.
- **First-run model downloads:** keep `HF_HUB_OFFLINE=0` until ingest works.
- **`MODEL_FILE` path:** must be an existing host file; Compose resolves it
  relative to `deploy/docker/` if not absolute.
- **Unprivileged hosts (no Docker / Vast.ai):** do NOT use this stack —
  run `bash deploy/vast/start.sh`, `stop.sh`, `health.sh` on the host instead.
