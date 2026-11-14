# GPU / production deploy layer

Everything that makes the GPU production stack **stay up or come back by itself**.
This directory owns the last-known-good mechanism, the authoritative health gate,
and the auto-heal path.

```
deploy/gpu/
├── deploy.sh                  # the ONLY supported deploy entry point (preflight → ordered rollout → health gate → promote)
├── health.sh                  # SINGLE SOURCE OF TRUTH for "is prod serving?"
├── rollback.sh                # restore the recorded last-known-good images/config
├── reconcile.sh                # keep-alive / auto-heal: verify → heal to LKG → schedule retry
├── start.sh                   # legacy host-venv launcher (no docker; Gemma + uvicorn)
├── stop.sh                    # port-scoped + project-scoped stop (never `pkill python`)
├── lib/common.sh              # profile→layering/project/ports, probes, state helpers (sourced)
├── lib/state.py               # the only writer of state/last_good.json
├── systemd/
│   ├── dana-gpu-reconcile.service
│   └── dana-gpu-reconcile.timer
└── sim/                       # GPU-free proof harness (throwaway compose project)
    ├── simulate.sh            #   scenarios (a) no published port (b) promote (c) rollback
    ├── verify_report_repo.sh  #   proves the health-report push cannot trigger CI
    └── stack/                 #   disposable compose stack mirroring the prod hazard
```

## The failure this layer exists to make impossible

`deploy/compose/compose.base.yml` has **no `ports:` mappings**. Every reachable port
lives in an overlay (`compose.gpu.yml` for prod, `compose.local.yml` for dev/stage).

On 2026-11-12→14 production went dark while every container still reported
`healthy`: something restarted the stack with `compose.base.yml` alone, so the
containers were recreated with **zero published ports**. Container healthchecks probe
`127.0.0.1` *inside* the container, so they stayed green forever. The gateway pointed
at a dead host port and the site was unreachable for ~2 days with no alert.

Both halves of that failure are now structurally blocked:

1. **Un-published ports cannot be deployed.** `deploy.sh` resolves the compose config
   first and refuses to start anything unless every expected service publishes its
   exact loopback port (`lib/state.py check-ports`).
2. **Un-published ports cannot be reported healthy.** `health.sh` verifies from the
   host and names `NO_PUBLISHED_PORT` / `EXPECTED_PORT_MISSING` explicitly.

## Profiles (layering is fixed, never hand-typed)

| Profile | Compose layering | Project | Env file |
|---|---|---|---|
| `gpu` (prod) | `base + compose.gpu.yml` | `dana-prod` | `.env.prod` → `env.gpu.example` |
| `prod-sim` | `base + local + prod-sim` | `dana-prod-sim` | `.env` |
| `stage` | `base + local + stage` | `dana-stage` | `.env` |
| `local` | `base + local` | `dana-local` | `.env` |
| `host` | *(none — host venvs)* | `dana-host` | — |

The project name is **always** passed as `-p`. `deploy/compose/.env` contains
`COMPOSE_PROJECT_NAME=dana-local`, so relying on the env file would silently
retarget a prod deploy onto the laptop stack.

Port contract (`lib/common.sh` → `dana_port_spec`), loopback only:

| Service | prod | container |
|---|---|---|
| postgres | 15432 | 5432 |
| redis | 16379 | 6379 |
| kb | 8000 | 8000 |
| guardrails | 8200 | 8200 |
| tracing | 13002 | 3000 |
| orchestrator | 8100 | 8100 |
| webui | 13000 | 8080 |

## Last-known-good state

**Path:** `deploy/gpu/state/last_good.json` (host-local, gitignored directory)

Only `deploy.sh` (via `lib/state.py record`) writes it, and only after **every**
health gate passes. Sibling files:

| File | Purpose |
|---|---|
| `last_good.json` | the promoted record (schema below) |
| `last_good.prev.json` | the previous promotion, rotated on each successful deploy |
| `last_good.history.jsonl` | append-only log of promotions (last 50 kept) |
| `candidate-<run>.json` | per-deploy fact set before promotion |
| `health-<run>.json` | `health.sh` verdicts for that run |
| `rollback-<run>.pin.yml` | generated image-pin override used by a rollback |
| `logs/` | deploy / rollback / reconcile logs (falls back here if `/var/log/dana-rag` is not writable) |

### Schema (`schema_version: 1`)

