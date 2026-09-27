# History — Code Audit 2026-09-27: 142 Errors & Anti-Patterns Found

**Date:** 2026-09-27  
**Branch audited:** `main` @ `7bf1be3` (parent) + `706ade0` (KB) + `f206d83` (guardrails) + `8602e1c` (orchestrator)  
**Scope:** `components/orchestrator` + `components/guardrails` + `components/knowledgebase/kb-manager` + `components/tracing` + `components/server-setup` + `deploy/` + `eval/` + `contracts/` + `scripts/`  
**Method:** Full file reads (~12k LOC) + `grep` for `except/pass`, auth, traversal, SQL, XSS, `shell=True`, hardcoded secrets | Agents: explore (very thorough) ×4  
**Report:** `/tmp/CODE_AUDIT_REPORT.md` (162 lines, also copied here)  
**Next:** Fix plan at `.opencode/plans/audit-fix-2026-09-27.md` and `AGENTS_FIX_PLAN.md`

---

## 1. Summary Counts

| Severity | Count | Must-fix before prod | Owner |
|----------|-------|----------------------|-------|
| **Critical** | 21 | Yes — exploitable / DoS / auth bypass / data-loss | All components |
| **High** | 38 | Yes — correctness / security / reliability | All components |
| **Medium** | 52 | Sprint backlog | All components |
| **Low** | 31 | Hygiene / style | All components |
| **Total** | **142** | | |

**Hotspots:**
1. `components/knowledgebase/kb-manager` — 7 Critical + 10 High (path traversal, unauth DB, unbounded disk, silent failures, `ilike` wildcard DoS, `Vector(384)` hardcode)
2. `components/tracing` + `components/server-setup/llm_inference_manager` — 6 Critical + 10 High (tracked `.env` with `postgres`/`admin123`/`sk-local-dev`, open `POST /api/public/ingestion`, CORS `*` + credentials, `shell=True`, SQLite WAL races, SSRF `STUDIO_API`, `shell=True` `du -sh`, `admin/load` command injection)
3. `components/orchestrator` — 8 Critical + 12 High (global `Exception` swallowing `HTTPException`, streaming race on shared `initial_state`, unbounded `MemorySaver`, tracing thread explosion, `faq_verified` missing `TypedDict`, `SentenceTransformer` blocking event loop, hardcoded `/splunk-data/...` path, `shared AsyncClient` timeout ignored)
4. `components/guardrails` — 6 Critical + 10 High ( `RailsConfig.from_content` list not YAML, `LLM_API_KEY` alias bypass, Persian PII `۰۹۱۲` bypass, YAML injection `base_url: {base}`, domain gate fail-open when `policies/active.yaml` missing, NeMo `""` treated as `allow`)

---

## 2. All Found Errors — Complete List

### 2.1 CRITICAL (21)

#### Orchestrator (8)

| ID | File:Line | Error | Anti-pattern | Fix |
|----|-----------|-------|--------------|-----|
| **O-C1** | `orchestrator/src/work_rag_orchestrator/api.py:526` | `HTTPException` swallowed by global `Exception` handler → `500` instead of `404/422` | `Exception` catches subclass | Register `HTTPException` handler separately or `if isinstance(exc, HTTPException): return JSONResponse(exc.status_code, {"detail":exc.detail})` |
| **O-C2** | `orchestrator/api.py:247-250` | Streaming `asyncio.create_task(node_validate(initial_state))` + `node_retrieve(initial_state)` mutate **same dict** concurrently → `query`/`blocked`/`stage_timing_ms` race, retrieval even when `blocked=True` (policy leak) | Shared mutable state across `await` | Clone `dict(initial_state)` or `if (await v_task).get("blocked"): r_task.cancel()` |
| **O-C3** | `orchestrator/graph.py:65` `state.py:13` | `MemorySaver` unbounded → `thread_id=request_id` stored forever, memory leak linear with traffic | No eviction/TTL | TTL checkpointer (Postgres/Redis) or stateless `ainvoke` or `max_history` LRU |
| **O-C4** | `orchestrator/clients/guardrails.py:26-35` | `_get_shared_client(timeout)` ignores `timeout` after first creation → `faq_verifier` 15s gets 120s client | Singleton ignores param | Key pool by timeout or make timeout per-request `client.post(..., timeout=...)` |
| **O-C5** | `orchestrator/tracing.py:66,97,153` | Every `start_trace/update_trace/trace_span` spawns `threading.Thread(daemon=True)` → thousands threads OOM, plus `trust_env` default → localhost via Squid `192.168.203.2:3128` hangs | Unbounded thread creation | Single `ThreadPoolExecutor` or `httpx.AsyncClient`, `trust_env=False` |
| **O-C6** | `orchestrator/state.py:9` `nodes/retrieve.py:72` | `faq_verified` written but missing from `RAGState` `TypedDict` → `mypy strict` fail, runtime `KeyError` | `TypedDict` incomplete | Add `faq_verified: bool` to `RAGState` |
| **O-C7** | `orchestrator/faq_direct.py:99-130` | `SentenceTransformer` load (5-30s) at import time blocks event loop on `:8100` startup | Blocking I/O in async path | Lazy-load in `asyncio.to_thread()`, pre-warm at `lifespan` |
| **O-C8** | `orchestrator/faq_direct.py:108` | Hardcoded `/splunk-data/v1/...` breaks outside H200, fallback tries hub offline and fails | Hardcoded absolute path | Move to `Settings` / env `FAQ_EMBED_MODEL_PATH` |

