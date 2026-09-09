"""Build the static benchmark report site (GitHub Pages, no build step needed).

Reads eval/results/*.json + plots and emits docs/benchmark-report/index.html
with summary cards, comparison tables, plots, QA samples and findings.

Usage: python eval/build_report_site.py
"""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "eval" / "results"
PLOTS = RES / "plots"
SITE = ROOT / "docs" / "benchmark-report"
SITE_PLOTS = SITE / "plots"


def load(name: str) -> dict | None:
    p = RES / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def cards(summaries: dict[str, dict], judges: dict[str, dict]) -> str:
    parts = []
    for tag, s in summaries.items():
        j = judges.get(tag, {}).get("summary", {})
        parts.append(f"""
        <div class="card"><h3>{esc(tag)}</h3>
        <div class="bignum">{s.get('mean_similarity', 0):.3f}</div><div class="lbl">mean similarity</div>
        <div class="bignum">{s.get('median_similarity', 0):.3f}</div><div class="lbl">median similarity</div>
        <div class="row"><span>sim&gt;0.5</span><b>{s.get('similarity>0.5', 0):.0%}</b></div>
        <div class="row"><span>sim&gt;0.7</span><b>{s.get('similarity>0.7', 0):.0%}</b></div>
        <div class="row"><span>mean citations</span><b>{s.get('mean_citations', 0)}</b></div>
        <div class="row"><span>max citations</span><b>{s.get('max_citations', 0)}</b></div>
        <div class="row"><span>finish stop</span><b>{s.get('finish_reasons', {}).get('stop', 0)}/{s.get('n', 0)}</b></div>
        <div class="row"><span>judge pass</span><b>{(j.get('pass_rate', 0)):.0%}</b></div>
        </div>""")
    return "\n".join(parts)


def compare_table(summaries: dict[str, dict]) -> str:
    tags = list(summaries)
    if len(tags) < 2:
        return "<p>Single run — comparison appears after the Q8 rerun.</p>"
    keys = ["n", "mean_similarity", "median_similarity", "similarity>0.5",
            "similarity>0.7", "mean_citations", "max_citations", "low_similarity_lt0.5", "errors"]
    rows = "".join(
        f"<tr><td>{esc(k)}</td>" + "".join(f"<td>{esc(summaries[t].get(k, '—'))}</td>" for t in tags) + "</tr>"
        for k in keys)
    fr = "".join(f"<td>{esc(json.dumps(summaries[t].get('finish_reasons', {}), ensure_ascii=False))}</td>" for t in tags)
    rows += f"<tr><td>finish_reasons</td>{fr}</tr>"
    head = "".join(f"<th>{esc(t)}</th>" for t in tags)
    return f"<table><tr><th>metric</th>{head}</tr>{rows}</table>"


def qa_table(samples: list[dict]) -> str:
    rows = ""
    for s in samples:
        a = s["a"]
        shown = esc(a[:600]) + ("…" if len(a) > 600 else "")
        rows += (f"<tr><td>{esc(s['q'])}</td><td>{shown}</td>"
                 f"<td>{s['citations']}</td><td>{esc(s['finish'])}</td></tr>")
    return (f"<table><tr><th>question</th><th>agent answer (truncated)</th>"
            f"<th>citations</th><th>finish</th></tr>{rows}</table>")


def fail_table(results: list[dict], key: str, n: int = 8) -> str:
    if key == "low":
        items = sorted(results, key=lambda r: r.get("similarity", 0))[:n]
        rows = "".join(
            f"<tr><td>{esc(i['query'][:70])}</td><td>{i.get('similarity', 0):.3f}</td>"
            f"<td>{esc(i.get('format', ''))}</td><td>{esc((i.get('answer') or '')[:160])}…</td></tr>"
            for i in items)
        return (f"<table><tr><th>question</th><th>sim</th><th>format</th>"
                f"<th>answer (truncated)</th></tr>{rows}</table>")
    items = [r for r in results if r.get("verdict") == "fail"][:n]
    rows = "".join(
        f"<tr><td>{esc(i['query'][:70])}</td>"
        f"<td>f{i.get('faithfulness')} c{i.get('correctness')} t{i.get('tone')}</td>"
        f"<td>{esc(str(i.get('rationale', ''))[:160])}</td></tr>" for i in items)
    return (f"<table><tr><th>question</th><th>judge scores</th>"
            f"<th>rationale</th></tr>{rows}</table>")


PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Work Credit RAG — Agent Behaviour & Benchmark Report</title>
<link rel="stylesheet" href="style.css"></head>
<body><main>
<h1>Work Credit RAG — Agent Behaviour &amp; Benchmark Report</h1>
<p class="sub">Persian credit-scoring RAG agent · 120-question bank (6 wording formats) ·
model <code>unsloth/gemma-4-31B-it-GGUF</code> · run {date}</p>
<p>Sources: <a href="https://github.com/AliNikkhah2001/Work_Credit-RAG_Phase1">parent repo</a> ·
<a href="llm_answer_benchmark_v4.json">bench JSON (Q8)</a> · <a href="llm_judge_v4.json">judge JSON (Q8)</a> ·
<a href="llm_answer_benchmark_v3.json">bench JSON (Q4)</a> · <a href="llm_judge_v3.json">judge JSON (Q4)</a></p>

<h2>1. Summary</h2>
<div class="cards">{cards}</div>

<h2>2. Run comparison</h2>
{compare}

<h2>3. Answer statistics</h2>
<h3>Similarity distribution (answer vs ground truth)</h3>
<img src="plots/{sim_hist}" alt="similarity histogram">
<h3>Wording robustness (same info, different phrasing)</h3>
<img src="plots/{fmt}" alt="per-format means">
<h3>Citation counts (cap = 2)</h3>
<img src="plots/{cit}" alt="citation counts">
<h3>LLM-as-judge scores</h3>
{judgeimg}

<h2>4. QA samples (live)</h2>
{qa}

<h2>5. Findings</h2>
<h3>Faithfulness &amp; correctness</h3>
<ul>
<li>Dominant failure mode is <b>false abstention</b> (~18% pre-tweak): the agent said
“no answer found” despite 5 retrieved chunks. No polarity flips (بله↔خیر) observed — failures are omission, not inversion.</li>
<li>Mid-range answers sometimes <b>pad with retrieved-but-unasked context</b> (1–2 extra bullets not in ground truth).</li>
<li>After the abstention-threshold prompt tweak, previously abstained questions (e.g. «چرا امتیاز اعتباری… مهم است؟») return grounded answers with 1 citation.</li>
</ul>
<h3>Citations</h3>
<ul>
<li>100% of answers cite ≤ 2 sources; metadata returns only chunks actually referenced <code>[n]</code> in the text (fallback: top-1 chunk).</li>
<li>No invalid markers observed (no <code>[0]</code>/<code>[6+]</code>); one pre-tweak answer cited 3 markers in text while metadata correctly truncated to 2.</li>
</ul>
<h3>Tone &amp; identity</h3>
<ul>
<li>Answers are Persian-only, professional, and structured (intro + 1–3 points + closing). The agent answers as the Iranian credit scoring company AI agent.</li>
<li>Greeting rule tightened: «ببخشید» no longer triggers a سلام.</li>
</ul>
<h3>Wording robustness</h3>
<ul>
<li><code>reworded</code> is weakest (mean ~0.55, 30% below 0.5); <code>keyword_only</code> strongest (~0.65). Retrieval returns 5 chunks in all cases — failures come from 5 distractors, not empty retrieval.</li>
<li>Fix applied: light Persian normalization + politeness-filler strip in <code>retrieve.py</code> before KB search.</li>
</ul>
<h3>Guardrails</h3>
<ul>
<li>Two false positives found by the benchmark and fixed: <code>profanity:کردن</code> (common verb in swear list → removed bare forms, vulgar phrases like «کس کردن» still blocked) and <code>hate:پلیس</code> (police records are a legit credit data source → allowlisted).</li>
<li>Blocked-answer rate went 5/120 → 0/120.</li>
</ul>
<h3>Memory</h3>
<ul>
<li>The agent is <b>stateless</b>: it does not remember previous turns, neither across requests nor within multi-turn <code>messages</code> (only the latest user message is used as the query). Short-term history is not implemented in the MVP graph.</li>
</ul>

