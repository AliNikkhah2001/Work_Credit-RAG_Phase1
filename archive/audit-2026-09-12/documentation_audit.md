# Documentation Audit — Work Credit RAG Phase 1

Generated: 2026-09-12 | Auditor: Agent 1 (Repository Documentation Explorer)

---

## 1. Root README (`README.md`)

**Purpose:** Umbrella repo overview, submodule composition, MVP deployment, verification commands, benchmark reports, links.

**Audience:** New contributors, ops engineers, researchers evaluating the platform.

**Coverage:**
- ✅ Submodule table (4 components + pins)
- ✅ MVP architecture diagram (Mermaid)
- ✅ Request flow (text)
- ✅ Vast deployment details (instance specs, URLs)
- ✅ Quick start (host venvs, ports, env vars)
- ✅ Docker variant note
- ✅ Live status with detailed fix logs (Gemma, Guardrails, KB, Orchestrator)
- ✅ Sample curl commands for every service
- ✅ Benchmark results (120 questions, 4 prompt versions, tables + plots)
- ✅ Reranker shootout table (7 candidates)
- ✅ Done/Pending checklist with commit SHAs
- ✅ Verification scripts
- ✅ UI panels (WebUI, Langfuse v2, Studio)
- ✅ Ownership rules
- ✅ Submodule update procedure
- ✅ License + Links to runbook/migration/MVP plan

**Missing / Gaps:**
- ❌ No badges (Python version, license, build status)
- ❌ No table of contents anchors for long file
- ❌ No "Architecture" section with system diagram (only MVP flow)
- ❌ No consolidated "Models" table across all components
- ❌ No "Configuration" section aggregating all env vars
- ❌ No "Troubleshooting" section (known issues scattered in status)
- ❌ No "Contributing" / "Code of Conduct" / "Security" sections
- ❌ Quick start uses port 8004 for KB but AGENTS.md says 8000 — inconsistency
- ❌ Docker variant references `compose.mvp.yml` but deploy/docker uses different stack
- ❌ Some links point to `docs/benchmark-report/` but directory is empty in repo (built at runtime)

---

## 2. AGENTS.md

**Purpose:** Agent operating manual — repo map, service table, workflows, git rules, Vast gotchas, never-do list.

**Audience:** AI agents, ops engineers, anyone working on the Vast deployment.

**Coverage:**
- ✅ Repo map with ownership
- ✅ Service table (8 services: ports, venvs, key env vars)
- ✅ Standard workflows (health, restart one, full restart, E2E smoke, view traces, Studio)
- ✅ Git rules (pins, component fix flow, deployment branches, never force-push, secrets)
- ✅ Vast gotchas (9 items: unprivileged, NAT ports, loopback-only, phantom dentries, HF cache, asyncpg bug, Langfuse envelope, Gemma thinking flag, VRAM)
- ✅ Never-do list (9 items)

**Missing / Gaps:**
- ❌ No version/date stamp
- ❌ No link to contributing guide
- ❌ Service table instance ID (`50713720`) and date (`2026-09-12`) hardcoded — will stale
- ❌ No diagram of startup dependency order

---

## 3. Orchestrator README (`components/orchestrator/README.md`)

**Purpose:** Describe LangGraph orchestration and public API contract.

**Audience:** Component developers, integrators.

**Coverage:**
- ✅ Responsibility statement
- ✅ MVP graph diagram (text)
- ✅ MVP API contract table (health, ready, chat/completions)
- ✅ Initial config (env vars)
- ✅ Planned directory structure
- ✅ Initial state contract (TypedDict)
- ✅ Explicit scope exclusions (no retries, memory, rewriting, etc.)
- ✅ Links to parent MVP_INTEGRATION_PLAN.md

**Missing / Gaps:**
- ❌ **Status line says "not implemented yet" but it IS implemented** (see AGENTS.md, live on Vast)
- ❌ No actual implementation docs (graph.py nodes, tracing, schemas)
- ❌ No request/response examples
- ❌ No `schemas.py` field documentation
- ❌ No tracing/observability section
- ❌ No Studio/local debugger docs (exists in STUDIO.md but not linked)
- ❌ Port in config (8100) matches AGENTS.md but quickstart in root uses different KB port
- ❌ `REQUEST_TIMEOUT_SECONDS=120` not documented in AGENTS.md env table

---

## 4. KB Manager README (`components/knowledgebase/kb-manager/README.md`)

**Purpose:** Comprehensive KB management system docs — versions, pipeline, benchmarks, UI, config, CLI, troubleshooting.

**Audience:** KB engineers, data scientists, ops, researchers.

