"""
RAG Trace Capture — OpenWebUI Filter Function (Phase 2)

Captures full RAG pipeline data at three lifecycle stages:

  inlet   — original user query + monotonic start time
  request — injected <source> chunks + system prompt (RAG context)
  outlet  — final assistant response + latency → POST to observability

Fail-silent: if observability endpoint is unreachable the chat is never
broken. Uses only stdlib + pydantic so it runs inside the OpenWebUI
filter sandbox (no httpx).

Install: Admin Panel → Functions → Create New Function → paste this file.
Attach to model via Model settings → Functions.
Valves: trace_endpoint, capture_enabled, log_to_console
"""

from pydantic import BaseModel, Field
from typing import Optional
import time
import json
import re
import urllib.request
import urllib.error


# Matches <source ...>chunk content</source> across all RAG-injected messages
_SOURCE_RE = re.compile(r"<source[^>]*>(.*?)</source>", re.DOTALL)
# Attribute extractors for <source id="..." name="..." resource-id="...">
_ATTR_RE = re.compile(r'(\w[\w-]*)\s*=\s*"([^"]*)"')

# 8-stage pipeline labels used downstream by the observer
PIPELINE_STAGES = [
    "validate_input",
    "guardrail_input",
    "retrieve",
    "rerank",
    "build_context",
    "guarded_generate",
    "guardrail_output",
    "format_response",
]


