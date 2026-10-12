#!/usr/bin/env python3
"""
Benchmark report generator for Work Credit RAG.

Loads bench_results_latest.json (bench_runner) and ragas_results_latest.json (ragas_eval)
and generates detailed HTML + Markdown reports.

Features:
 - Header: date, total turns, total conversations, avg latency, error rate
 - Overall metrics bar chart (inline SVG, no CDN) for 8 metrics
 - Per-subspace comparison table + bar charts
 - Per-conversation drill-down (12 convs turn-by-turn)
 - Hallucination details (G5)
 - Ambiguity resolution scatter
 - Sticky persistence timeline
 - Direct retrieval probe comparison (kb_probes)

CLI:
    python3 -m evaluation.report --bench evaluation/artifacts/bench_results_latest.json \
        --ragas evaluation/artifacts/ragas_results_latest.json \
        --out evaluation/artifacts/bench_report_latest.html

Mirrored to:
    components/orchestrator/evaluation/report.py
    components/evaluation/report.py
    evaluation/report.py
"""
from __future__ import annotations

import argparse
import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(p: Path) -> Dict[str, Any]:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def fmt_score(v: Optional[float]) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{float(v):.3f}"

def fmt_lat(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{int(round(float(v)))} ms"
    except Exception:
        return str(v)

def esc(s: Any) -> str:
    return html.escape(str(s) if s is not None else "", quote=True)

def pct(v: Optional[float]) -> float:
    if v is None:
        return 0.0
    return max(0.0, min(1.0, float(v)))

# Color maps
SUBSPACE_COLORS: Dict[str, str] = {
    "cheque": "#1976d2",
    "facilities_person": "#388e3c",
    "facilities_legal": "#f57c00",
    "general": "#7b1fa2",
    "overall": "#455a64",
    "greeting": "#0288d1",
    "mixed": "#5d4037",
    "none": "#78909c",
    "unknown": "#9e9e9e",
}
METRIC_COLORS: Dict[str, str] = {
    "faithfulness": "#2e7d32",
    "answer_relevancy": "#1565c0",
    "context_relevancy": "#00838f",
    "context_recall": "#6a1b9a",
    "hallucination": "#c62828",
    "hallucination_inv": "#4caf50",
    "ambiguity_resolution": "#ef6c00",
    "sticky_persistence": "#4527a0",
    "retrieval_hit": "#00695c",
}
METRIC_LABELS: Dict[str, str] = {
    "faithfulness": "faithfulness",
    "answer_relevancy": "answer_relevancy",
    "context_relevancy": "context_relevancy",
    "context_recall": "context_recall",
    "hallucination": "hallucination (inv)",
    "ambiguity_resolution": "ambiguity_resolution",
    "sticky_persistence": "sticky_persistence",
    "retrieval_hit": "retrieval_hit",
}

# ---------------------------------------------------------------------------
# SVG helpers (no CDN, inline)
# ---------------------------------------------------------------------------

def svg_overall_metrics(overall: Dict[str, Any]) -> str:
    """Horizontal bar chart for 8 metrics: overall."""
    # Order per spec
    keys = ["faithfulness", "answer_relevancy", "context_relevancy", "context_recall",
            "hallucination", "ambiguity_resolution", "sticky_persistence", "retrieval_hit"]
    # Hallucination inverted: use non_hallucination if present else 1 - hallucination
    vals: List[Tuple[str, float, str]] = []
    for k in keys:
        if k == "hallucination":
            inv = overall.get("non_hallucination")
            if inv is not None:
                v = float(inv)
                label = METRIC_LABELS["hallucination"]
            else:
                raw = overall.get("hallucination")
                v = 1.0 - float(raw) if raw is not None else 0.0
                label = METRIC_LABELS["hallucination"]
            vals.append((label, v, METRIC_COLORS["hallucination_inv"]))
        else:
            v = overall.get(k)
            fv = float(v) if v is not None else 0.0
            vals.append((METRIC_LABELS.get(k, k), fv, METRIC_COLORS.get(k, "#607d8b")))

    W = 820
    H = 40 + len(vals) * 38 + 30
    left = 200
    right = 60
    chart_w = W - left - right
    bar_h = 18
    out = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Overall metrics">']
    out.append(f'<rect width="{W}" height="{H}" fill="#ffffff" rx="8"/>')
    out.append(f'<text x="{W//2}" y="22" text-anchor="middle" font-size="14" font-weight="700" fill="#222">Overall Metrics (0 — 1, higher is better; hallucination inverted)</text>')
    # axis
    for i, (label, v, color) in enumerate(vals):
        y = 40 + i * 38
        # label
        out.append(f'<text x="{left-10}" y="{y+13}" text-anchor="end" font-size="11" fill="#333">{esc(label)}</text>')
        # background
        out.append(f'<rect x="{left}" y="{y}" width="{chart_w}" height="{bar_h}" rx="4" fill="#eceff1" />')
        w = int(round(pct(v) * chart_w))
        out.append(f'<rect x="{left}" y="{y}" width="{w}" height="{bar_h}" rx="4" fill="{color}" />')
        # value
        out.append(f'<text x="{left+chart_w+8}" y="{y+13}" font-size="11" fill="#222" font-weight="600">{v:.3f}</text>')
        # grid lines 0.25,0.5,0.75
        # (draw tick marks under bg)
    # axis ticks
    for frac, lab in [(0.0, "0"), (0.5, "0.5"), (1.0, "1.0")]:
        x = left + int(round(frac * chart_w))
        out.append(f'<line x1="{x}" y1="38" x2="{x}" y2="{H-10}" stroke="#e0e0e0" stroke-dasharray="3 3"/>')
        out.append(f'<text x="{x}" y="{H-2}" text-anchor="middle" font-size="10" fill="#777">{lab}</text>')
    out.append('</svg>')
    return "\n".join(out)

def svg_subspace_grouped(by_subspace: Dict[str, Any], overall: Dict[str, Any]) -> str:
    """Grouped horizontal bars per metric across subspaces."""
    # Canonical subspaces to display
    requested = ["cheque", "facilities_person", "facilities_legal", "general", "overall"]
    # metrics to plot (inverted hallucination)
    metrics = ["faithfulness", "answer_relevancy", "context_relevancy", "hallucination", "ambiguity_resolution", "sticky_persistence", "retrieval_hit"]
    # Build combined dict including overall
    combined: Dict[str, Dict[str, Any]] = {}
    for k, v in by_subspace.items():
        combined[k] = v
    combined["overall"] = overall

    # Determine which requested subspaces have data
    present: List[str] = []
    for s in requested:
        if s == "overall":
            present.append(s)
        elif s in combined:
            present.append(s)
        else:
            # also check none/greeting fallback for general? skip if no data
            if s in by_subspace:
                present.append(s)
    # If some requested missing, still include with zero
    # Ensure at least overall + cheque if missing others we plot 0
    for s in requested:
        if s not in present:
            present.append(s)

    W = 860
    left = 180
    right = 50
    bar_h = 12
    gap_between_metrics = 26
    gap_between_bars = 4
    group_h = len(present) * (bar_h + gap_between_bars)
    H = 50 + len(metrics) * (group_h + gap_between_metrics) + 30
    chart_w = W - left - right
    out = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Per-subspace bars">']
    out.append(f'<rect width="{W}" height="{H}" fill="#ffffff" rx="8"/>')
    out.append(f'<text x="{W//2}" y="22" text-anchor="middle" font-size="14" font-weight="700" fill="#222">Per-Subspace Comparison (hallucination inverted)</text>')
    # legend
    leg_x = left
    leg_y = 32
    for idx, s in enumerate(present):
        color = SUBSPACE_COLORS.get(s, "#607d8b")
        x = leg_x + idx * 150
        out.append(f'<rect x="{x}" y="{leg_y}" width="14" height="14" rx="2" fill="{color}"/>')
        out.append(f'<text x="{x+18}" y="{leg_y+11}" font-size="11" fill="#333">{esc(s)}</text>')
    # fix legend overflow: wrap if needed, but keep simple
    y_cursor = 55
    for m_idx, mk in enumerate(metrics):
        label = METRIC_LABELS.get(mk if mk != "hallucination" else "hallucination", mk)
        out.append(f'<text x="{left-10}" y="{y_cursor + group_h//2 + 4}" text-anchor="end" font-size="11" font-weight="600" fill="#222">{esc(label)}</text>')
        for s_idx, s in enumerate(present):
            y = y_cursor + s_idx * (bar_h + gap_between_bars)
            src = combined.get(s, {})
            if mk == "hallucination":
                inv = src.get("non_hallucination")
                if inv is not None:
                    v = float(inv)
                else:
                    raw = src.get("hallucination")
                    v = 1.0 - float(raw) if raw is not None else 0.0
            else:
                vv = src.get(mk)
                v = float(vv) if vv is not None else 0.0
            color = SUBSPACE_COLORS.get(s, "#607d8b")
            w = int(round(pct(v) * chart_w))
            out.append(f'<rect x="{left}" y="{y}" width="{chart_w}" height="{bar_h}" rx="3" fill="#eceff1"/>')
            out.append(f'<rect x="{left}" y="{y}" width="{w}" height="{bar_h}" rx="3" fill="{color}" />')
            if w > 40:
                out.append(f'<text x="{left+w-4}" y="{y+9}" text-anchor="end" font-size="9" fill="#fff" font-weight="600">{v:.2f}</text>')
            else:
                out.append(f'<text x="{left+w+4}" y="{y+9}" font-size="9" fill="#333">{v:.2f}</text>')
        # group bottom line
        y_cursor += group_h + gap_between_metrics
        out.append(f'<line x1="{left}" y1="{y_cursor-8}" x2="{left+chart_w}" y2="{y_cursor-8}" stroke="#f0f0f0"/>')
    # axis ticks at bottom
    for frac, lab in [(0.0, "0"), (0.5, "0.5"), (1.0, "1.0")]:
        x = left + int(round(frac * chart_w))
        out.append(f'<line x1="{x}" y1="50" x2="{x}" y2="{y_cursor-8}" stroke="#e0e0e0" stroke-dasharray="3 3"/>')
        out.append(f'<text x="{x}" y="{H-4}" text-anchor="middle" font-size="10" fill="#777">{lab}</text>')
    out.append('</svg>')
    return "\n".join(out)

def svg_ambiguity_scatter(bench: Dict[str, Any], ragas_lookup: Dict[Tuple[str,int], Dict[str, Any]]) -> str:
    """Small scatter: x=turn order, y=ambiguity_resolution score, color by clarify pass."""
    # Collect scattered turns: expected_finish == clarify
    points: List[Dict[str, Any]] = []
    for conv in bench.get("conversations", []) or []:
        for t in conv.get("turns", []) or []:
            if (t.get("expected_finish") == "clarify"):
                key = (conv.get("id"), t.get("turn_index"))
                r = ragas_lookup.get(key, {})
                scores = r.get("scores", {}) if r else {}
                amb = scores.get("ambiguity_resolution") if scores else None
                # Determine clarified: actual finish_reason == clarify
                actual = t.get("finish_reason")
                clarified = (actual == "clarify")
                points.append({"conv": conv.get("id"), "turn": t.get("turn_index"), "query": t.get("user","")[:40], "clarified": clarified, "score": amb if amb is not None else (1.0 if clarified else 0.0)})
    # Also singles
    for s in bench.get("single_baselines", []) or []:
        if s.get("expected_finish") == "clarify":
            key = (s.get("id"), 1)
            r = ragas_lookup.get(key, {})
            scores = r.get("scores", {}) if r else {}
            amb = scores.get("ambiguity_resolution") if scores else None
            actual = s.get("finish_reason")
            clarified = (actual == "clarify")
            points.append({"conv": s.get("id"), "turn": 1, "query": s.get("query") or s.get("user","")[:40], "clarified": clarified, "score": amb if amb is not None else (1.0 if clarified else 0.0)})
    if not points:
        return '<div style="color:#777;padding:8px;">No clarify-expected turns found.</div>'
    W = 820
    H = 220
    left = 50
    right = 30
    top = 30
    bottom = 50
    chart_w = W - left - right
    chart_h = H - top - bottom
    out = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Ambiguity scatter">']
    out.append(f'<rect width="{W}" height="{H}" fill="#ffffff" rx="8"/>')
    out.append(f'<text x="{W//2}" y="18" text-anchor="middle" font-size="12" font-weight="700" fill="#222">Ambiguity Resolution: scattered queries (expected clarify) — clarified vs not</text>')
    # axes
    out.append(f'<line x1="{left}" y1="{top+chart_h}" x2="{left+chart_w}" y2="{top+chart_h}" stroke="#333"/>')
    out.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+chart_h}" stroke="#333"/>')
    out.append(f'<text x="{left-30}" y="{top+chart_h//2}" text-anchor="middle" font-size="10" fill="#555" transform="rotate(-90 {left-30} {top+chart_h//2})">ambiguity score</text>')
    out.append(f'<text x="{left+chart_w//2}" y="{H-8}" text-anchor="middle" font-size="10" fill="#555">turn index (scattered queries)</text>')
    # y ticks 0,0.5,1
    for v in [0.0, 0.5, 1.0]:
        y = top + chart_h - int(round(v * chart_h))
        out.append(f'<line x1="{left-4}" y1="{y}" x2="{left+chart_w}" y2="{y}" stroke="#e0e0e0" stroke-dasharray="3 3"/>')
        out.append(f'<text x="{left-8}" y="{y+3}" text-anchor="end" font-size="9" fill="#777">{v:.1f}</text>')
    # x positions evenly spaced
    n = len(points)
    for idx, p in enumerate(points):
        x = left + int(round((idx + 0.5) / n * chart_w)) if n > 1 else left + chart_w // 2
        score = float(p["score"]) if p["score"] is not None else 0.0
        y = top + chart_h - int(round(score * chart_h))
        color = "#2e7d32" if p["clarified"] else "#c62828"
        label = "clarified" if p["clarified"] else "not clarified"
        out.append(f'<circle cx="{x}" cy="{y}" r="7" fill="{color}" stroke="#fff" stroke-width="2"/>')
        out.append(f'<text x="{x}" y="{top+chart_h+14}" text-anchor="middle" font-size="8" fill="#333">{esc(p["conv"][:12])}</text>')
        out.append(f'<title>{esc(p["conv"])} T{p["turn"]} — {esc(label)} score={score:.2f} — {esc(p["query"])}</title>')
    # legend
    out.append(f'<rect x="{left+chart_w-140}" y="{top+6}" width="10" height="10" fill="#2e7d32" rx="2"/>')
    out.append(f'<text x="{left+chart_w-126}" y="{top+14}" font-size="9" fill="#333">clarified (pass)</text>')
    out.append(f'<rect x="{left+chart_w-140}" y="{top+20}" width="10" height="10" fill="#c62828" rx="2"/>')
    out.append(f'<text x="{left+chart_w-126}" y="{top+28}" font-size="9" fill="#333">not clarified (fail)</text>')
    out.append('</svg>')
    return "\n".join(out)

