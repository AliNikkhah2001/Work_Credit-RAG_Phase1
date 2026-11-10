# Parent GitHub Pages — report extracts

Sources: `docs/index.html`, `docs/technical.html`, `docs/high-level.html`, `docs/papers/benchmarks.html` (+ titles skim from `docs/papers/index.html`).  
Extracted as original bullets (not HTML dump). Pins and corpus numbers reflect what the Pages HTML lists; live gitlinks may differ.

---

## Platform snapshot

- Self-hosted Persian conversational RAG (Dana Agent Framework); production code in pinned Git submodules; parent owns pins, `deploy/`, E2E eval.
- Deploy targets: Vast.ai (RTX 3090) and H200; Open WebUI frontend branded ICS Helper.
- MVP request path (high level): Browser → WebUI `:13000` → Orchestrator `:8100` → Guardrails input + KB retrieve → guarded generate → citations/trace.

---

## Submodule pins (as listed on Pages)

| Path | Repo | Branch | Pin (HTML) | Owns |
|---|---|---|---|---|
| `components/server-setup` | Work_RAG-Server-Setup | `main` | `ff8c5a8` | Hardware, LLM manager `:9000`, embeds `:8001–8003` |
| `components/knowledgebase` | Work_RAG-KB | `master` | `92503e5` | Ingest, `folder_hierarchy`, `filter_path`, supplement, retrieval `:8000` |
| `components/guardrails` | Work_RAG-Guardrails | `main` | `1002ea8` | Persian safety + guarded Gemma `:8200` |
| `components/orchestrator` | Work_RAG-Orchestrator | `main` | `75cf970` | LangGraph API `:8100`, sticky MemorySaver, evidence guard |
| `components/tracing` | parent (not submodule) | — | — | Fallback collector `:3000`, `observability.db` |
| `agent-state` | ICS_ChatBot_agent-state | `main` | `a0d454e` | Agent context only (not production) |

- HTML note: run `git submodule status --recursive` for live pins.
- Historical pin footnote in changelog: parent `main d1c9b33` + submodules `c3c7476` / `d040c63` / `14c5f97` / `d615f66` (historical; not current live pins).

---

## Corpus / changelog numbers

- **KB corpus (v13, 2026-10-28):** Jalali source folder `1405-07-06` — **18 docs / 1,123 chunks**; features called out: `folder_hierarchy`, `filter_path`, supplement tool (cosine **0.4 / 0.6**), pgvector HNSW.
- Hybrid search description on overview: BM25 tantivy + dense MiniLM-384 + BGE-m3 rerank, RRF **k=60**, over **1123** chunks in pgvector HNSW.
- **v13 orchestrator (2026-10-24):** conditional clarify (`should_clarify` → `generate_clarification`), sticky MemorySaver via `X-Request-ID`, `MAX_CHUNKS=20` / context **9000**, evidence guard **0.15**, grounded follow-ups, DLQ; ambiguity SVM-RBF on **1000-sample** dataset.
- **v12 (2026-10-12):** Guardrails `:8200` Persian rails, HurtLex **19** lemmas, `enable_thinking:false` + `--no-mmproj --jinja`; Gemma 4 31B via `:18000` (Vast) / `:9000` (H200); embed trio `:8001–8003`.
- **v11:** WebUI `:13000` ICS Helper, Arena OFF, `rag_trace_capture` + 4 actions (rate/report/view/truth), `WEBUI_AUTH=false`.
- **v10:** Observability unified dashboard + Langfuse `:3001` + Studio `:2024`.
- **v9:** Multi-agent conversational bench **41 turns**, RAGAS per-subspace; report `docs/benchmark-report-2026-10-12.md`.

---

## Service map (ports)

- Open WebUI `:13000` · Orchestrator `:8100` · KB `:8000` · Guardrails `:8200`
- LLM Manager `:9000` (H200, 11-model registry) · direct Gemma llama-server `:18000` (Vast, loopback)
- Embed servers `:8001–8003` · Trace collector `:3000` · Langfuse `:3001` · Studio `:2024`

---

## Key runtime constants (from technical Pages)

- Search: `POST /search/api` with `top_k=20`; optional `POST /search/supplement` threshold **0.4**
- `build_context`: `MAX_CHUNKS=20`, `MAX_CONTEXT=9000`; abstain if evidence **&lt; 0.15**
- Generation: Gemma 4 31B Instruct, unsloth GGUF **UD-Q4_K_XL** (~**18.8 GiB**), `--ctx-size 8192` (4096 if OOM), `--temp 0.2`, `enable_thinking:false`
- Embedding: `paraphrase-multilingual-MiniLM-L12-v2`, **384-d**
- Reranker: BGE-m3 `BAAI/bge-reranker-v2-m3` (**568M**); fallback MiniLM mmarco (**118M**); `KB_RERANK_POOL` 15 CPU / 30 GPU
- Guardrails Ghadeer mmBERT thresholds: toxicity **0.80**, hate **0.80**, PII **0.90**, injection **0.85**
- Manager: MODEL_REGISTRY **11** models, champion `gemma-4-31b`; backends **8080–8084**

---

## Before/after bench deltas (`docs/papers/benchmarks.html`)

**41-turn multi-agent benchmark** (Before 2026-10-12 → After 2026-10-14):

