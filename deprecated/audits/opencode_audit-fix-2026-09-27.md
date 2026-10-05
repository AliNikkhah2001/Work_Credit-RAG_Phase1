# Plan: Fix 142 Code Audit Errors (2026-09-27)

**Source:** `docs/history/CODE_AUDIT_2026-09-27.md` + `/tmp/CODE_AUDIT_REPORT.md` (142 issues: 21 Critical, 38 High, 52 Medium, 31 Low)  
**Branch audited:** `main` @ `7bf1be3`  
**Goal:** Fix all Critical (21) before prod, High (38) next sprint, Medium/Low as backlog. Keep services green throughout.  
**Strategy:** 4 orders, each 1 PR (parent + submodules), `chore/*` branches, merge only after `health.sh` + `pytest` + `ruff`/`mypy` green.

---

## Order 1 — Critical (21) — 2 days — MUST FIX BEFORE PROD

### 1.1 Knowledgebase — 7 Critical (owner: Work_RAG-KB `master`)

| ID | File:Line | Task | Fix snippet | Verify |
|----|-----------|------|-------------|--------|
| K-C1 | `kb-manager/web/routes/documents.py:104` | Sanitize `file.filename` path traversal | `safe = Path(file.filename).name; sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', safe); if not safe or safe in (".",".."): raise HTTPException(400); p = (upload_dir / sanitized).resolve(); assert p.is_relative_to(upload_dir.resolve())` | `curl -F "file=@/tmp/pwn; filename=../../etc/cron.d/pwn"` → `400` |
| K-C2 | `kb-manager/web/routes/*` | Add auth to all `web/routes/*` (15 routers) | `APIRouter(dependencies=[Depends(require_auth)])` where `require_auth` checks `Header("X-Admin-Token")==os.getenv("KB_ADMIN_TOKEN")` | `curl http://:8000/documents` without token → `401` |
| K-C3 | `kb-manager/web/routes/ingestion_suite.py:352` | Restrict `from-path`/`export-path` arbitrary read | `root = Path(os.getenv("KB_ALLOWED_SOURCE_ROOTS","/data")).resolve(); assert (root / rel).resolve().is_relative_to(root); cap files<1000, bytes<2GB` | `POST {"path":"/etc/passwd"}` → `403` |
| K-C4 | `kb-manager/web/routes/ingestion_suite.py:280` | Quota + reaper for unbounded disk / zip bomb | `ZipInfo.file_size` + `compressed_size` ratio `>100 => reject`, `STAGE_ROOT` reaper `age>24h`, `MAX_ZIP_BYTES=500MB` also on `from-path`, `max_upload_size` middleware 100MB | `unzip -l bomb.zip` with 10KB→10GB → `413` |
| K-C5 | `kb-manager/web/routes/transparency.py:212` | Escape `ilike` wildcard `q=%` → full table DoS | `escaped = q.replace("\\","\\\\").replace("%","\\%").replace("_","\\_"); query.where(Document.title.ilike(f"%{escaped}%", escape="\\"))` | `curl "?q=%"` → not full table |
| K-C6 | `kb-manager/web/app.py:34,44` | Replace `except: pass` on ingestion/DB failures | `except Exception as e: log.exception("mark stale failed: %s", e); health degraded` | Kill DB → `GET /health` shows `degraded` not `running` forever |
| K-C7 | `kb-manager/templates/*.html` | Audit `|safe` on chunk content → stored XSS | `grep -r "|safe" kb_manager/web/templates/` → remove, ensure `autoescape=True` | Inject `<script>alert(1)</script>` in XLSX → rendered as `&lt;script&gt;` |

**Steps:**
1. `git switch -c chore/fix-critical-kb` in `components/knowledgebase`
2. Fix K-C1, K-C5, K-C6 (1 commit), K-C2, K-C3, K-C4, K-C7 (1 commit)
3. `pytest kb_manager/tests/` (17 tests) + manual `curl` traversal tests
4. Push `chore/fix-critical-kb`, PR to `master`, merge after review

### 1.2 Tracing + Server-Setup — 6 Critical

