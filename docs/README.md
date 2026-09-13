# Documentation Index

This directory contains project-wide documentation.

## Guides

| File | Description |
|------|-------------|
| [RUNBOOK_VAST.md](RUNBOOK_VAST.md) | Vast.ai startup, env, ports, troubleshooting |
| [VAST_GEMMA4_MIGRATION.md](VAST_GEMMA4_MIGRATION.md) | Migration log: discovery, 14 inspections, fixes, HurtLex audit |
| [MVP_INTEGRATION_PLAN.md](MVP_INTEGRATION_PLAN.md) | Cross-component implementation sequence, acceptance criteria |
| [GUARDRAILS_V2_PLAN.md](GUARDRAILS_V2_PLAN.md) | Risk scoring, observability, semantic interface, thresholds, rollback |
| [RERANKER_MEMORY_TASK.md](RERANKER_MEMORY_TASK.md) | Reranker/memory task specification |

## Technical Reference

| File | Description |
|------|-------------|
| [architecture.md](architecture.md) | System architecture, request flow, component diagrams, ports, env vars |
| [models.md](models.md) | Model cards for all models (generation, embedding, reranker, guardrails) |
| [evaluation.md](evaluation.md) | KB retrieval benchmarks, RAG E2E, LLM-as-judge, reproduction |
| [training.md](training.md) | KB ingestion pipeline, reranker shootout, query reform, quality gates |

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