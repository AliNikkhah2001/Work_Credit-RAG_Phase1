"""
Report Problem with this Answer — OpenWebUI Action Function (ICS helper)

> NOTE: The orchestrator should also handle /report at api.py:chat_completions
> (like the existing /rate handler) — add it there if missing, otherwise this
> action will handle it alone.

Panel shows a fixed list of problem categories; the user replies with
  /report <category> <comment> #tag1 #tag2
or
  /problem <category> <comment> #tag1 #tag2

Categories:
  - inaccurate — factually wrong
  - incomplete — missing important info
  - hallucination — cites sources that don't support the claim
  - wrong_source — retrieved from irrelevant document
  - off_topic — answer doesn't address the question
  - other — free-form

POSTs to {observability_endpoint}/api/observability/evaluations as:
  {request_id, chat_id, comment: "[REPORT:<category>] <comment>",
   tags: [..., "report:<category>"], user_id}

Also handles structured body fields: report_category / report_comment /
report_problem / problem_category.

Only stdlib + pydantic — uses urllib.request (no httpx).
"""

from pydantic import BaseModel, Field
from typing import Optional
import json
import re
import time
import urllib.request
import urllib.parse
import urllib.error


# /report or /problem — category first, then comment, then tags
_REPORT_RE = re.compile(
    r"/(?:report|problem)\s+(\w+)\s*(.*?)\s*(#[\w-]+(?:\s+#[\w-]+)*)?\s*$",
    re.IGNORECASE | re.DOTALL,
)

CATEGORIES: list[tuple[str, str]] = [
    ("inaccurate", "factually wrong"),
    ("incomplete", "missing important info"),
    ("hallucination", "cites sources that don't support the claim"),
    ("wrong_source", "retrieved from irrelevant document"),
    ("off_topic", "answer doesn't address the question"),
    ("other", "free-form"),
]
VALID_CATEGORIES = {c[0] for c in CATEGORIES}


