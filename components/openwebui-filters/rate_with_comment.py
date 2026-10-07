"""
Star Rating + Comment — OpenWebUI Action Function (ICS helper agent, NOT arena)

> NOTE: The orchestrator should also handle /report at api.py:chat_completions
> (like the existing /rate handler) — add it there if missing, otherwise this
> action will handle it alone.

Flow:
  1. User clicks the action button under an assistant message.
  2. This action extracts request_id / chat_id / message preview.
  3. Fetches any existing evaluation for that request_id.
  4. If body already contains a /rate command or direct rating fields,
     POSTs the evaluation immediately and shows confirmation.
  5. Otherwise shows a star-selection panel with instructions.

Chat command pattern (handled here AND by the rag_trace_capture filter inlet):
  /rate 5 Great response! #helpful #accurate
  /rate 3 Could be more detailed #needs-work
  /rate 1 Hallucinated sources #inaccurate

Only stdlib + pydantic — uses urllib.request for HTTP (no httpx).
"""

from pydantic import BaseModel, Field
from typing import Optional
import json
import re
import time
import urllib.request
import urllib.parse
import urllib.error


# Matches: /rate 5 Great response! #tag1 #tag2
_RATE_RE = re.compile(
    r"/rate\s+([1-5])\s*(.*?)\s*(#[\w-]+(?:\s+#[\w-]+)*)?\s*$",
    re.IGNORECASE | re.DOTALL,
)


