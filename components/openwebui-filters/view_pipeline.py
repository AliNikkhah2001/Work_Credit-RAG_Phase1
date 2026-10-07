"""
Show Retrieved Content + Full Pipeline — OpenWebUI Action Function (ICS helper)

> NOTE: The orchestrator should also handle /report at api.py:chat_completions
> (like the existing /rate handler) — add it there if missing, otherwise this
> action will handle it alone.

Dumps the retrieved KB chunks that were used for the current assistant
response, plus pipeline stage timing and citations.

- Extracts request_id with priority: metadata.request_id -> request_id ->
  chat_id -> message.id -> audit.request_id -> rag.request_id -> id
  (falls back to chat_id if no request_id found).
- GETs {base}/api/observability/traces/{request_id} and
       {base}/api/observability/pipeline/{request_id} (tries both, merges).
- Renders each retrieved chunk as:
    ### Chunk N — Title: ... Heading: ... [BOTH] score: 0.82
    Content: first 600 chars
- Also shows stage_timing table and citations when pipeline is available.
- Links to /dashboard/observability/pipeline/{id} and /api/observability/traces/{id}.

Only stdlib + pydantic — uses urllib.request (no httpx).
"""

from pydantic import BaseModel, Field
from typing import Optional
import json
import urllib.request
import urllib.parse
import urllib.error


