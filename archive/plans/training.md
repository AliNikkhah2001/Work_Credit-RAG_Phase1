# Training & Pipeline — Work Credit RAG Phase 1

> This is primarily an **inference-time RAG system**. No LLM fine-tuning is performed in the MVP. This document covers the retrieval pipeline "training" (indexing, embedding, reranker selection) and data preparation.

---

## 1. KB Ingestion Pipeline

```mermaid
flowchart LR
    SRC[Source XLSX\nkb-source/clean_files\n78 files] --> PARSE[XLSX Parser\nschema auto-detect]
    PARSE --> NORM[Persian Normalize\nZWNJ, Unicode cleanup]
    NORM --> CHUNK[Semantic Chunking\n1 row = 1 chunk\nQA pairs, reason codes, articles]
    CHUNK --> EMBED[Dense Embeddings\nMiniLM-L12 384-dim\ncontextual: title+heading]
    EMBED --> STORE[Store\npgvector HNSW\n+ .npz cache]
    STORE --> BM25[BM25 Index\nOkapi + char 3-grams\nkeyword 3× boost]
```

### Stages

| Stage | Module | Key Features |
|-------|--------|--------------|
| **Parse** | `parsers/xlsx_parser.py` | openpyxl/calamine, header normalization, schema overlap ≥60% |
| **Normalize** | `preprocessor/persian.py` | ZWNJ (ی/ي, ک/ك), Unicode cleanup, `~$` temp file skip |
| **Chunk** | `chunker/semantic.py` | Structure-aware: QA pairs, reason codes, articles; 1 row = 1 chunk |
| **Embed** | `dense/dense_index.py` | MiniLM-L12-v2, batch 64, `.npz` cache, contextual embeddings |
| **BM25** | `search.py` | Okapi BM25, Persian tokenizer, char 3-grams for typo robustness |
| **Rerank** | `reranker/cross_encoder.py` | CrossEncoder, pool 50, top-k 5, per-call latency logged |

### Version History

| Version | Corpus | Chunks | Pipeline | Key Changes |
|---------|--------|--------|----------|-------------|
| v1 | ~160 files (31Tir1405) | — | BM25 only | Initial architecture |
| v2 | 355 docs | 6,208 | BM25 + TF-IDF (RRF k=60) | First hybrid |
| v3 | 355 docs | 6,208 | + Dense MiniLM-L12 | Semantic leg |
| v4 | 355 docs | 6,208 | + Char 3-grams + Cross-encoder | Typo fix, mmarco rerank |
| v5 | 355 docs | 6,208 | P0-P5 frozen + BM25×3 | Frozen dataset, typo map fixed |
| v6 | 69 docs | 3,626 | P0-P8 remediation | Central maps, MinHash LSH, synonym beam5 |
| v7 | 34 docs | 2,074 | 1405-05-31 KB | Fresh corpus, TestQuestion* excluded, colloquial→formal 74 entries |
| **v8** ⭐ | **103 docs** | **6,593** | **pgvector HNSW** | **Vector(384) HNSW m16, tunable keyword×3.0, پرسش/پاسخ crm_qa fix** |

### v7 Key Changes
1. **Fresh corpus** from `kb-source/1405-05-31/` (legal/individual/other/technical)
2. **Test datasets excluded** — `TestQuestion*` dirs skipped in `_scan_files`
3. **Colloquial→formal expansion** — 74-entry map (چی/چه, رو/را, توی/در, قسطشون/قسط, رتبم/رتبه, چکم/چک…)
4. **IVA benchmark** — 15 questions, doc-level Hit@5 73.3%

### v8 Key Changes
1. **pgvector HNSW** — `Vector(384)` `m16 ef_construction 64` + `dense_embeddings.npz` backfilled
2. **Full clean_files re-ingested** — 78 files + 1405-05-31 = 103 docs
3. **پرسش/پاسخ schema fixed** — now `crm_qa` (165 rows)
4. **Web UI** — Caddy reverse proxy 32221→8000, pgvector on 8001
5. **GPU speedup** — HNSW CPU 23.1s → GPU 18.4s (1.3×), rerank 439→279ms (1.6×)

---

## 2. Embedding Generation

```bash
# Via KB Manager CLI
python -m kb_manager.cli ingest --full

# Or programmatically
python -c "
import asyncio
from kb_manager.pipeline.orchestrator import PipelineOrchestrator
from kb_manager.models.database import Database
from kb_manager.config import load_config

async def main():
    cfg = load_config()
    db = Database(cfg.db)
    orch = PipelineOrchestrator(database=db)
    summary = await orch.run_full_rebuild(cfg.source_dir)
    print(summary.to_dict())

asyncio.run(main())
"
```