<h2>6. Lowest-similarity cases</h2>
{lowtab}

<h2>7. Judge failures (sample)</h2>
{judgefails}

<h2>8. Reproduce</h2>
<pre>python eval/run_llm_answer_benchmark.py --out eval/results/llm_answer_benchmark_v3.json
python eval/run_llm_judge.py eval/results/llm_answer_benchmark_v3.json --out eval/results/llm_judge_v3.json
python eval/make_plots.py --bench eval/results/llm_answer_benchmark_v3.json --judge eval/results/llm_judge_v3.json --outdir eval/results/plots --tag v3
python eval/build_report_site.py</pre>
</main></body></html>
"""


def main() -> None:
    import datetime
    SITE.mkdir(parents=True, exist_ok=True)
    SITE_PLOTS.mkdir(parents=True, exist_ok=True)
    for p in PLOTS.glob("*.png"):
        shutil.copy(p, SITE_PLOTS / p.name)

    benches = {}
    for tag, name in (("v2 (Q4, pre-tweak)", "llm_answer_benchmark_v2.json"),
                      ("v3 (Q4, tweaked prompt)", "llm_answer_benchmark_v3.json"),
                      ("v4 (Q8, tweaked prompt)", "llm_answer_benchmark_v4.json")):
        d = load(name)
        if d:
            benches[tag] = d["summary"]
    judges = {}
    for tag, name in (("v2 (Q4, pre-tweak)", "llm_judge_v2.json"),
                      ("v3 (Q4, tweaked prompt)", "llm_judge_v3.json"),
                      ("v4 (Q8, tweaked prompt)", "llm_judge_v4.json")):
        d = load(name)
        if d:
            judges[tag] = d
    cur = load("llm_answer_benchmark_v3.json") or load("llm_answer_benchmark_v2.json") or {}
    curj = load("llm_judge_v3.json") or load("llm_judge_v2.json") or {}
    samples = load("qa_samples.json") or []
    if isinstance(samples, dict):
        samples = samples.get("samples", [])

    def pick(prefix: str, tag: str) -> str:
        cands = sorted(PLOTS.glob(f"{prefix}_{tag}.png"))
        if cands:
            return cands[-1].name
        anyc = sorted(PLOTS.glob(f"{prefix}_*.png"))
        return anyc[-1].name if anyc else ""

    def _has(t: str) -> bool:
        return (PLOTS / f"similarity_hist_{t}.png").exists()
    tag = "v4" if _has("v4") else ("v3" if _has("v3") else "v2")
    def _hasj(t: str) -> bool:
        return (PLOTS / f"judge_{t}.png").exists()
    jtag = "v4" if _hasj("v4") else ("v3" if _hasj("v3") else ("v2" if _hasj("v2") else ""))
    jfile = pick("judge", jtag) if jtag else ""
    judgeimg = (f'<img src="plots/{esc(jfile)}" alt="judge scores">' if jfile
                else "<p>Judge plot pending — rerun <code>make_plots.py --judge …</code>.</p>")
    page = PAGE.format(
        date=esc(datetime.date.today().isoformat()),
        cards=cards(benches, judges),
        compare=compare_table(benches),
        sim_hist=esc(pick("similarity_hist", tag)),
        fmt=esc(pick("format_means", tag)),
        cit=esc(pick("citations", tag)),
        judgeimg=judgeimg,
        qa=qa_table(samples),
        lowtab=fail_table(cur.get("results", []), "low"),
        judgefails=fail_table(curj.get("results", []), "judge") if curj else "<p>pending</p>",
    )
    (SITE / "index.html").write_text(page, encoding="utf-8")
    for name in ("llm_answer_benchmark_v4.json", "llm_judge_v4.json",
                 "llm_answer_benchmark_v3.json", "llm_judge_v3.json",
                 "llm_answer_benchmark_v2.json", "llm_judge_v2.json"):
        if (RES / name).exists():
            shutil.copy(RES / name, SITE / name)
    print(f"site -> {SITE}/index.html")


if __name__ == "__main__":
    main()
