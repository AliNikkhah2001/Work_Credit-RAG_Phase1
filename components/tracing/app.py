"""Self-hosted Langfuse-compatible trace collector (host fallback, no Docker needed).
Implements Langfuse ingestion API + simple UI for Vast unprivileged host.
Stores traces to /tmp/langfuse_traces.jsonl and provides /api/public/health
"""
from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse, HTMLResponse
import html as _htmlesc
import json, time, os
from pathlib import Path

try:
    import observe as observer  # request-to-response timelines (same dir, stdlib-only)
except Exception:
    observer = None

app = FastAPI(title="Work RAG Tracing (Langfuse self-hosted fallback)")

TRACE_FILE = Path("/tmp/langfuse_traces.jsonl")
TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)

@app.get("/health")
async def health():
    return {"status": "ok", "collector": "langfuse-fallback"}

@app.get("/api/public/health")
async def lf_health():
    # Langfuse SDK expects this
    return {"status": "ok"}

@app.get("/")
async def root():
    count = 0
    traces = []
    if TRACE_FILE.exists():
        try:
            lines = TRACE_FILE.read_text().strip().splitlines()[-20:]
            for l in lines:
                try:
                    traces.append(json.loads(l))
                    count += 1
                except: pass
        except: pass
    html = f"""
    <html><head><title>Work RAG Tracing</title></head><body>
    <h1>Work RAG Tracing (Langfuse Self-Hosted Fallback)</h1>
    <p>Collector mimics Langfuse ingestion at <code>POST /api/public/ingestion</code>. Use <code>LANGFUSE_HOST=http://127.0.0.1:3000</code></p>
    <p>Traces stored: {TRACE_FILE} ({count} recent)</p>
    <p><a href="/api/public/traces">/api/public/traces (JSON)</a> | <a href="/health">/health</a></p>
    <p><b>Observe:</b> <a href="/observe">/observe</a> (request list) | <a href="/api/observe/requests">/api/observe/requests</a> (JSON)</p>
    <p><b>Studio (local graph debugger):</b> <a href="/studio">/studio</a> — runs the <code>rag</code> graph via the :2024 API server-side, no smith.langchain.com needed.</p>
    <pre>{_htmlesc.escape(json.dumps(traces, ensure_ascii=False, indent=2)[:8000])}</pre>
    </body></html>
    """
    return HTMLResponse(html)


def _timeline_or_404(request_id: str):
    """v2 (:3001 live) first, fallback collector / JSONL file second."""
    if observer is None:
        return None
    tl = observer.get_timeline(request_id)
    if not tl.get("spans") and tl.get("input") is None and tl.get("output") is None:
        tl = observer.get_timeline(request_id, observer.FALLBACK_HOST)
    if not tl.get("spans") and tl.get("input") is None and tl.get("output") is None:
        tl = observer.get_timeline(request_id, None)  # file-only last resort
    if not tl.get("spans") and tl.get("input") is None and tl.get("output") is None:
        return None
    return tl


@app.get("/observe")
async def observe_list(limit: int = Query(20, ge=1, le=100)):
    if observer is None:
        return HTMLResponse("<html><body><h1>Observer unavailable</h1></body></html>", status_code=500)
    rows = observer.list_requests()[-limit:]
    rows = rows[::-1]  # newest first
    trs = []
    for r in rows:
        flag = "✓" if r.get("has_response") else "…"
        rid = _htmlesc.escape(str(r.get("request_id", "")))
        trs.append(
            f'<tr><td>{flag}</td><td><a href="/observe/{rid}">{rid}</a></td>'
            f'<td>{_htmlesc.escape(str(r.get("name", "")))}</td>'
            f'<td>{_htmlesc.escape(str(r.get("timestamp", "")))}</td>'
            f'<td>{r.get("spans", 0)}</td>'
            f'<td>{_htmlesc.escape(str(r.get("input_preview", ""))[:100])}</td></tr>'
        )
    return HTMLResponse(
        "<html><head><title>RAG Observer</title></head><body>"
        "<h1>RAG Observer — request → response</h1>"
        "<p>Live: Langfuse v2 :3001, backup: this collector / JSONL. "
        'Full UIs: <a href="http://127.0.0.1:3001">Langfuse :3001</a></p>'
        '<table border="1" cellpadding="4">'
        "<tr><th></th><th>request_id</th><th>name</th><th>timestamp</th><th>spans</th><th>input</th></tr>"
        + "".join(trs) +
        "</table></body></html>"
    )


