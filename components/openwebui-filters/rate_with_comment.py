"""
Rate with Comment — OpenWebUI Action Function (Phase 4)

Lets users rate an assistant response with stars + comment + tags.

Flow:
  1. User clicks the action button under a message.
  2. This action extracts request_id / chat_id / message content.
  3. It fetches any existing evaluation for that request_id.
  4. It returns a markdown panel with:
     - Current evaluation (if any)
     - Instructions for submitting a rating via `/rate` chat command
     - Dashboard link
     - If the body already contains a /rate pattern, it parses and POSTs
       the evaluation to {observability_endpoint}/api/observability/evaluations

Because OpenWebUI Action Functions cannot render interactive forms,
the MVP uses a chat-command pattern:

  /rate 5 Great response! #helpful #accurate

The filter/action sandbox is stdlib-only (urllib, not httpx).
"""

from pydantic import BaseModel, Field
from typing import Optional
import json
import re
import time
import urllib.request
import urllib.parse
import urllib.error
import asyncio


# Matches: /rate 5 Great response! #tag1 #tag2
# Groups: rating (1-5), comment, tags
_RATE_RE = re.compile(
    r"/rate\s+([1-5])\s*(.*?)\s*(#[\w-]+(?:\s+#[\w-]+)*)?\s*$",
    re.IGNORECASE | re.DOTALL,
)


