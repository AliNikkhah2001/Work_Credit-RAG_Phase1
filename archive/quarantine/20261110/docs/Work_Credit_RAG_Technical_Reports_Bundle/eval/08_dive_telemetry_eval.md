# Eval: `08_dive_telemetry.md`

**Status:** PASS_AFTER_FIX

## Initial verdict: FAIL

## Rubric (after fix)

| # | Criterion | Result |
|---|---|---|
| 1 | Section summary at start | Pass — `**Section summary.**` lead |
| 2 | Original prose | Pass — layered telemetry + latency evidence narrative |
| 3 | Hierarchical headings; purposeful bold/italic | Pass — `### 8.x` hierarchy |
| 4 | Every figure has multi-sentence caption | Pass — Figs 15–16 and two latency plots |
| 5 | Real code paths cited | Pass — `search.py`, `tracing.py`, `eval_store.py`, `retrieve.py`, guard `events.py`, etc. |
| 6 | Observed benchmarks with sources | Pass — v13.1 stage table; `bench_report_latest` E2E p50/avg |
| 7 | Tooling table with GitHub URLs | Pass after fix — added §8.9 Tooling (Langfuse, Prometheus, FastAPI, httpx) |
| 8 | No secrets | Pass |

## Flaws (pre-fix)

- No tooling table with GitHub URLs despite heavy use of Langfuse / Prometheus / FastAPI / httpx (other dive sections include one).

## Fixes applied

- Inserted `### 8.9 Tooling` table with GitHub URLs and logos.
- Renumbered documentation note to `### 8.10`.
