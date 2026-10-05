# Documentation Index

This directory contains project-wide documentation.

> **Note:** Historical planning and migration documents (including `RUNBOOK_VAST.md`, `MVP_INTEGRATION_PLAN.md`, `GUARDRAILS_V2_PLAN.md`, `RERANKER_MEMORY_TASK.md`, `architecture.md`, `models.md`, `training.md`, and `PROJECT_HIERARCHY.md`) have been moved to `deprecated/plans/`.

## Technical Reference & Evaluation

| File | Description |
|------|-------------|
| [evaluation.md](evaluation.md) | KB retrieval benchmarks, RAG E2E, LLM-as-judge, reproduction |
| [cross_encoder_benchmark_results.md](cross_encoder_benchmark_results.md) | Cross-encoder reranker benchmark results and latency breakdown |
| [history/](history/) | Historical code audits and reviews |

## Reports

- `benchmark-report/` — GitHub Pages site (built at runtime via `eval/build_report_site.py`)

## Component Documentation

Each component has its own README:

- [components/orchestrator/README.md](../components/orchestrator/README.md)
- [components/guardrails/README.md](../components/guardrails/README.md)
- [components/knowledgebase/kb-manager/README.md](../components/knowledgebase/kb-manager/README.md)
- [components/knowledgebase/kb-source/README.md](../components/knowledgebase/kb-source/README.md)
- [components/server-setup/README.md](../components/server-setup/README.md)
- [components/tracing/README.md](../components/tracing/README.md)

## Deployment

- [deploy/docker/README.md](../deploy/docker/README.md) — Privileged Docker Compose
- [deploy/vast/](../deploy/vast/) — Vast.ai host-venv scripts
- [compose.mvp.yml](../compose.mvp.yml) — Vast MVP variant

## Contracts

- [contracts/README.md](../contracts/README.md) — JSON Schema contracts for MVP integration