#### Guardrails (6)

| ID | File:Line | Error | Fix |
|----|-----------|-------|-----|
| **G-C1** | `guardrails/service.py:74` | `RailsConfig.from_content(yaml_content=config_dict.get("models", []))` passes **list** not YAML string → `TypeError` | `yaml.safe_dump({"models": ...})` |
| **G-C2** | `guardrails/service.py:211,245` | `headers={"Authorization": f"Bearer {settings.upstream_llm_api_key}"}` ignores `resolved_api_key` → Vast `LLM_API_KEY` fails | Use `settings.resolved_api_key` |
| **G-C3** | `guardrails/actions.py:275-288` | `check_pii_ir` `\b\d{10}\b` only ASCII, `۰۹۱۲` bypasses | `text = normalize_persian(text)` at top |
| **G-C4** | `guardrails/judge.py:43-46,117` | YAML injection `base_url: {base}` unescaped | Dict + `yaml.safe_dump`, use `resolved_base_url` |
| **G-C5** | `guardrails/signals.py:65-81` `judge.py:207` | Domain gate fail-open when `policies/active.yaml` missing → `allow` any off-domain | Fail-closed: `needs_domain_check` returns `True` when policy empty |
| **G-C6** | `guardrails/judge.py:173-177` | NeMo `generate()` `""` on block treated as `allow` (inverts security) | Treat `""` as `block`, verify NeMo behavior |

#### Knowledgebase (7)

| ID | File:Line | Error | Fix |
|----|-----------|-------|-----|
| **K-C1** | `kb-manager/web/routes/documents.py:104` | `file_path = upload_dir / file.filename` unsanitized → `../../etc/cron.d/pwn` arbitrary write | `Path(file.filename).name`, sanitize `[^a-zA-Z0-9._-]`, `resolve()` contained, allowlist |
| **K-C2** | `kb-manager/web/routes/*` | No `Depends(verify_token)` on any `web/routes/*` → anonymous delete/ingest | `APIRouter(dependencies=[Depends(require_auth)])` or `KB_ADMIN_TOKEN` |
| **K-C3** | `kb-manager/web/routes/ingestion_suite.py:352-377` | `from-path` copies **any** server path (`/etc/passwd`, `~/.ssh`) into attacker zip via `POST` JSON | Allowlist `KB_ALLOWED_SOURCE_ROOTS`, reject `..`, symlinks, cap files+bytes |
| **K-C4** | `kb-manager/web/routes/ingestion_suite.py:280-310` | Unbounded disk: `from-path` copies entire `/`, zip bomb `10KB→10GB`, never GCs `STAGE_ROOT` | Enforce quota 2GB, `ZipInfo.file_size` + ratio check, reaper `age>24h` |
| **K-C5** | `kb-manager/web/routes/transparency.py:212` | `like = f"%{q}%"` with `q` raw → `q=%` returns entire table (full scan DoS) | Escape `%`/`_`, `ilike(like, escape="\\")`, cap `len(q)<=200` |
| **K-C6** | `kb-manager/web/app.py:34,44` `search.py:584` | Bare `except: pass` hides DB down, pgvector extension missing → split-brain `running` forever | `log.exception`, fail-fast, surface `/health` degraded |
| **K-C7** | `kb-manager/templates/*.html` | Chunk `content` from XLSX `<script>` served as JSON that WebUI may `v-html` → stored XSS if `|safe` | `autoescape=True`, never `|safe` |

#### Tracing + Server-Setup (6)