@app.get("/observe/{request_id}")
async def observe_timeline(request_id: str):
    tl = _timeline_or_404(request_id)
    if tl is None:
        return HTMLResponse(
            f"<html><body><h1>No trace for {_htmlesc.escape(request_id)}</h1>"
            '<p><a href="/observe">back to list</a></p></body></html>', status_code=404)
    parts = [f'<p><a href="/observe">back to list</a> | '
             f'<a href="/api/observe/timeline/{_htmlesc.escape(request_id)}">JSON</a></p>',
             f"<h1>Timeline: {_htmlesc.escape(request_id)}</h1>",
             f"<p>trace: {_htmlesc.escape(str(tl.get('name')))} @ {_htmlesc.escape(str(tl.get('timestamp')))}</p>"]
    if tl.get("metadata"):
        parts.append(f"<p>metadata: {_htmlesc.escape(json.dumps(tl['metadata'], ensure_ascii=False)[:300])}</p>")
    parts.append(f"<h2>Request</h2><pre>{_htmlesc.escape(str(tl.get('input') or '(none)'))[:2000]}</pre>")
    for s in tl.get("spans", []):
        parts.append(f"<h3>span: {_htmlesc.escape(str(s.get('span')))} "
                     f"<small>{_htmlesc.escape(str(s.get('start', '')))}</small></h3>")
        if s.get("input") is not None:
            parts.append(f"<b>in:</b><pre>{_htmlesc.escape(str(s['input']))[:1500]}</pre>")
        if s.get("output") is not None:
            parts.append(f"<b>out:</b><pre>{_htmlesc.escape(str(s['output']))[:2000]}</pre>")
    parts.append(f"<h2>Response</h2><pre>{_htmlesc.escape(str(tl.get('output') or '(no response yet)'))[:2000]}</pre>")
    return HTMLResponse("<html><head><title>Timeline " + _htmlesc.escape(request_id) +
                        "</title></head><body>" + "".join(parts) + "</body></html>")


@app.get("/api/observe/requests")
async def api_observe_requests(limit: int = Query(20, ge=1, le=100)):
    if observer is None:
        return JSONResponse({"error": "observer unavailable"}, status_code=500)
    return {"data": observer.list_requests()[-limit:],
            "observe_ui": "/observe"}


@app.get("/api/observe/timeline/{request_id}")
async def api_observe_timeline(request_id: str):
    tl = _timeline_or_404(request_id)
    if tl is None:
        return JSONResponse({"error": f"no trace for {request_id}"}, status_code=404)
    return tl


# ---------------------------------------------------------------------------
# Local Studio: debug UI for the `rag` LangGraph graph.
# LangSmith/Smith Studio is SaaS-only and cannot be self-hosted; this page
# serves the same debug loop locally: it drives the :2024 LangGraph API
# server-side (thread -> run -> poll -> state), so the browser only needs
# this host (one SSH tunnel), never smith.langchain.com.
# ---------------------------------------------------------------------------
STUDIO_API = os.getenv("STUDIO_API", "http://127.0.0.1:2024")
_studio_assistant_id: str | None = None


def _sg_call(method: str, path: str, payload: dict | None = None, timeout: float = 20.0):
    """Sync LangGraph API call (run inside to_thread; stdlib only). Raises on failure."""
    import urllib.request

    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{STUDIO_API.rstrip('/')}{path}", data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _sg_assistant_id() -> str:
    """Resolve (and cache) the assistant_id for graph `rag`."""
    global _studio_assistant_id
    if _studio_assistant_id:
        return _studio_assistant_id
    raw = _sg_call("POST", "/assistants/search", {"limit": 10})
    items = raw if isinstance(raw, list) else raw.get("data", [])
    for a in items:
        if a.get("graph_id") == "rag" or a.get("name") == "rag":
            _studio_assistant_id = a["assistant_id"]
            return _studio_assistant_id
    if items:
        _studio_assistant_id = items[0]["assistant_id"]
        return _studio_assistant_id
    raise RuntimeError("no assistants on :2024 (is `bash deploy/vast/studio.sh` running?)")


def _clip_state(values: dict) -> dict:
    """Trim heavy fields (chunk contents) so the debug page stays readable."""
    out: dict = {}
    for k, v in (values or {}).items():
        if k == "retrieved_chunks" and isinstance(v, list):
            out[k] = [{kk: (str(vv)[:300] if kk == "content" else vv)
                       for kk, vv in (c.items() if isinstance(c, dict) else {"text": c}.items())}
                      for c in v]
        elif isinstance(v, str):
            out[k] = v[:3000]
        else:
            try:
                out[k] = json.loads(json.dumps(v, ensure_ascii=False, default=str)[:4000])
            except Exception:
                out[k] = str(v)[:2000]
    return out


