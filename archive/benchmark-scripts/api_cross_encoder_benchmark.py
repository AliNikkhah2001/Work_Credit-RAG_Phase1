#!/usr/bin/env python3
"""
Cross-Encoder Reranker Benchmark - Practical Version
Tests reranker models against the running KB search API.
Measures: latency, ranking quality, RRF vs reranker effect.
"""

import os
import sys
import json
import time
import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from typing import TYPE_CHECKING

import httpx
import numpy as np

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

# ─── Config ──────────────────────────────────────────────────────────
KB_URL = os.getenv("KB_URL", "http://127.0.0.1:8000")
ORCH_URL = os.getenv("ORCH_URL", "http://127.0.0.1:8100")
RESULTS_DIR = Path("data/reranker_benchmarks")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ─── Models to Test ──────────────────────────────────────────────────
RERANKER_MODELS = [
    # Baseline (current)
    {"name": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", "params": "118M", "loader": "crossencoder", "label": "mmarco (baseline)"},
    # BGE family
    {"name": "BAAI/bge-reranker-v2-m3", "params": "568M", "loader": "crossencoder", "label": "bge-reranker-v2-m3"},
    {"name": "BAAI/bge-reranker-v2-gemma", "params": "2.5B", "loader": "flag-llm", "label": "bge-reranker-v2-gemma"},
    # Qwen3 family
    {"name": "Qwen/Qwen3-Reranker-0.6B", "params": "0.6B", "loader": "flag-llm", "label": "Qwen3-Reranker-0.6B"},
    {"name": "Qwen/Qwen3-Reranker-4B", "params": "4B", "loader": "flag-llm", "label": "Qwen3-Reranker-4B"},
    # Jina
    {"name": "jinaai/jina-reranker-v3", "params": "0.6B", "loader": "crossencoder", "label": "jina-reranker-v3"},
    # GTE
    {"name": "Alibaba-NLP/gte-multilingual-reranker-base", "params": "~300M", "loader": "crossencoder", "label": "gte-multilingual-reranker-base"},
]

# Test queries (diverse Persian credit queries)
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
    "در این باره بگویید که همان‌طور که اشاره شد در صورت گسترده در سیستم بازپرداخت در تأخیر اقساط ارائه شود، شرکت چگونه وضعیت مدیریت می‌کند؟",
    "لطفاً بگویید همان‌طور که اشاره شد اطلاعات در باید قالب استاندارد شوند و چرا است؟؟",
    "ببخشید، داده‌های مربوط به بدهی بیمه‌ای و تامین اجتماعی چگونه پردازش میشن . لطفاً دقیق توضیح دهید.",
    "آیا دادههای بورس و اوراق بهادار نیز ارسال می‌شود؟",
]

@dataclass
class StageMetrics:
    stage: str
    retrieved_ids: List[str]
    scores: List[float]
    elapsed_ms: float

@dataclass
class QueryResult:
    query: str
    stages: Dict[str, StageMetrics]
    rerank_latency_ms: float
    total_latency_ms: float

@dataclass
class ModelResult:
    model_name: str
    model_label: str
    params: str
    loader: str
    total_queries: int
    avg_rerank_latency_ms: float
    avg_total_latency_ms: float
    stage_latencies: Dict[str, float]
    queries: List[Dict]