**Coverage:**
- ✅ Version history table (v1→v8 with metrics)
- ✅ Current status (v8 pgvector HNSW, 103 docs, 6593 chunks)
- ✅ Detailed v7 changelog + known gaps
- ✅ Quick start (pip install, run_server.py)
- ✅ Ingest CLI + Python snippet
- ✅ Retrieval pipeline diagram (text)
- ✅ Reranker backbones table (8 models, status, loader notes)
- ✅ Benchmark results (v5 120 queries, v7 IVA 15, v8 HNSW CPU/GPU)
- ✅ Web UI pages table (12 pages with URLs)
- ✅ Project structure tree
- ✅ Configuration table (12 env vars)
- ✅ Running tests
- ✅ CLI commands
- ✅ Transparency section (Excel→chunks pipeline with file:line refs)
- ✅ Troubleshooting (PowerShell blocked error)
- ✅ QA-Aware Retrieval Experiment (planned)
- ✅ Roadmap/Remediation table with priorities/owners/estimates
- ✅ License

**Missing / Gaps:**
- ❌ Status says v8 is current but AGENTS.md shows KB at `8b8f6e5` (v7 era) — inconsistency
- ❌ v8 metrics show "Hit@5 0.00*" for 5q verbatim — asterisk not explained in table
- ❌ Benchmark v9 "running" — no results, placeholder only
- ❌ No diagram of HNSW vs file-based architecture
- ❌ `KB_DB_MODE=pgvector` but `KB_DB_URL` overrides — precedence not clear
- ❌ No model card for embedding model (`paraphrase-multilingual-MiniLM-L12-v2`)
- ❌ Web UI port 8001 mentioned but AGENTS.md says 8000 — inconsistency
- ❌ Caddy reverse proxy (32221→8000) is Vast-specific, not documented as such
- ❌ Troubleshooting only covers PowerShell — no KB-specific issues (empty search, pgvector fallback, embedding model download)
- ❌ `versions/v1..v4` READMEs are archival but not marked as such

---

## 5. KB Source README (`components/knowledgebase/kb-source/README.md`)

**Purpose:** Document the source files submodule.

**Coverage:**
- ✅ Contents table (archive, extracted files)
- ✅ Submodule path in main repo
- ✅ Clone command
- ✅ Ingest command
- ✅ Notes (UTF-8, de-dup)

**Missing / Gaps:**
- ❌ No file listing of the 78 XLSX files
- ❌ No schema description of the Excel sheets
- ❌ No version/date beyond "Source date 31 Tir 1405"
- ❌ No link to transparency/parsing docs in KB Manager

---

## 6. Guardrails README (`components/guardrails/README.md`)

**Purpose:** NeMo Guardrails boundary component.

**Audience:** Guardrails developers, integrators.

**Coverage:**
- ✅ Responsibility
- ✅ MVP API contract table (health, ready, rails/check, chat/completions)
- ✅ Planned config (env vars with UPSTREAM_LLM_BASE_URL=9000)
- ✅ Planned directory structure
- ✅ MVP safety scope (6 items)
- ✅ Link to parent MVP_INTEGRATION_PLAN.md

**Missing / Gaps:**
- ❌ **Status says "not implemented yet" but IT IS IMPLEMENTED** (live on :8200, see AGENTS.md, root README status)
- ❌ No actual implementation docs (service.py stages, risk/scorer, semantic interface, actions.py, hurtlex allowlist)
- ❌ Port in config (8200) matches AGENTS.md but UPSTREAM_LLM_BASE_URL=9000 is WRONG — actual is 18000
- ❌ No request/response examples for `/v1/rails/check` or `/v1/chat/completions`
- ❌ No Colang policy documentation (rails.co)
- ❌ No observability/risk scoring/semantic interface docs (exist in code, not README)
- ❌ No HurtLex allowlist documentation (15 lemmas, evidence, tests)
- ❌ No test documentation (test_hurtlex_allowlist.py 26 tests)
- ❌ No link to guardrails/kb/ or actual config files

---

## 7. Guardrails KB README (`components/guardrails/kb/README.md`)

**Purpose:** Document the HurtLex allowlist and Persian profanity lists.

**Status:** File exists but not read — need to check.

---

## 8. Server Setup README (`components/server-setup/README.md`)

**Purpose:** Verified runbook for H200 offline RAG dev/prod environment.

**Audience:** Infra engineers, ML engineers setting up H200 box.