@app.get("/studio")
async def studio_page():
    return HTMLResponse(
        """<html><head><title>Local Studio — rag graph</title></head><body>
<h1>Local Studio — <code>rag</code> graph debugger</h1>
<p>Drives the :2024 LangGraph API server-side. Same input contract as Smith Studio
(runs need <code>request_id</code>). After the run, open its timeline in the Observer.</p>
<form id="f">
<label>request_id: <input id="rid" size="28" value="studio-local-001"></label>
<label><input id="reuse" type="checkbox"> reuse thread_id:</label>
<input id="tid" size="40" placeholder="(empty = new thread)"><br><br>
<textarea id="msg" rows="3" cols="80">سلام</textarea><br><br>
<button type="submit">Run graph</button>
</form>
<pre id="out">idle</pre>
<script>
document.getElementById('f').onsubmit = async (e) => {
  e.preventDefault();
  const out = document.getElementById('out');
  const body = {message: document.getElementById('msg').value,
                request_id: document.getElementById('rid').value};
  if (document.getElementById('reuse').checked && document.getElementById('tid').value)
    body.thread_id = document.getElementById('tid').value;
  out.textContent = 'starting run…';
  const t0 = Date.now();
  let r;
  try {
    r = await fetch('/api/studio/run', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  } catch (err) { out.textContent = 'start failed (network): ' + err; return; }
  let j = await r.json();
  if (j.error) { out.textContent = 'start failed: ' + j.error; return; }
  const qs = new URLSearchParams(
    {thread_id: j.thread_id, run_id: j.run_id, request_id: j.request_id});
  for (let i = 0; i < 80; i++) {  // ~4 min max
    const el = Math.round((Date.now() - t0) / 1000);
    out.textContent = `status=${j.status}  thread=${j.thread_id}\nrun=${j.run_id}\nelapsed=${el}s  (single :2024 worker — concurrent runs queue; LLM calls take ~30-60s)`;
    if (j.status !== 'pending' && j.status !== 'running') break;
    await new Promise(res => setTimeout(res, 3000));
    try {
      const pr = await fetch('/api/studio/result?' + qs.toString());
      j = await pr.json();
    } catch (err) { out.textContent = 'poll failed (network): ' + err; return; }
  }
  out.textContent = JSON.stringify(j, null, 2).slice(0, 12000);
};
</script>
</body></html>""")


@app.post("/api/studio/run")
async def api_studio_run(request: Request):
    """Start a graph run and return immediately; poll GET /api/studio/result for completion."""
    import asyncio
    import uuid

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)
    message = str(body.get("message", "")).strip()
    if not message:
        return JSONResponse({"error": "message is required"}, status_code=400)
    if len(message) > 4000:
        return JSONResponse({"error": "message too long (max 4000 chars)"}, status_code=400)
    request_id = str(body.get("request_id") or f"studio-local-{uuid.uuid4().hex[:8]}")
    thread_id = body.get("thread_id") or None

    def _start():
        aid = _sg_assistant_id()
        tid = thread_id or _sg_call("POST", "/threads", {})["thread_id"]
        run = _sg_call("POST", f"/threads/{tid}/runs",
                       {"assistant_id": aid,
                        "input": {"request_id": request_id,
                                  "messages": [{"role": "user", "content": message}]}},
                       timeout=30)
        return {"request_id": request_id, "thread_id": tid,
                "run_id": run.get("run_id"), "status": run.get("status", "unknown"),
                "observe_url": f"/observe/{request_id}"}

    try:
        return await asyncio.to_thread(_start)
    except Exception as e:
        return JSONResponse(
            {"error": f"studio run failed to start: {e} (is :2024 up? `bash deploy/vast/studio.sh`)"},
            status_code=503)


@app.get("/api/studio/result")
async def api_studio_result(thread_id: str, run_id: str, request_id: str = ""):
    """Poll a run: {status} while pending/running; full clipped state once done."""
    import asyncio

    def _poll():
        try:
            run = _sg_call("GET", f"/threads/{thread_id}/runs/{run_id}", timeout=15)
        except Exception as e:
            return {"status": "unknown", "error": str(e)[:200],
                    "thread_id": thread_id, "run_id": run_id}
        status = run.get("status", "unknown")
        out: dict = {"status": status, "thread_id": thread_id, "run_id": run_id,
                     "request_id": request_id, "observe_url": f"/observe/{request_id}"}
        if status not in ("pending", "running"):
            try:
                state = _sg_call("GET", f"/threads/{thread_id}/state", timeout=20)
                out["state"] = _clip_state(state.get("values") or {})
            except Exception as e:
                out["state_error"] = str(e)[:200]
        return out

    return await asyncio.to_thread(_poll)

@app.get("/api/public/traces")
async def traces():
    out=[]
    if TRACE_FILE.exists():
        for l in TRACE_FILE.read_text().strip().splitlines()[-100:]:
            try: out.append(json.loads(l))
            except: pass
    return {"data": out, "total": len(out)}

@app.post("/api/public/ingestion")
async def ingestion(request: Request):
    body = await request.json()
    # Langfuse SDK sends {batch: [{type, body:{id, name, ...}}]}
    ts = int(time.time()*1000)
    try:
        with TRACE_FILE.open("a", encoding="utf-8") as f:
            # store raw batch
            f.write(json.dumps({"ts": ts, "batch": body}, ensure_ascii=False) + "\n")
            # also store individual traces for easy view
            batch = body.get("batch", []) if isinstance(body, dict) else [body]
            for item in batch:
                f.write(json.dumps({"ts": ts, "item": item}, ensure_ascii=False) + "\n")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return {"success": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