class Action:
    """OpenWebUI Action — star rating (1-5) + comment + tags."""

    class Valves(BaseModel):
        observability_endpoint: str = Field(
            default="http://rag-tracing-fallback:3000",
            description="Observability service endpoint (Docker: rag-tracing-fallback:3000, host: 127.0.0.1:3000)",
        )

    def __init__(self):
        self.valves = self.Valves()

    # ------------------------------------------------------------------
    # extract helpers
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
        v = body.get("id")
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
            v = meta.get("id")
            if isinstance(v, str) and v.strip():
                return v.strip()
        msg = body.get("message")
        if isinstance(msg, dict):
            v = msg.get("chat_id")
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    def _extract_message_content(self, body: dict) -> str:
        if not isinstance(body, dict):
            return ""
        msg = body.get("message")
        if isinstance(msg, dict):
            c = msg.get("content")
            if isinstance(c, str) and c.strip():
                return c.strip()
        choices = body.get("choices")
        if isinstance(choices, list) and choices:
            ch = choices[0]
            if isinstance(ch, dict):
                m = ch.get("message", {})
                if isinstance(m, dict) and isinstance(m.get("content"), str):
                    return m["content"].strip()
        messages = body.get("messages")
        if isinstance(messages, list) and messages:
            for m in reversed(messages):
                if isinstance(m, dict) and m.get("role") == "assistant":
                    c = m.get("content")
                    if isinstance(c, str) and c.strip():
                        return c.strip()
        for k in ("content", "response", "output", "text"):
            v = body.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    def _find_rate_command(self, body: dict) -> Optional[dict]:
        """Search body text for /rate or direct rating fields."""
        # 1) Direct structured fields (ICS helper could send JSON body)
        if isinstance(body, dict):
            for key in ("rating", "stars", "score"):
                v = body.get(key)
                if isinstance(v, int) and 1 <= v <= 5:
                    comment = body.get("comment") or body.get("text") or ""
                    tags = body.get("tags") if isinstance(body.get("tags"), list) else []
                    # normalize tags: strip leading '#'
                    tags = [str(t).lstrip("#") for t in tags]
                    return {"rating": v, "comment": str(comment).strip(), "tags": tags, "raw": f"direct:{key}={v}"}
                if isinstance(v, str) and v.strip().isdigit():
                    iv = int(v.strip())
                    if 1 <= iv <= 5:
                        comment = body.get("comment") or ""
                        tags = body.get("tags") if isinstance(body.get("tags"), list) else []
                        tags = [str(t).lstrip("#") for t in tags]
                        return {"rating": iv, "comment": str(comment).strip(), "tags": tags, "raw": f"direct:{key}={v}"}
            # nested evaluation object
            ev = body.get("evaluation")
            if isinstance(ev, dict) and isinstance(ev.get("rating"), int) and 1 <= ev["rating"] <= 5:
                return {
                    "rating": int(ev["rating"]),
                    "comment": str(ev.get("comment", "")).strip(),
                    "tags": [str(t).lstrip("#") for t in ev.get("tags", [])] if isinstance(ev.get("tags"), list) else [],
                    "raw": "direct:evaluation.rating",
                }

        # 2) Text pattern /rate 5 ...
        candidates: list[str] = []
        if isinstance(body, dict):
            for k in ("content", "text", "input", "comment"):
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

    def _fetch_evaluation(self, request_id: str) -> Optional[dict]:
        base = self.valves.observability_endpoint.rstrip("/")
        # try direct id, then search query param
        candidates = [
            f"{base}/api/observability/evaluations/{urllib.parse.quote(request_id)}",
            f"{base}/api/observability/evaluations?search={urllib.parse.quote(request_id)}",
            f"{base}/api/observability/evaluations?search={urllib.parse.quote(request_id)}&limit=10",
        ]
        for url in candidates:
            try:
                req = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        # direct evaluation object
                        if isinstance(data, dict) and "rating" in data:
                            return data
                        # envelope with data list — find matching request_id
                        if isinstance(data, dict) and isinstance(data.get("data"), list):
                            for item in data["data"]:
                                if isinstance(item, dict) and item.get("request_id") == request_id:
                                    return item
                            # if search returned single page, return first with rating
                            for item in data["data"]:
                                if isinstance(item, dict) and "rating" in item:
                                    return item
                            if data["data"]:
                                return {"evaluations": data["data"]}
                        if isinstance(data, dict) and isinstance(data.get("data"), dict):
                            inner = data["data"]
                            if "rating" in inner or "evaluations" in inner:
                                return inner
                        if isinstance(data, dict) and "evaluations" in data:
                            return data
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue
                continue
            except Exception:
                continue
        return None

    def _post_evaluation(self, payload: dict) -> tuple[bool, str]:
        base = self.valves.observability_endpoint.rstrip("/")
        url = f"{base}/api/observability/evaluations"
        try:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                body = resp.read().decode("utf-8")
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
            return "☆☆☆☆☆"
        rating = max(0, min(rating, 5))
        return "★" * rating + "☆" * (5 - rating)

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
        dash = base.replace("rag-tracing-fallback", "127.0.0.1")
        lines: list[str] = []

        # Title
        lines.append("## Star this response")
        lines.append("")
        # show current stars in title if existing
        if isinstance(existing, dict) and "rating" in existing:
            try:
                r = int(existing["rating"])
                lines.append(f"Current: {self._stars(r)} ({r}/5)")
                lines.append("")

            except Exception:
                pass

        rid_display = f"`{request_id}`" if request_id else "_(no request_id found)_"
        lines.append(f"**Request ID:** {rid_display}")
        if chat_id:
            lines.append(f"**Chat ID:** `{chat_id}`")
        lines.append("")

        if message_preview:
            preview = message_preview[:400] + ("…" if len(message_preview) > 400 else "")
            # blockquote preview
            lines.append(f"> {preview}")
            lines.append("")

        # Existing evaluation
        if isinstance(existing, dict) and ("rating" in existing or "comment" in existing):
            lines.append("### Current evaluation")
            r = existing.get("rating")
            if r is not None:
                try:
                    lines.append(f"- **Rating:** {self._stars(int(r))} ({r}/5)")
                except Exception:
                    lines.append(f"- **Rating:** {r}")
            if existing.get("comment"):
                lines.append(f"- **Comment:** {existing['comment']}")
            if existing.get("tags"):
                tags = existing["tags"]
                if isinstance(tags, list) and tags:
                    lines.append(f"- **Tags:** {', '.join('#' + str(t) for t in tags)}")
                elif isinstance(tags, str) and tags.strip():
                    lines.append(f"- **Tags:** {tags}")
            if existing.get("created_at") or existing.get("timestamp"):
                lines.append(f"- **Rated at:** {existing.get('created_at') or existing.get('timestamp')}")
            if existing.get("user_id"):
                lines.append(f"- **By:** `{existing['user_id']}`")
            lines.append("")
        elif isinstance(existing, dict) and isinstance(existing.get("evaluations"), list) and existing["evaluations"]:
            lines.append("### Recent evaluations for this request")
            for ev in existing["evaluations"][:5]:
                if isinstance(ev, dict):
                    rr = ev.get("rating", "?")
                    stars = self._stars(int(rr)) if isinstance(rr, int) else str(rr)
                    comment = ev.get("comment", "")
                    tags = ", ".join("#" + str(t) for t in ev.get("tags", [])) if isinstance(ev.get("tags"), list) else ""
                    lines.append(f"- {stars} ({rr}/5) — {comment} {tags}")
            lines.append("")
        else:
            lines.append("_No evaluation yet for this message._")
            lines.append("")

        # If a /rate was just parsed and posted
        if parse_result is not None:
            lines.append("---")
            if post_ok:
                lines.append(f"**Saved:** {self._stars(parse_result['rating'])} ({parse_result['rating']}/5)")
                if parse_result["comment"]:
                    lines.append(f"> {parse_result['comment']}")
                if parse_result["tags"]:
                    lines.append(f"Tags: {', '.join('#' + t for t in parse_result['tags'])}")
                lines.append("")
            else:
                lines.append(f"**Failed to save rating:** {post_msg}")
                lines.append("")
                lines.append(f"Payload attempted: `rating={parse_result['rating']}` comment=`{parse_result['comment'][:100]}` tags={parse_result['tags']}")
                lines.append("")
            # after save, still show instructions below

        # Star selection + instructions
        lines.append("---")
        lines.append("### How to rate")
        lines.append("")
        lines.append("Pick a star value and send it as your next message:")
        lines.append("")
        lines.append("- **1** — `☆☆☆☆☆` — Poor / incorrect")
        lines.append("- **2** — `★★☆☆☆` — Below average")
        lines.append("- **3** — `★★★☆☆` — Acceptable")
        lines.append("- **4** — `★★★★☆` — Good")
        lines.append("- **5** — `★★★★★` — Excellent")
        lines.append("")
        lines.append("**Quick submit — copy, edit and send:**")
        lines.append("")
        lines.append("```")
        lines.append("/rate 5 Great response! #helpful #accurate")
        lines.append("```")
        lines.append("")
        lines.append("**More examples:**")
        lines.append("```")
        lines.append("/rate 5 Excellent, very accurate")
        lines.append("/rate 3 Could be more detailed #needs-work")
        lines.append("/rate 1 Hallucinated sources #inaccurate")
        lines.append("/rate 4 Helpful but missing citation #incomplete")
        lines.append("```")
        lines.append("")
        lines.append("- Rating is **1–5** (required, first number after `/rate`)")
        lines.append("- Comment is free text after the rating")
        lines.append("- Tags are optional `#tag` words at the end (e.g. `#helpful`)")
        lines.append("- The filter saves it instantly — the LLM is not called for `/rate` messages")
        lines.append("")
        lines.append("> After you send `/rate ...`, you will get a confirmation and the rating appears in the dashboard.")
        lines.append("")
        lines.append("**Direct JSON (ICS helper):** you can also POST structured data — if this action receives `{\"rating\": 5, \"comment\": \"...\", \"tags\": [...]}` it will save immediately without needing the `/rate` prefix.")
        lines.append("")

        # Dashboard links
        lines.append("---")
        if request_id:
            lines.append(f"[View Pipeline]({dash}/api/observability/pipeline/{urllib.parse.quote(request_id)}) · [Dashboard]({dash}/dashboard/observability) · [All Traces]({dash}/observe)")
        else:
            lines.append(f"[Dashboard]({dash}/dashboard/observability) · [All Traces]({dash}/observe) · [Health]({dash}/health)")
        lines.append("")
        lines.append(f"<sub>Observability: `{base}` — ICS helper agent only (NOT arena).</sub>")

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
    ) -> str:
        """Show star panel or parse & save a /rate command."""
        try:
            request_id = self._extract_request_id(body)
            if not request_id:
                for k in ("request_id", "chat_id", "id"):
                    v = kwargs.get(k)
                    if isinstance(v, str) and v.strip():
                        request_id = v.strip()
                        break

            chat_id = self._extract_chat_id(body) or kwargs.get("chat_id")
            if isinstance(chat_id, str) and not chat_id.strip():
                chat_id = None

            message_preview = self._extract_message_content(body)

            # Check if body already contains a /rate command or direct rating
            rate_cmd = self._find_rate_command(body)
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
                ok, msg = self._post_evaluation(payload)
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
                existing = None
                if ok:
                    existing = self._fetch_evaluation(request_id)
                    if not isinstance(existing, dict) or "rating" not in existing:
                        existing = payload
                else:
                    existing = self._fetch_evaluation(request_id)
                return self._render_panel(request_id, chat_id, message_preview, existing, rate_cmd, ok, msg)

            # No /rate — just show panel + existing rating
            existing = None
            if request_id:
                existing = self._fetch_evaluation(request_id)

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
    ) -> str:
        """Alias for `action` — OpenWebUI <=0.5 dispatches to `pipe` for actions."""
        return await self.action(body, __user__, __event_emitter__, **kwargs)
