# Documentation Changes Summary

Generated: 2026-09-12 | Agents 1-8 Documentation Upgrade

---

## Files Created

| File | Agent | Description |
|------|-------|-------------|
| `artifacts/documentation/repository_documentation_map.json` | 1 | Machine-readable inventory of all READMEs and docs |
| `docs/documentation_audit.md` | 1 | Per-README audit: purpose, audience, coverage, gaps, inconsistencies |
| `artifacts/documentation/fact_check_report.json` | 2 | Verified/incorrect/missing claims across all docs |
| `docs/architecture.md` | 3 | System architecture with Mermaid diagrams (system, request flow, graph, retrieval, guardrails, data flow, startup, ports, env) |
| `docs/models.md` | 6 | Model cards for generation, embedding, reranker, guardrails, server-setup models |
| `docs/evaluation.md` | 6 | KB retrieval benchmarks, RAG E2E, LLM-as-judge, metrics, reproduction |
| `docs/training.md` | 6 | KB ingestion pipeline, reranker shootout, query reform, quality gates |
| `docs/README.md` | 4 | Documentation index linking all guides and references |

## Files Updated

| File | Changes |
|------|---------|
| `README.md` (root) | Complete restructure: badges, TOC, architecture diagrams, request flow, model table, config table, observability section, evaluation summary, done/pending checklists, verification commands |
| `components/orchestrator/README.md` | Status → IMPLEMENTED, added graph diagram, API examples, state schema, tracing spans, Studio debugger, project structure |
| `components/guardrails/README.md` | Status → IMPLEMENTED, added pipeline stages tables, HurtLex allowlist (19 lemmas), risk scoring, semantic interface, project structure |
| `components/tracing/README.md` | **NEW** — Collector, Observe UI, Studio UI, API endpoints, CLI, data sources |
| `deploy/docker/.env.example` | **NEW** — All env vars for Docker stack with comments |
| `docs/README.md` | **NEW** — Documentation index |

## Key Fixes Applied

### Corrected Inconsistencies

| Issue | Before | After |
|-------|--------|-------|
| Orchestrator status | "not implemented" | ✅ IMPLEMENTED (live on Vast) |
| Guardrails status | "not implemented" | ✅ IMPLEMENTED (live on :8200) |
| Guardrails upstream URL | 9000 (default only) | Documented `LLM_BASE_URL` alias → 18000 in production |
| KB port in quickstart | 8004 (dev SQLite) | Documented 8000 (prod pgvector) + 8004 dev note |
| HurtLex allowlist count | 11 / 15 (conflicting) | **19 lemmas** (single source: `hurtlex_allowlist.json`) |
| MAX_CHUNKS / MAX_CHARS | 3 / 4000 (root README) | **5 / 6000** (actual code in build_context.py) |
| REQUEST_TIMEOUT_SECONDS | Documented in orchestrator README | Removed (not in code) |

### Added Missing Documentation

- **Architecture diagrams** (6 Mermaid diagrams in architecture.md)
- **Model cards** for all 4 model roles (generation, embedding, reranker, guardrails)
- **Evaluation methodology** with reproduction commands
- **Training/pipeline docs** for KB ingestion and reranker shootout
- **Observability section** with 3 UIs (Langfuse, Observe, Studio)
- **Local Studio debugger** at `/studio` (no Smith panel needed)
- **Configuration reference table** (28 env vars across 5 components)
- **Troubleshooting index** in root README (links to component troubleshooting)

## Cross-Component Alignment

| Aspect | Root README | AGENTS.md | Component READMEs | Code |
|--------|-------------|-----------|-------------------|------|
| Ports | ✅ 8 services | ✅ Service table | ✅ Per-component | ✅ start.sh |
| Env vars | ✅ 28 vars table | ✅ Key env per service | ✅ Per-component | ✅ Config classes |
| Model IDs | ✅ Model table | ✅ Gemma only | ✅ Per-component | ✅ Actual usage |
| HurtLex | ✅ 19 lemmas | — | ✅ Guardrails + eval | ✅ JSON file |
| Startup order | ✅ Diagram + text | ✅ start.sh | — | ✅ start.sh |

## Verification Commands Added

```bash
# Gemma clean output
for p in "سلام" "Hello" "اعتبارسنجی چیست" ...; do
  curl ... | python3 -c "print('has_unused:', '<unused' in c)"
done

# Guardrails tests
PYTHONPATH=components/guardrails/src /tmp/guard-venv/bin/python -m pytest tests/test_hurtlex_allowlist.py -v

# RAG E2E
curl ... | jq '{finish, citations, content}'

# Observe CLI
python components/tracing/observe.py --list --limit 5
python components/tracing/observe.py --request <id> --json
```

## Remaining Documentation Debt (Post-MVP)

- [ ] CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md
- [ ] CHANGELOG.md per component (KB has version table, others need)
- [ ] OpenAPI/Swagger specs for each service
- [ ] Mark v1-v4 KB READMEs as archival
- [ ] Consolidate server-setup history logs
- [ ] Add "Known Issues" section to each component README