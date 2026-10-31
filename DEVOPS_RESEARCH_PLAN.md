# DevOps & Deployment Research Plan — Work Credit RAG Phase 1

**Date:** 2026-10-28  
**Repo:** `Work_Credit-RAG_Phase1` (umbrella, `main`/`develop`)  
**Goal:** Containerize services, establish CI/CD, optimize Gemma inference (Triton/TensorRT), productionize deployment.

---

## 1. Current Deployment State (Baseline)

| Layer | How it runs today | Host | Ports | Containerized? |
|-------|-------------------|------|-------|----------------|
| Gemma LLM (5× backends) | `llama_chat_server.py` via `gemma_supervisor.sh` | H200 / Vast | 8080–8084 | No (host venv) |
| LLM Manager (gateway) | `llm_inference_manager/app.py` | H200 | 9000 | No |
| Embeddings (3 models) | `embed_server.py` ×3 | H200 / Vast | 8001–8003 | No |
| KB Retrieval | `kb_manager.web.app:app` | Vast | 8000 | No |
| Guardrails | `work_rag_guardrails.api:create_app` | Vast | 8200 | No |
| Orchestrator (LangGraph) | `work_rag_orchestrator.api:create_app` | Vast | 8100 | No |
| Tracing fallback | `components/tracing/app.py` | Vast | 3000 | No |
| Open WebUI | Docker `open-webui:main` | Docker | 13000 | ✅ Yes |
| postgres + pgvector | system cluster | system | 5432 | No |
| Redis | system | system | 16379 | No |

**Pain points:**
- Vast.ai is **unprivileged** → no Docker, no `unshare`/iptables → host venvs only
- H200 host has Docker but services run as bare Python processes
- No CI/CD pipeline → manual `git push` + manual `bash deploy/vast/start.sh`
- No health-check automation, no rollback, no blue/green
- Gemma runs via llama.cpp (not Triton/TensorRT) → suboptimal GPU utilization on H200

---

## 2. Research Areas

### A. Containerization Strategy

**Investigate:**
1. **Multi-service Docker Compose** for privileged hosts (H200, local dev)
   - One container per service: KB, guardrails, orchestrator, tracing, manager, embed servers
   - Shared Docker network, health checks, restart policies
   - Volume mounts for models (`offline-prep/models/`), configs, logs
2. **Dockerfiles per service** (Python base, `requirements.txt`, non-root user, `gunicorn`/`uvicorn` workers)
3. **Vast.ai workaround** (unprivileged, no Docker):
   - Continue host venvs OR use `proot`/`bubblewrap` for lightweight isolation
   - Document dual deployment paths: Docker Compose (privileged) vs. host venv (Vast)
4. **Base image selection**: `python:3.11-slim` vs. `nvidia/cuda:12.x-base` for GPU services
5. **Multi-stage builds** to reduce image size (build deps in stage 1, runtime in stage 2)

**Deliverable:** `deploy/docker/` updated with per-service Dockerfiles + `docker-compose.prod.yml`

---

### B. CI/CD Pipeline

**Investigate:**

| Tool | Fit for this project | Notes |
|------|---------------------|-------|
| **GitHub Actions** | ✅ Best fit | Repo already on GitHub, free for public, easy secrets, matrix builds |
| **Jenkins** | ⚠️ Overkill | Self-hosted, heavy, good if you already have Jenkins infra |
| **GitLab CI** | ❌ Not used | Repo is on GitHub |
| **Azure DevOps** | ❌ Not used | No Azure presence |

**Recommended: GitHub Actions**
- **CI workflow** (`.github/workflows/ci.yml`): run on PR to `develop`/`main`
  - `ruff` lint, `mypy` type check, `pytest` on `eval/`, `scripts/gen_readme_toc.py --check`
  - Build Docker images (dry-run), verify submodule pins
- **CD workflow** (`.github/workflows/cd.yml`): run on merge to `main`
  - Deploy to Vast.ai via SSH tunnel (`ssh` + `bash deploy/vast/start.sh`)
  - Health check gates, rollback on failure
- **Secrets**: `VAST_SSH_KEY`, `VAST_HOST`, `VAST_SSH_PORT`, `DOCKER_HUB_TOKEN`

**Branch protection integration:**
- CI must pass before merge (already planned in Rulesets)
- Status checks: `lint`, `test`, `docker-build`, `health-check`

**Deliverable:** `.github/workflows/ci.yml`, `.github/workflows/cd.yml`, `.github/workflows/docker.yml`

---

### C. Gemma Model Optimization — Triton / TensorRT

**Investigate:**

#### 1. llama.cpp (current) limitations
- Runs GGUF on CUDA via `llama_chat_server.py` (`n_gpu_layers=-1`)
- Good for quick start, but **no dynamic batching**, **no continuous batching**, **no KV cache reuse optimization**
- Context overflow issues seen earlier (663KB prompt → Triton 400)

