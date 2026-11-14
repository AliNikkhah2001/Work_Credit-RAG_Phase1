# Knowledgebase GitHub Pages — report extracts

Sources: `components/knowledgebase/docs/index.html`, `technical.html`, `high-level.html`.  
Original bullet extracts for the technical report (not HTML dump).

---

## Release / corpus (v13)

- Production status: implemented, operational, **RAM-first**.
- Current release label: **`v13_1405-07-06`** — **18 docs / 1,123 chunks**; full rebuild dated **2026-10-07**.
- Source folders in kb-source submodule: `1405-05-31`, `1405-06-23`, **`1405-07-06` (current)**.
- KB owns: documents, ingest, indexing, retrieval, reranking, KB evaluation — **not** model lifecycle, safety policy, orchestration, or frontend.
- Frozen eval set: **120** queries, 6 formats; **v11 Hit@5 = 0.9306**; **v13 Hit@5 pending** re-benchmark on 1405-07-06.
- Latency detail page notes measurement corpus **1110 chunks**, `top_k=5` (close to 1123; treat as same rebuild family).

### Chunk-type mix (v13 folder tree caption)

- `qa_pair` **776** · `reason_detail` **198** · `body` **71** · `article` **46** · `kv_pair` **19** (+ **13** parent chunks).
- Four hierarchy roots: حقیقی تسهیلات, حقیقی چک, حقوقی تسهیلات, عمومی (no third sheet).

### EntityList supplements (not chunks)

- XLSX list sheets (shareholders, lenders, loan titles, etc.) → `entity_lists` table.
- Search **step 8**: query MiniLM cosine vs `description_embedding`, threshold **≥ 0.6** → `injected_entities`.
- Orchestrator consumes as `rag.supplemental`.

---

## RAM-first stack & parameters

**Stack blurb:** FastAPI · SQLAlchemy async · SQLite / pgvector (HNSW 384d, RAM-pinned) · Rust tantivy BM25 (RAM, **50 MB** heap) · MiniLM-L12 384-d (GPU) · BGE-v2-m3 cross-encoder (GPU) · hazm/shekar · Redis result cache.

| Stage | Param | Value | Notes |
|---|---|---|---|
| Postgres | `shared_buffers` / `effective_cache_size` | **16 GB** / **800 GB** + `pg_prewarm` | Vectors + HNSW resident in RAM |
| BM25 engine | tantivy | **0.26.2**, `RAMDirectory`, heap **50 MB** | `KB_USE_TANTIVY=true` |
| BM25 | **k1 / b** | **1.5 / 0.75** | content + keyword legs |
| BM25 | keyword boost / n-grams | **×3** / char **3**-grams | `KB_KEYWORD_BOOST=3.0` |
| Synonym beam | `KB_SYNONYM_BEAM` | **5** (set `1` to cut BM25 ~5×) | **93**-entry colloquial→formal map (v12) |
| Dense | model / dim / batch / device | MiniLM-L12-v2 / **384** / **64** / **cuda** | ~3 GB HBM on H200 |
| Dense index | pgvector HNSW | `vector_cosine_ops`, **m=16**, **ef=64** | + npz cache |
| RRF | k | **60** | |
| Fusion α | RRF↔rerank | **0.7** | `KB_RERANK_FUSION_ALPHA` |
| Rerank | model / pool | BAAI/bge-reranker-v2-m3 / `min(50, top_k×3)` | GPU; pin-protect top-3 ≥ rank 10 |
| Redis | TTL / hit latency | **600 s**, **2–7 ms** hits | **~150×** vs cold; `KB_REDIS_URL` |
| Fast cache | `KB_FAST_CACHE` | **true** | skips **~2.7 s** fingerprint scan per search |
| Chunk | strategy / max tokens | semantic / **512** | parent max **1536**, scope sheet |
| HyDE | `KB_HYDE_ENABLED` | **false** (default) | |

Host cited for latency: **1.0 TiB** RAM · **2× H200** 143 GB HBM.

---

## Latency before / after (RAM-first + Rust tantivy)

Measured **2026-10-07** on 1405-07-06 corpus (`top_k=5`, warm after GPU load).

| Stage | Before (Python BM25 / CPU) | After (tantivy + GPU) | Share after |
|---|---:|---:|---:|
| BM25 lexical (content+kw, beam5) | **~3000 ms** | **3.8–5.9 ms** | ~7% |
| Dense cosine (pgvector HNSW) | 16–50 ms warm (CPU path **~3000 ms**) | **22–27 ms** | ~44% |
| RRF k=60 | 0.1–0.2 ms | 0.1–0.2 ms | &lt;1% |
| Cross-encoder BGE-v2-m3 | 20–23 ms warm (CPU **~5400 ms**) | **21–25 ms** | ~44% |
| **Total warm** | **~3100 ms** (cold ~**12 s**) | **51–66 ms** (**avg ~55 ms**) | 100% |
| Redis hit | 2–7 ms | 2–7 ms (~**2 ms** on index page) | **~150×** vs cold |

Cold first query after restart (detail page): dense **4246 ms** + rerank **5396 ms** + BM25 **~5 ms** → ~**12 s** one-time; then ~**55 ms** avg.