| ID | File:Line | Task | Fix |
|----|-----------|------|-----|
| T-C1 | `deploy/docker/.env:6` `docker-compose.yml:69` | Rotate secrets, `git rm --cached` tracked `.env` | `echo ".env" >> .gitignore; git rm --cached deploy/docker/.env; cp .env .env.example` with `changeme-` placeholders; `openssl rand -hex 32` at deploy |
| T-C2 | `server-setup/llm_inference_manager/app.py:264` `tracing/app.py:335` | Auth on `POST /api/public/ingestion`, `/api/dashboard`, `dashboard_api.py` 12 endpoints | `Depends(verify_token)` with `require_auth=true` default, keep only `/api/public/health` open |
| T-C3 | `server-setup/llm_inference_manager/app.py:204` | CORS `allow_origins=["*"], allow_credentials=True` → invalid, credential theft | `allow_origins=env("CORS_ORIGINS","").split(",") or ["http://localhost:13000"]` or `allow_credentials=False` when `*` |
| T-C4 | `server-setup/llm_inference_manager/app.py:618` | `shell=True` `du -sh` + `/api/dashboard` disclosure to unauth | `glob.glob` + `subprocess.run([...], shell=False)`; restrict `/api/dashboard` to auth |
| T-C5 | `server-setup/llm_inference_manager/app.py:502` | `admin/load` command injection via `port`/`n_ctx` | `if not 1024 <= port <= 65535: 400; if n_ctx not in {512,4096,8192,16384}: 400; whitelist MODEL_REGISTRY; require admin token` |
| T-C6 | `server-setup/llm_inference_manager/app.py:210` `tracing/eval_store.py:17` | `manager.db` `check_same_thread=True` + no `WAL`, JSONL without `fcntl` → `database is locked`, torn lines | `PRAGMA journal_mode=WAL; busy_timeout=10000; timeout=10; check_same_thread=False` + `threading.Lock` or `aiosqlite`; `filelock` for JSONL |

**Steps:** Similar: `chore/fix-critical-tracing` branches in `components/tracing` (parent) + `components/server-setup`.

### 1.3 Orchestrator — 8 Critical

| ID | File:Line | Task | Fix |
|----|-----------|------|-----|
| O-C1 | `orchestrator/api.py:526` | `HTTPException` swallowed | Register `HTTPException` handler separately |
| O-C2 | `orchestrator/api.py:247` | Streaming race on shared `initial_state` | Clone `dict(initial_state)` or `r_task.cancel()` when `blocked` |
| O-C3 | `orchestrator/graph.py:65` | `MemorySaver` unbounded | TTL checkpointer or stateless `ainvoke` |
| O-C4 | `orchestrator/clients/guardrails.py:26` | Shared client ignores `timeout` | Key pool by timeout or per-request `timeout=` |
| O-C5 | `orchestrator/tracing.py:66` | Thread explosion + `trust_env` default | `ThreadPoolExecutor` + `trust_env=False` |
| O-C6 | `orchestrator/state.py:9` | `faq_verified` missing `TypedDict` | Add `faq_verified: bool` |
| O-C7 | `orchestrator/faq_direct.py:99` | `SentenceTransformer` blocks event loop | `asyncio.to_thread()` at `lifespan` |
| O-C8 | `orchestrator/faq_direct.py:108` | Hardcoded `/splunk-data/...` path | Env `FAQ_EMBED_MODEL_PATH` |

**Steps:** `chore/fix-critical-orchestrator` branch.

### 1.4 Guardrails — 6 Critical

| ID | File:Line | Task | Fix |
|----|-----------|------|-----|
| G-C1 | `guardrails/service.py:74` | `RailsConfig.from_content` list not YAML | `yaml.safe_dump` |
| G-C2 | `guardrails/service.py:211` | Alias bypass `LLM_API_KEY` | `resolved_api_key` |
| G-C3 | `guardrails/actions.py:275` | Persian PII `۰۹۱۲` bypass | `normalize_persian` before regex |
| G-C4 | `guardrails/judge.py:117` | YAML injection | Dict + `safe_dump` |
| G-C5 | `guardrails/signals.py:65` | Domain gate fail-open | Fail-closed when policy empty |
| G-C6 | `guardrails/judge.py:173` | NeMo `""` treated as `allow` | Treat `""` as `block` |

**Steps:** `chore/fix-critical-guardrails` branch.

**Verification for Order 1:** `bash deploy/vast/health.sh` (5 `ok`), `curl` E2E `{"finish":"stop","citations":5}`, PII Persian `۰۹۱۲۳۴۵۶۷۸۹` → blocked, policy-missing → fail-closed `blocked=True`.

