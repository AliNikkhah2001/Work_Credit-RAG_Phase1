#!/usr/bin/env python3
"""Sample 10 random KB FAQ Q&A pairs and run timed retrieval + generation QA.

Writes:
  <out>/e2e/random_qa.json          full results + per-question timings
  <out>/e2e/latency_summary.json    aggregates for the Pages dashboard
  <out>/e2e/summary.txt / score.txt appended-compatible scores

Timing sources (inspection tools already on the APIs):
  * KB ``/search/api`` → ``stage_ms`` / ``elapsed_ms`` / ``rerank_ms``
  * Orchestrator ``/v1/chat/completions`` → ``audit.stage_timing_ms`` / ``audit.latency_ms``
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None


def load_faq_pairs(canned_paths: list[Path]) -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    for path in canned_paths:
        if not path.is_file():
            continue
        raw: Any
        text = path.read_text(encoding="utf-8", errors="replace")
        if yaml is not None:
            raw = yaml.safe_load(text)
        else:
            # Minimal fallback: only works if the file is already JSON-compatible.
            try:
                raw = json.loads(text)
            except ValueError:
                continue
        if not isinstance(raw, dict):
            continue
        short = raw.get("faq_shortlist") or []
        if isinstance(short, list):
            for item in short:
                if not isinstance(item, dict):
                    continue
                q = item.get("q") or item.get("question")
                a = item.get("a") or item.get("answer")
                if isinstance(q, str) and isinstance(a, str) and q.strip() and a.strip():
                    pairs.append({"question": q.strip(), "answer": a.strip(), "source": str(path)})
    # de-dupe by question text
    seen: set[str] = set()
    uniq: list[dict[str, str]] = []
    for p in pairs:
        if p["question"] in seen:
            continue
        seen.add(p["question"])
        uniq.append(p)
    return uniq


def http_json(url: str, payload: dict[str, Any] | None = None, timeout: float = 120.0) -> tuple[int, dict[str, Any], float]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            code = int(resp.status)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        code = int(e.code)
    except Exception as e:
        return 0, {"error": f"{type(e).__name__}: {e}"}, (time.perf_counter() - t0) * 1000.0
    wall = (time.perf_counter() - t0) * 1000.0
    try:
        parsed = json.loads(body) if body else {}
    except ValueError:
        parsed = {"_raw": body[:2000]}
    if not isinstance(parsed, dict):
        parsed = {"_value": parsed}
    return code, parsed, wall


def run_one(
    question: str,
    expected: str,
    *,
    orch: str,
    kb: str,
    model: str,
) -> dict[str, Any]:
    # 1) retrieval-only
    scode, sbody, swall = http_json(
        f"{kb.rstrip('/')}/search/api",
        {"query": question, "top_k": 5},
        timeout=60.0,
    )
    retrieval = {
        "http": scode,
        "wall_ms": round(swall, 1),
        "elapsed_ms": sbody.get("elapsed_ms"),
        "rerank_ms": sbody.get("rerank_ms"),
        "stage_ms": sbody.get("stage_ms") if isinstance(sbody.get("stage_ms"), dict) else {},
        "hits": len(sbody.get("final_results") or []) if isinstance(sbody.get("final_results"), list) else 0,
        "ok": scode == 200 and bool(sbody.get("final_results")),
    }

    # 2) full generation (orchestrator) — pulls audit.stage_timing_ms
    ccode, cbody, cwall = http_json(
        f"{orch.rstrip('/')}/v1/chat/completions",
        {
            "model": model,
            "messages": [{"role": "user", "content": question}],
            "stream": False,
        },
        timeout=180.0,
    )
    audit = cbody.get("audit") if isinstance(cbody.get("audit"), dict) else {}
    answer = ""
    try:
        answer = ((cbody.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    except Exception:
        answer = ""
    if not answer and isinstance(audit.get("final_answer"), str):
        answer = audit["final_answer"]
    stage = audit.get("stage_timing_ms") if isinstance(audit.get("stage_timing_ms"), dict) else {}
    generation = {
        "http": ccode,
        "wall_ms": round(cwall, 1),
        "latency_ms": audit.get("latency_ms"),
        "stage_timing_ms": stage,
        "retrieval_method": audit.get("retrieval_method"),
        "chunks_used": audit.get("retrieval_chunks_used"),
        "ok": ccode == 200 and bool(str(answer).strip()),
        "answer_preview": str(answer)[:400],
    }
    passed = bool(retrieval["ok"] and generation["ok"])
    return {
        "question": question,
        "expected_answer_preview": expected[:300],
        "passed": passed,
        "retrieval": retrieval,
        "generation": generation,
        "e2e_wall_ms": round(swall + cwall, 1),
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    e2e = [r["e2e_wall_ms"] for r in results if isinstance(r.get("e2e_wall_ms"), (int, float))]
    ret = [r["retrieval"]["wall_ms"] for r in results if r.get("retrieval")]
    gen = [r["generation"]["wall_ms"] for r in results if r.get("generation")]
    stages: dict[str, list[float]] = {}
    for r in results:
        st = (r.get("generation") or {}).get("stage_timing_ms") or {}
        for k, v in st.items():
            if isinstance(v, (int, float)):
                stages.setdefault(k, []).append(float(v))
        rst = (r.get("retrieval") or {}).get("stage_ms") or {}
        for k, v in rst.items():
            if isinstance(v, (int, float)):
                stages.setdefault(f"retrieval.{k}", []).append(float(v))

    def stats(vals: list[float]) -> dict[str, float | None]:
        if not vals:
            return {"n": 0, "avg_ms": None, "p50_ms": None, "p95_ms": None, "max_ms": None}
        s = sorted(vals)
        n = len(s)
        return {
            "n": n,
            "avg_ms": round(sum(s) / n, 1),
            "p50_ms": round(s[n // 2], 1),
            "p95_ms": round(s[max(0, int(n * 0.95) - 1)], 1),
            "max_ms": round(s[-1], 1),
        }

    passed = sum(1 for r in results if r.get("passed"))
    return {
        "schema_version": "qa-latency/v1",
        "count": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "e2e": stats(e2e),
        "retrieval": stats(ret),
        "generation": stats(gen),
        "stages": {k: stats(v) for k, v in sorted(stages.items())},
        "questions": [r.get("question") for r in results],
    }


def default_canned(repo: Path) -> list[Path]:
    return [
        repo / "components/knowledgebase/kb-source/processed/1405-08-20/packs/canned/v1.0.2.yaml",
        repo / "components/knowledgebase/kb-manager/packs/canned/v1.0.2.yaml",
        repo / "components/knowledgebase/kb-manager/packs/canned/v1.0.1.yaml",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True, help="report OUT dir (writes e2e/)")
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=None, help="optional RNG seed (default: time-based)")
    ap.add_argument("--orch", default="http://127.0.0.1:8100")
    ap.add_argument("--kb", default="http://127.0.0.1:8000")
    ap.add_argument("--model", default="gemma-4-31b")
    args = ap.parse_args(argv)

    out = args.out.resolve()
    e2e = out / "e2e"
    e2e.mkdir(parents=True, exist_ok=True)

    pairs = load_faq_pairs(default_canned(args.repo.resolve()))
    if len(pairs) < 1:
        print("ERROR: no FAQ q/a pairs found in canned packs", file=sys.stderr)
        (e2e / "random_qa.json").write_text(
            json.dumps({"error": "no FAQ pairs", "results": []}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return 2

    seed = args.seed if args.seed is not None else int(time.time())
    rng = random.Random(seed)
    n = max(1, min(args.n, len(pairs)))
    sample = rng.sample(pairs, n)

    results: list[dict[str, Any]] = []
    for i, pair in enumerate(sample, 1):
        print(f"[qa] {i}/{n}: {pair['question'][:80]}", flush=True)
        results.append(
            run_one(
                pair["question"],
                pair["answer"],
                orch=args.orch,
                kb=args.kb,
                model=args.model,
            )
        )

    summary = summarize(results)
    summary["seed"] = seed
    payload = {
        "schema_version": "random-qa/v1",
        "seed": seed,
        "n": n,
        "pool_size": len(pairs),
        "results": results,
        "summary": summary,
    }
    (e2e / "random_qa.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (e2e / "latency_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # Compatible score lines for the existing publisher
    passed = summary["passed"]
    total = summary["count"]
    lines = [f"random_qa_{i} http={'200' if r.get('passed') else '000'}" for i, r in enumerate(results, 1)]
    lines.append(f"random_qa_batch passed={passed}/{total} seed={seed}")
    (e2e / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (e2e / "score.txt").write_text(f"qa_pass={passed}/{total}\n", encoding="utf-8")
    print(f"[qa] done passed={passed}/{total} seed={seed} e2e_p50={summary['e2e']['p50_ms']}ms")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
