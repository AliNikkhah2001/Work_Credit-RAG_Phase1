# OpenWebUI RAG Filters & Actions — Agent Testing UI (Phase 2 & 4)

Three OpenWebUI Functions that connect the chat UI to the Work Credit RAG
observability stack (`:3000` tracing collector / `:3001` Langfuse v2).

| File | Kind | Purpose |
|------|------|---------|
| `rag_trace_capture.py` | **Filter** (Inlet → Request → Outlet) | Captures the full RAG pipeline payload at every turn and POSTs it to observability |
| `view_pipeline.py` | **Action** (button under each message) | Fetches and renders the 8-stage pipeline timeline for the message's `request_id` |
| `rate_with_comment.py` | **Action** (button under each message) | Rates a response (1–5 stars + comment + `#tags`) and POSTs an evaluation |

Single dependency: `pydantic` (pre-installed in OpenWebUI). Everything else
is stdlib (`urllib`, `re`, `json`, `time`) — **no `httpx`**.

---

## 1. What each function does

### 1.1 `rag_trace_capture.py` — Filter Function (Phase 2)

Runs on every chat turn that uses a model with the filter enabled.

- **Inlet** — extracts `body["messages"][-1]["content"]` as the original query,
  stores `time.monotonic()` in `__metadata__["_trace_start"]` and the query in
  `__metadata__["_trace_data"]`. Handles `__metadata__ is None` (direct API calls
  that bypass OpenWebUI's metadata injection).
- **Request** — after OpenWebUI injects RAG context, parses all
  `<source id="..." name="..." resource-id="...">…</source>` tags via
  `re.findall(r'<source[^>]*>(.*?)</source>', content, re.DOTALL)` across every
  message, plus captures `body["messages"][0]` when `role == "system"`.
  Idempotent — sets `_chunks_parsed` so re-entry during a tool loop is a no-op.
- **Outlet** — combines original query + chunks + system prompt + final assistant
  text (`messages[-1]` or `choices[0].message` or `content/response/output/text`
  fallbacks), computes `latency_ms` from `_trace_start`, and
  `POST {trace_endpoint}/api/observability/traces`.
  **Never raises** — the POST is wrapped in `try/except`; on failure the chat
  continues normally. Uses `urllib.request` with a 2 s timeout.

Valves:

```python
# Python code defaults to Docker service URL; configure to 127.0.0.1 for local/host
trace_endpoint: str = "http://rag-tracing-fallback:3000"  # Docker default (local host: http://127.0.0.1:3000)
capture_enabled: bool = True
log_to_console: bool = False
```

Toggle `capture_enabled` off to pause capture without detaching the filter.
`file_handler = False` so built-in RAG is not intercepted.

### 1.2 `view_pipeline.py` — Action Function (Phase 4)

Button labelled **View Pipeline** under every assistant message.

- Extracts `request_id` from all known body shapes:
  `metadata.request_id`, `request_id`, `chat_id`, `message.id`,
  `messages[*].metadata.request_id`, `audit.request_id`, `rag.request_id`.
- GETs in order (first 200 wins):
  `{endpoint}/api/observability/pipeline/{id}`
  `{endpoint}/api/observability/traces/{id}`
  `{endpoint}/api/observe/timeline/{id}`
  Handles envelope unwrapping (`{data: {...}}` and `{data: [...]}`).
- Returns a markdown timeline covering the 8 stages:
  `validate_input → guardrail_input → retrieve → rerank → build_context → guarded_generate → guardrail_output → format_response`.
  Shows spans, chunk previews (capped by `max_content_preview`), citation counts,
  per-stage timing if present, the context sent to Gemma, and links to the
  dashboard/timeline JSON.
- If no trace is found returns:
  `"No pipeline trace found for this request. The trace may not have been captured yet."`
  plus troubleshooting hints.

Implements **both `action` and `pipe`** for compatibility across OpenWebUI
versions that dispatch to either name.

Valves:

```python
# Python code defaults to Docker service URL; configure to 127.0.0.1 for local/host
observability_endpoint: str = "http://rag-tracing-fallback:3000"  # Docker default (local host: http://127.0.0.1:3000)
max_content_preview: int = 500
```

### 1.3 `rate_with_comment.py` — Action Function (Phase 4)

Button labelled **Rate Response** under every assistant message.

Because Action buttons cannot render interactive forms, the MVP uses a
chat-command pattern:

```
/rate 5 Great response! #helpful #accurate
/rate 3 Could be more detailed #needs-work
/rate 1 Hallucinated sources #inaccurate
```

- On invocation extracts `request_id`, `chat_id`, and the assistant message
  preview, then GETs any existing evaluation:
  `/api/observability/evaluations/{id}` or `?request_id=…`.
- If the current chat input already contains a `/rate` command
  (`/rate <1-5> [comment] [#tags…]`), parses it (`rating`, `comment`, `tags`)
  and `POST {endpoint}/api/observability/evaluations` with
  `{request_id, chat_id, rating, comment, tags, timestamp, user_id}`.
- Otherwise returns a markdown panel with the current evaluation (if any),
  a preview of the message, usage instructions with examples, and links to
  the pipeline trace / dashboard / recent traces.

Rating scale is capped by `rating_scale` valve (default 5 → `1–5`).

Implements `action` + `pipe` alias.

Valves:

```python
# Python code defaults to Docker service URL; configure to 127.0.0.1 for local/host
observability_endpoint: str = "http://rag-tracing-fallback:3000"  # Docker default (local host: http://127.0.0.1:3000)
rating_scale: int = 5
```

---

## 2. Installation (OpenWebUI Admin)

OpenWebUI must already be running (`:13000` in this repo: `open-webui serve`
with `OPENAI_API_BASE_URL=http://127.0.0.1:8100/v1`).

1. Open **Admin Panel → Functions** (or **Workspace → Functions** on older builds).
2. **Create New Function** → paste the contents of the desired file.
   - `rag_trace_capture.py` → Type **Filter**
   - `view_pipeline.py` → Type **Action**
   - `rate_with_comment.py` → Type **Action**
3. Save. OpenWebUI validates the `Filter` / `Action` class and calls `py_compile`.

### CLI equivalent (if using the OpenWebUI API)

```bash
# Example — upload filter via API (requires admin token)
curl -s http://127.0.0.1:13000/api/v1/functions/create \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d @- <<'JSON'
{
  "id": "rag_trace_capture",
  "name": "RAG Trace Capture",
  "meta": {"description": "Captures RAG pipeline data"},
  "content": "<paste rag_trace_capture.py here>"
}
JSON
```

### Verify

```bash
python3 -m py_compile components/openwebui-filters/rag_trace_capture.py
python3 -m py_compile components/openwebui-filters/view_pipeline.py
python3 -m py_compile components/openwebui-filters/rate_with_comment.py
```

---

## 3. Attach to a model (Functions toggle)

Filters/Actions are **per-model** in OpenWebUI.

1. **Workspace → Models** (or **Admin → Models**) → select the model that fronts
   the RAG stack (e.g. `gemma-4-31b` / `work-rag-agent` via `OPENAI_API_BASE_URL=http://127.0.0.1:8100/v1`).
2. **Settings → Functions** (or **Advanced → Functions**).
3. Toggle **ON**:
   - `RAG Trace Capture` (filter) — must be on for traces to exist.
   - `View Pipeline` (action) — button under each assistant reply.
   - `Rate Response` (action) — button under each assistant reply.
4. Save model settings. New chats with that model will now run the filter and
   show the action buttons. Existing chats need to be reloaded.

> **Order matters**: if you use multiple filters, keep `rag_trace_capture`
> early in the filter chain so it sees RAG-injected `<source>` tags produced
> by the built-in RAG filter.

---

## 4. API endpoints they communicate with

All three point at the **observability service** (code defaults to `http://rag-tracing-fallback:3000` for Docker container-to-container networking; use `http://127.0.0.1:3000` for local host testing with the fallback collector at `components/tracing/app.py`, or swap to `:3001` for the full Langfuse v2 UI).

| Endpoint | Method | Used by | Notes |
|----------|--------|---------|-------|
| `/api/observability/traces` | `POST` | `rag_trace_capture` (outlet) | Create trace. Body: `{request_id, query, chunks, system_prompt, response, latency_ms, timestamp, stages, metadata}`. 2 s timeout, fail-silent. |
| `/api/observability/pipeline/{id}` | `GET` | `view_pipeline` | Stage timeline (preferred). |
| `/api/observability/traces/{id}` | `GET` | `view_pipeline`, `rate_with_comment` | Single trace (fallback). |
| `/api/observability/evaluations` | `POST` | `rate_with_comment` | Create evaluation. Body: `{request_id, chat_id, rating, comment, tags, timestamp, user_id}`. |
| `/api/observability/evaluations/{id}` | `GET` | `rate_with_comment` | Fetch evaluation(s) for `request_id`. Also tries `?request_id=…`. |
| `/api/observe/timeline/{id}` | `GET` | `view_pipeline` (fallback) | Compatibility with current collector (`:3000`). |
| `/health` | `GET` | All (docs) | Liveness probe. |
| `/observe/{id}` | `GET` (browser) | Dashboard links in markdown output | HTML timeline. |
| `/observe` | `GET` (browser) | Dashboard links | Request list. |

Collector health:

```bash
curl -s http://127.0.0.1:3000/health | jq .
curl -s http://127.0.0.1:3000/api/observe/requests?limit=5 | jq .
curl -s http://127.0.0.1:3000/api/observe/timeline/<request_id> | jq .
```

For Langfuse v2 (`:3001`) replace the host and add auth from `/tmp/opencode/langfuse.env`:

```bash
set -a; . /tmp/opencode/langfuse.env; set +a
curl -s -u "$LANGFUSE_INIT_PROJECT_PUBLIC_KEY:$LANGFUSE_INIT_PROJECT_SECRET_KEY" \
  http://127.0.0.1:3001/api/public/traces?limit=5 | jq .
```

---

## 5. Valves configuration

Valves are edited in the Functions UI (each function card → **Settings/Valves**)
or via the API. No restart is needed.

### `rag_trace_capture`

| Valve | Default | Description |
|-------|---------|-------------|
| `trace_endpoint` | `http://rag-tracing-fallback:3000` | Collector base URL. Defaults to Docker service name `http://rag-tracing-fallback:3000`. For local/host environments or Vast host venv, set to `http://127.0.0.1:3000` (fallback) or `http://127.0.0.1:3001` (Langfuse v2). Trailing slash is stripped. |
| `capture_enabled` | `true` | Master toggle for capture (filter still runs but is a no-op when false). |
| `log_to_console` | `false` | Print trace lifecycle to the OpenWebUI server log (useful for debugging). |

### `view_pipeline`

| Valve | Default | Description |
|-------|---------|-------------|
| `observability_endpoint` | `http://rag-tracing-fallback:3000` | Base URL for pipeline/trace GETs (Docker default; use `http://127.0.0.1:3000` for local host). |
| `max_content_preview` | `500` | Max characters per chunk/stage preview in the rendered markdown. Increase for more context, decrease for compact cards. |

### `rate_with_comment`

| Valve | Default | Description |
|-------|---------|-------------|
| `observability_endpoint` | `http://rag-tracing-fallback:3000` | Base URL for evaluation GET/POST (Docker default; use `http://127.0.0.1:3000` for local host). |
| `rating_scale` | `5` | Max star rating. The `/rate` parser accepts `1–rating_scale`. Change to `10` for a 10-point scale. |

All URLs respect `http://` vs `https://` and optional non-standard ports.
If the observability service is behind an SSH tunnel (e.g. Vast
`ssh -L 3000:localhost:3000`), use the tunneled `http://127.0.0.1:3000`.

---

## 6. End-to-end smoke test

```bash
# 1. Collector is up
curl -s http://127.0.0.1:3000/health

# 2. Send a real RAG request (creates a trace if filter is attached)
curl -s http://127.0.0.1:8100/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"اعتبارسنجی چیست؟"}]}' \
  | jq -c '{finish:.choices[0].finish_reason, citations:(.rag.citations|length)}'

# 3. Collector received it (fallback path)
curl -s http://127.0.0.1:3000/api/observe/requests?limit=3 | jq .
curl -s http://127.0.0.1:3000/api/public/traces | jq '.data | length'

# 4. Observability traces API
curl -s http://127.0.0.1:3000/api/observability/traces | jq .
```

---

## 7. Troubleshooting

- **No trace found** from `View Pipeline` → the filter was not attached when the
  message was sent, or the collector was down (filter fails silent by design).
  Re-send the query after enabling the filter and confirming `curl /health`.
- **Action button not visible** → ensure the function Type is **Action** and
  it is toggled ON under the model's **Functions** settings; reload the chat.
- **`__metadata__ is None`** in logs → normal for direct API calls; only
  browser chats via OpenWebUI populate metadata.
- **Inside OpenWebUI the filter cannot reach `127.0.0.1:3000`** (Docker networking)
  → within Docker Compose, the default `http://rag-tracing-fallback:3000` connects
  directly to the tracing container. If running without Compose networking,
  set `trace_endpoint` to `http://host.docker.internal:3000` or the host's
  LAN IP, or run OpenWebUI with `--network host`.