---

## Order 2 — High (38) — 3 days

**Orchestrator 12 (O-H1..H12):** Fix `except Exception: pass` → `log.warning`, streaming conditional edge cancel, `faq_verified` gate, `_get_client` leak, `raise_for_status`, `max_length` validator, stream parse `log.debug`, `MAX_CONTEXT_CHARS` suffix, `REWRITE_URL` env, `health_check` `/health`, shared client lock, `trust_env=False` for rewrite.

**Guardrails 10 (G-H1..H10):** Lock for globals, `log.debug` for detectors, `upstream_read_timeout` overall timeout, `except: pass` PII → log+fallback, `sk-local-dev` require env, output rails per token, `fcntl` for events, sequential judge → `asyncio.gather`, `\b` → `re.compile` with Persian boundary, Sheba spaced bypass.

**Knowledgebase 10 (K-H1..H10):** No default `postgres:postgres`, `db_url` not leaked, `asyncio.Lock` for caches, fingerprint via `max(updated_at)` not 4 scans, `Vector(dim)` from config, `is_relative_to`, `KB_SQLITE_PATH` validation, `BackgroundTasks` not `create_task`, remove `D:/Code/...`, rename `Chunk` DTO.

**Tracing/Setup 10 (T-H1..H10):** `shell=False`, OOM bounds (read JSONL streaming, `limit` param), SSRF allowlist for `STUDIO_API`, `log.exception` not `pass`, `Pydantic UUID4` for `request_id`, `esc()` with `'`, hardcoded IPs → env, `extra="forbid"`, unreachable `guardrail_input` branch.

**Steps:** One `chore/fix-high-*` branch per component, `pytest -q` + `ruff check` + `mypy --strict` + `bandit`.

---

## Order 3 — Medium (52) — 2 days

- Centralize magic numbers in `config.py` (`_KEYWORD_BOOST`, `k=60`, `batch_size`), batch `COUNT(*)` with `asyncio.gather`, `to_thread` for `load_workbook`, `422` for `{"error":"Empty query"}`, wire `HyDE` multi or remove, lazy `db` singleton, `Query(ge/le)` validation, `KB_EMBED_DEVICE` validation.

## Order 4 — Low (31) — 1 day

- `ruff --select ALL` + `mypy --strict` CI, `__all__`, remove `opentelemetry` bloat, `COPY .env.example` remove, `eval` `statistics.quantiles` fix.

---

## Execution Plan

```
main @ 7bf1be3
  ├── chore/fix-critical-kb (K-C1..C7) ─┐
  ├── chore/fix-critical-tracing (T-C1..C6) ─┤
  ├── chore/fix-critical-orchestrator (O-C1..C8) ─┤─► PR1 (Critical, 2 days) → main
  └── chore/fix-critical-guardrails (G-C1..C6) ─┘

main @ PR1
  ├── chore/fix-high-* (4 branches, 38 issues) ─► PR2 (High, 3 days) → main

main @ PR2
  ├── chore/fix-medium-* (52) ─► PR3 (2 days) → main
  └── chore/fix-low-* (31) ─► PR4 (1 day) → main (or squash into PR3)
```

Each PR: `health.sh` (5 `ok`) + `curl` E2E + `pytest` (guardrails `tests/`, kb-manager 17, orchestrator) + `ruff check` + `mypy --strict` + `bandit -r kb_manager` green before merge. No force-push, `chore/*` branches, merge via PR after approval (like `chore/cleanup-consolidated` precedent).

---

## Agents

- **Backend-specialist:** Knowledgebase path traversal, auth, `ilike` escape, `WAL`/`filelock`, `Vector(384)` fix.
- **Security-auditor:** Tracing/Setup secrets, CORS, `shell=True`, `admin/load` injection, guardrails PII bypass, `POST /api/public/ingestion` auth.
- **General:** Orchestrator streaming race, `HTTPException` handler, `MemorySaver`, `faq_verified` TypedDict, `SentenceTransformer` `to_thread`.
- **Review:** Final `ruff`/`mypy`/`bandit` gates.

All `file:line` exact at 2026-09-27 `main` @ `7bf1be3`. See `docs/history/CODE_AUDIT_2026-09-27.md` for full list with `Fix:` snippets.
