# Sticky multiturn stress QA (`dev/stress`)

Development-only harnesses for long sticky conversations against local
orchestrator (`:8100`). Not used in production deploy.

## Harnesses

| Script | Purpose |
|--------|---------|
| `longconv_stress.py` | Sticky streaming N-turn stress (no clarify auto-reply) |
| `longconv_stress_clarify.py` | Same questions; auto-answers subspace clarifies (`حقیقی` / `حقوقی` / `چک` / …) and scores turns with a light heuristic |
| `compare_before_after.py` | Diff clarify baselines vs `*_after.json` reruns |
| `eval_final_regression.py` | Focused hard-case pack (سفته, ضمانت‌نامه, سوابق, …) + LiteLLM judge |

```bash
# Clarify-aware 30 / 40 / 50 (sticky X-Request-ID)
python3 dev/stress/longconv_stress_clarify.py --turns 30 \
  --label after-fix-30 --out dev/stress/results/stress_clarify_30_after.json

python3 dev/stress/compare_before_after.py
```

Requires healthy dana-local stack (`8100` orch, `8200` guardrails, `8000` KB).

## Before → after QA-loop fixes (2026-11-16)

Baselines: `results/stress_clarify_{30,40,50}.json` (pre-fix).  
Reruns: `results/stress_clarify_{30,40,50}_after.json`.  
Full write-up: [`results/compare_clarify_before_after.md`](results/compare_clarify_before_after.md).

| Suite | avg score | content_filter | یافت نشد / no_evidence | hard errors |
|------:|----------:|---------------:|-------------------------:|------------:|
| 30 | 0.908 → **0.932** | 1 → **0** | 2 → **1** | 0 → 0 |
| 40 | 0.904 → **0.955** | 1 → **0** | 4 → **0** | 0 → 0 |
| 50 | 0.907 → **0.947** | 2 → **0** | 4 → **1** | 0 → 0 |

All three after runs finished with **0 hard errors** (36/36, 47/47, 58/58 OK).

### Component fixes exercised by this pack

| Area | Change | Repo / PR |
|------|--------|-----------|
| Abstention recovery when evidence exists | orch | Work_RAG-Orchestrator #26 |
| T1/T2 `scope_broadened` disclosure | orch | #27 |
| Buffer RAG before SSE | orch | #29 |
| ضمانت‌نامه vs ضامن ranking | orch | #30 |
| `سوابق منفی` domain keywords | guardrails | Work_RAG-Guardrails #9 |
| `سفته` in-domain | guardrails | #11 |

Umbrella pin: orchestrator `80bcb5c`, guardrails `35a990d`.

### Residual

`تفاوت اعتبارسنجی حقیقی و حقوقی چیست؟` still returned «یافت نشد» on the 30- and 50-turn after runs (clean on 40). Treat as follow-up, not closed by this loop.
