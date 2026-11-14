# Dana compose stack (laptop test ↔ GPU prod)

## LLM upstream flag (required mental model)

| `DANA_ENV` | `LLM_UPSTREAM_MODE` | Overlay | Generation backend |
|---|---|---|---|
| `test` | `openrouter` | `compose.local.yml` | LiteLLM → OpenRouter (`google/gemma-4-31b-it`) |
| `prod` | `self_hosted` | `compose.gpu.yml` or `deploy/docker/` | Gemma `:18000` / Manager `:9000` / TRT |

**Never** set `LLM_UPSTREAM_MODE=openrouter` on the GPU server. App code only sees OpenAI-compatible `UPSTREAM_LLM_*` URLs.

Self-hosted Gemma/TRT paths:

- [deploy/docker/docker-compose.yml](../docker/docker-compose.yml) — CUDA `llama-server` image
- Server-setup manager / TRT docs under `components/server-setup/`

## One-command bootstrap

```bash
# Laptop: Docker + submodules + .env + Jenkins (:8085) + dana-local stack
bash scripts/setup_project.sh
bash scripts/setup_project.sh --with-stage   # also dana-stage
bash scripts/setup_project.sh --check        # health only

# GPU host (apps only; Gemma/Manager must already be up):
bash scripts/setup_project.sh --gpu
```

### Keep latest on the GPU server (optional daemon)

Jenkins Multibranch + hourly `pollSCM` + `[ci prod]` on `main` is the primary path.
If you also want a simple host daemon/timer that always tracks a **healthy** `origin/main`:

```bash
bash scripts/gpu_keep_latest.sh --dry-run
bash scripts/gpu_keep_latest.sh --loop --interval 300   # foreground
# or systemd: deploy/jenkins/dana-keep-latest.{service,timer}
```

On health failure after a pull it runs `scripts/ci_rollback.sh` (apps only — not Gemma/TRT).

## Laptop (test)

```bash
cp deploy/compose/.env.example deploy/compose/.env
# set OPENROUTER_API_KEY=...
# ensure:
#   DANA_ENV=test
#   LLM_UPSTREAM_MODE=openrouter

docker compose -p dana-local \
  -f deploy/compose/compose.base.yml \
  -f deploy/compose/compose.local.yml \
  --env-file deploy/compose/.env \
  up -d
```

UI: http://127.0.0.1:13000 · API: http://127.0.0.1:8100 · Jenkins: http://127.0.0.1:8085

> **`-p` is not optional.** `deploy/compose/.env` sets
> `COMPOSE_PROJECT_NAME=dana-local`, and Compose reads that key from
> `--env-file`. Running the stage overlay without `-p dana-stage` therefore
> resolves to project `dana-local` and *overwrites the dev stack* instead of
> creating a second one. Always pass the project name explicitly.

> **Never run `compose.base.yml` alone.** It declares no `ports:` at all. A
> base-only `up -d` recreates every container with zero published ports and
> takes http://localhost:13000 down without any error.

### Laptop retrieval gotcha (stale image ≠ git tip)

`compose.local.yml` bind-mounts `kb-manager/packs` **and** `kb-manager/kb_manager` so recreate picks up host source. Still rebuild after dependency changes:

```bash
docker compose -p dana-local \
  -f deploy/compose/compose.base.yml \
  -f deploy/compose/compose.local.yml \
  --env-file deploy/compose/.env \
  up -d --build kb
```

Default laptop embed/rerank is **local MiniLM 384-d + BGE** (matches a typical existing pgvector index). Switching to OpenRouter `text-embedding-3-small` (1536-d) without rebuilding the image **and** re-ingesting will break `/search/api` (and the search UI used to crash on missing `elapsed_ms`).

## GPU server (prod)

Prefer existing stacks (`deploy/docker/`). If using this compose family:

```bash
# .env.prod: DANA_ENV=prod, LLM_UPSTREAM_MODE=self_hosted, KB_*_DEVICE=cuda
docker compose -p dana-prod \
  -f deploy/compose/compose.base.yml \
  -f deploy/compose/compose.gpu.yml \
  --env-file deploy/compose/.env.prod \
  up -d --build
```

## Profiles

| File | Role |
|---|---|
| `compose.base.yml` | Shared services (default upstream = self-hosted Gemma) |
| `compose.local.yml` | LiteLLM OpenRouter + CPU embed/rerank + loopback ports |
| `compose.stage.yml` | Alt ports for Jenkins `develop` |
| `compose.prod-sim.yml` | Laptop prod-sim naming (still OpenRouter if local overlay) |
| `compose.gpu.yml` | Self-hosted Gemma upstream + CUDA devices |
