---
name: work-credit-rag
description: >-
  Onboards and guides work on the Work Credit RAG Phase 1 platform (Persian RAG,
  LangGraph orchestrator, KB hybrid retrieval, guardrails, Vast/H200 server-setup).
  Use when resuming this project, picking a component, reading agent history,
  deploying, evaluating, or continuing OpenCode/agent-state todos.
---

# Work Credit RAG — project skill

## First actions every session

1. Read `agent-state/context/context.md` + `agent-state/context/todo.md`
2. Skim `agent-state/insights.md` (and this skill’s **Known gaps**)
3. Match task → owning submodule → edit only there
4. Prefer `feature/*` → PR → `develop` → `main`/`master`

## Platform map

```
WebUI :13000
  → Orchestrator :8100  (LangGraph, MemorySaver)
      → Guardrails :8200  POST /v1/rails/check  (input)
      → KB :8000          POST /search/api      (+ optional /search/supplement)
      → build_context     (≤20 chunks, prompt_char_budget≈20k, entity trim)
      → Guardrails :8200  POST /v1/chat/completions → Gemma :18000 or Manager :9000
      → format_response   citations
```

| Path | Repo | Owns |
|---|---|---|
| `components/knowledgebase` | Work_RAG-KB `master` | ingest, BM25+dense+RRF+rerank, EntityList |
| `components/orchestrator` | Work_RAG-Orchestrator `main` | graph, sticky subspace, clarify, chat API |
| `components/guardrails` | Work_RAG-Guardrails `main` | signals + LLM/Mizan judge, guarded generate |
| `components/server-setup` | Work_RAG-Server-Setup `main` | H200 manager `:9000`, embeds, runbook |
| `components/tracing` | parent | fallback collector `:3000` |
| `agent-state/` | ICS_ChatBot_agent-state | mission, todos, OpenCode history |

Parent `api/*.py` are thin wrappers only. Production impl is always in `components/`.

## Orchestrator graph (validated against `graph.py`)

`validate_input` → `classify` → (`greeting`/`specification` → format) |
(`question` → optional `hybrid_classify` → `retrieve`) →
`should_clarify` (entity evidence short-circuits) →
`generate_clarification` **or** `build_context` → `guarded_generate` → `format_response`.

Key files: `graph.py`, `state.py`, `config.py`, `nodes/retrieve.py` (~2.2k LOC), `nodes/build_context.py`, `clients/knowledgebase.py`.

## KB retrieval (validated against `search.py` / `dense.py`)

1. Persian normalize + synonym beam  
2. BM25 (tantivy/in-proc) + dense MiniLM-384 (`DenseSemanticIndex._ensure_model` / `_encode`)  
3. RRF k=60 → BGE-m3 rerank → `final_results` + `merged_candidates`  
4. Step-8 EntityList inject into `injected_entities` (cosine on `description_embedding`)  
5. Optional tool: orchestrator `supplementary_search` → `POST /search/supplement`

## Guardrails (validated against `service.py` / `judge.py`)

NeMo **removed**. Path = deterministic `signals` → policy/LLM or Mizan/hybrid judge → fail-closed. `trust_env=False` on all localhost httpx. Clean Gemma junk tokens (`<unused*>`, tool tags).

## Agent / OpenCode history (other computer)

| Source | Status |
|---|---|
| `agent-state/history/archive/*` | Canonical session archives |
| `components/server-setup/.opencode/` | H200 README/manager/OpenCode mission — **completed** Aug 2026 |
| DeepSeek-V4 archive | **Paused** — not current RAG work |
| `audit-fix-2026-09-27.md` | Security backlog index (21 critical) |

## Known gaps on current `master` tips (actionable)

Updated 2026-11-11 against live entity/supplement work:

1. **EntityList ضمیمه path is implemented** (`entity_lists.py`, `/search/supplement`, subspace score force-inject, orch trim-by-relevance + format_response Entity Data recovery). Catalog E2E 9/9 on local stack for `1405-08-20`.
2. **`hasattr(dense, 'model')`** — re-verify on tip if dense inject silently no-ops; prefer `_ensure_model()` / `_encode()`.
3. Parent gitlinks must be advanced after KB/orch feature merges (do not leave docker-cp-only fixes unpinned).
4. Audit criticals (auth, path traversal, CORS, PII Persian digits, etc.) may still be open — re-check before claiming fixed.

## Coding hard rules

- `httpx.AsyncClient(..., trust_env=False)` for localhost  
- Never `asyncio.to_thread` + asyncpg  
- Never `pkill python` — `bash deploy/vast/stop.sh`  
- Gemma: `enable_thinking:false` + `--no-mmproj --jinja`  
- Conventional commits; no force-push; no secrets  

## More

- [reference.md](reference.md) — decisions, ports, hosts  
- Component skills: `rag-component-workflow`, plus `rag-kb`, `rag-orchestrator`, `rag-guardrails` under `.cursor/skills/`  
- UI skills: `dana-ui`, `dana-contrast` (see also `.cursor/UI_TOOLING.md`)  
- Agent copies: `agent-state/skills/`
