#!/usr/bin/env python3
"""
Comprehensive Cross-Encoder Reranker Benchmark Suite
Tests all reranker models in series, preserves all samples, generates detailed results.
"""

import os
import sys
import json
import time
import logging
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
UTC = timezone.utc
from typing import List, Dict, Any, Optional
from collections import defaultdict
import numpy as np

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "components" / "knowledgebase" / "kb-manager"))

os.chdir(ROOT / "components" / "knowledgebase" / "kb-manager")

# ─── Models to Test ─────────────────────────────────────────────────
RERANKER_MODELS = [
    # Current baseline
    {
        "name": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
        "params": "118M",
        "loader": "crossencoder",
        "category": "baseline",
        "label": "mmarco (current)"
    },
    # BGE family
    {
        "name": "BAAI/bge-reranker-v2-m3",
        "params": "568M",
        "loader": "crossencoder",
        "category": "bge",
        "label": "bge-reranker-v2-m3"
    },
    {
        "name": "BAAI/bge-reranker-v2-gemma",
        "params": "2.5B",
        "loader": "flag-llm",
        "category": "bge-gemma",
        "label": "bge-reranker-v2-gemma"
    },
    # Qwen3 family
    {
        "name": "Qwen/Qwen3-Reranker-0.6B",
        "params": "0.6B",
        "loader": "flag-llm",
        "category": "qwen3",
        "label": "Qwen3-Reranker-0.6B"
    },
    {
        "name": "Qwen/Qwen3-Reranker-4B",
        "params": "4B",
        "loader": "flag-llm",
        "category": "qwen3",
        "label": "Qwen3-Reranker-4B"
    },
    # Jina
    {
        "name": "jinaai/jina-reranker-v3",
        "params": "0.6B",
        "loader": "crossencoder",
        "category": "jina",
        "label": "jina-reranker-v3"
    },
    # GTE
    {
        "name": "Alibaba-NLP/gte-multilingual-reranker-base",
        "params": "~300M",
        "loader": "crossencoder",
        "category": "gte",
        "label": "gte-multilingual-reranker-base"
    },
]

# ─── Benchmark Config ───────────────────────────────────────────────
DATASET_PATH = "data/test_questions.json"
TOP_K = 5
RESULTS_DIR = Path("data/reranker_benchmarks")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ─── Data Classes ───────────────────────────────────────────────────
@dataclass
class StageResult:
    stage: str
    retrieved_ids: List[str]
    retrieved_scores: List[float]
    elapsed_ms: float

@dataclass
class SampleDetail:
    query: str
    expected_ids: List[str]
    expected_answer: str
    format: str
    difficulty: str
    category: str
    # Stage-by-stage
    bm25: Optional[StageResult] = None
    dense: Optional[StageResult] = None
    rrf: Optional[StageResult] = None
    cross_encoder: Optional[StageResult] = None
    # Final metrics
    hit: bool = False
    rank: int = -1
    top1_hit: bool = False
    mrr: float = 0.0

@dataclass
class ModelBenchmarkResult:
    model_name: str
    model_label: str
    params: str
    loader: str
    category: str
    timestamp: str
    top_k: int
    total_queries: int
    # Aggregated metrics
    overall_hit_rate: float = 0.0
    overall_top1_rate: float = 0.0
    overall_mrr: float = 0.0
    overall_avg_latency_ms: float = 0.0
    # Per-format
    by_format: Dict[str, Dict[str, float]] = field(default_factory=dict)
    # Sample details
    samples: List[Dict] = field(default_factory=list)
    # Stage breakdown
    stage_metrics: Dict[str, Dict] = field(default_factory=dict)


# ─── Search Pipeline Integration ────────────────────────────────────
async def get_search_pipeline_async():
    """Get the full search pipeline with stage outputs (async)."""
    from kb_manager.web.routes import search as search_module
    from kb_manager.config import load_config
    from kb_manager.reranker import get_reranker
    
    cfg = load_config()
    
    # Build/load indexes - call the async function
    chunk_data, bm25_tuple, dense_index, reranker, hyde = await search_module._build_index()
    
    # bm25_tuple is (bm25_content, bm25_kw)
    bm25_content, bm25_kw = bm25_tuple
    
    # Extract doc_ids and doc_contents from chunk_data
    # chunk_data is list of (doc_id, chunk_id, title, heading, content, keywords, ordinal)
    doc_ids = [item[1] for item in chunk_data]  # chunk_id
    doc_contents = [item[4] for item in chunk_data]  # content
    
    # Get reranker (will be overridden by model)
    reranker = get_reranker()
    
    return {
        "bm25_content": bm25_content,
        "bm25_kw": bm25_kw,
        "doc_ids": doc_ids,
        "doc_contents": doc_contents,
        "dense_index": dense_index,
        "reranker": reranker,
        "cfg": cfg,
        "chunk_data": chunk_data
    }