class Action:
    """OpenWebUI Action — report a problem with the current answer."""

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
                vv = meta.get(key)
                if isinstance(vv, str) and vv.strip():
                    return vv.strip()
        if isinstance(msg, dict):
            for key in ("request_id", "chat_id"):
                vv = msg.get(key)
                if isinstance(vv, str) and vv.strip():
                    return vv.strip()
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

    def _find_report_command(self, body: dict) -> Optional[dict]:
        """Parse /report or /problem from body text or structured fields."""
        # 1) Structured fields
        if isinstance(body, dict):
            cat = None
            for k in ("report_category", "report_problem", "problem_category", "category", "report"):
                v = body.get(k)
                if isinstance(v, str) and v.strip():
                    # if value looks like a category word
                    word = v.strip().split()[0].lower()
                    if word in VALID_CATEGORIES or word == "other":
                        cat = word
                        # comment from sibling field
                        comment = body.get("report_comment") or body.get("comment") or body.get("text") or ""
                        # tags
                        tags: list[str] = []
                        tv = body.get("tags")
                        if isinstance(tv, list):
                            tags = [str(t).lstrip("#") for t in tv]
                        elif isinstance(tv, str):
                            tags = re.findall(r"#([\w-]+)", tv)
                        return {"category": cat, "comment": str(comment).strip(), "tags": tags, "raw": f"direct:{k}={cat}"}
                    # if report field already contains a full /report command text
                    if "/" in v:
                        body = {**body, "content": v}
                        break
            # also check nested report object
            rep = body.get("report")
            if isinstance(rep, dict):
                c = rep.get("category") or rep.get("report_category")
                if isinstance(c, str) and c.strip().lower() in VALID_CATEGORIES:
                    comment = rep.get("comment") or rep.get("report_comment") or ""
                    tags = rep.get("tags") if isinstance(rep.get("tags"), list) else []
                    tags = [str(t).lstrip("#") for t in tags]
                    return {"category": c.strip().lower(), "comment": str(comment).strip(), "tags": tags, "raw": "direct:report.category"}

        # 2) Text pattern
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
            m = _REPORT_RE.search(text.strip())
            if m:
                category = m.group(1).strip().lower()
                if category not in VALID_CATEGORIES:
                    # allow but normalize unknown to "other"
                    # still record original word as tag
                    category = "other" if category not in VALID_CATEGORIES else category
                    # keep original word in comment/tag? just use other
                comment = (m.group(2) or "").strip()
                tags_raw = (m.group(3) or "").strip()
                tags = re.findall(r"#([\w-]+)", tags_raw) if tags_raw else []
                return {"category": category, "comment": comment, "tags": tags, "raw": text.strip()}
        return None

    def _fetch_evaluations(self, request_id: str) -> list[dict]:
        base = self.valves.observability_endpoint.rstrip("/")
        url = f"{base}/api/observability/evaluations?search={urllib.parse.quote(request_id)}&limit=50"
        try:
            req = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    rows = data.get("data") if isinstance(data, dict) else None
                    if isinstance(rows, list):
                        return [r for r in rows if isinstance(r, dict)]
                    if isinstance(data, list):
                        return [r for r in data if isinstance(r, dict)]
        except Exception:
            pass
        return []

    def _filter_reports(self, rows: list[dict]) -> list[dict]:
        out: list[dict] = []
        for r in rows:
            comment = r.get("comment") if isinstance(r.get("comment"), str) else ""
            tags = r.get("tags") if isinstance(r.get("tags"), list) else []
            is_report = "[REPORT:" in comment or any(str(t).startswith("report:") for t in tags)
            if is_report:
                out.append(r)
        return out

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

    def _render_panel(
        self,
        request_id: Optional[str],
        chat_id: Optional[str],
        message_preview: str,
        existing_reports: list[dict],
        parse_result: Optional[dict] = None,
        post_ok: Optional[bool] = None,
        post_msg: str = "",
    ) -> str:
        base = self.valves.observability_endpoint.rstrip("/")
        dash = base.replace("rag-tracing-fallback", "127.0.0.1")
        lines: list[str] = []

        lines.append("## Report a problem with this answer")
        lines.append("")
        rid_display = f"`{request_id}`" if request_id else "_(no request_id found)_"
        lines.append(f"**Request ID:** {rid_display}")
        if chat_id:
            lines.append(f"**Chat ID:** `{chat_id}`")
        lines.append("")

        if message_preview:
            preview = message_preview[:400] + ("…" if len(message_preview) > 400 else "")
            lines.append(f"> {preview}")
            lines.append("")

        # Existing reports for this request
        if existing_reports:
            lines.append(f"### Existing reports ({len(existing_reports)})")
            lines.append("")
            for ev in existing_reports[:5]:
                comment = ev.get("comment", "")
                tags = ev.get("tags") if isinstance(ev.get("tags"), list) else []
                tag_str = ", ".join("#" + str(t) for t in tags) if tags else ""
                # extract category from comment prefix [REPORT:xxx]
                cat_m = re.search(r"\[REPORT:(\w+)\]", comment)
                cat_label = cat_m.group(1) if cat_m else "report"
                # strip prefix for display
                display_comment = re.sub(r"^\[REPORT:\w+\]\s*", "", comment)
                lines.append(f"- **{cat_label}** — {display_comment} {tag_str}")
                if ev.get("created_at"):
                    lines.append(f"  <sub>{ev.get('created_at')}</sub>")
            lines.append("")
        else:
            lines.append("_No reports yet for this message._")
            lines.append("")

        # If a /report was just parsed and posted
        if parse_result is not None:
            lines.append("---")
            if post_ok:
                lines.append(f"**Report saved:** `{parse_result['category']}`")
                if parse_result["comment"]:
                    lines.append(f"> {parse_result['comment']}")
                if parse_result["tags"]:
                    lines.append(f"Tags: {', '.join('#' + t for t in parse_result['tags'])} + #report:{parse_result['category']}")
                lines.append("")
            else:
                lines.append(f"**Failed to save report:** {post_msg}")
                lines.append("")
                lines.append(f"Payload attempted: category=`{parse_result['category']}` comment=`{parse_result['comment'][:100]}` tags={parse_result['tags']}")
                lines.append("")

        # Category selection
        lines.append("---")
        lines.append("### Problem categories — pick one")
        lines.append("")
        for cat, desc in CATEGORIES:
            lines.append(f"- **{cat}** — {desc}")
        lines.append("")
        lines.append("**Reply with one of these commands as your next message:**")
        lines.append("")
        lines.append("```")
        lines.append("/report inaccurate The year is wrong #fact-error")
        lines.append("/report hallucination It cites page 5 but page 5 says something else")
        lines.append("/report wrong_source Retrieved from contract.pdf but question is about credit score")
        lines.append("/report incomplete Answer omits the 2024 regulation update")
        lines.append("/report off_topic I asked about fees, answer is about history")
        lines.append("/report other Free-form issue description here")
        lines.append("```")
        lines.append("")
        lines.append("**Aliases & extras:**")
        lines.append("")
        lines.append("- `/problem` works the same as `/report`")
        lines.append("- Combine with stars: `/rate 2 /report inaccurate ...` (send as one message; the filter will save both)")
        lines.append("- Structured JSON also works: `{\"report_category\": \"hallucination\", \"report_comment\": \"...\", \"tags\": [\"fact-error\"]}`")
        lines.append("")
        lines.append("**Format:** `/report <category> <comment> [#tag ...]`")
        lines.append("- `category` is required and must be one of the six above")
        lines.append("- `comment` is free text after the category")
        lines.append("- `tags` are optional `#tag` words at the end")
        lines.append("")
        lines.append("> After you send `/report ...`, you will get a confirmation and the report appears in the dashboard.")
        lines.append("")

        # Dashboard links
        lines.append("---")
        if request_id:
            lines.append(f"[View Pipeline]({dash}/api/observability/pipeline/{urllib.parse.quote(request_id)}) · [Dashboard]({dash}/dashboard/observability) · [All Traces]({dash}/observe)")
        else:
            lines.append(f"[Dashboard]({dash}/dashboard/observability) · [All Traces]({dash}/observe) · [Health]({dash}/health)")
        lines.append("")
        lines.append(f"<sub>ICS helper agent only (NOT arena) — observability: `{base}`</sub>")

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
        """Show category panel or parse & save a /report command."""
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

            # Check if body already contains a /report or structured report
            report_cmd = self._find_report_command(body)
            existing_reports: list[dict] = []
            if request_id:
                try:
                    rows = self._fetch_evaluations(request_id)
                    existing_reports = self._filter_reports(rows)
                except Exception:
                    existing_reports = []

            if report_cmd is not None and request_id:
                category = report_cmd["category"]
                comment = report_cmd["comment"]
                tags = report_cmd["tags"]
                # build evaluation payload — store report as prefixed comment + tag
                prefixed_comment = f"[REPORT:{category}] {comment}".strip()
                all_tags = tags + [f"report:{category}"]
                # also try to carry rating if present in body (combine /rate + /report)
                rating = None
                if isinstance(body, dict):
                    for k in ("rating", "stars"):
                        v = body.get(k)
                        if isinstance(v, int) and 1 <= v <= 5:
                            rating = v
                            break
                payload: dict = {
                    "request_id": request_id,
                    "chat_id": chat_id,
                    "comment": prefixed_comment,
                    "tags": all_tags,
                    "timestamp": time.time(),
                    "user_id": __user__.get("id") if isinstance(__user__, dict) else None,
                    "message_preview": message_preview[:500],
                    "report": True,
                    "report_category": category,
                    "report_comment": comment,
                }
                if rating is not None:
                    payload["rating"] = rating

                ok, msg = self._post_evaluation(payload)
                if __event_emitter__ is not None:
                    try:
                        emitter = __event_emitter__
                        if callable(getattr(emitter, "__call__", None)):
                            await emitter(
                                {
                                    "type": "status",
                                    "data": {
                                        "description": "Report saved" if ok else f"Report failed: {msg[:80]}",
                                        "done": True,
                                    },
                                }
                            )
                    except Exception:
                        pass
                # re-fetch to show updated list
                if ok:
                    try:
                        rows = self._fetch_evaluations(request_id)
                        new_reports = self._filter_reports(rows)
                        if new_reports:
                            existing_reports = new_reports
                        else:
                            # merge so panel shows what was just saved even if search lags
                            existing_reports = [*existing_reports, {"comment": prefixed_comment, "tags": all_tags, "created_at": "just now"}]
                    except Exception:
                        existing_reports = [*existing_reports, {"comment": prefixed_comment, "tags": all_tags, "created_at": "just now"}]
                return self._render_panel(request_id, chat_id, message_preview, existing_reports, report_cmd, ok, msg)

            return self._render_panel(request_id, chat_id, message_preview, existing_reports)

        except Exception as e:
            base = self.valves.observability_endpoint.rstrip("/")
            return (
                f"Error loading report panel: {e}\n\n"
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
