# Eval: `05_dive_orch.md`

**Status:** PASS

## Rubric

| # | Criterion | Result |
|---|---|---|
| 1 | Section summary at start | Pass — `**Section summary.**` lead |
| 2 | Original prose | Pass — graph walkthrough with sticky/evidence design rationale |
| 3 | Hierarchical headings; purposeful bold/italic | Pass |
| 4 | Every figure has multi-sentence caption | Pass — HL + detail LangGraph figures |
| 5 | Real code paths cited | Pass — `graph.py`, `state.py`, `nodes/retrieve.py`, `build_context.py`, `clients/knowledgebase.py`, `api.py` (+ code map table) |
| 6 | Observed benchmarks with sources | Pass — `bench_report_latest` (2026-10-14): p50 4872 ms, retrieval_hit 0.780 |
| 7 | Tooling table with GitHub URLs | Pass — LangGraph, FastAPI, httpx, Langfuse |
| 8 | No secrets | Pass |

## Flaws

- None material. FastAPI URL uses historical `tiangolo/fastapi` org path (still valid redirect).