def svg_sticky_timeline_conv(conv: Dict[str, Any]) -> str:
    """Inline SVG timeline for one conversation showing applied_subspace per turn."""
    turns = conv.get("turns") or []
    if not turns:
        return ""
    n = len(turns)
    W = 760
    H = 70
    left = 20
    right = 20
    top = 18
    chart_w = W - left - right
    step = chart_w / n if n else chart_w
    out = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Sticky timeline {esc(conv.get("id",""))}">']
    out.append(f'<rect width="{W}" height="{H}" fill="#fafafa" rx="8" stroke="#e0e0e0"/>')
    # line
    y_mid = H // 2
    out.append(f'<line x1="{left+20}" y1="{y_mid}" x2="{left+chart_w-20}" y2="{y_mid}" stroke="#bdbdbd" stroke-width="3" stroke-linecap="round"/>')
    for idx, t in enumerate(turns):
        cx = left + step * (idx + 0.5)
        exp = t.get("expected_subspace")
        actual = t.get("applied_subspace")
        # color by actual, border indicates match
        color = SUBSPACE_COLORS.get(actual or "none", "#9e9e9e")
        exp_color = SUBSPACE_COLORS.get(exp or "none", "#9e9e9e") if exp else "#e0e0e0"
        match = (exp == actual) if exp is not None else True  # if no expected, pass
        # node circle
        out.append(f'<circle cx="{cx:.1f}" cy="{y_mid}" r="18" fill="{color}" stroke="#fff" stroke-width="2"/>')
        # inner ring for expected mismatch
        if not match:
            out.append(f'<circle cx="{cx:.1f}" cy="{y_mid}" r="22" fill="none" stroke="#c62828" stroke-width="2" stroke-dasharray="4 3"/>')
        # turn label
        out.append(f'<text x="{cx:.1f}" y="{y_mid+5}" text-anchor="middle" font-size="10" font-weight="700" fill="#fff">T{idx+1}</text>')
        # top label: actual
        display_actual = actual if actual else "∅"
        out.append(f'<text x="{cx:.1f}" y="14" text-anchor="middle" font-size="9" fill="#333">{esc(display_actual)}</text>')
        # bottom label: expected (small)
        if exp is not None:
            out.append(f'<text x="{cx:.1f}" y="{H-8}" text-anchor="middle" font-size="7" fill="#666">exp: {esc(exp)}</text>')
        else:
            out.append(f'<text x="{cx:.1f}" y="{H-8}" text-anchor="middle" font-size="7" fill="#999">exp: —</text>')
        # arrow between nodes
        if idx < n - 1:
            nx = left + step * (idx + 1.5)
            mid_x = (cx + nx) / 2
            out.append(f'<polygon points="{mid_x+6},{y_mid-6} {mid_x+6},{y_mid+6} {mid_x+14},{y_mid}" fill="#616161"/>')
    out.append('</svg>')
    return "\n".join(out)

def svg_kb_probe_hit(by_subspace_hit: Dict[str, Dict[str, float]], overall_hit: float) -> str:
    """Bar chart for kb probe Hit@K per subspace (with vs without filter)."""
    if not by_subspace_hit:
        return ""
    subspaces = list(by_subspace_hit.keys())
    W = 700
    left = 180
    right = 40
    bar_h = 14
    gap = 8
    H = 40 + len(subspaces) * (bar_h*2 + gap + 10) + 30
    chart_w = W - left - right
    out = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="KB probe hit">']
    out.append(f'<rect width="{W}" height="{H}" fill="#ffffff" rx="8"/>')
    out.append(f'<text x="{W//2}" y="20" text-anchor="middle" font-size="13" font-weight="700" fill="#222">Direct Retrieval Probe — Hit@K per subspace (top1 exists)</text>')
    y = 36
    for s in subspaces:
        data = by_subspace_hit[s]
        out.append(f'<text x="{left-10}" y="{y+10}" text-anchor="end" font-size="11" fill="#333">{esc(s)}</text>')
        # no_filter
        v_nf = float(data.get("no_filter", 0.0))
        w_nf = int(round(v_nf * chart_w))
        out.append(f'<rect x="{left}" y="{y}" width="{chart_w}" height="{bar_h}" rx="3" fill="#eceff1"/>')
        out.append(f'<rect x="{left}" y="{y}" width="{w_nf}" height="{bar_h}" rx="3" fill="#90a4ae"/>')
        out.append(f'<text x="{left+chart_w+6}" y="{y+10}" font-size="10" fill="#444">{v_nf:.2f} no_filter</text>')
        y += bar_h + 4
        # with_filter
        v_wf = float(data.get("with_filter", 0.0))
        w_wf = int(round(v_wf * chart_w))
        out.append(f'<rect x="{left}" y="{y}" width="{chart_w}" height="{bar_h}" rx="3" fill="#eceff1"/>')
        out.append(f'<rect x="{left}" y="{y}" width="{w_wf}" height="{bar_h}" rx="3" fill="#1976d2"/>')
        out.append(f'<text x="{left+chart_w+6}" y="{y+10}" font-size="10" fill="#444">{v_wf:.2f} with_filter</text>')
        y += bar_h + gap + 6
        out.append(f'<line x1="{left}" y1="{y-4}" x2="{left+chart_w}" y2="{y-4}" stroke="#f0f0f0"/>')
    # ticks
    for frac, lab in [(0.0,"0"),(0.5,"0.5"),(1.0,"1.0")]:
        x = left + int(round(frac*chart_w))
        out.append(f'<line x1="{x}" y1="36" x2="{x}" y2="{y-6}" stroke="#e0e0e0" stroke-dasharray="3 3"/>')
    out.append('</svg>')
    return "\n".join(out)