**Coverage:**
- ✅ Verified runbook badge (date, host, verification)
- ✅ Quick start (proxy, hardware, venv, docker, embeddings, LLMs, manager, OpenCode, benchmarks)
- ✅ Hardware & Environment table (verified nvidia-smi)
- ✅ Proxy configuration (comprehensive, persists to bashrc/apt/git/docker)
- ✅ Repo layout tree
- ✅ Python venv & requirements (with versions, conflict resolutions)
- ✅ Model files inventory (17 repos, table with HF links, sizes, quantization, benchmark means)
- ✅ Docker data plane (9 containers, verified docker inspect)
- ✅ Embedding services (3 live, ports, models, verify commands)
- ✅ LLM services (11 registry models, supervisor for 5× gemma, verify commands)
- ✅ LLM Inference Manager (OpenAI-compatible gateway, endpoints table, SQLite schema, auth, proxy fix)
- ✅ OpenCode integration (config, live demo transcript, hangs explanation)
- ✅ Benchmark code (7 scripts, Persian 7-task suite, reproduction commands)
- ✅ Benchmark results table (9 models, 7 tasks, tok/s)
- ✅ Reports/Plots (10 PNG + Plotly twins)
- ✅ Plan & Progress (P0-P5 with checklists)
- ✅ Troubleshooting (8 items)
- ✅ History (daily logs)

**Missing / Gaps:**
- ❌ This is the **Server Setup submodule** — not the Vast deployment (different hardware, different ports, different stack)
- ❌ No clear disclaimer: "This is for H200 `ai-gpu1`, NOT for Vast RTX 3090"
- ❌ Port conflicts: embeddings on 8001/8002/8003, LLMs on 8080-8090, manager on 9000 — none match Vast ports
- ❌ `compose.mvp.yml` in parent uses different stack entirely
- ❌ Docs folder has multipage report site but no index/README linking them
- ❌ No "Architecture" diagram for the H200 stack
- ❌ Troubleshooting section is minimal (only 8 items)

---

## 9. Server Setup Docs (`components/server-setup/docs/`)

- `README.md` — index of guides/reports/history/plan
- `guides/03-services-and-endpoints.md` — service endpoints table
- `guides/09-reboot-runbook.md` — reboot procedure
- `history/` — per-session logs (multiple files)
- `reports/` — 10 PNG + Plotly HTML + markdown reports
- `plan.md` — deliverable plan
- `reports/README_runbook_outline.md` — runbook structure
- `history/README.md` — history index

**Gap:** No single "Architecture" or "System Overview" doc for the H200 stack.

---

## 10. Deploy Docker README (`deploy/docker/README.md`)

**Purpose:** Full-stack Docker Compose for privileged CUDA hosts.

**Coverage:**
- ✅ Services table (9 services, images, in-stack URLs, host ports)
- ✅ Named volumes, network
- ✅ Prerequisites (Docker, NVIDIA Container Toolkit, disk, GPU)
- ✅ Quickstart (cp .env.example, edit MODEL_FILE, docker compose up)
- ✅ Startup order (healthchecks)
- ✅ Ports & debug access (override file pattern, never publish 18000/postgres/redis)
- ✅ KB ingest (bind-mount, cli commands, search sanity)
- ✅ Health checks (container-level, in-chat E2E)
- ✅ Teardown/rebuild
- ✅ Troubleshooting (6 items: OOM, build slow, unused leaks, KB empty, model downloads, MODEL_FILE path, unprivileged hosts)

**Missing / Gaps:**
- ❌ `.env.example` not in repo (referenced but missing — must create)
- ❌ No diagram of container network/dependencies
- ❌ `LLAMA_SERVER_BIN` prebuilt path not documented where to get it
- ❌ No Langfuse v2 setup in this stack (uses langfuse:2 image but no seeding docs)
- ❌ No mention of `compose.mvp.yml` relationship (older variant)

---

## 11. Eval README (`eval/README.md`)

**Purpose:** KB RAG evaluation results on Vast.

**Coverage:**
- ✅ Dataset source (test_questions.json, 120 questions)
- ✅ Method (5 steps: guardrails input → RAG → checks → tag → citation_hit)
- ✅ Results after fixes (20/20 ok, 0/120 blocked input/output)
- ✅ Before fix comparison (specific lemma blocks)
- ✅ After fix details (allowlist 11 lemmas, profanity len>2)
- ✅ Wrong samples handling
- ✅ Files list
- ✅ Next tweaks (3 items)

**Missing / Gaps:**
- ❌ Allowlist says 11 lemmas but root README says 15 — inconsistency
- ❌ No link to actual test scripts (`/tmp/eval_kb_rag2.py`, `/tmp/full_eval.py` — not in repo)
- ❌ No reproduction commands that work from repo root
- ❌ No benchmark methodology details (cosine similarity, LLM-judge prompt)
- ❌ No link to `eval/run_llm_answer_benchmark.py` etc. from root README

---

## 12. Contracts README (`contracts/README.md`)

**Purpose:** Cross-component JSON Schema contracts.

**Coverage:**
- ✅ Contracts table (5 files, descriptions, used by)
- ✅ Versioning procedure
- ✅ Testing guidelines