class Action:
    """OpenWebUI Action — rate a response with comment and tags."""

    class Valves(BaseModel):
        observability_endpoint: str = Field(
            default="http://rag-tracing-fallback:3000",
            description="Observability service endpoint (Docker: rag-tracing-fallback:3000, host: 127.0.0.1:3000)",
        )
        rating_scale: int = Field(
            default=5,
            description="Max rating (5 stars)",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.name = "rate_response"

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _extract_request_id(self, body: dict) -> Optional[str]:
        if not isinstance(body, dict):
            return None
        # Spec priority: metadata.request_id → request_id → chat_id → message.id
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
        # Fallbacks for compatibility
        if isinstance(meta, dict):
            for key in ("chat_id", "id"):
                v = meta.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()
        if isinstance(msg, dict):
            for key in ("request_id", "chat_id"):
                v = msg.get(key)
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
        # Scan messages for embedded request_id
        messages = body.get("messages")
        if isinstance(messages, list):
            for m in messages:
                if not isinstance(m, dict):
                    continue
                mm = m.get("metadata")
                if isinstance(mm, dict):
                    v = mm.get("request_id")
                    if isinstance(v, str) and v.strip():
                        return v.strip()
        return None

    def _extract_message_content(self, body: dict) -> str:
        """Best-effort assistant message extraction."""
        if not isinstance(body, dict):
            return ""
        # Direct message
        msg = body.get("message")
        if isinstance(msg, dict):
            c = msg.get("content")
            if isinstance(c, str) and c.strip():
                return c.strip()
        # Choices shape
        choices = body.get("choices")
        if isinstance(choices, list) and choices:
            ch = choices[0]
            if isinstance(ch, dict):
                m = ch.get("message", {})
                if isinstance(m, dict) and isinstance(m.get("content"), str):
                    return m["content"].strip()
        # Messages list — last assistant
        messages = body.get("messages")
        if isinstance(messages, list) and messages:
            for m in reversed(messages):
                if isinstance(m, dict) and m.get("role") == "assistant":
                    c = m.get("content")
                    if isinstance(c, str) and c.strip():
                        return c.strip()
        # Fallback keys
        for k in ("content", "response", "output", "text"):
            v = body.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

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

    def _find_rate_command(self, body: dict) -> Optional[dict]:
        """Search body text for a /rate command and parse it.

        Returns {rating:int, comment:str, tags:list} or None.
        Scans: body.content, body.message.content, messages[-1].content
        """
        candidates: list[str] = []
        if isinstance(body, dict):
            for k in ("content", "text", "input"):
                v = body.get(k)
                if isinstance(v, str):
                    candidates.append(v)
            msg = body.get("message")
            if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                candidates.append(msg["content"])
            messages = body.get("messages")
            if isinstance(messages, list) and messages:
                last = messages[-1]
                if isinstance(last, dict) and isinstance(last.get("content"), str):
                    candidates.append(last["content"])

        for text in candidates:
            m = _RATE_RE.search(text.strip())
            if m:
                rating = int(m.group(1))
                comment = (m.group(2) or "").strip()
                tags_raw = (m.group(3) or "").strip()
                tags = re.findall(r"#([\w-]+)", tags_raw) if tags_raw else []
                return {"rating": rating, "comment": comment, "tags": tags, "raw": text.strip()}
        return None

    async def _fetch_evaluation(self, request_id: str) -> Optional[dict]:
        """GET existing evaluation for request_id — returns dict or None."""
        base = self.valves.observability_endpoint.rstrip("/")
        candidates = [
            f"{base}/api/observability/evaluations/{urllib.parse.quote(request_id)}",
            f"{base}/api/observability/evaluations?request_id={urllib.parse.quote(request_id)}",
            f"{base}/api/observability/traces/{urllib.parse.quote(request_id)}",
        ]

        def _do_fetch(url):
            req = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
            return None

        for url in candidates:
            try:
                data = await asyncio.to_thread(_do_fetch, url)
                if data is None:
                    continue
                # Direct evaluation object
                if isinstance(data, dict) and ("rating" in data or "evaluations" in data):
                    return data
                # Envelope {data: {...}}
                if isinstance(data, dict) and isinstance(data.get("data"), dict):
                    inner = data["data"]
                    if "rating" in inner or "evaluations" in inner:
                        return inner
                # List envelope — find matching request_id
                if isinstance(data, dict) and isinstance(data.get("data"), list):
                    for item in data["data"]:
                        if isinstance(item, dict) and item.get("request_id") == request_id:
                            return item
                # Fallback: if trace payload contains evaluation
                if isinstance(data, dict) and "evaluation" in data:
                    return data["evaluation"]
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue
                continue
            except Exception:
                continue
        return None

    async def _post_evaluation(self, payload: dict) -> tuple[bool, str]:
        """POST evaluation to observability. Returns (ok, message)."""
        base = self.valves.observability_endpoint.rstrip("/")
        url = f"{base}/api/observability/evaluations"
        try:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url, data=data, method="POST", headers={"Content-Type": "application/json"}
            )
            def _do_post():
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    return resp.read().decode("utf-8")
            body = await asyncio.to_thread(_do_post)
            return True, body[:500]
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8")[:300]
            except Exception:
                err_body = str(e)
            return False, f"HTTP {e.code}: {err_body}"
        except Exception as e:
            return False, str(e)[:300]

    def _stars(self, rating: Optional[int]) -> str:
        if rating is None or not isinstance(rating, int):
            return "☆" * self.valves.rating_scale
        scale = self.valves.rating_scale
        rating = max(0, min(rating, scale))
        return "★" * rating + "☆" * (scale - rating)

    def _render_panel(
        self,
        request_id: Optional[str],
        chat_id: Optional[str],
        message_preview: str,
        existing: Optional[dict],
        parse_result: Optional[dict] = None,
        post_ok: Optional[bool] = None,
        post_msg: str = "",
    ) -> str:
        base = self.valves.observability_endpoint.rstrip("/")
        lines: list[str] = []
        scale = self.valves.rating_scale

        lines.append(f"# Rate Response {self._stars(existing.get('rating') if isinstance(existing, dict) else None) if isinstance(existing, dict) and 'rating' in existing else ''}".strip())
        lines.append("")

        rid_display = f"`{request_id}`" if request_id else "_(no request_id found)_"
        lines.append(f"**Request ID:** {rid_display}")
        if chat_id:
            lines.append(f"**Chat ID:** `{chat_id}`")
        lines.append("")

        if message_preview:
            preview = message_preview[:300] + ("…" if len(message_preview) > 300 else "")
            # Escape markdown-sensitive chars lightly — keep readable
            lines.append(f"> {preview}")
            lines.append("")

        # Existing evaluation
        if isinstance(existing, dict) and ("rating" in existing or "comment" in existing):
            lines.append("## Current Evaluation")
            r = existing.get("rating")
            if r is not None:
                lines.append(f"- **Rating:** {self._stars(int(r))} ({r}/{scale})")
            if existing.get("comment"):
                lines.append(f"- **Comment:** {existing['comment']}")
            if existing.get("tags"):
                tags = existing["tags"]
                if isinstance(tags, list):
                    lines.append(f"- **Tags:** {', '.join('#' + str(t) for t in tags)}")
                else:
                    lines.append(f"- **Tags:** {tags}")
            if existing.get("created_at") or existing.get("timestamp"):
                lines.append(f"- **Rated at:** {existing.get('created_at') or existing.get('timestamp')}")
            if existing.get("user_id"):
                lines.append(f"- **By:** `{existing['user_id']}`")
            lines.append("")
        elif isinstance(existing, dict) and isinstance(existing.get("evaluations"), list) and existing["evaluations"]:
            lines.append("## Current Evaluations")
            for ev in existing["evaluations"][:5]:
                if isinstance(ev, dict):
                    lines.append(f"- {self._stars(ev.get('rating'))} ({ev.get('rating','?')}/{scale}) — {ev.get('comment','')} {', '.join('#'+t for t in ev.get('tags',[]))}")
            lines.append("")
        else:
            lines.append("_No evaluation yet for this message._")
            lines.append("")

        # If a /rate command was just parsed and posted
        if parse_result is not None:
            lines.append("---")
            if post_ok:
                lines.append(f"Saved: {self._stars(parse_result['rating'])} ({parse_result['rating']}/{scale})")
                if parse_result["comment"]:
                    lines.append(f"> {parse_result['comment']}")
                if parse_result["tags"]:
                    lines.append(f"Tags: {', '.join('#'+t for t in parse_result['tags'])}")
                lines.append("")
            else:
                lines.append(f"Failed to save rating: {post_msg}")
                lines.append("")
                lines.append(f"Payload attempted: `rating={parse_result['rating']}` comment=`{parse_result['comment'][:100]}` tags={parse_result['tags']}")
                lines.append("")

        # Instructions — now handled live by the rag_trace_capture filter inlet
        lines.append("---")
        lines.append("## How to Rate — type a `/rate` command as your next message")
        lines.append("")
        lines.append(f"```\n/rate 5 Great response! #helpful #accurate\n```")
        lines.append("")
        lines.append(f"- Rating is **1–{scale}** (required, first number after `/rate`)")
        lines.append(f"- Comment is free text after the rating")
        lines.append(f"- Tags are optional `#tag` words at the end (e.g. `#helpful #accurate #needs-work`)")
        lines.append(f"- The filter saves it instantly — the LLM is not called for `/rate` messages")
        lines.append("")
        lines.append(f"**Examples — copy, edit, and send as your next message:**")
        lines.append(f"```\n/rate 5 Excellent, very accurate\n/rate 3 Could be more detailed #needs-work\n/rate 1 Hallucinated sources #inaccurate\n```")
        lines.append("")
        lines.append(f"> After you send `/rate ...`, you will get a confirmation and the rating appears in the dashboard.")

        # Dashboard link
        lines.append("")
        lines.append("---")
        dash = base.replace("rag-tracing-fallback", "127.0.0.1")
        if request_id:
            lines.append(f"[View Pipeline]({dash}/api/observability/pipeline/{urllib.parse.quote(request_id)}) · [Dashboard]({dash}/dashboard/observability) · [All Traces]({dash}/observe)")
        else:
            lines.append(f"[Dashboard]({dash}/dashboard/observability) · [All Traces]({dash}/observe) · [Health]({dash}/health)")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # OpenWebUI entry points
    # ------------------------------------------------------------------
    async def action(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__=None,
        **kwargs,
    ) -> Optional[str]:
        """Show current evaluation or parse a /rate command and save it."""
        try:
            request_id = self._extract_request_id(body)
            if not request_id:
                # Try kwargs
                for k in ("request_id", "chat_id", "id"):
                    v = kwargs.get(k)
                    if isinstance(v, str) and v.strip():
                        request_id = v.strip()
                        break

            chat_id = self._extract_chat_id(body) or kwargs.get("chat_id")
            if isinstance(chat_id, str) and not chat_id.strip():
                chat_id = None

            message_preview = self._extract_message_content(body)

            # Check if body already contains a /rate command to parse + save
            rate_cmd = self._find_rate_command(body)
            post_ok: Optional[bool] = None
            post_msg = ""
            if rate_cmd is not None and request_id:
                payload = {
                    "request_id": request_id,
                    "chat_id": chat_id,
                    "rating": rate_cmd["rating"],
                    "comment": rate_cmd["comment"],
                    "tags": rate_cmd["tags"],
                    "timestamp": time.time(),
                    "user_id": __user__.get("id") if isinstance(__user__, dict) else None,
                    "message_preview": message_preview[:500],
                }
                ok, msg = await self._post_evaluation(payload)
                post_ok = ok
                post_msg = msg
                if __event_emitter__ is not None:
                    try:
                        emitter = __event_emitter__
                        if callable(getattr(emitter, "__call__", None)):
                            await emitter(
                                {
                                    "type": "status",
                                    "data": {
                                        "description": "Rating saved" if ok else f"Rating failed: {msg[:80]}",
                                        "done": True,
                                    },
                                }
                            )
                    except Exception:
                        pass
                # Re-fetch to show updated evaluation
                existing = None
                if ok:
                    existing = await self._fetch_evaluation(request_id)
                    # Merge so panel shows what was just saved even if fetch lags
                    if not isinstance(existing, dict) or "rating" not in existing:
                        existing = payload
                else:
                    existing = await self._fetch_evaluation(request_id)
                return self._render_panel(request_id, chat_id, message_preview, existing, rate_cmd, post_ok, post_msg)

            # No /rate command — just show current evaluation + instructions
            existing = None
            if request_id:
                existing = await self._fetch_evaluation(request_id)

            if __event_emitter__ is not None:
                try:
                    emitter = __event_emitter__
                    if callable(getattr(emitter, "__call__", None)):
                        await emitter({"type": "status", "data": {"description": "Evaluation panel ready", "done": True}})
                except Exception:
                    pass

            return self._render_panel(request_id, chat_id, message_preview, existing)

        except Exception as e:
            base = self.valves.observability_endpoint.rstrip("/")
            return (
                f"Error loading evaluation panel: {e}\n\n"
                f"Endpoint: `{base}`\n"
                f"Try health check: `curl {base}/health`"
            )

    async def pipe(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__=None,
        **kwargs,
    ) -> Optional[str]:
        """Alias for `action` — OpenWebUI ≤0.5 dispatches to `pipe` for actions."""
        return await self.action(body, __user__, __event_emitter__, **kwargs)
