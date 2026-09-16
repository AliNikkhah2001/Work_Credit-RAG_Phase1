# Work Credit RAG — Phase 1

[![Python](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/downloads/release/python-3110/)
[![License](https://img.shields.io/github/license/AliNikkhah2001/Work_Credit-RAG_Phase1)](LICENSE)
[![Branch](https://img.shields.io/badge/branch-vast--gemma4--migration-orange)]()

Umbrella repository for a self-hosted, Persian-capable conversational RAG platform. The implementation is split into independently maintained Git submodules so model/server operations, knowledge-base lifecycle, safety policy, and LangGraph orchestration can evolve without returning to a monolith.

> **Status:** `vast-gemma4-migration` live on Vast.ai (2026-09-12). `main` is last stable monolith checkpoint (`3ee1780`). Do not merge to `main` until §16 (persistent llama-server) is complete.

---

## Table of Contents

- [Architecture](#architecture)
- [Repository Composition](#repository-composition)
- [MVP Target](#mvp-target)
- [Quick Start](#quick-start)
- [Models](#models)
- [Configuration](#configuration)
- [Observability](#observability)
- [Evaluation](#evaluation)
  - [Retrieval quality (measured)](#retrieval-quality-measured)
- [Done vs Pending](#done-vs-pending)
- [Verification](#verification)
- [Updating a Submodule](#updating-a-submodule)
- [License](#license)
- [Links](#links)

---

## Architecture

### System Overview

```mermaid
flowchart TB
    subgraph Client["Client Layer"]
        Browser["🌐 Browser"]
        WebUI["💬 Open WebUI :13000"]
    end

    subgraph API["API Gateway"]
        Orch["🎯 Orchestrator :8100\nLangGraph + OpenAI-compatible"]
    end

    subgraph Retrieval["Retrieval Layer"]
        KB["📚 KB Manager :8000\nBM25 + Dense + RRF + Rerank"]
    end

    subgraph Safety["Safety Layer"]
        GR["🛡️ Guardrails :8200\nDeterministic Persian rails\nRisk scoring + Semantic"]
    end

    subgraph Generation["Generation Layer"]
        Gemma["🤖 Gemma :18000\nllama.cpp GGUF UD-Q4_K_XL"]
    end

    subgraph Observability["Observability"]
        LF2["📊 Langfuse v2 :3001"]
        LF1["📝 Fallback :3000"]
        Studio["🔍 Studio API :2024"]
        TraceApp["🔎 Tracing App :3000\n/observe, /studio"]
    end

    Browser --> WebUI
    WebUI --> Orch
    Orch --> KB
    Orch --> GR
    GR --> Gemma
    Orch -.-> LF2
    Orch -.-> LF1
    Orch -.-> Studio
    Orch -.-> TraceApp
```

### Request Flow (MVP)

```mermaid
sequenceDiagram
    participant U as User
    participant W as Open WebUI :13000
    participant O as Orchestrator :8100
    participant K as KB Manager :8000
    participant G as Guardrails :8200
    participant M as Gemma :18000
    participant L as Langfuse v2 :3001

    U->>W: Persian question
    W->>O: POST /v1/chat/completions {X-Request-ID, messages[]}
    O->>L: trace-create(input)
    
    O->>G: validate_input (stage=input)
    G-->>O: {allowed, categories, reason}
    
    alt blocked
        O->>O: format_refusal
        O-->>W: refusal, citations: []
    else allowed
        O->>K: retrieve (top_k=5)
        K-->>O: final_results[chunks...]
        O->>O: build_context (MAX_CHUNKS=5, MAX_CONTEXT_CHARS=6000)
        O->>G: guarded_generate
        G->>M: chat/completions {enable_thinking:false}
        M-->>G: answer
        G-->>O: {answer, finish_reason}
        O->>O: format_response (citations)
        O->>L: trace-create upsert(output, metadata)
        O-->>W: {choices:[{message,finish_reason}], rag:{citations:N}}
    end
```

### Orchestrator Graph (LangGraph)

```mermaid
flowchart TD
    START([START]) --> VI[validate_input]
    VI -->|blocked| FR[format_refusal]
    VI -->|allowed| RET[retrieve]
    RET --> BC[build_context]
    BC --> GG[guarded_generate]
    GG --> FRMT[format_response]
    FRMT --> END([END])
    FR --> END
```

---

## Repository Composition

| Path | Repository | Responsibility | Default Branch | Vast Pin |
|------|------------|----------------|----------------|----------|
| `components/server-setup` | [Work_RAG-Server-Setup](https://github.com/AliNikkhah2001/Work_RAG-Server-Setup) | Hardware, model lifecycle, infra (H200) | `main` | `5d5a7e4` |
| `components/knowledgebase` | [Work_RAG-KB](https://github.com/AliNikkhah2001/Work_RAG-KB) | Ingestion, retrieval, reranking (kb-manager) | `master` | `8b8f6e5` |
| `components/guardrails` | [Work_RAG-Guardrails](https://github.com/AliNikkhah2001/Work_RAG-Guardrails) | Policy, guarded Gemma, risk/semantic | `main` | `6ce319f` |
| `components/orchestrator` | [Work_RAG-Orchestrator](https://github.com/AliNikkhah2001/Work_RAG-Orchestrator) | LangGraph workflow, public API | `main` | `cdb6e7d` |

Each gitlink is pinned to an exact commit. Updating a component requires a component-repo commit followed by a parent-repo commit that advances the gitlink.

```bash
git submodule status --recursive
# 6ce319f... components/guardrails (heads/vast-gemma4-migration)
# 8b8f6e5...       components/knowledgebase (heads/vast-gemma4-migration)
# cdb6e7d...       components/orchestrator (heads/vast-gemma4-migration)
# 5d5a7e4...       components/server-setup (heads/vast-gemma4-migration)
```

---

## MVP Target

The first goal is one small, deterministic, observable request path:

```mermaid
flowchart LR
    UI["Open WebUI :13000"] --> ORCH["LangGraph API :8100"]
    ORCH --> KB["KB retrieval :8000"]
    ORCH --> GR["Guardrails :8200"]
    GR --> GEMMA["Gemma :18000 external llama-server"]
```

**Request order:**

```text
browser :13000 → Open WebUI → Orchestrator :8100
  → KB :8000 hybrid retrieval (BM25 + MiniLM-384 + RRF + mmarco cross-encoder)
  → context construction (MAX_CHUNKS=5, MAX_CONTEXT_CHARS=6000)
  → Guardrails :8200 → Gemma :18000 (unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL)
  → citation-shaped response (rag.citations) → frontend
```

**Excluded from MVP:** long-term memory, PostgreSQL LangGraph checkpoints, query rewriting, agent loops, retrieval retries, streaming, GraphRAG, multi-agent routing, Kubernetes.

Detailed plan: [docs/MVP_INTEGRATION_PLAN.md](docs/MVP_INTEGRATION_PLAN.md)

---

## Quick Start

### Vast.ai (Host Venvs — Docker Unprivileged)

```bash
# 1. Clone with submodules
git clone --recurse-submodules https://github.com/AliNikkhah2001/Work_Credit-RAG_Phase1.git
cd Work_Credit-RAG_Phase1
git switch vast-gemma4-migration
git submodule sync --recursive && git submodule update --init --recursive

# 2. Full startup (postgres → Gemma → KB → guardrails → collector → orchestrator → WebUI)
bash deploy/vast/start.sh

# 3. Health check
bash deploy/vast/health.sh

# 4. Access via SSH tunnel
ssh -p <ssh_port> root@<ssh_host> \
  -L 13000:localhost:13000 -L 8100:localhost:8100 \
  -L 3000:localhost:3000 -L 3001:localhost:3001 -L 2024:localhost:2024
# Open http://localhost:13000 (WebUI)
# Open http://localhost:3001 (Langfuse, admin@local.test / Langfuse-Admin-139b81ba)
# Open http://localhost:3000/observe (local trace viewer)
# Open http://localhost:3000/studio (local graph debugger)
```

### Docker (Privileged Host Only)

```bash
cd deploy/docker
cp .env.example .env   # Set MODEL_FILE to your Gemma GGUF path
docker compose up -d --build
# WebUI at http://<host>:13000
```

---

## Models

| Role | Model | Version | Size | Key Config |
|------|-------|---------|------|------------|
| **Generation** | Gemma 4 31B Instruct | `unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL` | 18.8 GiB | `--no-mmproj --jinja --ctx-size 8192 --temp 0.2` + `chat_template_kwargs:{"enable_thinking":false}` |
| **Embedding** | paraphrase-multilingual-MiniLM-L12-v2 | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 384-dim | `KB_EMBED_DEVICE=cpu/cuda` |
| **Reranker** | mmarco-mMiniLMv2-L12-H384-v1 | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` | 118M | `KB_RERANK_POOL=50`, `KB_RERANKER_DEVICE=cpu/cuda` |
| **Guardrails** | Ghadeer mmBERT (toxicity/hate/intent) | — | — | F1 0.94 Persian, thresholds: toxicity 0.80, hate 0.80, PII 0.90, injection 0.85 |

**Model Cards:** [docs/models.md](docs/models.md)

---

## Configuration

### Key Environment Variables

| Component | Variable | Default | Production |
|-----------|----------|---------|------------|
| **Gemma** | `MODEL` | — | `/tmp/hf_clean/.../gemma-4-31B-it-UD-Q4_K_XL.gguf` |
| | `CTX_SIZE` | 8192 | 8192 (4096 if OOM) |
| **KB** | `KB_DB_URL` | `sqlite+aiosqlite:///./data/kb_test.db` | `postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/kb_manager` |
| | `KB_WEB_HOST` | `0.0.0.0` | `0.0.0.0` |
| | `KB_WEB_PORT` | 8000 | 8000 |
| | `KB_EMBED_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | same |
| | `KB_EMBED_DEVICE` | `cpu` | `cuda` (on GPU host) |
| | `KB_RERANKER_MODEL` | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` | same |
| | `KB_KEYWORD_BOOST` | 3.0 | 3.0 |
| **Guardrails** | `GUARDRAILS_HOST` | `0.0.0.0` | `0.0.0.0` |
| | `GUARDRAILS_PORT` | 8200 | 8200 |
| | `UPSTREAM_LLM_BASE_URL` | `http://127.0.0.1:9000/v1` | `http://127.0.0.1:18000/v1` (via `LLM_BASE_URL` alias) |
| | `UPSTREAM_LLM_MODEL` | `gemma-4-31b` | `unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL` |
| **Orchestrator** | `KB_BASE_URL` | `http://127.0.0.1:8000` | `http://127.0.0.1:8000` |
| | `GUARDRAILS_BASE_URL` | `http://127.0.0.1:8200` | `http://127.0.0.1:8200` |
| | `LANGFUSE_HOST` | `http://127.0.0.1:3000` | `http://127.0.0.1:3001` |
| | `LANGFUSE_PUBLIC_KEY` | `pk-lf-mvp-local` | from `/tmp/opencode/langfuse.env` |
| | `LANGFUSE_SECRET_KEY` | `sk-lf-mvp-local` | from `/tmp/opencode/langfuse.env` |
| | `TRACE_ENABLED` | `true` | `true` |
| **WebUI** | `OPENAI_API_BASE_URL` | — | `http://127.0.0.1:8100/v1` |
| | `OPENAI_API_KEY` | — | `sk-local-dev` |
| | `WEBUI_AUTH` | `false` | `false` |
| | `DATA_DIR` | — | `/tmp/webui-data` |

**Full reference:** [docs/architecture.md](docs/architecture.md#environment-variables)

---

## Observability

| Tool | URL | Purpose |
|------|-----|---------|
| **Langfuse v2** | `http://localhost:3001` (via tunnel) | Full trace UI, Postgres-backed. Login: `admin@local.test` / `Langfuse-Admin-139b81ba` |
| **Fallback Collector** | `http://localhost:3000` | JSONL at `/tmp/langfuse_traces.jsonl`, ingestion API compatible |
| **Local Trace Viewer** | `http://localhost:3000/observe` | Request list → timeline (request → validate_input → retrieve → build_context → guarded_generate → format_response) |
| **Local Graph Debugger** | `http://localhost:3000/studio` | Runs `rag` graph via :2024 API server-side, shows state + observe link |
| **LangGraph Studio** | `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024` | Visual debugger (needs `-L 2024:localhost:2024` tunnel) |

**CLI:**
```bash
# List recent requests
python components/tracing/observe.py --list --limit 10

# Full timeline for request_id
python components/tracing/observe.py --request <request_id>
python components/tracing/observe.py --request <request_id> --json
```

---

## Evaluation

### Retrieval quality (measured)

Wave-1 full-800 reranker shootout, CPU (2026-09-12/13). Dataset: 800 Persian QA, answer-grounded golds remapped to the live 2077-chunk PG KB (threshold 0.6, 772/800 covered, ~7 gold/query), top_k=5. Method: `docs/WAVE2_GPU_RUNBOOK.md` §1.

| Backbone | Pool | Hit@5 | Top-1 | MRR | s/q (CPU) |
|---|---|---|---|---|---|
| **BGE-m3 `BAAI/bge-reranker-v2-m3` (default)** | 15 | 0.536 | 0.474 | **0.496** | ~5–15 (rerank solo; pool-15 production cap) |
| MiniLM-L12 `mmarco-mMiniLMv2-L12-H384-v1` (lightweight fallback) | 15 | 0.536 | 0.469 | 0.493 | 3.9 |
| MiniLM-L12 | 30 | 0.538 | — | 0.495 | 7.4 |
| BGE-m3 `BAAI/bge-reranker-v2-m3` | 30 | 0.536 | 0.474 | 0.496 | 52 |
| Jina-v3 | — | EXCLUDED | — | 0.117 | — |

Decision (2026-09-15): **default is `BAAI/bge-reranker-v2-m3`** — best measured MRR (0.496; hit 0.536, top1 0.474 on 800 Persian credit queries, top-5) plus multilingual/Persian backbone support (see below). MiniLM stays as the lightweight CPU fallback (`KB_RERANKER_MODEL=cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`: 0.493 at pool15, 0.495 at pool30 — within 0.003 at a fraction of the latency). Jina-v3 excluded (classification head failed to load under transformers 5: "MISSING params newly initialized" → near-random scores, MRR 0.117 — not a quality signal). bgemma-2B interim (identical 25-query slice, pool15, detailed prompt): 0.44/0.44/0.186 @ 64 s/q vs MiniLM 0.44/0.44/0.191 @ 6.2 s/q — identical ranking at ~10x cost; heavies must prove on GPU full-800. Qwen3-Reranker-4B (think-disabled, GPU): MRR 0.233 — decisively behind. Production CPU note: 568M → `KB_RERANK_POOL=15`; GPU hosts can raise to 30.

**Persian support:** v2-m3's backbone is BGE-M3 (XLM-RoBERTa-Large base, 568M params, 2.27GB, Apache-2.0) with multilinguality over 100+ languages including Persian; SOTA on MIRACL multilingual (includes Persian `fa`) and MKQA cross-lingual; vendor BGE docs explicitly recommend v2-m3 "for multilingual". Plain cross-encoder loader — no `trust_remote_code`. Default is set in code (`reranker.py _DEFAULT_MODEL`, `config.py RerankerConfig`, `search.py _RERANKER_MODEL` fallback; KB `master` `8d0c506`) and live on production KB `:8000` via `KB_RERANKER_MODEL` + `KB_RERANK_POOL=15`.

Full method + GPU next steps: `docs/WAVE2_GPU_RUNBOOK.md`, `deploy/vast/wave2_gpu.sh`. Bench data + session transcripts: `handoff/`.

### Massive stage-level benchmark (current)

Status: **DIAGNOSIS FOUND, fix under test** (2026-09-16). Extends the repo's benchmark
infra (`kb_manager/evaluation/`) with per-stage capture (BM25 / Dense / RRF / CrossEncoder).

> Reproducibility note: the shared PG corpus changed mid-campaign (3308→1253→3330
> chunks, concurrent re-ingests). All runs now record a corpus fingerprint
> (count + ID hash + embedding coverage, start/end) and abort-flag on drift.
> Baseline-v1 numbers below predate the guard; baseline-v2 re-runs everything
> on fingerprinted corpus `0368bdd4` (3330 chunks, 1253 embedded).

- Ground truth: `benchmark/datasets/eval_remapped.json` — 796/800 eval_clean questions
  remapped to the live 3330-chunk KB by answer-token coverage ≥ 0.6
  (graded relevance = coverage; 4 empty-answer + 20 zero-gold excluded from means).
  Primary golds = source QA rows fuzzy-matched by question text (certain if F1 ≥ 0.7).
  Stale `expected_chunk_ids` (0% coverage on current KB) are NOT used.
- Pipeline: production code path (`search_knowledge_base`, top_k=20, pool=15,
  `BAAI/bge-reranker-v2-m3`), stage lists kept to depth 100, CE ranking pool-capped at 15.
- Metrics: Recall/Hit/NDCG @1,3,5,10,20,50,100 + MRR per stage, candidate recall,
  RRF/CE gain-loss, failure categories. Validated against hand-computed cases
  (`benchmark/test_metrics.py`) and cross-checked with `kb_manager` metrics.
- Artifacts: `benchmark/raw/massive_results.jsonl` (local; aggregates committed),
  `benchmark/metrics/`, `benchmark/diagnostics/`, `benchmark/plots/`.
  Harness: `benchmark/run_massive.py`; analysis: `benchmark/analyze.py`; plots: `benchmark/plots.py`.

**Baseline (n=776, certain-primary view, n=424):**
BM25 hit@5 0.658 · Dense 0.384 · RRF 0.762 · CE 0.859 (pool cap).

**ROOT CAUSE (measured):** the `KB_KEYWORD_BOOST=3.0` score addition
(`content + 3×keyword`, unnormalized scales) buries exact matches: a verbatim
query whose true chunks rank BM25-content #1/#2 drops to #113/#118 after the
boost, because generic shared keywords flood the ranking. Keyword leg alone
ranks the same golds #2484/#760.
**Cross-encoder exonerated:** zero true demotions (all 44 "CE failures" are
pool-cap misses at RRF 16–100); CE hit@1 jumps 0.500→0.762.
**Dense is the weakest leg** (hit@5 0.384 vs BM25 0.658) — second fix candidate.
Fix experiment running: boost ∈ {0, 1.0} ablation on stratified 199-query subset.

### Cross-Encoder Reranker Direct API Benchmark (2026-09-15)

Direct API benchmark on 20 Persian credit queries, KB v8 (6593 chunks), rerankers on CPU (GPU OOM). Latency measured per-query (BM25+Dense+RRF search → rerank 50→5).

| Model | Params | Loader | Avg Rerank (ms) | Search (ms) | Status |
|---|---|---|---|---|---|
| **mmarco (baseline)** | 118M | crossencoder | **628** | 902 | ✅ Production |
| **bge-reranker-v2-m3** | 568M | crossencoder | 3,754 | 660 | ⚠️ 6× slower |
| bge-reranker-v2-gemma | 2.5B | flag-llm | 43,000 | - | ❌ CPU too slow |
| Qwen3-Reranker-0.6B | 0.6B | flag-llm | 30,000 | - | ❌ CPU too slow |
| Qwen3-Reranker-4B | 4B | flag-llm | — | — | ⏳ Pending |
| jina-reranker-v3 | 0.6B | crossencoder | — | — | ⏳ Pending |
| gte-multilingual-reranker-base | ~300M | crossencoder | — | — | ⏳ Pending |

**Key Findings:**
- **mmarco (baseline)** remains best CPU production choice: 628 ms rerank, fastest overall
- **bge-reranker-v2-m3** gains expected quality but 6× slower (3.7s vs 0.6s) — only justified on GPU (1.6× speedup)
- **Flag-LLM loaders** (bge-gemma, Qwen3) are LLM-based rerankers → 30-43s/query on CPU → **not viable for CPU production**
- GPU would give ~1.6× speedup for crossencoder models (HNSW 1.6×, rerank 1.6×) but flag-llm still needs GPU

Full results: `docs/cross_encoder_benchmark_results.md`, raw data: `data/reranker_benchmarks/`

### KB Retrieval (v8, 6593 chunks, RTX 6000 Ada)

| Variant | Device | Avg Latency | Hit@5 (5q verbatim) | Rerank 50 |
|---------|--------|-------------|---------------------|-----------|
| File-based | CPU | ~22.7s | 0.00* | 439ms |
| HNSW pgvector CPU | CPU | 23.1s | 0.00 | 439ms |
| **HNSW pgvector GPU** | **cuda:0** | **18.4s** | 0.00 | **279ms 1.6×** |

*Hit 0/5 on 5q verbatim after re-ingest (mismatched expected IDs). IVA 15 still 73.3% baseline.

### RAG End-to-End (120 questions, after fixes)

| Metric | Result |
|--------|--------|
| 20 diverse samples | **20/20 ok** |
| 120 input guardrail check | **0/120 blocked** |
| 120 output guardrail check | **0/120 blocked** |
| Finish `stop` rate | 120/120 |
| Citations per answer | ≤ 2 (max 2 enforced) |

### LLM-as-Judge (v4 Q8 prompt)

| Metric | Score |
|--------|-------|
| Mean cosine similarity | 0.620 |
| Judge pass rate | 45% |
| Faithfulness / Correctness / Tone / Citation | 3.65 / 3.14 / 4.90 / 4.95 |

**Reproduction:**
```bash
python eval/run_llm_answer_benchmark.py --out eval/results/llm_answer_benchmark_v4.json
python eval/run_llm_judge.py eval/results/llm_answer_benchmark_v4.json --out eval/results/llm_judge_v4.json
python eval/make_plots.py ...
python eval/build_report_site.py  # GitHub Pages at docs/benchmark-report/
```

**Full details:** [docs/evaluation.md](docs/evaluation.md)

---

## Done vs Pending

### Done ✓

- [x] **Branches** `vast-gemma4-migration` on parent + 4 submodules, pinned and pushed
- [x] **Environment** validated (1× RTX 3090 24GB, CUDA 12.x, no proxy, host venvs)
- [x] **KB** v8 pgvector HNSW: 103 docs, 6593 chunks, hybrid retrieval verified
- [x] **Guardrails** deterministic Persian rails, HurtLex allowlist 19 lemmas, risk scoring, semantic interface
- [x] **Orchestrator** LangGraph 5 nodes, Persian-only prompt, MAX_CHUNKS=5, 5 citations
- [x] **Gemma source fix** — llama.cpp 0f3a71b, `--no-mmproj --jinja`, `enable_thinking:false` → clean Persian
- [x] **HurtLex allowlist** — 19 lemmas with evidence, 26 tests pass, 0/120 blocked
- [x] **Compose** `compose.mvp.yml` (no gemma-manager, only 13000 public)
- [x] **Docs** RUNBOOK_VAST, VAST_GEMMA4_MIGRATION, MVP_INTEGRATION_PLAN, GUARDRAILS_V2_PLAN
- [x] **Public URL** `http://91.108.80.253:13000` verified
- [x] **Commits** all pushed to `main` and `vast` branches, no force-push

### Pending ⏳

- [ ] **Make llama-server persistent** — currently `nohup` manual, need supervisor with `LD_LIBRARY_PATH=/opt/llama-new/lib:/usr/local/cuda/lib64`
- [ ] **Docker privileged** — Vast host unprivileged (`unshare` denied); need privileged host or host-network fallback
- [ ] **KB completeness** — 5 XLSX fail `No valid sheets`; `dense_embeddings.npz` git-ignored
- [ ] **Vast port mapping** — 13000 not in instance ports; reachable via host but should be explicit
- [ ] **HurtLex coverage** — audit future false positives via 30-text script
- [ ] **Orchestrator fallback cleanup** — decide on duplicate fallback in `format_response`
- [ ] **Merge to `main`** — after llama-server persistent + 13000 mapping explicit

---

## Verification

```bash
# Gemma raw clean (5 prompts)
curl -s http://127.0.0.1:18000/v1/models | jq .data[0].id
for p in "سلام" "Hello" "اعتبارسنجی چیست" "چگونه گزارش اعتباری خود را دریافت کنم؟" "یک پاسخ کوتاه فارسی بده"; do
  curl -s http://127.0.0.1:18000/v1/chat/completions -H 'Content-Type: application/json' \
    -d "{\"model\":\"unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL\",\"messages\":[{\"role\":\"user\",\"content\":\"$p\"}],\"temperature\":0,\"max_tokens\":50,\"chat_template_kwargs\":{\"enable_thinking\":false}}" \
    | python3 -c "import json,sys; j=json.load(sys.stdin); c=j['choices'][0]['message']['content']; print('$p', 'has_unused', '<unused' in c, 'len', len(c))"
done

# Guardrails allowlist (26 tests) + baseline
PYTHONPATH=components/guardrails/src /tmp/guard-venv/bin/python -m pytest components/guardrails/tests/test_hurtlex_allowlist.py -v
PYTHONPATH=components/guardrails/src /tmp/guard-venv/bin/python /workspace/Work_Credit-RAG_Phase1/eval/run_guardrails_eval.py

# RAG E2E
curl -s http://127.0.0.1:8100/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"چگونه می‌توانم گزارش اعتباری خود را دریافت کنم؟"}]}' \
  | jq '{finish:.choices[0].finish_reason, citations:(.rag.citations|length), content:.choices[0].message.content}'

# Observe CLI
python components/tracing/observe.py --list --limit 5
python components/tracing/observe.py --request <request_id> --json
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

Always run contract and end-to-end tests before advancing a production pin.

---

## License

See [LICENSE](LICENSE). Each submodule may also declare its own license and dependency obligations.

---

## Links

- **Runbook** (startup, env, ports, troubleshooting): [docs/RUNBOOK_VAST.md](docs/RUNBOOK_VAST.md)
- **Migration log** (discovery, fixes, HurtLex audit): [docs/VAST_GEMMA4_MIGRATION.md](docs/VAST_GEMMA4_MIGRATION.md)
- **MVP plan & acceptance tests**: [docs/MVP_INTEGRATION_PLAN.md](docs/MVP_INTEGRATION_PLAN.md)
- **Compose (Vast)**: [compose.mvp.yml](compose.mvp.yml) + [server-setup/deploy/docker-compose.vast.yml](components/server-setup/deploy/docker-compose.vast.yml)
- **Guardrails allowlist**: [components/guardrails/kb/hurtlex_allowlist.json](components/guardrails/kb/hurtlex_allowlist.json) + [actions.py](components/guardrails/src/work_rag_guardrails/actions.py)
- **Tests**: [guardrails tests](components/guardrails/tests/test_hurtlex_allowlist.py) (26), [orchestrator tests](components/orchestrator/tests) (9), [KB tests](components/knowledgebase/kb-manager/tests) (32)
- **Architecture docs**: [docs/architecture.md](docs/architecture.md), [docs/models.md](docs/models.md), [docs/evaluation.md](docs/evaluation.md), [docs/training.md](docs/training.md)