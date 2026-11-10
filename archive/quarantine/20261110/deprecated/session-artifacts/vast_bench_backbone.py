"""Retrieval benchmark for ONE reranker backbone (own process, CPU).
Usage: bench_backbone.py <variant> <model_id_or_DEFAULT> <pool> <dataset_json> <out_json> [top_k]
Env needed: KB_DB_URL, HF_HOME, HF_HUB_CACHE, HF_HUB_OFFLINE, OMP_NUM_THREADS.
"""
import json
import os
import sys

VARIANT = sys.argv[1]
MODEL = sys.argv[2]
POOL = int(sys.argv[3])
DATASET = sys.argv[4]
OUT = sys.argv[5]
TOP_K = int(sys.argv[6]) if len(sys.argv) > 6 else 5

os.environ["KB_RERANK_POOL"] = str(POOL)
if MODEL != "DEFAULT":
    os.environ["KB_RERANKER_MODEL"] = MODEL

sys.path.insert(0, "/workspace/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager")
os.chdir("/workspace/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager")

import torch  # noqa: E402

torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "12")))

import asyncio

from kb_manager.evaluation.benchmark import BenchmarkRunner, summarize_ir_metrics  # noqa: E402
from kb_manager.web.routes.search import search_knowledge_base  # noqa: E402

# One persistent event loop per worker: the asyncpg pool binds connections to
# the loop that first uses it, so asyncio.run() per query breaks queries 2+
# ("another operation is in progress"). Production (uvicorn) is single-loop.
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def search_fn(query: str, k: int):
    steps = _LOOP.run_until_complete(search_knowledge_base(query, k))
    return [(r.chunk_id, r.hybrid_score) for r in steps.final_results]


def main():
    from kb_manager.evaluation.benchmark import BenchmarkResult
    dataset = json.load(open(DATASET, encoding="utf-8"))
    items = dataset if isinstance(dataset, list) else dataset.get("items", dataset.get("questions", []))
    sub_file = os.environ.get("BENCH_INDICES")
    if sub_file:
        idx = json.load(open(sub_file))
        items = [items[i] for i in idx]
        print(f"[{VARIANT}] subset: {len(items)} queries", flush=True)
    # resume from partial output if present
    done_ids: set[int] = set()
    prev_queries: list[dict] = []
    if os.path.exists(OUT):
        try:
            prev = json.load(open(OUT, encoding="utf-8"))
            for q in prev.get("queries", []):
                if q.get("_idx") is not None:
                    done_ids.add(q["_idx"])
                    prev_queries.append(q)
            print(f"[{VARIANT}] resuming: {len(done_ids)} done", flush=True)
        except Exception:
            pass
    print(f"[{VARIANT}] {len(items)} queries, model={MODEL}, pool={POOL}, top_k={TOP_K}", flush=True)
    runner = BenchmarkRunner(search_fn, top_k=TOP_K, version=f"reranker-{VARIANT}")
    result = BenchmarkResult(version=f"reranker-{VARIANT}",
                             created_at="", top_k=TOP_K, total_queries=len(items))
    queries = list(prev_queries)
    pending = [(n, it) for n, it in enumerate(items) if n not in done_ids]
    import time as _time
    for pos, (n, item) in enumerate(pending, 1):
        start = _time.monotonic()
        try:
            raw = search_fn(item.get("query", ""), TOP_K)
            retrieved = [r[0] for r in raw] if raw else []
        except Exception as e:
            retrieved = []
            print(f"[{VARIANT}] query {n} ERROR: {str(e)[:120]}", flush=True)
        elapsed_ms = round((_time.monotonic() - start) * 1000, 1)
        expected = item.get("expected_chunk_ids", [])
        rank = next((i + 1 for i, cid in enumerate(retrieved) if cid in expected), -1)
        queries.append({
            "query": item.get("query", ""), "expected_ids": expected,
            "format": item.get("format", "verbatim"), "difficulty": item.get("difficulty", "medium"),
            "hit": rank != -1, "rank": rank, "top1_hit": rank == 1,
            "elapsed_ms": elapsed_ms, "retrieved_ids": retrieved, "_idx": n,
        })
        if pos % 25 == 0 or pos == len(pending):
            print(f"[{VARIANT}] {len(queries)}/{len(items)}", flush=True)
        if pos % 100 == 0:
            result.queries = queries
            result.overall = runner._aggregate([
                type("Q", (), {"hit": q["hit"], "top1_hit": q["top1_hit"], "rank": q["rank"],
                               "elapsed_ms": q["elapsed_ms"]})() for q in queries])
            d = result.to_dict()
            d["variant"] = VARIANT
            json.dump(d, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    result.queries = queries
    result.created_at = __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat()
    result.by_format = {}
    for fmt in sorted({q["format"] for q in queries}):
        result.by_format[fmt] = runner._aggregate([
            type("Q", (), {"hit": q["hit"], "top1_hit": q["top1_hit"], "rank": q["rank"],
                           "elapsed_ms": q["elapsed_ms"]})() for q in queries if q["format"] == fmt])
    result.overall = runner._aggregate([
        type("Q", (), {"hit": q["hit"], "top1_hit": q["top1_hit"], "rank": q["rank"],
                       "elapsed_ms": q["elapsed_ms"]})() for q in queries])
    try:
        ir = summarize_ir_metrics(result)
    except Exception as e:
        ir = {"error": str(e)[:200]}
    d = result.to_dict()
    d["variant"] = VARIANT
    d["reranker_model"] = MODEL
    d["pool"] = POOL
    d["ir_metrics"] = ir
    json.dump(d, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[{VARIANT}] overall={json.dumps(d['overall'], ensure_ascii=False)}", flush=True)
    print(f"[{VARIANT}] ir={json.dumps(ir, ensure_ascii=False)[:300]}", flush=True)
    print(f"[{VARIANT}] saved -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
