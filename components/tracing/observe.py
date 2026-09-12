"""RAG request-to-response observer.

Reads the traces produced by the existing observability stack and
reconstructs a per-request timeline:

  request (trace-create) -> validate_input -> query-rewrite -> retrieve
    -> build_context -> guarded_generate -> format_response
    -> response (trace-create upsert with same id)

Sources (in priority order):
  1. GET {HOST}/api/public/traces  (collector :3000 or Langfuse v2 :3001)
  2. /tmp/langfuse_traces.jsonl    (fallback collector file)

Existing producers (do NOT duplicate):
  components/orchestrator/src/work_rag_orchestrator/tracing.py
    start_trace() / update_trace() / trace_span()
  components/tracing/app.py  (POST /api/public/ingestion, GET /api/public/traces)

Usage:
  python -m observe --list [--host http://127.0.0.1:3000] [--limit 10]
  python -m observe --request <request_id> [--host ...]
  python -m observe --request <request_id> --json
  from observe import list_requests, get_timeline
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

TRACE_FILE = Path(os.getenv("TRACE_FILE", "/tmp/langfuse_traces.jsonl"))
# Live orchestrator traces go to Langfuse v2 :3001 (deploy/vast/start.sh default);
# fallback collector :3000 / JSONL file is the offline backup.
DEFAULT_HOST = os.getenv("LANGFUSE_HOST", "http://127.0.0.1:3001")
FALLBACK_HOST = "http://127.0.0.1:3000"

# Canonical pipeline order for display. Spans not in this list go last.
SPAN_ORDER = [
    "validate_input",
    "query-rewrite",
    "retrieve",
    "build_context",
    "guarded_generate",
    "format_response",
]


def _parse_item(obj: dict) -> dict | None:
    """Normalize one stored record into {type, body}. Handles both collector layouts."""
    if not isinstance(obj, dict):
        return None
    # Layout A: {"ts":..., "item": {"type":..., "body":{...}}}
    item = obj.get("item")
    if isinstance(item, dict) and "type" in item:
        return item
    # Layout B: raw envelope {"id":..., "type":..., "body":{...}}
    if "type" in obj and "body" in obj:
        return obj
    # Layout C: {"ts":..., "batch": {"batch":[...]}} — expand by caller, skip here
    return None


def _dedup(items: list[dict]) -> list[dict]:
    """Collector stores each envelope twice (batch line + item line). Dedupe by envelope id."""
    seen: set[str] = set()
    out: list[dict] = []
    for it in items:
        key = f"{it.get('type')}:{it.get('id')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def _load_from_file(path: Path = TRACE_FILE, max_lines: int = 5000) -> list[dict]:
    items: list[dict] = []
    if not path.exists():
        return items
    from collections import deque
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = deque(f, maxlen=max_lines)
    except Exception:
        return items
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        # batch wrapper lines contain nested batch; expand them
        batch = None
        if isinstance(obj, dict):
            b = obj.get("batch")
            if isinstance(b, dict) and isinstance(b.get("batch"), list):
                batch = b["batch"]
            elif isinstance(obj.get("item"), dict):
                it = _parse_item(obj)
                if it:
                    items.append(it)
                continue
        if batch is not None:
            for it in batch:
                if isinstance(it, dict) and "type" in it:
                    items.append(it)
        else:
            it = _parse_item(obj)
            if it:
                items.append(it)
    return items


def _v2_auth() -> tuple[str, str] | None:
    """Basic-auth creds for Langfuse v2. Prefers env, falls back to seeded file."""
    pk = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    sk = os.getenv("LANGFUSE_SECRET_KEY", "")
    if pk and sk:
        return pk, sk
    try:
        env_file = Path("/tmp/opencode/langfuse.env")
        if env_file.exists():
            vals: dict[str, str] = {}
            for line in env_file.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    vals[k.strip()] = v.strip()
            pk = vals.get("LANGFUSE_INIT_PROJECT_PUBLIC_KEY", "")
            sk = vals.get("LANGFUSE_INIT_PROJECT_SECRET_KEY", "")
            if pk and sk:
                return pk, sk
    except Exception:
        pass
    return None


def _http_get_json(url: str, auth: tuple[str, str] | None = None,
                   params: dict | None = None, timeout: float = 10.0) -> dict | None:
    """Zero-dependency GET (urllib) returning parsed JSON object. None on failure."""
    import base64
    import urllib.parse
    import urllib.request

    try:
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        if auth and auth[0] and auth[1]:
            token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
            req.add_header("Authorization", f"Basic {token}")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _v2_get(host: str, path: str, params: dict | None = None, timeout: float = 10.0) -> dict | None:
    """GET against Langfuse v2 public API. None on auth/network failure."""
    auth = _v2_auth()
    if not auth:
        return None
    return _http_get_json(f"{host.rstrip('/')}{path}", auth=auth, params=params, timeout=timeout)


def list_requests_v2(host: str, limit: int = 20) -> list[dict]:
    """List requests from Langfuse v2 (:3001). Empty list if unreachable/unauthorized."""
    data = _v2_get(host, "/api/public/traces", {"limit": limit})
    if not data or not isinstance(data.get("data"), list):
        return []
    obs = _v2_get(host, "/api/public/observations", {"limit": 100}) or {}
    span_counts: dict[str, int] = {}
    for o in obs.get("data", []) if isinstance(obs.get("data"), list) else []:
        tid = o.get("traceId")
        if tid:
            span_counts[tid] = span_counts.get(tid, 0) + 1
    rows = []
    for t in data["data"]:
        rid = t.get("id", "")
        rows.append({
            "request_id": rid,
            "name": t.get("name", ""),
            "input_preview": str(t.get("input") or "")[:120],
            "timestamp": t.get("timestamp", ""),
            "has_response": bool(t.get("output")),
            "output_preview": str(t.get("output") or "")[:120],
            "spans": span_counts.get(rid, 0),
        })
    return rows


def get_timeline_v2(request_id: str, host: str) -> dict | None:
    """Full timeline from Langfuse v2. None if trace not found / unreachable."""
    t = _v2_get(host, f"/api/public/traces/{request_id}")
    if not t or t.get("id") != request_id:
        return None
    obs = _v2_get(host, "/api/public/observations", {"traceId": request_id, "limit": 50}) or {}
    spans = []
    raw = obs.get("data", [])
    for o in raw if isinstance(raw, list) else []:
        spans.append({
            "span": o.get("name", "?"),
            "start": o.get("startTime", ""),
            "input": o.get("input"),
            "output": o.get("output"),
            "metadata": o.get("metadata", {}),
        })
    order = {n: i for i, n in enumerate(SPAN_ORDER)}
    spans.sort(key=lambda s: (order.get(s["span"], 99), str(s["start"])))
    return {
        "request_id": request_id,
        "name": t.get("name"),
        "timestamp": t.get("timestamp"),
        "input": t.get("input"),
        "output": t.get("output"),
        "metadata": t.get("metadata", {}),
        "spans": spans,
    }


def _load_from_api(host: str = FALLBACK_HOST, timeout: float = 5.0) -> list[dict]:
    """Query fallback collector GET /api/public/traces (returns last ~100). Empty on failure."""
    data = _http_get_json(f"{host.rstrip('/')}/api/public/traces", timeout=timeout) or {}
    payload = data.get("data", [])
    items: list[dict] = []
    for obj in payload if isinstance(payload, list) else []:
        it = _parse_item(obj)
        if it:
            items.append(it)
        # stored batch wrappers inside /traces payload
        elif isinstance(obj, dict) and isinstance(obj.get("batch"), dict):
            for sub in obj["batch"].get("batch", []):
                s = _parse_item(sub)
                if s:
                    items.append(s)
    return items


def load_items(host: str | None = DEFAULT_HOST) -> list[dict]:
    """API first, file fallback. Pass host=None to read file only."""
    if host:
        items = _dedup(_load_from_api(host))
        if items:
            return items
    return _dedup(_load_from_file())


def list_requests(host: str | None = DEFAULT_HOST) -> list[dict]:
    """One row per request_id: id, name, input preview, span count.

    Tries Langfuse v2 (:3001, live traffic) first, then the fallback
    collector envelopes (:3000 / JSONL file).
    """
    if host:
        rows = list_requests_v2(host)
        if rows:
            return rows
    traces: dict[str, dict] = {}
    spans: dict[str, int] = {}
    for it in load_items(host):
        t, b = it.get("type"), it.get("body", {})
        if t in ("trace-create", "trace-update") and isinstance(b, dict):
            rid = b.get("id")
            if not rid or rid in traces:
                # keep first input; later upsert only adds output
                if rid and "output" in b:
                    traces[rid]["output_preview"] = str(b["output"])[:120]
                    traces[rid].update({"has_response": True})
                continue
            if rid:
                traces[rid] = {
                    "request_id": rid,
                    "name": b.get("name", ""),
                    "input_preview": str(b.get("input", ""))[:120],
                    "timestamp": b.get("timestamp", ""),
                    "has_response": "output" in b,
                    "output_preview": str(b.get("output", ""))[:120],
                }
        elif t == "span-create" and isinstance(b, dict):
            tid = b.get("traceId")
            if tid:
                spans[tid] = spans.get(tid, 0) + 1
    rows = []
    for rid, row in traces.items():
        row["spans"] = spans.get(rid, 0)
        rows.append(row)
    # spans for request_ids seen only via spans (no trace-create, e.g. test-123)
    for tid, n in spans.items():
        if tid not in traces:
            rows.append({"request_id": tid, "name": "?", "input_preview": "",
                         "timestamp": "", "has_response": False,
                         "output_preview": "", "spans": n})
    rows.sort(key=lambda r: str(r.get("timestamp", "")))
    return rows


def get_timeline(request_id: str, host: str | None = DEFAULT_HOST) -> dict:
    """Full request->response timeline for one request_id.

    Tries Langfuse v2 (:3001, live traffic) first, then the fallback
    collector envelopes (:3000 / JSONL file).
    """
    if host:
        tl = get_timeline_v2(request_id, host)
        if tl:
            return tl
    req_input = req_output = req_name = req_ts = None
    req_meta: dict = {}
    span_list: list[dict] = []
    for it in load_items(host):
        t, b = it.get("type"), it.get("body", {})
        if not isinstance(b, dict):
            continue
        if t in ("trace-create", "trace-update") and b.get("id") == request_id:
            req_name = b.get("name", req_name)
            req_ts = b.get("timestamp", req_ts) or req_ts
            if b.get("input") is not None and req_input is None:
                req_input = b["input"]
            if b.get("output") is not None:
                req_output = b["output"]  # last upsert wins
            if isinstance(b.get("metadata"), dict):
                req_meta.update(b["metadata"])
        elif t == "span-create" and b.get("traceId") == request_id:
            span_list.append({
                "span": b.get("name", "?"),
                "start": b.get("startTime", ""),
                "input": b.get("input"),
                "output": b.get("output"),
                "metadata": b.get("metadata", {}),
            })
    order = {n: i for i, n in enumerate(SPAN_ORDER)}
    span_list.sort(key=lambda s: (order.get(s["span"], 99), str(s["start"])))
    return {
        "request_id": request_id,
        "name": req_name,
        "timestamp": req_ts,
        "input": req_input,
        "output": req_output,
        "metadata": req_meta,
        "spans": span_list,
    }


def render_text(tl: dict) -> str:
    L: list[str] = []
    L.append(f"request_id: {tl['request_id']}")
    L.append(f"trace:      {tl.get('name')} @ {tl.get('timestamp')}")
    if tl.get("metadata"):
        L.append(f"metadata:   {json.dumps(tl['metadata'], ensure_ascii=False)[:300]}")
    L.append(f"\n[REQUEST]\n{tl.get('input') or '(no trace-create input found)'}")
    for s in tl.get("spans", []):
        L.append(f"\n--- span: {s['span']} ({s['start']}) ---")
        if s.get("input") is not None:
            L.append(f"in:  {str(s['input'])[:800]}")
        if s.get("output") is not None:
            L.append(f"out: {str(s['output'])[:1500]}")
        if s.get("metadata"):
            L.append(f"meta: {json.dumps(s['metadata'], ensure_ascii=False)[:300]}")
    L.append(f"\n[RESPONSE]\n{tl.get('output') or '(no trace-create upsert with output yet)'}")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Observe RAG request-to-response traces")
    p.add_argument("--host", default=DEFAULT_HOST,
                   help="collector host (:3000 fallback or :3001 Langfuse v2)")
    p.add_argument("--file-only", action="store_true", help="read JSONL file, skip HTTP")
    p.add_argument("--list", dest="list_mode", action="store_true")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--request", dest="request_id", default=None)
    p.add_argument("--json", dest="as_json", action="store_true")
    a = p.parse_args(argv)
    host = None if a.file_only else a.host

    if a.request_id:
        tl = get_timeline(a.request_id, host)
        if not tl.get("spans") and tl.get("input") is None and tl.get("output") is None:
            # retry once against the other backend (v2 <-> fallback file)
            alt = FALLBACK_HOST if (host or "") != FALLBACK_HOST else DEFAULT_HOST
            tl = get_timeline(a.request_id, None if a.file_only else alt)
        if not tl.get("spans") and tl.get("input") is None and tl.get("output") is None:
            print(f"No trace found for request_id={a.request_id}", file=sys.stderr)
            return 1
        print(json.dumps(tl, ensure_ascii=False, indent=2) if a.as_json else render_text(tl))
        return 0

    rows = list_requests(host)
    for r in rows[-a.limit:]:
        flag = "✓" if r["has_response"] else "…"
        print(f"{flag} {r['request_id']}  spans={r['spans']}  in={r['input_preview'][:80]}")
        if r.get("output_preview"):
            print(f"    out={r['output_preview'][:100]}")
    if not rows:
        print("No traces found (is the collector running? start.sh launches :3000).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
