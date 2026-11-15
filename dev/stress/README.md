# Sticky stress QA — moved to Evaluation Suite

Canonical harnesses and frozen 30/40/50 before→after results now live in the
evaluation submodule:

| Item | Path |
|------|------|
| Suite README | [`components/evaluation/datasets/stress/README.md`](../../components/evaluation/datasets/stress/README.md) |
| Scripts | `components/evaluation/scripts/run_stress_clarify.py` (+ sticky / compare / regression) |
| Results | `components/evaluation/datasets/stress/results/` |
| Report | [`components/evaluation/docs/STRESS_CLARIFY_BEFORE_AFTER_2026-11-16.md`](../../components/evaluation/docs/STRESS_CLARIFY_BEFORE_AFTER_2026-11-16.md) |

```bash
cd components/evaluation
python scripts/run_stress_clarify.py --turns 50
python scripts/compare_stress_clarify.py
```

Do not add new stress baselines here — commit them in Work_RAG-Evaluation_Suite.
