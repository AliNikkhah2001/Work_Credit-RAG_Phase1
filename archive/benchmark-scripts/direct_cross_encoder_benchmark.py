#!/usr/bin/env python3
"""
Cross-Encoder Reranker Benchmark - Direct Python API
Tests reranker models using KB Manager's Python API directly.
"""

import os
import sys
import json
import time
import logging
import asyncio
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import numpy as np

# Add KB manager to path
ROOT = Path(__file__).resolve().parent.parent / "components" / "knowledgebase" / "kb-manager"
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# ─── Config ──────────────────────────────────────────────────────────
RESULTS_DIR = Path("data/reranker_benchmarks")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ─── Models to Test ──────────────────────────────────────────────────
RERANKER_MODELS = [
    {"name": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", "params": "118M", "loader": "crossencoder", "label": "mmarco (baseline)"},
    {"name": "BAAI/bge-reranker-v2-m3", "params": "568M", "loader": "crossencoder", "label": "bge-reranker-v2-m3"},
    {"name": "BAAI/bge-reranker-v2-gemma", "params": "2.5B", "loader": "flag-llm", "label": "bge-reranker-v2-gemma"},
    {"name": "Qwen/Qwen3-Reranker-0.6B", "params": "0.6B", "loader": "flag-llm", "label": "Qwen3-Reranker-0.6B"},
    {"name": "Qwen/Qwen3-Reranker-4B", "params": "4B", "loader": "flag-llm", "label": "Qwen3-Reranker-4B"},
    {"name": "jinaai/jina-reranker-v3", "params": "0.6B", "loader": "crossencoder", "label": "jina-reranker-v3"},
    {"name": "Alibaba-NLP/gte-multilingual-reranker-base", "params": "~300M", "loader": "crossencoder", "label": "gte-multilingual-reranker-base"},
]

TEST_QUERIES = [
    "اعتبارسنجی چیست؟",
    "امتیاز اعتباری چگونه محاسبه می‌شود؟",
    "چگونه می‌توانم گزارش اعتباری خود را دریافت کنم؟",
    "تفاوت رتبه اعتباری با امتیاز اعتباری چیست؟",
    "بخشی از اطلاعات اعتباری من ناقص است، چگونه اصلاح کنم؟",
    "تامین مالی از طریق تسهیلات بانکی چگونه انجام می‌شود؟",
    "داده‌های گمرک چه تأثیری در ارزیابی اعتبار کسب‌وکارها دارند؟",
    "در صورت اختلال گسترده در سیستم بانکی که باعث تأخیر در بازپرداخت اقساط شود، شرکت چگونه این وضعیت را مدیریت می‌کند؟",
    "ببخشید، داده‌های مربوط به بدهی بیمه‌ای و تامین اجتماعی چگونه پردازش می‌شوند؟",
    "آیا جریمه دیرکرد اقساط در گزارش اعتباری من درج می‌شود؟",
    "محل سکونت پست پایگاه داده داده اعتباری تحلیل مکان مدیریت داده",
    "آیا داده‌های بورس و اوراق بهادار نیز ارسال می‌شود؟",
    "چرا سوابق تسهیلاتی افراد تاثیر کمی بر امتیاز چک دارد؟",
    "در پنل کاربری خود گزینه‌ای برای «بازگشت وجه به کارت بانکی» مشاهده نکردم؛ آیا این قابلیت در دسترس کاربران قرار دارد یا خیر؟",
    "چنانچه حکم دادگاه برای پرداخت نفقه یا مهریه داشته باشم و آن را پرداخت نکنم، آیا این موضوع بر رتبه اعتباری من تاثیر دارد؟",
    "ممکن است توضیح دهید که داده‌های گمرک چه تأثیری اعتبار ارزیابی در کسب‌وکارها دارند؟",
    "در این باره بگویید که همان‌طور که اشاره شد در صورت گسترده در سیستم بازپرداخت در تأخیر اقساط ارائه شود، شرکت چگونه این وضعیت را مدیریت می‌کند؟",
    "لطفاً بگویید همان‌طور که اشاره شد اطلاعات در باید قالب استاندارد شوند و چرا است؟؟",
    "ببخشید، داده‌های مربوط به بدهی بیمه‌ای و تامین اجتماعی چگونه پردازش میشن . لطفاً دقیق توضیح دهید.",
    "آیا دادههای بورس و اوراق بهادار نیز ارسال می‌شود؟",
]

@dataclass
class QueryResult:
    query: str
    rrf_latency_ms: float
    rerank_latency_ms: float
    rrf_top_ids: List[str]
    reranked_ids: List[str]
    rerank_scores: List[float]
    score_mean: float
    score_std: float

@dataclass
class ModelResult:
    model_name: str
    model_label: str
    params: str
    loader: str
    total_queries: int
    avg_rerank_latency_ms: float
    avg_search_latency_ms: float
    stage_latencies: Dict[str, float]
    queries: List[Dict]


async def benchmark_model(model_spec: dict) -> dict:
    """Benchmark a single reranker model using KB Manager API directly."""
    model_name = model_spec["name"]
    log.info(f"═══ Benchmarking: {model_spec['label']} ({model_name}) ═══")
    
    # Set environment variable for reranker model
    os.environ["KB_RERANKER_MODEL"] = model_spec["name"]
    os.environ["KB_RERANKER_DEVICE"] = "cpu"
    os.environ["KB_EMBED_DEVICE"] = "cpu"
    os.environ["KB_DB_URL"] = "sqlite+aiosqlite:///./data/kb_1405.db"
    
    # Import after setting env vars
    import importlib
    import kb_manager.web.routes.search as search_module
    import kb_manager.config as config_module
    importlib.reload(config_module)
    importlib.reload(search_module)
    
    from kb_manager.config import load_config
    from kb_manager.reranker import get_reranker
    
    cfg = load_config()
    
    # Build pipeline
    log.info("Building search pipeline...")
    chunk_data, bm25_tuple, dense_index, reranker, hyde = await search_module._build_index()
    bm25_content, bm25_kw = bm25_tuple
    doc_ids = [item[1] for item in chunk_data]
    doc_contents = [item[4] for item in chunk_data]
    
    # Replace reranker with our model
    from kb_manager.reranker import get_reranker
    reranker = get_reranker(model_name=model_spec["name"], device="cpu")
    
    pipeline = {
        "bm25_content": bm25_content,
        "bm25_kw": bm25_kw,
        "doc_ids": doc_ids,
        "doc_contents": doc_contents,
        "dense_index": dense_index,
        "reranker": reranker,
        "cfg": cfg,
    }
    
    from kb_manager.web.routes.search import _tokenize, _expand_query_for_bm25, _PERSIAN_TRANSLATE_TABLE, _KEYWORD_BOOST_DEFAULT
    from kb_manager.web.routes import search as search_module
    
    results = []
    stage_latencies = {"search_without_rerank": [], "search_with_rerank": [], "rerank_only": []}
    total_rerank_latency = 0
    total_latency = 0
    
    for i, query in enumerate(TEST_QUERIES):
        log.info(f"  [{i+1}/{len(TEST_QUERIES)}] {query[:50]}...")
        
        # Stage 1: Search without reranker (BM25 + Dense + RRF)
        start = time.perf_counter()
        query_norm = query.lower().translate(search_module._PERSIAN_TRANSLATE_TABLE)
        query_tokens = search_module._tokenize(query_norm)
        expanded_queries = search_module._expand_query_for_bm25(query)
        
        scores = np.zeros(len(pipeline["doc_ids"]), dtype=np.float32)
        for q in expanded_queries:
            q_tokens = search_module._tokenize(q.lower().translate(search_module._PERSIAN_TRANSLATE_TABLE))
            for i in range(len(pipeline["doc_ids"])):
                scores[i] += pipeline["bm25_content"].score(q_tokens, i) + 3.0 * pipeline["bm25_kw"].score(q_tokens, i)
        
        top_indices = np.argsort(scores)[::-1][:50]
        rrf_ids = [pipeline["doc_ids"][i] for i in top_indices]
        
        # Dense search
        dense_results = pipeline["dense_index"].search(query, 50)
        dense_ids = [r[0] for r in dense_results]
        
        # RRF fusion
        k = 60
        rrf_scores = {}
        for rank, doc_id in enumerate(pipeline["doc_ids"][idx] for idx in top_indices):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
        for rank, doc_id in enumerate(dense_ids):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
        
        rrf_sorted = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:50]
        
        search_latency = (time.perf_counter() - start) * 1000
        stage_latencies["search_without_rerank"].append(search_latency)
        
        # Stage 2: Rerank
        start_rerank = time.perf_counter()
        candidates = []
        doc_idx_map = {doc_id: i for i, doc_id in enumerate(pipeline["doc_ids"])}
        for doc_id in rrf_sorted[:50]:
            if doc_id in doc_idx_map:
                idx = doc_idx_map[doc_id]
                text = pipeline["doc_contents"][idx]
                candidates.append({"content": text, "doc_id": doc_id})
        
        if candidates:
            reranked = pipeline["reranker"].rerank(
                query=query,
                candidates=candidates,
                top_k=len(candidates),
                score_key="hybrid_score"
            )
        else:
            reranked = []
        
        rerank_latency = (time.perf_counter() - start_rerank) * 1000
        stage_latencies["rerank_only"].append(rerank_latency)
        
        reranked_ids = [c["doc_id"] for c in reranked]
        rerank_scores = [c.get("rerank_score", 0) for c in reranked]
        
        result = {
            "query": query,
            "rrf_latency_ms": search_latency,
            "rerank_latency_ms": rerank_latency,
            "rrf_top_ids": [pipeline["doc_ids"][i] for i in top_indices][:10],
            "reranked_ids": reranked_ids,
            "rerank_scores": rerank_scores,
            "score_mean": float(np.mean(rerank_scores)) if rerank_scores else 0,
            "score_std": float(np.std(rerank_scores)) if rerank_scores else 0,
        }
        results.append(result)
        
        if (i + 1) % 5 == 0:
            log.info(f"  Progress: {i+1}/{len(TEST_QUERIES)}")
    
    n = len(TEST_QUERIES)
    return {
        "model_name": model_spec["name"],
        "model_label": model_spec["label"],
        "params": model_spec["params"],
        "loader": model_spec["loader"],
        "total_queries": len(TEST_QUERIES),
        "avg_rerank_latency_ms": round(np.mean([r["rerank_latency_ms"] for r in results]), 1),
        "avg_search_latency_ms": round(np.mean([r["rrf_latency_ms"] for r in results]), 1),
        "stage_latencies": {k: round(np.mean(v), 1) for k, v in stage_latencies.items() if v},
        "queries": [
            {
                "query": r["query"],
                "rrf_latency_ms": r["rrf_latency_ms"],
                "rerank_latency_ms": r["rerank_latency_ms"],
                "rerank_scores": r["rerank_scores"][:5],
                "score_mean": r["score_mean"],
                "score_std": r["score_std"],
            }
            for r in results
        ]
    }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", help="Model names to test")
    parser.add_argument("--output", default="data/reranker_benchmarks")
    args = parser.parse_args()
    
    RESULTS_DIR = Path("data/reranker_benchmarks")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    models_to_test = RERANKER_MODELS
    if args.models:
        models_to_test = [m for m in RERANKER_MODELS if m["name"] in args.models]
    
    log.info(f"Testing {len(models_to_test)} models: {[m['label'] for m in models_to_test]}")
    
    all_results = []
    for model_spec in models_to_test:
        try:
            result = await benchmark_model(model_spec)
            
            out_path = Path("data/reranker_benchmarks") / f"benchmark_{model_spec['label'].replace('/', '_').replace('-', '_')}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            log.info(f"Saved: {out_path}")
            
            all_results.append(result)
        except Exception as e:
            log.error(f"Failed on {model_spec['label']}: {e}")
            import traceback
            traceback.print_exc()
    
    # Save combined
    combined_path = Path("data/reranker_benchmarks") / "direct_api_benchmark_results.json"
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    log.info(f"Combined saved: {combined_path}")
    
    # Print comparison
    print("\n" + "="*100)
    print("DIRECT API BENCHMARK COMPARISON")
    print("="*100)
    print(f"{'Model':<35} {'Params':>8} {'Loader':<12} {'Avg Rerank':>12} {'Avg Search':>12}")
    print("-"*100)
    for r in all_results:
        print(f"{r['model_label']:<35} {r['params']:>8} {r['loader']:<12} "
              f"{r['avg_rerank_latency_ms']:>12.1f} {r['avg_search_latency_ms']:>12.1f}")
    
    # Generate markdown
    generate_md(all_results, Path("data/reranker_benchmarks/DIRECT_API_BENCHMARK_RESULTS.md"))


