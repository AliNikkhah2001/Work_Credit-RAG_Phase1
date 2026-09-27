"""
View Pipeline — OpenWebUI Action Function (Phase 4)

Shows the full RAG pipeline trace for the current message.

Shows as a button under each assistant message. Clicking fetches the
trace from the observability service and returns a formatted markdown
timeline covering all 8 pipeline stages:

  1. validate_input  2. guardrail_input  3. retrieve       4. rerank
  5. build_context   6. guarded_generate 7. guardrail_output 8. format_response

Compatibility: implements BOTH `action` and `pipe` so it works across
OpenWebUI versions that dispatch to either entry point.

Uses only stdlib + pydantic (urllib, not httpx).
"""

from pydantic import BaseModel, Field
from typing import Optional
import json
import urllib.request
import urllib.parse
import urllib.error


PIPELINE_STAGES = [
    ("validate_input", "Validate Input"),
    ("guardrail_input", "Guardrail Input Check"),
    ("retrieve", "KB Retrieval (BM25 + Dense + RRF)"),
    ("rerank", "Cross-Encoder Rerank"),
    ("build_context", "Build Context"),
    ("guarded_generate", "Guarded Generate (Gemma)"),
    ("guardrail_output", "Guardrail Output Check"),
    ("format_response", "Format Response"),
]


