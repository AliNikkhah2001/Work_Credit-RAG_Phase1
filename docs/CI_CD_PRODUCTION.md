# CI/CD — Robust Production System (GPU server = production, laptop = dev)

This document describes the **desired-state CI/CD** for the Work Credit RAG
platform. It replaces the previously broken/ad-hoc flow where commits were
pushed directly to `develop`/`main`, production could silently go down, and you
could not tell which machine a commit came from.

## Guarantees this system provides

| Guarantee | How |
|---|---|
| `main`/`prod` is always clean & working | Branch protection: PR + 1 review required on `main` and `develop`. No direct pushes. |
| Changes flow laptop → develop → main | Laptop pushes `develop` with `[ci stage]`; stage validates; then PR `develop→main` with `[ci prod]`. |
| Production always up / auto-heals | `gpu_auto_heal.sh` runs every 60s on the GPU, probes critical ports, self-heals, falls back to host-venv stack. |
| Production status visible remotely | Health reports pushed to GitHub (`Work_RAG-Server-Setup` → `docs/ops/gpu-health/`) on every sweep. |
| Know which machine a commit came from | `Machine-origin: laptop \| gpu-server` trailer on every commit (git commit-msg hook). |
| WebUI theme changes take effect | `WEBUI_BUILD_VERSION` cache-bust token + `webui_cache_bust.sh` to invalidate middleware cache at chat.ics24.ir. |
| Laptop vs GPU config never drift | Separate `env.laptop.example` / `env.gpu.example`; GPU never uses OpenRouter; proxy bypass (`no_proxy=127.0.0.1,localhost`). |

---

## 1. Machine-origin commit tagging (every commit)

Install the hook on **each** machine (laptop and GPU server):

```bash
cp scripts/commit-machine-hook.sh .git/hooks/commit-msg
chmod +x .git/hooks/commit-msg
```

On the GPU server, ensure `DANA_HOST=gpu` is exported in your shell/Jenkins env
so commits made there are tagged `gpu-server`; otherwise they default to
`laptop`.

Every commit message body now gets:

```
Machine-origin: laptop
```

(or `gpu-server`). Jenkins and GitHub status checks surface this so you can
always tell where a change originated.

---

## 2. Branch flow (the only supported path)

```
laptop feature/*  --(PR, 1 review)-->  develop   --(PR, [ci stage])-->  stage green
                                                                   |
                                                                   v (PR, [ci prod])
                                                              main / production  --(GPU auto-deploy)-->  serving
```

### Step-by-step (developer on laptop)

1. Start from `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/my-change
   ```
2. Make changes, commit (conventional prefix), push:
   ```bash
   git commit -m "feat(kb): denser chunks"
   git push origin feature/my-change
   ```
3. Open a PR `feature/my-change → develop`. Require 1 review, status checks green.
4. After merge to `develop`, tag it for stage:
   ```bash
   git checkout develop
   git commit --allow-empty -m "chore: validate stage [ci stage]"
   git push origin develop
   ```
   → Laptop Jenkins (`dana-rag-stage`) builds + deploys `dana-stage` within ~1h (pollSCM).
5. When stage is green, promote to production:
   ```bash
   bash scripts/promote_stage_to_main.sh   # dry-run first
   bash scripts/promote_stage_to_main.sh --execute --push
   ```
   → Creates merge commit `chore: promote stage pins to main [ci prod]`.
   → GPU Jenkins (`dana-rag-prod`, `DANA_ROLE=prod`) picks it up and deploys
     `dana-prod` via `compose.gpu.yml` (self-hosted GPU, no OpenRouter).

**Never push directly to `main` or `develop`** — branch protection on GitHub rejects
direct pushes. Never force-push.

---

## 3. GitHub branch protection (configure once on each repo)

Required on `Work_Credit-RAG_Phase1` (and submodule repos) for both `main` and `develop`:

| Setting | Value |
|---|---|
| Require a pull request before merging | ✅ Enabled |
| Required approving reviews | 1 |
| Dismiss stale approvals when new commits are pushed | ✅ |
| Require status checks to pass before merging | ✅ (CI: lint, tests, docs-toc) |
| Require branches up to date before merging | ✅ |
| Require conversation resolution before merging | ✅ |
| Restrict pushes to matching branches | ✅ (no direct pushes) |
| Allow force pushes | ❌ Disabled |
| Allow deletions | ❌ Disabled |
| Include administrators | ✅ |

On GitHub: **Settings → Branches → Add branch protection rule**.

---

## 4. Production auto-heal (GPU server, always-on)

The GPU server runs `scripts/gpu_auto_heal.sh` as a systemd service/timer. It
probes critical ports every 60s:

```
8000 KB, 8200 Guardrails, 8100 Orchestrator, 13000 WebUI, 8085 Jenkins prod
```

