"""Self-hosted Langfuse-compatible trace collector (host fallback, no Docker needed).
Implements Langfuse ingestion API + simple UI for Vast unprivileged host.
Stores traces to /tmp/langfuse_traces.jsonl and provides /api/public/health
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
import json, time, os
from pathlib import Path

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
    <pre>{json.dumps(traces, ensure_ascii=False, indent=2)[:8000]}</pre>
    </body></html>
    """
    return HTMLResponse(html)

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