#### 2. NVIDIA Triton Inference Server
- **What**: NVIDIA's model serving platform, supports TensorRT, ONNX, PyTorch, llama.cpp backend
- **Pros**: Dynamic batching, model ensemble, GPU/CPU mixed, metrics endpoint, HTTP/GRPC
- **Cons**: Complex config (`config.pbtxt`), larger image, steeper learning curve
- **Backend options**:
  - `llama.cpp backend` for Triton (drop-in replacement for current llama-server)
  - `TensorRT-LLM backend` (best performance on H200/Runtime 3090)

#### 3. NVIDIA TensorRT-LLM
- **What**: NVIDIA's LLM optimization framework (quantization FP8/INT4, KV cache paging, in-flight batching, speculative decoding)
- **Pros**: 2–5× throughput vs llama.cpp on H200, FP8 quantization, PagedAttention
- **Cons**: Requires model conversion (HF → TRT-LLM format), H200 (Hopper) fully supported, RTX 3090 (Ampere) limited FP8
- **Workflow**:
  1. Export Gemma-4-31B HF weights → TensorRT-LLM engine (`.engine` file)
  2. Quantize to FP8 (H200) or INT4/INT8 (RTX 3090)
  3. Serve via Triton `tensorrtllm` backend or standalone `trtllm-serve`

#### 4. Optimization techniques to research
| Technique | Benefit | Applies to |
|-----------|---------|------------|
| **FP8 quantization** | 2× VRAM reduction, 1.5–2× speed | H200 (Hopper) only |
| **INT4/INT8 quantization** | 4× VRAM reduction | RTX 3090 (Ampere), H200 |
| **PagedAttention / KV cache paging** | Eliminates OOM on long contexts | TensorRT-LLM, vLLM |
| **Continuous batching** | Higher throughput under concurrent load | Triton, TensorRT-LLM, vLLM |
| **Speculative decoding** | 2–3× token/s with draft model | TensorRT-LLM |
| **CUDA graphs** | Lower kernel launch overhead | Triton, TensorRT-LLM |

**Decision matrix:**
| Host | GPU | Recommended stack |
|------|-----|-------------------|
| H200 | Hopper SM90 | TensorRT-LLM + Triton (FP8) |
| Vast.ai | RTX 3090 (Ampere) | TensorRT-LLM (INT8) or llama.cpp (current) |
| Local dev | Any | llama.cpp (simplest) |

**Deliverable:** `deploy/triton/` directory with `config.pbtxt`, model conversion scripts, benchmark plan

---

### D. Production Infrastructure

**Investigate:**
1. **Reverse proxy / API Gateway**: Nginx, Traefik, or Caddy for TLS termination, rate limiting, routing to `:9000`/`:8000`/`:8100`/`:8200`
2. **Load balancing**: Round-robin across Gemma 5 backends (already in manager), plus health-based failover
3. **Service mesh (optional)**: Istio/Linkerd — likely overkill for 7 services
4. **Monitoring**: Prometheus (already at `:19090`), Grafana (`:13001`), add alertmanager for service-down alerts
5. **Logging**: Centralized JSONL → ELK or Loki; current `/tmp/langfuse_traces.jsonl` is ephemeral
6. **Secrets management**: HashiCorp Vault or AWS Secrets Manager — currently `.env` files (risk)
7. **Database**: postgres + pgvector on system — consider Dockerizing or managed (RDS/Crunchy)
8. **Redis cache**: Currently system `:16379` — Dockerize or managed Elasticache

---

### E. Vast.ai Specific Constraints

**Investigate:**
- Unprivileged container → no Docker daemon → all services as host processes
- Fixed NAT ports → SSH tunnels for external access
- Ephemeral disk → models must be re-downloaded or mounted from persistent volume
- No `iptables`/`unshare` → no rootless Docker
- **Workaround**: Use `systemd` user services or `supervisord` for process management, `ngrok`/`cloudflared` for public tunnels

---

## 3. Detailed Investigation Plan (Phase by Phase)

### Phase 1: Audit & Documentation (Week 1)
- [ ] Inventory all services, entry points, env vars, dependencies
- [ ] Map current `deploy/vast/start.sh` → service startup order
- [ ] Document all `.env` requirements and secrets
- [ ] Benchmark current Gemma latency/throughput (baseline for optimization)
- [ ] Check Docker availability on H200 host

### Phase 2: Containerization (Week 2–3)
- [ ] Write `Dockerfile` for KB service (Python 3.11, `sentence-transformers`, `asyncpg`)
- [ ] Write `Dockerfile` for Guardrails (Python 3.11, `transformers`, `nemo`)
- [ ] Write `Dockerfile` for Orchestrator (Python 3.11, `langgraph`, `langfuse`)
- [ ] Write `Dockerfile` for Tracing collector
- [ ] Write `Dockerfile` for Embed servers (×3, one image with model env var)
- [ ] Write `Dockerfile` for LLM Manager (FastAPI, `httpx`, `llama_cpp`)
- [ ] Create `docker-compose.prod.yml` with networks, volumes, health checks, restart policies
- [ ] Test `docker compose up -d` on H200 host
- [ ] Document Vast.ai host-venv fallback (no Docker)