def generate_md(results: list, out_path: Path):
    md = ["# Cross-Encoder Reranker Direct API Benchmark Results\n"]
    md.append(f"*Generated: {datetime.now(timezone.utc).isoformat()}*\n")
    md.append(f"*Test Queries: {len(TEST_QUERIES)} diverse Persian credit queries*\n")
    md.append("## Latency Comparison\n")
    md.append("| Model | Params | Loader | Avg Rerank (ms) | Avg Search (ms) |")
    md.append("|-------|--------|--------|-----------------|-----------------|")
    for r in results:
        md.append(f"| {r['model_label']} | {r['params']} | {r['loader']} | "
                  f"{r['avg_rerank_latency_ms']:.1f} | {r['avg_search_latency_ms']:.1f} |")
    md.append("\n## Stage Latencies\n")
    for r in results:
        md.append(f"\n### {r['model_label']}\n")
        md.append("| Stage | Avg Latency (ms) |")
        md.append("|-------|------------------|")
        for stage, lat in r['stage_latencies'].items():
            md.append(f"| {stage} | {lat:.1f} |")
    
    out_path = Path("data/reranker_benchmarks/DIRECT_API_BENCHMARK_RESULTS.md")
    out_path.write_text("\n".join(md), encoding="utf-8")
    log.info(f"Markdown saved: {out_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", help="Model names to test")
    args = parser.parse_args()
    asyncio.run(main())