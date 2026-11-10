# Dana compose stack (laptop test ↔ GPU prod)

## LLM upstream flag (required mental model)

| `DANA_ENV` | `LLM_UPSTREAM_MODE` | Overlay | Generation backend |
|---|---|---|---|
| `test` | `openrouter` | `compose.local.yml` | LiteLLM → OpenRouter (`google/gemma-4-31b-it`) |
| `prod` | `self_hosted` | `compose.gpu.yml` or `deploy/docker/` / `deploy/vast/` | Gemma `:18000` / Manager `:9000` / TRT |

**Never** set `LLM_UPSTREAM_MODE=openrouter` on the GPU server. App code only sees OpenAI-compatible `UPSTREAM_LLM_*` URLs.

Self-hosted Gemma/TRT paths are unchanged:

- [deploy/vast/start.sh](../vast/start.sh) — llama-server `:18000`
- [deploy/docker/docker-compose.yml](../docker/docker-compose.yml) — CUDA `llama-server` image
- Server-setup manager / TRT docs under `components/server-setup/`

## Laptop (test)

```bash
cp deploy/compose/.env.example deploy/compose/.env
# set OPENROUTER_API_KEY=...
# ensure:
#   DANA_ENV=test
#   LLM_UPSTREAM_MODE=openrouter

docker compose -f deploy/compose/compose.base.yml \
  -f deploy/compose/compose.local.yml \
  --env-file deploy/compose/.env \
  up -d --build
```

UI: http://127.0.0.1:13000 · API: http://127.0.0.1:8100 · Jenkins: http://127.0.0.1:8085

### Laptop retrieval gotcha (stale image ≠ git tip)

`compose.local.yml` bind-mounts `kb-manager/packs` **and** `kb-manager/kb_manager` so recreate picks up host source. Still rebuild after dependency changes:

```bash
docker compose -f deploy/compose/compose.base.yml \
  -f deploy/compose/compose.local.yml \
  --env-file deploy/compose/.env \
  up -d --build kb
```

Default laptop embed/rerank is **local MiniLM 384-d + BGE** (matches a typical existing pgvector index). Switching to OpenRouter `text-embedding-3-small` (1536-d) without rebuilding the image **and** re-ingesting will break `/search/api` (and the search UI used to crash on missing `elapsed_ms`).

## GPU server (prod)

Prefer existing stacks (`deploy/vast/` or `deploy/docker/`). If using this compose family:

```bash
# .env.prod: DANA_ENV=prod, LLM_UPSTREAM_MODE=self_hosted, KB_*_DEVICE=cuda
docker compose -f deploy/compose/compose.base.yml \
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
