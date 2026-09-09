"""Answer-statistics plots for the RAG benchmark report.

Usage: python eval/make_plots.py --bench eval/results/llm_answer_benchmark_v3.json
       --judge eval/results/llm_judge_v3.json --outdir eval/results/plots --tag v3
Also supports --compare A.json B.json for Q4-vs-Q8 similarity comparison.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def plot_sim_hist(results: list[dict], out: Path) -> None:
    sims = [r["similarity"] for r in results]
    plt.figure(figsize=(7, 4))
    plt.hist(sims, bins=20, edgecolor="black")
    plt.axvline(sum(sims) / len(sims), linestyle="--", label=f"mean {sum(sims)/len(sims):.3f}")
    plt.xlabel("cosine similarity (answer vs ground truth)")
    plt.ylabel("questions")
    plt.title("Answer similarity distribution")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out, dpi=120)
    plt.close()


def plot_format_means(results: list[dict], out: Path) -> None:
    by: dict[str, list[float]] = {}
    for r in results:
        by.setdefault(r.get("format", "?"), []).append(r["similarity"])
    labels = sorted(by)
    means = [sum(v) / len(v) for v in (by[k] for k in labels)]
    plt.figure(figsize=(7, 4))
    plt.bar(labels, means)
    plt.ylim(0, 1)
    plt.ylabel("mean similarity")
    plt.title("Robustness to wording (same info, different phrasing)")
    plt.xticks(rotation=20)
    plt.tight_layout()
    plt.savefig(out, dpi=120)
    plt.close()


def plot_citations(results: list[dict], out: Path) -> None:
    from collections import Counter
    c = Counter(r["n_citations"] for r in results if r.get("finish_reason") == "stop")
    xs = sorted(c)
    plt.figure(figsize=(6, 4))
    plt.bar([str(x) for x in xs], [c[x] for x in xs])
    plt.xlabel("citations per answer")
    plt.ylabel("answers")
    plt.title("Citation counts (cap = 2)")
    plt.tight_layout()
    plt.savefig(out, dpi=120)
    plt.close()


def plot_judge(judge: dict, out: Path) -> None:
    dims = ["faithfulness", "correctness", "tone", "citation"]
    vals = []
    for d in dims:
        xs = [r.get(d) for r in judge["results"] if isinstance(r.get(d), (int, float))]
        vals.append(sum(xs) / len(xs) if xs else 0)
    plt.figure(figsize=(7, 4))
    plt.bar(dims, vals)
    plt.ylim(0, 5)
    plt.ylabel("mean score (1-5)")
    plt.title(f"LLM-as-judge scores (pass rate {judge['summary'].get('pass_rate', 0):.0%})")
    plt.tight_layout()
    plt.savefig(out, dpi=120)
    plt.close()


def plot_compare(a: dict, b: dict, la: str, lb: str, out: Path) -> None:
    ra = {r["query"]: r["similarity"] for r in a["results"]}
    rb = {r["query"]: r["similarity"] for r in b["results"]}
    common = sorted(set(ra) & set(rb))
    xs = [ra[q] for q in common]
    ys = [rb[q] for q in common]
    plt.figure(figsize=(6, 6))
    plt.scatter(xs, ys, s=10, alpha=0.6)
    plt.plot([0, 1], [0, 1], linestyle="--")
    plt.xlabel(f"{la} similarity")
    plt.ylabel(f"{lb} similarity")
    plt.title(f"{lb} vs {la} per-question similarity (n={len(common)})")
    plt.tight_layout()
    plt.savefig(out, dpi=120)
    plt.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", type=str, default=None)
    ap.add_argument("--judge", type=str, default=None)
    ap.add_argument("--outdir", type=str, required=True)
    ap.add_argument("--tag", type=str, default="v")
    ap.add_argument("--compare", nargs=3, metavar=("A", "B", "OUT"), default=None)
    a = ap.parse_args()
    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    if a.compare:
        pa, pb, oname = a.compare
        plot_compare(load(Path(pa)), load(Path(pb)), Path(pa).stem, Path(pb).stem, outdir / oname)
        print("wrote", outdir / oname)
        return
    data = load(Path(a.bench))
    res = data["results"]
    plot_sim_hist(res, outdir / f"similarity_hist_{a.tag}.png")
    plot_format_means(res, outdir / f"format_means_{a.tag}.png")
    plot_citations(res, outdir / f"citations_{a.tag}.png")
    print("wrote similarity/format/citation plots")
    if a.judge:
        plot_judge(load(Path(a.judge)), outdir / f"judge_{a.tag}.png")
        print("wrote judge plot")


if __name__ == "__main__":
    main()
