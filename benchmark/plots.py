#!/usr/bin/env python3
"""10 required diagnostic plots from benchmark/metrics + raw results."""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
M = json.load(open(ROOT / "benchmark" / "metrics" / "overall_metrics.json"))
Q = [json.loads(l) for l in open(ROOT / "benchmark" / "metrics" / "metrics_by_query.jsonl")]
RAW = {}
for line in open(ROOT / "benchmark" / "raw" / "massive_results.jsonl"):
    r = json.loads(line)
    if r.get("status") == "SUCCESS":
        RAW[r["idx"]] = r

STAGES = ["bm25", "dense", "rrf", "final"]
LBL = {"bm25": "BM25", "dense": "Dense", "rrf": "RRF", "final": "CrossEncoder"}
COL = {"bm25": "#1f77b4", "dense": "#ff7f0e", "rrf": "#2ca02c", "final": "#d62728"}
P = ROOT / "benchmark" / "plots"
P.mkdir(parents=True, exist_ok=True)
KS = [1, 3, 5, 10, 20, 50, 100]


def p1_recall():
    fig, ax = plt.subplots(figsize=(8, 5))
    for s in STAGES:
        ax.plot(KS, [M[f"{s}_recall@{k}"] for k in KS], "o-", label=LBL[s], color=COL[s])
    ax.set_xscale("log"); ax.set_xticks(KS); ax.set_xticklabels(KS)
    ax.set_ylim(0, 1); ax.set_xlabel("K"); ax.set_ylabel("Recall@K")
    ax.set_title("Recall@K by stage"); ax.legend(); ax.grid(True, alpha=0.3)
    fig.savefig(P / "recall_at_k.png", dpi=120); plt.close(fig)


def p2_mrr():
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar([LBL[s] for s in STAGES], [M[f"{s}_mrr"] for s in STAGES],
           color=[COL[s] for s in STAGES])
    ax.set_ylim(0, 1); ax.set_ylabel("MRR"); ax.set_title("MRR by stage")
    fig.savefig(P / "mrr_comparison.png", dpi=120); plt.close(fig)


def p3_ndcg():
    fig, ax = plt.subplots(figsize=(8, 5))
    for s in STAGES:
        ax.plot([1, 3, 5, 10, 20], [M[f"{s}_ndcg@{k}"] for k in (1, 3, 5, 10, 20)],
                "o-", label=LBL[s], color=COL[s])
    ax.set_xlabel("K"); ax.set_ylabel("NDCG@K"); ax.set_title("NDCG@K by stage")
    ax.legend(); ax.grid(True, alpha=0.3)
    fig.savefig(P / "ndcg_at_k.png", dpi=120); plt.close(fig)


def gold_ranks(stage):
    return [e["ranks"].get(stage, -1) for e in Q]


def p4_rank_dist():
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    for ax, s in zip(axes.flat, STAGES):
        r = [x for x in gold_ranks(s) if x != -1]
        ax.hist(r, bins=min(50, max(10, len(set(r)))), color=COL[s])
        ax.set_title(f"{LBL[s]} (found {len(r)}/{len(Q)})")
        ax.set_xlabel("gold rank"); ax.set_ylabel("queries")
    fig.suptitle("Gold rank distribution by stage"); fig.tight_layout()
    fig.savefig(P / "gold_rank_distribution.png", dpi=120); plt.close(fig)


def p5_cdf():
    fig, ax = plt.subplots(figsize=(8, 5))
    xs = range(1, 101)
    for s in STAGES:
        r = gold_ranks(s)
        ax.plot(xs, [sum(1 for v in r if 0 < v <= k) / len(r) for k in xs],
                label=LBL[s], color=COL[s])
    ax.set_xlabel("K"); ax.set_ylabel("P(gold rank <= K)")
    ax.set_title("Gold rank CDF"); ax.legend(); ax.grid(True, alpha=0.3)
    fig.savefig(P / "gold_rank_cdf.png", dpi=120); plt.close(fig)


def _gain_plot(key, title, fname):
    cats, vals = [], []
    order = ["improved", "unchanged", "degraded", "recovered", "lost", "absent_both"]
    counts = {e[key] for e in Q}
    from collections import Counter
    c = Counter(e[key] for e in Q)
    labels = [o for o in order if o in c]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(labels, [c[o] for o in labels], color="#6a5acd")
    ax.set_title(title); ax.set_ylabel("queries")
    fig.savefig(P / fname, dpi=120); plt.close(fig)


def p8_candidate():
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ks = [10, 15, 20, 50, 100]
    ax.bar([str(k) for k in ks], [M.get(f"cand_recall@{k}", 0) for k in ks], color="#2ca02c")
    ax.set_ylim(0, 1); ax.set_xlabel("RRF top-K"); ax.set_ylabel("candidate recall")
    ax.set_title("CE candidate ceiling (gold in RRF pool)")
    fig.savefig(P / "candidate_recall.png", dpi=120); plt.close(fig)


def p9_scores():
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    spec = [("bm25", "bm25_score"), ("dense", "dense_score"),
            ("rrf", "hybrid_score"), ("final", "rerank_score")]
    for ax, (s, sk) in zip(axes.flat, spec):
        vals = []
        for idx, e in enumerate(Q):
            row = RAW.get(e["idx"])
            if not row:
                continue
            for d in row["stages"][s][:20]:
                v = d["scores"].get(sk)
                if v is not None:
                    vals.append(v)
        ax.hist(vals, bins=50, color=COL[s])
        ax.set_title(f"{LBL[s]} {sk} (n={len(vals)})")
    fig.suptitle("Score distributions (top-20/stage)")
    fig.tight_layout(); fig.savefig(P / "score_distributions.png", dpi=120); plt.close(fig)


def p10_failures():
    from collections import Counter
    c = Counter(e["category"] for e in Q)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(list(c.keys()), list(c.values()), color="#cd5c5c")
    ax.set_title("Failure category distribution"); ax.set_ylabel("queries")
    plt.xticks(rotation=20, ha="right"); fig.tight_layout()
    fig.savefig(P / "failure_categories.png", dpi=120); plt.close(fig)


p1_recall(); p2_mrr(); p3_ndcg(); p4_rank_dist(); p5_cdf()
_gain_plot("rrf_vs_best_leg", "RRF vs best leg (rank space)", "rrf_gain_loss.png")
_gain_plot("ce_vs_rrf", "Cross-encoder vs RRF (rank space)", "cross_encoder_gain_loss.png")
p8_candidate(); p9_scores(); p10_failures()
print("plots ->", P)