Infra note: HNSW distance is **CPU-only** in Postgres; GPU used for embed + rerank. Relation sizes cited for ~1110 chunks: HNSW index **~4.8 MB**, chunks **~1.2 MB**, `pg_total_relation_size` **~203 MB**, kept hot via `pg_prewarm`.

Warm hybrid search claim on overview: **~55 ms**.

---

## Changelog highlights (version summary)

| Ver | Corpus | Key change | Benchmark |
|---|---|---|---|
| v1 | ~160 files (31Tir1405) | baseline ingest + BM25 | — |
| v2 | 355 docs / 6,208 chunks | BM25 + TF-IDF RRF k=60 | Hit@5 90%, MRR 0.736 |
| v3 | same | + dense MiniLM-L12 | Hit@5 89.2%, MRR 0.787 |
| v4 | same | + char 3-grams + cross-encoder | Hit@5 90%, MRR 0.775 |
| v5 | same | frozen dataset BM25×3 | Hit@5 84.2%, MRR 0.751 |
| v6 | 69 docs / 3,626 chunks | P0–P8 remediation, synonym **beam5**, MinHash dedup | 10-q smoke 100% Hit@5 |
| v7 | 34 docs / 2,074 chunks | fresh 1405-05-31, colloquial expansion, IVA-15 | doc-Hit@5 73.3% |
| v8 | 103 docs / 6,593 chunks | pgvector HNSW-384, keyword×3.0 | HNSW GPU 18.4 s (load note) |
| v9 | 21+32 docs / ~1,084 chunks | type-aware, transparency/zip | IVA 11/15 |
| v10 | 35 docs / 2,282 chunks | 1405-06-23, kv/single-col schemas, stage bench | Hit@5 **0.9244** |
| v11 | 35 docs / 2,227 chunks | chunk-fix rebuild, `dense use_context=False` | Hit@5 **0.9306**, MRR **0.8281** |
| v12 | same as v11 KB | typo fixes, exclusive-term beam, **Redis cache** | SYNONYM_MAP **93** entries |
| **v13** | **18 docs / 1,123 chunks** | **1405-07-06 RAM-first**: tantivy RAM BM25, pgvector 16 GB buffers + prewarm, GPU dense/rerank H200 | latency **~55 ms**, Hit@5 **pending** |

- v11 manifest path cited: `kb-manager/versions/v11_1405-06-23/manifest.json`.
- “v13-RAM” = code + infra tuning on top of v13 corpus.

---

## Retrieval pipeline (technical)

1. Normalize (Arabic→Persian, ZWNJ, digits) → tokenize words + Persian char 3-grams.
2. Synonym / multi-query **beam=5**; optional HyDE off.
3. Parallel: tantivy BM25 (content + keyword, k1=1.5, b=0.75, boost×3) + dense MiniLM HNSW.
4. RRF **k=60** → BGE cross-encoder → fuse α=**0.7** + pin protection.
5. Final top-k / `min_relevance` gate → EntityList inject (≥0.6).
6. Redis + in-memory cache key: `sha256(normalized_query|top_k|boost|filter_path)`; errors never cached.
7. `filter_path` → `allowed_ids` from `folder_hierarchy` before BM25/dense (subspace scoping).

Primary endpoint: `POST /search/api` → `SearchSteps` + `final_results` (+ `injected_entities`). Web UI/ops on `:8000`.

---

## Diagram inventory (KB technical page)

1. Ingest pipeline (detailed) — scan → parse → preprocess → semantic chunk → embed → store → quality → version; EntityList branch.
2. Retrieval pipeline (detailed) — normalize → beam → BM25/dense → RRF → rerank → fuse → EntityList → Redis.
3. Query classification & ambiguity resolver (v13.1) — greeting/spec/question + scattered gate (overlaps orchestrator; present on KB pages).
4. Knowledge tree / folder hierarchy (18 docs, 1123 chunks).
5. EntityList supplements flow.
6. Conditional subspace retrieval (`filter_path` → `allowed_ids`).
7. Clarifying question / scattered leaves flow.
8. Open WebUI scope picker + provenance.
9. Mizan System-1 hybrid architecture (v13.1) — SVM-RBF ~**1 ms** gate vs Mizan ~**50–100 ms**; Mizan GGUF available offline but not always deployed.

Plots cited: latency breakdown (log), stage-share pie, improvement factor, Postgres RAM fit, OOM before/after.

---

## Other report-useful notes

- Tests cited: `pytest` **116 passed**, 6 skipped, 1 env-dependent failure (`test_qa_massive_count`).
- LLM-as-judge RCA themes: fusion casualties, keyword-stuffed reason-code traps, dense-invisible phrasing, twin crowding / answer dupes; Cheque OOM episode (**55** empty ranks) resolved on re-run.
- Ranked RCA on 663-row run: true misses (A=25) &gt; reranker near-misses (B=13) &gt; fusion losses (A′=8) &gt; twin crowding.
- Quick start: `KB_DB_MODE=sqlite|pgvector`, `KB_SOURCE_DIR=./kb-source` → `python -m kb_manager.cli ingest --full` / `serve` on `0.0.0.0:8000`.
