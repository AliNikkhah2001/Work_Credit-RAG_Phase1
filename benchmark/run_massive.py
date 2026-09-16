#!/usr/bin/env python3
"""Massive stage-capture retrieval benchmark (extends the repo's benchmark infra).

For every query in benchmark/datasets/eval_remapped.json, captures the full
retrieval trajectory through the PRODUCTION pipeline (same code path as
search_knowledge_base, same env pool/model):
  BM25 (depth 100) -> Dense (depth 100) -> RRF (depth 100) -> CE rerank (pool=15 prod)

Usage:
  KB_DB_URL=postgresql+asyncpg://... KB_RERANK_POOL=15 /tmp/kb-venv/bin/python benchmark/run_massive.py [--indices-file F] [--out DIR] [--top-k 10] [--depth 100]

Resume: re-running with the same --out continues from benchmark/raw/massive_results.jsonl
Env needed: KB_DB_URL, HF_HOME, HF_HUB_CACHE, HF_HUB_OFFLINE.
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "components" / "knowledgebase" / "kb-manager"))
os.chdir(str(ROOT / "components" / "knowledgebase" / "kb-manager"))

import torch  # noqa: E402

torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "12")))

from kb_manager.web.routes.search import search_knowledge_base  # noqa: E402
from kb_manager.reranker import get_rerank_pool, get_reranker_model_name  # noqa: E402

# One persistent event loop: the asyncpg pool binds to the loop that first
# uses it (same pattern as handoff/scripts/bench_backbone.py).
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)

TOP_K = 10
DEPTH = 100


def search_stages(query: str, top_k: int, depth: int, keyword_boost=None) -> dict:
    steps = _LOOP.run_until_complete(
        search_knowledge_base(query, top_k, keyword_boost=keyword_boost, stage_depth=depth))

    def pack(lst, score_keys):
        out = []
        for r in lst:
            d = r.model_dump() if hasattr(r, "model_dump") else dict(r)
            out.append({
                "id": d.get("chunk_id"),
                "scores": {k: d.get(k) for k in score_keys},
                "doc_id": d.get("doc_id"),
                "title": d.get("doc_title"),
            })
        return out

    return {
        "bm25": pack(steps.bm25_results, ["bm25_score"]),
        "dense": pack(steps.dense_results, ["dense_score", "semantic_score"]),
        "rrf": pack(steps.merged_candidates, ["hybrid_score", "bm25_score", "dense_score"]),
        "final": pack(steps.final_results, ["rerank_score", "hybrid_score"]),
        "tokens": steps.tokens,
        "total_indexed": steps.total_chunks_indexed,
        "elapsed_ms": steps.elapsed_ms,
        "rerank_ms": steps.rerank_ms,
    }


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                                       text=True).strip()
    except Exception:
        return "unknown"


def corpus_fingerprint() -> dict:
    """Count + ID hash + embedding coverage of the live chunks table.

    Guards reproducibility: concurrent re-ingests change the corpus under us.
    """
    import hashlib

    async def _fp():
        from sqlalchemy import text as sqltext
        from kb_manager.config import load_config
        from kb_manager.models.database import Database
        cfg = load_config()
        db = Database(cfg.db)
        async with db.session() as s:
            try:
                n = (await s.execute(sqltext("SELECT count(*) FROM chunks"))).scalar()
            except Exception:
                n = -1
            try:
                ne = (await s.execute(
                    sqltext("SELECT count(*) FROM chunks WHERE embedding IS NOT NULL"))).scalar()
            except Exception:
                ne = -1
            try:
                rows = (await s.execute(sqltext("SELECT id FROM chunks ORDER BY id"))).fetchall()
                h = hashlib.md5(",".join(r[0] for r in rows).encode()).hexdigest()
            except Exception:
                h = "unknown"
        await db.close()
        return {"chunk_count": n, "embedded_count": ne, "id_hash": h}

    return _LOOP.run_until_complete(_fp())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indices-file", default=None)
    ap.add_argument("--out", default=str(ROOT / "benchmark" / "raw"))
    ap.add_argument("--top-k", type=int, default=TOP_K)
    ap.add_argument("--depth", type=int, default=DEPTH)
    ap.add_argument("--keyword-boost", type=float, default=None,
                    help="override KB keyword boost (default: server env)")
    args = ap.parse_args()

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "massive_results.jsonl"

    ds = json.load(open(ROOT / "benchmark" / "datasets" / "eval_remapped.json", encoding="utf-8"))
    items = ds["items"]
    if args.indices_file:
        idx = json.load(open(args.indices_file))
        items = [(i, ds["items"][i]) for i in idx]
    else:
        items = list(enumerate(ds["items"]))

    done: set[int] = set()
    if jsonl_path.exists():
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["idx"])
                except Exception:
                    pass
        print(f"resuming: {len(done)} done", flush=True)

    config = {
        "git_sha": git_sha(),
        "corpus_start": corpus_fingerprint(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reranker_model": get_reranker_model_name(),
        "rerank_pool": get_rerank_pool(),
        "top_k": args.top_k,
        "stage_depth": args.depth,
        "keyword_boost_override": args.keyword_boost,
        "dataset_meta": ds["meta"],
        "env": {k: os.getenv(k, "") for k in
                 ["KB_RERANK_POOL", "KB_RERANKER_MODEL", "KB_KEYWORD_BOOST",
                  "KB_SYNONYM_ENABLED", "KB_SYNONYM_BEAM", "KB_EMBED_MODEL",
                  "KB_RERANKER_DEVICE", "KB_DB_URL", "OMP_NUM_THREADS"]},
    }
    json.dump(config, open(out_dir / "massive_config.json", "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)

    pending = [(n, it) for n, it in items if n not in done]
    print(f"queries: {len(items)} total, {len(pending)} pending", flush=True)
    t_all = time.monotonic()
    with open(jsonl_path, "a", encoding="utf-8") as f:
        for pos, (n, item) in enumerate(pending, 1):
            t0 = time.monotonic()
            rec: dict = {"idx": n, "query": item["query"],
                         "relevance": item["relevance_scores"],
                         "n_gold": len(item["expected_chunk_ids"])}
            try:
                if not item["expected_chunk_ids"]:
                    rec["status"] = "NO_GOLD"
                else:
                    rec["stages"] = search_stages(item["query"], args.top_k, args.depth,
                                                      args.keyword_boost)
                    rec["status"] = "SUCCESS"
            except Exception as e:  # noqa: BLE001 - taxonomy requires explicit capture
                rec["status"] = "SEARCH_ERROR"
                rec["error"] = str(e)[:300]
            rec["wall_ms"] = round((time.monotonic() - t0) * 1000, 1)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if pos % 10 == 0 or pos == len(pending):
                el = time.monotonic() - t_all
                print(f"[{pos}/{len(pending)}] idx={n} status={rec['status']} "
                      f"wall={rec['wall_ms']}ms elapsed={el:.0f}s", flush=True)
    print(f"DONE {len(pending)} queries in {time.monotonic()-t_all:.0f}s -> {jsonl_path}", flush=True)
    end_fp = corpus_fingerprint()
    print(f"corpus end: {end_fp}", flush=True)
    cfg_path = out_dir / "massive_config.json"
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    cfg["corpus_end"] = end_fp
    cfg["corpus_stable"] = (cfg.get("corpus_start") == end_fp)
    json.dump(cfg, open(cfg_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    if not cfg["corpus_stable"]:
        print("WARNING: corpus changed mid-run - results may mix corpora!", flush=True)


if __name__ == "__main__":
    main()