```json
{
  "schema_version": 1,
  "status": "healthy",                 // "healthy" is REQUIRED to promote
  "promoted_at": "2026-11-14T15:08:08Z",
  "runtime": "compose",                // "compose" | "host-venv"
  "project": "dana-prod",
  "profile": "gpu",
  "recorded_by": "deploy/gpu/deploy.sh run=20261114T150742Z",

  "compose": {
    "files": ["/workspace/.../compose.base.yml", "/workspace/.../compose.gpu.yml"],
    "env_file": "/workspace/.../env.gpu",
    "config_sha256": "3c3dae66…",      // sha256 of `docker compose config --format json` (sorted keys)
    "project_name": "dana-prod",
    "port_check_ok": true
  },

  "git": {
    "parent_sha": "7cd59c7c…",
    "parent_branch": "main",
    "parent_dirty": false,
    "submodules": [ { "path": "components/knowledgebase", "sha": "…", "describe": "…", "dirty": false } ],
    "submodules_dirty": []
  },

  "images": [
    {
      "service": "kb",
      "image": "rag-kb:local",             // compose image ref
      "image_id": "sha256:91347495…",      // exact bytes that were running
      "repo_digest": "rag-kb@sha256:…",    // registry digest (null for local builds)
      "rollback_tag": "dana-lastgood/kb:20261114T150742Z-7cd59c7",
      "container": "dana-prod-kb-1",
      "container_health": "healthy"
    }
  ],

  "ports": {
    "kb": { "published": 8000, "target": 8000, "health_path": "/health" }
  },

  "health": { "checked_at": "…", "all_healthy": true, "verdicts": { "kb": "OK" } },

  "schedule": {
    "last_check_at": "…",
    "last_success_at": "…",
    "next_retry_at": "…",              // cadence source of truth
    "consecutive_failures": 0,
    "last_rollback_at": "…",           // added by rollback.sh
    "last_rollback_reason": "…"
  }
}
```

`images[]` is the part that makes rollback real: it records the **image ID**, not
just a tag. A tag is mutable; a deploy that rebuilds `rag-kb:local` would otherwise
make "roll back to the previous tag" a no-op.

## health.sh verdicts and exit codes

`health.sh` prints one row per service and exits with the worst severity:

| Exit | Meaning | Typical verdict |
|---|---|---|
| 0 | all critical services serving | `OK` |
| 1 | **deploy/layering bug** | `NO_PUBLISHED_PORT`, `EXPECTED_PORT_MISSING`, `WRONG_BIND`, `PORT_OWNED_BY_FOREIGN` |
| 2 | container down | `NO_CONTAINER`, `NOT_RUNNING`, `UNHEALTHY` |
| 3 | port up, HTTP failing | `ENDPOINT_DOWN` |
| 4 | drift vs last-good (`--state-check`) | `STATE_DRIFT` |

Optional services (`tracing`, `redis`) show as `WARN` rows and never fail the gate.

### The exact check that catches "healthy container, unpublished port"

```bash
# deploy/gpu/health.sh — evaluate_service()
if [ "$USE_COMPOSE" = "1" ] && [ -z "$published" ]; then
  verdict="NO_PUBLISHED_PORT"
  detail="container '$container' is ${chealth} but publishes NO host port; expected ${port}->${target}. compose.base.yml alone has no ports: — overlay missing from the deploy."
  add_row "$svc" "$port" "$container" "$chealth" "NONE" "-" "$verdict" "$detail" "$optional"
  return
fi
```

`published` comes from Docker itself, not from the compose file:

```bash
dana_live_publishers() {          # lib/common.sh
  docker inspect --format '{{json .NetworkSettings.Ports}}' "$1" \
    | python3 -c '...print each HostIp:HostPort...'
}
```

So a container that is `healthy` with `"Ports": {"8080/tcp": null}` produces
`published=""` → `NO_PUBLISHED_PORT`, regardless of what the YAML claims.

## Deploy

```bash
bash deploy/gpu/deploy.sh --dry-run          # validate layering + show the plan
bash deploy/gpu/deploy.sh                    # deploy → verify → promote
bash deploy/gpu/deploy.sh --no-promote       # deploy + verify, leave LKG untouched
bash deploy/gpu/deploy.sh --allow-dirty      # deploy uncommitted code (SHA recorded as-is)
```

Order of operations:

1. **Port preflight** — `state.py check-ports` against the resolved config. Aborts
   before touching anything if a required port is missing.
2. **Current-state snapshot** — health verdicts saved for post-mortem.
3. **Ordered rollout** — dependency order derived from `depends_on` (Kahn's
   algorithm, tier-ordered ties): `postgres → redis → kb → guardrails → tracing →
   orchestrator → webui`. After each tier: wait for its healthcheck (bounded by
   `--timeout`, default 600s) **and** for its published host port to accept a TCP
   connection. No fixed `sleep`.
4. **Health gate** — full `health.sh` with host probes.
5. **Promote** — only if the gate passed; rotates the previous record and appends
   history.
6. **Auto-rollback** — if the gate failed and an LKG exists, `rollback.sh` runs
   automatically (suppress with `--no-rollback`).

## Rollback

```bash
bash deploy/gpu/rollback.sh --dry-run
bash deploy/gpu/rollback.sh                              # to last_good.json
bash deploy/gpu/rollback.sh --from-state deploy/gpu/state/last_good.prev.json
bash deploy/gpu/rollback.sh --reason "manual: bad deploy"
```