**Configuration:**
| Variable | Default | Description |
|----------|---------|-------------|
| `KB_EMBED_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Embedding model |
| `KB_EMBED_DEVICE` | `cpu` | `cpu` or `cuda` |
| `KB_EMBED_BATCH` | 64 | Batch size |
| `KB_CHUNK_MAX` | 512 | Max tokens per chunk |

---

## 3. Reranker Selection (Backbone Shootout)

### Method
- **Dataset:** 800 QA pairs from `eval_clean.json` (gold `expected_chunk_ids`)
- **Pool:** 30, **Top-K:** 5
- **Parallel:** In-process CPU workers (`/tmp/opencode/bench_backbone.py`)
- **Metrics:** Hit@5, MRR, latency, ranx metrics
- **Output:** `eval/results/reranker_benchmark_*` + plots

### Candidates

| Model | Params | License | Loader | Status |
|-------|--------|---------|--------|--------|
| `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` | 118M | Apache 2.0 | CrossEncoder | **Production baseline** |
| `BAAI/bge-reranker-v2-m3` | 568M | MIT | CrossEncoder | Candidate — m3 tops FaMTEB Persian |
| `jinaai/jina-reranker-v3` | 0.6B | Apache 2.0 | CrossEncoder (trust_remote_code) | Candidate |
| `Qwen/Qwen3-Reranker-0.6B` | 0.6B | Apache 2.0 | FlagEmbedding LLM head | Candidate |
| `Qwen/Qwen3-Reranker-4B` | 4B | Apache 2.0 | FlagEmbedding LLM head | Candidate (~23GB) |
| `BAAI/bge-reranker-v2-gemma` | 2.5B | Apache 2.0 | FlagEmbedding LLM head | Candidate, biggest SOTA |
| `BAAI/bge-reranker-v2-minicpm-layerwise` | 2.7B | Apache 2.0 | — | **Blocked** (transformers-5) |
| `Alibaba-NLP/gte-multilingual-reranker-base` | ~300M | Apache 2.0 | — | **Blocked** (rope bug) |

### Selection Criteria
1. **Hit@5 / MRR** on 800 QA pairs
2. **Latency** (CPU and GPU)
3. **License** (Apache 2.0 / MIT preferred)
4. **Loader stability** (no custom modeling bugs)
5. **Persian performance** (FaMTEB if available)

---

## 4. Query Reformulation (Not in MVP)

Planned for post-MVP:
- **Synonym beam5** — colloquial→formal expansion (74 entries, in v7)
- **Multi-query rewriting** — beam5 RRF with LLM generator
- **HyDE** — Hypothetical Document Embeddings (consolidated in `hyde.py`, disabled by default)
- **HyDE A/B** — controlled experiment planned

---

## 5. Data Preparation Scripts

| Script | Purpose |
|--------|---------|
| `kb_manager/pipeline/orchestrator.py` | Full rebuild: parse→chunk→embed→store |
| `kb_manager/cli.py` | CLI: `ingest --full`, `status`, `dedup` |
| `kb_manager/scripts/cleanup_incomplete_qa.py` | Find/preview/cleanup incomplete QA chunks |
| `kb_manager/regen_test_questions.py` | Regenerate benchmark dataset from current KB |
| `kb_manager/evaluation/generator.py` | Synthetic test data generator |

---

## 6. Quality Gates (Pipeline)

```mermaid
flowchart TD
    ING[Ingest Complete] --> Q1{Fingerprint\nchanged?}
    Q1 -->|No| SKIP[Skip embed\n(invalidated)]
    Q1 -->|Yes| EMB[Generate embeddings]
    EMB --> Q2{Parent key\nmap valid?}
    Q2 -->|No| FIX[Repair parent\nO(1) map]
    Q2 -->|Yes| DEDUP[MinHash LSH\ndedup]
    DEDUP --> STORE[Store pgvector\n+ .npz cache]
    STORE --> BM25[Build BM25\nindex]
    BM25 --> READY[Search ready]
```

**Quality Checks:**
- Fingerprint: `model_name + context_fields` hash (detects embedding model/context changes)
- Invalidation: fingerprint + `max(updated_at)` per document
- Parent key map: O(1) lookup for chunk→document hierarchy
- Dedup: MinHash LSH (target 2074→~1700 chunks)
- Schema validation: overlap ≥60% for Excel header matching

---

## 6. Reproduction Commands

```bash
# Full rebuild (v8 pgvector)
KB_DB_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/kb_manager" \
KB_DB_MODE=pgvector \
KB_SOURCE_DIR=./kb-source/clean_files \
python -m kb_manager.cli ingest --full

# Status check
python -m kb_manager.cli status

# Dedup preview
python scripts/cleanup_incomplete_qa.py --dry-run

# Benchmark (v9 shootout running)
python -m kb_manager.evaluation.benchmark --backbones all --pool 30 --top_k 5

# Regenerate test questions from current KB
python regen_test_questions.py
```

---

## 7. Known Issues & Remediation

| Issue | Phase | Status |
|-------|-------|--------|
| IVA 4 misses (Q11/Q12 guaranteed loan, Q14 rank-vs-score, Q15 negative-contract) | v7 | P0 — RERANKER_TOP_K 50→100 or per-domain rerank |
| Latency ~22.7s CPU (cross-encoder bottleneck) | v7/v8 | P1 — GPU, batch 128, float16, BM25 cache |
| TestQuestion* exclusion not in v8 re-ingest | v8 | Verify `_scan_files` skips |
| Colloquial expansion only 74 entries | v7 | Expand based on query logs |
| Corpus dedup not applied | v8 | P2 — `python -m kb_manager.cli dedup` |
| Multi-query rewriting not implemented | — | P2 — consolidate `query_reform.MultiQueryGenerator` |

---

## 8. Artifacts

```
components/knowledgebase/kb-manager/
├── data/
│   ├── kb_test.db                    # SQLite (dev)
│   ├── kb_1405.db                    # SQLite (v7)
│   ├── test_questions.json           # 120 benchmark queries
│   ├── benchmark_comparison.json     # v2/v3/v4 comparison
│   ├── plots/                        # Generated benchmark plots
│   ├── hnsw_benchmark_detailed.json  # v8 GPU/CPU
│   └── iva_results.json              # IVA 15 results
├── versions/
│   └── v4_retrieval/                 # Latest versioned snapshot
├── logs/                             # Pipeline run logs
└── eval/
    └── reranker_benchmark_*.json     # Shootout results
```