**Missing / Gaps:**
- ❌ No example schema content
- ❌ No `pytest tests/contract/` in any component (not implemented)
- ❌ No contract version in filenames (all `mvp-1` implied)

---

## 13. Tracing Component (`components/tracing/`)

**Files:** `app.py` (collector), `observe.py` (new observer CLI + web endpoints)

**Missing / Gaps:**
- ❌ **No README.md at all** — critical gap for new observe endpoints (`/observe`, `/studio`, `/api/observe/*`, `/api/studio/*`)

---

## 14. Parent Docs (`docs/`)

| File | Purpose | Status |
|------|---------|--------|
| `RUNBOOK_VAST.md` | Startup, env, ports, troubleshooting | Exists, detailed |
| `VAST_GEMMA4_MIGRATION.md` | Discovery, 14 inspections, fixes, verification, HurtLex audit | Exists, detailed |
| `MVP_INTEGRATION_PLAN.md` | Cross-component implementation sequence, acceptance criteria | Exists |
| `GUARDRAILS_V2_PLAN.md` | Risk scoring, observability, semantic interface, thresholds, rollback | Exists |
| `RERANKER_MEMORY_TASK.md` | Reranker/memory task | Exists |
| `benchmark-report/` | GitHub Pages site (built at runtime) | Directory exists, empty in repo |

**Gap:** No index/README in `docs/` linking these.

---

## 15. Cross-Cutting Issues

### Inconsistencies

| Item | Root README | AGENTS.md | Component README | Actual (live) |
|------|-------------|-----------|------------------|---------------|
| KB port | 8004 (quickstart) | 8000 | 8000 / 8001 (UI) | 8000 (prod), 8004 (dev) |
| Guardrails upstream | 18000 | 18000 | **9000 (wrong)** | 18000 |
| Orchestrator port | 8100 | 8100 | 8100 | 8100 |
| Gemma port | 18000 | 18000 (127.0.0.1) | 8080-8090 (H200) | 18000 (Vast) |
| WebUI port | 13000 | 13000 | 13000 (H200:8080→13000) | 13000 |
| HurtLex allowlist | 15 lemmas | — | 11 lemmas (eval) | 15 (code) |
| KB chunks (v8) | 6593 | 2399 (v7) | 6593 | ? |
| KB docs (v8) | 103 | 69 (v7) | 103 | ? |

### Missing Documentation Types

1. **Architecture diagrams** — Only MVP flow diagram in root README
2. **Model cards** — Scattered in server-setup table, KB reranker table, guardrails missing
3. **Configuration reference** — No single table of all env vars across components
4. **Installation guide** — Three variants (Vast host venv, Docker privileged, H200) not consolidated
5. **Troubleshooting index** — Scattered across 4 READMEs
6. **API reference** — Only contract schemas, no OpenAPI/Swagger
7. **Changelog/Releases** — Only in KB Manager version table
8. **Contributing guide** — None
9. **Security policy** — None
10. **Code of Conduct** — None

---

## 16. Recommendations (Priority Order)

### P0 — Critical (blockers for new users)
1. Fix Guardrails README: update status, correct UPSTREAM_LLM_BASE_URL, document actual implementation
2. Fix Orchestrator README: update status, document actual graph/tracing/schemas
3. Create `components/tracing/README.md` for observe endpoints
4. Add `.env.example` to `deploy/docker/`
5. Resolve port inconsistencies (KB 8000 vs 8004, Guardrails upstream 9000 vs 18000)

### P1 — High (professional polish)
6. Add badges, TOC, Architecture section to root README
7. Consolidate model cards into single table in root README
8. Create unified configuration reference table
9. Add troubleshooting index in root README linking to component troubleshooting
10. Create `docs/README.md` index

### P2 — Medium (developer experience)
11. Add Mermaid architecture diagrams (system, training, inference)
12. Document actual API request/response examples in each component
13. Create CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md
14. Add CHANGELOG.md to each component (KB has version table, others don't)
15. Mark archival version READMEs (v1-v4) as deprecated

### P3 — Low (maintenance)
16. Add date/version stamps to AGENTS.md service table
17. Link STUDIO.md from Orchestrator README
18. Document transparency/benchmark UI pages from KB Manager in a user guide
19. Add script documentation for eval/ benchmark scripts
20. Archive old server-setup history files or create index

---

## 17. Artifacts Produced

- `artifacts/documentation/repository_documentation_map.json` — Machine-readable map
- `docs/documentation_audit.md` — This file
- Next: `artifacts/documentation/fact_check_report.json` (Agent 2)
- Next: `docs/architecture.md` (Agent 3)
- Next: Updated README files (Agents 4-5)
- Next: `docs/models.md`, `docs/training.md`, `docs/evaluation.md` (Agent 6)
- Next: Developer experience improvements (Agent 7)
- Next: Final review checklist (Agent 8)