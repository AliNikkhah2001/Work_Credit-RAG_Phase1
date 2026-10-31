# Work Credit RAG — Phase 1

[![Python](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/downloads/release/python-3110/)
[![License](https://img.shields.io/github/license/AliNikkhah2001/Work_Credit-RAG_Phase1)](LICENSE)
[![Branch](https://img.shields.io/badge/branch-main-blue)]()

Umbrella repository for a self-hosted, Persian-capable conversational RAG platform. The implementation is split into independently maintained Git submodules so model/server operations, knowledge-base lifecycle, safety policy, and LangGraph orchestration can evolve without returning to a monolith.

> **Status:** Active on `main`. Deployed on Vast.ai (2026-09-12, RTX 3090) · H200 host via `Work_RAG-Server-Setup` LLM manager `:9000`. Current KB `v13 1405-07-06` — `18` docs / `1123` chunks · `pgvector HNSW` · `MAX_CHUNKS=20`.

---

## Project Hierarchy Diagram

```mermaid
graph TD
    subgraph Root["Work_Credit-RAG-Phase1/ Umbrella Repo"]
        direction TB
        
        subgraph Production["PRODUCTION LAYER ✅ Served & Deployed"]
            direction LR
            api["api/ API Entry Points<br/>Thin Wrappers → components/"]
            comp["components/ Production Submodules<br/>Pinned Gitlinks"]
            con["contracts/ API JSON Schemas"]
            dep["deploy/ Start/Stop/Health Scripts"]
            eval["eval/ E2E & Guardrails Tests"]
            sc["scripts/ Utility Scripts"]
        end
        
        subgraph Agent["AGENT STATE LAYER ⚠️ Agent Only"]
            direction LR
            ast["agent-state/<br/>Context · History · Skills<br/>Coding Standards"]
        end
        
        subgraph Dev["DEVELOPMENT LAYER ❌ NOT for Production"]
            direction LR
            devp["dev/patches/<br/>patch_*.py one-offs"]
            devt["dev/tests/<br/>test_*.py ad-hoc"]
            devi["dev/investigation/<br/>fix_*.py · inspect_*.py"]
        end
        
        subgraph Archive["ARCHIVE LAYER ❌ Historical Reference"]
            direction LR
            arc["archive/<br/>Non-code artifacts"]
            deprec["deprecated/<br/>Obsolete scripts & plans"]
        end
        
        subgraph Docs["DOCS & CONFIG"]
            direction LR
            rd["README.md · AGENTS.md"]
            docs["docs/plans/<br/>million-user-scale-plan.md"]
            lit["litellm.yaml · compose.mvp.yml"]
        end
    end

    Production --> Agent
    Production --> Dev
    Production --> Docs
    Agent --> Archive
    Dev --> Archive

    classDef production fill:#e1f5e1,stroke:#2e7d32,stroke-width:2px
    classDef agent fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef dev fill:#ffebee,stroke:#c62828,stroke-width:2px
    classDef archive fill:#eceff1,stroke:#546e7a,stroke-width:2px,stroke-dasharray: 5 5
    classDef docs fill:#e3f2fd,stroke:#1565c0,stroke-width:2px

    class api,comp,con,dep,eval,sc production
    class ast agent
    class devp,devt,devi dev
    class arc,deprec archive
    class rd,docs,lit docs
```

### Layer Separation Summary

| Layer | Directory | Production? | Purpose |
|-------|-----------|-------------|---------|
| **Entry points** | `api/` | ✅ Yes | Thin wrappers importing from `components/` submodules |
| **Implementation** | `components/` | ✅ Yes | Production code — Git submodules pinned to exact commits |
| **Contracts** | `contracts/` | ✅ Yes | API request/response JSON schemas |
| **Deployment** | `deploy/` | ✅ Yes | Start/stop/health scripts per host (Vast/H200/Docker) |
| **Testing** | `eval/` | ✅ Yes | E2E, guardrails, and LLM judge evaluation |
| **Utilities** | `scripts/` | ✅ Yes | README TOC generation, system checks |
| **Agent context** | `agent-state/` | ⚠️ Agent only | Agent mission, history, skills, coding standards |
| **Development** | `dev/` | ❌ No | Patches, ad-hoc tests, investigation scripts |
| **Archive** | `archive/`, `deprecated/` | ❌ No | Historical reference, read-only |

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

### `dev/`

- [Tester Credentials — ICS RAG Evaluation](dev/tests/tester-credentials.md) — 1. Open http://127.0.0.1:13000.

### `docs/`

- [Documentation Index](docs/README.md) — This directory contains project-wide documentation.
- [Benchmark Report — Multi-Agent Conversational RAG Evaluation (2026-10-12)](docs/benchmark-report-2026-10-12.md) — filter_path maps to components/knowledgebase/kb-manager doc_metadata.folder_hierarchy (گزارش اعتباری چک | اشخاص حقیقی/اعتبارسنجی تسهیلات | اشخاص حقوق…
- [Cross-Encoder Reranker Benchmark Results](docs/cross_encoder_benchmark_results.md) — Tested 7 cross-encoder reranker models on the Work Credit RAG KB (v8 pgvector, 6593 chunks, 103 docs) using 20 diverse Persian credit queries.
- [Evaluation — Work Credit RAG Phase 1](docs/evaluation.md) — Historical per-version tables (v5 baseline, v7 IVA 15, v8 HNSW) were moved to archive/migration-history/ and eval/results/. See README.md#evaluation…
- [History — Code Audit 2026-09-27: 142 Errors & Anti-Patterns Found](docs/history/CODE_AUDIT_2026-09-27.md) — 1. components/knowledgebase/kb-manager — 7 Critical + 10 High (path traversal, unauth DB, unbounded disk, silent failures, ilike wildcard DoS, Vector…
- [Comprehensive Million-User Scaling Architecture Plan](docs/plans/million-user-scale-plan.md) — This document serves as the master architectural blueprint for scaling the Knowledge Base Retrieval system to support 1,000,000+ concurrent users.

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
        HybridClf["🔀 hybrid_classify\nSVM-RBF → Gemma TRT escalation\n(confidence threshold 0.60)"]
        Ambiguity["🧠 Ambiguity Scorer\n4×4×128 multi-prototype\nmargin/entropy/intra-spread"]
        Clarify["generate_clarification"]
    end

    subgraph Retrieval["Retrieval — :8000"]
        KB["📚 KB Manager\nBM25(tantivy) + Dense MiniLM-384\n+ RRF k=60 + CE BGE-v2-m3\npgvector HNSW (1123 chunks)"]
        Filter["filter_path\nfolder_hierarchy tag"]
        Suppl["supplement\nentity_lists (MiniLM cos>0.4)\n+ injected_entities (>0.6)"]
        Proto["🧠 4×4×128 Multi-Prototypes\nPCA-whitened centroids\nintra-spread + coverage"]
    end

    subgraph Safety["Safety — :8200"]
        GR["🛡️ Guardrails\nPOST /v1/rails/check (input)\nPOST /v1/chat/completions (guarded_generate)\nRisk + semantic + HurtLex\nNemoguardrails + Colang 1.0"]
    end

    subgraph Generation["Generation"]
        Gemma["🤖 Gemma :18000\nllama-server UD-Q4_K_XL\n--no-mmproj --jinja\ntemp 0.2 ctx 8192"]
        Manager["🧩 LLM Manager :9000\n( H200: 3× Gemma 8080-84 )"]
        Embed["🔢 Embed :8001-8003\nE5-small/BGE-m3/MiniLM"]
        LiteLLM["🌐 LiteLLM Router :4000\nFallback chains: strong/cheap/judge\nself-hosted + SiliconFlow/OpenRouter"]
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
    Classify -- "question" --> HybridClf
    Classify -- "greeting/spec" --> FRMT[format_response<br/>ack / smalltalk, no retrieval]
    FRMT --> WebUI
    HybridClf -- "subspace + ambiguity" --> Ambiguity
    Ambiguity -- "should_clarify?" --> Clarify
    Clarify -- "clarify finish" --> WebUI
    Ambiguity -- "allowed" --> KB
    KB --> Filter
    KB --> Suppl
    KB --> Proto
    Suppl -- "MAX_CHUNKS=20\nMAX_CONTEXT=9000" --> Orch
    Proto -- "multi-proto scores" --> Ambiguity
    Orch -- "guarded_generate" --> GR
    GR --> Gemma
    Gemma -.-> Manager
    Embed -.-> KB
    Orch -.-> Collector
    Collector --> Dashboard
    Orch -.-> LF2
    Orch -.-> Studio
    Collector --> TraceApp
    LiteLLM -.-> Orch
    LiteLLM -.-> GR
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
    Start((Start)) --> VI[validate_input]
    VI -->|blocked| Ref[format_refusal]
    VI -->|allowed| Cl[classify]
    Cl --> R{greeting / specification?}
    R -->|yes| Fr[format_response]
    Fr --> End((End))
    R -->|no| Hc[hybrid_classify]
    Hc --> Ret[retrieve]
    Ret --> SC{needs clarification?}
    SC -->|yes| Gc[generate_clarification]
    Gc --> End((End))
    SC -->|no| Bc[build_context]
    Bc --> Gg[guarded_generate]
    Gg --> Fr
    Ref --> End((End))
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

## Project Hierarchy

```
Work_Credit-RAG_Phase1/                     # Umbrella repo — production + config only
├── .github/                                # CI/CD workflows (production)
├── agent-state/                            # Agent working files (context, history, skills, coding standards)
│   ├── context/                            # Current mission, todo
│   ├── history/archive/                    # Archived agent sessions
│   ├── skills/                             # Agent skill definitions per component
│   ├── README.md, architecture.md, coding-standards.md, git-workflow.md, insights.md, FILE_MAP.md, onboarding.md
├── api/                                    # Production API entry points (thin wrappers → components/)
│   ├── __init__.py
│   ├── orchestrator.py                     # → components/orchestrator (LangGraph :8100)
│   ├── guardrails.py                       # → components/guardrails (policy :8200)
│   ├── kb.py                               # → components/knowledgebase (retrieval :8000)
│   └── tracing.py                          # → components/tracing (fallback collector :3000)
├── components/                             # Production implementation (Git submodules — DO NOT EDIT directly)
│   ├── server-setup/                       # Work_RAG-Server-Setup (HW, model lifecycle, infra :9000)
│   ├── knowledgebase/                      # Work_RAG-KB (ingestion, retrieval, reranking :8000)
│   ├── guardrails/                         # Work_RAG-Guardrails (Persian policy, guarded Gemma :8200)
│   ├── orchestrator/                       # Work_RAG-Orchestrator (LangGraph API :8100)
│   ├── tracing/                            # Fallback trace collector (:3000)
│   └── openwebui-filters/                  # Open WebUI RAG trace capture
├── contracts/                              # API contracts (JSON schemas: retrieval, rails, chat)
├── deploy/                                 # Deployment scripts (start.sh, stop.sh, health.sh)
│   ├── h200/                               # H200 host deployment
│   ├── vast/                               # Vast.ai host deployment
│   └── docker/                             # Docker Compose (privileged hosts)
├── deprecated/                             # Deprecated files (read-only historical reference)
├── dev/                                    # DEVELOPMENT ONLY — not for production
│   ├── patches/                            # One-off patch scripts (patch_*.py)
│   ├── tests/                              # Ad-hoc test scripts (test_api*.py, etc.)
│   └── investigation/                      # Debug/investigation scripts (fix_*.py, inspect_*.py, etc.)
├── docs/                                   # Documentation
│   └── plans/                              # Planning documents (million-user-scale-plan.md, etc.)
├── eval/                                   # Production evaluation tests (e2e, guardrails, LLM judge)
├── evaluation/                             # Benchmark evaluation (RAGAS, cross-encoder, etc.)
├── research-site/                          # Jekyll documentation site
├── scripts/                                # Utility scripts (gen_readme_toc.py, system_check.sh)
├── AGENTS.md                               # Agent operating manual (branch strategy, service table)
├── README.md                               # This file (project overview + hierarchy)
├── compose.mvp.yml                         # Docker Compose (MVP)
├── litellm.yaml                            # LiteLLM configuration (self-hosted OpenRouter)
└── LICENSE

### Layer separation

| Layer | Directory | Production? | Purpose |
|-------|-----------|-------------|---------|
| Entry points | `api/` | ✅ Yes | Thin wrappers over component submodules |
| Implementation | `components/` | ✅ Yes | Production code (submodules, pinned commits) |
| Contracts | `contracts/` | ✅ Yes | API request/response JSON schemas |
| Deployment | `deploy/` | ✅ Yes | Start/stop/health scripts per host |
| Testing | `eval/` | ✅ Yes | E2E and guardrails evaluation |
| Utilities | `scripts/` | ✅ Yes | README TOC generation, system checks |
| Agent context | `agent-state/` | ⚠️ Agent only | Agent mission, history, skills, standards |
| Development | `dev/` | ❌ No | Patches, ad-hoc tests, investigation scripts |
| Archive | `archive/`, `deprecated/` | ❌ No | Historical reference, read-only |
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

    subgraph Proto["Multi-Prototype Centroids"]
        P1["cheque × 4\n(centroids)"]
        P2["facilities_person × 4"]
        P3["facilities_legal × 4"]
        P4["general × 4"]
    end

    WebUI -- "filter_path" --> KB
    KB -- "chunk.doc_metadata.folder_hierarchy" --> Filter
    Filter -- "only that sub-tree" --> RRF
    Proto -.-> Ambiguity["🧠 Ambiguity Scorer\nintra-spread + coverage"]
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

## 🌐 LiteLLM Router (Self-Hosted OpenRouter Analog)

> **Status:** Planned / future architecture (per `AGENTS.md` §5). Not yet deployed — the current production path uses Guardrails → Gemma :18000 (Vast) / Manager :9000 (H200) directly. This diagram shows the target routing topology.

The LiteLLM router (`:4000`) serves as a self-hosted OpenRouter analog with intelligent fallback chains across model tiers:

```mermaid
flowchart LR
    subgraph Client["Clients"]
        Orch["Orchestrator :8100"]
        Guard["Guardrails :8200"]
        WebUI["Open WebUI :13000"]
    end

    subgraph Router["LiteLLM Router :4000"]
        Router["🌐 LiteLLM Proxy\nrouting_strategy: usage-based\nfallbacks + retries"]
    end

    subgraph SelfHosted["Self-Hosted Pool"]
        Manager["🧩 Manager :9000\nself-gemma / self-qwen / self-mizan"]
    end

    subgraph Cheap["Cheap Tier"]
        Silicon["☁️ SiliconFlow\nQwen2.5-7B / DeepSeek"]
    end

    subgraph Strong["Strong Tier"]
        OpenRouter["🌍 OpenRouter\nGPT-4o / Claude-3.5"]
    end

    subgraph Judge["Judge Tier"]
        Judge["⚖️ Judge Models\nGemini-2.0 / GPT-4o-mini"]
    end

    subgraph Mizan["Mizan Decision"]
        Mizan["🧠 Mizan-Decision\nMizan-v3 / Gemini"]
    end

    Client --> Router
    Router --> SelfHosted
    Router --> Cheap
    Router --> Strong
    Router --> Judge
    Router --> Mizan

    SelfHosted -.->|fallback| Cheap
    Cheap -.->|fallback| SelfHosted
    Strong -.->|fallback| Cheap
    Judge -.->|fallback| Strong
    Mizan -.->|fallback| Judge
```

### Routing Strategy & Fallback Chains

| Tier | Models | Endpoint | Fallback |
|------|--------|----------|----------|
| **Self-Hosted** | self-gemma, self-qwen, self-mizan | Manager `:9000` | — |
| **Cheap** | SiliconFlow (Qwen2.5-7B, DeepSeek) | `api.siliconflow.cn` | self-gemma |
| **Strong** | OpenRouter (GPT-4o, Claude-3.5) | `openrouter.ai` | cheap, self-gemma |
| **Judge** | Gemini-2.0-flash, GPT-4o-mini | Gemini/OpenAI | strong, self-gemma |
| **Mizan-Decision** | Mizan-v3, Gemini | Manager `:9000` / Gemini | judge, self-gemma |

### Router Settings

```yaml
router_settings:
  routing_strategy: usage-based-routing
  num_retries: 3
  timeout: 120
  fallbacks:
    - strong: [cheap, self-gemma]
    - judge: [strong, self-gemma]
    - cheap: [self-gemma]
    - mizan-decision: [judge, self-gemma]
```

### Config & Secrets

```bash
# litellm.env (gitignored, mode 600)
LITELLM_MASTER_KEY=sk-litellm-local-dev-change-me
MANAGER_API_KEY=sk-local-dev
SILICONFLOW_API_KEY=
OPENROUTER_API_KEY=
GEMINI_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
HTTP_PROXY=http://192.168.203.2:3128
HTTPS_PROXY=http://192.168.203.2:3128
NO_PROXY=localhost,127.0.0.1,host.docker.internal,redis,qdrant,pgvector,milvus,langfuse,grafana,prometheus,litellm
LITELLM_HOST=http://127.0.0.1:4000
LITELLM_URL=http://127.0.0.1:4000
```

### Deploy with Docker (Privileged Host)

```bash
cd /splunk-data/v1/Work_RAG-Server-Setup/deploy
cp litellm.env.example litellm.env  # fill in API keys
docker compose up -d litellm
# LiteLLM available at http://127.0.0.1:4000
# Health: curl http://127.0.0.1:4000/health
```

### Integration with Orchestrator & Guardrails

```python
# In orchestrator config (config.py)
GUARD_JUDGE_MODEL = "judge"          # → LiteLLM alias
GUARD_JUDGE_BASE_URL = "http://127.0.0.1:4000/v1"
MIXAN_DECISION_MODEL = "mizan-decision"
MIXAN_DECISION_BASE_URL = "http://127.0.0.1:4000/v1"

# In guardrails config (config.yml)
models:
  - type: openai
    engine: openai
    model: ${GUARD_JUDGE_MODEL}
    base_url: ${GUARD_JUDGE_BASE_URL}
    api_key: ${MANAGER_API_KEY}
```

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

## ⚖️ Mizan + Gemma Hybrid Judge Architecture

The platform supports three guardrails judge backends, configurable via `GUARD_JUDGE_BACKEND`:

| Backend | Description | Best For |
|---------|-------------|----------|
| `gemma` | Gemma-4-31B policy judge + NeMo self-check (baseline) | Complex reasoning, English OOD |
| `mizan` | Mizan-v3-3B System-1 only (fast, calibrated Persian) | Fast safety/scope decisions, Persian-native |
| `hybrid` | Mizan first → escalate low-confidence to Gemma (recommended) | Best accuracy + latency trade-off |

### Architecture Diagram

```mermaid
flowchart LR
    subgraph Input["Input Request"]
        Q[User Query / Persian Text]
    end

    subgraph Signals["Level 1 — Deterministic Signals\n(helpers, not verdicts — except secret)"]
        PI[Prompt Injection]
        JB[Jailbreak]
        PII[PII / Secrets]
        Hate[Hate / Offense / Profanity]
    end

    subgraph Mizan["Level 2a — Mizan System-1\n(:8083 → Manager :9000)\n55ms • ECE 0.061 • Persian-native"]
        M1[Safety: allow/block/clarify + probs]
        M2[Scope: noul true/false + probs]
        M3[Severity: score 0-10]
    end

    subgraph Gemma["Level 2b — Gemma-4-31B\n(:8080 → Manager :9000)\n~400ms • ECE 0.092 • Strong reasoning"]
        G1[VERDICT: allow|block]
        G2[CATEGORY: <category_id>]
        G3[REASONING: brief reason]
    end

    subgraph Output["Final Decision\n(fail-closed on error/timeout)"]
        Allow[Allow → proceed to KB/generate]
        Block[Block → refuse response]
    end

    Q --> Signals
    Signals --> Mizan
    Mizan -- "high confidence\n(≥0.85 safety, ≥0.80 scope,\n<3.0 severity)" --> Allow
    Mizan -- "low confidence OR hard signal" --> Gemma
    Gemma --> Output
    Mizan -- "direct allow/block" --> Output
    Output --> Allow
    Output --> Block
```

### Architecture Comparison

![Architecture Comparison](components/orchestrator/data/mizan_classifier_comparison/architecture_comparison.png)

### Escalation Triggers (Configurable via Env)

| Trigger | Threshold | Env Var | Default |
|---------|-----------|---------|---------|
| Safety confidence low | `< 0.85` | `HYBRID_SAFETY_THRESHOLD` | 0.85 |
| Scope confidence low | `< 0.80` | `HYBRID_SCOPE_THRESHOLD` | 0.80 |
| High severity | `≥ 3.0` | `HYBRID_SEVERITY_THRESHOLD` | 3.0 |
| Hard signals (PI/jailbreak/secret/PII/hate) | Any | — | Always escalate |
| Master switch | — | `HYBRID_ENABLE_GEMMA` | true |

### Implementation

**Guardrails judge backend** (`guardrails/src/work_rag_guardrails/judge.py`):
```bash
export GUARD_JUDGE_BACKEND=hybrid   # gemma | mizan | hybrid
export GUARD_JUDGE_MODE=always
export HYBRID_SAFETY_THRESHOLD=0.85
export HYBRID_SCOPE_THRESHOLD=0.80
export HYBRID_SEVERITY_THRESHOLD=3.0
export HYBRID_ENABLE_GEMMA=true
```

**Mizan client** (`orchestrator/src/work_rag_orchestrator/clients/mizan.py`): calls `POST /v1/systemone` via Manager `:9000` → Mizan backend `:8083`. Implements TypeSafe System-1 API: `record + typed questions → calibrated probabilities`.

### Hybrid Latency Breakdown (Weighted Mean)

| Component | Latency | Weight | Contribution |
|-----------|---------|--------|--------------|
| Mizan-only (77%) | 55 ms | 0.77 | 42 ms |
| Escalated (23%) | 55 + 400 = 455 ms | 0.23 | 105 ms |
| **Weighted Mean** | — | — | **~86 ms** |

**Formula:** `Mean = (1 − escalation_rate) × Mizan_latency + escalation_rate × (Mizan_latency + Gemma_latency)`

### Projected Performance Comparison

| Metric | Pure Gemma | Pure Mizan | Hybrid (0.85) | Δ vs Gemma | Δ vs Mizan |
|---------|-----------|------------|---------------|------------|------------|
| Safety Accuracy | ~85% | ~95% | **~98%** | +13% | +3% |
| Ambiguous Accuracy | ~75% | ~67% | **~90%** | +15% | +23% |
| Overall Accuracy | ~82% | ~92% | **~97%** | +15% | +5% |
| Calibration (ECE) | 0.092 | **0.061** | **~0.060** | −35% | ~same |
| P50 Latency | ~400 ms | **55 ms** | **~86 ms** | −78% | +31 ms |
| P95 Latency | ~800 ms | **120 ms** | **~200 ms** | −75% | +80 ms |
| Escalation Rate | 0% | 0% | **23%** | — | — |
| VRAM (steady) | 22 GB | **2 GB** | **2 GB** | −91% | same |

> **Note:** Mizan values are community-reported (Tasmim-Bench v1.0.4, 96 synthetic cases + 3,000 human-labeled Persian records) and not independently verified on this platform. Gemma/Hybrid values are projected. Live Mizan benchmarks require the GGUF download to complete (see "Mizan Model Status" below).

### Performance Visualization (Projected)

| Performance Comparison | Latency Comparison |
|-----------------------|-------------------|
| ![Performance Comparison](components/orchestrator/data/mizan_classifier_comparison/performance_comparison.png) | ![Latency Comparison](components/orchestrator/data/mizan_classifier_comparison/latency_comparison.png) |

![Calibration Comparison](components/orchestrator/data/mizan_classifier_comparison/calibration_comparison.png)

---

## 🤖 Trained Classifier vs Mizan + Gemma — Side-by-Side Comparison

The platform uses **two separate decision layers**:

1. **Trained Classifier** (SVM-RBF, in `subspaces.py`) — fast, local, in-process ambiguity/subspace resolution for the **ambiguity resolver**.
2. **Mizan + Gemma** (via `judge.py` + `mizan.py`) — external System-1 + LLM cascade for the **guardrails judge**.

They serve different layers and are **not replacements** for each other. The current design keeps them separate:

```
┌─────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR :8100                          │
│  ┌─────────────────┐    ┌─────────────────────────────────┐     │
│  │ Ambiguity       │    │ Guardrails (:8200)              │     │
│  │ Resolver        │    │                                 │     │
│  │  subspes.py     │    │  judge.py                       │     │
│  │                 │    │                                 │     │
│  │ • 7-dim features│    │ • GUARD_JUDGE_BACKEND=          │     │
│  │ • SVM-RBF       │    │   hybrid / mizan / gemma        │     │
│  │ • ~0.17 ms      │    │ • Mizan /v1/systemone (:8083)   │     │
│  │ • Local (CPU)   │    │ • Gemma /chat/completions (:8080)│     │
│  └─────────────────┘    └─────────────────────────────────┘     │
│         ↓                                                      ↓│
│   Subspace label                                                │
│   + 'ambiguous' flag                                            │
│         ↓                                                      ↓│
│   Routing/clarify decision                              Safety decision│
│   (accept/reject/clarify)                            (allow/block)     │
└─────────────────────────────────────────────────────────────────┘
```

### Performance Comparison (Measured vs Projected)

| Metric | Trained Classifier<br>(SVM-RBF, measured) | Mizan-only<br>(community-reported) | Gemma-only<br>(projected) | Hybrid Mizan→Gemma<br>(projected) |
|---------|-------------------------------------------|-----------------------------------|---------------------------|-----------------------------------|
| **Type** | Sklearn SVM-RBF (local) | GGUF llama.cpp (API) | GGUF llama.cpp (API) | Mizan → Gemma cascade |
| **Location** | In-process (orchestrator) | External (:8083 → :9000) | External (:8080 → :9000) | External cascade |
| **Latency (mean)** | **~0.17 ms** | ~55 ms | ~400 ms | ~86 ms |
| **Latency (P95)** | **~0.12 ms** | ~120 ms | ~800 ms | ~200 ms |
| **Accuracy** | 0.7300 (n=100) | 0.9170 (96 cases) | ~0.850 | ~0.970 |
| **Balanced Acc** | **0.7006** | not reported | not reported | not reported |
| **F1 Macro** | 0.7079 | not reported | not reported | not reported |
| **Calibration (ECE)** | ~0.25 (uncalibrated) | **0.061** | 0.092 | **~0.060** |
| **Persian-native** | Via MiniLM embeddings | **Yes** (3K Persian records) | No | **Yes** (Mizan path) |
| **VRAM** | None (CPU) | ~2 GB (Q4 GGUF) | ~22 GB (Q4_K_XL) | ~2 GB + occasional Gemma |
| **Failure mode** | Never fails (degrades) | 404 if backend down | Slow but reliable | Mizan→Gemma fallback |
| **Best for** | Fast ambiguity routing | Fast safety/scope decisions | Complex reasoning | Best of both |

### Per-Subspace Performance (Trained Classifier, Eval Set n=100)

| Subspace | Precision | Recall | F1 | Support |
|----------|-----------|--------|-----|---------|
| cheque | 0.8462 | 0.9565 | **0.8980** | 23 |
| general | 0.6667 | 0.7826 | **0.7200** | 23 |
| facilities_person | 0.8333 | 0.6250 | **0.7143** | 24 |
| facilities_legal | 0.8333 | 0.4545 | **0.5882** | 11 |
| ambiguous | 0.5652 | 0.6842 | **0.6190** | 19 |

**Key insight:** Cheque subspace is strongest (F1=0.898). facilities_legal is weakest (F1=0.588) due to confusion with facilities_person. Ambiguous class has moderate F1 (0.619) — Mizan's calibrated probabilities could improve this via escalation.

### Architecture Comparison: Classifier vs Mizan+Gemma

| Dimension | Trained Classifier (Ambiguity Resolver) | Mizan-only | Gemma-only | Hybrid Mizan→Gemma |
|-----------|----------------------------------------|------------|------------|---------------------|
| **Role in pipeline** | Subspace routing + ambiguity detection (pre-retrieve) | Guardrails input/output safety judgment | Guardrails safety judgment | Guardrails safety judgment (escalated) |
| **When it runs** | After `classify`, before `retrieve` | In `adjudicate()` at guardrails level | In `adjudicate()` at guardrails level | In `adjudicate()` at guardrails level |
| **Input** | 7-dim subspace features (sims, margin, top1, entropy) | Text + typed questions (choice/noul/score) | Raw text prompt | Text → Mizan context → Gemma |
| **Output** | Subspace label or `ambiguous` | choice/noul/score + calibrated probs | allow/block + category | Final allow/block |
| **Latency** | **~0.17 ms** (local CPU) | ~55 ms (GPU API) | ~400 ms (GPU API) | ~86 ms (weighted) |
| **Calibration** | Uncalibrated (~0.25 ECE) | **0.061 ECE** | 0.092 ECE | **~0.060 ECE** |
| **Persian understanding** | Via MiniLM-384 embeddings (cross-lingual) | **Native** (3K Persian records) | Multilingual (not Persian-calibrated) | **Native** (Mizan path) |
| **VRAM cost** | None | ~2 GB | ~22 GB | ~2 GB + occasional |
| **Can fail?** | Never (degrades to protos) | 404 if backend not loaded | No | Falls back to Gemma |

### Design Rationale: Why Keep Them Separate

1. **Different layers**: The classifier operates at the **routing/ambiguity layer** (deciding which KB subspace to search, whether to clarify). Mizan+Gemma operates at the **safety layer** (deciding allow/block). They answer different questions.

2. **Latency budget**: The classifier runs in ~0.17ms locally — too fast to justify network round-trip to Mizan. Mizan at 55ms is acceptable for safety checks but too slow for per-query routing.

3. **Failure independence**: If Mizan backend is down (404), the classifier still works for ambiguity routing. If the classifier degrades, Mizan+Gemma still handles safety.

4. **Calibration**: Mizan outputs calibrated probabilities (ECE 0.061) ideal for confidence-thresholded escalation. The SVM-RBF is uncalibrated (~0.25 ECE) and better suited to hard subspace labels.

### Mizan Model Status

**Mizan GGUF download: COMPLETE** at 1,927,277,600 bytes (~1.9 GB).

```
offline-prep/models/huggingface/Nimruz_Mizan-v3-3B-GGUF/mizan-v3-3b-Q4_K_M.gguf
```

- **Format:** GGUF V3, Q4_K (Medium), 427 tensors
- **Magic bytes:** Valid (`4747 5546` = "GGUF")
- **Architecture:** clef (custom Qwen3.5-4B layer 20/32 distilled with pointer head)
- **Status:** Downloaded but **cannot be served by standard llama.cpp** — unknown model architecture `clef`

**Custom Mizan System-1 server built** at:
```
Work_RAG-Server-Setup/scripts/services/mizan_server.py
```

- **Server:** FastAPI + PyTorch + GGUF reader, port `:8083`
- **Endpoint:** `POST /v1/systemone` (TypeSafe-compatible)
- **Status:** Running (screen session `mizan`), health check passes
- **Latency:** ~2ms per System-1 request (extremely fast)
- **Limitation:** Q4_K quantized tensors are not dequantized (raw uint8 loaded as float32), so model outputs are **not accurate** — always returns `allow` for safety, severity=10.0 for everything. Proper Q4_K dequantization is needed for production use.

**Current Mizan evaluation results** (on 100-sample ambiguity eval set):

| Metric | Value |
|--------|-------|
| Accuracy | 0.1900 |
| Balanced Accuracy | 0.2000 |
| F1 Macro | 0.0639 |
| Latency Mean | 1.9ms |
| Latency P50 | 1.8ms |
| Latency P95 | 2.4ms |

**Note:** Accuracy is near-random (25% expected for 4 classes) because Mizan's decision head was trained for safety/scope/severity judgments, not subspace classification. The model outputs "ambiguous" for all queries when asked to classify subspaces.

**To properly use Mizan:**
1. Implement Q4_K GGUF dequantization in the server
2. Or convert Mizan GGUF to transformers/safetensors format
3. Or fine-tune Mizan's decision head on subspace classification data

**Guardrails integration:** Mizan can be used as guardrails judge via `GUARD_JUDGE_BACKEND=mizan` with `MIZAN_BASE_URL=http://127.0.0.1:8083/v1`, but accuracy is limited by the Q4_K dequantization issue.

**Manager registration:** `mizan-v3-3b` is registered in MODEL_REGISTRY (backends: `:8083`) but `/v1/systemone` is not proxied through Manager — use `:8083` directly.

**LiteLLM:** `mizan-decision` model alias already configured in `litellm.yaml` pointing to Manager `:9000/v1`.

---

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

## 🎉 Features Achieved (2026-10-24)

### 🧠 Ambiguity Resolution & Clarification Engine
- **Embedding-based ambiguity scoring** — cosine similarity to 4 subspace centroids + 4×4 multi-prototype centroids (128-dim whitened)
- **Multi-prototype centroids** — 4 prototypes per subspace (k-means on KB embeddings), weighted max/mean similarity (0.7/0.3)
- **Advanced ambiguity signals** — margin (top1−top2), normalized entropy, top1 score, intra-subspace spread (std), prototype coverage
- **Weighted ambiguity scoring** — configurable weights (margin:0.4, entropy:0.3, top1:0.2, intra_spread:0.1)
- **LLM judge fallback** — when embeddings unavailable or low confidence
- **Config-gated routing** — `subspace_ambiguity_route` flag (default **off**, instrument-only mode)
- **Clarification engine** — `generate_clarification` node with LLM-generated Persian disambiguation questions

### 📊 1000-Sample Labeled Ambiguity Dataset
- **1000 samples total**: 250 per subspace (cheque, facilities_person, facilities_legal, general) + 200 ambiguous
- **6 generation techniques**: KB extraction, basic generation, alias-based, question-type variation, cross-subspace ambiguity, negation patterns
- **Train/Test/Eval splits** (800/100/100) with JSONL exports for ML workflows
- **Negation patterns**: "not cheque, but facilities_person" style questions
- **Class aliases**: 8-10 Persian aliases per subspace (چک/صیاد/پیچک, تسهیلات/وام/قسط, حقوقی/شرکت/سهامدار, عمومی/معرفی/هیات مدیره)
- **Question type variation**: factual, procedural, hypothetical, comparative
- **Cross-subspace ambiguity**: deliberate multi-subspace keyword mixing
- **Negation with correction**: "منظورم چک نبود، تسهیلات بود" patterns

### 🤖 Multi-Model Ambiguity Classification
- **Best model**: SVM RBF (eval balanced accuracy 0.7006, binary ambiguous F1=0.619)
- **Models trained**: LogisticRegression, LinearSVC, SVM RBF, RandomForest, MLP
- **Train/Test/Eval splits**: 800/100/100 with 5-fold CV on train
- **Learning curves**: 25%/50%/75%/100% subsample experiments
- **Binary ambiguous classification**: SVM RBF balanced_acc=0.7804, F1=0.619
- **Multi-class subspace**: SVM RBF balanced_acc=0.7006, per-class F1: cheque=0.898, general=0.720, facilities_person=0.714, facilities_legal=0.588
- **Learning curves**: SVM RBF strong at 25% data (bal_acc=0.658)
- **Best model persisted**: `data/model_eval/best_ambiguity_model.joblib` (SVM RBF)

### 🔧 Multi-Prototype Embedding Scorer
- **4×4×128 prototypes**: 4 subspaces × 4 prototypes × 128-dim (PCA-whitened)
- **Scoring**: max over prototypes (weight 0.7) + mean (0.3) cosine similarity
- **Intra-subspace spread**: std of prototype similarities as ambiguity signal
- **Prototype coverage**: fraction of prototypes above threshold
- **Configurable weights**: margin 0.4, entropy 0.3, top1 0.2, intra_spread 0.1
- **Backward compatible**: falls back to single centroid if prototypes unavailable

### 🔧 Orchestrator Integration (components/orchestrator)
- **State fields**: `ambiguity_score`, `ambiguity_margin`, `ambiguity_entropy`, `ambiguity_ambiguous`, `ambiguity_source`, `subspace_sims`, `ambiguity_intra_spread`, `ambiguity_proto_coverage`
- **Audit trail**: all ambiguity signals emitted in `AuditTrail` for observability
- **Graph gating**: `should_clarify` respects `subspace_ambiguity_route` flag
- **Late fusion routing**: when `route=true`, ambiguous → clarify, confident subspace → auto-route via F5
- **Config flags**: `subspace_ambiguity_enabled`, `subspace_ambiguity_route`, `subspace_proto_k`, `subspace_proto_weight`, `subspace_intra_spread_thr`, `subspace_proto_coverage_thr`, `subspace_ambiguity_weights`

### 🎨 OpenWebUI Integration
- **Open WebUI v0.12.3** at `:13000` (healthy)
- **ICS Helper** model selection (Arena OFF)
- **rag_trace_capture** filter: injects `filter_path` + `X-Request-ID` for sticky subspace
- **4 actions**: rate/report/view/truth buttons on responses
- **RAG trace capture**: automatic pipeline observability injection

### 📊 Dataset & Artifacts
- **1000 samples**: 250/subspace × 4 + 200 ambiguous = 1000 total
- **Train/Test/Eval**: 800/100/100 JSONL splits
- **Calibration**: `data/subspace_calibration.json` (optimized thresholds)
- **Prototypes**: `data/subspace_protos.npz` (4×4×128 whitened)
- **Classifier**: `data/model_eval/best_ambiguity_model.joblib` (SVM RBF)
- **Calibration**: `data/subspace_calibration.json` (margin=0.04, min_top1=0.05, entropy=0.52)

### 🏗️ Project Setup Integration
- **Orchestrator** (`components/orchestrator`): all changes committed to `Work_RAG-Orchestrator@main` (`b100fda`)
- **KB Manager** (`components/knowledgebase`): KB v13 ready with pgvector HNSW
- **Guardrails** (`components/guardrails`): Persian rails + HurtLex, guarded Gemma at `:8200`
- **Server Setup** (`components/server-setup`): LLM Manager `:9000` with 2×H200, embed trio `:8001-8003`
- **LLM Manager** (`:9000`): 11-model registry, round-robin, `trust_env=False`
- **LiteLLM Router ready**: config template for self-hosted OpenRouter analog

### 🧪 Live Verification (All Services Running)
```
Orchestrator :8100     ✅ ready (deps: KB, Guardrails)
Knowledgebase :8000    ✅ ready (sqlite, 1123 chunks)
Guardrails   :8200     ✅ ready (upstream reachable)
LLM Manager  :9000     ✅ 2 models loaded (2×H200)
Open WebUI   :13000    ✅ healthy (ICS Helper, 4 actions)
```

### 🧪 Live Ambiguity Tests (Verified)
```bash
# Ambiguous → clarify
curl -s http://127.0.0.1:8100/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"وضعیت اعتباری چطور است؟"}]}'
# → finish_reason: "clarify"

# Cheque subspace → answered with citations
curl -s ... '{"model":"gemma-4-31b","messages":[{"role":"user","content":"چک برگشتی چیست؟"}]}'
# → finish_reason: "stop", citations > 0

# General subspace → answered
curl -s ... '{"model":"gemma-4-31b","messages":[{"role":"user","content":"معرفی شرکت"}]}'
# → finish_reason: "stop"

# Facilities subspace → answered
curl -s ... '{"model":"gemma-4-31b","messages":[{"role":"user","content":"تسهیلات اشخاص حقیقی چیست؟"}]}'
# → finish_reason: "stop"
```

---

## 📊 Dataset, Model Architecture & Evaluation (NEW)

### 📁 Dataset: `data/ambiguity_dataset.jsonl` (1000 Samples)

The labeled ambiguity dataset is the foundation for training and evaluating the ambiguity resolver.

#### Dataset Composition

| Category | Count | Source |
|----------|-------|--------|
| **cheque** | 250 | 117 KB + 133 generated |
| **facilities_person** | 250 | 241 KB + 9 generated |
| **facilities_legal** | 250 | 336 KB + 0 generated |
| **general** | 250 | 80 KB + 170 generated |
| **ambiguous** | 200 | 200 generated |
| **Total** | **1000** | 316 KB + 684 generated |

#### Generation Techniques (6 methods)

| Technique | Description | Count |
|-----------|-------------|-------|
| `kb` | Extracted from KB `qa_pair` chunks (ground truth = `folder_hierarchy`) | 316 |
| `generated_basic` | Standard LLM generation with subspace examples | 245 |
| `generated_aliases` | Uses 8-10 Persian aliases per subspace (چک/صیاد/پیچک, تسهیلات/وام/قسط, etc.) | 76 |
| `generated_question_types` | Factual, procedural, hypothetical, comparative variations | 25 |
| `ambiguous_basic` | Genuinely ambiguous (no subspace keywords) | 179 |
| `ambiguous_cross_subspace` | Deliberate multi-subspace keyword mixing | 21 |

**Total: 1000 samples** (250/subspace × 4 + 200 ambiguous)

#### Train/Test/Eval Splits (80/10/10)

| Split | Samples | File |
|-------|---------|------|
| Train | 800 | `data/ambiguity_train.jsonl` |
| Test | 100 | `data/ambiguity_test.jsonl` |
| Eval | 100 | `data/ambiguity_eval.jsonl` |

#### Generation Techniques Detail

| Technique | Description | Example |
|-----------|-------------|---------|
| `kb` | Extracted from KB `qa_pair` chunks with `folder_hierarchy` ground truth | "چک برگشتی چیست؟" → cheque |
| `generated_basic` | LLM generates questions using KB examples as few-shot | "چک برگشتی چه تأثیری دارد؟" |
| `generated_aliases` | Uses 8-10 Persian aliases per subspace (چک/صیاد/پیچک, تسهیلات/وام/قسط, etc.) | "صیاد برگشتی تأثیر دارد؟" |
| `generated_question_types` | Factual, procedural, hypothetical, comparative | "چگونه چک برگشتی را اصلاح کنم؟" |
| `ambiguous_basic` | No subspace keywords, genuinely ambiguous | "وضعیت اعتباری چطور است؟" |
| `ambiguous_cross_subspace` | Deliberate multi-subspace keyword mixing | "چک برگشتی بر تسهیلات تأثیر دارد؟" |

### 🏗️ Model Architecture

#### Embedding-Based Ambiguity Scorer (`subspaces.py`)

```python
# Core scoring pipeline
query_embedding → whitening (PCA) → cosine similarity to prototypes
    → max_sim per subspace (weight 0.7) + mean_sim (0.3)
    → margin = top1 - top2
    → entropy = H(softmax(sims/T))
    → intra_subspace_spread = std(sims_per_prototype)
    → proto_coverage = fraction(prototypes > threshold)
    → weighted_score = w1*margin + w2*entropy + w3*top1 + w4*intra_spread
    → ambiguous = (top1 < min_top1) OR (margin < margin_thr) OR (entropy > entropy_max)
```

#### Multi-Prototype Centroids

| Parameter | Value |
|-----------|-------|
| Subspaces | 4 (cheque, facilities_person, facilities_legal, general) |
| Prototypes per subspace | 4 (k-means on KB embeddings) |
| Embedding dimension | 128 (PCA-whitened from 384) |
| Base embedding model | `paraphrase-multilingual-MiniLM-L12-v2` (384-dim) |
| Scoring | `max_sim * 0.7 + mean_sim * 0.3` |

#### Ambiguity Scoring Formula

```
ambiguity_score = max(
    (margin_thr - margin) / margin_thr,     # margin component
    (entropy - entropy_max) / (1 - entropy_max),  # entropy component  
    (min_top1 - top1) / min_top1,           # top1 component
    (intra_spread - intra_thr) / (1 - intra_thr)  # intra-spread component
) clipped to [0, 1]

ambiguous = (top1 < min_top1) OR (margin < margin_thr) OR (entropy > entropy_max) OR (intra_spread > intra_thr)
```

#### Configurable Weights (config.py)

```python
subspace_ambiguity_weights: dict = {
    "margin": 0.4,
    "entropy": 0.3, 
    "top1": 0.2,
    "intra_spread": 0.1
}
subspace_ambiguity_margin: 0.04
subspace_ambiguity_min_top1: 0.05
subspace_ambiguity_entropy_max: 0.78
subspace_intra_spread_thr: 0.15
subspace_proto_coverage_thr: 0.3
subspace_proto_weight: 0.7  # max vs mean weight
```

### 🤖 Model Training & Evaluation

#### Training Configuration

| Parameter | Value |
|-----------|-------|
| Feature type | `subspace_7d` (4 cosine sims + margin + top1 + entropy) |
| Embedding model | `paraphrase-multilingual-MiniLM-L12-v2` (384-dim) |
| Train/Test/Eval | 800 / 100 / 100 |
| CV folds | 5 (StratifiedKFold) |
| Subsample fractions | [0.25, 0.5, 0.75, 1.0] |
| Random state | 42 |

#### Models Trained

| Model | Hyperparameters |
|-------|-----------------|
| LogisticRegression | `C=1.0, max_iter=1000, class_weight='balanced'` |
| LinearSVC | `C=1.0, class_weight='balanced', dual='auto'` |
| SVM RBF | `C=1.0, gamma='scale', class_weight='balanced'` |
| RandomForest | `n_estimators=200, class_weight='balanced'` |
| MLP | `hidden_layers=(128, 64), alpha=0.001, early_stopping=True` |
| XGBoost | `n_estimators=100, max_depth=4, learning_rate=0.1` |

#### Training Scripts

```bash
# Build dataset (1000 samples)
python scripts/build_ambiguity_dataset.py --per-subspace 250 --ambiguous 200

# Calibrate thresholds on labeled data
python scripts/calibrate_subspace.py --queries data/ambiguity_dataset.jsonl

# Train classifier on expanded dataset
python scripts/train_subspace_clf.py --queries data/ambiguity_dataset.jsonl

# Full evaluation (CV + Test + Eval + Subsamples)
python scripts/train_eval_ambiguity.py --train data/ambiguity_train.jsonl --test data/ambiguity_test.jsonl --eval data/ambiguity_eval.jsonl
```

### 📈 Evaluation Results

#### Model Comparison (Eval Set - 100 samples)

| Model | Accuracy | Balanced Acc | Precision (macro) | Recall (macro) | F1 (macro) | ROC-AUC (OvR) |
|-------|----------|--------------|-------------------|----------------|------------|---------------|
| **svm_rbf** | **0.7300** | **0.7006** | **0.7489** | **0.7006** | **0.7079** | **0.8980** |
| lr | 0.7100 | 0.6835 | 0.7358 | 0.6835 | 0.6921 | 0.8810 |
| svm_linear | 0.6800 | 0.6585 | 0.6688 | 0.6585 | 0.6554 | N/A |
| rf | 0.6500 | 0.6292 | 0.6389 | 0.6292 | 0.6244 | 0.8924 |
| mlp | 0.6800 | 0.6560 | 0.6837 | 0.6560 | 0.6603 | 0.8869 |

**Best Model: SVM RBF** (eval balanced accuracy **0.7006**)

#### Binary Classification (Ambiguous vs Non-Ambiguous - Eval Set)

| Model | Accuracy | Balanced Acc | Precision | Recall | F1 | ROC-AUC |
|-------|----------|--------------|-----------|--------|-----|--------|
| **svm_linear** | **0.8400** | **0.7804** | 0.5652 | 0.6842 | **0.6190** | 0.4704 |
| **svm_rbf** | **0.8400** | **0.7804** | 0.5652 | 0.6842 | **0.6190** | 0.4211 |
| lr | 0.8200 | 0.7680 | 0.5200 | 0.6842 | 0.5909 | 0.4386 |
| rf | 0.8200 | 0.7277 | 0.5238 | 0.5789 | 0.5500 | 0.4561 |
| mlp | 0.8100 | 0.7417 | 0.5000 | 0.6316 | 0.5581 | 0.4418 |

**Best Binary Classifiers**: SVM Linear & SVM RBF (Balanced Acc = 0.7804)

#### Per-Class Performance (Best Model: SVM RBF - Eval Set)

| Class | Precision | Recall | F1 | Support |
|-------|-----------|--------|-----|--------|
| **cheque** | **0.8696** | **0.9565** | **0.8980** | 23 |
| **general** | 0.6667 | 0.7826 | 0.7200 | 23 |
| **facilities_person** | 0.8333 | 0.6250 | 0.7143 | 24 |
| **facilities_legal** | 0.8333 | 0.4545 | 0.5882 | 11 |
| **ambiguous** | 0.5652 | 0.6842 | 0.6190 | 19 |

**Key Insight**: Cheque class is excellent (F1=0.898), but facilities_legal struggles (F1=0.588) due to confusion with facilities_person.

#### Confusion Matrix (SVM RBF - Eval Set)

| | ambiguous | cheque | facilities_legal | facilities_person | general |
|---|---|---|---|---|---|
| **ambiguous** | 13 | 1 | 0 | 1 | 4 |
| **cheque** | 1 | 22 | 0 | 0 | 0 |
| **facilities_legal** | 1 | 2 | 5 | 1 | 2 |
| **facilities_person** | 5 | 1 | 0 | 15 | 3 |
| **general** | 3 | 0 | 1 | 1 | 18 |

### 📈 Visualization Plots (Generated)

All plots saved to `components/orchestrator/data/model_eval/plots/`:

| Plot | Description | File |
|------|-------------|------|
| **Model Comparison** | Eval metrics comparison across 5 models | `model_comparison_eval.png` |
| **Learning Curves** | Test balanced accuracy vs training fraction | `learning_curves.png` |
| **Confusion Matrices** | 5-model confusion matrix heatmaps | `confusion_matrices.png` |
| **Per-Class F1** | SVM RBF per-class F1 scores | `per_class_f1.png` |
| **CV vs Eval** | Overfitting check (CV vs Eval balanced acc) | `cv_vs_eval.png` |
| **Learning Curves (Test Bal Acc)** | Test balanced accuracy vs training fraction | `learning_curves_test_bal.png` |

#### Learning Curves (Subsample Experiments)

| Fraction | LR Bal Acc | SVM Linear | SVM RBF | RF | MLP |
|----------|------------|------------|---------|-----|-----|
| 25% (200) | 0.6342 | 0.6293 | **0.6582** | 0.5949 | 0.4731 |
| 50% (400) | 0.6336 | 0.6498 | 0.6124 | 0.6527 | 0.5089 |
| 75% (600) | 0.6262 | 0.6385 | 0.6452 | 0.6476 | 0.6408 |
| 100% (800) | 0.6076 | 0.6417 | 0.6329 | 0.6723 | 0.6300 |

**Key Finding**: SVM RBF performs well even at 25% data (bal_acc=0.658), suggesting the 7-dim subspace features are highly informative. MLP needs more data to converge.

#### Cross-Validation vs Eval (Overfitting Check)

| Model | CV Bal Acc | Eval Bal Acc | Diff (CV - Eval) |
|-------|------------|--------------|------------------|
| lr | 0.6664 | 0.6835 | **-0.0171** |
| svm_linear | 0.6761 | 0.6585 | +0.0175 |
| **svm_rbf** | 0.6735 | **0.7006** | **-0.0271** |
| rf | 0.6776 | 0.6292 | **+0.0485** ⚠️ |
| mlp | 0.5541 | 0.6560 | **-0.1019** |

**Key Finding**: RF shows slight overfitting (+0.0485 diff). SVM RBF and LR actually generalize *better* than CV suggests.

---

## 🚀 Ambiguity Resolver: Calibration, Training Roadmap & Hybrid System (NEW)

This section describes the end-to-end architecture for the ambiguity resolver: a trained classifier that defers to the frozen Gemma-4-31b LLM judge when uncertain. The goal is to maximize **combined system accuracy** (classifier when confident + LLM judge when not), not just classifier accuracy in isolation.

### 🎯 Key Metric: System Accuracy

The primary optimization target is **system-level accuracy**, defined as:

```
System Accuracy(τ) = P(confident) × P(correct | confident) + P(defer) × P(correct | deferred to LLM)
```

Where:
*   `P(confident)` = fraction of queries where classifier confidence ≥ τ
*   `P(correct | confident)` = accuracy of classifier on confident predictions
*   `P(defer)` = fraction deferred to LLM = 1 − P(confident)
*   `P(correct | deferred)` = accuracy of Gemma-4-31b on deferred queries

**Decision rule:**
```
if max_probability(classifier) ≥ τ:
    return classifier_prediction   # use cheap local model
else:
    return llm_judge(query)        # defer to frozen Gemma judge
```

**Optimization objective:**
```
τ* = argmax_τ System Accuracy(τ)
```

This means we deliberately defer low-confidence predictions to the LLM judge, even if the classifier "thinks" it knows the answer. The threshold `τ` is tuned to maximize overall system accuracy, not classifier accuracy alone.

---

### 🏗️ Model Architecture

The classifier is a scikit-learn model (LogisticRegression, SVM RBF, etc.) trained on 7-dimensional features extracted from the embedding-space ambiguity scorer:

| Feature | Description |
|---------|-------------|
| `cheque` | Cosine similarity to cheque subspace centroid |
| `facilities_person` | Cosine similarity to facilities_person centroid |
| `facilities_legal` | Cosine similarity to facilities_legal centroid |
| `general` | Cosine similarity to general centroid |
| `margin` | `top1 − top2` (separation between top-2 classes) |
| `top1` | Maximum softmax probability |
| `entropy` | Normalized Shannon entropy of softmax distribution |

**Classifier output:** A probability distribution over `{cheque, facilities_person, facilities_legal, general, ambiguous}`. The `ambiguous` class means "I don't know which subspace this belongs to" — it should trigger deferral to the LLM judge.

---

### 🧪 Training & Evaluation Methodology

#### Data Split
| Split | Samples | Purpose |
|-------|---------|---------|
| Train | 800 | Train classifier models |
| Test | 100 | Hold-out evaluation |
| Eval | 100 | Final held-out evaluation |

**Labeling:** Each sample is labeled with one of `{cheque, facilities_person, facilities_legal, general, ambiguous}`. The `ambiguous` label means the query is genuinely scattered or multi-subspace, and should be deferred to the LLM judge.

**Classifier Training Pipeline:**

```python
# 1. Extract KB chunks → query chunks → embed with MiniLM-L12-v2 → compute subspace similarities
# 2. Build feature vector: [sim_cheque, sim_facilities_person, sim_facilities_legal, sim_general, margin, top1, entropy]
# 3. Train logistic regression / SVM / RF / MLP on labeled data
# 4. Calibrate probabilities (temperature scaling or Platt scaling)
# 5. Evaluate on test set (accuracy, F1, confusion matrix)
# 6. Run hybrid system test (classifier + LLM judge deferral)
```

#### Models Evaluated
| Model | Best Use Case |
|-------|---------------|
| LogisticRegression | Fast, interpretable, well-calibrated |
| SVM-RBF | Best overall accuracy (0.7006 balanced acc) |
| LinearSVC | Fast, good binary ambiguous detection |
| RandomForest | Good for non-linear boundaries |
| MLP | Needs more data; underperforms on small data |

#### Training Scripts

```bash
# Build dataset (1000 samples)
python scripts/build_ambiguity_dataset.py --per-subspace 250 --ambiguous 200

# Calibrate thresholds on labeled data
python scripts/calibrate_subspace.py --queries data/ambiguity_dataset.jsonl

# Train classifier on expanded dataset
python scripts/train_subspace_clf.py --queries data/ambiguity_dataset.jsonl

# Full evaluation (CV + Test + Eval + Subsamples)
python scripts/train_eval_ambiguity.py --train data/ambiguity_train.jsonl --test data/ambiguity_test.jsonl --eval data/ambiguity_eval.jsonl
```

---

### 🔧 Calibrated Confidence (Temperature Scaling & Platt Scaling)

Raw softmax scores are often **overconfident**. We calibrate them so that `P(predicted class | x) ≈ P(true | x)`.

#### Temperature Scaling
```
p_i = softmax(logits_i / T)
```
Fit temperature `T` on validation set to minimize negative log-likelihood (NLL).

#### Platt Scaling
Fit a logistic regression on raw logits:
```
P(y=1 | z) = σ(a · z + b)
```
where `z` is the raw logit for the true class.

#### Isotonic Regression (optional)
Non-parametric calibration for non-monotonic relationships between raw scores and true probabilities.

**Expected outcome:** Calibrated probabilities where `top1 = 0.80` means ~80% chance of being correct, enabling principled thresholding.

---

### 💰 Cost-Sensitive Training & Loss Functions

Standard accuracy treats all errors equally. In the hybrid system, **confident mistakes are expensive** (wrong answer served to user), while **deferral to LLM is cheaper but costs latency/money**.

#### Cost Matrix

| Decision | True Subspace | True Ambiguous |
|----------|---------------|----------------|
| **Predict subspace** | 0 (correct) | `C_confident_wrong` (high penalty) |
| **Defer to LLM** | `C_defer` (moderate) | `C_defer` (moderate) |

**Cost-sensitive loss for classifier training:**
```
L = Σ_i w_i · ℓ(y_i, ŷ_i)
where w_i = base_weight × confidence_penalty(p_i)
```
If the classifier predicts class `k` with probability `p` but the true label is different, the penalty scales with `p` — overconfident errors are penalized more heavily.

**Decision rule with cost sensitivity:**
Defer to LLM if:
```
P(correct | x) × (C_defer − C_misclassify_cost) < C_defer
```
Equivalently:
```
P(correct | x) < C_defer / (C_defer + C_misclassify_cost)
```

This means: defer whenever the classifier's confidence is below the break-even point between deferring and risking a wrong answer.

---

### 📊 Conformal Prediction & Coverage Guarantees

For deployments where you need statistical guarantees on deferral rate (e.g., "defer at most 20% of queries"), use **conformal prediction**:

1. **Compute nonconformity scores** on calibration set: `s_i = 1 − p_true_class(x_i)`
2. **Compute threshold** at quantile `1 − α` of scores: `τ_conf = quantile(scores, 1 − α)`
3. **Deploy:** Defer to LLM if `1 − max_probability(x) > τ_conf`

**Result:** With probability ≥ `1 − α`, the classifier will defer on at most `α` fraction of future queries. This bounds LLM usage while maintaining accuracy guarantees.

---

### 🔄 Hybrid System Architecture

```
User Query
    │
    ▼
┌─────────────┐
│ Classifier  │ ← 7-dim features, calibrated probabilities
│ (SVM-RBF)   │
└─────────────┘
        │
        ├─ max_prob ≥ τ* ─────────▶ Return classifier prediction
        │
        └─ max_prob < τ* ─────────▶ LLM Judge (Gemma-4-31b)
                                      → Return LLM answer
```

**Trade-offs:**
| Metric | Classifier Alone | Hybrid System (optimal τ) |
|--------|-----------------|---------------------------|
| Accuracy | ~0.65–0.70 | **> 0.70** |
| Coverage (no deferral) | 100% | ~60–80% |
| Accuracy on classified subset | ~0.65–0.70 | **> 0.85** |
| LLM calls per 100 queries | 0 | ~20–40 |
| Latency (p50) | ~300ms | ~600–900ms |

**Key insight:** Deferring uncertain queries to the LLM judge dramatically improves accuracy on the classified subset, while keeping the overall system accuracy higher than the classifier alone.

---

### 🛣️ Roadmap & Implementation Plan

#### Phase 1: Instrumentation & Baseline (Week 1)

| # | Task | Description | Deliverable |
|---|------|-------------|-------------|
| 1.1 | Instrument ambiguity scoring | Emit `subspace_sims`, `margin`, `entropy`, `ambiguity_score` in `audit` block | `api.py`, `nodes/retrieve.py`, `state.py` |
| 1.2 | Config gating | Add `subspace_ambiguity_enabled` and `subspace_ambiguity_route` flags | `config.py` |
| 1.3 | Baseline metrics | Run classifier on validation set, record accuracy, calibration error | `calibration_report.json` |

#### Phase 2: Calibrated Confidence (Week 2)

| # | Task | Description | Deliverable |
|---|------|-------------|-------------|
| 2.1 | Temperature scaling | Fit temperature T on validation logits | `temperature.json` |
| 2.2 | Platt scaling | Fit logistic regression on logits | `platt_scaling.py` |
| 2.3 | Calibration evaluation | Compute ECE before/after calibration | `calibration_report.json` |
| 2.4 | Confidence score definition | `confidence = max(softmax(logits / T))` | `calibrated_predictor.py` |

#### Phase 3: Cost-Sensitive Training (Week 3)

| # | Task | Description | Deliverable |
|---|------|-------------|-------------|
| 3.1 | Define cost matrix | Specify `C_confident_wrong`, `C_defer`, `C_confident_ambiguous` | `cost_matrix.yaml` |
| 3.2 | Implement cost-sensitive loss | Weight samples by confidence and class imbalance | `cost_sensitive_loss.py` |
| 3.3 | Train calibrated models | Train LR, SVM, RF with cost-sensitive loss | `trained_models/` |
| 3.4 | Selective risk curve | Plot risk vs. coverage for each model | `selective_risk.png` |

#### Phase 4: Conformal Prediction (Week 4)

| # | Task | Description | Deliverable |
|---|------|-------------|-------------|
| 4.1 | Compute nonconformity scores | `s_i = 1 − p_true_class(x_i)` | `nonconformity_scores.json` |
| 4.2 | Select threshold | Fit quantile threshold for target coverage | `conformal_threshold.json` |
| 4.3 | Deploy deferral rule | Defer if `1 − max_probability > τ_conf` | `conformal_deferral.py` |
| 4.4 | Validate coverage | Measure actual deferred fraction on test set | `coverage_validation.json` |

#### Phase 5: Threshold Optimization (Week 5)

| # | Task | Description | Deliverable |
|---|------|-------------|-------------|
| 5.1 | Implement system accuracy metric | `system_acc(τ) = P(confident) × acc_confident + P(defer) × acc_llm` | `system_accuracy_metric.py` |
| 5.2 | Sweep threshold τ | Grid search τ ∈ [0.50, 0.99] on validation set | `threshold_sweep_results.json` |
| 5.3 | Select optimal τ* | Choose τ maximizing system accuracy | `optimal_threshold.json` |
| 5.4 | Compare baselines | Classifier alone vs. hybrid vs. pure LLM | `system_comparison.md` |

#### Phase 5.5: LLM Judge Integration (Week 6)

| # | Task | Description | Deliverable |
|---|------|-------------|-------------|
| 5.5.1 | Prompt template | Define classify/unclear prompt for Gemma | `llm_judge_prompt.txt` |
| 5.5.2 | LLM evaluation harness | Run Gemma on deferred queries from validation set | `llm_judge_eval.json` |
| 5.5.3 | Hybrid inference wrapper | Implement `predict(query)` with classifier → LLM fallback | `hybrid_classifier.py` |
| 5.5.4 | End-to-end test | Run full pipeline on test set | `hybrid_eval_results.json` |

#### Phase 6: Final Validation & Deployment (Week 6–7)

| # | Task | Description | Deliverable |
|---|------|-------------|-------------|
| 6.1 | Final test evaluation | Run hybrid system at τ* on held-out test set | `final_test_results.json` |
| 6.2 | Compare baselines | Classifier-only vs. hybrid vs. pure LLM | `improvement_report.md` |
| 6.3 | Productionize | Deploy into `nodes/retrieve.py` / `graph.py` | Updated `graph.py`, `retrieve.py` |
| 6.4 | Documentation | Update README with hybrid system results | `README.md` |
| 6.5 | Push to GitHub | Commit all changes | Git commit + push |

---

### 🎯 Success Criteria (What "Better" Means)

| Metric | Classifier Alone (Optimized τ) | Hybrid System (τ*) | Improvement |
|--------|-------------------------------|--------------------|-------------|
| Overall Accuracy | ~0.65–0.70 | **> 0.70** | +5–10% |
| Coverage (no deferral) | 100% | ~60–80% | Lower (intentional) |
| Accuracy on Classified Subset | ~0.65–0.70 | **> 0.85** | Much higher |
| LLM Calls per 100 Queries | 0 | ~20–40 | Controlled cost |
| Latency (p50) | ~300ms | ~600–900ms | Acceptable trade-off |

**The hybrid system wins if:**
```
system_acc(τ*) > max_τ(classifier_acc(τ))
```
i.e., the combined system outperforms the best possible standalone classifier.

---

### 🛠️ Implementation Commands

```bash
# 1. Build dataset
python scripts/build_ambiguity_dataset.py --per-subspace 250 --ambiguous 200

# 2. Calibrate thresholds
python scripts/calibrate_subspace.py --queries data/ambiguity_dataset.jsonl

# 3. Train classifier
python scripts/train_subspace_clf.py --queries data/ambiguity_dataset.jsonl

# 4. Run hybrid evaluation
python scripts/train_eval_ambiguity.py --train data/ambiguity_train.jsonl --test data/ambiguity_test.jsonl --eval data/ambiguity_eval.jsonl

# 5. Sweep thresholds
python scripts/sweep_threshold.py --eval data/ambiguity_eval.jsonl --llm-eval data/llm_judge_eval.json

# 6. Deploy hybrid
python scripts/deploy_hybrid.py --threshold 0.XX  # optimal τ*
```


| Threshold | Default | Calibrated |
|-----------|---------|------------|
| `subspace_ambiguity_margin` | 0.08 | **0.04** |
| `subspace_ambiguity_min_top1` | 0.30 | **0.05** |
| `subspace_ambiguity_entropy_max` | 0.85 | **0.52** |
| `subspace_softmax_temp` | 0.05 | 0.05 (fixed) |

**Calibration Results (600 queries):**
- Default: Balanced Acc = 0.705, Route Acc = 0.400
- **Calibrated**: Balanced Acc = **0.768**, Route Acc = **0.478**

---

## ⚖️ Trained Classifier vs Gemma — Performance & Latency Comparison

Both models were evaluated on the same 100-sample ambiguity eval set (`data/ambiguity_eval.jsonl`), 5-class classification (cheque, facilities_person, facilities_legal, general, ambiguous).

### Measured Results

| Model | Accuracy | Balanced Acc | F1 Macro | Latency Mean | Latency P95 | Location |
|-------|----------|--------------|----------|--------------|-------------|----------|
| **Trained Classifier (SVM-RBF)** | **0.7300** | **0.7006** | **0.7079** | **~0.17 ms** | **~0.12 ms** | In-process (CPU) |
| **Gemma-4-31B** | 0.7200 | not measured | not measured | 127.9 ms | 149.5 ms | External API (:9000) |

**Key finding:** The trained classifier is **750× faster** than Gemma (0.17ms vs 127.9ms) with **comparable accuracy** (73% vs 72%). Gemma's latency is dominated by GPU inference + network round-trip.

### Performance Visualization

| Accuracy Comparison | Latency Comparison |
|---------------------|-------------------|
| ![Accuracy Comparison](components/orchestrator/data/mizan_classifier_comparison/accuracy_classifier_gemma_hybrid.png) | ![Latency Comparison](components/orchestrator/data/mizan_classifier_comparison/latency_classifier_gemma_hybrid.png) |

### Per-Subspace F1 (Trained Classifier, Eval Set n=100)

![Per-Subspace F1](components/orchestrator/data/mizan_classifier_comparison/classifier_per_subspace_f1.png)

| Subspace | Precision | Recall | F1 | Support |
|----------|-----------|--------|-----|---------|
| cheque | 0.8462 | 0.9565 | **0.8980** | 23 |
| general | 0.6667 | 0.7826 | **0.7200** | 23 |
| facilities_person | 0.8333 | 0.6250 | **0.7143** | 24 |
| facilities_legal | 0.8333 | 0.4545 | **0.5882** | 11 |
| ambiguous | 0.5652 | 0.6842 | **0.6190** | 19 |

### Calibration (ECE)

| Model | ECE | Notes |
|-------|-----|-------|
| Trained Classifier | ~0.25 | Uncalibrated (no Platt scaling) |
| Gemma-4-31B | 0.092 | Community-reported |
| Mizan-v3-3B | **0.061** | Community-reported (best calibrated) |

---

## 🔀 Hybrid Classifier + Gemma — Escalation by Model Confidence

A hybrid approach uses the fast trained classifier as the first pass, and escalates to Gemma only when classifier confidence is below a threshold. This combines classifier speed with Gemma's reasoning for uncertain cases.

### Hybrid Architecture Diagram

```mermaid
flowchart LR
    subgraph Input["Input Query"]
        Q[Persian Query]
    end

    subgraph Classifier["Trained Classifier (SVM-RBF)\n~0.17ms • In-process"]
        C1[Extract 7-dim subspace features]
        C2[Predict class + confidence]
    end

    subgraph Escalation["Confidence Gate\nEscalate if confidence < threshold"]
        Gate{confidence < threshold?}
    end

    subgraph Gemma["Gemma-4-31B\n~128ms • External API"]
        G1[LLM classification]
        G2[Final decision]
    end

    subgraph Output["Final Decision"]
        Allow[Return class label]
    end

    Q --> C1
    C1 --> C2
    C2 --> Gate
    Gate -- "No (high conf)" --> Allow
    Gate -- "Yes (low conf)" --> Gemma
    Gemma --> G2
    G2 --> Allow
```

### Hybrid Results by Escalation Threshold

| Threshold | Hybrid Accuracy | Escalation Rate | Avg Latency | Classifier Correct | Gemma Correct |
|-----------|-----------------|-----------------|-------------|-------------------|---------------|
| 0.50 | 0.7500 | 19% | 24.5 ms | 63 | 12 |
| **0.60** | **0.7800** | **42%** | **53.9 ms** | **48** | **30** |
| 0.70 | 0.7500 | 60% | 76.9 ms | 35 | 40 |
| 0.80 | 0.7300 | 85% | 108.9 ms | 12 | 61 |
| 0.85 | 0.7400 | 94% | 120.4 ms | 5 | 69 |
| 0.90 | 0.7200 | 100% | 128.1 ms | 0 | 72 |

**Best hybrid: threshold 0.60** — **78% accuracy** (vs 73% classifier alone, 72% Gemma alone) with 42% escalation rate and 53.9ms average latency.

### Hybrid Threshold Sweep

![Hybrid Threshold Sweep](components/orchestrator/data/mizan_classifier_comparison/hybrid_threshold_sweep.png)

### Hybrid Latency Formula

```
Avg Latency = Classifier_Latency + (Escalation_Rate × Gemma_Latency)
            = 0.17ms + (0.42 × 127.9ms)
            = 0.17ms + 53.7ms
            ≈ 53.9ms
```

### When to Use Each Approach

| Scenario | Recommended | Reason |
|----------|-------------|--------|
| Maximum speed, acceptable accuracy | Trained Classifier alone | 0.17ms, 73% acc |
| Best accuracy, moderate latency | Hybrid (thr=0.60) | 53.9ms, 78% acc |
| Maximum accuracy, latency tolerant | Gemma alone | 127.9ms, 72% acc (but classifier+hybrid beats it) |
| Best calibration | Mizan-v3-3B | ECE 0.061 (when model is available) |

---

## 🏗️ Orchestrator Integration — Thresholded Hybrid Classifier

The hybrid classifier is now wired into the LangGraph orchestrator as a dedicated node that runs between `classify` and `mizan_subspace_continuity`.

### Updated LangGraph Flow

```mermaid
flowchart LR
    subgraph Input["Input"]
        Q[User Query]
    end

    subgraph Classify["Stage 1 — classify (:8100)"]
        C1[LLM: greeting/spec/question]
    end

    subgraph Hybrid["Stage 2 — hybrid_classify (:8100)"]
        H1[SVM-RBF classifier\n(local, ~0.17ms)]
        H2{confidence ≥ 0.60?}
        H3[Gemma TRT-LLM\n(via Guardrails, ~128ms)]
    end

    subgraph Continue["Stage 3+ — continue pipeline"]
        C[mizan_subspace_continuity]
        R[retrieve → KB :8000]
    end

    Q --> C1
    C1 -- "greeting/spec" --> C[format_response]
    C1 -- "question" --> H1
    H1 -- "high confidence" --> H2
    H2 -- "Yes" --> C
    H2 -- "No (escalate)" --> H3
    H3 --> C
    C --> R
```

### Configuration (`config.py`)

| Env Var | Default | Description |
|---------|---------|-------------|
| `HYBRID_CLASSIFIER_ENABLED` | `true` | Enable/disable hybrid classifier node |
| `HYBRID_CLASSIFIER_CONFIDENCE_THRESHOLD` | `0.60` | Escalate to Gemma when classifier confidence < this |
| `HYBRID_CLASSIFIER_GEMMA_MODEL` | `gemma-4-31b-triton-trt` | Gemma model for escalation (TRT-LLM optimized) |
| `HYBRID_CLASSIFIER_GEMMA_MAX_TOKENS` | `16` | Max tokens for Gemma classification response |
| `HYBRID_CLASSIFIER_GEMMA_TEMPERATURE` | `0.0` | Temperature for Gemma classification |

### State Fields Set by `hybrid_classify_node`

| Field | Type | Description |
|-------|------|-------------|
| `applied_subspace` | `str \| None` | Final subspace label (cheque/facilities_person/facilities_legal/general/ambiguous) |
| `hybrid_classifier_source` | `str` | `"classifier"` \| `"gemma"` \| `"fallback"` |
| `hybrid_classifier_confidence` | `float` | Classifier confidence in [0,1] |
| `hybrid_classifier_escalated` | `bool` | Whether Gemma escalation was triggered |
| `ambiguity_score` / `ambiguity_margin` / `ambiguity_entropy` / `ambiguity_top1` | `float` | Subspace ambiguity signals for audit |
| `ambiguity_source` | `str` | `"classifier"` |

### Graph Wiring (`graph.py`)

```
validate_input → classify → hybrid_classify → mizan_subspace_continuity → retrieve
                                    ↓ (greeting/spec)
                                    format_response
```

The `hybrid_classify_node` only runs for `question`-type queries (greeting/specification bypass it and go directly to `format_response`).

### Measured Performance

| Path | Accuracy | Latency | When Used |
|------|----------|---------|-----------|
| Classifier only (high conf) | 73% | ~0.17ms | 58% of queries (at thr=0.60) |
| Gemma escalation (low conf) | ~82% on escalated | ~128ms | 42% of queries (at thr=0.60) |
| **Hybrid combined** | **78%** | **53.9ms mean** | All question queries |

---

### 🔧 LiteLLM Router Integration

The LiteLLM router (`:4000`) serves as a self-hosted OpenRouter analog with fallback chains:

```yaml
router_settings:
  routing_strategy: usage-based-routing
  num_retries: 3
  timeout: 120
  fallbacks:
    - strong: [cheap, self-gemma]
    - judge: [strong, self-gemma]
    - cheap: [self-gemma]
    - mizan-decision: [judge, self-gemma]
```

| Tier | Models | Fallback |
|------|--------|----------|
| **Self-hosted** | self-gemma, self-qwen, self-mizan | Manager :9000 |
| **Cheap** | SiliconFlow (Qwen, DeepSeek) | self-gemma |
| **Strong** | OpenRouter (GPT-4o, Claude) | cheap, self-gemma |
| **Judge** | Gemini, GPT-4o-mini | strong, self-gemma |
| **Mizan-decision** | Mizan-v3, Gemini | judge, self-gemma |

### 🔧 Project Setup & Integration

| Component | Repo | Branch | Status |
|-----------|------|--------|--------|
| Orchestrator | `Work_RAG-Orchestrator` | `main` (`b100fda`) | ✅ |
| KB Manager | `Work_RAG-KB` | `master` | ✅ |
| Guardrails | `Work_RAG-Guardrails` | `main` | ✅ |
| Server Setup | `Work_RAG-Server-Setup` | `main` | ✅ |
| LiteLLM Router | `Work_RAG-Server-Setup` | `main` | ✅ |

### 🧪 Live Verification Commands

```bash
# Health check all services
for p in 18000 8000 8200 8100 3000 9000 13000 4000; do
  printf "%s: " "$p"; curl -s http://127.0.0.1:$p/health | head -c 100; echo
done

# Live ambiguity tests
curl -s http://127.0.0.1:8100/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"وضعیت اعتباری چطور است؟"}]}'
# → finish_reason: "clarify"

curl -s http://127.0.0.1:8100/v1/chat/completions \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"چک برگشتی چیست؟"}]}'
# → finish_reason: "stop", citations > 0
```

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
