"""LLM-as-judge — score RAG answers against ground truth with the local Gemma model.

Reads a benchmark JSON produced by run_llm_answer_benchmark.py and, for each
item, asks Gemma (llama-server, direct call) to judge the agent answer versus
the ground-truth answer on faithfulness / correctness / tone / citation use.
Writes <out> with per-item verdicts plus aggregates.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import httpx

LLM_URL = "http://127.0.0.1:18000/v1/chat/completions"

JUDGE_SYS = (
    "You are a strict evaluator of a Persian credit-scoring RAG assistant. "
    "Compare AGENT_ANSWER to GROUND_TRUTH for the QUESTION. "
    "Score 1-5 on: faithfulness (no invented/contradicted facts vs ground truth), "
    "correctness (answers the question the way ground truth does), "
    "tone (Persian, professional, concise, no irrelevant padding), "
    "citation (uses at most 2 [n] markers, markers look intentional). "
    "Reply with STRICT JSON only: "
    '{"faithfulness": N, "correctness": N, "tone": N, "citation": N, "verdict": "pass"|"fail", "rationale": "one short sentence"}'
)


def judge_item(client: httpx.Client, model: str, item: dict) -> dict:
    user = (
        f"QUESTION: {item['query']}\n"
        f"GROUND_TRUTH: {item.get('expected_answer', '')}\n"
        f"AGENT_ANSWER: {item.get('answer', '')}\n"
        f"CITATIONS_COUNT: {item.get('n_citations', 0)}"
    )
    t0 = time.monotonic()
    try:
        r = client.post(LLM_URL, json={
            "model": model,
            "messages": [
                {"role": "system", "content": JUDGE_SYS},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": 300,
            "chat_template_kwargs": {"enable_thinking": False},
        })
        r.raise_for_status()
        txt = r.json()["choices"][0]["message"]["content"]
        m = re.search(r"\{.*\}", txt, re.DOTALL)
        verdict = json.loads(m.group(0)) if m else {"verdict": "parse_error", "raw": txt[:200]}
        verdict["latency_ms"] = int((time.monotonic() - t0) * 1000)
        verdict["error"] = None
        return verdict
    except Exception as exc:  # noqa: BLE001
        return {"verdict": "error", "error": str(exc)[:200],
                "latency_ms": int((time.monotonic() - t0) * 1000)}


def main(bench: Path, out: Path, model: str, limit: int | None) -> None:
    data = json.loads(bench.read_text(encoding="utf-8"))
    items = data["results"][:limit] if limit else data["results"]
    client = httpx.Client(timeout=180)
    judged = []
    for i, item in enumerate(items, 1):
        v = judge_item(client, model, item)
        judged.append({
            "query": item["query"], "format": item.get("format"),
            "similarity": item.get("similarity"), "n_citations": item.get("n_citations"),
            "finish_reason": item.get("finish_reason"), **v,
        })
        print(f"[{i}/{len(items)}] verdict={v.get('verdict')} "
              f"f={v.get('faithfulness')} c={v.get('correctness')} :: {item['query'][:40]}",
              flush=True)
    ok = [j for j in judged if j["verdict"] in ("pass", "fail")]
    summary = {
        "n": len(judged),
        "pass_rate": round(sum(1 for j in ok if j["verdict"] == "pass") / len(ok), 4) if ok else 0,
        "mean_faithfulness": round(sum(j.get("faithfulness", 0) for j in ok) / len(ok), 3) if ok else 0,
        "mean_correctness": round(sum(j.get("correctness", 0) for j in ok) / len(ok), 3) if ok else 0,
        "mean_tone": round(sum(j.get("tone", 0) for j in ok) / len(ok), 3) if ok else 0,
        "mean_citation": round(sum(j.get("citation", 0) for j in ok) / len(ok), 3) if ok else 0,
        "errors": sum(1 for j in judged if j["verdict"] not in ("pass", "fail")),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "results": judged},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== JUDGE SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"saved -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("bench", type=str)
    ap.add_argument("--out", type=str, required=True)
    ap.add_argument("--model", type=str,
                    default="/workspace/.hf_home/hub/models--unsloth--gemma-4-31B-it-GGUF/snapshots/c1ac76e99d5513b141e8adde7288b85c3f9c32ec/gemma-4-31B-it-UD-Q4_K_XL.gguf")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    main(Path(a.bench), Path(a.out), a.model, a.limit)