What it does:

1. Validates the state file (`state.py validate`), refusing a corrupt/unhealthy record.
2. Re-derives the config hash and **warns on drift** (compose files changed since
   the good deploy) — the health gate stays authoritative.
3. Resolves each service to its recorded **image ID**, re-tagging it to
   `dana-lastgood/<service>:<stamp>-<sha>`. If the recorded image was pruned it
   warns and falls back to the current ref rather than lying about success.
4. Writes a generated `rollback-<run>.pin.yml` and appends it **last** in the
   layering, so compose resolves `image:` to exactly the recorded bytes. It does
   *not* re-point shared tags like `python:3.11-slim` (that would leak the rollback
   into unrelated stacks).
5. `compose up -d --no-build --force-recreate` tier by tier.
6. **Re-verifies** with `health.sh`, polling until the published ports answer
   (bounded by `--timeout`, default 420s). Exit 3 if the stack is up but unhealthy.

Triggers: deploy failure (automatic), `reconcile.sh` (automatic), or an operator.

## Keep-alive cadence

```bash
sudo cp deploy/gpu/systemd/dana-gpu-reconcile.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now dana-gpu-reconcile.timer
```

The timer wakes **hourly** (`RandomizedDelaySec=300` to avoid colliding with
Jenkins `pollSCM`) plus a **daily full check at 04:10** host-local, with
`Persistent=true` so a missed run is replayed after downtime.

`reconcile.sh` owns the actual cadence through `schedule.next_retry_at`:

| Last run | `next_retry_at` | Effect |
|---|---|---|
| healthy | now + 24h | hourly ticks exit 0 quickly; daily re-verify runs |
| healed | now + 24h | back to daily |
| still failing | now + **3h** | retries every 3 hours until healthy |

Keeping the cadence in the state file means it is inspectable
(`state.py get --field schedule`), survives reboots, is not desynchronised by a
manual `--force`, and works unchanged under cron/launchd.

Semantics of a reconcile run:

```
health.sh green?            → record last_check/last_success, exit 0
red + LKG exists            → rollback.sh (heal TOWARDS recorded good)
red + no LKG                → deploy.sh --no-rollback once (bootstrap), promote if green
still red                   → consecutive_failures += 1, next_retry_at = +3h, exit 1
```

It never does a blind `docker compose up -d` on the current working tree — that is
precisely the healing strategy that re-applied the broken layering.

## Health-report push isolation

`scripts/gpu_full_recover_report.sh` pushes to
`https://github.com/AliNikkhah2001/Work_RAG_HealthCheck.git`, which is a **separate
repository**. Verified 2026-11-14:

```bash
gh api repos/AliNikkhah2001/Work_RAG_HealthCheck/hooks --jq 'length'                 # 0
gh api repos/AliNikkhah2001/Work_RAG_HealthCheck/actions/workflows --jq '.total_count' # 0
# no Jenkinsfile, .gitlab-ci.yml, .github/workflows, azure-pipelines.yml, .circleci
```

The repo contains only `reports/`. It is **not** a Jenkins multibranch source, so a
push cannot trigger a build there or anywhere else. The script additionally
force-sets `origin` and refuses to push if the target normalises to the umbrella
repo or any component submodule.

Run the check yourself:

```bash
bash deploy/gpu/sim/verify_report_repo.sh
```

## GPU-free proof

```bash
bash deploy/gpu/sim/simulate.sh           # scenarios a, b, c
bash deploy/gpu/sim/simulate.sh a         # just the "no published port" detection
bash deploy/gpu/sim/verify_report_repo.sh
```

`simulate.sh` creates a disposable compose project (`dana-sim`, ports 19300-19302
published, no volumes of value), freezes the scripts under test into a private copy
(so a concurrent edit cannot corrupt a run), and tears the project down afterwards.
It never touches `dana-local` or `dana-stage`.

## Runbook (GPU host)

```bash
# is prod actually serving?
bash deploy/gpu/health.sh                      # verdict table; exit code is the signal
bash deploy/gpu/health.sh --json /tmp/h.json   # machine-readable

# what was the last good deploy?
python3 deploy/gpu/lib/state.py show --state deploy/gpu/state/last_good.json

# deploy the current checkout
bash deploy/gpu/deploy.sh

# something is wrong and you want the last good stack back
bash deploy/gpu/rollback.sh --reason "manual"

# force an immediate keep-alive pass (ignores next_retry_at)
bash deploy/gpu/reconcile.sh --force

# stop / start
bash deploy/gpu/stop.sh                        # compose stop (volumes preserved)
bash deploy/gpu/deploy.sh
```

Never: `pkill python` (use `stop.sh`), `docker compose ... down -v` on prod,
`docker compose up -d` without `-p`, or a compose invocation that omits the overlay.
