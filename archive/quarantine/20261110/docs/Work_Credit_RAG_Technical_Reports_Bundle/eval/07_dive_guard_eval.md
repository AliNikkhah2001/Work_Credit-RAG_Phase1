# Eval: `07_dive_guard.md`

**Status:** PASS_AFTER_FIX

## Initial verdict: FAIL

## Rubric (after fix)

| # | Criterion | Result |
|---|---|---|
| 1 | Section summary at start | Pass — `## Section summary` |
| 2 | Original prose | Pass — post-NeMo signals/judge design, not README dump |
| 3 | Hierarchical headings; purposeful bold/italic | Pass |
| 4 | Every figure has multi-sentence caption | Pass after fix — Fig 11 expanded; Fig 12 already multi-sentence |
| 5 | Real code paths cited | Pass — `service.py`, `signals.py`, `judge.py`, `events.py`, `dashboard.py`, `observability.py` |
| 6 | Observed benchmarks with sources | Pass (N/A) — no latency bench claimed; policy behavior described instead |
| 7 | Tooling table with GitHub URLs | Pass after fix — Pydantic and uvicorn now have GitHub links |
| 8 | No secrets | Pass — `sk-…` / pattern tokens are detector examples, not live credentials |

## Flaws (pre-fix)

- Figure 11 caption had only one explanatory sentence after the title.
- Tooling table listed “Pydantic / uvicorn” without GitHub URLs (“stdlib of the FastAPI stack”).

## Fixes applied

- Expanded Figure 11 caption (orchestrator contract, Vast vs H200 upstream, masked vs refuse outcomes).
- Split Pydantic and uvicorn into rows with `pydantic/pydantic` and `encode/uvicorn` URLs.
