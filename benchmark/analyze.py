#!/usr/bin/env python3
"""Analyze massive benchmark results: per-stage metrics, candidate recall,
gold positions, failure categories, RRF/CE gain-loss.

Reads benchmark/raw/massive_results.jsonl -> writes:
  benchmark/metrics/overall_metrics.json   (per-stage means at all K + MRR)
  benchmark/metrics/metrics_by_query.jsonl (per-query per-stage metrics)
  benchmark/diagnostics/failure_analysis.jsonl
  benchmark/diagnostics/gold_ranks.jsonl
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(os.getenv("BENCH_ROOT", Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(ROOT))
from benchmark.metrics import K_VALUES, query_metrics

STAGES = ["bm25", "dense", "rrf", "final"]
STAGE_LABEL = {"bm25": "BM25", "dense": "Dense", "rrf": "RRF", "final": "CrossEncoder"}


def stage_ids(stages: dict, stage: str):
    return [d["id"] for d in stages.get(stage, [])]


def classify(row: dict, ranks: dict) -> str:
    """Failure category from gold-rank pattern across stages."""
    b, d, r, f = (ranks.get(s, -1) for s in STAGES)
    in_top = lambda x, k=5: x != -1 and x <= k
    if all(x == -1 for x in (b, d, r, f)):
        return "GOLD_ABSENT_ALL"
    if f != -1:
        return "NO_FAILURE"
    # final misses but RRF saw it
    if r != -1:
        return "CROSS_ENCODER_FAILURE"
    if b != -1 and d != -1:
        return "RRF_FAILURE"
    if b != -1:
        return "DENSE_FAILURE"
    if d != -1:
        return "BM25_FAILURE"
    return "CANDIDATE_GENERATION_FAILURE"


def main():
    raw = ROOT / "benchmark" / "raw" / "massive_results.jsonl"
    rows = [json.loads(l) for l in open(raw, encoding="utf-8")]
    ok = [r for r in rows if r.get("status") == "SUCCESS" and r.get("n_gold", 0) > 0]
    nogold = [r["idx"] for r in rows if r.get("status") == "NO_GOLD" or
              (r.get("status") == "SUCCESS" and not r.get("n_gold"))]
    err = [r for r in rows if r.get("status") not in ("SUCCESS", "NO_GOLD")]
    print(f"rows={len(rows)} ok={len(ok)} no_gold={len(nogold)} errors={len(err)}")

    per_query = []
    for r in ok:
        rel = r["relevance"]
        entry = {"idx": r["idx"], "query": r["query"][:80], "n_gold": r["n_gold"],
                 "wall_ms": r.get("wall_ms")}
        ranks = {}
        for s in STAGES:
            ids = stage_ids(r["stages"], s)
            try:
                m = query_metrics(ids, rel)
            except ValueError:
                continue
            ranks[s] = m["gold_rank"]
            for k in K_VALUES:
                entry[f"{s}_recall@{k}"] = m[f"recall@{k}"]
                entry[f"{s}_hit@{k}"] = m[f"hit@{k}"]
                entry[f"{s}_ndcg@{k}"] = m[f"ndcg@{k}"]
            entry[f"{s}_rr"] = m["rr"]
        entry["ranks"] = ranks
        entry["category"] = classify(r, ranks)
        # RRF gain/loss vs best leg; CE gain/loss vs RRF (rank space, lower better; -1=absent)
        best_leg = min([v for v in (ranks.get("bm25", -1), ranks.get("dense", -1)) if v != -1],
                       default=-1)
        entry["rrf_vs_best_leg"] = _cmp(best_leg, ranks.get("rrf", -1))
        entry["ce_vs_rrf"] = _cmp(ranks.get("rrf", -1), ranks.get("final", -1))
        per_query.append(entry)

    # Aggregate means
    overall: dict = {"n": len(per_query), "n_no_gold": len(nogold), "n_errors": len(err),
                     "no_gold_idx": nogold,
                     "error_idx": [r["idx"] for r in err]}
    for s in STAGES:
        for k in K_VALUES:
            vals = [e[f"{s}_recall@{k}"] for e in per_query]
            overall[f"{s}_recall@{k}"] = round(sum(vals) / len(vals), 4) if vals else 0.0
            vals = [e[f"{s}_ndcg@{k}"] for e in per_query]
            overall[f"{s}_ndcg@{k}"] = round(sum(vals) / len(vals), 4) if vals else 0.0
            vals = [e[f"{s}_hit@{k}"] for e in per_query]
            overall[f"{s}_hit@{k}"] = round(sum(vals) / len(vals), 4) if vals else 0.0
        vals = [e[f"{s}_rr"] for e in per_query]
        overall[f"{s}_mrr"] = round(sum(vals) / len(vals), 4) if vals else 0.0
    # candidate recall: RRF gold present at K (pool-independent ceiling for CE)
    for k in (10, 15, 20, 50, 100):
        overall[f"cand_recall@{k}"] = overall.get(f"rrf_recall@{k}", 0.0)
    overall["categories"] = dict(Counter(e["category"] for e in per_query))
    overall["rrf_gain"] = dict(Counter(e["rrf_vs_best_leg"] for e in per_query))
    overall["ce_gain"] = dict(Counter(e["ce_vs_rrf"] for e in per_query))

    out_m = ROOT / "benchmark" / "metrics"
    out_d = ROOT / "benchmark" / "diagnostics"
    out_m.mkdir(parents=True, exist_ok=True)
    out_d.mkdir(parents=True, exist_ok=True)
    json.dump(overall, open(out_m / "overall_metrics.json", "w"), indent=2)
    with open(out_m / "metrics_by_query.jsonl", "w") as f:
        for e in per_query:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    fails = [e for e in per_query if e["category"] != "NO_FAILURE"]
    with open(out_d / "failure_analysis.jsonl", "w") as f:
        for e in fails:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    with open(out_d / "gold_ranks.jsonl", "w") as f:
        for e in per_query:
            f.write(json.dumps({"idx": e["idx"], "ranks": e["ranks"],
                                "category": e["category"]}, ensure_ascii=False) + "\n")
    print(f"analyzed {len(per_query)} queries -> {out_m}/overall_metrics.json")
    print("categories:", overall["categories"])
    print("ce_vs_rrf:", overall["ce_gain"])


def _cmp(before: int, after: int) -> str:
    if before == -1 and after == -1:
        return "absent_both"
    if before == -1:
        return "recovered"
    if after == -1:
        return "lost"
    if after < before:
        return "improved"
    if after == before:
        return "unchanged"
    return "degraded"


if __name__ == "__main__":
    main()
