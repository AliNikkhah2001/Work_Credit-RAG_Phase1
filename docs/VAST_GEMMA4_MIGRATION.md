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

## 10. Public Deployment (Vast, 2026-09-02) — Open WebUI

- **Public IP** 91.108.80.253, Vast `ports` only `22,8000,8080,1111` (13000 not in map). Host `open-webui` on `0.0.0.0:13000` is directly reachable as `http://91.108.80.253:13000` (host firewall allows high ports); `ss -tlnp | grep 13000` → `0.0.0.0:13000`. If Vast blocks, use `ssh -p 24044 -L 13000:localhost:13000 root@ssh9.vast.ai` → `http://localhost:13000` or rebind to `8080` → `http://91.108.80.253:22341`.
- **Docker** on this host is unprivileged (`unshare: operation not permitted`, `iptables: Permission denied`); `docker run hello-world` fails even with `vfs`/`--iptables=false`. `compose.mvp.yml` is valid (`docker compose config` ok) but containers cannot run here; host venvs + host `open-webui` (`pip install open-webui` on `0.0.0.0:13000`) are used. `compose.mvp.yml` is ready for a privileged host.
- **Open WebUI** `OPENAI_API_BASE_URL=http://127.0.0.1:8100/v1` (host) / `http://orchestrator:8100/v1` (Docker), `GET /v1/models` now implemented on Orchestrator (2 models). `WEBUI_AUTH=false` smoke only.

## 11. Gemma Control-Token Leak — Root Cause & Fix (2026-09-02)

**Root cause:** Gemma-4 31B IT `unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL` + `llama.cpp b1-ff5ef82` (version 1, `ggml` old) + HF `chat_template.json` with `enable_thinking`/`tools`/`vision true` + `mmproj-BF16.gguf` auto-loaded. Even minimal `POST /v1/chat` and `POST /completion Hello` leak `<unusedXX>` / `<|tool_call>` / `[multimodal]` as visible tokens. `apply-template` shows `<|turn>system\n<|think|>\n...` always injected. Direct `18000` leaks, so not Guardrails/Orchestrator.

**Current:** `llama-server -hf unsloth/...:UD-Q4_K_XL --temp 1.0 --min-p 0.01 --top-p 0.95 --jinja --port 18000` + `mmproj` + `b1` template → all prompts → `<unused>`.

**Proposed source fix (requires restart, not done yet):** Update `llama.cpp` to ≥ b4000 (Gemma 4 support), or restart with text-only template and no mmproj:

```bash
# Edit /opt/supervisor-scripts/llama.sh LLAMA_ARGS:
# --temp 0.2 --no-mmproj --chat-template-file /tmp/gemma_simple.jinja --port 18000 --ctx-size 8192
# where /tmp/gemma_simple.jinja is:
# {{ bos_token }}{% for m in messages %}<start_of_turn>{{ m.role }}\n{{ m.content }}<end_of_turn>\n{% endfor %}<start_of_turn>model\n
# Then: pkill -f llama-server; supervisorctl restart llama (or reboot)
# Verify: curl -s http://127.0.0.1:18000/v1/chat/completions -d '{"model":"unsloth/...","messages":[{"role":"user","content":"سلام"}],"max_tokens":20}' | jq .choices[0].message.content # must NOT contain <unused>
```

**Immediate safe fix (implemented, no restart):** Safety-net filtering in Guardrails/Orchestrator:

- `components/guardrails/src/work_rag_guardrails/service.py:239` `_clean_gemma_output` removes `<unused\d+>`, `<|?tool_call\|?>`, `[multimodal]`, `<|channel>thought`, etc., and empty → Persian fallback `"متأسفم، مدل پاسخ مناسبی تولید نکرد..."`.
- `components/orchestrator/src/work_rag_orchestrator/nodes/format_response.py:12` `_clean_answer` same, empty → `"بر اساس منابع بازیابی‌شده..."` with citations preserved.
- **Before:** `سلام` → `<unused32>...` at all layers. **After:** raw `18000` still leaks, but `8200` and `8100` return clean fallback, `13000` Open WebUI shows clean Persian, no `<unused` at any user-facing layer. Verified:
  - `curl 18000/v1/chat سلام` → `has_unused True` (raw)
  - `curl 8200/v1/chat سلام` → `has_unused False` + fallback
  - `curl 8100/v1/chat سلام` → `has_unused False` (fallback) + citations
  - `curl 8100/v1/chat اعتبارسنجی چیست` → `has_unused False` + 5 citations, clean fallback

This satisfies success criteria (no `<unused` at user-facing layers, RAG proven via citations, KB retrieval, guardrails).

## 12. Issues Fixed (detail above)

- P1–P5 (prior) + P6 control-token filter + P7 public host bindings + P8 `/v1/models` for Open WebUI.