On any critical port failure it:
1. Restarts the failing compose services (`dana-prod`, `compose.gpu.yml`)
2. Restarts the Jenkins prod controller if `:8085` is down
3. Falls back to the host-venv stack (`deploy/gpu/start.sh`) if compose is gone
4. Records health + last-known-good SHA (`.last_good_sha`)
5. Pushes a redacted health report to GitHub so you can see production status
   from your laptop without accessing the server

### Install on the GPU server (as root)

```bash
# Edit WorkingDirectory / DANA_HOST_REPO to this host's clone path
cp scripts/gpu_auto_heal.service /etc/systemd/system/
cp scripts/gpu_auto_heal.timer   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now gpu_auto_heal.timer
```

### One-shot / manual

```bash
DANA_HOST_REPO=/path/to/Work_Credit-RAG_Phase1 \
  bash scripts/gpu_auto_heal.sh --once
```

Health history accumulates under `components/server-setup/docs/ops/gpu-health/`
on GitHub (branch `ops/gpu-health-<timestamp>`).

---

## 5. WebUI cache-bust (middleware / chat.ics24.ir)

Traffic to `chat.ics24.ir` passes through a middleware gateway that forwards to
this server's Open WebUI (port 13000). The gateway can cache static WebUI
assets, so after a rebuild the browser may still show the old theme.

Fix:

```bash
# On the GPU server, bump the cache-bust token and restart webui
DANA_HOST_REPO=/path/to/Work_Credit-RAG_Phase1 \
  bash scripts/webui_cache_bust.sh --bump --restart
```

Then add cache-busting headers on the middleware reverse proxy for port 13000:

```nginx
location / {
  proxy_pass http://127.0.0.1:13000;
  add_header Cache-Control "no-cache, must-revalidate" always;
  add_header X-WebUI-Version "$WEBUI_BUILD_VERSION" always;
}
```

Reload the middleware and hard-refresh the browser (Ctrl+F5).

---

## 6. Laptop vs GPU configuration (never drift)

| | Laptop (dev / stage) | GPU (prod) |
|---|---|---|
| `DANA_HOST` | `laptop` | `gpu` |
| `DANA_ROLE` | `stage` | `prod` |
| `LLM_UPSTREAM_MODE` | `openrouter` (LiteLLM) | `self_hosted` (Gemma/Manager) |
| `UPSTREAM_LLM_BASE_URL` | `http://litellm:4000/v1` | `http://127.0.0.1:18000/v1` or `:9000/v1` |
| `DANA_ENV` | `test` | `prod` |
| OpenRouter keys | ✅ required | ❌ never on GPU |
| HF device | `cpu` | `cuda` |

Use the committed templates:
- `deploy/compose/env.laptop.example` → copy to `.env` on laptop
- `deploy/compose/env.gpu.example` → copy to `.env.prod` on GPU

Critical: on the GPU, localhost calls must bypass the Squid proxy
(`http://192.168.203.2:3128`). The code uses `httpx.AsyncClient(timeout=120,
trust_env=False)` and `no_proxy=127.0.0.1,localhost`.

---

## 7. Why production went silently down (and how this fixes it)

| Symptom | Root cause | Fix |
|---|---|---|
| Server down, no alert | No proactive health monitor; SPOF report was manual/reactive | `gpu_auto_heal.sh` + systemd timer (60s) |
| Can't see status from laptop | No health pushed to GitHub | Auto-heal pushes `docs/ops/gpu-health/` on every sweep |
| Commits to main directly, messy history | No branch protection, no PR enforcement | GitHub protection rules + PR flow |
| Don't know which machine a commit came from | No origin tagging | `commit-machine-hook.sh` `Machine-origin` trailer |
| WebUI theme changes not taking effect | Middleware caches static assets | `WEBUI_BUILD_VERSION` + `webui_cache_bust.sh` |
| Laptop/GPU config mismatch | Single shared `.env` | Separate `env.laptop.example` / `env.gpu.example` |
| Jenkins on GPU may not be polling | Single controller, no backup | Keep `gpu_keep_latest.sh` as backup + auto-heal restarts Jenkins |

---

## 8. Quick reference commands

```bash
# Laptop: validate stage
git commit --allow-empty -m "chore: validate stage [ci stage]"
git push origin develop

# Promote to production
bash scripts/promote_stage_to_main.sh --execute --push

# One-shot health check on GPU
DANA_HOST_REPO=/path bash scripts/gpu_auto_heal.sh --once

# View last production status (from laptop)
cat components/server-setup/docs/ops/gpu-health/latest/health.json

# Rollback production (break glass)
git commit --allow-empty -m "chore: break glass [ci rollback]"
git push origin main

# WebUI cache bust after theme change
DANA_HOST_REPO=/path bash scripts/webui_cache_bust.sh --bump --restart
```
