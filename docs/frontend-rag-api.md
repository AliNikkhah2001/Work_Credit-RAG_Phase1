# Dana RAG Agent — Frontend API

Base URL (orchestrator only):

| Env | URL |
|---|---|
| Local | `http://127.0.0.1:8100` |
| Stage | `http://127.0.0.1:18100` |

Headers on every call:

```
Authorization: Bearer sk-local-dev
X-Request-ID: <uuid>
Content-Type: application/json
```

Model: `ics-helper-agent`

---

## Endpoints

| Method | Path |
|---|---|
| `GET` | `/health` |
| `GET` | `/ready` |
| `GET` | `/v1/models` |
| `POST` | `/v1/chat/completions` |

---

## GET `/health`

**Response**

```json
{ "status": "ok" }
```

---

## GET `/ready`

**Response**

```json
{
  "status": "ready",
  "dependencies": [
    { "name": "kb", "status": "ready", "url": "…", "error": null }
  ]
}
```

---

## GET `/v1/models`

**Response**

```json
{
  "object": "list",
  "data": [
    {
      "id": "ics-helper-agent",
      "object": "model",
      "created": 0,
      "owned_by": "ics",
      "name": "دانا"
    }
  ]
}
```

---

## POST `/v1/chat/completions`

### Request

```json
{
  "model": "ics-helper-agent",
  "messages": [
    { "role": "user", "content": "رتبه اعتباری چیست؟" }
  ],
  "stream": true,
  "temperature": 0.0,
  "max_tokens": 1024,
  "session_id": null,
  "filter_path": null
}
```

`stream` defaults to `true`.

### Response (`stream: false`)

```json
{
  "id": "chatcmpl-…",
  "object": "chat.completion",
  "model": "ics-helper-agent",
  "choices": [
    {
      "index": 0,
      "message": { "role": "assistant", "content": "…" },
      "finish_reason": "stop"
    }
  ],
  "usage": null,
  "rag": {
    "request_id": "…",
    "citations": [
      {
        "chunk_id": "…",
        "document_id": "…",
        "title": "…",
        "heading": "…"
      }
    ],
    "supplemental": null,
    "follow_ups": ["…"],
    "applied_subspace": "general",
    "sticky_subspace": "general",
    "available_subspaces": null,
    "magic": [
      {
        "name": "CREDIT_SCORE_GAUGE",
        "params": {
          "score": 610,
          "min": 250,
          "max": 900,
          "model": "person",
          "variant": "ring",
          "band": "سبز",
          "code": "B",
          "codes": ["B1", "B2", "B3"],
          "bands": [],
          "color_mode": "stepped"
        }
      }
    ]
  },
  "audit": null
}
```

`finish_reason`: `stop` | `clarify` | `content_filter` | `length` | `error`

### Dana magic widgets (`rag.magic`) — post-hoc, outside the body

Widgets are computed **after** the model answer is final. They are **not** appended into `choices[].message.content`.

| Field | Meaning |
|---|---|
| `rag.magic` | Optional list of `{ "name": "TOKEN", "params": {…} }` |
| `content` | Plain Persian answer only — never contains `<<<MAGIC:…>>>` |

Frontend (Open WebUI / Dana): middleware reads `rag.magic` from the final SSE chunk (or non-stream body), persists `message.magic`, and emits socket `chat:message:magic`. Renderers glue widgets **beside** the text, not inside it. Legacy in-body `<<<MAGIC:…>>>` is still parsed as a fallback for old saved chats.

Emit gates (orchestrator): score gauges only when the turn has an explicit cheque (0–100) / credit (250–900) number, colour tag, named band, grade code, or layout keyword; shareholders / data-providers only for شرکت اعتبارسنجی ایران; clarify cards on `finish_reason=clarify`.

### Response (`stream: true`) — SSE

Media type: `text/event-stream`

```
data: {"id":"chatcmpl-…","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-…","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"اعتبارسنجی "},"finish_reason":null}]}

data: {"id":"chatcmpl-…","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"فرآیندی "},"finish_reason":null}]}

data: {"id":"chatcmpl-…","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"rag":{"request_id":"…","citations":[],"follow_ups":[],"magic":[{"name":"CREDIT_SCORE_GAUGE","params":{"score":610,"model":"person","variant":"ring"}}]}}

data: [DONE]
```

Lines starting with `:` are progress comments — ignore.  
Append every `choices[0].delta.content` (body only).  
Final chunk may include `rag` — read `rag.magic` here and render widgets out-of-band.  
End on `data: [DONE]`.

---

## Rating — `/rate`

Same endpoint. Last user message content:

```
/rate <1-5> [comment] [#tag …]
```

### Request

```json
{
  "model": "ics-helper-agent",
  "messages": [
    { "role": "user", "content": "/rate 5 پاسخ خوب بود #helpful" }
  ],
  "stream": false
}
```

Use the same `X-Request-ID` as the rated answer.

### Response

```json
{
  "id": "chatcmpl-…",
  "object": "chat.completion",
  "model": "ics-helper-agent",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Rating saved: ★★★★★ (5/5)\n> پاسخ خوب بود  Tags: #helpful\n\nView in dashboard: http://127.0.0.1:3000/dashboard/observability"
      },
      "finish_reason": "stop"
    }
  ],
  "rag": { "request_id": "…", "citations": [] },
  "audit": null
}
```

### Related commands (same endpoint)

```
/report inaccurate توضیح #bug
/truth متن پاسخ صحیح
```

Report categories: `inaccurate` | `incomplete` | `hallucination` | `wrong_source` | `off_topic` | `other`

---

## Test

```bash
curl -s http://127.0.0.1:8100/health

curl -s http://127.0.0.1:8100/v1/models

curl -s http://127.0.0.1:8100/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer sk-local-dev' \
  -H 'X-Request-ID: test-001' \
  -d '{"model":"ics-helper-agent","messages":[{"role":"user","content":"سلام"}],"stream":false}'

curl -N -s http://127.0.0.1:8100/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer sk-local-dev' \
  -H 'X-Request-ID: test-002' \
  -d '{"model":"ics-helper-agent","messages":[{"role":"user","content":"اعتبارسنجی چیست؟"}],"stream":true}'

curl -s http://127.0.0.1:8100/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer sk-local-dev' \
  -H 'X-Request-ID: test-001' \
  -d '{"model":"ics-helper-agent","messages":[{"role":"user","content":"/rate 5 #ok"}],"stream":false}'

# Score ask — body stays clean; widgets on rag.magic
curl -s http://127.0.0.1:8100/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer sk-local-dev' \
  -d '{"model":"ics-helper-agent","messages":[{"role":"user","content":"امتیاز ۶۱۰ حقیقی در چه رنگی است؟"}],"stream":false}' \
  | jq '{body_has_magic:(.choices[0].message.content|contains("<<<MAGIC:")), magic:.rag.magic}'
```