class Action:
    """OpenWebUI Action — show retrieved KB chunks + pipeline for a message."""

    class Valves(BaseModel):
        observability_endpoint: str = Field(
            default="http://rag-tracing-fallback:3000",
            description="Observability service endpoint (Docker: rag-tracing-fallback:3000, host: 127.0.0.1:3000)",
        )

    def __init__(self):
        self.valves = self.Valves()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _extract_request_id(self, body: dict) -> Optional[str]:
        if not isinstance(body, dict):
            return None
        meta = body.get("metadata")
        if isinstance(meta, dict):
            v = meta.get("request_id")
            if isinstance(v, str) and v.strip():
                return v.strip()
        v = body.get("request_id")
        if isinstance(v, str) and v.strip():
            return v.strip()
        v = body.get("chat_id")
        if isinstance(v, str) and v.strip():
            return v.strip()
        msg = body.get("message")
        if isinstance(msg, dict):
            v = msg.get("id")
            if isinstance(v, str) and v.strip():
                return v.strip()
            m2 = msg.get("metadata")
            if isinstance(m2, dict):
                v = m2.get("request_id")
                if isinstance(v, str) and v.strip():
                    return v.strip()
        if isinstance(meta, dict):
            for key in ("chat_id", "id", "session_id"):
                vv = meta.get(key)
                if isinstance(vv, str) and vv.strip():
                    return vv.strip()
            inner = meta.get("metadata")
            if isinstance(inner, dict):
                v = inner.get("request_id")
                if isinstance(v, str) and v.strip():
                    return v.strip()
        v = body.get("id")
        if isinstance(v, str) and v.strip():
            return v.strip()
        messages = body.get("messages")
        if isinstance(messages, list):
            for m in messages:
                if not isinstance(m, dict):
                    continue
                mmeta = m.get("metadata")
                if isinstance(mmeta, dict):
                    v = mmeta.get("request_id")
                    if isinstance(v, str) and v.strip():
                        return v.strip()
        audit = body.get("audit")
        if isinstance(audit, dict):
            v = audit.get("request_id")
            if isinstance(v, str) and v.strip():
                return v.strip()
        rag = body.get("rag")
        if isinstance(rag, dict):
            v = rag.get("request_id")
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    def _extract_chat_id(self, body: dict) -> Optional[str]:
        if not isinstance(body, dict):
            return None
        v = body.get("chat_id")
        if isinstance(v, str) and v.strip():
            return v.strip()
        meta = body.get("metadata")
        if isinstance(meta, dict):
            v = meta.get("chat_id")
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    def _fetch_json(self, url: str) -> Optional[dict]:
        try:
            req = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            return None
        except Exception:
            return None
        return None

    def _fetch_trace_and_pipeline(self, request_id: str) -> tuple[Optional[dict], Optional[dict]]:
        """GET traces/{id} and pipeline/{id}, return (trace, pipeline)."""
        base = self.valves.observability_endpoint.rstrip("/")
        qid = urllib.parse.quote(request_id)
        # trace endpoint (SQLite traces)
        trace = self._fetch_json(f"{base}/api/observability/traces/{qid}")
        if isinstance(trace, dict) and "error" in trace and len(trace) <= 2:
            # error envelope with no real data
            trace = None
        # pipeline endpoint (trace + observer timeline merged)
        pipeline = self._fetch_json(f"{base}/api/observability/pipeline/{qid}")
        if isinstance(pipeline, dict) and "error" in pipeline and len(pipeline) <= 2:
            pipeline = None
        return trace, pipeline

    def _unwrap_chunks(self, trace: Optional[dict], pipeline: Optional[dict]) -> list:
        """Return retrieved_chunks list from either payload."""
        for src in (pipeline, trace):
            if not isinstance(src, dict):
                continue
            # direct retrieved_chunks
            rc = src.get("retrieved_chunks")
            if isinstance(rc, list) and rc:
                return rc
            # alternative keys
            for k in ("chunks", "final_results", "retrieved", "sources"):
                v = src.get(k)
                if isinstance(v, list) and v:
                    return v
            # nested timeline
            tl = src.get("timeline")
            if isinstance(tl, dict):
                for k in ("retrieved_chunks", "chunks"):
                    v = tl.get(k)
                    if isinstance(v, list) and v:
                        return v
        return []

    def _chunk_title(self, c: dict) -> str:
        for k in ("title", "name", "source", "document_title", "doc_title"):
            v = c.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()[:120]
        return c.get("id", c.get("chunk_id", c.get("resource_id", "")))[:60] or "(no title)"

    def _chunk_heading(self, c: dict) -> str:
        for k in ("heading", "section", "header", "subtitle"):
            v = c.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()[:120]
        return ""

    def _chunk_score(self, c: dict) -> str:
        for k in ("score", "rerank_score", "similarity", "distance", "rank_score"):
            v = c.get(k)
            if isinstance(v, (int, float)):
                return f"{v:.4f}" if isinstance(v, float) else str(v)
            if isinstance(v, str) and v.strip():
                return v.strip()[:20]
        return ""

    def _chunk_content(self, c: dict) -> str:
        for k in ("content", "content_preview", "text", "body", "chunk_content"):
            v = c.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        # fallback: dump dict
        return json.dumps(c, ensure_ascii=False)[:1000]

    def _render(self, request_id: str, chat_id: Optional[str], trace: Optional[dict], pipeline: Optional[dict]) -> str:
        base = self.valves.observability_endpoint.rstrip("/")
        dash = base.replace("rag-tracing-fallback", "127.0.0.1")
        qid = urllib.parse.quote(request_id)
        lines: list[str] = []

        lines.append(f"# Retrieved Content — `{request_id}`")
        if chat_id and chat_id != request_id:
            lines.append(f"**Chat ID:** `{chat_id}`")
        lines.append("")

        # Determine chunks
        chunks = self._unwrap_chunks(trace, pipeline)
        # Also collect citations
        citations: list = []
        for src in (pipeline, trace):
            if isinstance(src, dict) and isinstance(src.get("citations"), list):
                citations = src["citations"]
                break
        # query / latency / model from either payload
        query = ""
        for src in (pipeline, trace):
            if isinstance(src, dict):
                q = src.get("user_query") or src.get("query") or src.get("original_query") or src.get("input") or ""
                if isinstance(q, dict):
                    q = q.get("content", str(q))
                if isinstance(q, str) and q.strip():
                    query = q.strip()[:800]
                    break
        latency = None
        for src in (pipeline, trace):
            if isinstance(src, dict) and src.get("latency_ms") is not None:
                latency = src["latency_ms"]
                break
        model = ""
        for src in (pipeline, trace):
            if isinstance(src, dict) and isinstance(src.get("model"), str) and src["model"].strip():
                model = src["model"].strip()
                break

        if query:
            lines.append(f"**Query:** {query}")
            lines.append("")
        if model:
            lines.append(f"**Model:** `{model}`")
        if latency is not None:
            lines.append(f"**Latency:** {latency} ms")
        if model or latency is not None:
            lines.append("")

        # ---- Retrieved chunks dump ----
        if chunks:
            lines.append(f"**Retrieved chunks:** {len(chunks)} | **Citations:** {len(citations)}")
            lines.append("")
            lines.append("---")
            lines.append("## Retrieved KB chunks (full dump)")
            lines.append("")
            for idx, c in enumerate(chunks, start=1):
                if not isinstance(c, dict):
                    lines.append(f"### Chunk {idx}")
                    lines.append(f"```\n{str(c)[:600]}\n```")
                    lines.append("")
                    continue
                title = self._chunk_title(c)
                heading = self._chunk_heading(c)
                score = self._chunk_score(c)
                # retrieval method hint
                method = c.get("retrieval_method") or c.get("method") or c.get("source_method") or ""
                if not method:
                    # top-level
                    for src in (pipeline, trace):
                        if isinstance(src, dict) and src.get("retrieval_method"):
                            method = src["retrieval_method"]
                            break
                heading_part = f" Heading: `{heading}`" if heading else ""
                method_part = f" [{method}]" if method else ""
                score_part = f" score: {score}" if score else ""
                lines.append(f"### Chunk {idx} — Title: `{title}`{heading_part}{method_part}{score_part}")
                content = self._chunk_content(c)
                snippet = content[:600]
                lines.append("")
                lines.append(f"```\n{snippet}\n```")
                if len(content) > 600:
                    lines.append(f"_… ({len(content)} chars total, showing first 600)_")
                # optional metadata row
                meta_bits: list[str] = []
                for k in ("id", "chunk_id", "resource_id", "doc_id", "source_id"):
                    v = c.get(k)
                    if isinstance(v, str) and v.strip():
                        meta_bits.append(f"{k}={v[:40]}")
                        break
                if meta_bits:
                    lines.append(f"<sub>{' · '.join(meta_bits)}</sub>")
                lines.append("")
        else:
            lines.append("No retrieved content found for this request (maybe not a RAG turn). Check /observe or the knowledge base.")
            lines.append("")
            # still show trace/pipeline raw hint if present
            if trace is not None or pipeline is not None:
                lines.append("_Trace exists but contains no `retrieved_chunks`._")
                lines.append("")
            lines.append(f"- Check recent: [{dash}/observe]({dash}/observe)")
            lines.append(f"- KB health: `curl {dash.replace(':3000', ':8000')}/health`")

        # ---- Stage timing + citations from pipeline ----
        # stage_timing may be in trace, pipeline, or timeline
        stage_timing = None
        for src in (pipeline, trace):
            if isinstance(src, dict) and isinstance(src.get("stage_timing"), dict) and src["stage_timing"]:
                stage_timing = src["stage_timing"]
                break
            tl = src.get("timeline") if isinstance(src, dict) else None
            if isinstance(tl, dict) and isinstance(tl.get("stage_timing"), dict) and tl["stage_timing"]:
                stage_timing = tl["stage_timing"]
                break
        if isinstance(stage_timing, dict) and stage_timing:
            lines.append("---")
            lines.append("## Stage timing (ms)")
            lines.append("")
            lines.append("| Stage | ms |")
            lines.append("|-------|----|")
            for k, v in stage_timing.items():
                lines.append(f"| `{k}` | {v} |")
            lines.append("")

        if citations:
            lines.append("---")
            lines.append(f"## Citations ({len(citations)})")
            lines.append("")
            for i, cit in enumerate(citations[:10], start=1):
                if isinstance(cit, dict):
                    title = cit.get("title") or cit.get("name") or cit.get("id", "")[:60]
                    snippet = (cit.get("content_preview") or cit.get("content") or cit.get("snippet") or "")[:300]
                    lines.append(f"{i}. **{title}** — {snippet}")
                else:
                    lines.append(f"{i}. {str(cit)[:300]}")
            if len(citations) > 10:
                lines.append(f"_… and {len(citations) - 10} more_")
            lines.append("")

        # context preview
        ctx = ""
        for src in (pipeline, trace):
            if isinstance(src, dict):
                for k in ("context_preview", "context_sent_to_gemma", "system_prompt"):
                    v = src.get(k)
                    if isinstance(v, str) and v.strip():
                        ctx = v.strip()[:2000]
                        break
                if ctx:
                    break
        if ctx:
            lines.append("---")
            lines.append("**Context sent to Gemma (preview):**")
            lines.append(f"```\n{ctx}\n```")
            lines.append("")

        # links
        lines.append("---")
        lines.append(f"[Pipeline JSON]({dash}/api/observability/pipeline/{qid}) · [Trace JSON]({dash}/api/observability/traces/{qid}) · [Dashboard]({dash}/dashboard/observability) · [Observer]({dash}/observe/{qid}) · [Timeline JSON]({dash}/api/observe/timeline/{qid})")
        lines.append("")
        lines.append(f"<sub>ICS helper agent only (NOT arena) — observability: `{base}`</sub>")
        return "\n".join(lines)

    def _no_trace_message(self, request_id: Optional[str], chat_id: Optional[str]) -> str:
        rid = f"`{request_id}`" if request_id else "(no request_id found in message)"
        cid = f"`{chat_id}`" if chat_id else "(none)"
        base = self.valves.observability_endpoint.rstrip("/")
        dash = base.replace("rag-tracing-fallback", "127.0.0.1")
        return (
            f"# Retrieved Content — no data\n\n"
            f"No retrieved content found for this request (maybe not a RAG turn). Check /observe or the knowledge base.\n\n"
            f"- **Request ID searched:** {rid}\n"
            f"- **Chat ID fallback:** {cid}\n\n"
            f"**Possible reasons:**\n"
            f"- The message was not a RAG turn (no KB retrieval)\n"
            f"- The RAG Trace Capture filter is not attached to the model\n"
            f"- The tracing collector at `{base}` is unreachable\n"
            f"- The message was sent before tracing was enabled\n\n"
            f"**Try:**\n"
            f"- `curl {base}/health`\n"
            f"- [Observer — recent requests]({dash}/observe)\n"
            f"- [Dashboard]({dash}/dashboard/observability)\n"
            f"- `curl {dash}/api/observe/requests?limit=5`\n"
        )

    # ------------------------------------------------------------------
    # OpenWebUI entry points
    # ------------------------------------------------------------------
    async def action(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__=None,
        **kwargs,
    ) -> str:
        """Fetch and dump retrieved chunks + pipeline for the current message."""
        try:
            request_id = self._extract_request_id(body)
            chat_id = self._extract_chat_id(body)
            fallback_id = chat_id if chat_id and chat_id != request_id else None

            # allow kwargs override
            if not request_id:
                for k in ("request_id", "chat_id", "id"):
                    v = kwargs.get(k)
                    if isinstance(v, str) and v.strip():
                        request_id = v.strip()
                        break

            if not request_id:
                if __event_emitter__ is not None:
                    try:
                        emitter = __event_emitter__
                        if callable(getattr(emitter, "__call__", None)):
                            await emitter({"type": "status", "data": {"description": "No request_id in message", "done": True}})
                    except Exception:
                        pass
                return self._no_trace_message(None, chat_id)

            trace, pipeline = self._fetch_trace_and_pipeline(request_id)

            # fallback: try chat_id if request_id trace not found
            if trace is None and pipeline is None and fallback_id:
                t2, p2 = self._fetch_trace_and_pipeline(fallback_id)
                if t2 is not None or p2 is not None:
                    trace, pipeline = t2, p2
                    request_id = fallback_id

            if trace is None and pipeline is None:
                return self._no_trace_message(request_id, chat_id)

            if __event_emitter__ is not None:
                try:
                    emitter = __event_emitter__
                    if callable(getattr(emitter, "__call__", None)):
                        await emitter({"type": "status", "data": {"description": "Retrieved content ready", "done": True}})
                except Exception:
                    pass

            return self._render(request_id, chat_id, trace, pipeline)

        except Exception as e:
            return f"Error fetching retrieved content: {e}\n\nEndpoint: `{self.valves.observability_endpoint}`"

    async def pipe(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__=None,
        **kwargs,
    ) -> str:
        """Alias for `action` — OpenWebUI <=0.5 dispatches to `pipe` for actions."""
        return await self.action(body, __user__, __event_emitter__, **kwargs)
