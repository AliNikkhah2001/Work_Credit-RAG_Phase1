#!/usr/bin/env python3
"""
Guardrails Evaluation Runner — Phase 2

For every sample in eval/samples/*.json, record:
- existing guardrail result (via POST /v1/rails/check or direct actions)
- triggered rule
- latency
- false positive/negative
- semantic scores if available (placeholder, 0.0 until Phase 5)

Output: eval/results/baseline.json
"""
import asyncio
import json
import time
import pathlib
import sys
from typing import Dict, Any, List

# Add guardrails src to path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "components" / "guardrails" / "src"))

from work_rag_guardrails.actions import (
    check_input_persian,
    check_output_persian,
    normalize_persian,
)

# Try to import semantic if available (Phase 5)
try:
    from work_rag_guardrails.semantic import get_toxicity_score  # placeholder
    HAS_SEMANTIC = True
except ImportError:
    HAS_SEMANTIC = False

SAMPLES_DIR = pathlib.Path(__file__).parent / "samples"
RESULTS_DIR = pathlib.Path(__file__).parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

def evaluate_sample(sample: Dict[str, Any]) -> Dict[str, Any]:
    text = sample["text"]
    expected = sample["expected_action"]  # allow or block
    category = sample["category"]
    start = time.perf_counter()
    # Use input check for benign/hate/injection/pii/financial_fp; for output, also check output
    # For this baseline, we check both input and output and take the most restrictive
    blocked_in, cat_in, reason_in = check_input_persian(text)
    blocked_out, cat_out, reason_out = check_output_persian(text)
    blocked = blocked_in or blocked_out
    triggered_rule = reason_in if blocked_in else reason_out if blocked_out else ""
    triggered_category = cat_in if blocked_in else cat_out if blocked_out else ""
    latency_ms = (time.perf_counter() - start) * 1000

    # Determine actual action
    actual = "block" if blocked else "allow"
    is_fp = (expected == "allow" and actual == "block")
    is_fn = (expected == "block" and actual == "allow")
    correct = (expected == actual)

    # Semantic scores placeholder
    semantic_scores = {}
    if HAS_SEMANTIC:
        try:
            # Example: toxicity, hate, intent
            from work_rag_guardrails.semantic.toxicity import score_text as tox_score
            semantic_scores["toxicity"] = tox_score(text)
        except Exception:
            semantic_scores["toxicity"] = 0.0
    else:
        semantic_scores = {"toxicity": 0.0, "hate": 0.0, "intent": 0.0}

    return {
        "id": sample.get("id"),
        "text": text,
        "category": category,
        "expected_action": expected,
        "actual_action": actual,
        "correct": correct,
        "false_positive": is_fp,
        "false_negative": is_fn,
        "triggered_rule": triggered_rule,
        "triggered_category": triggered_category,
        "blocked_input": blocked_in,
        "blocked_output": blocked_out,
        "latency_ms": round(latency_ms, 2),
        "semantic_scores": semantic_scores,
        "normalized": normalize_persian(text)[:100],
    }

def main():
    import glob
    samples = []
    for path in sorted(SAMPLES_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            for s in data:
                s["source_file"] = path.name
                samples.append(s)

    print(f"Loaded {len(samples)} samples from {SAMPLES_DIR}")
    results = []
    for s in samples:
        r = evaluate_sample(s)
        results.append(r)

    # Metrics
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    fp = sum(1 for r in results if r["false_positive"])
    fn = sum(1 for r in results if r["false_negative"])
    # Per-category
    from collections import Counter, defaultdict
    cat_stats = defaultdict(lambda: {"total":0, "correct":0, "fp":0, "fn":0})
    for r in results:
        cat = r["category"]
        cat_stats[cat]["total"] += 1
        if r["correct"]:
            cat_stats[cat]["correct"] += 1
        if r["false_positive"]:
            cat_stats[cat]["fp"] += 1
        if r["false_negative"]:
            cat_stats[cat]["fn"] += 1

    avg_latency = sum(r["latency_ms"] for r in results) / total if total else 0

    summary = {
        "total": total,
        "correct": correct,
        "accuracy": round(correct/total, 4) if total else 0,
        "false_positives": fp,
        "false_negatives": fn,
        "fp_rate": round(fp/total, 4) if total else 0,
        "fn_rate": round(fn/total, 4) if total else 0,
        "avg_latency_ms": round(avg_latency, 2),
        "per_category": dict(cat_stats),
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "has_semantic": HAS_SEMANTIC,
    }

    output = {
        "summary": summary,
        "results": results,
    }

    out_path = RESULTS_DIR / "baseline.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Baseline evaluation complete: {correct}/{total} correct ({summary['accuracy']:.1%})")
    print(f"FP: {fp} ({summary['fp_rate']:.1%}), FN: {fn} ({summary['fn_rate']:.1%}), avg latency: {avg_latency:.1f}ms")
    for cat, stats in cat_stats.items():
        print(f"  {cat}: {stats['correct']}/{stats['total']} correct, FP {stats['fp']}, FN {stats['fn']}")
    print(f"Saved to {out_path}")
    if HAS_SEMANTIC:
        print("Semantic scores included")
    else:
        print("Semantic scores placeholder (0.0) — Phase 5 will add real models")

if __name__ == "__main__":
    main()
