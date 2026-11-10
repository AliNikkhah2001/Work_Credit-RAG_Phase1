# Technical report dive sections — quality eval summary

| Section file | Eval file | Status |
|---|---|---|
| `sections/04_dive_kb.md` | `eval/04_dive_kb_eval.md` | **PASS** |
| `sections/05_dive_orch.md` | `eval/05_dive_orch_eval.md` | **PASS** |
| `sections/06_dive_server.md` | `eval/06_dive_server_eval.md` | **PASS_AFTER_FIX** |
| `sections/07_dive_guard.md` | `eval/07_dive_guard_eval.md` | **PASS_AFTER_FIX** |
| `sections/08_dive_telemetry.md` | `eval/08_dive_telemetry_eval.md` | **PASS_AFTER_FIX** |

## Fix notes (FAIL → PASS_AFTER_FIX)

- **06 server:** expanded Figure 17 caption; Docker tooling URL → `moby/moby`.
- **07 guard:** expanded Figure 11 caption; added Pydantic + uvicorn GitHub URLs.
- **08 telemetry:** added tooling table (Langfuse, Prometheus, FastAPI, httpx).

All five sections now meet the rubric after the above minimal edits.
