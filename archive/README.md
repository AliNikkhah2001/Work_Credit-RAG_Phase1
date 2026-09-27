# Archive — Non-code artifacts

This directory holds artifacts moved off `main` during `chore/cleanup-consolidated`.

| Path | What's here | Why archived |
|------|-------------|--------------|
| `handoff-sessions/` | 36 `ses_f6*.md` transcripts + `SESSION_WAVE1_HANDOFF.md` | Agent chat logs, not docs. Deterministic re-run via `deploy/vast/start.sh`. |
| `audit-2026-09-12/` | `documentation_audit.md` + `artifacts/documentation/*` | One-off 2026-09-12 audit; superseded. `tracing/README.md` now exists. |
| `migration-history/` | `VAST_GEMMA4_MIGRATION.md`, `WAVE2_GPU_RUNBOOK.md` | Historical migration; current runbook is `AGENTS.md §2` + `deploy/vast/*.sh`. |
| `benchmark-history/docs-benchmark-2026-09/` | `llm_answer_benchmark_{v2,v3,v4}.json`, `llm_judge_{v2,v3,v4}.json`, `plots/*` | Exact `md5` duplicates of `eval/results/` (canonical). Added to `.gitignore`; regenerate via `eval/build_report_site.py`. |

**In `components/knowledgebase/archive/`:**

| Path | Content |
|------|---------|
| `windows-launchers/` | 17 `*.bat`/`*.ps1` + 2 `opencode.json` (Windows `cmd.exe`). Linux host uses `deploy/vast/start.sh`. |
| `debug-scripts/` | 20 `debug_*/diag_*/_check_*.py` one-offs from retrieval tuning. |
| `debug-html/` | 5 HTML page dumps (`comparison_debug.html` etc.). Real templates are `kb_manager/web/templates/*.html`. |
| `before-snapshots/` | 3 `*_BEFORE.json` identical to current (`md5` verified). |
| `duplicate-data/` | Removed 14MB `persian-rag-*.json` duplicate (canonical is `kb-manager/persian-rag-*.json`). |

**Retention:** Keep for 1 release cycle, then delete branches. `eval/results/` remains canonical for benchmarks.
