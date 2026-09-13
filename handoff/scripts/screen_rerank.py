"""Screen one reranker variant on the hard-question subset via full E2E pipeline.
Usage: screen_rerank.py <variant_name> <out_json> [idx idx ...]  (no idx = all hard)
"""
import asyncio
import json
import statistics
import sys

sys.path.insert(0, "/workspace/Work_Credit-RAG_Phase1/eval")
from run_llm_answer_benchmark import ask, load_model, sim  # noqa: E402

import httpx  # noqa: E402

V4 = "/workspace/Work_Credit-RAG_Phase1/eval/results/llm_answer_benchmark_v4.json"
DATA = "/workspace/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager/data/test_questions.json"


async def main(variant: str, out: str, indices: list[int]):
    dataset = json.loads(open(DATA, encoding="utf-8").read())
    questions = dataset if isinstance(dataset, list) else dataset.get("questions", dataset.get("items", []))
    items = [questions[i] for i in indices]
    model = load_model()
    results = []
    async with httpx.AsyncClient(timeout=300) as client:
        for n, item in enumerate(items, 1):
            q = item["query"]
            res = await ask(q, client)
            res["expected_answer"] = item.get("expected_answer", "")
            res["similarity"] = sim(res["answer"], res["expected_answer"], model)
            res["format"] = item.get("format", "")
            results.append(res)
            print(f"[{n}/{len(items)}] sim={res['similarity']:.3f} cit={res['n_citations']} :: {q[:45]}", flush=True)
    sims = [r["similarity"] for r in results if r.get("similarity") is not None]
    summary = {
        "variant": variant,
        "n": len(results),
        "mean_similarity": round(statistics.mean(sims), 4),
        "median_similarity": round(statistics.median(sims), 4),
        "sim_lt_05": sum(1 for s in sims if s < 0.5),
    }
    print("SUMMARY:", json.dumps(summary, ensure_ascii=False))
    json.dump({"summary": summary, "results": results}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved ->", out)


if __name__ == "__main__":
    variant = sys.argv[1]
    out = sys.argv[2]
    idx = [int(x) for x in sys.argv[3:]] or [0, 2, 3, 6, 14, 16, 17, 18, 35, 37, 39, 40, 44, 45, 53, 57, 63, 79, 85, 86, 89, 94, 97, 99, 102, 103]
    asyncio.run(main(variant, out, idx))
