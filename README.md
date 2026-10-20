# Work Credit RAG — Phase 1

[![Python](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/downloads/release/python-3110/)
[![License](https://img.shields.io/github/license/AliNikkhah2001/Work_Credit-RAG_Phase1)](LICENSE)
[![Branch](https://img.shields.io/badge/branch-main-blue)]()

Umbrella repository for a self-hosted, Persian-capable conversational RAG platform. The implementation is split into independently maintained Git submodules so model/server operations, knowledge-base lifecycle, safety policy, and LangGraph orchestration can evolve without returning to a monolith.

> **Status:** Active on `main`. Deployed on Vast.ai (2026-09-12, RTX 3090) · H200 host via `Work_RAG-Server-Setup` LLM manager `:9000`. Current KB `v13 1405-07-06` — `18` docs / `1123` chunks · `pgvector HNSW` · `MAX_CHUNKS=20`.

---

## 🌐 Research Site (NEW)

**Interactive multi-page research site:** [https://alinikkhah2001.github.io/Work_Credit-RAG_Phase1/](https://alinikkhah2001.github.io/Work_Credit-RAG_Phase1/)

- **Problems**: Detailed root cause analysis for all 6 problems
- **Papers & Solutions**: 25+ papers from ACL 2025, EMNLP 2025, SIGIR 2024/25, SIGDIAL 2025/26, SemEval 2026, NeurIPS 2025
- **Architectures**: Mermaid diagrams for SPLIT-RAG, PC-RAG, RAC, ICR, CPP, CALMem, H-RAG, 5ting, GUIR, DUTIR, CoRAG, IM-RAG
- **Relevance Mapping**: 10 fixes → 25+ papers with section-level mapping
- **Benchmarks**: MTRAG, MTRAGEval, CORAL, RAD-Bench, our 41-turn results
- **Our Implementation**: T1-T8 fixes, code pointers, benchmark deltas, deployment notes

---

## Latest Metrics

| Layer | Metric | Value | Source |
|---|---|---|---|
| **Retrieval (v13, 1123 chunks)** | General Hit@K | `0.600` (best) vs cheque `0.111` | `docs/benchmark-report-2026-10-12.md` (41 turns) |
| | Overall retrieval_hit | `0.537` | RAGAS, same |
| **RAG (41-turn multi-agent, 2026-10-12)** | faithfulness / non_hallucination | `0.644` / `0.805` | gemma-4-31b judge via `:9000` |
| | ambiguity `0.854*` / sticky `0.610` | *`0/6` scattered fails hidden | same |
| | p50 latency | `8006ms` (`retrieve 1681ms` + `generate 5381ms`) | same |
| | error_rate | `0.0%` (41/41 `200 OK`) | same |
| **Retrieval legacy (v8, 6593 chunks, 800 Q)** | MRR (BGE-m3 pool15) | `0.496` vs MiniLM `0.493` | full-800 reranker shootout `2026-09-12/13` |
| | Hit@5 | `0.536` | same |

> Historical tables kept in [`docs/benchmark-report-2026-10-12.md`](docs/benchmark-report-2026-10-12.md) §2–3 and legacy `archive/migration-history/`.

## Table of Contents

- [Architecture](#architecture)
- [Repository Composition](#repository-composition)
- [Request Lifecycle](#request-lifecycle)
- [Quick Start](#quick-start)
- [Tester Accounts](#tester-accounts) — **20 sample logins + dashboard**
- [Models](#models)
- [Configuration](#configuration)
- [Observability](#observability)
- [Evaluation](#evaluation) — **conversational RAGAS 2026-10-12**
- [Knowledge Subspaces & Filtering](#knowledge-subspaces--filtering)
- [Supplementary Data](#supplementary-data)
- [Done vs Pending](#done-vs-pending)
- [Verification](#verification)
- [Archive](#archive)
- [Updating a Submodule](#updating-a-submodule)

<!-- docs-toc:start -->
## Documentation Index

> Auto-generated from this repository's tracked Markdown notes (**106** files). Refresh with `python scripts/gen_readme_toc.py` — the `docs-toc` workflow does this automatically on push.

### Repository root

- [AGENTS.md — Agent Operating Manual (umbrella repo)](AGENTS.md) — Umbrella repo; implementation lives in submodules. Do NOT duplicate component code in parent.
- [Comprehensive Million-User Scaling Architecture Plan](million-user-scale-plan.md) — This document serves as the master architectural blueprint for scaling the Knowledge Base Retrieval system to support 1,000,000+ concurrent users.
- [Tester Credentials — ICS RAG Evaluation](tester-credentials.md) — 1. Open http://127.0.0.1:13000.

### `.opencode/`

- [Plan: Fix 142 Code Audit Errors (2026-09-27)](.opencode/plans/audit-fix-2026-09-27.md) — 1. git switch -c chore/fix-critical-kb in components/knowledgebase

### `archive/`

- [Archive — Non-code artifacts](archive/README.md) — This directory holds artifacts moved off main during chore/cleanup-consolidated.
- [Documentation Audit — Work Credit RAG Phase 1](archive/audit-2026-09-12/documentation_audit.md) — Generated: 2026-09-12 | Auditor: Agent 1 (Repository Documentation Explorer)
- [Documentation Changes Summary](archive/audit-2026-09-12/documentation_changes.md) — Generated: 2026-09-12 | Agents 1-8 Documentation Upgrade
- [Final Documentation Review Checklist](archive/audit-2026-09-12/final_review_checklist.md) — Generated: 2026-09-12 | Agent 8 — Final Review
- [Archived Benchmark Scripts](archive/benchmark-scripts/README.md) — Two near-duplicate reranker benchmark scripts archived from scripts/ — canonical is scripts/cross_encoder_benchmark.py.
- [Opencode session export](archive/handoff-sessions/SESSION_WAVE1_HANDOFF.md) — Session: ses_f6b058c02ffej8lpFUThWHsld0
- [Session index](archive/handoff-sessions/sessions/INDEX.md)
- [Commit + push all repos (@general subagent)](archive/handoff-sessions/sessions/ses_f662eaa09ffek59tAqzqgrzmk3_commit-push-all-repos-general-subagent.md) — Session: ses_f662eaa09ffek59tAqzqgrzmk3
- [Validate stack + E2E smoke (@general subagent)](archive/handoff-sessions/sessions/ses_f662eaa2cffeqIf44RU7HD6lr5_validate-stack-e2e-smoke-general-subagen.md) — Session: ses_f662eaa2cffeqIf44RU7HD6lr5
- [Finish wave-1 bench + aggregate (@general subagent)](archive/handoff-sessions/sessions/ses_f662eaa64ffeVRZClGRfuksXF6_finish-wave-1-bench-aggregate-general-su.md) — Session: ses_f662eaa64ffeVRZClGRfuksXF6
- [Fact-check guardrails+setup (@general subagent)](archive/handoff-sessions/sessions/ses_f69bd0067ffeYkQj7BGbueJNdi_fact-check-guardrails-setup-general-suba.md) — Session: ses_f69bd0067ffeYkQj7BGbueJNdi
- [Fact-check KB submodule (@general subagent)](archive/handoff-sessions/sessions/ses_f69bd00e1ffeZpMuACZP7ACDqh_fact-check-kb-submodule-general-subagent.md) — Session: ses_f69bd00e1ffeZpMuACZP7ACDqh
- [Fact-check orchestrator (@general subagent)](archive/handoff-sessions/sessions/ses_f69bd0132ffe2p2YKzUyAoAX4g_fact-check-orchestrator-general-subagent.md) — Session: ses_f69bd0132ffe2p2YKzUyAoAX4g
- [Fact-check root+deploy (@general subagent)](archive/handoff-sessions/sessions/ses_f69bd0148ffeo0kdaWGrhDa6gn_fact-check-root-deploy-general-subagent.md) — Session: ses_f69bd0148ffeo0kdaWGrhDa6gn
- [Doc explorer inventory (@general subagent)](archive/handoff-sessions/sessions/ses_f69bd019cffe7w8mbt1Nvf53kO_doc-explorer-inventory-general-subagent.md) — Session: ses_f69bd019cffe7w8mbt1Nvf53kO
- [Audit mystery observe code (@general subagent)](archive/handoff-sessions/sessions/ses_f69fe249effefURDV1vv5x7Ttk_audit-mystery-observe-code-general-subag.md) — Session: ses_f69fe249effefURDV1vv5x7Ttk
- [Find observability tooling (@explore subagent)](archive/handoff-sessions/sessions/ses_f6a50d043ffe5vMowwTpZc2eul_find-observability-tooling-explore-subag.md) — Session: ses_f6a50d043ffe5vMowwTpZc2eul
- [Find conversation history (@explore subagent)](archive/handoff-sessions/sessions/ses_f6a50d05cffef0ThivrPDUeYeI_find-conversation-history-explore-subage.md) — Session: ses_f6a50d05cffef0ThivrPDUeYeI
- [RAG agent history location and observability](archive/handoff-sessions/sessions/ses_f6a50ebb5ffeHsJtLNMo7LEtg5_rag-agent-history-location-and-observabi.md) — Session: ses_f6a50ebb5ffeHsJtLNMo7LEtg5
- [FlagEmbedding big-model loaders (@general subagent)](archive/handoff-sessions/sessions/ses_f6a52d486ffeKuQPQG2ppRetTT_flagembedding-big-model-loaders-general.md) — Session: ses_f6a52d486ffeKuQPQG2ppRetTT
- [Orchestrator memory code (@general subagent)](archive/handoff-sessions/sessions/ses_f6a575eeaffeM2uwbOgHGye6ef_orchestrator-memory-code-general-subagen.md) — Session: ses_f6a575eeaffeM2uwbOgHGye6ef
- [KB reranker registry code (@general subagent)](archive/handoff-sessions/sessions/ses_f6a575ef9ffenaUjaoyJIMHrEG_kb-reranker-registry-code-general-subage.md) — Session: ses_f6a575ef9ffenaUjaoyJIMHrEG
- [Download rerankers set B (@general subagent)](archive/handoff-sessions/sessions/ses_f6a575f11fferEABLFMd57wGM6_download-rerankers-set-b-general-subagen.md) — Session: ses_f6a575f11fferEABLFMd57wGM6
- [Download 9B reranker (@general subagent)](archive/handoff-sessions/sessions/ses_f6a575f29ffecMT5puzXMjSxCv_download-9b-reranker-general-subagent.md) — Session: ses_f6a575f29ffecMT5puzXMjSxCv
- [Download rerankers set A (@general subagent)](archive/handoff-sessions/sessions/ses_f6a575f42ffe8YMbPSYvlfdqbA_download-rerankers-set-a-general-subagen.md) — Session: ses_f6a575f42ffe8YMbPSYvlfdqbA
- [Map reranker and memory code (@explore subagent)](archive/handoff-sessions/sessions/ses_f6a5ca448ffe8q908qHWfK4yfS_map-reranker-and-memory-code-explore-sub.md) — Session: ses_f6a5ca448ffe8q908qHWfK4yfS
- [Write docker stack files (@general subagent)](archive/handoff-sessions/sessions/ses_f6a7738f9ffe6RAZA5rnjuvxBe_write-docker-stack-files-general-subagen.md) — Session: ses_f6a7738f9ffe6RAZA5rnjuvxBe
- [Write AGENTS.md + commands (@general subagent)](archive/handoff-sessions/sessions/ses_f6a773916ffeTskweHocLEiRAC_write-agents-md-commands-general-subagen.md) — Session: ses_f6a773916ffeTskweHocLEiRAC
- [Build real Langfuse v2 UI (@general subagent)](archive/handoff-sessions/sessions/ses_f6a97a23affe977umsOKmNDWKm_build-real-langfuse-v2-ui-general-subage.md) — Session: ses_f6a97a23affe977umsOKmNDWKm
- [Setup LangGraph Studio (@general subagent)](archive/handoff-sessions/sessions/ses_f6a97a260ffeNWjOmUVpgAKRNd_setup-langgraph-studio-general-subagent.md) — Session: ses_f6a97a260ffeNWjOmUVpgAKRNd
- [Create py venvs install deps (@general subagent)](archive/handoff-sessions/sessions/ses_f6ad8e88effer0fXVBgn30KyXr_create-py-venvs-install-deps-general-sub.md) — Session: ses_f6ad8e88effer0fXVBgn30KyXr
- [Setup postgres pgvector DB (@general subagent)](archive/handoff-sessions/sessions/ses_f6ad8e89dffegpnjRGd8kSSLW1_setup-postgres-pgvector-db-general-subag.md) — Session: ses_f6ad8e89dffegpnjRGd8kSSLW1
- [Build llama.cpp CUDA (@general subagent)](archive/handoff-sessions/sessions/ses_f6ad8e8c3ffeKEoTAsrQxIu6Ya_build-llama-cpp-cuda-general-subagent.md) — Session: ses_f6ad8e8c3ffeKEoTAsrQxIu6Ya
- [Explore llama-server build/run docs (@explore subagent)](archive/handoff-sessions/sessions/ses_f6ae9b92dffeCirKJEEjVK2fdE_explore-llama-server-build-run-docs-expl.md) — Session: ses_f6ae9b92dffeCirKJEEjVK2fdE
- [Explore orchestrator+guardrails run (@explore subagent)](archive/handoff-sessions/sessions/ses_f6ae9f317ffeSmRPrDg6hREnnA_explore-orchestrator-guardrails-run-expl.md) — Session: ses_f6ae9f317ffeSmRPrDg6hREnnA
- [Explore KB pgvector setup (@explore subagent)](archive/handoff-sessions/sessions/ses_f6aea1199ffe0EIUQ3IBkDuBL2_explore-kb-pgvector-setup-explore-subage.md) — Session: ses_f6aea1199ffe0EIUQ3IBkDuBL2
- [Sync orchestrator git (@general subagent)](archive/handoff-sessions/sessions/ses_f6af2b3a1ffeqp0RpKmQCp9t0g_sync-orchestrator-git-general-subagent.md) — Session: ses_f6af2b3a1ffeqp0RpKmQCp9t0g
- [Sync guardrails git (@general subagent)](archive/handoff-sessions/sessions/ses_f6af2c18effebM96RGD21aMR6h_sync-guardrails-git-general-subagent.md) — Session: ses_f6af2c18effebM96RGD21aMR6h
- [Sync knowledgebase git (@general subagent)](archive/handoff-sessions/sessions/ses_f6af2da53ffeZAu3vFPZU39v3C_sync-knowledgebase-git-general-subagent.md) — Session: ses_f6af2da53ffeZAu3vFPZU39v3C
- [Sync server-setup git (@general subagent)](archive/handoff-sessions/sessions/ses_f6af303aaffe5bPJzZj0L31OED_sync-server-setup-git-general-subagent.md) — Session: ses_f6af303aaffe5bPJzZj0L31OED
- [Sync parent repo git (@general subagent)](archive/handoff-sessions/sessions/ses_f6af32e65ffe85ebRy2z0t20qB_sync-parent-repo-git-general-subagent.md) — Session: ses_f6af32e65ffe85ebRy2z0t20qB
- [Find chat history for RAG agent project](archive/handoff-sessions/sessions/ses_f6b058c02ffej8lpFUThWHsld0_find-chat-history-for-rag-agent-project.md) — Session: ses_f6b058c02ffej8lpFUThWHsld0
- [Handoff Archive](archive/handoff/README.md) — Raw evaluation artifacts moved from handoff/ on chore/cleanup-phase2.
- [Vast.ai Gemma-4 Migration — Execution Log](archive/migration-history/VAST_GEMMA4_MIGRATION.md) — Discovery report (architecture map, 14 inspection items, H/I/J/K/L findings) approved before this log.
- [Wave-2 GPU Runbook — heavy reranker shootout on a bigger machine](archive/migration-history/WAVE2_GPU_RUNBOOK.md) — Date: 2026-09-13. Wave 1 (CPU, 800 remapped queries) is done for
- [Guardrails v2 Plan — Risk Scoring + Semantic + Observability](archive/plans/GUARDRAILS_V2_PLAN.md) — Every POST /v1/rails/check and POST /v1/chat/completions will expose (in logs and optional response header X-Guardrails-Observability):
- [Task: reranker benchmark + conversation memory (branch feat/reranker-memory)](archive/plans/RERANKER_MEMORY_TASK.md) — 1. Compare cross-encoder rerankers (incl. biggest SOTA) on our Persian credit KB and pick the winner.
- [Vast.ai Runbook — Work Credit RAG Phase 1 (Public)](archive/plans/RUNBOOK_VAST.md) — Existing Gemma is external http://127.0.0.1:18000/v1 (unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL, llama-server pid 676). Do NOT launch gemma-manager, do…
- [System Architecture — Work Credit RAG Phase 1](archive/plans/architecture.md)
- [Model Cards — Work Credit RAG Phase 1](archive/plans/models.md)
- [Training & Pipeline — Work Credit RAG Phase 1](archive/plans/training.md) — 1. Fresh corpus from kb-source/1405-05-31/ (legal/individual/other/technical)
- [Archived Scripts](archive/scripts/README.md) — Utilities moved from scripts/ — not in deploy/vast/start.sh hot path.
- [Windows Launchers (archived)](archive/windows-launchers/README.md) — Linux host uses deploy/vast/start.sh + scripts/run_mvp.sh. Windows artifacts archived:

### `components/`

- [Work Credit RAG — Benchmark Report](components/evaluation/artifacts/bench_report_latest.md) — Artifacts: bench_results_latest.json + ragas_results_latest.json → bench_report_latest.html / .md
- [OpenWebUI RAG Filters & Actions — Agent Testing UI (Phase 2 & 4)](components/openwebui-filters/README.md) — Three OpenWebUI Functions that connect the chat UI to the Work Credit RAG
- [Work RAG Tracing](components/tracing/README.md) — Fallback trace collector and local observation UI for the Work Credit RAG platform.

### `contracts/`

- [Cross-Component Contracts](contracts/README.md) — This directory contains versioned JSON Schema contracts for the MVP integration.

### `deploy/`

- [Work Credit RAG — Docker deployment (privileged CUDA host)](deploy/docker/README.md) — Full-stack docker compose version of the platform. Mirrors

### `deprecated/`

- [Deprecated Files — Reconstruction Guide](deprecated/README.md) — These files were moved here on 2026-09-27 during a repository cleanup.
- [AGENTS — Fix Plan for 142 Audit Errors (2026-09-27)](deprecated/audits/AGENTS_FIX_PLAN.md) — This file is the agent operating manual for fixing the audit. Use with AGENTS.md (repo map, ports, workflows) and README.md (architecture). For how t…
- [Plan: Fix 142 Code Audit Errors (2026-09-27)](deprecated/audits/opencode_audit-fix-2026-09-27.md) — 1. git switch -c chore/fix-critical-kb in components/knowledgebase
- [GUARDRAILS_V2_PLAN — Archived](deprecated/plans/GUARDRAILS_V2_PLAN.md) — Historical content archived at archive/plans/GUARDRAILS_V2_PLAN.md (2026-09-27, chore/cleanup-phase2).
- [Work Credit RAG Integration Plan](deprecated/plans/MVP_INTEGRATION_PLAN.md) — This plan converts Work_Credit-RAG_Phase1 from a monolithic prototype into the composition and release repository for four independently maintained c…
- [Work Credit RAG — Full Project Hierarchy](deprecated/plans/PROJECT_HIERARCHY.md) — Generated: 2026-09-27 | Root: /splunk-data/v1/Work_Credit-RAG_Phase1 | Branch: main @ f402517
- [RERANKER_MEMORY_TASK — Archived](deprecated/plans/RERANKER_MEMORY_TASK.md) — Historical content archived at archive/plans/RERANKER_MEMORY_TASK.md (2026-09-27, chore/cleanup-phase2).
- [RUNBOOK_VAST — Archived](deprecated/plans/RUNBOOK_VAST.md) — Historical content archived at archive/plans/RUNBOOK_VAST.md (2026-09-27, chore/cleanup-phase2).
- [architecture — Archived](deprecated/plans/architecture.md) — Historical content archived at archive/plans/architecture.md (2026-09-27, chore/cleanup-phase2).
- [models — Archived](deprecated/plans/models.md) — Historical content archived at archive/plans/models.md (2026-09-27, chore/cleanup-phase2).
- [training — Archived](deprecated/plans/training.md) — Historical content archived at archive/plans/training.md (2026-09-27, chore/cleanup-phase2).
- [Continuation prompt — paste into a new opencode session on the bigger GPU machine](deprecated/session-artifacts/handoff_CONTINUE.md) — You are continuing the Persian Credit RAG Phase-1 project. Context files (read first):
- [Handoff — Archived](deprecated/session-artifacts/handoff_README.md)
- [COMMANDS.md — Vast.ai command reference (instance 50713720, 2026-09-12, 1x RTX 3090)](deprecated/session-artifacts/vast_COMMANDS.md) — Copy-pasteable. Root = /workspace/Work_Credit-RAG_Phase1. All RAG services bind 0.0.0.0 except Gemma (127.0.0.1:18000 by design).
- [Opencode session export](deprecated/session-artifacts/vast_SESSION_WAVE1_HANDOFF.md) — Session: ses_f6b058c02ffej8lpFUThWHsld0

### `docs/`

- [Documentation Index](docs/README.md) — This directory contains project-wide documentation.
- [Benchmark Report — Multi-Agent Conversational RAG Evaluation (2026-10-12)](docs/benchmark-report-2026-10-12.md) — filter_path maps to components/knowledgebase/kb-manager doc_metadata.folder_hierarchy (گزارش اعتباری چک | اشخاص حقیقی/اعتبارسنجی تسهیلات | اشخاص حقوق…
- [Cross-Encoder Reranker Benchmark Results](docs/cross_encoder_benchmark_results.md) — Tested 7 cross-encoder reranker models on the Work Credit RAG KB (v8 pgvector, 6593 chunks, 103 docs) using 20 diverse Persian credit queries.
- [Evaluation — Work Credit RAG Phase 1](docs/evaluation.md) — Historical per-version tables (v5 baseline, v7 IVA 15, v8 HNSW) were moved to archive/migration-history/ and eval/results/. See README.md#evaluation…
- [History — Code Audit 2026-09-27: 142 Errors & Anti-Patterns Found](docs/history/CODE_AUDIT_2026-09-27.md) — 1. components/knowledgebase/kb-manager — 7 Critical + 10 High (path traversal, unauth DB, unbounded disk, silent failures, ilike wildcard DoS, Vector…

### `eval/`

- [Wrong Samples Findings — Detailed Analysis (2026-09-02)](eval/FINDINGS.md) — This document details every RAG response that was wrong (blocked, fallback, English, or missing citations) when evaluated against KB ground truth, ho…
- [KB RAG Evaluation — 2026-09-02](eval/README.md) — This directory contains end-to-end evaluation of the RAG agent against KB ground truth on Vast VM.

### `evaluation/`

- [Work Credit RAG — Benchmark Report](evaluation/artifacts/bench_report_latest.md) — Artifacts: bench_results_latest.json + ragas_results_latest.json → bench_report_latest.html / .md

### `research-site/`

- [Architectures](research-site/architectures.md) — Mermaid diagrams of paper architectures: SPLIT-RAG, PC-RAG, RAC, ICR, CPP, CALMem, H-RAG, 5ting, GUIR, DUTIR, CoRAG, IM-RAG
- [Benchmarks](research-site/benchmarks.md) — MTRAG, MTRAGEval, CORAL, RAD-Bench, SemEval 2026 Task 8 - 842-turn multi-turn benchmark, nDCG@5, RAGAS, human evaluation, automated eval
- [Overview](research-site/index.md) — Comprehensive research on multi-turn RAG challenges: subspace filtering, ambiguity resolution, sticky context, and their 2025-2026 state-of-the-art s…
- [Our Implementation](research-site/our-impl.md) — T1-T8 fixes, code pointers, benchmark deltas, deployment notes, and remaining gaps
- [Advanced RAG Paradigms Papers](research-site/papers/advanced-rag.md) — CoRAG, IM-RAG, CoopRAG, MMOA-RAG, Reflective RAG, CalibRAG - Chain-of-Retrieval, Inner Monologues, Cooperative RAG, Multi-agent RL, Self-evaluation
- [Ambiguity & Clarification Papers](research-site/papers/ambiguity-clarification.md) — RAC, ICR, Qulac/ClariQ/ClariT, CLARITY - Retrieval-grounded clarification, iterative clarify-rewrite loops, multi-facet ambiguity
- [Benchmarks & Evaluation Papers](research-site/papers/benchmarks.md) — MTRAG, MTRAGEval, CORAL, RAD-Bench, SemEval 2026 Task 8 - 842-turn multi-turn benchmark, nDCG@5, RAGAS, human evaluation, automated eval
- [Faithfulness & Hallucination Papers](research-site/papers/faithfulness.md) — DUTIR, Reflective RAG, 5ting, CoRAG, CoopRAG, CalibRAG - Faithfulness guards, self-evaluation, evidence-constrained generation, calibration
- [Papers & Solutions](research-site/papers/index.md) — 40+ papers from ACL 2025, EMNLP 2025, SIGIR 2024/25, SIGDIAL 2025/26, SemEval 2026, NeurIPS 2025, ICML 2025
- [Memory Architectures Papers](research-site/papers/memory-architectures.md) — CALMem, CPP, Context Recycling, Rag.NET, OpenAI Sessions - Dual memory, segmented episodic memory, bounded hierarchical context
- [Retrieval Fusion & RRF Papers](research-site/papers/retrieval-fusion.md) — GUIR, 5ting, H-RAG, Sifei, IITKanBDone, AILS-NTUA, uva-irlab - Multi-query fusion, dual-query merge, nested-RRF, hybrid dense+sparse, parent-child re…
- [Sticky Context & Memory Papers](research-site/papers/sticky-context.md) — CPP, CALMem, Context Recycling, Rag.NET, OpenAI Sessions - Segmented episodic memory, dual memory layers, bounded hierarchical context
- [Subspace & Domain Partitioning Papers](research-site/papers/subspace-filtering.md) — PC-RAG, SPLIT-RAG, DSRAG, EvoRAG - Domain-partitioned retrieval, question-driven graph partitioning, hierarchical KGs
- [Ambiguity Resolution Failure](research-site/problems/ambiguity-resolution.md) — 6/6 scattered queries failed to clarify. Fixed with retrieval-grounded clarification gate + iterative rewrite loop.
- [Hallucination Control](research-site/problems/hallucination.md) — Weak-evidence answers hallucinated. Fixed with coverage+score guard + lexical evidence bypass + per-subspace thresholds.
- [Problems](research-site/problems/index.md) — Detailed breakdown of each multi-turn RAG problem: root cause, production impact, and our fixes
- [CPU Latency Bottleneck](research-site/problems/latency.md) — Dense embed 2.3s dominated latency. Fixed with GPU embed + reranker + pool 30 = 100× speedup.
- [Retrieval Degradation](research-site/problems/retrieval-degradation.md) — Filtered retrieval = hard filter, no fallback. Fixed with RRF fusion + broadened retry + GPU acceleration.
- [Sticky Context Decay](research-site/problems/sticky-context.md) — Context lost after 3-4 generic turns. Fixed with sticky carry + decay after 3 generic turns + semantic segmentation.
- [Subspace Filtering Failure](research-site/problems/subspace-filtering.md) — Root cause: subspace_map mismatch ('چک' vs KB folder 'گزارش اعتباراتنجی چک'). Fixed with map correction + RRF fusion.
- [Relevance Mapping](research-site/relevance.md) — Detailed table mapping each of our fixes to the specific paper, section, and mechanism that validates it

<!-- docs-toc:end -->

---

## Architecture

### System Overview — Current Deployment (Vast + H200)

```mermaid
flowchart TB
    subgraph Client["Client Layer"]
        Browser["🌐 Browser"]
        WebUI["💬 Open WebUI :13000\nICS Helper (Arena OFF)\nFilters: rag_trace_capture\nActions: ⭐ rate / 🐛 report / 📄 view / ✅ truth"]
    end

    subgraph Orchestration["Orchestration — :8100"]
        Orch["🎯 Orchestrator\nLangGraph (MemorySaver)\nOpenAI-compatible /v1/chat/completions\nX-Request-ID sticky thread"]
        Classify["classify\n(greeting/spec/question)"]
        InferSpec["infer_specification\n+ LLM subspace judge"]
        Clarify["generate_clarification"]
    end

    subgraph Retrieval["Retrieval — :8000"]
        KB["📚 KB Manager\nBM25(tantivy) + Dense MiniLM-384\n+ RRF k=60 + CE BGE-v2-m3\npgvector HNSW (1123 chunks)"]
        Filter["filter_path\nfolder_hierarchy tag"]
        Suppl["supplement\nentity_lists (MiniLM cos>0.4)\n+ injected_entities (>0.6)"]
    end

    subgraph Safety["Safety — :8200"]
        GR["🛡️ Guardrails\nPOST /v1/rails/check (input)\nPOST /v1/chat/completions (guarded_generate)\nRisk + semantic + HurtLex"]
    end

    subgraph Generation["Generation"]
        Gemma["🤖 Gemma :18000\nllama-server UD-Q4_K_XL\n--no-mmproj --jinja\ntemp 0.2 ctx 8192"]
        Manager["🧩 LLM Manager :9000\n( H200: 5× Gemma 8080-84 )"]
        Embed["🔢 Embed :8001-8003\nE5-small/BGE-m3/MiniLM"]
    end

    subgraph Observability["Observability"]
        Collector["📝 Collector :3000\nPOST /api/observability/*\nSQLite observability.db"]
        Dashboard["📊 Dashboard :3000/dashboard/observability\n8-stage chunk cards"]
        LF2["📊 Langfuse v2 :3001\nPostgres + ClickHouse"]
        Studio["🔍 Studio :2024\nLangGraph API"]
        TraceApp["🔎 /observe + /studio"]
    end

    Browser --> WebUI
    WebUI -- "OPENAI_API_BASE_URL=8100/v1\n+ X-Request-ID" --> Orch
    Orch --> Classify
    Classify --> InferSpec
    InferSpec -- "should_clarify?" --> Clarify
    Clarify -- "clarify finish" --> WebUI
    InferSpec -- "allowed" --> KB
    KB --> Filter
    KB --> Suppl
    Suppl -- "MAX_CHUNKS=20\nMAX_CONTEXT=9000" --> Orch
    Orch -- "guarded_generate" --> GR
    GR --> Gemma
    Gemma -.-> Manager
    Embed -.-> KB
    Orch -.-> Collector
    Collector --> Dashboard
    Orch -.-> LF2
    Orch -.-> Studio
    Collector --> TraceApp
```

**What changed vs the old diagram:** `LangGraph` now has a **conditional clarify branch** (`should_clarify` → `generate_clarification` with `available_subspaces`) instead of linear 5 nodes; **KB** exposes `filter_path` on `folder_hierarchy` + **supplemental** entity-list injection (tool `POST /search/supplement`); **WebUI** runs `rag_trace_capture` filter that tags `filter_path` into `X-Request-ID` sticky threads; **Observability** is the unified `observability.db` (`dashboard/observability`) not just Langfuse fallback; **Generation** on H200 is fronted by `llm_inference_manager :9000` (Vast uses bare `:18000`).

### Request Flow — Sticky + Filtered RAG

```mermaid
sequenceDiagram
    participant U as User
    participant W as WebUI :13000 + filter
    participant O as Orchestrator :8100
    participant K as KB :8000
    participant G as Guardrails :8200
    participant M as Gemma :18000
    participant Obs as Collector :3000 / Langfuse :3001

    U->>W: Persian message (maybe "چک")
    W->>W: rag_trace_capture: prefix [چک]/scope → filter_path
    W->>O: POST /v1/chat/completions {messages[], filter_path?, X-Request-ID}
    O->>Obs: trace-create(input)

    O->>G: validate_input (input rails)
    G-->>O: {allowed, action, categories}

    alt blocked
        O->>O: format_refusal
        O-->>W: refusal (finish=content_filter)
    else allowed
        O->>O: classify (greeting/spec/question) + infer_specification (LLM)
        alt should_clarify (scattered / threshold 0.8 / general_exempt)
            O->>O: generate_clarification {question, available_subspaces}
            O-->>W: clarify (finish=clarify, no retrieval)
        else not clarify
            O->>K: POST /search/api {query (rewritten), top_k=20, filter_path?}
            K-->>O: SearchSteps {final_results[10], injected_entities, stage_ms}
            O->>K: POST /search/supplement {query, threshold=0.4} (tool, parallel)
            K-->>O: supplemental [{list_name, content, similarity}]
            O->>O: build_context (MAX_CHUNKS=20, MAX_CONTEXT_CHARS=9000, evidence_min_score 0.15 guard)
            alt no evidence (<0.15)
                O-->>W: abstain "پاسخی یافت نشد" (finish=stop, 0 citations)
            else has evidence
                O->>G: POST /v1/chat/completions (guarded_generate, enable_thinking:false)
                G->>M: llama-server chat
                M-->>G: raw answer
                G-->>O: {answer, guardrail_output}
                O->>O: format_response (citations ≤20, grounded follow_ups, supplemental envelope)
                O->>Obs: trace-create upsert(output, audit{retrieved_chunks, stage_timing, applied_subspace, filter_path})
                O-->>W: {choices[0].message.content, finish=stop, rag:{citations, supplemental, follow_ups}, audit}
            end
        end
    end
```

Key differences from MVP flow:
- `filter_path` travels **WebUI filter → Orchestrator → KB** and **sticks** via `X-Request-ID` thread until re-specified (short token `چک` re-spec switches subspace).
- `supplemental` is a **second KB call** (`POST /search/supplement`) for shareholder / entity lists, merged into context as `rag.supplemental`.
- `evidence_min_score 0.15` guards hallucination (G5) — low-score `0.028` cheque hits correctly abstain.
- `follow_ups` are **grounded** from the same `retrieved_chunks`, not LLM-free.

### Orchestrator Graph (LangGraph `components/orchestrator/src/work_rag_orchestrator/graph.py`)

```mermaid
flowchart TD
    START([START]) --> VI[validate_input]
    VI -->|blocked| FR[format_refusal]
    VI -->|allowed| CL[classify]
    CL --> INF[infer_specification]
    INF --> SC{should_clarify?}
    SC -->|yes| GC[generate_clarification]
    GC --> END([END])
    SC -->|no| RET[retrieve]
    RET --> BC[build_context]
    BC --> GG[guarded_generate]
    GG --> FRMT[format_response]
    FRMT --> END
    FR --> END

    style SC fill:#fff3e0,stroke:#ff9800
    style GC fill:#fff8e1,stroke:#f57f17
```

Old doc showed linear `validate → retrieve → build → generate → format`. Now there is a **diamond** before `retrieve`: ambiguous/scattered queries short-circuit to `generate_clarification` and return `finish=clarify` with `available_subspaces: ["cheque","facilities_person","facilities_legal","general"]`. Sticky is kept in `StateGraph(RAGState, MemorySaver)` checkpoint keyed by `X-Request-ID`.

---

## Repository Composition

| Path | Repository | Responsibility | Default Branch | Pin (2026-10-12) |
|------|------------|----------------|----------------|-------------------|
| `components/server-setup` | [Work_RAG-Server-Setup](https://github.com/AliNikkhah2001/Work_RAG-Server-Setup) | Hardware, LLM manager `:9000`, embed `:8001-8003`, infra | `main` | `d615f66` |
| `components/knowledgebase` | [Work_RAG-KB](https://github.com/AliNikkhah2001/Work_RAG-KB) | Ingestion, `folder_hierarchy` tagging, `filter_path`, `supplement` (entity lists), retrieval | `master` | `d040c63` |
| `components/guardrails` | [Work_RAG-Guardrails](https://github.com/AliNikkhah2001/Work_RAG-Guardrails) | Persian policy, HurtLex allowlist 19 lemmas, guarded Gemma `:8200` | `main` | `c3c7476` |
| `components/orchestrator` | [Work_RAG-Orchestrator](https://github.com/AliNikkhah2001/Work_RAG-Orchestrator) | LangGraph + sticky + `filter_path` + `evidence 0.15` + supplemental tool, public API `:8100` | `main` | `14c5f97` |
| `components/tracing` | parent (not submodule) | Fallback collector `:3000`, `observability.db`, `/dashboard/observability` | — | — |

Each gitlink is pinned to an exact commit. Updating a component requires a component-repo commit followed by a parent-repo commit that advances the gitlink.

> **Note:** Run `git submodule status --recursive` for current pins (Vast) or `git submodule status` for H200.

```bash
git submodule status --recursive
```

---

## Request Lifecycle

1. **WebUI filter** (`components/openwebui-filters/rag_trace_capture.py`) — captures `filter_path` from `UserValves.scope` or `[چک]` prefix, injects `X-Request-ID`, records trace start.
2. **Orchestrator `validate_input`** — Guardrails input rails; short-circuit refusal.
3. **`classify` + `infer_specification`** — LLM judge (`GuardrailsClient` via `:8200` or `:9000`) classifies `greeting/spec/question`; maps query to `applied_subspace` via `subspace_map` (`cheque` ↔ `گزارش اعتباری چک` …) and `general` exempt.
4. **`should_clarify?`** — if scattered (low max score, multi-subspace hit, `threshold 0.8`) and not `general` → `generate_clarification` returns `finish=clarify` with pills, **no KB call**.
5. **`retrieve`** — `POST /search/api` with `query` (rewritten), `top_k=20`, `filter_path` (explicit or sticky `applied_subspace`). KB returns `SearchSteps` + `injected_entities` (cos>0.6). Parallel `POST /search/supplement` (`threshold 0.4`) for entity lists.
6. **`build_context`** — `MAX_CHUNKS=20` (`v13` up from `5`), `MAX_CONTEXT_CHARS=9000` (`6000` before), evidence guard `0.15` — if `top rerank <0.15` → abstain.
7. **`guarded_generate`** — `Guardrails :8200 → Gemma :18000` (`chat_template_kwargs enable_thinking:false`, `--no-mmproj --jinja`).
8. **`format_response`** — citations, `rag.supplemental`, grounded `follow_ups`, DLQ on failure, latency `stage_timing_ms`.
9. **Observability** — async `POST /api/observability/traces` to `:3000` + Langfuse `:3001`; DLQ `/tmp/dlq_retrieval.jsonl` on empty filtered.

**Excluded:** long-term memory beyond `MemorySaver` thread, Kubernetes, GraphRAG, agent loops besides clarify.

---

## Quick Start

### Vast.ai (Host Venvs — Docker Unprivileged, RTX 3090)

```bash
# 1. Clone with submodules
git clone --recurse-submodules https://github.com/AliNikkhah2001/Work_Credit-RAG_Phase1.git
cd Work_Credit-RAG_Phase1
git switch main
git submodule sync --recursive && git submodule update --init --recursive

# 2. Full startup (postgres → Gemma → KB → guardrails → collector → orchestrator → WebUI)
bash deploy/vast/start.sh

# 3. Health check
bash deploy/vast/health.sh
# or: for p in 18000 8000 8200 8100 3000 9000 13000; do printf "$p: "; curl -s http://127.0.0.1:$p/health | head -c 120; echo; done

# 4. Access via SSH tunnel
ssh -p <ssh_port> root@<ssh_host> \
  -L 13000:localhost:13000 -L 8100:localhost:8100 \
  -L 3000:localhost:3000 -L 3001:localhost:3001 -L 2024:localhost:2024
# Open http://localhost:13000 (WebUI → ICS Helper)
# Open http://localhost:3001 (Langfuse, admin@local.test / Langfuse-Admin-139b81ba)
# Open http://localhost:3000/dashboard/observability (unified trace dashboard)
# Open http://localhost:3000/observe (legacy timeline)
```

### H200 Host (Manager `:9000`)

```bash
# LLM manager (self-hosted OpenRouter analog) + 5× Gemma backends 8080-84 + embed 8001-8003
# is managed by Work_RAG-Server-Setup; Orchestrator points GUARDRAILS at :9000 there.
# See Work_RAG-Server-Setup/README.md and AGENTS.md §1 for H200 bring-up.
```

### Docker (Privileged Host Only)

```bash
cd deploy/docker
cp .env.example .env   # Set MODEL_FILE to your Gemma GGUF path
docker compose up -d --build
# WebUI at http://<host>:13000
```

## Tester Accounts

> **WebUI (ICS Helper, NOT Arena):** `http://127.0.0.1:13000` — select **ICS Helper** at top of chat (Arena is disabled).
> **Dashboard:** `http://127.0.0.1:3000/dashboard/observability` — 8-stage formatted traces (chunk cards BOTH/CE/RRF, guardrail badges, score bars), evaluations, pipeline inspector, export (JSONL/CSV).
> Full list also in [`tester-credentials.md`](tester-credentials.md).

| # | Username (email) | Password | Display name (obviously fake — not real personnel) |
|---|------------------|----------|--------------------------------------------------|
| 01 | `tester01@ics.local` | `Tester2024!` | TestAccount_01 |
| 02 | `tester02@ics.local` | `Tester2024!` | TestAccount_02 |
| 03 | `tester03@ics.local` | `Tester2024!` | DemoTester_03 |
| 04 | `tester04@ics.local` | `Tester2024!` | DemoTester_04 |
| 05 | `tester05@ics.local` | `Tester2024!` | EvalUser_05 |
| 06 | `tester06@ics.local` | `Tester2024!` | EvalUser_06 |
| 07 | `tester07@ics.local` | `Tester2024!` | QA_Fake_07 |
| 08 | `tester08@ics.local` | `Tester2024!` | QA_Fake_08 |
| 09 | `tester09@ics.local` | `Tester2024!` | Dummy_09 |
| 10 | `tester10@ics.local` | `Tester2024!` | Dummy_10 |
| 11 | `tester11@ics.local` | `Tester2024!` | MockAccount_11 |
| 12 | `tester12@ics.local` | `Tester2024!` | MockAccount_12 |
| 13 | `tester13@ics.local` | `Tester2024!` | SampleTest_13 |
| 14 | `tester14@ics.local` | `Tester2024!` | SampleTest_14 |
| 15 | `tester15@ics.local` | `Tester2024!` | Placeholder_15 |
| 16 | `tester16@ics.local` | `Tester2024!` | Placeholder_16 |
| 17 | `tester17@ics.local` | `Tester2024!` | SimUser_17 |
| 18 | `tester18@ics.local` | `Tester2024!` | SimUser_18 |
| 19 | `tester19@ics.local` | `Tester2024!` | Synthetic_19 |
| 20 | `tester20@ics.local` | `Tester2024!` | Synthetic_20 |

- **Admin:** `admin@localhost` / `admin` — has Users/Functions/Models management. Login currently goes to admin ( `WEBUI_AUTH=false` — direct chat without forced login; set `WEBUI_AUTH=true` to force a login redirect, then `testerNN@ics.local` gets its own `user_id` so ratings show the distinct evaluator). Change passwords via **Settings → Profile → Change Password**.
- **Buttons on each ICS helper reply:** **Star Rating** (1–5 ★) · **Report Problem** (6 categories `inaccurate/incomplete/hallucination/wrong_source/off_topic/other` via `/report …`) · **Retrieved Content** (full KB chunks with source badges) · **Ground Truth** (`/truth The correct answer is …` stores `[GROUND_TRUTH]`).
- **Persistence:** Chats are in `webui.db`; traces/evaluations are in a separate `observability.db` (`docker-data/volumes/docker_trace-data/_data` + `/tmp/langfuse_traces.jsonl`) with `created_at` timestamps, `request_id`, `retrieved_chunks`, `stage_timing`, `user_id` — **deleting a chat in WebUI does NOT delete its traces/evaluations** (verified: delete → traces/evaluations counts unchanged, full retrieval+generation log remains).
- See [`tester-credentials.md`](tester-credentials.md) for the full file with login, dashboard, and persistence notes.

---

## Models

| Role | Model | Version | Size | Key Config |
|------|-------|---------|------|------------|
| **Generation** | Gemma 4 31B Instruct | `unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL` | 18.8 GiB | `--no-mmproj --jinja --ctx-size 8192 --temp 0.2` + `chat_template_kwargs:{"enable_thinking":false}` |
| **Embedding** | paraphrase-multilingual-MiniLM-L12-v2 | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 384-dim | `KB_EMBED_DEVICE=cpu/cuda` (`dim 384`) |
| **Reranker** | BGE-m3 `BAAI/bge-reranker-v2-m3` (default) / MiniLM fallback | `BAAI/bge-reranker-v2-m3` (568M) vs `mmarco-mMiniLMv2-L12-H384-v1` (118M) | 2.27 GB / 118M | `KB_RERANK_POOL=15` (CPU) `30` (GPU), `KB_RERANKER_DEVICE=cpu/cuda` |
| **Guardrails** | Ghadeer mmBERT (toxicity/hate/intent) | — | — | F1 0.94 Persian, thresholds: toxicity 0.80, hate 0.80, PII 0.90, injection 0.85 |
| **Judge (bench)** | gemma-4-31b | via `:9000` (fallback `:8100` `:18000`) | — | RAGAS `ragas_eval.py` LLM-as-judge |

**Model Cards:** See [AGENTS.md](AGENTS.md) §1–2 for the service and model table. Default reranker is `BAAI/bge-reranker-v2-m3` (MRR `0.496` on 800 Persian Q, `pool15`); MiniLM is lightweight fallback (`MRR 0.493`).

---

## Configuration

### Key Environment Variables (current `v13` + bench)

| Component | Variable | Default | Production (Vast) | Notes |
|-----------|----------|---------|------------|---|
| **Gemma** | `MODEL` | — | `/tmp/hf_clean/.../gemma-4-31B-it-UD-Q4_K_XL.gguf` | H200 uses manager `:9000` |
| | `CTX_SIZE` | 8192 | 8192 (4096 if OOM) | Gemma |
| **KB** | `KB_DB_URL` | `sqlite+aiosqlite:///./data/kb_test.db` | `postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/kb_manager` | `mode=pgvector` → HNSW |
| | `KB_WEB_PORT` | 8000 | 8000 | |
| | `KB_EMBED_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | same | 384-d |
| | `KB_RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | same | or `mmarco-mMiniLMv2-L12-H384-v1` |
| | `KB_RERANK_POOL` | 15 | 15 (CPU) / 30 (GPU) | |
| | `KB_KEYWORD_BOOST` | 3.0 | 3.0 | BM25 keyword ×3 |
| **Guardrails** | `GUARDRAILS_PORT` | 8200 | 8200 | |
| | `UPSTREAM_LLM_BASE_URL` | `http://127.0.0.1:9000/v1` | `http://127.0.0.1:18000/v1` (alias `LLM_BASE_URL`) | Vast bare |
| | `UPSTREAM_LLM_MODEL` | `gemma-4-31b` | `unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL` | |
| **Orchestrator** | `KB_BASE_URL` | `http://127.0.0.1:8000` | same | `kb_search_url = {KB}/search/api` |
| | `GUARDRAILS_BASE_URL` | `http://127.0.0.1:8200` | same | |
| | `LANGFUSE_HOST` | `http://127.0.0.1:3000` | `http://127.0.0.1:3001` | `TRACE_ENABLED=true` |
| | `retrieval_top_k` | 20 | 20 | up from `5` (MVP) |
| | `subspace_map` | `cheque:گزارش اعتباری چک` | same | + `facilities_person/legal`/`general` |
| | `subspace_threshold` | 0.8 | 0.8 | clarify gate |
| | `evidence_min_score` | 0.15 | 0.15 | hallucination guard (G5) |
| | `response_detail` | `production` | `production` | hides GT block |
| | `MAX_CHUNKS` / `MAX_CONTEXT` | 20 / 9000 | 20 / 9000 | up from `5 / 6000` |
| **WebUI** | `OPENAI_API_BASE_URL` | — | `http://127.0.0.1:8100/v1` | ICS Helper |
| | `WEBUI_AUTH` | `false` | `false` | `true` for per-user `user_id` |

**Full reference:** See [AGENTS.md](AGENTS.md) §1–4 and `components/orchestrator/src/work_rag_orchestrator/config.py`.

---

## Observability

| Tool | URL | Purpose |
|------|-----|---------|
| **Unified Dashboard** | `http://localhost:3000/dashboard/observability` (via tunnel) | 8-stage chunk cards (BOTH/CE/RRF), guardrail badges, `applied_subspace` badge, clarifying state, export JSONL/CSV |
| **Langfuse v2** | `http://localhost:3001` | Full trace UI, Postgres+ClickHouse. Keys in `/tmp/opencode/langfuse.env` |
| **Fallback Collector** | `http://localhost:3000` | `POST /api/observability/traces` → `observability.db` (SQLite) + JSONL `/tmp/langfuse_traces.jsonl` |
| **Local Timeline** | `http://localhost:3000/observe` | Request list → timeline (request → validate → classify → infer → retrieve → generate → format) |
| **Graph Debugger** | `http://localhost:3000/studio` | Drives `:2024` server-side, shows state + observe link |
| **LangGraph Studio** | `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024` | Visual debugger (`-L 2024:localhost:2024`) |
| **Bench Artifacts** | `evaluation/artifacts/` | `bench_results_latest.json` · `ragas_results_latest.json` · `bench_report_latest.html` |

**CLI:**
```bash
# Unified dashboard API
curl -s 'http://127.0.0.1:3000/api/observability/traces?limit=3' | jq .
curl -s 'http://127.0.0.1:3000/api/observability/pipeline/{request_id}' | jq .

# Legacy observe CLI
python components/tracing/observe.py --list --limit 10
python components/tracing/observe.py --request <request_id> --json

# Bench repro (multi-agent, 391s, 41 turns)
PYTHONPATH=".:components/orchestrator:$PYTHONPATH" python3 -m evaluation.bench_runner
PYTHONPATH=".:components/orchestrator:$PYTHONPATH" python3 -m evaluation.ragas_eval --input evaluation/artifacts/bench_results_latest.json
PYTHONPATH=".:components/orchestrator:$PYTHONPATH" python3 -m evaluation.report --bench evaluation/artifacts/bench_results_latest.json --ragas evaluation/artifacts/ragas_results_latest.json
```

> **End-to-end testing (filter_path + clarifying):** see [`components/knowledgebase/kb-manager/README.md` → Testing on Open WebUI](components/knowledgebase/kb-manager/README.md#testing-on-open-webui--end-to-end-rag--filter_path--clarifying) — KB tester `:8000/search`, WebUI scope picker + `rag_trace_capture` filter (`filter_path`), and sticky clarifying (`cheque` / `facilities_person` / `facilities_legal`).

---

## Knowledge Subspaces & Filtering

```mermaid
flowchart LR
    subgraph KBTree["KB Tree — folder_hierarchy (4 subspaces)"]
        Root["پایگاه دانش"]
        Root --> Cheque["گزارش اعتباری چک\n(cheque)"]
        Root --> FP["اشخاص حقیقی / اعتبارسنجی تسهیلات\n(facilities_person)"]
        Root --> FL["اشخاص حقوقی / اعتبارسنجی تسهیلات\n(facilities_legal)"]
        Root --> Gen["پایگاه دانش عمومی\n(general)"]
    end

    WebUI -- "filter_path" --> KB
    KB -- "chunk.doc_metadata.folder_hierarchy" --> Filter
    Filter -- "only that sub-tree" --> RRF
```

- **Ingestion:** `kb-source/1405-07-06/…` path parsed → `doc_metadata.folder_hierarchy: list[str]` per chunk (`components/knowledgebase/kb-manager/kb_manager/models/database.py`).
- **Query:** `POST /search/api {filter_path}` — if contains `/` matches `"/".join(folder_hierarchy)` else membership; cache key includes `filter_path`.
- **Sticky:** `filter_path` = `subspace_map[applied_subspace]` persists via `X-Request-ID` thread until re-spec (`چک` → `cheque`); `general` is exempt from clarify gate.
- **Tracer:** `audit.applied_subspace` + `filter_path` badge on `dashboard/observability`.

## Supplementary Data (`ضمیمه پایگاه دانش`)

Not all knowledge suits Dense vectors (bank lists, reason codes `DCB3-3`, shareholder tables):

- **System configs (`واژگان معادل.xlsx`):** BM25 synonyms via `query_expansion`.
- **Guardrails (`سوالات نامربوط.xlsx`):** excluded from RAG.
- **Entity Lists (5):** JSON + MiniLM embedding of `description` cached. During `search`, if `cos(query, description) > 0.6` → `injected_entities` (whole JSON injected); tool `POST /search/supplement` uses `0.4` threshold. Returned as `rag.supplemental` in response.

See `docs/benchmark-report-2026-10-12.md` §7 and `data/supplementary_architecture.md`.

---

## Evaluation

### 🧪 Multi-Agent Conversational Benchmark — 2026-10-12 (NEW)

> **41 turns** (12 multi-turn convs · 29 turns + 12 single baselines) across **4 subspaces** — multi-agent suite with RAGAS (`faithfulness`, `answer_relevancy`, `context_relevancy`, `context_recall`, `hallucination`, `ambiguity_resolution`, `sticky_persistence`, `retrieval_hit`) + LLM judge `gemma-4-31b` via `:9000`. See **[docs/benchmark-report-2026-10-12.md](docs/benchmark-report-2026-10-12.md)** for the full report with samples, explanations, tables, and Mermaid plots.

| Metric | Score | Verdict |
|---|---:|---|
| faithfulness | 0.644 | Moderate — abstains correctly but 2 cases suppressed valid context |
| answer_relevancy | 0.212 | Low — topic-selection turns judged irrelevant |
| context_relevancy | 0.078 | Very low — many 0-chunk greetings |
| **non_hallucination** | **0.805** | **Good — G5 fake grade never hallucinated** |
| ambiguity_resolution | 0.854* | *0/6 scattered fails hidden by trivial passes |
| sticky_persistence | 0.610 | Fragile — re-spec ok, sticky follow-ups drop |
| retrieval_hit | 0.537 | general 0.600 > cheque 0.111 |

| Subspace | n | faith | hit | sticky | p50 |
|---|---:|---:|---:|---:|---:|
| cheque | 9 | 0.556 | **0.111** | 0.444 | 10741 ms |
| facilities_person | 6 | 0.833 | 0.167 | 0.500 | 7130 ms |
| facilities_legal | 3 | **0.933** | 0.333 | 0.667 | 11150 ms |
| general | 10 | 0.660 | **0.600** | 0.300 | 8006 ms |

Latency `p50 8006ms` — `retrieve 1681ms` vs `guarded_generate 5381ms` (65% generation-bound). **Key fixes:** `0/6` scattered should clarify, cheque `evidence_min_score 0.15` starves `0.028` hits, sticky drops on generic follow-ups. Repro: `PYTHONPATH=".:components/orchestrator:$PYTHONPATH" python3 -m evaluation.bench_runner && python3 -m evaluation.ragas_eval --input evaluation/artifacts/bench_results_latest.json && python3 -m evaluation.report --bench evaluation/artifacts/bench_results_latest.json --ragas evaluation/artifacts/ragas_results_latest.json` → artfacts in `evaluation/artifacts/`.

### Retrieval quality (legacy, 800 Q, v8 6593 chunks)

Wave-1 full-800 reranker shootout, CPU (2026-09-12/13). Dataset: 800 Persian QA, answer-grounded golds remapped to live PG KB (threshold 0.6, 772/800 covered, ~7 gold/query), `top_k=5`.

| Backbone | Pool | Hit@5 | Top-1 | MRR | s/q (CPU) |
|---|---|---|---|---|---|
| **BGE-m3 `BAAI/bge-reranker-v2-m3` (default)** | 15 | 0.536 | 0.474 | **0.496** | ~5–15 |
| MiniLM `mmarco-mMiniLMv2-L12-H384-v1` (fallback) | 15 | 0.536 | 0.469 | 0.493 | 3.9 |
| MiniLM | 30 | 0.538 | — | 0.495 | 7.4 |
| BGE-m3 | 30 | 0.536 | 0.474 | 0.496 | 52 |

Full method: `archive/migration-history/WAVE2_GPU_RUNBOOK.md`. Historical per-version tables archived.

### Cross-Encoder Direct API (2026-09-15, 20 Q, v8)

| Model | Params | Loader | Avg Rerank | Status |
|---|---|---|---|---|
| **mmarco** | 118M | crossencoder | 628 ms | ✅ Production |
| **bge-reranker-v2-m3** | 568M | crossencoder | 3,754 ms | ⚠️ 6× slower (GPU 1.6×) |
| bge-gemma / Qwen3-0.6B | 2.5B/0.6B | flag-llm | 30–43s | ❌ CPU too slow |

### RAG End-to-End (120 Q) & LLM-as-Judge

| Metric | Result |
|--------|--------|
| 20 diverse samples | 20/20 ok |
| 120 guardrail checks (in+out) | 0 blocked |
| LLM-as-Judge (v4 Q8) | cosine 0.620 / pass 45% / faith 3.65 / cit 4.95 |

**Full details:** [docs/evaluation.md](docs/evaluation.md) · [docs/benchmark-report-2026-10-12.md](docs/benchmark-report-2026-10-12.md)

---

## Archive

| Archive path | Content | Original |
|--------------|---------|----------|
| `archive/handoff-sessions/` | 36 session transcripts | `handoff/`, `docs/SESSION_WAVE1_HANDOFF.md` |
| `archive/benchmark-history/` | `docs/benchmark-report/` GH Pages | `docs/benchmark-report/` (now `.gitignore`) |
| `archive/migration-history/` | `VAST_GEMMA4_MIGRATION.md`, `WAVE2_GPU_RUNBOOK.md` | `docs/` |

---

## Done vs Pending

### Done ✓ (2026-10-12)

- [x] **KB v13** `1405-07-06` · 18 docs / 1123 chunks · `folder_hierarchy` + `filter_path` + `supplement` tool (cos 0.4/0.6) · pgvector HNSW
- [x] **Orchestrator** LangGraph conditional clarify (`should_clarify` → `generate_clarification`), sticky `MemorySaver` (`X-Request-ID`), `MAX_CHUNKS=20/9000`, `evidence 0.15` G5 guard, grounded `follow_ups`, DLQ
- [x] **Guardrails** `:8200` Persian rails, HurtLex 19 lemmas, `enable_thinking:false` / `--no-mmproj --jinja` clean Persian
- [x] **Generation** Gemma 4 31B `UD-Q4_K_XL` via `:18000` (Vast) / `:9000` manager (H200) · embed trio `:8001-8003`
- [x] **WebUI** `:13000` ICS Helper (Arena OFF) · `rag_trace_capture` filter + 4 actions (`rate`/`report`/`view`/`truth`) · `WEBUI_AUTH=false` direct, `true` for per-user `user_id`
- [x] **Observability** `:3000/dashboard/observability` (unified `observability.db` chunk cards, subspace badge, export) + Langfuse `:3001` + Studio `:2024`
- [x] **Benchmark** multi-agent conversational `41` turns · RAGAS per-subspace · `d1c9b33` · `docs/benchmark-report-2026-10-12.md`
- [x] **Pins** `main` `d1c9b33` (+ submodules `c3c7476`/`d040c63`/`14c5f97`/`d615f66`)

### Pending ⏳

- [ ] **Clarify gate** `0/6` scattered fail — lower `subspace_threshold` / explicit `ambiguous` classifier
- [ ] **Evidence threshold per subspace** — cheque `0.028` vs `0.15` → empty; per-subspace tuning
- [ ] **Sticky carry** — generic follow-ups lose `applied_subspace`; carry `filter_path` from previous turn
- [ ] **Generation faith** — 2 abstains despite `ctx_rel 1.0`; citation-gate too strict
- [ ] **Latency** — `generate 5.3s` dominates; batch Gemma / reranker on GPU (1.6×)
- [ ] **Supervision** — `llama-server` `nohup` → supervisor; Docker privileged vs host-venv split

---

## Verification

```bash
# Health
for p in 18000 8000 8200 8100 3000 9000 13000; do printf "%s: " "$p"; curl -s http://127.0.0.1:$p/health | head -c 100; echo; done

# Gemma clean (no <unused*>)
curl -s http://127.0.0.1:18000/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL","messages":[{"role":"user","content":"سلام"}],"chat_template_kwargs":{"enable_thinking":false}}' \
  | python3 -c "import json,sys; print('<unused' not in json.load(sys.stdin)['choices'][0]['message']['content'])"

# RAG E2E (sticky + filter_path)
curl -s http://127.0.0.1:8100/v1/chat/completions -H 'Content-Type: application/json' -H 'X-Request-ID: test-001' \
  -d '{"model":"ics-helper-agent","messages":[{"role":"user","content":"چک"}],"filter_path":"گزارش اعتباری چک"}' | jq '.audit.applied_subspace'
curl -s http://127.0.0.1:8100/v1/chat/completions -H 'Content-Type: application/json' -H 'X-Request-ID: test-001' \
  -d '{"model":"ics-helper-agent","messages":[{"role":"user","content":"تاثیر چک برگشتی بر امتیاز چقدر است؟"}]}' | jq '.choices[0].finish_reason, .rag.citations|length'

# KB filtered vs supplement
curl -s http://127.0.0.1:8000/search/api -H 'Content-Type: application/json' -d '{"query":"سهامداران","top_k":5}' | jq '.injected_entities|length'
curl -s http://127.0.0.1:8000/search/supplement -H 'Content-Type: application/json' -d '{"query":"سهامداران","threshold":0.4}' | jq '.results|length'

# Observe / bench
curl -s 'http://127.0.0.1:3000/api/observability/traces?limit=1' | jq .
python components/tracing/observe.py --list --limit 3
PYTHONPATH=".:components/orchestrator:$PYTHONPATH" python3 -m evaluation.bench_runner --dry-run
```

---

## Updating a Submodule

```bash
cd components/orchestrator
git switch main && git pull --ff-only
cd ../..
git add components/orchestrator
git commit -m "chore: advance orchestrator submodule"
```

Always run health + `evaluation/bench_runner --dry-run` before advancing a production pin.

---

## License

See [LICENSE](LICENSE). Each submodule may also declare its own license and dependency obligations.

---

## Links

- **Runbook:** [AGENTS.md](AGENTS.md) §2–3 + `deploy/vast/start.sh` + `deploy/vast/health.sh`
- **Bench report (NEW):** [docs/benchmark-report-2026-10-12.md](docs/benchmark-report-2026-10-12.md) (also `evaluation/artifacts/bench_report_latest.html`)
- **Migration log:** [archive/migration-history/VAST_GEMMA4_MIGRATION.md](archive/migration-history/VAST_GEMMA4_MIGRATION.md)
- **Compose:** [compose.mvp.yml](compose.mvp.yml) + [deploy/docker/docker-compose.yml](deploy/docker/docker-compose.yml)
- **Guardrails allowlist:** `components/guardrails/kb/hurtlex_allowlist.json`
- **Evaluation docs:** [docs/evaluation.md](docs/evaluation.md) · [docs/cross_encoder_benchmark_results.md](docs/cross_encoder_benchmark_results.md)

## 🚀 Production Scaling (1 Million+ Users)

For millions of concurrent users, Python FastAPI + `RankBM25` + CrossEncoder CPU become bottlenecks. Million-User plan replaces `RankBM25` with SPLADE, moves ML to Triton+TensorRT, introduces semantic cache.

See: 👉 [**Million-User Scale Plan**](million-user-scale-plan.md)
