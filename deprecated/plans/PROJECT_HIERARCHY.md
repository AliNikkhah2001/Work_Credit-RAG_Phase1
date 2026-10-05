# Work Credit RAG — Full Project Hierarchy

Generated: 2026-09-27 | Root: /splunk-data/v1/Work_Credit-RAG_Phase1 | Branch: main @ f402517

```
/splunk-data/v1/Work_Credit-RAG_Phase1/
│   ├── archive/
│   │   ├── audit-2026-09-12/
│   │   │   ├── documentation_audit.md
│   │   │   ├── documentation_changes.md
│   │   │   ├── fact_check_report.json
│   │   │   ├── final_review_checklist.md
│   │   │   └── repository_documentation_map.json
│   │   ├── benchmark-history/
│   │   │   └── docs-benchmark-2026-09/
│   │   │       ├── plots/
│   │   │       │   ├── citations_v2.png
│   │   │       │   ├── citations_v3.png
│   │   │       │   ├── citations_v4.png
│   │   │       │   ├── format_means_v2.png
│   │   │       │   ├── format_means_v3.png
│   │   │       │   ├── format_means_v4.png
│   │   │       │   ├── judge_v2.png
│   │   │       │   ├── judge_v3.png
│   │   │       │   ├── judge_v4.png
│   │   │       │   ├── similarity_hist_v2.png
│   │   │       │   ├── similarity_hist_v3.png
│   │   │       │   ├── similarity_hist_v4.png
│   │   │       │   └── v3-vs-v4.png
│   │   │       ├── index.html
│   │   │       ├── llm_answer_benchmark_v2.json
│   │   │       ├── llm_answer_benchmark_v3.json
│   │   │       ├── llm_answer_benchmark_v4.json
│   │   │       ├── llm_judge_v2.json
│   │   │       ├── llm_judge_v3.json
│   │   │       ├── llm_judge_v4.json
│   │   │       └── style.css
│   │   ├── handoff-sessions/
│   │   │   ├── sessions/
│   │   │   │   ├── INDEX.md
│   │   │   │   ├── ses_f662eaa09ffek59tAqzqgrzmk3_commit-push-all-repos-general-subagent.md
│   │   │   │   ├── ses_f662eaa2cffeqIf44RU7HD6lr5_validate-stack-e2e-smoke-general-subagen.md
│   │   │   │   ├── ses_f662eaa64ffeVRZClGRfuksXF6_finish-wave-1-bench-aggregate-general-su.md
│   │   │   │   ├── ses_f69bd0067ffeYkQj7BGbueJNdi_fact-check-guardrails-setup-general-suba.md
│   │   │   │   ├── ses_f69bd00e1ffeZpMuACZP7ACDqh_fact-check-kb-submodule-general-subagent.md
│   │   │   │   ├── ses_f69bd0132ffe2p2YKzUyAoAX4g_fact-check-orchestrator-general-subagent.md
│   │   │   │   ├── ses_f69bd0148ffeo0kdaWGrhDa6gn_fact-check-root-deploy-general-subagent.md
│   │   │   │   ├── ses_f69bd019cffe7w8mbt1Nvf53kO_doc-explorer-inventory-general-subagent.md
│   │   │   │   ├── ses_f69fe249effefURDV1vv5x7Ttk_audit-mystery-observe-code-general-subag.md
│   │   │   │   ├── ses_f6a50d043ffe5vMowwTpZc2eul_find-observability-tooling-explore-subag.md
│   │   │   │   ├── ses_f6a50d05cffef0ThivrPDUeYeI_find-conversation-history-explore-subage.md
│   │   │   │   ├── ses_f6a50ebb5ffeHsJtLNMo7LEtg5_rag-agent-history-location-and-observabi.md
│   │   │   │   ├── ses_f6a52d486ffeKuQPQG2ppRetTT_flagembedding-big-model-loaders-general.md
│   │   │   │   ├── ses_f6a575eeaffeM2uwbOgHGye6ef_orchestrator-memory-code-general-subagen.md
│   │   │   │   ├── ses_f6a575ef9ffenaUjaoyJIMHrEG_kb-reranker-registry-code-general-subage.md
│   │   │   │   ├── ses_f6a575f11fferEABLFMd57wGM6_download-rerankers-set-b-general-subagen.md
│   │   │   │   ├── ses_f6a575f29ffecMT5puzXMjSxCv_download-9b-reranker-general-subagent.md
│   │   │   │   ├── ses_f6a575f42ffe8YMbPSYvlfdqbA_download-rerankers-set-a-general-subagen.md
│   │   │   │   ├── ses_f6a5ca448ffe8q908qHWfK4yfS_map-reranker-and-memory-code-explore-sub.md
│   │   │   │   ├── ses_f6a7738f9ffe6RAZA5rnjuvxBe_write-docker-stack-files-general-subagen.md
│   │   │   │   ├── ses_f6a773916ffeTskweHocLEiRAC_write-agents-md-commands-general-subagen.md
│   │   │   │   ├── ses_f6a97a23affe977umsOKmNDWKm_build-real-langfuse-v2-ui-general-subage.md
│   │   │   │   ├── ses_f6a97a260ffeNWjOmUVpgAKRNd_setup-langgraph-studio-general-subagent.md
│   │   │   │   ├── ses_f6ad8e88effer0fXVBgn30KyXr_create-py-venvs-install-deps-general-sub.md
│   │   │   │   ├── ses_f6ad8e89dffegpnjRGd8kSSLW1_setup-postgres-pgvector-db-general-subag.md
│   │   │   │   ├── ses_f6ad8e8c3ffeKEoTAsrQxIu6Ya_build-llama-cpp-cuda-general-subagent.md
│   │   │   │   ├── ses_f6ae9b92dffeCirKJEEjVK2fdE_explore-llama-server-build-run-docs-expl.md
│   │   │   │   ├── ses_f6ae9f317ffeSmRPrDg6hREnnA_explore-orchestrator-guardrails-run-expl.md
│   │   │   │   ├── ses_f6aea1199ffe0EIUQ3IBkDuBL2_explore-kb-pgvector-setup-explore-subage.md
│   │   │   │   ├── ses_f6af2b3a1ffeqp0RpKmQCp9t0g_sync-orchestrator-git-general-subagent.md
│   │   │   │   ├── ses_f6af2c18effebM96RGD21aMR6h_sync-guardrails-git-general-subagent.md
│   │   │   │   ├── ses_f6af2da53ffeZAu3vFPZU39v3C_sync-knowledgebase-git-general-subagent.md
│   │   │   │   ├── ses_f6af303aaffe5bPJzZj0L31OED_sync-server-setup-git-general-subagent.md
│   │   │   │   ├── ses_f6af32e65ffe85ebRy2z0t20qB_sync-parent-repo-git-general-subagent.md
│   │   │   │   └── ses_f6b058c02ffej8lpFUThWHsld0_find-chat-history-for-rag-agent-project.md
│   │   │   └── SESSION_WAVE1_HANDOFF.md
│   │   ├── migration-history/
│   │   │   ├── VAST_GEMMA4_MIGRATION.md
│   │   │   └── WAVE2_GPU_RUNBOOK.md
│   │   └── README.md
│   ├── components/
│   │   ├── guardrails/
│   │   │   ├── config/
│   │   │   │   ├── config.yml
│   │   │   │   └── rails.co
│   │   │   ├── kb/
│   │   │   │   ├── hurtlex_allowlist.json
│   │   │   │   ├── hurtlex_fa.json
│   │   │   │   ├── hurtlex_FA.tsv
│   │   │   │   ├── hurtlex_fa_conservative.json
│   │   │   │   ├── out_of_scope.json
│   │   │   │   ├── persian_swear.json
│   │   │   │   ├── persian_swear_raw.json
│   │   │   │   ├── prompt_injection_fa.json
│   │   │   │   └── README.md
│   │   │   ├── policies/
│   │   │   │   ├── active.yaml
│   │   │   │   ├── ics-credit-v1.0.0.yaml
│   │   │   │   └── README.md
│   │   │   ├── src/
│   │   │   │   └── work_rag_guardrails/
│   │   │   │       ├── risk/
│   │   │   │       ├── semantic/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── actions.py
│   │   │   │       ├── api.py
│   │   │   │       ├── config.py
│   │   │   │       ├── dashboard.py
│   │   │   │       ├── events.py
│   │   │   │       ├── judge.py
│   │   │   │       ├── models.py
│   │   │   │       ├── observability.py
│   │   │   │       ├── policies.py
│   │   │   │       ├── service.py
│   │   │   │       └── signals.py
│   │   │   ├── tests/
│   │   │   │   ├── test_hurtlex_allowlist.py
│   │   │   │   └── test_input_rails.py
│   │   │   ├── .gitignore
│   │   │   ├── Dockerfile
│   │   │   ├── pyproject.toml
│   │   │   └── README.md
│   │   ├── knowledgebase/
│   │   │   ├── archive/
│   │   │   │   ├── before-snapshots/
│   │   │   │   │   ├── benchmark_results_BEFORE.json
│   │   │   │   │   ├── ir_metrics_BEFORE.json
│   │   │   │   │   └── iva_results_BEFORE.json
│   │   │   │   ├── debug-html/
│   │   │   │   │   ├── comparison_debug.html
│   │   │   │   │   ├── dashv7.html
│   │   │   │   │   ├── iva_debug.html
│   │   │   │   │   ├── pipl.html
│   │   │   │   │   └── ver.html
│   │   │   │   ├── debug-scripts/
│   │   │   │   │   ├── _check_db.py
│   │   │   │   │   ├── _check_tq.py
│   │   │   │   │   ├── _test_search.py
│   │   │   │   │   ├── analyze_chunks.py
│   │   │   │   │   ├── analyze_massive_failures.py
│   │   │   │   │   ├── debug_iva_detailed.py
│   │   │   │   │   ├── debug_iva_retrieved.py
│   │   │   │   │   ├── debug_keywords.py
│   │   │   │   │   ├── debug_massive_detailed.py
│   │   │   │   │   ├── diag_beam.py
│   │   │   │   │   ├── diag_iva.py
│   │   │   │   │   ├── diag_miss.py
│   │   │   │   │   ├── diag_pretank.py
│   │   │   │   │   ├── test_benchmark_run.py
│   │   │   │   │   ├── test_comparison.py
│   │   │   │   │   ├── test_comparison2.py
│   │   │   │   │   ├── test_search_kw.py
│   │   │   │   │   ├── test_server.py
│   │   │   │   │   ├── verify_all_unicode.py
│   │   │   │   │   └── verify_fixes.py
│   │   │   │   ├── duplicate-data/
│   │   │   │   └── windows-launchers/
│   │   │   │       ├── debug_iva.bat
│   │   │   │       ├── fix_chunks.bat
│   │   │   │       ├── fix_port.bat
│   │   │   │       ├── launch_mining_shard.bat
│   │   │   │       ├── push_and_merge.bat
│   │   │   │       ├── rebuild_after_fix.bat
│   │   │   │       ├── rebuild_iva.bat
│   │   │   │       ├── restart_server.bat
│   │   │   │       ├── restart_with_zip.bat
│   │   │   │       ├── run_benchmarks_fixed.bat
│   │   │   │       ├── run_massive_qa.bat
│   │   │   │       ├── start_gemma.bat
│   │   │   │       ├── start_guardrails.bat
│   │   │   │       ├── start_kb_manager.bat
│   │   │   │       ├── start_kb_permanent.ps1
│   │   │   │       └── start_orchestrator.bat
│   │   │   ├── docs/
│   │   │   │   ├── BENCHMARK_DEBUG_REPORT.md
│   │   │   │   └── TABULAR_CHUNKING_RESEARCH.md
│   │   │   ├── kb-manager/
│   │   │   │   ├── artifacts/
│   │   │   │   │   └── retrieval_training/
│   │   │   │   ├── configs/
│   │   │   │   │   ├── chunking/
│   │   │   │   │   └── default.yaml
│   │   │   │   ├── data/
│   │   │   │   │   ├── kb_zips/
│   │   │   │   │   ├── plots/
│   │   │   │   │   ├── uploads/
│   │   │   │   │   ├── benchmark_comparison.json
│   │   │   │   │   ├── benchmark_comparison_before_after.json
│   │   │   │   │   ├── benchmark_results.json
│   │   │   │   │   ├── benchmark_results_iva.json
│   │   │   │   │   ├── domain_profile.json
│   │   │   │   │   ├── hnsw_benchmark_detailed.json
│   │   │   │   │   ├── ir_metrics.json
│   │   │   │   │   ├── iva_results.json
│   │   │   │   │   ├── kb_test.db
│   │   │   │   │   ├── pipeline_summary.json
│   │   │   │   │   ├── pipeline_summary_1405.json
│   │   │   │   │   ├── qa_duplication.json
│   │   │   │   │   ├── reingest_dedup_summary.json
│   │   │   │   │   ├── synonym_map_generated.json
│   │   │   │   │   ├── test_questions.json
│   │   │   │   │   ├── test_questions.sha256
│   │   │   │   │   ├── test_questions_iva.json
│   │   │   │   │   ├── test_questions_small.json
│   │   │   │   │   ├── test_questions_tiny.json
│   │   │   │   │   └── versions.lock
│   │   │   │   ├── docs/
│   │   │   │   │   ├── reports/
│   │   │   │   │   ├── retrieval_training/
│   │   │   │   │   ├── index.md
│   │   │   │   │   ├── KV_CHUNKING_PLAN.md
│   │   │   │   │   ├── REMEDIATION_PLAN.md
│   │   │   │   │   ├── synthetic-generation.md
│   │   │   │   │   └── technical-report.md
│   │   │   │   ├── kb_manager/
│   │   │   │   │   ├── chunker/
│   │   │   │   │   ├── cleanup/
│   │   │   │   │   ├── embedder/
│   │   │   │   │   ├── evaluation/
│   │   │   │   │   ├── models/
│   │   │   │   │   ├── parsers/
│   │   │   │   │   ├── pipeline/
│   │   │   │   │   ├── preprocessor/
│   │   │   │   │   ├── retrieval_training/
│   │   │   │   │   ├── versioning/
│   │   │   │   │   ├── web/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── cli.py
│   │   │   │   │   ├── config.py
│   │   │   │   │   ├── dedup.py
│   │   │   │   │   ├── dense.py
│   │   │   │   │   ├── famteb.py
│   │   │   │   │   ├── hyde.py
│   │   │   │   │   ├── llm.py
│   │   │   │   │   ├── query_enhance.py
│   │   │   │   │   ├── query_expansion.py
│   │   │   │   │   ├── query_reform.py
│   │   │   │   │   ├── reranker.py
│   │   │   │   │   ├── synonym_eda.py
│   │   │   │   │   └── synonym_generator.py
│   │   │   │   ├── scripts/
│   │   │   │   │   ├── retrieval_training/
│   │   │   │   │   ├── cleanup_incomplete_qa.py
│   │   │   │   │   ├── init_db.sql
│   │   │   │   │   └── seed_data.py
│   │   │   │   ├── synthetic_generation/
│   │   │   │   │   ├── generators/
│   │   │   │   │   ├── config.yaml
│   │   │   │   │   └── run_generation.py
│   │   │   │   ├── tests/
│   │   │   │   │   ├── retrieval_training/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── conftest.py
│   │   │   │   │   ├── test_characterization.py
│   │   │   │   │   ├── test_chunker.py
│   │   │   │   │   ├── test_cli.py
│   │   │   │   │   ├── test_embedder.py
│   │   │   │   │   ├── test_evaluation.py
│   │   │   │   │   ├── test_ingestion_suite.py
│   │   │   │   │   ├── test_kb_history.py
│   │   │   │   │   ├── test_parsers.py
│   │   │   │   │   ├── test_pipeline.py
│   │   │   │   │   ├── test_preprocessor.py
│   │   │   │   │   ├── test_qa_massive.py
│   │   │   │   │   ├── test_query_enhance.py
│   │   │   │   │   └── test_xlsx_parser.py
│   │   │   │   ├── versions/
│   │   │   │   │   ├── v1/
│   │   │   │   │   ├── v10_1405-06-23/
│   │   │   │   │   ├── v11_1405-06-23/
│   │   │   │   │   ├── v2/
│   │   │   │   │   ├── v4_retrieval/
│   │   │   │   │   ├── v6/
│   │   │   │   │   └── v7_iva_1405-05-31/
│   │   │   │   ├── .gitignore
│   │   │   │   ├── _config.yml
│   │   │   │   ├── BENCHMARK_COMPARISON.md
│   │   │   │   ├── build_iva_dataset.py
│   │   │   │   ├── compare_benchmarks.py
│   │   │   │   ├── create_comparison_plots.py
│   │   │   │   ├── create_small_dataset.py
│   │   │   │   ├── create_tiny_dataset.py
│   │   │   │   ├── create_v7_snapshot.py
│   │   │   │   ├── docker-compose.yml
│   │   │   │   ├── Dockerfile
│   │   │   │   ├── Gemfile
│   │   │   │   ├── generate_test_questions.py
│   │   │   │   ├── IMPLEMENTATION_PLAN.md
│   │   │   │   ├── ingest.py
│   │   │   │   ├── ingest_full.py
│   │   │   │   ├── Inspect
│   │   │   │   ├── kb_root.json
│   │   │   │   ├── opencode.json
│   │   │   │   ├── persian-rag-kb-architecture-with-pgvector-design.json
│   │   │   │   ├── PERSIAN_RESOURCES.md
│   │   │   │   ├── PLAN.md
│   │   │   │   ├── pyproject.toml
│   │   │   │   ├── README.md
│   │   │   │   ├── regen.py
│   │   │   │   ├── regen_test_questions.py
│   │   │   │   ├── reingest.py
│   │   │   │   ├── reingest_dedup.py
│   │   │   │   ├── repair_chunks.py
│   │   │   │   ├── restart_now.py
│   │   │   │   ├── ruff.toml
│   │   │   │   ├── run_benchmark.py
│   │   │   │   ├── run_benchmark_quick.py
│   │   │   │   ├── run_eval.py
│   │   │   │   ├── run_iva_eval.py
│   │   │   │   ├── run_iva_test.py
│   │   │   │   ├── run_server.py
│   │   │   │   ├── start_orchestrator.py
│   │   │   │   ├── start_server.py
│   │   │   │   ├── start_server_detached.py
│   │   │   │   ├── warm.py
│   │   │   │   └── write_v7_results.py
│   │   │   ├── kb-source/
│   │   │   │   ├── 1405-05-31/
│   │   │   │   │   ├── (done)حقوقی/
│   │   │   │   │   ├── (done)حقیقی/
│   │   │   │   │   ├── TestQuestions_IVA/
│   │   │   │   │   ├── سایر/
│   │   │   │   │   └── فنی/
│   │   │   │   ├── 1405-06-23/
│   │   │   │   │   ├── حقوقی/
│   │   │   │   │   ├── حقیقی/
│   │   │   │   │   ├── سایر/
│   │   │   │   │   └── ضمیمه پایگاه دانش چت بات/
│   │   │   │   ├── archives/
│   │   │   │   │   └── KB_31Tir1405_clean.zip
│   │   │   │   ├── KB_9.7.2026/
│   │   │   │   │   ├── حقیقی/
│   │   │   │   │   └── سایر/
│   │   │   │   ├── .gitignore
│   │   │   │   ├── 1405-06-23.zip
│   │   │   │   ├── KB-Source.zip
│   │   │   │   ├── KB_9.7.2026.zip
│   │   │   │   └── README.md
│   │   │   ├── .gitignore
│   │   │   ├── .gitmodules
│   │   │   ├── apply_conservative.py
│   │   │   ├── debug_tsv.py
│   │   │   ├── KB_ARCHITECTURE.md
│   │   │   ├── opencode.json
│   │   │   ├── prismal_architecture.svg
│   │   │   ├── README.md
│   │   │   ├── retrieval-evaluation-research.md
│   │   │   ├── SKILL.md
│   │   │   └── start_guardrails.py
│   │   ├── openwebui-filters/
│   │   │   ├── rag_trace_capture.py
│   │   │   ├── rate_with_comment.py
│   │   │   ├── README.md
│   │   │   └── view_pipeline.py
│   │   ├── orchestrator/
│   │   │   ├── src/
│   │   │   │   └── work_rag_orchestrator/
│   │   │   │       ├── clients/
│   │   │   │       ├── nodes/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── api.py
│   │   │   │       ├── config.py
│   │   │   │       ├── faq_direct.py
│   │   │   │       ├── graph.py
│   │   │   │       ├── rewrite.py
│   │   │   │       ├── schemas.py
│   │   │   │       ├── state.py
│   │   │   │       └── tracing.py
│   │   │   ├── tests/
│   │   │   │   ├── test_memory_coref.py
│   │   │   │   └── test_orchestrator.py
│   │   │   ├── .gitignore
│   │   │   ├── Dockerfile
│   │   │   ├── langgraph.json
│   │   │   ├── pyproject.toml
│   │   │   ├── README.md
│   │   │   ├── STUDIO.md
│   │   │   └── studio_graph.py
│   │   ├── server-setup/
│   │   │   ├── archive/
│   │   │   │   └── app.py.bak
│   │   │   ├── deploy/
│   │   │   │   ├── gateway/
│   │   │   │   │   ├── index.html
│   │   │   │   │   └── index.public.html
│   │   │   │   ├── monitoring/
│   │   │   │   │   ├── grafana/
│   │   │   │   │   ├── docker-compose.yml
│   │   │   │   │   ├── otel-config.yml
│   │   │   │   │   └── prometheus.yml
│   │   │   │   ├── docker-compose.vast.yml
│   │   │   │   ├── docker-compose.yml
│   │   │   │   ├── recreate_webui.sh
│   │   │   │   └── setup_data_plane.py
│   │   │   ├── docs/
│   │   │   │   ├── guides/
│   │   │   │   │   ├── 01-environment.md
│   │   │   │   │   ├── 02-engines-and-libraries.md
│   │   │   │   │   ├── 03-services-and-endpoints.md
│   │   │   │   │   ├── 04-docker-and-storage.md
│   │   │   │   │   ├── 05-models-catalog.md
│   │   │   │   │   ├── 06-model-runnability-fit.md
│   │   │   │   │   ├── 07-download-daemon.md
│   │   │   │   │   ├── 08-sample-projects.md
│   │   │   │   │   └── 09-reboot-runbook.md
│   │   │   │   ├── history/
│   │   │   │   │   ├── 001_2026-08-10_initial_offline_prep.md
│   │   │   │   │   ├── 002_2026-08-11_manual_installs_and_docker.md
│   │   │   │   │   ├── 003_2026-08-15_stabilize_environment.md
│   │   │   │   │   ├── 004_2026-08-15_models_and_services.md
│   │   │   │   │   ├── 005_2026-08-15_token_and_remote_access.md
│   │   │   │   │   ├── 006_2026-08-15_gguf_inference_verification.md
│   │   │   │   │   ├── 007_2026-08-15_model_evaluation.md
│   │   │   │   │   ├── 008_2026-08-16_big_model_inference_eval.md
│   │   │   │   │   ├── 009_2026-08-16_persian_llm_benchmark.md
│   │   │   │   │   ├── 010_2026-08-17_extended_persian_benchmarks.md
│   │   │   │   │   └── README.md
│   │   │   │   ├── reports/
│   │   │   │   │   ├── interactive/
│   │   │   │   │   ├── persian_by_task.png
│   │   │   │   │   ├── persian_eval_report.md
│   │   │   │   │   ├── persian_improvement.png
│   │   │   │   │   ├── persian_mean.png
│   │   │   │   │   ├── persian_nshot.png
│   │   │   │   │   ├── persian_parallel.csv
│   │   │   │   │   ├── persian_parallel.json
│   │   │   │   │   ├── persian_parallel.png
│   │   │   │   │   ├── persian_prompt_compare.md
│   │   │   │   │   ├── persian_radar.png
│   │   │   │   │   ├── persian_radar_family.png
│   │   │   │   │   ├── persian_sample_questions.md
│   │   │   │   │   ├── persian_scatter.png
│   │   │   │   │   ├── persian_speed.png
│   │   │   │   │   ├── persian_spider.png
│   │   │   │   │   ├── persian_temperature.png
│   │   │   │   │   └── README_runbook_outline.md
│   │   │   │   ├── findings.md
│   │   │   │   ├── gemma_endpoints.md
│   │   │   │   ├── manager_openapi_curls.md
│   │   │   │   ├── plan.md
│   │   │   │   ├── README.md
│   │   │   │   └── REPORT.md
│   │   │   ├── docs-site/
│   │   │   │   ├── _reports/
│   │   │   │   │   ├── 01-models-sorted-by-mean-accuracy.md
│   │   │   │   │   ├── 02-model-details-architecture-creator-license-deployment.md
│   │   │   │   │   ├── 03-ability-group-scores-radar-chart-data.md
│   │   │   │   │   ├── 04-figures.md
│   │   │   │   │   ├── 05-improved-prompting-vs-vanilla.md
│   │   │   │   │   ├── 06-few-shot-scaling-0-1-2-3-5-shot.md
│   │   │   │   │   ├── 07-effect-of-temperature.md
│   │   │   │   │   ├── 07-sample-questions.md
│   │   │   │   │   ├── 08-prompt-engineering-qa.md
│   │   │   │   │   ├── 08-same-question-all-models-first-example-per-task.md
│   │   │   │   │   ├── 09-embeddings.md
│   │   │   │   │   ├── 09-per-model-samples.md
│   │   │   │   │   ├── 10-history-001_2026-08-10_initial_offline_prep.md
│   │   │   │   │   ├── 11-history-002_2026-08-11_manual_installs_and_docker.md
│   │   │   │   │   ├── 12-history-003_2026-08-15_stabilize_environment.md
│   │   │   │   │   ├── 13-history-004_2026-08-15_models_and_services.md
│   │   │   │   │   ├── 14-history-005_2026-08-15_token_and_remote_access.md
│   │   │   │   │   ├── 15-history-006_2026-08-15_gguf_inference_verification.md
│   │   │   │   │   ├── 16-history-007_2026-08-15_model_evaluation.md
│   │   │   │   │   ├── 17-history-008_2026-08-16_big_model_inference_eval.md
│   │   │   │   │   ├── 18-history-009_2026-08-16_persian_llm_benchmark.md
│   │   │   │   │   └── 19-history-010_2026-08-17_extended_persian_benchmarks.md
│   │   │   │   ├── assets/
│   │   │   │   │   └── plots/
│   │   │   │   ├── _config.yml
│   │   │   │   ├── Gemfile
│   │   │   │   └── index.md
│   │   │   ├── e2e-test/
│   │   │   │   ├── corpus/
│   │   │   │   │   ├── docker.md
│   │   │   │   │   ├── gpu.md
│   │   │   │   │   ├── kubernetes.md
│   │   │   │   │   ├── llm.md
│   │   │   │   │   ├── monitoring.md
│   │   │   │   │   ├── postgresql.md
│   │   │   │   │   ├── python.md
│   │   │   │   │   ├── rag.md
│   │   │   │   │   ├── redis.md
│   │   │   │   │   ├── security.md
│   │   │   │   │   └── vector-db.md
│   │   │   │   └── qa_ground_truth.json
│   │   │   ├── llm_inference_manager/
│   │   │   │   ├── app.py
│   │   │   │   ├── Dockerfile
│   │   │   │   ├── manager.db
│   │   │   │   ├── requirements.txt
│   │   │   │   └── test_manager.sh
│   │   │   ├── scripts/
│   │   │   │   ├── deepseek_bf16/
│   │   │   │   │   └── requirements.txt
│   │   │   │   ├── services/
│   │   │   │   │   ├── autogit_daemon.sh
│   │   │   │   │   ├── deepseek_server.py
│   │   │   │   │   ├── embed_server.py
│   │   │   │   │   ├── gemma_supervisor.sh
│   │   │   │   │   ├── gpu_metrics_exporter.py
│   │   │   │   │   ├── lightrag_run.sh
│   │   │   │   │   ├── llama_chat_server.py
│   │   │   │   │   ├── run_improved_evals.sh
│   │   │   │   │   ├── run_speed_bench.sh
│   │   │   │   │   ├── run_sweeps.sh
│   │   │   │   │   ├── run_sweeps2.sh
│   │   │   │   │   └── vllm_server.sh
│   │   │   │   ├── auto_status_commit.py
│   │   │   │   ├── bench_speed.py
│   │   │   │   ├── convert_deepseek_raw.py
│   │   │   │   ├── download_embeddings.py
│   │   │   │   ├── download_eval_data.py
│   │   │   │   ├── download_models.py
│   │   │   │   ├── download_persian_eval.py
│   │   │   │   ├── eval_gguf.py
│   │   │   │   ├── eval_persian.py
│   │   │   │   ├── find_tricky_samples.py
│   │   │   │   ├── gen_eval_report.py
│   │   │   │   ├── gen_pages.py
│   │   │   │   ├── gen_prompt_compare.py
│   │   │   │   ├── gen_sample_questions.py
│   │   │   │   ├── opencode_test_session.sh
│   │   │   │   ├── persian_norm.py
│   │   │   │   ├── progress_report.py
│   │   │   │   ├── rag_test_harness.py
│   │   │   │   ├── test_embeddings.py
│   │   │   │   ├── verify_gguf_chat.py
│   │   │   │   └── verify_gguf_inference.py
│   │   │   ├── .gitignore
│   │   │   ├── AGENTS.md
│   │   │   ├── Dockerfile.embed
│   │   │   ├── fix_env.sh
│   │   │   ├── offline_prepare_cli.py
│   │   │   ├── proxy_setup.sh
│   │   │   ├── README.md
│   │   │   ├── README.md.bak.20260823
│   │   │   ├── README.runbook.md
│   │   │   └── start.sh
│   │   └── tracing/
│   │       ├── templates/
│   │       │   └── observability.html
│   │       ├── app.py
│   │       ├── dashboard_api.py
│   │       ├── eval_store.py
│   │       ├── observe.py
│   │       └── README.md
│   ├── contracts/
│   │   ├── kb_retrieval_request.json
│   │   ├── kb_retrieval_result.json
│   │   ├── orchestrator_chat_response.json
│   │   ├── rail_check_request.json
│   │   ├── rail_check_response.json
│   │   └── README.md
│   ├── deploy/
│   │   ├── docker/
│   │   │   ├── docker-compose.override.yml
│   │   │   ├── docker-compose.yml
│   │   │   ├── Dockerfile.llama
│   │   │   └── README.md
│   │   └── vast/
│   │       ├── wave2_assets/
│   │       │   ├── aggregate_bench.py
│   │       │   ├── bench_backbone.py
│   │       │   ├── eval_remapped.json
│   │       │   ├── remap_gold.py
│   │       │   ├── SESSION_WAVE1_HANDOFF.md
│   │       │   └── smoke5.json
│   │       ├── Caddyfile.public
│   │       ├── COMMANDS.md
│   │       ├── health.sh
│   │       ├── langfuse-v2.sh
│   │       ├── start.sh
│   │       ├── stop.sh
│   │       ├── studio.sh
│   │       └── wave2_gpu.sh
│   ├── docs/
│   │   ├── architecture.md
│   │   ├── cross_encoder_benchmark_results.md
│   │   ├── evaluation.md
│   │   ├── GUARDRAILS_V2_PLAN.md
│   │   ├── models.md
│   │   ├── MVP_INTEGRATION_PLAN.md
│   │   ├── README.md
│   │   ├── RERANKER_MEMORY_TASK.md
│   │   ├── RUNBOOK_VAST.md
│   │   └── training.md
│   ├── eval/
│   │   ├── e2e/
│   │   │   └── questions.json
│   │   ├── results/
│   │   │   ├── plots/
│   │   │   │   ├── citations_v2.png
│   │   │   │   ├── citations_v3.png
│   │   │   │   ├── citations_v4.png
│   │   │   │   ├── format_means_v2.png
│   │   │   │   ├── format_means_v3.png
│   │   │   │   ├── format_means_v4.png
│   │   │   │   ├── judge_v2.png
│   │   │   │   ├── judge_v3.png
│   │   │   │   ├── judge_v4.png
│   │   │   │   ├── similarity_hist_v2.png
│   │   │   │   ├── similarity_hist_v3.png
│   │   │   │   ├── similarity_hist_v4.png
│   │   │   │   └── v3-vs-v4.png
│   │   │   ├── baseline.json
│   │   │   ├── llm_answer_benchmark_v2.json
│   │   │   ├── llm_answer_benchmark_v3.json
│   │   │   ├── llm_answer_benchmark_v4.json
│   │   │   ├── llm_judge_v2.json
│   │   │   ├── llm_judge_v3.json
│   │   │   ├── llm_judge_v4.json
│   │   │   ├── qa_samples.json
│   │   │   └── reranker_benchmark_metrics.png
│   │   ├── samples/
│   │   │   ├── benign_credit.json
│   │   │   ├── financial_false_positive.json
│   │   │   ├── hate_toxicity.json
│   │   │   ├── pii.json
│   │   │   └── prompt_injection.json
│   │   ├── __init__.py
│   │   ├── build_report_site.py
│   │   ├── FINDINGS.md
│   │   ├── kb_rag_evaluation_20samples.json
│   │   ├── make_plots.py
│   │   ├── README.md
│   │   ├── run_e2e.py
│   │   ├── run_guardrails_eval.py
│   │   ├── run_llm_answer_benchmark.py
│   │   ├── run_llm_judge.py
│   │   └── test_short_term_history.py
│   ├── handoff/
│   │   ├── bench/
│   │   │   ├── bench_bgem3.json
│   │   │   ├── bench_bgemma25.json
│   │   │   ├── bench_jina.json
│   │   │   ├── bench_minilm-p30.json
│   │   │   ├── bench_minilm.json
│   │   │   ├── bench_minilm25.json
│   │   │   ├── bench_qwen06_smoke.json
│   │   │   ├── bench_qwen4b_gpu800.json
│   │   │   ├── chat_multi.json
│   │   │   ├── chat_rag.json
│   │   │   ├── chat_salam.json
│   │   │   ├── eval_remapped.json
│   │   │   ├── kb_out.json
│   │   │   ├── mem_t2.txt
│   │   │   ├── mem_t3.txt
│   │   │   ├── screen_baseline.json
│   │   │   ├── screen_bgem3-p30.json
│   │   │   ├── screen_minilm-p30.json
│   │   │   ├── smoke5.json
│   │   │   └── strat200.json
│   │   ├── scripts/
│   │   │   ├── aggregate_bench.py
│   │   │   ├── bench_backbone.py
│   │   │   ├── bench_loop.sh
│   │   │   ├── bench_wave2.sh
│   │   │   ├── demo_bgemma_prompt.py
│   │   │   ├── export_session.py
│   │   │   ├── gte_dbg.py
│   │   │   ├── jina_dbg.py
│   │   │   ├── measure_mem.py
│   │   │   ├── migrate_kb.py
│   │   │   ├── minicpm_dbg.py
│   │   │   ├── minicpm_dbg2.py
│   │   │   ├── minicpm_dbg3.py
│   │   │   ├── minicpm_dbg4.py
│   │   │   ├── remap_gold.py
│   │   │   ├── screen_rerank.py
│   │   │   ├── toy_rerank.py
│   │   │   ├── verify_dev.py
│   │   │   ├── verify_extra.py
│   │   │   ├── verify_full.py
│   │   │   └── verify_one.py
│   │   ├── CONTINUE.md
│   │   └── README.md
│   ├── scripts/
│   │   ├── api_cross_encoder_benchmark.py
│   │   ├── bootstrap_gpu_machine.sh
│   │   ├── cross_encoder_benchmark.py
│   │   ├── debug_hurtlex.py
│   │   ├── direct_cross_encoder_benchmark.py
│   │   ├── mock_gemma_manager.py
│   │   ├── run_mvp.ps1
│   │   ├── run_mvp.sh
│   │   ├── system_check.sh
│   │   ├── test_mvp.py
│   │   ├── test_runner_tui.py
│   │   └── test_runner_tui.sh
│   ├── .gitignore
│   ├── .gitmodules
│   ├── AGENTS.md
│   ├── compose.mvp.yml
│   ├── LICENSE
│   └── README.md
```

