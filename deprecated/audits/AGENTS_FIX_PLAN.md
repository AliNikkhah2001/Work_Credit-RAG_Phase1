# AGENTS — Fix Plan for 142 Audit Errors (2026-09-27)

> **Scope:** All 142 errors & anti-patterns from `docs/history/CODE_AUDIT_2026-09-27.md` (21 Critical, 38 High, 52 Medium, 31 Low).  
> **Source:** `/tmp/CODE_AUDIT_REPORT.md` (full) + `docs/history/CODE_AUDIT_2026-09-27.md` (history) + `.opencode/plans/audit-fix-2026-09-27.md` (execution plan).  
> **Branch audited:** `main` @ `7bf1be3` (parent) + `706ade0` (KB) + `f206d83` (guardrails) + `8602e1c` (orchestrator).

This file is the **agent operating manual** for fixing the audit. Use with `AGENTS.md` (repo map, ports, workflows) and `README.md` (architecture). For how to run tasks, see `.opencode/plans/audit-fix-2026-09-27.md` Order 1-4.

---

## 1. Task Map — Who Fixes What

| Priority | Component | Repo / Branch | Owner Agent | IDs | Est. |
|----------|-----------|---------------|-------------|-----|------|
| **Order 1 — Critical (21)** | `components/knowledgebase` | `Work_RAG-KB` `master` | `backend-specialist` | K-C1..C7 (path traversal, auth, from-path, disk, ilike, except:pass, XSS) | 1 day |
| | `components/tracing` (parent) + `components/server-setup` | Parent + `Work_RAG-Server-Setup` `main` | `security-auditor` | T-C1..C6 (secrets, open ingestion, CORS `*`, shell=True, admin/load, WAL) | 0.5 day |
| | `components/orchestrator` | `Work_RAG-Orchestrator` `main` | `general` | O-C1..C8 (HTTPException swallow, streaming race, MemorySaver, thread explosion) | 0.5 day |
| | `components/guardrails` | `Work_RAG-Guardrails` `main` | `security-auditor` | G-C1..C6 (RailsConfig arity, alias bypass, Persian PII, YAML injection, fail-open) | 0.5 day |
| **Order 2 — High (38)** | All 4 | Same | `general` + `backend-specialist` + `review` | O-H1..H12, G-H1..H10, K-H1..H10, T-H1..H10 | 3 days |
| **Order 3 — Medium (52)** | All 4 | Same | `general` | Magic numbers, N+1, blocking I/O, 422, HyDE dead code, Query(ge/le) | 2 days |
| **Order 4 — Low (31)** | All 4 | Same | `general` | `ruff`/`mypy`, `__all__`, `opentelemetry` bloat | 1 day |

**Total:** 8 days if sequential, 4 days if Order 1 parallelized across 4 agents.

---

## 2. Critical Tasks — Detailed Steps (Order 1)

### 2.1 Knowledgebase — `Work_RAG-KB` `master` — `chore/fix-critical-kb`

**Branch:** `git switch -c chore/fix-critical-kb` in `components/knowledgebase`

| ID | File:Line | Action | Verify |
|----|-----------|--------|--------|
| K-C1 | `kb-manager/web/routes/documents.py:104` | Sanitize `file.filename`: `safe = Path(file.filename).name; sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', safe); if not safe or safe in (".",".."): raise HTTPException(400); p = (upload_dir / sanitized).resolve(); assert p.is_relative_to(upload_dir.resolve())` | `curl -F "file=@/tmp/x; filename=../../etc/cron.d/pwn"` → `400` |
| K-C2 | `kb-manager/web/routes/*` (15 routers) | `APIRouter(dependencies=[Depends(require_auth)])` where `require_auth` checks `Header("X-Admin-Token")==os.getenv("KB_ADMIN_TOKEN")` | `curl http://:8000/documents` without token → `401` |
| K-C3 | `kb-manager/web/routes/ingestion_suite.py:352` | Allowlist `KB_ALLOWED_SOURCE_ROOTS=/data`; reject `..`, absolute outside root, symlinks (`p.resolve().is_relative_to(root)`), cap files<1000 bytes<2GB | `POST {"path":"/etc/passwd"}` → `403` |
| K-C4 | `kb-manager/web/routes/ingestion_suite.py:280` | `ZipInfo.file_size` + `compressed_size` ratio `>100 => reject`, `STAGE_ROOT` reaper `age>24h`, `MAX_ZIP_BYTES` also on `from-path` | Bomb `10KB→10GB` → `413` |
| K-C5 | `kb-manager/web/routes/transparency.py:212` | `escaped = q.replace("\\","\\\\").replace("%","\\%").replace("_","\\_"); query.where(Document.title.ilike(f"%{escaped}%", escape="\\"))` + `len(q)<=200` | `curl "?q=%"` → not full table |
| K-C6 | `kb-manager/web/app.py:34,44` | `except Exception as e: log.exception(...); health degraded` not `pass` | Kill DB → `GET /health` shows `degraded` |
| K-C7 | `kb-manager/web/templates/*.html` | `grep -r "|safe"` → remove, ensure `autoescape=True` | Inject `<script>alert(1)</script>` in XLSX → `&lt;script&gt;` |