class Action:
    """OpenWebUI Action — view RAG pipeline trace for a message."""

    class Valves(BaseModel):
        observability_endpoint: str = Field(
            default="http://rag-tracing-fallback:3000",
            description="Observability service endpoint (Docker: rag-tracing-fallback:3000, host: 127.0.0.1:3000)",
        )
        max_content_preview: int = Field(
            default=500,
            description="Max chars per chunk preview",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.name = "view_pipeline"

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _extract_request_id(self, body: dict) -> Optional[str]:
        """Extract request_id from all known locations in the action body.

        Priority per spec: body.metadata.request_id → body.request_id →
        body.chat_id → body.message.id (+ fallbacks for nested / audit).
        """
        if not isinstance(body, dict):
            return None

        # Spec priority 1: body.metadata.request_id
        meta = body.get("metadata")
        if isinstance(meta, dict):
            for key in ("request_id",):
                v = meta.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()

        # Spec priority 2: body.request_id
        v = body.get("request_id")
        if isinstance(v, str) and v.strip():
            return v.strip()

        # Spec priority 3: body.chat_id
        v = body.get("chat_id")
        if isinstance(v, str) and v.strip():
            return v.strip()

        # Spec priority 4: body.message.id (+ metadata fallbacks)
        msg = body.get("message")
        if isinstance(msg, dict):
            v = msg.get("id")
            if isinstance(v, str) and v.strip():
                return v.strip()
            # nested message metadata
            m2 = msg.get("metadata")
            if isinstance(m2, dict):
                v = m2.get("request_id")
                if isinstance(v, str) and v.strip():
                    return v.strip()

        # Fallbacks: broader search (keeps compatibility)
        if isinstance(meta, dict):
            for key in ("chat_id", "id", "session_id"):
                v = meta.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            inner = meta.get("metadata")
            if isinstance(inner, dict):
                v = inner.get("request_id")
                if isinstance(v, str) and v.strip():
                    return v.strip()
        # top-level id fallback
        v = body.get("id")
        if isinstance(v, str) and v.strip():
            return v.strip()

        # messages list — scan for any message with metadata.request_id
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

        # audit trail embedded in body (orchestrator response)
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

    def _fetch_trace(self, request_id: str) -> Optional[dict]:
        """Try multiple endpoint shapes and return the first successful JSON."""
        base = self.valves.observability_endpoint.rstrip("/")
        candidates = [
            f"{base}/api/observability/pipeline/{urllib.parse.quote(request_id)}",
            f"{base}/api/observability/traces/{urllib.parse.quote(request_id)}",
            f"{base}/api/observe/timeline/{urllib.parse.quote(request_id)}",
        ]
        for url in candidates:
            try:
                req = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        # Unwrap common envelopes {data: {...}} or direct dict
                        if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
                            # check if data.data looks like a trace
                            if "request_id" in data["data"] or "spans" in data["data"]:
                                return data["data"]
                        return data
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue
                continue
            except Exception:
                continue
        return None

    def _format_timeline(self, trace: dict, request_id: str) -> str:
        """Return markdown timeline covering all 8 stages."""
        lines: list[str] = []
        max_preview = self.valves.max_content_preview

        lines.append(f"# RAG Pipeline Trace — `{request_id}`")
        lines.append("")

        # Top-level summary
        query = trace.get("query") or trace.get("original_query") or trace.get("input") or ""
        if isinstance(query, dict):
            query = query.get("content", str(query))
        query = str(query)[:1000]
        if query:
            lines.append(f"**Query:** {query}")
            lines.append("")

        latency = trace.get("latency_ms")
        if latency is not None:
            lines.append(f"**Latency:** {latency} ms")

        # Status fields that may be present in orchestrator audit
        model = trace.get("model", "")
        if model:
            lines.append(f"**Model:** `{model}`")

        retrieval_method = trace.get("retrieval_method", "")
        if retrieval_method:
            lines.append(f"**Retrieval:** {retrieval_method}")

        if latency is not None or model:
            lines.append("")

        # Stage timing if available
        stage_timing = trace.get("stage_timing_ms")
        if isinstance(stage_timing, dict) and stage_timing:
            lines.append("**Stage timing (ms):**")
            for k, v in stage_timing.items():
                lines.append(f"  - {k}: {v} ms")
            lines.append("")

        # Chunks / citations
        chunks = trace.get("chunks") or trace.get("retrieved_chunks") or trace.get("final_results") or []
        if not isinstance(chunks, list):
            chunks = []
        citations = trace.get("citations", [])
        if not isinstance(citations, list):
            citations = []

        lines.append(f"**Chunks retrieved:** {len(chunks)} | **Citations:** {len(citations)}")
        lines.append("")

        # Stage-by-stage timeline
        lines.append("---")
        lines.append("## Pipeline Stages")
        lines.append("")

        # Build a lookup for trace-provided stage data
        spans = trace.get("spans", [])
        span_map: dict = {}
        if isinstance(spans, list):
            for s in spans:
                if isinstance(s, dict) and "span" in s:
                    span_map[str(s["span"])] = s
        # Also check trace has per-stage keys directly
        for idx, (stage_key, stage_label) in enumerate(PIPELINE_STAGES, start=1):
            lines.append(f"### {idx}. {stage_label} (`{stage_key}`)")
            span = span_map.get(stage_key)
            stage_data = trace.get(stage_key)

            if span is not None:
                inp = span.get("input")
                out = span.get("output")
                if inp is not None:
                    preview = str(inp)[:max_preview]
                    lines.append(f"- **Input:** `{preview}`" + ("…" if len(str(inp)) > max_preview else ""))
                if out is not None:
                    preview = str(out)[:max_preview]
                    lines.append(f"- **Output:** `{preview}`" + ("…" if len(str(out)) > max_preview else ""))
                if inp is None and out is None:
                    lines.append("- _No span I/O recorded_")
            elif stage_data is not None:
                preview = str(stage_data)[:max_preview]
                lines.append(f"- `{preview}`" + ("…" if len(str(stage_data)) > max_preview else ""))
            else:
                # Provide contextual info from top-level fields for stages that map there
                if stage_key == "retrieve" and chunks:
                    lines.append(f"- Retrieved {len(chunks)} chunk(s); showing top {min(3, len(chunks))}:")
                    for c in chunks[:3]:
                        if isinstance(c, dict):
                            cid = c.get("chunk_id", c.get("id", ""))[:40]
                            title = c.get("title", c.get("name", ""))[:80]
                            content = str(c.get("content", c.get("content_preview", "")))[:max_preview]
                            score = c.get("score", c.get("rerank_score", ""))
                            lines.append(f"  - `{cid}` **{title}** (score={score}): {content}…")
                        else:
                            lines.append(f"  - {str(c)[:max_preview]}…")
                elif stage_key == "guarded_generate":
                    raw = trace.get("raw_model_output", "")
                    if raw:
                        lines.append(f"- Raw model output: {str(raw)[:max_preview]}…")
                    else:
                        lines.append("- _No stage detail (trace may be lightweight)_")
                elif stage_key in ("guardrail_input", "guardrail_output"):
                    sig_key = "guardrail_input_signals" if stage_key == "guardrail_input" else "guardrail_output_signals"
                    signals = trace.get(sig_key, [])
                    decision = trace.get("guardrail_input" if stage_key == "guardrail_input" else "guardrail_output")
                    if isinstance(decision, dict):
                        lines.append(f"  - Decision: allowed={decision.get('allowed')} action={decision.get('action')} policy={decision.get('policy_version','')}")
                    if signals:
                        lines.append(f"  - Signals: {str(signals)[:max_preview]}")
                    if not signals and not isinstance(decision, dict):
                        lines.append("- _No guardrail detail_")
                elif stage_key == "format_response":
                    final = trace.get("final_answer") or trace.get("response") or trace.get("output") or ""
                    if final:
                        lines.append(f"- Final answer: {str(final)[:max_preview]}…")
                    else:
                        lines.append("- _No formatted response recorded_")
                else:
                    lines.append("- _No detail recorded for this stage_")
            lines.append("")

        # Context sent to Gemma
        ctx = trace.get("context_sent_to_gemma") or trace.get("context_preview") or trace.get("system_prompt", "")
        if ctx:
            lines.append("---")
            lines.append("**Context sent to Gemma (preview):**")
            lines.append(f"```\n{str(ctx)[:2000]}\n```")
            lines.append("")

        # Dashboard link
        base = self.valves.observability_endpoint.rstrip("/")
        lines.append("---")
        lines.append(f"[Open full trace in Observability Dashboard]({base}/observe/{urllib.parse.quote(request_id)})")
        lines.append(f"[Timeline JSON]({base}/api/observe/timeline/{urllib.parse.quote(request_id)})")

        return "\n".join(lines)

    def _no_trace_message(self, request_id: Optional[str]) -> str:
        rid = f"`{request_id}`" if request_id else "(no request_id found in message)"
        base = self.valves.observability_endpoint.rstrip("/")
        return (
            f"No pipeline trace found for this request. The trace may not have been captured yet.\n\n"
            f"Request ID searched: {rid}\n\n"
            f"Possible reasons:\n"
            f"- The RAG Trace Capture filter is not attached to the model\n"
            f"- The tracing collector at `{base}` is unreachable\n"
            f"- The message was sent before tracing was enabled\n\n"
            f"Try:\n"
            f"- Check that the filter `rag_trace_capture` is enabled for the model (Admin → Models → Functions)\n"
            f"- Verify the collector health: `curl {base}/health`\n"
            f"- View recent traces: [{base}/observe]({base}/observe)\n"
        )

    # ------------------------------------------------------------------
    # OpenWebUI entry points — implement BOTH for version compatibility
    # ------------------------------------------------------------------
    async def action(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__=None,
        **kwargs,
    ) -> Optional[str]:
        """Fetch and render the pipeline timeline for the current message."""
        try:
            request_id = self._extract_request_id(body)

            # Also check kwargs for request_id passed differently
            if not request_id:
                for k in ("request_id", "chat_id", "id"):
                    v = kwargs.get(k)
                    if isinstance(v, str) and v.strip():
                        request_id = v.strip()
                        break

            if not request_id:
                msg = self._no_trace_message(None)
                if __event_emitter__ is not None:
                    try:
                        emitter = __event_emitter__
                        if callable(getattr(emitter, "__call__", None)):
                            await emitter({"type": "status", "data": {"description": "No request_id in message", "done": True}})
                    except Exception:
                        pass
                return msg

            trace = self._fetch_trace(request_id)
            if trace is None or (isinstance(trace, dict) and trace.get("error")):
                # Distinguish "error: no trace" from real trace with error field
                if isinstance(trace, dict) and "error" in trace and len(trace) == 1:
                    return self._no_trace_message(request_id)
                if trace is None:
                    return self._no_trace_message(request_id)

            return self._format_timeline(trace, request_id)

        except Exception as e:
            return f"Error fetching pipeline trace: {e}\n\nEndpoint: `{self.valves.observability_endpoint}`"

    async def pipe(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__=None,
        **kwargs,
    ) -> Optional[str]:
        """Alias for `action` — OpenWebUI ≤0.5 dispatches to `pipe` for actions."""
        return await self.action(body, __user__, __event_emitter__, **kwargs)