## Modules & Ownership

| Path | Repo / Branch | Role | Port | Key Entry |
|------|---------------|------|------|-----------|
| `components/server-setup` | Work_RAG-Server-Setup `main` | Hardware, model lifecycle, infra (H200) | 9000/8080-8084 | `llm_inference_manager/app.py:917`, `scripts/services/` |
| `components/knowledgebase` | Work_RAG-KB `master` | KB ingestion, retrieval, reranking | 8000 | `kb-manager/kb_manager/web/app.py`, `web/routes/search.py:753` |
| `components/guardrails` | Work_RAG-Guardrails `main` | Safety policy, guarded Gemma | 8200 | `src/work_rag_guardrails/service.py`, `judge.py` |
| `components/orchestrator` | Work_RAG-Orchestrator `main` | LangGraph API, public gateway | 8100 | `src/work_rag_orchestrator/api.py:113`, `graph.py` |
| `components/tracing` | Parent (not submodule) | Fallback collector, observe | 3000 | `app.py`, `observe.py` |
| `components/openwebui-filters` | Untracked (parent) | WebUI filters & actions | — | `rag_trace_capture.py`, `rate_with_comment.py` |
| `components/knowledgebase/kb-source` | Nested submodule | KB source XLSX/PDF | — | `1405-06-23/`, `1405-05-31/` |
| Parent | Work_Credit-RAG_Phase1 `main` | Umbrella, pins, deploy | 13000/3001/2024 | `deploy/vast/start.sh`, `compose.mvp.yml` |

## Folder Details

- `./` — 950 files
- `archive/` — 66 files
- `docs/` — 10 files
- `deploy/` — 20 files
- `eval/` — 39 files
- `contracts/` — 6 files
- `components/guardrails/` — 39 files
- `components/orchestrator/` — 29 files
- `components/knowledgebase/kb-manager/` — 334 files
- `components/tracing/` — 6 files
- `components/server-setup/` — 171 files
- `scripts/` — 12 files
- `handoff/` — 43 files
