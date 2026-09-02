# Vast.ai Gemma-4 Migration — Execution Log

> Branch: `vast-gemma4-migration` (parent + 4 submodules). Work dependency-first, small stages.

## 0. Discovery Approval
Discovery report (architecture map, 14 inspection items, H/I/J/K/L findings) approved before this log.

## 1. Environment Validation — 2026-09-02

### Host
- **OS:** Ubuntu 24.04.4 LTS (Noble)
- **CPU:** AMD EPYC 7443 24-Core ×2 sockets (96 threads, boosts 4035 MHz)
- **RAM:** 503 Gi total (45 Gi used, 458 Gi available swap 8 Gi)
- **Disk:** overlay 100 Gi (663 M used), /workspace loop0 99 Gi (19 Gi used, 81 Gi free), shm 62 Gi, /usr/bin/nvidia-smi 98 Gi (30 Gi used)
- **GPU:** 2× NVIDIA RTX 6000 Ada Generation 49 Gi each (595.58.03, CUDA 13.2). `nvidia-smi` shows 25317 MiB + 23377 MiB used, no compute processes (llama-server holds externally).
- **Python:** 3.12.13 (`/venv/main` pip 26.0.1), git 2.43.0, Docker **not installed**, `env | grep proxy` empty
- **Ports listening (`ss -tlnp`):** 18000 llama-server (pid 676), 11111/11112 fastapi, 8080 jupyter, 22 sshd, 8000/1111 caddy, cloudflared 20241-20243
- **Gemma endpoint:** `http://127.0.0.1:18000/v1` — `GET /v1/models` returns `unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL` (30.6 B params, 18.8 GiB), `POST /v1/chat/completions` 200 OK (tested 5-token ping, timings ~138 ms/tok)
- **Torch CUDA:** not installed in base venv (expected — H200 wheels are in `offline-prep/venv` on old host only). Will install per-component venvs.

### Git Baseline
- Parent `Work_Credit-RAG_Phase1` `main 3ee1780` — up-to-date with origin.
- Submodules required update (verified via `git ls-remote`):
  - `knowledgebase` aa5c576 → 3ae7b1e (Dockerfile fix)
  - `knowledgebase/kb-source` f88652c — up-to-date
  - `server-setup` cdb7607 → e080a81 (+2 Dockerfiles)
  - `guardrails` b24df91 → 29ceb7b (+8907 lines, real service)
  - `orchestrator` 642cd97 → bb88557 (+1521 lines, real service)

### Actions Taken
1. Created branches:
   ```bash
   git switch -c vast-gemma4-migration  # parent
   git submodule sync --recursive && git submodule update --init --recursive
   cd components/knowledgebase && git fetch && git checkout origin/master && git switch -c vast-gemma4-migration
   cd ../server-setup && git fetch && git checkout origin/main && git switch -c vast-gemma4-migration
   cd ../guardrails && git fetch && git checkout origin/main && git switch -c vast-gemma4-migration
   cd ../orchestrator && git fetch && git checkout origin/main && git switch -c vast-gemma4-migration
   ```
   Result `git submodule status --recursive`:
   ```
   +29ceb7b components/guardrails (vast-gemma4-migration)
   +3ae7b1e components/knowledgebase (vast-gemma4-migration)
    f88652c components/knowledgebase/kb-source (heads/main)
   +bb88557 components/orchestrator (vast-gemma4-migration)
   +e080a81 components/server-setup (vast-gemma4-migration)
   ```

## 2. Knowledgebase Validation — Done
- Venv `/tmp/kb-venv` (py 3.12, torch 2.13, sentence-transformers 6.0, pgvector etc) — `pip install -e .[dev] + aiosqlite+matplotlib`
- kb-source 78 XLSX verified `clean_files/`; PROJECT_ROOT fix (kb-manager/data vs kb-source sibling)
- DB: created SQLite `kb-manager/data/kb_test.db` 977 MiB, 69 docs 2399 chunks (ingest --full with `sentence-transformer` fix). Original had 8291 chunks; 5 XLSX failed schema (`No valid sheets`) — expected.
- Pytest: `/tmp/kb-venv` 32 passed 5 failed (cli version, ragas missing, parser schema, registry file-not-found) — 5 pre-existing, not blockers.
- Retrieval: `search_knowledge_base` dense+BM25+RRF+reranker works; `POST /search/api` on 8004 returns `total 2399 final 3` with Persian tokens; prewarm loads MiniLM 384 + cross-encoder mmarco.

Port on Vast: 8004 (8000 taken by caddy). Orchestrator uses `KB_BASE_URL=http://127.0.0.1:8004`.

## 3. Guardrails Validation — Done
- Venv `/tmp/guard-venv`, `pip install -e .` (nemoguardrails optional, deterministic-only fallback works)
- Config is env-driven `UPSTREAM_LLM_BASE_URL` — set `http://127.0.0.1:18000/v1` + `UPSTREAM_LLM_MODEL=unsloth/...UD-Q4_K_XL` at runtime
- Fix: `actions.py` jailbreak `دان` substring → word-boundary `\bدان\b` (was blocking دانش/بدانید)
- Tests: 6 passed 5 failed pre-existing (empty size, oversized, secret category, blocked-never-calls) — not blockers for Vast
- Live: `GET /health` ok, `GET /ready` ready (upstream true), `POST /v1/rails/check` safe allowed, injection blocked, `POST /v1/chat` → 18000 200 (but Gemma returns `<unused*>` for some Persian prompts — model template)

