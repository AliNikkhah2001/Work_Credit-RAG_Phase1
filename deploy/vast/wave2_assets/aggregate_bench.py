"""Aggregate per-variant benchmark JSONs -> comparison table, plots, report.
Usage: aggregate_bench.py <glob_or_files...> --outdir eval/results
Reads bench_<variant>.json files with {summary, results, overall/by_format/ir_metrics}.
"""
import glob
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def load(path):
    d = json.load(open(path, encoding="utf-8"))
    s = d.get("summary", {})
    o = d.get("overall", {})
    ir = d.get("ir_metrics", {}) or {}
    return {
        "variant": d.get("variant", os.path.basename(path)),
        "model": d.get("reranker_model", "?"),
        "n": s.get("n", d.get("total_queries", 0)),
        "hit_rate": o.get("hit_rate"),
        "top1": o.get("top1_hit_rate"),
        "mrr": o.get("mrr"),
        "avg_rank": o.get("avg_rank"),
        "latency": o.get("avg_latency_ms"),
        "ndcg": ir.get("ndcg_at_k") or ir.get("ndcg"),
        "recall": ir.get("recall_at_k") or ir.get("recall"),
        "by_format": d.get("by_format", {}),
    }


def main(paths, outdir):
    rows = [load(p) for p in paths]
    os.makedirs(outdir, exist_ok=True)
    # console table
    print(f"{'variant':<12} {'hit':>6} {'top1':>6} {'mrr':>6} {'ndcg':>6} {'lat/ms':>8}")
    for r in rows:
        ndcg = r["ndcg"]
        ndcg_s = f"{ndcg:.4f}" if isinstance(ndcg, (int, float)) else "-"
        print(f"{r['variant']:<12} {r['hit_rate'] or 0:>6.4f} {r['top1'] or 0:>6.4f} "
              f"{r['mrr'] or 0:>6.4f} {ndcg_s:>6} {r['latency'] or 0:>8.1f}")
    json.dump(rows, open(os.path.join(outdir, "reranker_benchmark_summary.json"), "w"), indent=1)
    # plots
    names = [r["variant"] for r in rows]
    x = range(len(names))
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, key, title in [
        (axes[0, 0], "hit_rate", "Hit rate@5"),
        (axes[0, 1], "mrr", "MRR"),
        (axes[1, 0], "top1", "Top-1 rate"),
        (axes[1, 1], "latency", "Avg latency ms/query"),
    ]:
        vals = [(r[key] or 0) for r in rows]
        ax.bar(list(x), vals)
        ax.set_title(title)
        ax.set_xticks(list(x), names, rotation=20, ha="right")
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "reranker_benchmark_metrics.png"), dpi=110)
    print("saved summary + plot ->", outdir)
    # by-format hit table
    fmts = sorted({f for r in rows for f in r["by_format"]})
    print(f"\n{'format':<16}" + "".join(f"{n:>10}" for n in names))
    for f in fmts:
        line = f"{f:<16}"
        for r in rows:
            v = (r["by_format"].get(f) or {}).get("hit_rate")
            line += f"{(v if v is not None else float('nan')):>10.3f}"
        print(line)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    outdir = sys.argv[sys.argv.index("--outdir") + 1] if "--outdir" in sys.argv else "eval/results"
    paths = []
    for a in args:
        paths.extend(sorted(glob.glob(a)))
    main(paths, outdir)
