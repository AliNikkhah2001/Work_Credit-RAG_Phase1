"""LLM answer benchmark — run the full KB question bank through the RAG agent and
measure answer similarity against ground-truth retrieval content.

Dataset: components/knowledgebase/kb-manager/data/test_questions.json (120 questions)
Method: for each question, POST to the orchestrator chat API (which runs
retrieve -> build_context -> guarded_generate against Gemma), then embed the
LLM answer and the ground-truth answer with the KB embedding model
(paraphrase-multilingual-MiniLM-L12-v2) and report cosine similarity.

Outputs benchmark_results_llm_v2.json into eval/results/ plus a human summary.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

import httpx

ORCH_URL = "http://127.0.0.1:8100/v1/chat/completions"
MODEL = "gemma-4-31b"
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "components/knowledgebase/kb-manager/data/test_questions.json"
OUT_JSON = ROOT / "eval/results/llm_answer_benchmark_v2.json"


def load_model():
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    return m


def sim(a: str, b: str, model, vocab_bit=0.0) -> float:
    import numpy as np
    if not a.strip() or not b.strip():
        return 0.0
    ea = model.encode(a, normalize_embeddings=True, convert_to_numpy=True)
    eb = model.encode(b, normalize_embeddings=True, convert_to_numpy=True)
    return float(np.dot(ea, eb))


async def ask(query: str, client: httpx.AsyncClient) -> dict:
    t0 = time.monotonic()
    try:
        r = await client.post(ORCH_URL, json={
            "model": MODEL,
            "messages": [{"role": "user", "content": query}],
            "temperature": 0,
            "max_tokens": 512,
        })
        r.raise_for_status()
        j = r.json()
        choice = j["choices"][0]
        audit = j.get("audit") or {}
        return {
            "query": query,
            "answer": choice["message"]["content"],
            "finish_reason": choice["finish_reason"],
            "citations": [c.get("chunk_id", "") for c in j.get("rag", {}).get("citations", [])],
            "n_citations": len(j.get("rag", {}).get("citations", [])),
            "retrieved": len(audit.get("retrieved_chunks", [])),
            "latency_ms": audit.get("latency_ms") or int((time.monotonic() - t0) * 1000),
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "query": query, "answer": "", "finish_reason": "error",
            "citations": [], "n_citations": 0, "retrieved": 0,
            "latency_ms": int((time.monotonic() - t0) * 1000), "error": str(exc),
        }


async def run(dataset: list[dict], limit: int | None = None, client: httpx.AsyncClient | None = None):
    model = load_model()  # sync load once (torch model)
    if client is None:
        client = httpx.AsyncClient(timeout=180)
    items = list(dataset[:limit]) if limit else list(dataset)
    results = []
    for i, item in enumerate(items, 1):
        q = item["query"]
        res = await ask(q, client)
        gt = item.get("expected_answer", "")
        res["expected_answer"] = gt
        res["gt"] = item.get("gt", "")
        res["difficulty"] = item.get("difficulty", "medium")
        res["format"] = item.get("format", "verbatim")
        res["expected_chunk_ids"] = item.get("expected_chunk_ids", [])
        res["similarity"] = sim(res["answer"], gt, model)
        results.append(res)
        print(f"[{i}/{len(items)}] sim={res['similarity']:.3f} cit={res['n_citations']} "
              f"fin={res['finish_reason']} :: {q[:40]}")
    if client is None:
        await client.aclose()
    return results


def summarize(results: list[dict]) -> dict:
    sims = [r["similarity"] for r in results if r.get("similarity") is not None]
    n_cit = [r["n_citations"] for r in results if r.get("finish_reason") == "stop"]
    by_finish: dict[str, int] = {}
    for r in results:
        by_finish[r["finish_reason"]] = by_finish.get(r["finish_reason"], 0) + 1
    low = [r for r in results if r.get("similarity", 0) < 0.5]
    by_format: dict[str, list[float]] = {}
    for r in results:
        by_format.setdefault(r["format"], []).append(r["similarity"])
    fmt_avg = {k: round(statistics.mean(v), 4) for k, v in sorted(by_format.items())}
    return {
        "n": len(results),
        "mean_similarity": round(statistics.mean(sims), 4) if sims else 0,
        "median_similarity": round(statistics.median(sims), 4) if sims else 0,
        "p25_similarity": round(statistics.quantiles(sims, n=4)[0], 4) if len(sims) >= 4 else None,
        "p75_similarity": round(statistics.quantiles(sims, n=4)[2], 4) if len(sims) >= 4 else None,
        "similarity>0.7": round(sum(1 for s in sims if s > 0.7) / len(sims), 4) if sims else 0,
        "similarity>0.5": round(sum(1 for s in sims if s > 0.5) / len(sims), 4) if sims else 0,
        "mean_citations": round(statistics.mean(n_cit), 3) if n_cit else 0,
        "max_citations": max(n_cit, default=0),
        "citations_le2": round(sum(1 for c in n_cit if c <= 2) / len(n_cit), 4) if n_cit else 0,
        "finish_reasons": by_finish,
        "by_format_mean_similarity": fmt_avg,
        "low_similarity_lt0.5": len(low),
        "errors": sum(1 for r in results if r.get("error")),
    }


async def main(limit: int | None, out: Path) -> None:
    with open(DATA, encoding="utf-8") as f:
        dataset = json.load(f)
    print(f"questions: {len(dataset)} (limit={limit})  harder: max of full set")
    results = await run(dataset, limit=limit)
    summary = summarize(results)
    payload = {"dataset": str(DATA), "n": len(results), "summary": summary, "results": results}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nsaved -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", type=str, default=str(OUT_JSON))
    args = ap.parse_args()
    asyncio.run(main(args.limit, Path(args.out)))