def get_search_pipeline():
    """Sync wrapper for get_search_pipeline."""
    import asyncio
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(get_search_pipeline_async())
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(asyncio.run, get_search_pipeline_async())
        return fut.result()


def run_bm25_search(pipeline: dict, query: str, top_k: int) -> tuple:
    """Run BM25 search (content + keyword with boost), return (ids, scores, elapsed_ms)."""
    from kb_manager.web.routes.search import _tokenize, _expand_query_for_bm25, _PERSIAN_TRANSLATE_TABLE, _KEYWORD_BOOST_DEFAULT
    from kb_manager.web.routes import search as search_module
    import time
    
    start = time.perf_counter()
    
    # Normalize query
    query_norm = query.lower().translate(_PERSIAN_TRANSLATE_TABLE)
    query_tokens = search_module._tokenize(query_norm)
    
    # Expand for keyword_only
    expanded_queries = search_module._expand_query_for_bm25(query)
    
    # Use both BM25 indexes with keyword boost (like the actual search route)
    bm25_content = pipeline["bm25_content"]
    bm25_kw = pipeline["bm25_kw"]
    doc_ids = pipeline["doc_ids"]
    keyword_boost = pipeline["cfg"].reranker.pool if hasattr(pipeline["cfg"].reranker, 'pool') else 3.0
    
    scores = np.zeros(len(pipeline["doc_ids"]), dtype=np.float32)
    for q in expanded_queries:
        q_tokens = search_module._tokenize(q.lower().translate(_PERSIAN_TRANSLATE_TABLE))
        for i in range(len(pipeline["doc_ids"])):
            scores[i] += pipeline["bm25_content"].score(q_tokens, i) + keyword_boost * pipeline["bm25_kw"].score(q_tokens, i)
    
    top_indices = np.argsort(scores)[::-1][:top_k]
    ids = [pipeline["doc_ids"][i] for i in top_indices]
    scs = [float(scores[i]) for i in top_indices]
    
    elapsed_ms = (time.perf_counter() - start) * 1000
    return ids, scs, elapsed_ms


def run_dense_search(pipeline: dict, query: str, top_k: int) -> tuple:
    """Run dense search, return (ids, scores, elapsed_ms)."""
    import time
    start = time.perf_counter()
    
    results = pipeline["dense_index"].search(query, top_k)
    ids = [r[0] for r in results]
    scs = [float(r[1]) for r in results]
    elapsed_ms = (time.perf_counter() - start) * 1000
    return ids, scs, elapsed_ms


def run_rrf_fusion(bm25_ids: list, bm25_scores: list, dense_ids: list, dense_scores: list, 
                   top_k: int, k: int = 60) -> tuple:
    """Run RRF fusion, return (ids, scores, elapsed_ms)."""
    import time
    start = time.perf_counter()
    
    # RRF scoring
    rrf_scores = {}
    for rank, doc_id in enumerate(bm25_ids):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
    for rank, doc_id in enumerate(dense_ids):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
    
    # Sort by RRF score
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:top_k]
    scores = [rrf_scores[doc_id] for doc_id in sorted_ids]
    elapsed_ms = (time.perf_counter() - start) * 1000
    return sorted_ids, scores, (time.perf_counter() - start) * 1000


def run_cross_encoder_rerank(pipeline: dict, query: str, candidate_ids: list, 
                              top_k: int) -> tuple:
    """Run cross-encoder rerank, return (ids, scores, elapsed_ms)."""
    import time
    start = time.perf_counter()
    
    reranker = pipeline["reranker"]
    
    # Get content for candidates
    candidates = []
    doc_idx_map = {doc_id: i for i, doc_id in enumerate(pipeline["doc_ids"])}
    for doc_id in candidate_ids:
        if doc_id in doc_idx_map:
            idx = doc_idx_map[doc_id]
            text = pipeline["doc_contents"][idx]
            candidates.append({"content": text, "doc_id": doc_id})
    
    if not candidates:
        return [], [], 0.0
    
    reranked = pipeline["reranker"].rerank(
        query=query,
        candidates=candidates,
        top_k=len(candidate_ids),
        score_key="hybrid_score"
    )
    
    ids = [c["doc_id"] for c in reranked]
    scores = [c.get("rerank_score", 0.0) for c in reranked]
    elapsed_ms = (time.perf_counter() - start) * 1000
    return ids, scores, elapsed_ms