**Test:** `pytest kb_manager/tests/` (17) + manual `curl` traversal tests.

### 2.2 Tracing + Server-Setup

**Branch:** `chore/fix-critical-tracing` (parent) + `chore/fix-critical-server-setup` (submodule)

| ID | File:Line | Action |
|----|-----------|--------|
| T-C1 | `deploy/docker/.env:6` | `git rm --cached`, only `.env.example` with `changeme-`, `openssl rand -hex 32` at deploy, require non-default via entrypoint |
| T-C2 | `server-setup/llm_inference_manager/app.py:264` `tracing/app.py:335` | `Depends(verify_token)` on `POST /api/public/ingestion`, `/api/dashboard`, `dashboard_api.py` 12 endpoints |
| T-C3 | `server-setup/llm_inference_manager/app.py:204` | `allow_origins=env("CORS_ORIGINS","").split(",") or ["http://localhost:13000"]` |
| T-C4 | `server-setup/llm_inference_manager/app.py:618` | `glob.glob` + `subprocess.run([...], shell=False)` |
| T-C5 | `server-setup/llm_inference_manager/app.py:502` | `if not 1024 <= port <= 65535: 400; if n_ctx not in {512,4096,8192,16384}: 400; whitelist MODEL_REGISTRY` |
| T-C6 | `server-setup/llm_inference_manager/app.py:210` | `PRAGMA journal_mode=WAL; busy_timeout=10000; timeout=10; check_same_thread=False` + `Lock` or `aiosqlite`; `filelock` for JSONL |

### 2.3 Orchestrator

**Branch:** `chore/fix-critical-orchestrator` in `components/orchestrator`

| ID | File:Line | Action |
|----|-----------|--------|
| O-C1 | `api.py:526` | `if isinstance(exc, HTTPException): return JSONResponse(exc.status_code, {"detail":exc.detail})` |
| O-C2 | `api.py:247` | `v_state = dict(initial_state); v_task = create_task(node_validate(v_state)); r_task = create_task(node_retrieve(dict(initial_state))); state = await v_task; if state.get("blocked"): r_task.cancel(); try: await r_task except CancelledError: pass` |
| O-C3 | `graph.py:65` | `MemorySaver` → TTL or stateless |
| O-C4 | `clients/guardrails.py:26` | Key pool by timeout or per-request `timeout=` |
| O-C5 | `tracing.py:66` | `ThreadPoolExecutor` + `trust_env=False` |
| O-C6 | `state.py:9` | Add `faq_verified: bool` to `RAGState` |
| O-C7 | `faq_direct.py:99` | `await asyncio.to_thread(SentenceTransformer, ...)` at `lifespan` |
| O-C8 | `faq_direct.py:108` | Env `FAQ_EMBED_MODEL_PATH` |

### 2.4 Guardrails

**Branch:** `chore/fix-critical-guardrails` in `components/guardrails`

| ID | File:Line | Action |
|----|-----------|--------|
| G-C1 | `service.py:74` | `yaml.safe_dump({"models": ...})` |
| G-C2 | `service.py:211` | `settings.resolved_api_key` |
| G-C3 | `actions.py:275` | `text = normalize_persian(text)` before regex |
| G-C4 | `judge.py:117` | Dict + `safe_dump` |
| G-C5 | `signals.py:65` | Fail-closed when policy empty |
| G-C6 | `judge.py:173` | Treat `""` as `block` |

**Verification for Order 1:** `bash deploy/vast/health.sh` (5 `ok`), `curl` E2E `{"finish":"stop","citations":5}`, PII Persian `۰۹۱۲۳۴۵۶۷۸۹` → blocked, policy-missing → fail-closed `blocked=True`.

---

## 3. How to Work

1. **Read order:** `docs/history/CODE_AUDIT_2026-09-27.md` (all 142 with `Fix:`) → `.opencode/plans/audit-fix-2026-09-27.md` (4 orders, branch strategy) → this file (who does what).
2. **Branch:** `git switch -c chore/fix-critical-<component>` on that repo's `main`/`master`, `git push -u origin chore/fix-critical-<component>`.
3. **Fix:** One commit per ID group, `Fix: <ID> <file:line> <1-line description>`.
4. **Test:** `health.sh` (5 `ok`) + `curl` E2E + `pytest -q` + `ruff check` + `mypy --strict` + `bandit` must be green before PR.
5. **PR:** `gh pr create --base main --head chore/fix-critical-<component>` — merge only after `health.sh` + `pytest` green (like `chore/cleanup-consolidated` precedent). No force-push.

**Agents:** Use `Task` tool with `subagent_type` as in §1 table. For `security-auditor` tasks, run `bandit -r kb_manager` after fix. For `backend-specialist`, run `pytest kb_manager/tests/`.

All `file:line` exact at 2026-09-27 `main` @ `7bf1be3`. See `docs/history/CODE_AUDIT_2026-09-27.md` for full list with `Fix:` snippets.