async def search_kb(query: str, top_k: int = 100, reranker: str = None) -> Dict:
    """Call KB search API."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        payload = {"query": query, "top_k": top_k}
        if reranker:
            payload["reranker_model"] = reranker
        start = time.perf_counter()
        resp = await client.post(f"{KB_URL}/search/api", json=payload)
        elapsed = (time.perf_counter() - start) * 1000
        if resp.status_code != 200:
            raise Exception(f"Search failed: {resp.status_code} {resp.text}")
        data = resp.json()
        return {"data": data, "latency_ms": elapsed}


async def search_without_rerank(query: str, top_k: int = 50) -> Dict:
    """Search without reranker (BM25 + Dense + RRF only)."""
    return await search_kb(query, top_k, reranker="")


async def search_with_rerank(query: str, top_k: int = 5, reranker_model: str = None) -> Dict:
    """Search with specific reranker model."""
    return await search_kb(query, top_k, reranker=reranker_model)


def compute_ranking_metrics(rrf_ids: list, reranked_ids: list, expected_ids: list) -> dict:
    """Compare RRF vs reranked ranking quality."""
    metrics = {}
    
    # Position of first relevant in RRF
    rrf_first_rel = -1
    for i, doc_id in enumerate(rrf_ids):
        if doc_id in expected_ids:
            metrics["rrf_first_relevant_rank"] = i + 1
            break
    else:
        metrics["rrf_first_relevant_rank"] = -1
    
    # Position of first relevant in reranked
    rerank_first_rel = -1
    for i, doc_id in enumerate(reranked_ids):
        if doc_id in expected_ids:
            metrics["rerank_first_relevant_rank"] = i + 1
            break
    else:
        metrics["rerank_first_relevant_rank"] = -1
    
    # Improvement
    if metrics["rrf_first_relevant_rank"] > 0 and metrics["rerank_first_relevant_rank"] > 0:
        metrics["rank_improvement"] = metrics["rrf_first_relevant_rank"] - metrics["rerank_first_relevant_rank"]
    else:
        metrics["rank_improvement"] = 0
    
    return metrics


async def benchmark_model(model_spec: dict) -> dict:
    """Benchmark a single reranker model."""
    model_name = model_spec["name"]
    log.info(f"Benchmarking: {model_spec['label']} ({model_name})")
    
    results = []
    total_rerank_latency = 0
    total_latency = 0
    stage_latencies = {"search_without_rerank": [], "search_with_rerank": [], "rerank_only": []}
    improvements = []
    
    for i, query in enumerate(TEST_QUERIES):
        log.info(f"  [{i+1}/{len(TEST_QUERIES)}] {query[:50]}...")
        
        # Stage 1: Search without reranker (BM25 + Dense + RRF)
        rrf_result = await search_without_rerank(query, top_k=50)
        rrf_latency = rrf_result["latency_ms"]
        rrf_ids = [r["chunk_id"] for r in rrf_result["data"]["final_results"][:10]]
        
        # Stage 2: Search with reranker
        rerank_result = await search_with_rerank(query, top_k=5, reranker_model=model_spec["name"])
        total_latency_ms = rerank_result["latency_ms"]
        reranked_ids = [r["chunk_id"] for r in rerank_result["data"]["final_results"]]
        
        # Estimate rerank latency (total - search_without_rerank would be approximate)
        rerank_latency = total_latency_ms - rrf_latency
        
        # Metrics (using heuristic - no ground truth chunk IDs available)
        # We can still measure: latency, rank changes, score distribution
        rerank_scores = [r.get("rerank_score", 0) for r in rerank_result["data"]["final_results"]]
        
        result = {
            "query": query,
            "rrf_latency_ms": rrf_latency,
            "total_latency_ms": total_latency_ms,
            "rerank_latency_ms": max(0, rerank_latency),
            "rrf_top_ids": rrf_ids[:10],
            "reranked_ids": reranked_ids,
            "rerank_scores": rerank_scores,
            "score_mean": np.mean(rerank_scores) if rerank_scores else 0,
            "score_std": np.std(rerank_scores) if rerank_scores else 0,
        }
        results.append(result)
        
        stage_latencies["search_without_rerank"].append(rrf_latency)
        stage_latencies["search_with_rerank"].append(total_latency_ms)
        stage_latencies["rerank_only"].append(max(0, rerank_latency))
        total_rerank_latency += max(0, rerank_latency)
        total_latency += total_latency_ms
        
        if i % 5 == 0:
            log.info(f"  Progress: {i+1}/{len(TEST_QUERIES)}")
    
    # Aggregate
    n = len(TEST_QUERIES)
    return {
        "model_name": model_spec["name"],
        "model_label": model_spec["label"],
        "params": model_spec["params"],
        "loader": model_spec["loader"],
        "total_queries": len(TEST_QUERIES),
        "avg_rerank_latency_ms": round(total_rerank_latency / n, 1),
        "avg_total_latency_ms": round(total_latency / n, 1),
        "avg_search_latency_ms": round(sum(stage_latencies["search_without_rerank"]) / len(TEST_QUERIES), 1),
        "stage_latencies": {k: round(sum(v)/len(v), 1) for k, v in stage_latencies.items() if v},
        "queries": results
    }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", help="Model names to test")
    parser.add_argument("--output", default="data/reranker_benchmarks")
    args = parser.parse_args()
    
    RESULTS_DIR = Path(args.output)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Check KB health
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{KB_URL}/health")
            log.info(f"KB Health: {resp.json()}")
        except Exception as e:
            log.error(f"KB not reachable at {KB_URL}: {e}")
            return
    
    # Filter models
    models_to_test = RERANKER_MODELS
    if args.models:
        models_to_test = [m for m in RERANKER_MODELS if m["name"] in args.models]
    
    log.info(f"Testing {len(models_to_test)} models: {[m['label'] for m in models_to_test]}")
    
    all_results = []
    for model_spec in models_to_test:
        try:
            result = await benchmark_model(model_spec)
            all_results.append(result)
            
            # Save individual
            out_path = Path(args.output) / f"benchmark_{model_spec['label'].replace('/', '_').replace('-', '_')}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            log.info(f"Saved: {out_path}")
        except Exception as e:
            log.error(f"Failed on {model_spec['label']}: {e}")
            import traceback
            traceback.print_exc()
    
    # Save combined
    combined_path = Path(args.output) / "api_benchmark_results.json"
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    log.info(f"Combined saved: {combined_path}")
    
    # Print comparison
    print("\n" + "="*100)
    print("API BENCHMARK COMPARISON")
    print("="*100)
    print(f"{'Model':<35} {'Params':>8} {'Loader':<12} {'Avg Rerank':>12} {'Avg Total':>12} {'Avg Search':>12}")
    print("-"*100)
    for r in all_results:
        print(f"{r['model_label']:<35} {r['params']:>8} {r['loader']:<12} "
              f"{r['avg_rerank_latency_ms']:>12.1f} {r['avg_total_latency_ms']:>12.1f} {r['avg_search_latency_ms']:>12.1f}")
    
    # Generate markdown
    generate_md(all_results, Path(args.output) / "API_BENCHMARK_RESULTS.md")


def generate_md(results: list, out_path: Path):
    md = ["# Cross-Encoder Reranker API Benchmark Results\n"]
    md.append(f"*Generated: {datetime.now(timezone.utc).isoformat()}*\n")
    md.append(f"*KB URL: {KB_URL}*\n")
    md.append(f"*Test Queries: {len(TEST_QUERIES)} diverse Persian credit queries*\n")
    md.append("## Latency Comparison\n")
    md.append("| Model | Params | Loader | Avg Rerank (ms) | Avg Total (ms) | Avg Search (ms) |")
    md.append("|-------|--------|--------|-----------------|----------------|-----------------|")
    for r in results:
        md.append(f"| {r['model_label']} | {r['params']} | {r['loader']} | "
                  f"{r['avg_rerank_latency_ms']:.1f} | {r['avg_total_latency_ms']:.1f} | {r['avg_search_latency_ms']:.1f} |")
    md.append("\n## Stage Latencies\n")
    for r in results:
        md.append(f"\n### {r['model_label']}\n")
        md.append("| Stage | Avg Latency (ms) |")
        md.append("|-------|------------------|")
        for stage, lat in r['stage_latencies'].items():
            md.append(f"| {stage} | {lat:.1f} |")
    
    out_path = Path("data/reranker_benchmarks/API_BENCHMARK_RESULTS.md")
    out_path.write_text("\n".join(md), encoding="utf-8")
    log.info(f"Markdown saved: {out_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+")
    parser.add_argument("--output", default="data/reranker_benchmarks")
    args = parser.parse_args()
    asyncio.run(main())