| ID | File:Line | Error | Fix |
|----|-----------|-------|-----|
| **T-C1** | `deploy/docker/.env:6` `docker-compose.yml:69` | `POSTGRES_PASSWORD=postgres`, `NEXTAUTH_SECRET=langfuse-secret-...`, `sk-local-dev` tracked + baked into image | `git rm --cached`, only `.env.example` with `changeme-`, generate at deploy, require non-default |
| **T-C2** | `server-setup/llm_inference_manager/app.py:264` `tracing/app.py:335` `dashboard_api.py:86` | `verify_token` bypass if `authorization is None`, `POST /api/public/ingestion` writes arbitrary JSON to `/tmp/langfuse_traces.jsonl` (log injection), `POST /api/studio/run` spawns LangGraph runs with user `thread_id` | `Depends(verify_token)` on all admin/ingestion, `require_auth=true` default |
| **T-C3** | `server-setup/llm_inference_manager/app.py:204` | `allow_origins=["*"], allow_credentials=True` invalid CORS → credential theft | Explicit `CORS_ORIGINS` env or `allow_credentials=False` when `*` |
| **T-C4** | `server-setup/llm_inference_manager/app.py:618` | `subprocess.check_output(["du","-sh",str(mdir / "*")], shell=True)` `shell=True` banned, `/api/dashboard` returns `paths`/`docker ps` to unauth caller | `shell=False` + `glob`, restrict `/api/dashboard` to auth role |
| **T-C5** | `server-setup/llm_inference_manager/app.py:502` | `POST /admin/models/load?model_id=&port=&n_ctx=` spawns `llama_chat_server.py` on any port, no validation | Validate `1024<=port<=65535`, `n_ctx` in `{512,4096,8192,16384}`, require admin token, whitelist `MODEL_REGISTRY` |
| **T-C6** | `server-setup/llm_inference_manager/app.py:210` `tracing/eval_store.py:17` `tracing/app.py:387` | `manager.db` `check_same_thread=True` + no `WAL`/`busy_timeout` → `database is locked`, JSONL `open("a")` without `fcntl` → torn lines | `PRAGMA journal_mode=WAL; busy_timeout=10000; timeout=10; check_same_thread=False` + `Lock` or `aiosqlite`, `filelock` for JSONL |

---

### 2.2 HIGH (38)