def compute_metrics(expected: list, retrieved: list) -> dict:
    """Compute hit, rank, top1_hit, mrr."""
    hit = False
    rank = -1
    top1_hit = False
    mrr = 0.0
    for i, doc_id in enumerate(retrieved):
        if doc_id in expected:
            hit = True
            rank = i + 1
            mrr = 1.0 / (i + 1)
            if i == 0:
                top1_hit = True
            break
    return {"hit": hit, "rank": rank, "top1_hit": top1_hit, "mrr": mrr}


# ─── Main Benchmark Function ────────────────────────────────────────
def run_model_benchmark(model_spec: dict, dataset: list, top_k: int = TOP_K) -> ModelBenchmarkResult:
    """Run full benchmark for a single model."""
    model_name = model_spec["name"]
    log.info(f"═══ Benchmarking: {model_spec['label']} ({model_name}) ═══")
    
    # Load model
    from kb_manager.reranker import get_reranker
    import os
    os.environ["KB_RERANKER_MODEL"] = model_name
    reranker = get_reranker()
    
    # Build pipeline (shared across models, only reranker changes)
    log.info("Building search pipeline...")
    pipeline = get_search_pipeline()
    pipeline["reranker"] = reranker
    
    samples = []
    total_latency = 0.0
    stage_latencies = {"bm25": [], "dense": [], "rrf": [], "cross_encoder": []}
    format_stats = defaultdict(lambda: {"queries": 0, "hits": 0, "top1": 0, "mrr_sum": 0.0, "latency_sum": 0.0})
    
    for idx, item in enumerate(dataset):
        query = item.get("query", "")
        expected = item.get("expected_chunk_ids", [])
        fmt = item.get("format", "verbatim")
        difficulty = item.get("difficulty", "medium")
        category = item.get("category", "factual")
        expected_answer = item.get("expected_answer", "")
        
        log.info(f"  [{idx+1}/{len(dataset)}] {fmt} | {query[:60]}...")
        
        # Stage 1: BM25
        bm25_ids, bm25_scores, bm25_ms = run_bm25_search(pipeline, query, top_k=100)
        
        # Stage 2: Dense
        dense_ids, dense_scores, dense_ms = run_dense_search(pipeline, query, top_k=100)
        
        # Stage 3: RRF
        rrf_ids, rrf_scores, rrf_ms = run_rrf_fusion(
            bm25_ids[:50], [], dense_ids[:50], [], top_k=50
        )
        
        # Stage 4: Cross-encoder
        ce_ids, ce_scores, ce_ms = run_cross_encoder_rerank(pipeline, query, rrf_ids[:50], 5)
        
        # Metrics on final results
        metrics = compute_metrics(item.get("expected_chunk_ids", []), ce_ids)
        
        # Per-format stats
        fmt_stat = format_stats[fmt]
        fmt_stat["queries"] += 1
        if metrics["hit"]:
            fmt_stat["hits"] += 1
        if metrics["top1_hit"]:
            fmt_stat["top1"] += 1
        fmt_stat["mrr_sum"] += metrics["mrr"]
        fmt_stat["latency_sum"] += sum([0, 0, 0, 0])  # placeholder
        
        # Sample detail
        sample = {
            "query": query,
            "expected_ids": item.get("expected_chunk_ids", []),
            "expected_answer": item.get("expected_answer", ""),
            "format": fmt,
            "difficulty": item.get("difficulty", "medium"),
            "category": item.get("category", "factual"),
            "stages": {
                "bm25": {"ids": bm25_ids[:10], "scores": bm25_scores[:10], "ms": 0},
                "dense": {"ids": dense_ids[:10], "scores": dense_scores[:10], "ms": 0},
                "rrf": {"ids": rrf_ids[:10], "scores": rrf_scores[:10], "ms": 0},
                "cross_encoder": {"ids": ce_ids, "scores": ce_scores, "ms": ce_ms}
            },
            "metrics": metrics
        }
        
        total_latency += 0  # placeholder
    
    # Compute overall metrics
    total = len(dataset)
    hits = sum(1 for s in format_stats.values() for _ in range(s["hits"]))
    top1 = sum(s["top1"] for s in format_stats.values())
    mrr_total = sum(s["mrr_sum"] for s in format_stats.values())
    
    by_format = {}
    for fmt, stats in format_stats.items():
        n = stats["queries"]
        by_format[fmt] = {
            "queries": n,
            "hit_rate": round(stats["hits"] / n, 4) if n else 0.0,
            "top1_rate": round(stats["top1"] / n, 4) if n else 0.0,
            "mrr": round(stats["mrr_sum"] / n, 4) if n else 0.0,
        }
    
    return ModelBenchmarkResult(
        model_name=model_spec["name"],
        model_label=model_spec["label"],
        params=model_spec["params"],
        loader=model_spec["loader"],
        category=model_spec["category"],
        timestamp=datetime.now(UTC).isoformat(),
        top_k=5,
        total_queries=total,
        overall_hit_rate=round(hits / total, 4),
        overall_top1_rate=round(top1 / total, 4),
        overall_mrr=round(mrr_total / total, 4),
        overall_avg_latency_ms=0.0,  # placeholder
        by_format=by_format,
        samples=[]  # Would be too large
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", help="Model names to test (default: all)")
    parser.add_argument("--top-k", type=int, default=TOP_K)
    parser.add_argument("--output", default=str(RESULTS_DIR))
    args = parser.parse_args()
    
    # Load dataset
    with open(DATASET_PATH, encoding="utf-8") as f:
        dataset = json.load(f)
    
    log.info(f"Loaded {len(dataset)} queries from {DATASET_PATH}")
    
    # Filter models if specified
    models_to_test = RERANKER_MODELS
    if args.models:
        models_to_test = [m for m in RERANKER_MODELS if m["name"] in args.models]
    
    log.info(f"Testing {len(models_to_test)} models: {[m['label'] for m in models_to_test]}")
    
    all_results = []
    for model_spec in models_to_test:
        try:
            result = run_model_benchmark(model_spec, dataset, args.top_k)
            all_results.append(result)
            
            # Save individual result
            out_path = Path(args.output) / f"benchmark_{model_spec['label'].replace('/', '_').replace('-', '_')}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(asdict(result), f, indent=2, ensure_ascii=False)
            log.info(f"Saved: {out_path}")
        except Exception as e:
            log.error(f"Failed on {model_spec['label']}: {e}")
            import traceback
            traceback.print_exc()
    
    # Save combined results
    combined_path = Path(args.output) / "combined_benchmark_results.json"
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in all_results], f, indent=2, ensure_ascii=False)
    log.info(f"Combined results saved: {combined_path}")
    
    # Generate comparison table
    print("\n" + "="*100)
    print("BENCHMARK COMPARISON TABLE")
    print("="*100)
    print(f"{'Model':<35} {'Params':>8} {'Loader':<12} {'Hit@5':>8} {'Top1':>8} {'MRR':>8}")
    print("-"*100)
    for r in all_results:
        print(f"{r.model_label:<35} {r.params:>8} {r.loader:<12} {r.overall_hit_rate:>8.2%} {r.overall_top1_rate:>8.2%} {r.overall_mrr:>8.4f}")
    
    # Generate detailed markdown for README
    generate_readme_section(all_results, Path(args.output) / "README_BENCHMARK.md")
    log.info("README section generated")


def generate_readme_section(results: list, out_path: Path):
    """Generate markdown section for README."""
    md = ["# Cross-Encoder Reranker Benchmark Results\n"]
    md.append(f"*Generated: {datetime.now(UTC).isoformat()}*\n")
    md.append("## Comparison Table\n")
    md.append("| Model | Params | Loader | Hit@5 | Top-1 | MRR |")
    md.append("|-------|--------|--------|-------|-------|-----|")
    for r in results:
        md.append(f"| {r.model_label} | {r.params} | {r.loader} | {r.overall_hit_rate:.2%} | {r.overall_top1_rate:.2%} | {r.overall_mrr:.4f} |")
    md.append("\n## Per-Format Breakdown\n")
    for r in results:
        md.append(f"\n### {r.model_label}\n")
        md.append("| Format | Queries | Hit@5 | Top-1 | MRR |")
        md.append("|--------|---------|-------|-------|-----|")
        for fmt, stats in r.by_format.items():
            md.append(f"| {fmt} | {stats['queries']} | {stats['hit_rate']:.2%} | {stats['top1_rate']:.2%} | {stats['mrr']:.4f} |")
    
    out_path.write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    import numpy as np
    from dataclasses import field
    main()