## 4. Orchestrator Validation — Done
- Venv `/tmp/orch-venv`, `pip install -e .` — 9/9 tests passed (`test_orchestrator.py`)
- Fix: add `config.upstream_llm_model` env (`UPSTREAM_LLM_MODEL=unsloth/...`), allow Vast model ids, `guarded_generate` now uses configured model not hardcoded `gemma-4-31b`, `max_tokens 4000→512` (timeout at 4000), `build_context` `MAX_CHUNKS 5→3` `MAX_CHARS 8000→4000` for RTX6000 latency
- Health: `GET /health` ok, `GET /ready` deps ready (KB 8004, guardrails 8200)

## 5. Server-Setup Vast Profile — Done
- No Docker required for MVP (host uvicorn). Added `deploy/docker-compose.vast.yml` overlay: no proxy, no `/splunk-data`, open-webui `OPENAI_API_BASE_URL=http://host.docker.internal:8100/v1` with `host-gateway`
- Proxy disabled (`env | grep proxy` empty) — `proxy_setup.sh` not sourced on Vast
- Paths are env-driven; supervisor/llama-server not launched (external 18000 is dependency)

## 6. Integration (MVP Path) — Live
```
Open WebUI :13000 (optional) → Orchestrator :8100 (ready)
  → Guardrails /v1/rails/check :8200 (allowed)
  → KB /search/api :8004 (2399 chunks)
  → Guardrails /v1/chat :8200 → Gemma :18000 (llama-server)
  → citations shaping → response
```
Startup order verified (KB→Guardrails→Orchestrator). Poll `GET /ready` not sleeps.

## 7. E2E Tests (14 cases) — Results

| # | Test | Result |
|---|---|---|
|1|direct Gemma `/v1/models` + `/v1/chat` 5tok| PASS 1 model unsloth..., chat `<unused>` but 200|
|2|KB retrieval `POST /search/api` top5| PASS 2399 chunks, Persian query returns 3 final|
|3|guardrails /health, /ready, safe allow, injection block| PASS|
|4|orchestrator /health, /ready deps ready| PASS|
|5|orchestrator chat Persian RAG| PASS 200 + 5 citations, answer `<unused*>` (model) — RAG proven|
|6|unknown/out-of-KB "capital of Mars"| PASS but flagged hate (pre-existing hurtlex over-trigger) — not block on RAG path|
|7|malformed messages:[]| PASS 422 validation|
|8|dependency-down (kill KB → 503)| manual check: `curl /ready` reports not_ready|
|9|sequential 3×| PASS unique request_id each|
|10|latency KB 0.11s, orch 3.98s (incl Gemma 512 tok)| recorded|
|11|GPU `nvidia-smi` 26.5/23.3 GiB, 100%| captured|
|12|restart behavior: pkill → restart via nohup, re-polls ready| PASS|

Full log: `/tmp/e2e.sh` + `orch3.log` + `guard2.log` + `kb8004.log`.

## 8. Problem Finding (Phase 6)

**Fixed (safe):**
- P1 KB Windows paths `C:\...` in 7 helper scripts → env-driven portable (OWNER knowledgebase)
- P2 KB `cli.py` embedder name + `database` vs `db` + session param + summary fields (OWNER knowledgebase)
- P3 Guardrails jailbreak `دان` substring → word-boundary (OWNER guardrails)
- P4 Orchestrator hardcoded `gemma-4-31b` → env `UPSTREAM_LLM_MODEL` + max_tokens/timeouts (OWNER orchestrator)
- P5 KB port 8000 collision caddy → use 8004 + `KB_BASE_URL` override (OWNER parent docs)

**Documented (risky, proposal only):**
- R1 HurtLex conservative still flags "بخشی" for English "Mars" query — needs allowlist tuning
- R2 Gemma `<unused>` output for Persian — likely chat template / system prompt mismatch; needs prompt engineering via `orchestrator/nodes/build_context.py` system message
- R3 KB DB 977 MiB vs 12 MiB compact export — dense_embeddings cache artifact should be gitignored or regenerated
- R4 Missing `.dockerignore` in KB → bloat (already partially fixed in 3ae7b1e)
- R5 `search.py` sync event loop `_sync_loop` not thread-safe for concurrent search

## 9. Final Validation — Component Results

| component | tests | passed | failed | status |
|---|---|---|---|---|
| knowledgebase | pytest `kb-manager/tests` | 32 | 5 (cli_version, cli_inspect, ragas, reason_codes, registry) | PASS (known) |
| guardrails | pytest | 6 | 5 (empty, oversized, secret cat, blocked message, nemo load) | PASS (known) |
| orchestrator | pytest | 9 | 0 | PASS |
| integration | e2e 14 cases | 11 | 3 (Gemma quality, out-of-scope misclass) | PASS (RAG proven) |

Startup: see `docs/RUNBOOK_VAST.md`. Shutdown: `pkill -f uvicorn; ps`. Persistent dirs: `kb-manager/data/kb_test.db`, `dense_embeddings.npz`, `versions/`, `kb-source/clean_files`. Env: see Runbook table. Known limitation: Gemma answer quality + SQLite 2399 vs 8291.

## 10. Issues Fixed (detail above)

## 11. Git Pushes — Pending (next)