# ---------------------------------------------------------------------------
# Report building
# ---------------------------------------------------------------------------

def build_lookup(ragas: Dict[str, Any]) -> Dict[Tuple[str,int], Dict[str, Any]]:
    lookup: Dict[Tuple[str,int], Dict[str, Any]] = {}
    for pt in ragas.get("per_turn", []) or []:
        key = (str(pt.get("conv_id")), int(pt.get("turn_index", 0)))
        lookup[key] = pt
    return lookup

def generate_html(bench: Dict[str, Any], ragas: Dict[str, Any]) -> str:
    meta_bench = bench.get("meta", {})
    summary = bench.get("summary", {})
    overall = ragas.get("overall", {})
    by_subspace = ragas.get("by_subspace", {}) or {}
    # Header values
    date_str = meta_bench.get("timestamp") or ragas.get("meta", {}).get("timestamp") or datetime.now(timezone.utc).isoformat()
    try:
        dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        date_pretty = dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        date_pretty = str(date_str)
    total_turns = overall.get("total_turns") if overall.get("total_turns") is not None else summary.get("total_turns")
    total_convs = summary.get("total_conversations", len(bench.get("conversations", [])))
    avg_lat = None
    if overall.get("latency_ms") and isinstance(overall["latency_ms"], dict):
        avg_lat = overall["latency_ms"].get("avg")
    if avg_lat is None:
        avg_lat = summary.get("latency_ms", {}).get("avg") if isinstance(summary.get("latency_ms"), dict) else None
    error_rate = overall.get("error_rate")
    if error_rate is None:
        errs = summary.get("errors", 0)
        tot = summary.get("total_turns", total_turns or 1)
        error_rate = round(errs / tot, 4) if tot else 0.0

    ragas_lookup = build_lookup(ragas)

    # For per-subspace table: ensure overall row
    # Metrics order for table columns
    table_metrics = ["faithfulness", "answer_relevancy", "context_relevancy", "hallucination", "ambiguity_resolution", "sticky_persistence", "retrieval_hit"]

    # Collect kb probes
    kb_probes = bench.get("kb_probes")
    has_probes = isinstance(kb_probes, list) and len(kb_probes) > 0

    # Count for G5 highlight: find bench turns with G5
    g5_turns: List[Dict[str, Any]] = []
    for conv in bench.get("conversations", []) or []:
        for t in conv.get("turns", []) or []:
            if "G5" in (t.get("user") or "") or "G5" in (t.get("notes") or "") or "G5" in (t.get("content") or ""):
                g5_turns.append({"conv_id": conv.get("id"), "turn": t, "type": "conv"})
    for s in bench.get("single_baselines", []) or []:
        q = s.get("query") or s.get("user") or ""
        if "G5" in q or "G5" in (s.get("notes") or ""):
            g5_turns.append({"conv_id": s.get("id"), "turn": s, "type": "single"})

    html_parts: List[str] = []
    html_parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Work Credit RAG — Benchmark Report</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 24px; color: #222; background: #f8f9fa; line-height: 1.5; }
  .container { max-width: 1100px; margin: 0 auto; background: #fff; padding: 28px; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
  h1 { font-size: 26px; margin: 0 0 6px 0; color: #111; }
  h2 { font-size: 18px; margin: 32px 0 12px 0; padding-bottom: 6px; border-bottom: 2px solid #e3f2fd; color: #1565c0; }
  h3 { font-size: 15px; margin: 20px 0 8px 0; color: #333; }
  .subtitle { color: #666; font-size: 13px; margin-bottom: 18px; }
  .kpi-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin: 16px 0 20px 0; }
  .kpi { background: #f5f7fb; border: 1px solid #e0e7ff; border-radius: 10px; padding: 12px 14px; text-align: center; }
  .kpi .val { font-size: 22px; font-weight: 700; color: #1565c0; }
  .kpi .lbl { font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.04em; }
  table { width: 100%; border-collapse: collapse; margin: 10px 0 16px 0; font-size: 13px; }
  th { background: #f5f7fb; color: #333; font-weight: 600; padding: 8px 6px; border: 1px solid #dde3ea; text-align: center; }
  td { padding: 7px 6px; border: 1px solid #e6e8eb; text-align: center; vertical-align: top; }
  tr:nth-child(even) { background: #fafbfc; }
  .rtl { direction: rtl; text-align: right; font-family: Tahoma, "DejaVu Sans", sans-serif; background: #fffbe6; padding: 4px 8px; border-radius: 4px; }
  .pass { color: #2e7d32; font-weight: 700; }
  .fail { color: #c62828; font-weight: 700; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
  .badge-stop { background: #e8f5e9; color: #2e7d32; border: 1px solid #c8e6c9; }
  .badge-clarify { background: #fff8e1; color: #f57f17; border: 1px solid #ffe082; }
  .badge-greeting { background: #e3f2fd; color: #1565c0; border: 1px solid #bbdefb; }
  .badge-error { background: #ffebee; color: #c62828; border: 1px solid #ef9a9a; }
  .snippet { font-size: 12px; color: #444; text-align: left; max-width: 260px; word-break: break-word; }
  .chunk-preview { font-size: 11px; color: #555; text-align: left; background: #f6f8fa; padding: 6px; border-radius: 4px; max-width: 260px; }
  .alert { padding: 12px 16px; border-radius: 8px; margin: 12px 0; font-size: 13px; }
  .alert-info { background: #e3f2fd; border: 1px solid #90caf9; color: #0d47a1; }
  .alert-warn { background: #fff3e0; border: 1px solid #ffcc80; color: #e65100; }
  .alert-success { background: #e8f5e9; border: 1px solid #a5d6a7; color: #1b5e20; }
  .alert-danger { background: #ffebee; border: 1px solid #ef9a9a; color: #b71c1c; }
  .timeline-wrap { overflow-x: auto; padding: 8px 0; }
  svg { display: block; margin: 12px auto; max-width: 100%; height: auto; }
  .toc { background: #f5f7fb; border: 1px solid #e0e7ff; border-radius: 8px; padding: 12px 18px; margin: 12px 0 20px 0; }
  .toc a { color: #1565c0; text-decoration: none; font-size: 13px; }
  .toc a:hover { text-decoration: underline; }
  .toc li { margin: 4px 0; }
  .persian { direction: rtl; font-family: Tahoma, sans-serif; }
  @media print {
    body { background: #fff; padding: 0; font-size: 11pt; }
    .container { box-shadow: none; border: none; padding: 12px; max-width: none; }
    .kpi-grid { grid-template-columns: repeat(5, 1fr); }
    table { page-break-inside: auto; }
    tr { page-break-inside: avoid; }
    h2 { page-break-after: avoid; }
    svg { page-break-inside: avoid; }
  }
  @media (max-width: 700px) {
    .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  }
</style>
</head>
<body>
<div class="container">
""")
    html_parts.append(f'<h1>Work Credit RAG — Benchmark Report</h1>')
    html_parts.append(f'<div class="subtitle">Generated {esc(date_pretty)} &nbsp;·&nbsp; model: {esc(meta_bench.get("model","—"))} &nbsp;·&nbsp; bench: {esc(bench.get("meta",{}).get("timestamp","—"))} &nbsp;·&nbsp; ragas judge: {esc(ragas.get("meta",{}).get("model_judge","heuristic"))} ({esc(ragas.get("meta",{}).get("endpoint_judge","—"))})</div>')

    # KPI header
    html_parts.append('<div class="kpi-grid">')
    html_parts.append(f'<div class="kpi"><div class="val">{total_turns if total_turns is not None else "—"}</div><div class="lbl">total turns</div></div>')
    html_parts.append(f'<div class="kpi"><div class="val">{total_convs}</div><div class="lbl">total conversations</div></div>')
    html_parts.append(f'<div class="kpi"><div class="val">{fmt_lat(avg_lat)}</div><div class="lbl">avg latency</div></div>')
    html_parts.append(f'<div class="kpi"><div class="val">{error_rate:.1%}' + '</div><div class="lbl">error rate</div></div>')
    p50 = (overall.get("latency_ms", {}) or {}).get("p50") if isinstance(overall.get("latency_ms"), dict) else None
    html_parts.append(f'<div class="kpi"><div class="val">{fmt_lat(p50)}</div><div class="lbl">p50 latency</div></div>')
    html_parts.append('</div>')

    # TOC
    html_parts.append('<div class="toc"><strong>Contents</strong><ol>'
                      '<li><a href="#overall">Overall Metrics</a></li>'
                      '<li><a href="#subspace">Per-Subspace Comparison</a></li>'
                      '<li><a href="#convs">Per-Conversation Drill-Down</a></li>'
                      '<li><a href="#hallucination">Hallucination Details (G5)</a></li>'
                      '<li><a href="#ambiguity">Ambiguity Resolution Scatter</a></li>'
                      '<li><a href="#sticky">Sticky Persistence Timeline</a></li>'
                      '<li><a href="#kbprobe">Direct Retrieval Probe</a></li>'
                      '</ol></div>')

    # Overall metrics bar chart
    html_parts.append('<h2 id="overall">1. Overall Metrics</h2>')
    # Table small
    html_parts.append('<table><tr><th>Metric</th><th>Score (0–1)</th><th>Interpretation</th></tr>')
    order_for_table = ["faithfulness", "answer_relevancy", "context_relevancy", "context_recall", "hallucination", "ambiguity_resolution", "sticky_persistence", "retrieval_hit"]
    for k in order_for_table:
        if k == "hallucination":
            inv = overall.get("non_hallucination")
            if inv is not None:
                v = float(inv)
                raw = overall.get("hallucination")
                html_parts.append(f'<tr><td>hallucination <span style="color:#666">(inverted: 1 − hallucination)</span></td><td><strong>{v:.3f}</strong> <span style="color:#777;font-size:11px;">(raw hallucination {fmt_score(raw)})</span></td><td>higher is better — not hallucinating</td></tr>')
            else:
                raw = overall.get("hallucination")
                inv_v = 1.0 - float(raw) if raw is not None else None
                html_parts.append(f'<tr><td>hallucination (inverted)</td><td>{fmt_score(inv_v)}</td><td>1 − hallucination</td></tr>')
        else:
            html_parts.append(f'<tr><td>{esc(k)}</td><td><strong>{fmt_score(overall.get(k))}</strong></td><td>{"higher is better"}</td></tr>')
    html_parts.append('</table>')
    html_parts.append(svg_overall_metrics(overall))
    # Stage timing if present
    stage = overall.get("stage_timing_ms")
    if isinstance(stage, dict) and stage:
        html_parts.append('<h3>Stage Timing (ms) p50 / p95 / avg</h3>')
        html_parts.append('<table><tr><th>Stage</th><th>p50</th><th>p95</th><th>avg</th><th>count</th></tr>')
        for st, vals in stage.items():
            if isinstance(vals, dict):
                html_parts.append(f'<tr><td>{esc(st)}</td><td>{vals.get("p50","—")}</td><td>{vals.get("p95","—")}</td><td>{vals.get("avg","—")}</td><td>{vals.get("count","—")}</td></tr>')
        html_parts.append('</table>')

    # Per-subspace comparison
    html_parts.append('<h2 id="subspace">2. Per-Subspace Comparison</h2>')
    html_parts.append('<p style="font-size:12px;color:#666;">Columns: count, faithfulness, answer_relevancy, context_relevancy, hallucination (inverted), ambiguity_resolution, sticky_persistence, retrieval_hit, p50 latency. Hallucination shown as 1 − hallucination so higher is better. “overall” row is weighted mean across all turns.</p>')
    # Build subspace table rows
    # canonical order: cheque, facilities_person, facilities_legal, general, overall, plus any others
    subspaces_order = ["cheque", "facilities_person", "facilities_legal", "general", "overall"]
    # Add extra subspaces present not in canonical
    for k in sorted(by_subspace.keys()):
        if k not in subspaces_order and k not in ("overall",):
            subspaces_order.insert(-1, k)
    html_parts.append('<table><tr><th>Subspace</th><th>count</th><th>faithfulness</th><th>answer_relevancy</th><th>context_relevancy</th><th>hallucination (inv)</th><th>ambiguity</th><th>sticky</th><th>retrieval_hit</th><th>p50 latency</th></tr>')
    for s in subspaces_order:
        if s == "overall":
            agg = overall
            cnt = agg.get("total_turns", agg.get("count", total_turns))
            # overall agg uses different keys; ensure metrics exist
            faith = fmt_score(agg.get("faithfulness"))
            ans_rel = fmt_score(agg.get("answer_relevancy"))
            ctx_rel = fmt_score(agg.get("context_relevancy"))
            # hallucination inv
            inv = agg.get("non_hallucination")
            if inv is None and agg.get("hallucination") is not None:
                inv = 1.0 - float(agg.get("hallucination"))
            hall_inv = fmt_score(inv)
            amb = fmt_score(agg.get("ambiguity_resolution"))
            stick = fmt_score(agg.get("sticky_persistence"))
            hit = fmt_score(agg.get("retrieval_hit"))
            p50v = fmt_lat((agg.get("latency_ms", {}) or {}).get("p50") if isinstance(agg.get("latency_ms"), dict) else None)
            html_parts.append(f'<tr style="background:#e8f0fe;font-weight:600;"><td>{esc(s)}</td><td>{cnt if cnt is not None else "—"}</td><td>{faith}</td><td>{ans_rel}</td><td>{ctx_rel}</td><td>{hall_inv}</td><td>{amb}</td><td>{stick}</td><td>{hit}</td><td>{p50v}</td></tr>')
        else:
            agg = by_subspace.get(s)
            if agg is None:
                # show empty row with 0
                html_parts.append(f'<tr><td>{esc(s)}</td><td>0</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td></tr>')
                continue
            cnt = agg.get("count", 0)
            faith = fmt_score(agg.get("faithfulness"))
            ans_rel = fmt_score(agg.get("answer_relevancy"))
            ctx_rel = fmt_score(agg.get("context_relevancy"))
            inv = agg.get("non_hallucination")
            if inv is None and agg.get("hallucination") is not None:
                inv = 1.0 - float(agg.get("hallucination"))
            hall_inv = fmt_score(inv)
            amb = fmt_score(agg.get("ambiguity_resolution"))
            stick = fmt_score(agg.get("sticky_persistence"))
            hit = fmt_score(agg.get("retrieval_hit"))
            p50v = fmt_lat((agg.get("latency_ms", {}) or {}).get("p50") if isinstance(agg.get("latency_ms"), dict) else None)
            html_parts.append(f'<tr><td><span style="display:inline-block;width:10px;height:10px;background:{SUBSPACE_COLORS.get(s,"#9e9e9e")};border-radius:2px;margin-right:4px;vertical-align:middle;"></span>{esc(s)}</td><td>{cnt}</td><td>{faith}</td><td>{ans_rel}</td><td>{ctx_rel}</td><td>{hall_inv}</td><td>{amb}</td><td>{stick}</td><td>{hit}</td><td>{p50v}</td></tr>')
    html_parts.append('</table>')
    html_parts.append(svg_subspace_grouped(by_subspace, overall))

    # Per-conversation drill-down
    html_parts.append('<h2 id="convs">3. Per-Conversation Drill-Down</h2>')
    html_parts.append(f'<p style="font-size:12px;color:#666;">{len(bench.get("conversations",[]) or [])} multi-turn conversations + {len(bench.get("single_baselines",[]) or [])} single baselines. Turn-by-turn: query (RTL), expected vs actual finish_reason (green=match/red=mismatch), subspace, latency, faithfulness, content snippet (200 chars), retrieved chunks preview.</p>')
    for conv in bench.get("conversations", []) or []:
        cid = conv.get("id", "unknown")
        html_parts.append(f'<h3 style="margin-top:18px;">{esc(cid)} — <span style="font-weight:400;color:#555;">{esc(conv.get("description",""))}</span> <span style="font-size:11px;color:#777;">[{esc(conv.get("subspace",""))}] elapsed {fmt_lat(conv.get("elapsed_ms"))}</span></h3>')
        html_parts.append('<table><tr><th>#</th><th>Query (RTL)</th><th>Expected → Actual <br>finish_reason</th><th>Expected → Actual <br>subspace</th><th>Latency</th><th>Faithfulness</th><th>Content snippet (200)</th><th>Retrieved chunks</th></tr>')
        for t in conv.get("turns", []) or []:
            idx = t.get("turn_index", 0)
            q = t.get("user", "")
            exp_f = t.get("expected_finish")
            act_f = t.get("finish_reason")
            exp_s = t.get("expected_subspace")
            act_s = t.get("applied_subspace")
            lat = t.get("latency_ms_wall") if t.get("latency_ms_wall") is not None else t.get("latency_ms")
            # ragas faithfulness
            key = (cid, idx)
            rag = ragas_lookup.get(key, {})
            faith_v = (rag.get("scores", {}) or {}).get("faithfulness") if rag else None
            faith_m = (rag.get("metrics", {}) or {}).get("faithfulness", {}) if rag else {}
            faith_reason = faith_m.get("reason", "") if isinstance(faith_m, dict) else ""
            # finish match
            fm = t.get("finish_match")
            if fm is True:
                fin_cls = "pass"
                fin_icon = "✓"
            elif fm is False:
                fin_cls = "fail"
                fin_icon = "✗"
            else:
                # derive
                if exp_f == "greeting" and act_f in ("stop", "greeting"):
                    fin_cls = "pass"; fin_icon = "✓"
                else:
                    fin_cls = "fail" if exp_f != act_f else "pass"
                    fin_icon = "✓" if fin_cls=="pass" else "✗"
            # subspace match
            sm = t.get("subspace_match")
            if sm is True:
                sub_cls = "pass"; sub_icon = "✓"
            elif sm is False:
                sub_cls = "fail"; sub_icon = "✗"
            elif exp_s is None:
                sub_cls = "pass"; sub_icon = "—"
            else:
                sub_cls = "fail" if exp_s != act_s else "pass"
                sub_icon = "✓" if sub_cls=="pass" else "✗"

            # badge for actual finish
            act_badge_cls = "badge-stop"
            if act_f == "clarify":
                act_badge_cls = "badge-clarify"
            elif act_f == "greeting":
                act_badge_cls = "badge-greeting"
            elif act_f == "error":
                act_badge_cls = "badge-error"

            content_snip = (t.get("content_preview") or t.get("content") or "")[:200]
            # retrieved chunks preview
            chunks = t.get("retrieved_chunks") or []
            chunk_html = ""
            if not chunks:
                chunk_html = '<span style="color:#999;font-size:11px;">— no chunks (0)</span>'
            else:
                parts = []
                for ci, ch in enumerate(chunks[:2]):
                    if isinstance(ch, dict):
                        preview = ch.get("content_preview") or ch.get("content") or ch.get("text") or ""
                        preview = preview[:120]
                        fh = ch.get("folder_hierarchy") or ch.get("folderHierarchy") or []
                        fh_str = " / ".join(str(x) for x in fh) if isinstance(fh, list) and fh else ""
                        score = ch.get("rerank_score") or ch.get("hybrid_score") or ch.get("score")
                        score_str = f" score={float(score):.3f}" if isinstance(score, (int,float)) else ""
                        parts.append(f'<div style="margin-bottom:4px;"><span style="font-size:10px;color:#78909c;">#{ci+1}{esc(" — " + fh_str if fh_str else "")}{esc(score_str)}</span><br>{esc(preview)}</div>')
                    else:
                        parts.append(f'<div>{esc(str(ch)[:120])}</div>')
                if len(chunks) > 2:
                    parts.append(f'<div style="font-size:10px;color:#999;">+{len(chunks)-2} more</div>')
                chunk_html = "".join(parts)

            html_parts.append('<tr>'
                              f'<td>{idx}</td>'
                              f'<td><div class="rtl" dir="rtl">{esc(q)}</div><div style="font-size:10px;color:#888;margin-top:4px;text-align:left;">{esc(t.get("notes",""))}</div></td>'
                              f'<td><span style="font-size:11px;">{esc(exp_f or "—")}</span> → <span class="badge {act_badge_cls}">{esc(act_f or "—")}</span><br><span class="{fin_cls}">{fin_icon} {"match" if fin_cls=="pass" else "mismatch"}</span></td>'
                              f'<td><span style="font-size:11px;">{esc(exp_s if exp_s is not None else "—")}</span> → <span style="font-size:11px;">{esc(act_s if act_s is not None else "∅")}</span><br><span class="{sub_cls}">{sub_icon} {esc("sticky N/A" if exp_s is None else ("keep" if t.get("should_keep_sticky") else "match" if sub_cls=="pass" else "mismatch"))}</span></td>'
                              f'<td>{fmt_lat(lat)}</td>'
                              f'<td title="{esc(faith_reason)}">{fmt_score(faith_v)}</td>'
                              f'<td><div class="snippet" dir="rtl">{esc(content_snip)}</div></td>'
                              f'<td><div class="chunk-preview">{chunk_html}</div></td>'
                              '</tr>')
        html_parts.append('</table>')

    # Singles
    singles = bench.get("single_baselines", []) or []
    if singles:
        html_parts.append('<h3>Single-Turn Baselines</h3>')
        html_parts.append('<table><tr><th>ID</th><th>Query (RTL)</th><th>Expected → Actual</th><th>Latency</th><th>Faithfulness</th><th>Content snippet</th><th>Retrieved</th></tr>')
        for s in singles:
            q = s.get("query") or s.get("user") or ""
            exp_f = s.get("expected_finish")
            act_f = s.get("finish_reason")
            lat = s.get("latency_ms_wall") if s.get("latency_ms_wall") is not None else s.get("latency_ms")
            key = (s.get("id"), 1)
            rag = ragas_lookup.get(key, {})
            faith_v = (rag.get("scores", {}) or {}).get("faithfulness") if rag else None
            content_snip = (s.get("content_preview") or s.get("content") or "")[:200]
            rc = s.get("retrieved_chunks_count", len(s.get("retrieved_chunks") or []))
            html_parts.append(f'<tr><td>{esc(s.get("id"))}<br><span style="font-size:10px;color:#777;">{esc(s.get("subspace",""))}</span></td>'
                              f'<td><div class="rtl" dir="rtl">{esc(q)}</div></td>'
                              f'<td>{esc(exp_f or "—")} → <span class="badge { "badge-clarify" if act_f=="clarify" else "badge-stop"}">{esc(act_f or "—")}</span></td>'
                              f'<td>{fmt_lat(lat)}</td><td>{fmt_score(faith_v)}</td>'
                              f'<td><div class="snippet" dir="rtl">{esc(content_snip)}</div></td>'
                              f'<td>{rc}</td></tr>')
        html_parts.append('</table>')

    # Hallucination details
    html_parts.append('<h2 id="hallucination">4. Hallucination Details — G5 Grade Guard</h2>')
    html_parts.append('<div class="alert alert-info">Expected behaviour: <strong>non-existent grade G5</strong> must <em>not</em> be hallucinated. Correct response contains <span dir="rtl" class="persian">پاسخی یافت نشد</span> or “وجود ندارد / نامعتبر / یافت نشد” and does <strong>not</strong> invent a score / tier. Hallucination metric = 1.0 if hallucinated (bad), 0.0 if correct (good).</div>')
    if not g5_turns:
        html_parts.append('<div class="alert alert-warn">No G5 turns found in bench definitions (looked for “G5” in query/notes). Hallucination probe may be missing.</div>')
    else:
        for item in g5_turns:
            cid = item["conv_id"]
            t = item["turn"]
            # find ragas
            # need turn_index; for conv, turn has index; for single, 1
            ti = t.get("turn_index", 1) if item["type"]=="conv" else 1
            key = (cid, ti)
            rag = ragas_lookup.get(key, {})
            scores = (rag.get("scores", {}) or {}) if rag else {}
            hall = scores.get("hallucination")
            non_hall = scores.get("non_hallucination")
            metrics_h = (rag.get("metrics", {}) or {}).get("hallucination", {}) if rag else {}
            reason = metrics_h.get("reason", "") if isinstance(metrics_h, dict) else ""
            faith = scores.get("faithfulness")
            # bench fields for this turn (need to locate actual content if single vs conv)
            # For conv, content is in t; for single_baselines, content may be under turn itself; but bench single has no content until after execution? In bench_results, singles have content. Use t's content.
            q = t.get("user") or t.get("query") or ""
            content = t.get("content") or t.get("content_preview") or ""
            has_refusal = "پاسخی یافت نشد" in content
            has_not_exist = any(phrase in content for phrase in ["وجود ندارد", "یافت نشد", "نامعتبر", "چنین"])
            has_g5 = "G5" in content or "G5" in q
            hall_class = "alert-success" if (hall == 0 or hall == 0.0) else "alert-danger" if hall and hall > 0.5 else "alert-warn"
            hall_icon = "✓ PASS — not hallucinated" if hall == 0 else f"✗ FAIL — hallucinated (score {fmt_score(hall)})" if hall and hall>0 else f"score {fmt_score(hall)}"
            html_parts.append(f'<div class="alert {hall_class}" style="border-left: 6px solid {"#2e7d32" if hall==0 else "#c62828"};">'
                              f'<strong>{esc(cid)} T{ti}</strong> — Hallucination: <strong>{hall_icon}</strong> — non_hallucination {fmt_score(non_hall)} — faithfulness {fmt_score(faith)}<br>'
                              f'<span style="font-size:12px;color:#555;">Reason: {esc(reason)}</span>'
                              f'</div>')
            html_parts.append('<table><tr><th style="width:30%">Query (RTL)</th><th>Response (200 chars)</th><th style="width:18%">Checks</th><th style="width:16%">Metrics</th></tr>')
            checks = []
            checks.append(f'پاسخی یافت نشد: {"<span class=\'pass\'>✓ present</span>" if has_refusal else "<span class=\'fail\'>✗ missing</span>"}')
            checks.append(f'وجود ندارد/یافت نشد/نامعتبر: {"<span class=\'pass\'>✓ present</span>" if has_not_exist else "<span class=\'fail\'>✗ missing</span>"}')
            checks.append(f'Invented G5 in answer: {"<span class=\'fail\'>G5 present (hallucinated)</span>" if ("G5" in content and not has_not_exist) else "<span class=\'pass\'>no G5 tier invented</span>"}')
            html_parts.append(f'<tr><td><div class="rtl" dir="rtl">{esc(q)}</div></td>'
                              f'<td><div class="snippet" dir="rtl">{esc(content[:300])}</div></td>'
                              f'<td style="font-size:12px;text-align:left;">{"<br>".join(checks)}</td>'
                              f'<td>hallucination {fmt_score(hall)}<br>non_hall {fmt_score(non_hall)}<br>faith {fmt_score(faith)}</td></tr>')
            html_parts.append('</table>')
            # Also show top retrieved context if any
            chunks = t.get("retrieved_chunks") or []
            if chunks:
                html_parts.append('<div style="font-size:11px;color:#666;margin:6px 0 14px 0;">Retrieved chunks for G5 turn: ' + esc("; ".join((c.get("content_preview") or c.get("content") or "")[:80] for c in chunks[:2])) + '</div>')
            else:
                html_parts.append('<div style="font-size:11px;color:#888;margin:6px 0 14px 0;">No retrieved chunks (expected for hallucination probe — low grounding is correct if refused).</div>')

    # Ambiguity resolution scatter
    html_parts.append('<h2 id="ambiguity">5. Ambiguity Resolution Scatter</h2>')
    html_parts.append('<p style="font-size:12px;color:#666;">Scattered / ambiguous queries that should trigger <code>clarify</code> (expected_finish = clarify). Green = correctly clarified, red = should have clarified but answered directly. Score is ambiguity_resolution (1.0 = correct, 0.0 = failed).</p>')
    html_parts.append(svg_ambiguity_scatter(bench, ragas_lookup))
    # Table
    amb_rows = []
    for conv in bench.get("conversations", []) or []:
        for t in conv.get("turns", []) or []:
            if t.get("expected_finish") == "clarify":
                key = (conv.get("id"), t.get("turn_index"))
                rag = ragas_lookup.get(key, {})
                amb = (rag.get("scores", {}) or {}).get("ambiguity_resolution") if rag else None
                amb_rows.append({"conv": conv.get("id"), "turn": t.get("turn_index"), "query": t.get("user",""), "expected": t.get("expected_finish"), "actual": t.get("finish_reason"), "score": amb, "content": (t.get("content_preview") or t.get("content") or "")[:120]})
    for s in singles:
        if s.get("expected_finish") == "clarify":
            key = (s.get("id"), 1)
            rag = ragas_lookup.get(key, {})
            amb = (rag.get("scores", {}) or {}).get("ambiguity_resolution") if rag else None
            amb_rows.append({"conv": s.get("id"), "turn": 1, "query": s.get("query") or s.get("user",""), "expected": s.get("expected_finish"), "actual": s.get("finish_reason"), "score": amb, "content": (s.get("content_preview") or s.get("content") or "")[:120]})
    if amb_rows:
        html_parts.append('<table><tr><th>Conversation / Turn</th><th>Query (RTL)</th><th>Expected</th><th>Actual</th><th>Ambiguity score</th><th>Result</th><th>Response snippet</th></tr>')
        for r in amb_rows:
            clarified = (r["actual"] == "clarify")
            res_cls = "pass" if clarified else "fail"
            res_txt = "✓ clarified" if clarified else "✗ not clarified"
            html_parts.append(f'<tr><td>{esc(r["conv"])} T{r["turn"]}</td><td><div class="rtl" dir="rtl">{esc(r["query"])}</div></td><td><span class="badge badge-clarify">clarify</span></td><td><span class="badge {"badge-clarify" if clarified else "badge-stop"}">{esc(r["actual"] or "—")}</span></td><td>{fmt_score(r["score"])}</td><td class="{res_cls}">{res_txt}</td><td><div class="snippet" dir="rtl">{esc(r["content"])}</div></td></tr>')
        html_parts.append('</table>')
        # summary
        clarified_cnt = sum(1 for r in amb_rows if r["actual"]=="clarify")
        html_parts.append(f'<div class="alert alert-info">Ambiguous queries: {len(amb_rows)} total — clarified {clarified_cnt}/{len(amb_rows)} ({clarified_cnt/len(amb_rows):.0%}) — missed {len(amb_rows)-clarified_cnt}</div>')
    else:
        html_parts.append('<div class="alert alert-warn">No ambiguous (clarify-expected) turns found.</div>')

    # Sticky persistence timeline
    html_parts.append('<h2 id="sticky">6. Sticky Persistence Timeline</h2>')
    html_parts.append('<p style="font-size:12px;color:#666;">For each multi-turn conversation, evolution of <code>applied_subspace</code> per turn. Dashed red ring = sticky mismatch (actual ≠ expected). Colors: cheque=blue, facilities_person=green, facilities_legal=orange, general=purple, ∅=grey.</p>')
    multi_convs = [c for c in bench.get("conversations", []) or [] if len(c.get("turns",[]))>1]
    if not multi_convs:
        html_parts.append('<div class="alert alert-warn">No multi-turn conversations found.</div>')
    else:
        for conv in multi_convs:
            html_parts.append(f'<h3>{esc(conv.get("id"))} <span style="font-weight:400;color:#666;font-size:12px;">— {esc(conv.get("description",""))}</span></h3>')
            html_parts.append(f'<div class="timeline-wrap">{svg_sticky_timeline_conv(conv)}</div>')
            # also small table for exact values + ragas sticky scores
            html_parts.append('<table><tr><th>Turn</th><th>Query (RTL)</th><th>Expected subspace</th><th>Actual subspace</th><th>Should keep sticky</th><th>Sticky score</th><th>Retrieved</th></tr>')
            for t in conv.get("turns", []) or []:
                key = (conv.get("id"), t.get("turn_index"))
                rag = ragas_lookup.get(key, {})
                sticky = (rag.get("scores", {}) or {}).get("sticky_persistence") if rag else None
                q = t.get("user","")
                exp_s = t.get("expected_subspace")
                act_s = t.get("applied_subspace")
                sm = t.get("subspace_match")
                stick_cls = "pass" if sm else "fail" if sm is False else ""
                rc = t.get("retrieved_chunks_count", 0)
                html_parts.append(f'<tr><td>T{t.get("turn_index")}</td><td><div class="rtl" dir="rtl">{esc(q[:50])}</div></td><td>{esc(exp_s if exp_s is not None else "—")}</td><td><span style="display:inline-block;padding:2px 6px;border-radius:4px;background:{SUBSPACE_COLORS.get(act_s or "none","#eceff1")};color:#fff;font-size:11px;">{esc(act_s if act_s is not None else "∅")}</span></td><td>{ "yes" if t.get("should_keep_sticky") else "no"}</td><td class="{stick_cls}">{fmt_score(sticky)}</td><td>{rc}</td></tr>')
            html_parts.append('</table>')

    # Direct retrieval probe comparison
    html_parts.append('<h2 id="kbprobe">7. Direct Retrieval Probe — with vs without filter</h2>')
    if not has_probes:
        html_parts.append('<div class="alert alert-warn">No <code>kb_probes</code> data in bench_results (run <code>bench_runner</code> without <code>--skip-kb-probe</code> to generate Hit@K with vs without filter_path). Showing ragas retrieval_hit as proxy instead.</div>')
        # Show retrieval_hit per subspace as fallback
        if by_subspace:
            html_parts.append('<table><tr><th>Subspace</th><th>retrieval_hit (ragas)</th><th>count</th></tr>')
            for s in subspaces_order:
                if s == "overall":
                    continue
                agg = by_subspace.get(s)
                if agg:
                    html_parts.append(f'<tr><td>{esc(s)}</td><td>{fmt_score(agg.get("retrieval_hit"))}</td><td>{agg.get("count")}</td></tr>')
            html_parts.append('</table>')
    else:
        # Table per probe
        html_parts.append(f'<p style="font-size:12px;color:#666;">{len(kb_probes)} probes: direct KB <code>POST /search/api</code> with and without <code>filter_path</code> (top1 score + preview). Hit = top1 exists with rerank_score &gt; 0.</p>')
        html_parts.append('<table><tr><th>ID / Subspace</th><th>Query (RTL)</th><th>no_filter top1 score / has_results</th><th>with_filter top1 score / has_results</th><th>filter improves?</th><th>top1 preview (with_filter)</th></tr>')
        # aggregate per subspace
        agg_map: Dict[str, Dict[str, float]] = {}
        counts: Dict[str, int] = {}
        for pr in kb_probes:
            sid = pr.get("id","")
            q = pr.get("query","")
            fp = pr.get("filter_path")
            # derive subspace from filter or id
            subspace_guess = "unknown"
            # try to infer from by_subspace keys or id prefix
            for cand in ["cheque","facilities_person","facilities_legal","general","greeting"]:
                if cand in sid:
                    subspace_guess = cand
                    break
            if fp:
                for k, v in {"گزارش اعتباری چک":"cheque","اشخاص حقیقی":"facilities_person","اشخاص حقوقی":"facilities_legal","پایگاه دانش عمومی":"general"}.items():
                    if k in fp:
                        subspace_guess = v
            if subspace_guess == "unknown" and fp is None:
                subspace_guess = "greeting" if "greeting" in sid else "unknown"
            nf = pr.get("no_filter", {}) or {}
            wf = pr.get("with_filter", {}) or {}
            nf_score = nf.get("top1_score")
            wf_score = wf.get("top1_score")
            nf_has = nf.get("has_results", False)
            wf_has = wf.get("has_results", False)
            improves = pr.get("filter_improves")
            # for agg
            if subspace_guess not in agg_map:
                agg_map[subspace_guess] = {"no_filter_hit":0, "with_filter_hit":0}
                counts[subspace_guess] = 0
            counts[subspace_guess] += 1
            if nf_has:
                agg_map[subspace_guess]["no_filter_hit"] += 1
            if wf_has:
                agg_map[subspace_guess]["with_filter_hit"] += 1

            nf_score_str = f"{float(nf_score):.3f}" if isinstance(nf_score,(int,float)) else "—"
            wf_score_str = f"{float(wf_score):.3f}" if isinstance(wf_score,(int,float)) else "—"
            html_parts.append(f'<tr>'
                              f'<td><strong>{esc(sid)}</strong><br><span style="font-size:10px;color:#777;">{esc(subspace_guess)} · filter={esc(fp or "∅")}</span></td>'
                              f'<td><div class="rtl" dir="rtl">{esc(q)}</div></td>'
                              f'<td>{nf_score_str} <br><span style="font-size:10px;color:{"#2e7d32" if nf_has else "#c62828"};">{"✓ has_results" if nf_has else "✗ empty"}</span><br><span style="font-size:10px;color:#999;">lat {fmt_lat(nf.get("latency_ms"))}</span></td>'
                              f'<td>{wf_score_str} <br><span style="font-size:10px;color:{"#2e7d32" if wf_has else "#c62828"};">{"✓ has_results" if wf_has else "✗ empty"}</span><br><span style="font-size:10px;color:#999;">lat {fmt_lat(wf.get("latency_ms"))}</span></td>'
                              f'<td>{"<span class=\'pass\'>✓ yes</span>" if improves else "<span class=\'fail\'>✗ no</span>" if improves is False else "—"}</td>'
                              f'<td><div class="snippet">{esc((wf.get("top1_preview") or "")[:160])}</div></td>'
                              f'</tr>')
        html_parts.append('</table>')
        # Hit@K per subspace summary
        by_sub_hit: Dict[str, Dict[str,float]] = {}
        for s, agg in agg_map.items():
            tot = counts.get(s, 1)
            by_sub_hit[s] = {"no_filter": agg["no_filter_hit"]/tot if tot else 0.0, "with_filter": agg["with_filter_hit"]/tot if tot else 0.0}
        html_parts.append('<h3>Hit@K Summary per Subspace (Hit = has_results)</h3>')
        html_parts.append('<table><tr><th>Subspace</th><th>count</th><th>Hit no_filter</th><th>Hit with_filter</th><th>Δ (with − without)</th></tr>')
        for s in sorted(by_sub_hit.keys()):
            d = by_sub_hit[s]
            delta = d["with_filter"] - d["no_filter"]
            delta_cls = "pass" if delta >= 0 else "fail"
            html_parts.append(f'<tr><td>{esc(s)}</td><td>{counts.get(s,0)}</td><td>{d["no_filter"]:.2f}</td><td>{d["with_filter"]:.2f}</td><td class="{delta_cls}">{delta:+.2f}</td></tr>')
        html_parts.append('</table>')
        html_parts.append(svg_kb_probe_hit(by_sub_hit, 0.0))
        # also explain overall
        total_no = sum(v["no_filter_hit"] for v in agg_map.values())
        total_with = sum(v["with_filter_hit"] for v in agg_map.values())
        total_n = sum(counts.values())
        html_parts.append(f'<div class="alert alert-info">Overall Hit: no_filter {total_no}/{total_n} ({total_no/total_n:.1%}) vs with_filter {total_with}/{total_n} ({total_with/total_n:.1%}) across {total_n} probes.</div>')

    # Footer
    html_parts.append('<hr style="margin:28px 0;border:none;border-top:1px solid #e0e0e0;">')
    html_parts.append(f'<div style="font-size:11px;color:#888;text-align:center;">Work Credit RAG Benchmark Report — generated {esc(date_pretty)} · total turns {esc(str(total_turns))} · error rate {error_rate:.1%} · judge {esc(ragas.get("meta",{}).get("model_judge",""))}<br>Artifacts: bench_results_latest.json + ragas_results_latest.json → bench_report_latest.html</div>')
    html_parts.append('</div></body></html>')
    return "\n".join(html_parts)

def generate_markdown(bench: Dict[str, Any], ragas: Dict[str, Any]) -> str:
    meta_bench = bench.get("meta", {})
    summary = bench.get("summary", {})
    overall = ragas.get("overall", {})
    by_subspace = ragas.get("by_subspace", {}) or {}
    date_str = meta_bench.get("timestamp") or ragas.get("meta", {}).get("timestamp") or ""
    try:
        dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        date_pretty = dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        date_pretty = str(date_str)
    total_turns = overall.get("total_turns") if overall.get("total_turns") is not None else summary.get("total_turns")
    total_convs = summary.get("total_conversations", len(bench.get("conversations", [])))
    avg_lat = None
    if overall.get("latency_ms") and isinstance(overall["latency_ms"], dict):
        avg_lat = overall["latency_ms"].get("avg")
    if avg_lat is None:
        avg_lat = summary.get("latency_ms", {}).get("avg") if isinstance(summary.get("latency_ms"), dict) else None
    error_rate = overall.get("error_rate")
    if error_rate is None:
        errs = summary.get("errors", 0)
        tot = summary.get("total_turns", total_turns or 1)
        error_rate = round(errs / tot, 4) if tot else 0.0
    ragas_lookup = build_lookup(ragas)

    lines: List[str] = []
    lines.append(f"# Work Credit RAG — Benchmark Report")
    lines.append("")
    lines.append(f"> Generated {date_pretty} · model: {meta_bench.get('model','—')} · total turns {total_turns} · conversations {total_convs} · avg latency {fmt_lat(avg_lat)} · error rate {error_rate:.1%} · judge {ragas.get('meta',{}).get('model_judge','heuristic')}")
    lines.append("")
    lines.append(f"Artifacts: `bench_results_latest.json` + `ragas_results_latest.json` → `bench_report_latest.html` / `.md`")
    lines.append("")
    # Overall
    lines.append("## 1. Overall Metrics (0–1, higher is better; hallucination inverted)")
    lines.append("")
    lines.append("| Metric | Score |")
    lines.append("|---|---:|")
    for k in ["faithfulness","answer_relevancy","context_relevancy","context_recall","hallucination","ambiguity_resolution","sticky_persistence","retrieval_hit"]:
        if k == "hallucination":
            inv = overall.get("non_hallucination")
            if inv is None and overall.get("hallucination") is not None:
                inv = 1.0 - float(overall.get("hallucination"))
            raw = overall.get("hallucination")
            lines.append(f"| hallucination (inverted = 1 − hallucination {fmt_score(raw)}) | {fmt_score(inv)} |")
        else:
            lines.append(f"| {k} | {fmt_score(overall.get(k))} |")
    lines.append("")
    # Per-subspace
    lines.append("## 2. Per-Subspace Comparison")
    lines.append("")
    lines.append("> Columns: count, faithfulness, answer_relevancy, context_relevancy, hallucination (inv), ambiguity, sticky, retrieval_hit, p50 latency")
    lines.append("")
    lines.append("| Subspace | count | faith | ans_rel | ctx_rel | hall_inv | amb | sticky | hit | p50 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    subspaces_order = ["cheque","facilities_person","facilities_legal","general","overall"]
    for k in sorted(by_subspace.keys()):
        if k not in subspaces_order:
            subspaces_order.insert(-1, k)
    for s in subspaces_order:
        if s == "overall":
            agg = overall
            cnt = agg.get("total_turns", agg.get("count", total_turns))
            inv = agg.get("non_hallucination")
            if inv is None and agg.get("hallucination") is not None:
                inv = 1.0 - float(agg.get("hallucination"))
            p50v = fmt_lat((agg.get("latency_ms", {}) or {}).get("p50") if isinstance(agg.get("latency_ms"), dict) else None)
            lines.append(f"| **{s}** | {cnt if cnt is not None else '—'} | {fmt_score(agg.get('faithfulness'))} | {fmt_score(agg.get('answer_relevancy'))} | {fmt_score(agg.get('context_relevancy'))} | {fmt_score(inv)} | {fmt_score(agg.get('ambiguity_resolution'))} | {fmt_score(agg.get('sticky_persistence'))} | {fmt_score(agg.get('retrieval_hit'))} | {p50v} |")
        else:
            agg = by_subspace.get(s)
            if agg is None:
                lines.append(f"| {s} | 0 | — | — | — | — | — | — | — | — |")
                continue
            inv = agg.get("non_hallucination")
            if inv is None and agg.get("hallucination") is not None:
                inv = 1.0 - float(agg.get("hallucination"))
            p50v = fmt_lat((agg.get("latency_ms", {}) or {}).get("p50") if isinstance(agg.get("latency_ms"), dict) else None)
            lines.append(f"| {s} | {agg.get('count',0)} | {fmt_score(agg.get('faithfulness'))} | {fmt_score(agg.get('answer_relevancy'))} | {fmt_score(agg.get('context_relevancy'))} | {fmt_score(inv)} | {fmt_score(agg.get('ambiguity_resolution'))} | {fmt_score(agg.get('sticky_persistence'))} | {fmt_score(agg.get('retrieval_hit'))} | {p50v} |")
    lines.append("")
    # Per-conversation drill-down
    lines.append("## 3. Per-Conversation Drill-Down")
    lines.append("")
    for conv in bench.get("conversations", []) or []:
        cid = conv.get("id")
        lines.append(f"### {cid} — {conv.get('description','')} [{conv.get('subspace','')}]")
        lines.append("")
        lines.append(f"elapsed {fmt_lat(conv.get('elapsed_ms'))} · turns {conv.get('turns_count')}")
        lines.append("")
        lines.append("| # | Query | Expected → Actual (finish) | Expected → Actual (subspace) | Latency | Faith | Snippet | Retrieved |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for t in conv.get("turns", []) or []:
            idx = t.get("turn_index")
            q = (t.get("user") or "").replace("|","/").replace("\n"," ")
            exp_f = t.get("expected_finish") or "—"
            act_f = t.get("finish_reason") or "—"
            exp_s = t.get("expected_subspace") or "—"
            act_s = t.get("applied_subspace") or "∅"
            fm = t.get("finish_match")
            fin_icon = "✓" if fm else "✗" if fm is False else ("✓" if exp_f==act_f or (exp_f=="greeting" and act_f in ("stop","greeting")) else "✗")
            sm = t.get("subspace_match")
            sub_icon = "✓" if sm else "✗" if sm is False else ("✓" if exp_s==act_s else "—" if exp_s=="—" else "✗")
            lat = fmt_lat(t.get("latency_ms_wall") if t.get("latency_ms_wall") is not None else t.get("latency_ms"))
            key = (cid, idx)
            rag = ragas_lookup.get(key, {})
            faith = fmt_score((rag.get("scores",{}) or {}).get("faithfulness") if rag else None)
            snippet = (t.get("content_preview") or t.get("content") or "")[:80].replace("|","/").replace("\n"," ")
            chunks = t.get("retrieved_chunks") or []
            ch_preview = ""
            if chunks:
                first = chunks[0]
                if isinstance(first, dict):
                    ch_preview = (first.get("content_preview") or first.get("content") or "")[:60].replace("|","/").replace("\n"," ")
                else:
                    ch_preview = str(first)[:60]
                ch_preview = f"{len(chunks)} chunks: {ch_preview}"
            else:
                ch_preview = "0"
            lines.append(f"| {idx} | {q[:50]} | {exp_f} → {act_f} {fin_icon} | {exp_s} → {act_s} {sub_icon} | {lat} | {faith} | {snippet} | {ch_preview} |")
        lines.append("")
    singles = bench.get("single_baselines", []) or []
    if singles:
        lines.append("### Single-Turn Baselines")
        lines.append("")
        lines.append("| ID | Query | Expected → Actual | Latency | Faith | Retrieved |")
        lines.append("|---|---|---|---|---|---|")
        for s in singles:
            q = (s.get("query") or s.get("user") or "").replace("|","/")[:50]
            exp_f = s.get("expected_finish") or "—"
            act_f = s.get("finish_reason") or "—"
            lat = fmt_lat(s.get("latency_ms_wall") if s.get("latency_ms_wall") is not None else s.get("latency_ms"))
            key = (s.get("id"), 1)
            rag = ragas_lookup.get(key, {})
            faith = fmt_score((rag.get("scores",{}) or {}).get("faithfulness") if rag else None)
            rc = s.get("retrieved_chunks_count", len(s.get("retrieved_chunks") or []))
            lines.append(f"| {s.get('id')} | {q} | {exp_f} → {act_f} | {lat} | {faith} | {rc} |")
        lines.append("")
    # Hallucination
    lines.append("## 4. Hallucination Details — G5 Guard")
    lines.append("")
    lines.append("> G5 is a non-existent grade. Correct response must contain `پاسخی یافت نشد` or `وجود ندارد / یافت نشد / نامعتبر` and must NOT invent a G5 tier/score. Hallucination 1.0 = hallucinated (bad).")
    lines.append("")
    g5_found = False
    for conv in bench.get("conversations", []) or []:
        for t in conv.get("turns", []) or []:
            if "G5" in (t.get("user") or "") or "G5" in (t.get("notes") or ""):
                g5_found = True
                key = (conv.get("id"), t.get("turn_index"))
                rag = ragas_lookup.get(key, {})
                hall = fmt_score((rag.get("scores",{}) or {}).get("hallucination") if rag else None)
                content = (t.get("content") or t.get("content_preview") or "")[:160].replace("|","/")
                has_refusal = "پاسخی یافت نشد" in (t.get("content") or "")
                lines.append(f"- **{conv.get('id')} T{t.get('turn_index')}:** query `{t.get('user')}` · hallucination {hall} · refusal `پاسخی یافت نشد` {'✓' if has_refusal else '✗'} · response: `{content}`")
    for s in singles:
        if "G5" in (s.get("query") or s.get("user") or "") or "G5" in (s.get("notes") or ""):
            g5_found = True
            key = (s.get("id"), 1)
            rag = ragas_lookup.get(key, {})
            hall = fmt_score((rag.get("scores",{}) or {}).get("hallucination") if rag else None)
            content = (s.get("content") or s.get("content_preview") or "")[:160].replace("|","/")
            has_refusal = "پاسخی یافت نشد" in (s.get("content") or "")
            lines.append(f"- **{s.get('id')}:** query `{s.get('query') or s.get('user')}` · hallucination {hall} · refusal {'✓' if has_refusal else '✗'} · response: `{content}`")
    if not g5_found:
        lines.append("(No G5 turns found in bench definitions — probe missing)")
    lines.append("")
    # Ambiguity
    lines.append("## 5. Ambiguity Resolution Scatter")
    lines.append("")
    lines.append("| Conv / Turn | Query | Expected | Actual | Score | Result |")
    lines.append("|---|---|---|---|---|---|")
    for conv in bench.get("conversations", []) or []:
        for t in conv.get("turns", []) or []:
            if t.get("expected_finish") == "clarify":
                key = (conv.get("id"), t.get("turn_index"))
                rag = ragas_lookup.get(key, {})
                amb = fmt_score((rag.get("scores",{}) or {}).get("ambiguity_resolution") if rag else None)
                res = "✓ clarified" if t.get("finish_reason")=="clarify" else "✗ not clarified"
                lines.append(f"| {conv.get('id')} T{t.get('turn_index')} | {(t.get('user') or '')[:40].replace('|','/')} | clarify | {t.get('finish_reason')} | {amb} | {res} |")
    for s in singles:
        if s.get("expected_finish") == "clarify":
            key = (s.get("id"), 1)
            rag = ragas_lookup.get(key, {})
            amb = fmt_score((rag.get("scores",{}) or {}).get("ambiguity_resolution") if rag else None)
            res = "✓ clarified" if s.get("finish_reason")=="clarify" else "✗ not clarified"
            lines.append(f"| {s.get('id')} | {(s.get('query') or s.get('user') or '')[:40].replace('|','/')} | clarify | {s.get('finish_reason')} | {amb} | {res} |")
    lines.append("")
    # Sticky
    lines.append("## 6. Sticky Persistence Timeline")
    lines.append("")
    for conv in bench.get("conversations", []) or []:
        if len(conv.get("turns",[])) <=1:
            continue
        lines.append(f"### {conv.get('id')} — {conv.get('description','')}")
        lines.append("")
        seq = " → ".join(f"T{t.get('turn_index')}:{(t.get('applied_subspace') or '∅')}" for t in conv.get("turns",[]) )
        exp_seq = " → ".join(f"T{t.get('turn_index')}:{(t.get('expected_subspace') or '—')}" for t in conv.get("turns",[]) )
        lines.append(f"- **applied_subspace:** {seq}")
        lines.append(f"- **expected_subspace:** {exp_seq}")
        # sticky scores
        for t in conv.get("turns",[]):
            key = (conv.get("id"), t.get("turn_index"))
            rag = ragas_lookup.get(key, {})
            sticky = fmt_score((rag.get("scores",{}) or {}).get("sticky_persistence") if rag else None)
            sm = t.get("subspace_match")
            lines.append(f"  - T{t.get('turn_index')} `{t.get('user')[:40].replace('|','/')}` sticky {sticky} {'✓' if sm else '✗' if sm is False else ''}")
        lines.append("")
    # KB probe
    lines.append("## 7. Direct Retrieval Probe (with vs without filter)")
    lines.append("")
    kb_probes = bench.get("kb_probes")
    if not isinstance(kb_probes, list) or not kb_probes:
        lines.append("> No `kb_probes` data (run bench_runner without `--skip-kb-probe`). Ragas `retrieval_hit` per subspace is used as proxy above.")
        lines.append("")
    else:
        lines.append(f"{len(kb_probes)} probes (top1 with vs without filter_path)")
        lines.append("")
        lines.append("| ID | Subspace | Query | no_filter score | has_results | with_filter score | has_results | filter improves |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for pr in kb_probes:
            sid = pr.get("id","")
            q = (pr.get("query") or "")[:40].replace("|","/")
            fp = pr.get("filter_path") or "∅"
            nf = pr.get("no_filter",{}) or {}
            wf = pr.get("with_filter",{}) or {}
            nf_s = nf.get("top1_score")
            wf_s = wf.get("top1_score")
            lines.append(f"| {sid} | {fp} | {q} | {fmt_score(nf_s)} | {'✓' if nf.get('has_results') else '✗'} | {fmt_score(wf_s)} | {'✓' if wf.get('has_results') else '✗'} | {pr.get('filter_improves')} |")
        lines.append("")
    lines.append("---")
    lines.append(f"_Generated {date_pretty} · bench {meta_bench.get('timestamp','')} · judge {ragas.get('meta',{}).get('model_judge','')} · error_rate {error_rate:.1%}_")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Work Credit RAG benchmark report generator")
    p.add_argument("--bench", type=str, default="evaluation/artifacts/bench_results_latest.json", help="Path to bench_results_latest.json")
    p.add_argument("--ragas", type=str, default="evaluation/artifacts/ragas_results_latest.json", help="Path to ragas_results_latest.json")
    p.add_argument("--out", type=str, default="evaluation/artifacts/bench_report_latest.html", help="Path to write HTML report")
    p.add_argument("--md-out", type=str, default=None, help="Path to write Markdown report (default: same dir as --out with .md extension)")
    p.add_argument("--bench-only", action="store_true", help="Generate report from bench only (dummy ragas with zeros) if ragas file missing")
    return p.parse_args()

def resolve_path(p: str) -> Path:
    path = Path(p)
    if path.exists():
        return path
    # Try relative to repo roots
    here = Path(__file__).resolve().parent
    # orchestrator -> repo root is parents[3]
    try:
        if "orchestrator" in str(here):
            repo_root = Path(__file__).resolve().parents[3]
        else:
            # components/evaluation or evaluation
            repo_root = Path(__file__).resolve().parents[2] if "components" in str(here) else Path.cwd()
    except Exception:
        repo_root = Path.cwd()
    candidates = [
        repo_root / p,
        here / Path(p).name,
        here / "artifacts" / Path(p).name,
        repo_root / "evaluation" / "artifacts" / Path(p).name,
        repo_root / "components" / "orchestrator" / "evaluation" / "artifacts" / Path(p).name,
        repo_root / "components" / "evaluation" / "artifacts" / Path(p).name,
        Path.cwd() / p,
    ]
    for c in candidates:
        if c.exists():
            return c
    return path  # return original for error reporting

def main() -> None:
    args = parse_args()
    bench_path = resolve_path(args.bench)
    ragas_path = resolve_path(args.ragas)
    out_path = Path(args.out)
    # Allow resolving out relative to cwd if not absolute
    if not out_path.is_absolute():
        # Keep as given (may be relative to repo root)
        # If contains evaluation/artifacts, ensure parent exists
        pass
    md_out_path = Path(args.md_out) if args.md_out else out_path.with_suffix(".md")

    if not bench_path.exists():
        print(f"[ERROR] bench results not found: {bench_path} (arg: {args.bench})")
        raise SystemExit(1)

    bench = load_json(bench_path)

    if not ragas_path.exists():
        if args.bench_only:
            print(f"[WARN] ragas results not found: {ragas_path}, generating dummy ragas (bench-only mode)")
            # Build dummy ragas with zeros? Better to run minimal aggregation from bench
            # Create overall with zeros
            ragas = {
                "meta": {"timestamp": bench.get("meta",{}).get("timestamp",""), "model_judge": "none", "endpoint_judge": "none", "total_turns": bench.get("summary",{}).get("total_turns",0)},
                "overall": {k: 0.0 for k in ["faithfulness","answer_relevancy","context_relevancy","context_recall","hallucination","non_hallucination","ambiguity_resolution","sticky_persistence","retrieval_hit"]},
                "by_subspace": {},
                "per_turn": []
            }
            # Add latency from bench
            ragas["overall"]["latency_ms"] = bench.get("summary",{}).get("latency_ms", {})
            ragas["overall"]["total_turns"] = bench.get("summary",{}).get("total_turns", 0)
            ragas["overall"]["error_rate"] = 0.0
            ragas["overall"]["non_hallucination"] = 1.0 - ragas["overall"]["hallucination"]
        else:
            print(f"[ERROR] ragas results not found: {ragas_path} (arg: {args.ragas})")
            print("  Hint: run ragas_eval first or pass --bench-only")
            raise SystemExit(1)
    else:
        ragas = load_json(ragas_path)

    # Ensure ragas overall has non_hallucination
    if "overall" in ragas and "non_hallucination" not in ragas["overall"] and "hallucination" in ragas["overall"]:
        try:
            ragas["overall"]["non_hallucination"] = round(1.0 - float(ragas["overall"]["hallucination"]), 4)
        except Exception:
            ragas["overall"]["non_hallucination"] = 1.0
    # Ensure by_subspace also
    for sub, agg in (ragas.get("by_subspace") or {}).items():
        if "non_hallucination" not in agg and "hallucination" in agg:
            try:
                agg["non_hallucination"] = round(1.0 - float(agg["hallucination"]), 4)
            except Exception:
                agg["non_hallucination"] = 1.0

    html_content = generate_html(bench, ragas)
    md_content = generate_markdown(bench, ragas)

    # Write HTML
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[REPORT] wrote HTML {out_path} ({out_path.stat().st_size} bytes)")

    # Write Markdown
    md_out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(md_out_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"[REPORT] wrote Markdown {md_out_path} ({md_out_path.stat().st_size} bytes)")

    # Mirror to other artifact dirs (like bench_runner does)
    try:
        here = Path(__file__).resolve().parent
        repo_root = Path(__file__).resolve().parents[3] if "orchestrator" in str(here) else Path(__file__).resolve().parents[2] if "components" in str(here) else Path.cwd()
        mirror_dirs = [
            here / "artifacts",
            repo_root / "evaluation" / "artifacts",
            repo_root / "components" / "evaluation" / "artifacts",
            repo_root / "components" / "orchestrator" / "evaluation" / "artifacts",
        ]
        for md_dir in mirror_dirs:
            try:
                md_dir.mkdir(parents=True, exist_ok=True)
                # Only mirror if this dir already has bench artifacts or is the primary
                if md_dir.resolve() == out_path.parent.resolve():
                    continue
                # Write mirrors
                html_mirror = md_dir / out_path.name
                md_mirror = md_dir / md_out_path.name
                with open(html_mirror, "w", encoding="utf-8") as f:
                    f.write(html_content)
                with open(md_mirror, "w", encoding="utf-8") as f:
                    f.write(md_content)
                print(f"[REPORT] mirrored to {html_mirror}")
                print(f"[REPORT] mirrored to {md_mirror}")
            except Exception as e:
                print(f"[WARN] mirror failed for {md_dir}: {e}")
    except Exception as e:
        print(f"[WARN] mirroring failed: {e}")

if __name__ == "__main__":
    main()