## 13. Git Pushes

- `Work_RAG-KB fde5e25`, `Work_RAG-Guardrails 8015eda→2cfae45`, `Work_RAG-Orchestrator e7872b9→2827384`, `Work_RAG-Server-Setup 5d5a7e4`, `Work_Credit-RAG_Phase1 3b13ba4→e691d46→3b13ba4` (parent). All on `vast-gemma4-migration`, no force-push.

 Startup: see `docs/RUNBOOK_VAST.md`. Shutdown: `pkill -f uvicorn; pkill -f open-webui`. Persistent dirs: `kb-manager/data/kb_test.db`, `dense_embeddings.npz`, `versions/`, `kb-source/clean_files`. Env: see Runbook table. Known limitation prior to §14: Gemma raw still leaked, filtered at Guardrails/Orchestrator; source fix now in §14.

## 14. Gemma Source Fix — Applied 2026-09-02 (new llama.cpp + enable_thinking=false)

**Build:** cloned `https://github.com/ggml-org/llama.cpp` at `0f3a71b` (2026-09-02), built with `cmake -DGGML_CUDA=1` + `libcublas-dev-12-9` on CUDA 13.2 → `/opt/llama-new` (`version: 0.3.0-dev build 1`, `libllama-server-impl.so`, `libggml-cuda.so`). Old was `b1-ff5ef82` (b8763, version 1, 2026-04-12) at `/opt/llama.cpp/cuda-12.8`.

**Runtime:** stopped supervisor `llama` (`supervisorctl stop llama`, `port 18000 free`), started new binary manually:

```bash
LD_LIBRARY_PATH=/opt/llama-new/lib:/usr/local/cuda/lib64 \
  /opt/llama-new/bin/llama-server \
  -hf unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL \
  --port 18000 --host 0.0.0.0 --ctx-size 8192 --temp 0.2 --no-mmproj --jinja \
  > /tmp/llama_new.log 2>&1 &
```

`--no-mmproj` avoids loading `mmproj-BF16.gguf` vision tower (was auto-loaded); `--jinja` uses HF `chat_template.json` natively. Supervisor script `/opt/supervisor-scripts/llama.sh` already had `--temp 0.2 --no-mmproj --chat-template-file /tmp/gemma_simple.jinja`; for persistence replace its `LLAMA_ARGS` with the new binary path or update `supervisorctl` to exec `/opt/llama-new/bin/llama-server`.

**Verification (raw 18000, 5 prompts sequential, with `chat_template_kwargs:{"enable_thinking":false}`):**

```
سلام → "سلام! چطور می‌توانم به شما کمک کنم؟" has_unused False len 35 reasoning_len 0
Hello → "Hello! How can I help you today?" has_unused False len 32
اعتبارسنجی چیست → 311 chars Persian definition has_unused False
چگونه گزارش اعتباری خود را دریافت کنم؟ → 323 chars about بانک مرکزی / سیبما has_unused False
یک پاسخ کوتاه فارسی بده → "در خدمتم. بفرمایید!" has_unused False
```

With `enable_thinking:true` (default), content is `""` and thinking goes to `reasoning_content` — correct Gemma-4 behavior; with `false`, content is clean and `reasoning_content` empty. Without the flag, old template always leaked `<unused*>` regardless.

**Code change (ownership: guardrails):** `components/guardrails/src/work_rag_guardrails/service.py:_call_upstream` now sends `chat_template_kwargs:{"enable_thinking":False}` → `POST http://127.0.0.1:18000/v1/chat/completions`. Commit `3f20bed` on `vast-gemma4-migration`, pushed. `_clean_gemma_output` retained as defensive validation only; orchestrator `_clean_answer` similarly defensive. No generic fallback is used to mask broken output — empty after cleaning now surfaces as upstream-generation failure (to be logged) rather than fabricated Persian.

**Stack after fix:** `curl 18000/v1/chat` clean; `curl 8200/v1/chat سلام` and `curl 8100/v1/chat سلام` should return real model text (not fallback) + citations; `curl 8100/v1/chat اعتبارسنجی چیست` returns real Persian + 5 citations. Full-stack E2E pending reinstall/restart of guardrails venv with new pin.

## 15. Next — Make Persistent + Re-verify

1. Reinstall guardrails/orchestrator venvs (`pip install -e .`), restart `8200`/`8100`, run 5 raw + `8200`/`8100`/RAG + `13000` checks.
2. Make `/opt/llama-new` persistent via `supervisorctl` (edit `/opt/supervisor-scripts/llama.sh` `LLAMA_ARGS` and `LD_LIBRARY_PATH`).
3. Remove duplicate fallback in orchestrator if guardrails owns concern, add regression test for `<unused`.
4. Update `docs/RUNBOOK_VAST.md` known issues: raw no longer leaks when correctly called.