### Phase 3: CI/CD (Week 3–4)
- [ ] `.github/workflows/ci.yml`: lint + test + docker build (dry-run)
- [ ] `.github/workflows/cd.yml`: deploy to Vast via SSH on `main` merge
- [ ] Configure GitHub branch protection (Rulesets) — already planned
- [ ] Add `Dockerfile` lint (`hadolint`) to CI
- [ ] Add `docker-compose config` validation to CI

### Phase 4: Model Optimization (Week 4–6)
- [ ] Research TensorRT-LLM conversion for Gemma-4-31B
- [ ] Convert HF GGUF → TensorRT-LLM engine (FP8 on H200, INT8 on RTX 3090)
- [ ] Deploy Triton server with `tensorrtllm` backend
- [ ] Benchmark: tokens/s, TTFT, VRAM usage vs llama.cpp baseline
- [ ] Document quantization tradeoffs (FP8 vs INT4 vs INT8)
- [ ] If TensorRT-LLM too complex: evaluate `vLLM` as alternative (simpler, good perf)

### Phase 5: Production Hardening (Week 6–8)
- [ ] Reverse proxy (Nginx/Traefik) with TLS, rate limiting
- [ ] Prometheus + Grafana dashboards (service uptime, GPU VRAM, request latency)
- [ ] Alertmanager: service-down, high latency, OOM alerts
- [ ] Centralized logging (Loki/EFK) — replace `/tmp/*.jsonl`
- [ ] Secrets: move `.env` to Vault or GitHub Secrets + runtime injection
- [ ] Blue/green or rolling restart strategy for zero-downtime deploys
- [ ] Disaster recovery: postgres backup, model checkpoint restore

---

## 4. Tooling Recommendations Summary

| Category | Recommended Tool | Why |
|----------|-----------------|-----|
| CI/CD | GitHub Actions | Repo on GitHub, free, integrated with branch protection |
| Container runtime | Docker + Docker Compose | Simple, matches existing `deploy/docker/` |
| Model serving | NVIDIA Triton + TensorRT-LLM | Best GPU utilization, dynamic batching, FP8 on H200 |
| Alternative model server | vLLM | Simpler than Triton, excellent throughput |
| Reverse proxy | Traefik or Nginx | TLS termination, routing, rate limiting |
| Monitoring | Prometheus + Grafana | Already partially deployed (`:19090`, `:13001`) |
| Alerting | Prometheus Alertmanager | Integrated with Prometheus |
| Logging | Loki or ELK | Centralized, queryable |
| Secrets | GitHub Secrets + runtime inject | No new infra for now |
| Process mgmt (Vast) | supervisord / systemd user | No Docker on Vast |

---

## 5. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Vast.ai no Docker → can't containerize there | Keep host venv path; Docker only for H200/privileged hosts |
| TensorRT-LLM conversion complexity | Fallback to llama.cpp (current) or vLLM |
| Gemma-4-31B too large for single GPU | Model parallelism (MP=2) across 2× H200 or RTX 3090s |
| Breaking changes during containerization | Feature flag: keep old start.sh working until new stack verified |
| Secrets in `.env` committed accidentally | `.gitignore` already blocks `*.env`; add pre-commit hook |
| Long context overflow (663KB prompt) | Triton dynamic batching + max context config; app-level truncation |

---

## 6. Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Gemma tokens/s (H200) | ~TBD (baseline needed) | 2–3× via TensorRT-LLM FP8 |
| TTFT (time-to-first-token) | ~TBD | < 2s for RAG queries |
| VRAM per Gemma backend | ~TBD | 30–40% reduction via quantization |
| Deploy time | Manual (~10 min) | Automated (< 2 min via CI/CD) |
| Service uptime | N/A (manual restart) | 99.9% with auto-restart |
| Rollback time | Manual | < 1 min (previous image tag) |

---

## 7. Immediate Next Steps (You can approve)

1. **Approve this plan** — confirm which areas to prioritize
2. **Provide H200 access / Docker confirmation** — can we build images there?
3. **Provide Vast.ai SSH details** — for CI/CD deploy testing (or I document the commands without running)
4. **Decide on CI/CD** — GitHub Actions (recommended) vs. Jenkins vs. other
5. **Decide on model optimization target** — TensorRT-LLM vs. vLLM vs. keep llama.cpp

Once approved, I'll start implementing Phase 1 (audit + Dockerfiles) and Phase 2 (CI/CD workflows).