class Filter:
    """OpenWebUI Filter — captures RAG trace across inlet/request/outlet."""

    class Valves(BaseModel):
        trace_endpoint: str = Field(
            default="http://rag-tracing-fallback:3000",
            description="Observability service endpoint (tracing collector). Inside Docker use rag-tracing-fallback:3000, on host use 127.0.0.1:3000",
        )
        capture_enabled: bool = Field(
            default=True,
            description="Enable trace capture",
        )
        log_to_console: bool = Field(
            default=False,
            description="Also log to console",
        )

    def __init__(self):
        self.valves = self.Valves()
        # OpenWebUI convention: Filters may expose toggle / file_handler
        # For this filter we want built-in RAG to run, so we do NOT use file_handler.
        self.toggle = True
        self.file_handler = False  # do not intercept file uploads

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _log(self, msg: str) -> None:
        if self.valves.log_to_console:
            print(f"[rag_trace_capture] {msg}")

    def _ensure_trace_data(self, metadata: Optional[dict]) -> Optional[dict]:
        """Return metadata['_trace_data'] dict, creating it if needed.
        Returns None if metadata itself is None (direct API calls)."""
        if metadata is None:
            return None
        if "_trace_data" not in metadata:
            metadata["_trace_data"] = {}
        return metadata["_trace_data"]

    def _parse_source_chunks(self, content: str) -> list:
        """Parse all <source> tags in a single message content string.

        Returns list of {id, name, resource_id, content_preview, content}
        """
        chunks = []
        # Find full <source ...>header</source> with attributes
        # We iterate over raw header + inner content separately
        header_re = re.compile(r"<source\s*([^>]*)>(.*?)</source>", re.DOTALL)
        for m in header_re.finditer(content):
            header_raw = m.group(1) or ""
            inner = m.group(2) or ""
            attrs = dict(_ATTR_RE.findall(header_raw))
            chunks.append(
                {
                    "id": attrs.get("id", ""),
                    "name": attrs.get("name", ""),
                    "resource_id": attrs.get("resource-id", attrs.get("resource_id", "")),
                    "content": inner.strip(),
                    "content_preview": inner.strip()[:500],
                }
            )
        # Fallback: if header_re found nothing but _SOURCE_RE matches,
        # capture content without attrs
        if not chunks:
            for inner in _SOURCE_RE.findall(content):
                chunks.append(
                    {
                        "id": "",
                        "name": "",
                        "resource_id": "",
                        "content": inner.strip(),
                        "content_preview": inner.strip()[:500],
                    }
                )
        return chunks

    def _post_trace(self, payload: dict) -> None:
        """POST payload to {trace_endpoint}/api/observability/traces — fail silently."""
        if not self.valves.capture_enabled:
            return
        url = self.valves.trace_endpoint.rstrip("/") + "/api/observability/traces"
        try:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            # Short timeout so chat is not delayed if collector is down
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                self._log(f"trace POST {resp.status} to {url}")
        except Exception as e:
            # NEVER break the chat — log and swallow
            self._log(f"trace POST failed ({url}): {e}")

    # ------------------------------------------------------------------
    # OpenWebUI lifecycle
    # ------------------------------------------------------------------
    # /rate command: /rate 5 comment text #tag1 #tag2
    _RATE_RE = re.compile(
        r"^\s*/rate\s+([1-5])\s*(.*?)\s*(#[\w-]+(?:\s+#[\w-]+)*)?\s*$",
        re.IGNORECASE | re.DOTALL,
    )

    def _handle_rate_command(
        self,
        text: str,
        chat_id: Optional[str],
        user_id: Optional[str],
    ) -> Optional[str]:
        """If text is a /rate command, save evaluation and return confirmation.

        Returns confirmation string if handled, None if not a /rate command.
        Uses chat_id as request_id fallback when no dedicated trace exists.
        """
        m = self._RATE_RE.match(text.strip())
        if not m:
            return None
        rating = int(m.group(1))
        comment = (m.group(2) or "").strip()
        tags_raw = (m.group(3) or "").strip()
        tags = re.findall(r"#([\w-]+)", tags_raw) if tags_raw else []
        # chat_id is the best correlation key — the last assistant turn in this chat
        request_id = chat_id or f"rate-{int(time.time())}"
        payload = {
            "request_id": request_id,
            "chat_id": chat_id,
            "rating": rating,
            "comment": comment,
            "tags": tags,
            "user_id": user_id,
            "timestamp": time.time(),
        }
        ok, msg = self._post_evaluation(payload)
        stars = "★" * rating + "☆" * (5 - rating)
        if ok:
            tag_str = f"  Tags: {', '.join('#'+t for t in tags)}" if tags else ""
            cmt_str = f"\n> {comment}" if comment else ""
            return (
                f"Rating saved: {stars} ({rating}/5){cmt_str}{tag_str}\n\n"
                f"View it in the dashboard: {self.valves.trace_endpoint.rstrip('/')}/dashboard/observability"
            )
        return f"Failed to save rating ({rating}/5): {msg[:200]}"

    def _post_evaluation(self, payload: dict) -> tuple[bool, str]:
        """POST evaluation — returns (ok, message). Fail-silent for caller."""
        url = self.valves.trace_endpoint.rstrip("/") + "/api/observability/evaluations"
        try:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url, data=data, method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return True, resp.read().decode("utf-8")[:300]
        except urllib.error.HTTPError as e:
            try:
                err = e.read().decode("utf-8")[:200]
            except Exception:
                err = str(e)
            return False, f"HTTP {e.code}: {err}"
        except Exception as e:
            return False, str(e)[:200]

    async def inlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
        __event_emitter__=None,
        **kwargs,
    ) -> dict:
        """Capture original user query and start monotonic timer.

        Also intercepts /rate commands: when the user types
          /rate 5 Great response! #helpful
        the filter saves the evaluation via POST and replaces the message
        content with a confirmation so the LLM is not called.

        Stores:
          __metadata__["_trace_start"]  — float (time.monotonic)
          __metadata__["_trace_data"]   — dict with original_query, user, timestamp
        """
        try:
            if not self.valves.capture_enabled:
                return body

            # --- /rate command interception (before normal tracing) ---
            messages = body.get("messages", []) if isinstance(body, dict) else []
            if messages:
                last = messages[-1]
                if isinstance(last, dict) and last.get("role") == "user":
                    text = str(last.get("content", ""))
                    if text.strip().lower().startswith("/rate"):
                        chat_id = None
                        if isinstance(__metadata__, dict):
                            chat_id = __metadata__.get("chat_id") or __metadata__.get("id")
                        if not chat_id and isinstance(body, dict):
                            chat_id = body.get("chat_id") or body.get("id")
                        user_id = __user__.get("id") if isinstance(__user__, dict) else None
                        confirmation = self._handle_rate_command(text, chat_id, user_id)
                        if confirmation is not None:
                            # Keep as user message but rewrite content so the LLM
                            # echoes the confirmation instead of treating /rate as a question.
                            # This avoids breaking the messages array contract (last must be user).
                            last["content"] = (
                                f"[SYSTEM: The user just submitted a rating for the previous response. "
                                f"Reply with ONLY the following text, nothing else:]\n\n{confirmation}"
                            )
                            if isinstance(__metadata__, dict):
                                __metadata__["_rate_handled"] = True
                                # Mark so outlet still captures but doesn't double-count latency
                                __metadata__["_rate_confirmation"] = confirmation
                            self._log(f"inlet handled /rate command -> {confirmation[:80]}")
                            if __event_emitter__ is not None:
                                try:
                                    emitter = __event_emitter__
                                    if callable(getattr(emitter, "__call__", None)):
                                        await emitter({"type": "status", "data": {"description": "Rating saved", "done": True}})
                                except Exception:
                                    pass
                            return body
                        # /rate-like but parse failed — let it through with hint
                        if text.strip().startswith("/rate"):
                            last["content"] = (
                                f"Your message looked like a rating command but could not be parsed.\n"
                                f"Use: `/rate 5 Great response! #helpful`\n"
                                f"  (rating 1-5, then optional comment and #tags)\n"
                                f"Original: {text[:200]}"
                            )
                            return body

            if __metadata__ is None:
                self._log("inlet: __metadata__ is None (direct API call) — skip")
                return body

            # Extract original query from last user message
            original_query = ""
            if messages:
                last = messages[-1]
                if isinstance(last, dict):
                    original_query = str(last.get("content", ""))

            # Store timing + query for correlation with outlet
            __metadata__["_trace_start"] = time.monotonic()
            trace_data = self._ensure_trace_data(__metadata__)
            if trace_data is not None:
                trace_data["original_query"] = original_query
                trace_data["inlet_timestamp"] = time.time()
                trace_data["user"] = __user__.get("id") if isinstance(__user__, dict) else None
                # Preserve chat_id / request_id if already present
                if isinstance(__metadata__, dict):
                    for k in ("chat_id", "message_id", "request_id", "session_id"):
                        if k in __metadata__ and k not in trace_data:
                            trace_data[k] = __metadata__[k]
                self._log(f"inlet captured query len={len(original_query)}")

            if __event_emitter__ is not None:
                try:
                    # Optional visual feedback — guard for emitter shape
                    emitter = __event_emitter__
                    if callable(getattr(emitter, "__call__", None)):
                        await emitter({"type": "status", "data": {"description": "Tracing enabled", "done": True}})
                except Exception:
                    pass

        except Exception as e:
            self._log(f"inlet error (swallowed): {e}")
        return body

    async def request(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
        __event_emitter__=None,
        **kwargs,
    ) -> dict:
        """At this point RAG chunks are injected as <source> tags in messages.

        Parses them and stores in __metadata__["_trace_data"]:
          - chunks: list of {id, name, resource_id, content_preview, content}
          - system_prompt: content of messages[0] if role == system
          - chunk_count: int

        Must be idempotent — don't duplicate data if called multiple times
        in a tool loop.
        """
        try:
            if not self.valves.capture_enabled:
                return body
            if __metadata__ is None:
                return body

            trace_data = self._ensure_trace_data(__metadata__)
            if trace_data is None:
                return body

            # Idempotency: skip if already parsed in this request cycle
            if trace_data.get("_chunks_parsed"):
                self._log("request: already parsed — skip (idempotent)")
                return body

            messages = body.get("messages", []) if isinstance(body, dict) else []
            if not messages:
                return body

            # Capture system prompt from messages[0] if role is system
            system_prompt = ""
            first = messages[0] if messages else None
            if isinstance(first, dict) and first.get("role") == "system":
                system_prompt = str(first.get("content", ""))
                trace_data["system_prompt"] = system_prompt
                trace_data["system_prompt_preview"] = system_prompt[:1000]

            # Parse <source> tags across ALL messages (often injected into last user msg)
            all_chunks: list = []
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                content = str(msg.get("content", ""))
                if "<source" not in content:
                    continue
                chunks = self._parse_source_chunks(content)
                all_chunks.extend(chunks)

            if all_chunks:
                trace_data["chunks"] = all_chunks
                trace_data["chunk_count"] = len(all_chunks)
            else:
                trace_data.setdefault("chunks", [])
                trace_data.setdefault("chunk_count", 0)

            # Also capture normalized query / messages snapshot for debugging
            trace_data["messages_snapshot"] = [
                {"role": str(m.get("role", "")), "content_preview": str(m.get("content", ""))[:500]}
                for m in messages
                if isinstance(m, dict)
            ][:10]  # cap to avoid huge metadata

            trace_data["_chunks_parsed"] = True
            self._log(f"request captured {len(all_chunks)} chunks, system_prompt len={len(system_prompt)}")

        except Exception as e:
            self._log(f"request error (swallowed): {e}")
        return body

    async def outlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
        __event_emitter__=None,
        **kwargs,
    ) -> dict:
        """Capture final assistant response + latency and POST to observability.

        Combines:
          - original_query, chunks, system_prompt from _trace_data
          - final response content from body
          - latency computed from _trace_start

        POSTs to {trace_endpoint}/api/observability/traces
        FAILS SILENTLY if endpoint unreachable — never breaks the chat.
        """
        try:
            if not self.valves.capture_enabled:
                return body

            # Extract final response content — handle both OpenWebUI shapes
            final_content = ""
            if isinstance(body, dict):
                # Shape 1: {"messages": [..., {"role":"assistant","content":"..."}]}
                msgs = body.get("messages")
                if isinstance(msgs, list) and msgs:
                    last = msgs[-1]
                    if isinstance(last, dict) and last.get("role") == "assistant":
                        final_content = str(last.get("content", ""))
                # Shape 2: {"choices": [{"message": {"content": "..."}}]}
                if not final_content:
                    choices = body.get("choices", [])
                    if isinstance(choices, list) and choices:
                        ch = choices[0]
                        if isinstance(ch, dict):
                            msg = ch.get("message", {})
                            if isinstance(msg, dict):
                                final_content = str(msg.get("content", ""))
                            # streaming delta fallback
                            if not final_content:
                                delta = ch.get("delta", {})
                                if isinstance(delta, dict):
                                    final_content = str(delta.get("content", ""))
                # Shape 3: {"content": "..."} or {"response": "..."}
                if not final_content:
                    for k in ("content", "response", "output", "text"):
                        if k in body and isinstance(body[k], str):
                            final_content = body[k]
                            break

            # Skip trace POST for /rate commands (already handled in inlet)
            if isinstance(__metadata__, dict) and __metadata__.get("_rate_handled"):
                return body

            # Compute latency
            latency_ms = None
            trace_data: Optional[dict] = None
            if isinstance(__metadata__, dict):
                trace_data = __metadata__.get("_trace_data")
                start = __metadata__.get("_trace_start")
                if isinstance(start, (int, float)):
                    latency_ms = (time.monotonic() - start) * 1000.0

            # Build payload
            # Generate a client-side request_id if none exists
            request_id = None
            if isinstance(trace_data, dict):
                request_id = trace_data.get("request_id") or trace_data.get("chat_id")
            if not request_id and isinstance(__metadata__, dict):
                request_id = __metadata__.get("request_id") or __metadata__.get("chat_id")
            if not request_id and isinstance(body, dict):
                request_id = body.get("request_id") or body.get("id") or body.get("chat_id")
            if not request_id:
                # Derive deterministic-ish id from query + timestamp
                q = trace_data.get("original_query", "") if isinstance(trace_data, dict) else ""
                request_id = f"filter-{abs(hash(q)) % 10_000_000:07d}-{int(time.time())}"

            payload = {
                "request_id": request_id,
                "query": trace_data.get("original_query", "") if isinstance(trace_data, dict) else "",
                "original_query": trace_data.get("original_query", "") if isinstance(trace_data, dict) else "",
                "chunks": trace_data.get("chunks", []) if isinstance(trace_data, dict) else [],
                "chunk_count": trace_data.get("chunk_count", 0) if isinstance(trace_data, dict) else 0,
                "system_prompt": trace_data.get("system_prompt", "") if isinstance(trace_data, dict) else "",
                "system_prompt_preview": trace_data.get("system_prompt_preview", "") if isinstance(trace_data, dict) else "",
                "messages_snapshot": trace_data.get("messages_snapshot", []) if isinstance(trace_data, dict) else [],
                "response": final_content,
                "final_answer": final_content,
                "latency_ms": round(latency_ms, 2) if isinstance(latency_ms, float) else None,
                "timestamp": time.time(),
                "stages": PIPELINE_STAGES,
                "metadata": {
                    "user_id": __user__.get("id") if isinstance(__user__, dict) else None,
                    "chat_id": __metadata__.get("chat_id") if isinstance(__metadata__, dict) else None,
                    "model": body.get("model", "") if isinstance(body, dict) else "",
                },
            }

            self._log(f"outlet response len={len(final_content)} latency_ms={payload['latency_ms']}")

            # Fire-and-forget POST — never raise
            # Run synchronously but with short timeout; wrapped in try/except
            # We do this in a thread-safe way without blocking the event loop too long
            try:
                self._post_trace(payload)
            except Exception as e:
                self._log(f"outlet POST wrapper error (swallowed): {e}")

            # Optional event emitter notification
            if __event_emitter__ is not None:
                try:
                    emitter = __event_emitter__
                    if callable(getattr(emitter, "__call__", None)):
                        await emitter(
                            {
                                "type": "status",
                                "data": {
                                    "description": f"Trace captured ({payload['chunk_count']} chunks)",
                                    "done": True,
                                },
                            }
                        )
                except Exception:
                    pass

        except Exception as e:
            # Absolute fail-safe — outlet must never break the chat
            try:
                self._log(f"outlet outer error (swallowed): {e}")
            except Exception:
                pass
        return body
