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

### Last-known-good image tags: bounded retention

`dana-lastgood/<service>:<stamp>-<sha>` tags are what makes rollback a re-tag
instead of a rebuild. They are now pruned to a bounded set:

```bash
bash scripts/dana_lastgood_prune.sh            # dry-run: show keep/remove
bash scripts/dana_lastgood_prune.sh --apply    # retire old tags
```

Keeps the newest `DANA_LASTGOOD_KEEP` (default **5**) per repository, plus every
tag a last-known-good state file names, plus the last reference to any image a
running container uses. Dry-run unless `--apply` / `DANA_LASTGOOD_PRUNE_APPLY=1`.
Only tags are removed — never images, layers or volumes. Optional
`--prune-dangling` / `--prune-build-cache` disk hygiene is off by default.
Details: [deploy/gpu/README.md](../gpu/README.md#last-known-good-tag-retention).

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

### Building images when Docker Hub is blocked

On some networks (observed on the Iranian dev laptop, Nov 2026) Docker Hub is
DNS-sinkholed: `registry-1.docker.io`, `auth.docker.io`, and
`production.cloudflare.docker.com` all resolve to the same ISP IP and the TLS
handshake dies. `docker pull` then fails with a bare EOF, and every rebuild
fails too — not because of the component, but because BuildKit cannot fetch
anything from the registry.

Use the wrapper instead of raw `docker build`:

```bash
# one component at a time; same context / dockerfile / args as the compose build: block
bash scripts/docker_build_offline.sh \
  --image rag-guardrails:local --context components/guardrails

bash scripts/docker_build_offline.sh \
  --image rag-kb:local --context components/knowledgebase/kb-manager \
  --build-arg TORCH_CHANNEL=cpu          # compose.local.yml pins cpu; compose.gpu.yml uses cuda

bash scripts/docker_build_offline.sh \
  --image rag-tracing:local --context components/tracing
```

Flags: `--image`, `--context`, `--dockerfile`, `--build-arg K=V` (repeatable),
`--no-cache`, `--dry-run`, `--self-test`. `--self-test` exercises the
reachability probe, the directive strip, and the `FROM` parser with no network
and no build, so it is safe to run in CI.

**Why the `# syntax=` directive must be stripped.** Every component Dockerfile
starts with `# syntax=docker/dockerfile:1`. That line makes BuildKit pull the
`docker/dockerfile:1` frontend image *before* parsing the file, which is exactly
what a blocked Hub kills. Once `docker/dockerfile:1` is unavailable, that line
has to go for the build to start. Nothing else depends on it: classic Dockerfile
syntax plus `RUN --mount=type=cache,target=/root/.cache/pip` is handled by the
frontend built into BuildKit. The helper copies the Dockerfile to a temp file,
removes only that one line, and keeps the original build context — **the
submodule Dockerfile is never modified**.

**Base images still have to be present locally.** Offline, a missing `FROM`
image can only fail; the helper resolves and `docker image inspect`s every base
first, then exits `2` naming the exact missing image:

| Component | Context | Required base image(s) | Cached on the laptop? |
|---|---|---|---|
| guardrails | `components/guardrails` | `python:3.11-slim` | yes |
| orchestrator | `components/orchestrator` | `python:3.11-slim` | yes |
| kb | `components/knowledgebase/kb-manager` | `python:3.11-slim` | yes |
| tracing | `components/tracing` | `python:3.11-slim` | yes |
| webui | `components/webui` (`Dockerfile.local`) | `python:3.12-slim-trixie`, plus `node:22-alpine3.20` / `nginx:alpine` on other stages | **no** |

So `guardrails`, `orchestrator`, `kb`, and `tracing` rebuild offline; **`webui`
cannot** — it needs Hub access (or a `docker load` of the base images from a
machine that has it). The same applies to `postgres:16-alpine` if it is ever
evicted from the local cache.

**The GPU server should use the normal path.** It has Hub access, so
`docker compose ... build` works with the Dockerfiles untouched and the syntax
directive preserved. The strip is an offline-only workaround; the helper only
does it when the 5-second probe of `registry-1.docker.io/v2/` fails.

Before overwriting `:local`, retag the current image so rollback stays possible:

```bash
docker tag rag-guardrails:local rag-guardrails:stale-$(date +%Y%m%d)
```

Then recreate only the services that changed:

```bash
docker compose -p dana-local \
  -f deploy/compose/compose.base.yml -f deploy/compose/compose.local.yml \
  --env-file deploy/compose/.env \
  up -d --no-deps --force-recreate guardrails orchestrator kb tracing
```

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