| Component | ID | File:Line | Issue |
|-----------|----|-----------|-------|
| Orchestrator | O-H1 | `api.py:125-175` | `except Exception: pass` swallows `IndexError`/`TypeError` in `/rate` → invisible bugs |
| Orchestrator | O-H2 | `api.py:243` `graph.py:18` | Streaming bypasses `graph` conditional edge → KB+`rewrite_query` (60s LLM) runs even when `blocked=True` |
| Orchestrator | O-H3 | `nodes/format_response.py:170` | Gates on `faq_matched` not `faq_verified` → rejected FAQ suppresses `citations=[]` even though KB has results |
| Orchestrator | O-H4 | `clients/knowledgebase.py:47` | `_get_client()` leaks `AsyncClient` when used outside `async with` |
| Orchestrator | O-H5 | `clients/faq_verifier.py:37` | Missing `raise_for_status()` → 5xx parsed as JSON → silent `False` |
| Orchestrator | O-H6 | `api.py:122` `schemas.py:14` | Unbounded `messages[].content` (100KB) → regex CPU + LLM overflow |
| Orchestrator | O-H7 | `clients/guardrails.py:168` | `except Exception: continue` swallows stream parse errors → missing tokens |
| Orchestrator | O-H8 | `nodes/build_context.py:122` | `context_text[:budget] + "...[truncated]"` exceeds `MAX_CONTEXT_CHARS` by 14, `len(str)` not tokens → may exceed 8192 `n_ctx` |
| Orchestrator | O-H9 | `rewrite.py:21` | Hardcoded `REWRITE_URL=http://127.0.0.1:18000` ignores H200 `:9000`, no `trust_env=False` → Squid hang |
| Orchestrator | O-H10 | `clients/knowledgebase.py:146` | `health_check` `GET {kb_base_url}/` checks dashboard HTML not `/health` → false positive |
| Orchestrator | O-H11 | `clients/guardrails.py:26` | `_get_shared_client` without lock → two coroutines create two clients, one leaked |
| Orchestrator | O-H12 | `rewrite.py:137` | `AsyncClient` without `trust_env=False` → Squid hang |
| Guardrails | G-H1 | `service.py:43` | Global mutable `_rails_app` without `asyncio.Lock` → race on `/ready` |
| Guardrails | G-H2 | `service.py:106` | `except Exception: return/pass` swallows `KeyError` → hidden bugs |
| Guardrails | G-H3 | `service.py:191` | `upstream_read_timeout=120` ×2 → 180s per `check_rails`, no overall timeout |
| Guardrails | G-H4 | `service.py:372` | Bare `except: pass` on PII masking → raw PII leaks |
| Guardrails | G-H5 | `config.py:29` | `sk-local-dev` baked into image, `COPY .env.example .env` ships token |
| Guardrails | G-H6 | `service.py:477` | Streaming never runs output rails per token → secret leaks chunk-by-chunk |
| Guardrails | G-H7 | `events.py:52` | `open("a")` without `fcntl` → torn JSONL lines |
| Guardrails | G-H8 | `judge.py:84` | Sequential `for cat in cats: await _call_judge` (120s), `{{` in user text → `judge:unrendered-template` block even if benign |
| Guardrails | G-H9 | `actions.py:178` | `\b` unreliable for Persian, 1100 regex compilations per request |
| Guardrails | G-H10 | `actions.py:259` | Sheba `\bIR\d{24}\b` rejects spaced `IR 1234...`, landline loop dead |
| Knowledgebase | K-H1 | `config.py:213` `web/app.py:127` | Default `postgres:postgres`, `/health` leaks `db_url` |
| Knowledgebase | K-H2 | `search.py:458` `pipeline.py:18` | Globals `_index_cache`/`_mem_cache`/`_JOBS` without `asyncio.Lock` → `RuntimeError: dict changed size` |
| Knowledgebase | K-H3 | `search.py:482` | Fingerprint on hot path: 4 full table scans per request → DB saturation |
| Knowledgebase | K-H4 | `orchestrator.py:362` `models/database.py:106` | `Chunk.embedding Vector(384)` hardcoded even though `KB_EMBED_DIM` configurable |
| Knowledgebase | K-H5 | `search.py:588` `634` | BM25 `max-pool` vs `sum` inconsistent, pgvector `CAST(:q AS vector)` string interpolation |
| Knowledgebase | K-H6 | `ingestion_suite.py:91` `zip_browser.py:36` | `_safe_join` `startswith` bypass: `base=/tmp/a`, `p=/tmp/ab/evil` passes | Use `is_relative_to` |
| Knowledgebase | K-H7 | `config.py:195` | `KB_SQLITE_PATH=../../etc/passwd` writes anywhere |
| Knowledgebase | K-H8 | `pipeline.py:128` | Fire-and-forget `asyncio.create_task` without `await` → cancelled on reload, `running` forever |
| Knowledgebase | K-H9 | `benchmarks.py:585` | Hardcoded `D:/Code/KB/kb-source/...` breaks on Linux |
| Knowledgebase | K-H10 | `pipeline/orchestrator.py:28` `search.py:355` | `Chunk` DTO vs `DBChunk` shadowing, `SearchResult` duplicated |
| Tracing/Setup | T-H1 | `server-setup/llm_inference_manager/app.py:619` | `shell=True` with `du -sh`, `pip install` without hashes → MITM |
| Tracing/Setup | T-H2 | `tracing/app.py:382` `eval_store.py:805` | `await request.json()` no size limit → multi-GB OOM, `read_text().splitlines()` reads entire JSONL (GB) |
| Tracing/Setup | T-H3 | `tracing/app.py:173` | `STUDIO_API` SSRF → cloud metadata `169.254.169.254` |
| Tracing/Setup | T-H4 | `tracing/app.py:13` `eval_store.py:24` | Bare `except: pass` hides failures |
| Tracing/Setup | T-H5 | `contracts/rail_check_request.json:21` | `request_id` contract `format:uuid` but code accepts `../../etc/passwd`, `eval_store.py:405` generates non-UUID 12-hex |
| Tracing/Setup | T-H6 | `tracing/templates/observability.html:204` | `esc()` misses `'`, `innerHTML` XSS via `user_query`/`comment` |
| Tracing/Setup | T-H7 | `server-setup/offline_prepare_cli.py:18` | Hardcoded `192.168.203.2:3128`, `192.168.96.82:18000` leaks topology |
| Tracing/Setup | T-H8 | `tracing/dashboard_api.py:86` | `save_trace` `extra="allow"` → attacker injects keys → DB bloat |
| Tracing/Setup | T-H9 | `tracing/eval_store.py:126` | Unreachable branch `if field in ("guardrail_input",...)` inside `if field=="stage_timing"` → defaults never applied |
| Tracing/Setup | T-H10 | `server-setup/offline_prepare_cli.py:27` | `os.environ["PIP_CACHE_DIR"]=...` at import time pollutes env globally |

