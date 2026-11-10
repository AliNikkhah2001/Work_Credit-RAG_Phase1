# Work Credit RAG — Technical Documentation Report

**Organization:** Iranian Credit Scoring Company (ICS)  
**Platform:** Work Credit RAG Phase 1 (Dana Agent Framework)  
**Document date:** 2026-11-10

## Submodule pins

| Module | Branch | Pages pin | Owns |
|---|---|---|---|
| Server setup | `main` | `ff8c5a8` | LLM manager `:9000`, embeds `:8001`–`:8003` |
| Knowledge base | `master` | `92503e5` | Ingest, retrieval `:8000` |
| Guardrails | `main` | `1002ea8` | Persian rails, guarded generate `:8200` |
| Orchestrator | `main` | `75cf970` | LangGraph API `:8100` |
| Tracing | — | — | Fallback collector `:3000` |
| Agent-state | `main` | `a0d454e` | Agent context (off request path) |
