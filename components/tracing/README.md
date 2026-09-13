# Work RAG Tracing

Fallback trace collector and local observation UI for the Work Credit RAG platform.

> **Status:** ✅ **LIVE** on Vast.ai. Parent-owned (not a submodule). Serves on `:3000`.

## Responsibility

- Langfuse-compatible ingestion API (`POST /api/public/ingestion`)
- JSONL trace storage at `/tmp/langfuse_traces.jsonl`
- Local observation web UI: request list, timeline viewer, graph debugger
- Fallback when Langfuse v2 (:3001) unavailable

## Services

| Service | Port | Purpose |
|---------|------|---------|
| Collector | 3000 | `POST /api/public/ingestion`, `GET /api/public/traces`, `GET /api/public/health` |
| Observe UI | 3000 | `GET /observe` (request list), `GET /observe/{request_id}` (timeline) |
| Studio UI | 3000 | `GET /studio` (local graph debugger), `POST /api/studio/run`, `GET /api/studio/result` |

## API Endpoints

### Collector (Langfuse-compatible)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Collector health |
| `GET` | `/api/public/health` | Langfuse SDK health check |
| `POST` | `/api/public/ingestion` | Accept trace batches (Langfuse SDK format) |
| `GET` | `/api/public/traces` | Last 100 traces (JSON) |

### Observe (Request→Response Timeline)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/observe` | HTML page: recent requests with links |
| `GET` | `/observe/{request_id}` | HTML page: full pipeline timeline |
| `GET` | `/api/observe/requests` | JSON: recent requests list |
| `GET` | `/api/observe/timeline/{request_id}` | JSON: full timeline |

**Timeline includes:**
- Request input + metadata
- Per-node spans: `validate_input` → `query-rewrite` → `retrieve` → `build_context` → `guarded_generate` → `format_response`
- Response output + metadata (citations, latency, finish_reason)

### Studio (Local Graph Debugger)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/studio` | HTML page: run `rag` graph via :2024 API |
| `POST` | `/api/studio/run` | Start run: `{message, request_id, thread_id?}` |
| `GET` | `/api/studio/result` | Poll result: `?thread_id=...&run_id=...&request_id=...` |

**Run flow:** Creates thread → starts run → polls until `success`/`error` → returns clipped state + observe link

## Running

```bash
cd components/tracing
/tmp/orch-venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 3000
```

Or via parent startup: `bash deploy/vast/start.sh` (starts after guardrails)

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGFUSE_HOST` | `http://127.0.0.1:3001` | Upstream Langfuse v2 (for observe CLI) |
| `STUDIO_API` | `http://127.0.0.1:2024` | LangGraph Studio API |
| `TRACE_FILE` | `/tmp/langfuse_traces.jsonl` | JSONL storage path |

## Observe CLI

```bash
# List recent requests (reads from :3001 v2, fallback :3000, fallback JSONL)
python observe.py --list --limit 10

# Full timeline for request_id
python observe.py --request <request_id>
python observe.py --request <request_id> --json
python observe.py --request <request_id> --host http://127.0.0.1:3000  # force fallback
python observe.py --request <request_id> --file-only  # offline JSONL only
```

## Data Sources (Priority Order)

1. **Langfuse v2 (:3001)** — Live production traces, Postgres-backed, authenticated
2. **Fallback Collector (:3000)** — JSONL + ingestion API, no auth
3. **JSONL File** — `/tmp/langfuse_traces.jsonl` — Offline access

## Verification

```bash
# Collector health
curl -s http://127.0.0.1:3000/health
curl -s http://127.0.0.1:3000/api/public/health

# Observe UI
open http://127.0.0.1:3000/observe
open http://127.0.0.1:3000/studio

# API
curl -s http://127.0.0.1:3000/api/observe/requests?limit=5 | jq .
curl -s http://127.0.0.1:3000/api/observe/timeline/<request_id> | jq .

# Studio run
curl -s -X POST http://127.0.0.1:3000/api/studio/run \
  -H 'Content-Type: application/json' \
  -d '{"message":"سلام","request_id":"test-001"}' | jq .
# Poll:
curl -s "http://127.0.0.1:3000/api/studio/result?thread_id=...&run_id=...&request_id=test-001" | jq .
```

## Links

- [Parent README](../README.md#observability)
- [Architecture](../docs/architecture.md)
- [Langfuse v2 setup](../deploy/vast/langfuse-v2.sh)
- [Studio setup](../deploy/vast/studio.sh)