---

### 2.3 MEDIUM (52) + LOW (31) — Backlog

**Medium themes (52):** Hardcoded magic numbers (`_KEYWORD_BOOST=3.0`, `RRF k=60`, `batch_size=64`), N+1 queries (`monitoring.py` 5× `COUNT(*)`), blocking `load_workbook` in async handlers, `422`→`200` for `{"error":"Empty query"}`, orphaned `query_expansion`/`hyde` dead code, config triple alias `KB_SQLITE_PATH` vs `KB_DB_URL`, `page`/`per_page` no `ge=1/le=100` validation, logging PII `hyde.py:99`, `_utcnow` vs `datetime.now(UTC)` skew, `KB_EMBED_DEVICE` not validated.

**Low (31):** Unused imports, shadowing (`doc_metadata`/`metadata`), missing type hints (`Any` overuse), duplicated `_run_benchmark` vs `_run_massive`, hardcoded `dense_dim:384`, no `__all__`/`mypy strict`, duplicate `REGZ` compilation, hardcoded Persian prompts (should externalize).

Full detail in `/tmp/CODE_AUDIT_REPORT.md` (162 lines, 142 issues with `file:line` and `Fix:`).

---

## 3. Fix Priority & Verification

| Order | IDs | Action | Effort | Verify |
|-------|-----|--------|--------|--------|
| **1** | C1-21 (all Critical) | Auth on all `web/routes/*`, sanitize `file.filename`, restrict `from-path`, quota+reaper, escape `ilike`, `WAL`+`filelock`, rotate secrets, `CORS` explicit, `shell=False`, validate `port`/`n_ctx`, `RailsConfig` arity, Persian PII normalize, fail-closed domain gate | 2 days | `bash deploy/vast/health.sh` (5 `ok`), `curl` E2E `{"finish":"stop","citations":5}`, PII Persian `۰۹۱۲۳۴۵۶۷۸۹` test, policy-missing fail-closed test |
| **2** | H1-H38 | Fix `HTTPException` handler, streaming race, `MemorySaver` TTL, thread-pool for tracing, `faq_verified` TypedDict, `SentenceTransformer` `to_thread`, shared client timeout, sequential judge → `asyncio.gather`, output rails on stream, `fcntl` for events, uncompiled regex → `re.compile`, Sheba spaced bypass | 3 days | Same + `pytest -q` guardrails `tests/`, kb-manager 17 tests, `ruff check` + `mypy --strict` + `bandit -r kb_manager` |
| **3** | M1-M52 | Centralize magic numbers in `config.py`, batch queries with `asyncio.gather`, `to_thread` for parsers, `422` for validation, wire `HyDE` multi or remove, lazy `db` singleton, `Query(ge/le)` validation | 2 days | Same |
| **4** | L1-L31 | `ruff --select ALL` + `mypy --strict` CI, `__all__`, remove `opentelemetry` bloat, `Dockerfile` `COPY .env.example` remove, `eval` `statistics.quantiles` fix | 1 day | CI green |

---

## 4. History Notes

- **2026-09-27 07:47** — Initial performance audit `chore/cleanup-consolidated` latencies measured `main` @ `a5796bd`: `RAG cold ~13s` (rerank 6.5s 44%, Gemma 2.1s 14%), `FAQ 180ms` cached. Fixed Redis `KB_REDIS_TTL=600` + shared `httpx` pool + parallel `validate+retrieve`.
- **2026-09-27 08:24** — Full 4-agent code audit (explore very thorough ×3) on `main` @ `7bf1be3` found 142 issues (21 Critical). Prior fix `chore/code-quality` @ `438fe9d` compiled `_clean_gemma` regex, `record_timing` helper, async observability.
- **2026-09-27 09:24** — This history file created from `/tmp/CODE_AUDIT_REPORT.md`. Next step: `.opencode/plans/audit-fix-2026-09-27.md` (agent execution plan) and `AGENTS_FIX_PLAN.md` (per-component task breakdown).

All references `file:line` exact at 2026-09-27 `main` @ `7bf1be3` (parent) + `706ade0` (KB) + `f206d83` (guardrails) + `8602e1c` (orchestrator). Re-run `ruff check` + `mypy --strict` after each fix order.