| Metric | Before | After | Δ |
|---|---:|---:|---|
| Finish mismatches | 6/41 | 0/41 | −6 |
| Retrieval hit | 0.537 | 0.780 | +0.243 |
| Cheque hit | 0.111 | 0.667 | +0.556 |
| Context recall | 0.113 | 0.340 | +0.227 |
| Answer relevancy | 0.212 | 0.568 | +0.356 |
| Ambiguity resolution | 0.854 | 1.000 | +0.146 |
| Sticky persistence | 0.610 | 0.683 | +0.073 |
| p50 latency | 8006 ms | 4872 ms | **−39%** |

**Subspace breakdown (After):**

| Subspace | n | Hit | Faith | Sticky | p50 |
|---|---:|---:|---:|---:|---:|
| Cheque | 9 | 0.667 | 0.422 | 0.444 | 10301 ms |
| Facilities Person | 6 | 0.500 | 0.967 | 0.667 | 10718 ms |
| Facilities Legal | 3 | 0.667 | 0.917 | 0.333 | 10498 ms |
| General | 10 | 0.800 | 0.655 | 0.600 | 6981 ms |

**External / literature anchors on same page:**

- MTRAG (Katsis et al., ACL 2025): **110** conversations, **7.7** turns avg, **842** turns; **87%** non-standalone; ELSER R@5 **0.89 → 0.47** across turns (**51%** degradation).
- MTRAGEval SemEval 2026 Task 8: Task A nDCG@5 (top listed ~**0.5453**); Task C harmonic quality+faithfulness.
- Custom metrics called out for our bench: Ambiguity Resolution, Sticky Persistence, Retrieval Hit.

Reproduce (from page): `evaluation.bench_runner` (~214s) → `evaluation.ragas_eval` → `evaluation.report` → `bench_report_latest.html`.

---

## Open gaps (Pending on technical Pages)

- Clarify gate: **0/6** scattered failures — lower `subspace_threshold` / explicit ambiguous classifier.
- Evidence threshold per-subspace tuning (cheque **0.028** starves hits).
- Sticky carry: generic follow-ups lose `applied_subspace`.
- Generation faithfulness — citation gate too strict on **2** abstains.
- Latency — generation **~5.3 s** dominates; batch Gemma / reranker on GPU.
- Supervision — llama-server `nohup` → proper supervisor.

**Done checklist (same section):** KB v13 filter_path + supplement + HNSW; orchestrator clarify/sticky/evidence/follow-ups; guardrails Persian rails; Gemma via `:18000`/`:9000`; WebUI ICS Helper; observability stack; 41-turn RAGAS bench.

---

## Diagram inventory

### Parent `docs/technical.html` (mermaid pairs)

1. **System Overview — Variant A Detailed Technical** (flowchart TB) — ports, file paths, graph nodes, KB search pipeline, manager registry, collector/Langfuse/Studio.
2. **System Overview — Variant B High-Level Black Box** — Client / RAG platform / Observability only.
3. **Request Flow — Variant A Detailed Technical** (sequenceDiagram) — sticky + filtered RAG; rails check; clarify vs retrieve; `/search/api` + `/search/supplement`; abstain 0.15; guarded generate.
4. **Request Flow — Variant B High-Level Black Box** — simplified sequence.
5. **Orchestrator LangGraph — Variant A Detailed Technical** (flowchart TD) — real node modules, conditional edges `should_continue_after_validation` / `should_route_after_classify` / `should_clarify`.
6. **Orchestrator LangGraph — Variant B High-Level Black Box** — validate → classify → retrieve/clarify → build → generate → format.

### Parent `docs/high-level.html`

- Reuses black-box variants: System Overview, Request Flow, Orchestrator LangGraph (executive captions).

### Non-diagram technical sections (also on technical page)

- Request Lifecycle, Code Structure, API Contracts, Configuration env table, Models & Libraries, Observability & Services, Changelog, Done vs Pending, Verification Commands, Links.

---

## Papers index — title skim (`docs/papers/index.html`)

Categories / representative titles:

- **Subspace & Domain Partitioning:** PC-RAG, SPLIT-RAG, DSRAG, EvoRAG
- **Ambiguity & Clarification:** RAC, ICR, Qulac/ClariQ/ClariT, CLARITY
- **Sticky Context & Memory:** CPP, CALMem, Context Recycling, Rag.NET, OpenAI Sessions
- **Retrieval Fusion & RRF:** GUIR, 5ting, H-RAG, Sifei, IITKanBDone, AILS-NTUA, uva-irlab
- **Faithfulness & Hallucination:** DUTIR, Reflective RAG, 5ting, CoRAG, CoopRAG, CalibRAG
- **Memory Architectures:** CALMem, CPP, Context Recycling, Rag.NET, Scroll
- **Benchmarks & Evaluation:** MTRAG, MTRAGEval, CORAL, RAD-Bench, SemEval 2026 Task 8
- **Advanced RAG:** CoRAG, IM-RAG, CoopRAG, MMOA-RAG, Reflective RAG, CalibRAG

Problem → our-fix mapping on index: subspace → map fix + RRF; ambiguity → scattered gate; sticky → carry + decay; retrieval degradation → RRF + broadened retry; hallucination → faith guard + lexical bypass; latency → GPU embed + rerank pool 30.

Venue counts claimed: SemEval 2026 (8), NeurIPS 2025 (6), ACL 2025 (4), EMNLP 2025 (3), … total **29+** core papers; page header says **40+** papers across venues. Last updated note: October 20, 2026.

---

## Layer separation (index)

- Production: `api/`, `components/`, `contracts/`, `deploy/`, `eval/`, `scripts/`
- Agent-only: `agent-state/`
- Non-production: `dev/`, `archive/`, `deprecated/`
