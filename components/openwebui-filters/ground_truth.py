"""
Ground Truth Reporting — OpenWebUI Action Function (ICS helper)

User can send a response and say it is the true response for that question.
Chat commands:
  /truth <correct answer text>
  /ground_truth <text>
  /true <text>
  /correct <text>

Also handles structured body fields: ground_truth / true_response / correct_answer

When triggered with a ground truth payload:
  POST to {observability_endpoint}/api/observability/evaluations with:
    {request_id, user_query, comment: "[GROUND_TRUTH] <text>",
     tags: ["ground_truth", ...], ground_truth: <text>, user_id, model}

When action button is clicked without ground truth yet:
  Shows panel with instructions, current query/answer preview, examples,
  and existing ground truths for this request_id (filtered where comment
  contains [GROUND_TRUTH] or [TRUE]).

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


_TRUTH_RE = re.compile(
    r"^\s*/(?:truth|ground_truth|true|correct)\s+(.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)


class Action:
    """OpenWebUI Action — ground truth reporting."""

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

    def _extract_user_query(self, body: dict) -> str:
        if not isinstance(body, dict):
            return ""
        # primary: last user message in messages list
        messages = body.get("messages")
        if isinstance(messages, list) and messages:
            for m in reversed(messages):
                if isinstance(m, dict) and m.get("role") == "user":
                    c = m.get("content")
                    if isinstance(c, str) and c.strip():
                        return c.strip()
            # fallback: last message content regardless of role
            last = messages[-1]
            if isinstance(last, dict) and isinstance(last.get("content"), str) and last["content"].strip():
                return last["content"].strip()
        for k in ("user_query", "query", "original_query", "input"):
            v = body.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        msg = body.get("message")
        if isinstance(msg, dict):
            c = msg.get("content")
            if isinstance(c, str) and c.strip():
                return c.strip()
        return ""

    def _find_ground_truth_command(self, body: dict) -> Optional[dict]:
        """Parse ground truth from structured fields or chat command text."""
        # 1) Structured fields: ground_truth / true_response / correct_answer
        if isinstance(body, dict):
            for k in ("ground_truth", "true_response", "correct_answer", "groundTruth", "trueResponse", "correctAnswer"):
                v = body.get(k)
                if isinstance(v, str) and v.strip():
                    text = v.strip()
                    tags = re.findall(r"#([\w-]+)", text)
                    # also merge explicit tags field if present
                    tv = body.get("tags")
                    if isinstance(tv, list):
                        tags = tags + [str(t).lstrip("#") for t in tv if str(t).strip()]
                    elif isinstance(tv, str) and tv.strip():
                        tags = tags + re.findall(r"#([\w-]+)", tv)
                    return {"text": text, "tags": tags, "raw": f"direct:{k}"}
            # nested evaluation-style object
            for outer in ("evaluation", "report", "feedback"):
                ev = body.get(outer)
                if isinstance(ev, dict):
                    for k in ("ground_truth", "true_response", "correct_answer"):
                        v = ev.get(k)
                        if isinstance(v, str) and v.strip():
                            text = v.strip()
                            tags = re.findall(r"#([\w-]+)", text)
                            t2 = ev.get("tags")
                            if isinstance(t2, list):
                                tags = tags + [str(t).lstrip("#") for t in t2]
                            return {"text": text, "tags": tags, "raw": f"direct:{outer}.{k}"}

        # 2) Text pattern: /truth /ground_truth /true /correct
        candidates: list[str] = []
        if isinstance(body, dict):
            for k in ("content", "text", "input", "comment", "ground_truth", "true_response", "correct_answer"):
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
            if not isinstance(text, str):
                continue
            m = _TRUTH_RE.search(text.strip())
            if m:
                inner = m.group(1).strip()
                tags = re.findall(r"#([\w-]+)", inner)
                return {"text": inner, "tags": tags, "raw": text.strip()}
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

    def _filter_ground_truths(self, rows: list[dict]) -> list[dict]:
        out: list[dict] = []
        for r in rows:
            comment = r.get("comment") if isinstance(r.get("comment"), str) else ""
            tags = r.get("tags") if isinstance(r.get("tags"), list) else []
            is_gt = (
                "[GROUND_TRUTH]" in comment
                or "[TRUE]" in comment
                or "[GROUND_TRUTH]" in comment.upper()
                or any(str(t).lower() == "ground_truth" for t in tags)
                or "ground_truth" in r
                or "groundTruth" in r
            )
            if is_gt:
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
        user_query: str,
        existing_ground_truths: list[dict],
    ) -> str:
        base = self.valves.observability_endpoint.rstrip("/")
        dash = base.replace("rag-tracing-fallback", "127.0.0.1")
        lines: list[str] = []

        lines.append("## Ground truth — provide the correct answer")
        lines.append("")
        lines.append("Use this panel to submit the **true / correct answer** for the current question. It will be stored as a ground truth evaluation for later comparison.")
        lines.append("")
        rid_display = f"`{request_id}`" if request_id else "_(no request_id found)_"
        lines.append(f"**Request ID:** {rid_display}")
        if chat_id:
            lines.append(f"**Chat ID:** `{chat_id}`")
        lines.append("")

        if user_query:
            preview_q = user_query[:400] + ("…" if len(user_query) > 400 else "")
            lines.append(f"**Current query:**")
            lines.append(f"> {preview_q}")
            lines.append("")

        if message_preview:
            preview_a = message_preview[:400] + ("…" if len(message_preview) > 400 else "")
            lines.append(f"**Current answer preview:**")
            lines.append(f"> {preview_a}")
            lines.append("")

        # Existing ground truths
        if existing_ground_truths:
            lines.append(f"### Existing ground truths ({len(existing_ground_truths)})")
            lines.append("")
            for ev in existing_ground_truths[:5]:
                comment = ev.get("comment", "") if isinstance(ev.get("comment"), str) else ""
                gt = ev.get("ground_truth") or ev.get("groundTruth") or ""
                if not gt and comment:
                    gt = re.sub(r"^\[GROUND_TRUTH\]\s*", "", comment)
                    gt = re.sub(r"^\[TRUE\]\s*", "", gt)
                tags = ev.get("tags") if isinstance(ev.get("tags"), list) else []
                tag_str = ", ".join("#" + str(t) for t in tags) if tags else ""
                display = str(gt)[:300] if gt else str(comment)[:300]
                lines.append(f"- {display} {tag_str}")
                if ev.get("created_at"):
                    lines.append(f"  <sub>{ev.get('created_at')}</sub>")
            lines.append("")
        else:
            lines.append("_No ground truth yet for this message._")
            lines.append("")

        lines.append("---")
        lines.append("### How to submit ground truth")
        lines.append("")
        lines.append("Reply with one of:")
        lines.append("")
        lines.append("```")
        lines.append("/truth The correct answer is ...")
        lines.append("/ground_truth As stated in Article 5, the correct value is X")
        lines.append("/true Should be rejected because ...")
        lines.append("```")
        lines.append("")
        lines.append("**All aliases:** `/truth`, `/ground_truth`, `/true`, `/correct` — e.g.:")
        lines.append("")
        lines.append("```")
        lines.append("/truth The correct answer is ...")
        lines.append("/ground_truth As stated in Article 5, the correct value is X")
        lines.append("/true Should be rejected because ...")
        lines.append("/correct The accurate response should be ...")
        lines.append("```")
        lines.append("")
        lines.append("- You can add hashtags at the end, e.g. `/truth The value is 42 #verified` — they are saved as tags plus `ground_truth`.")
        lines.append("- Structured JSON also works: `{\"ground_truth\": \"The correct answer is ...\"}`, `{\"true_response\": \"...\"}`, or `{\"correct_answer\": \"...\"}`")
        lines.append("")
        lines.append("> After you send `/truth ...` (or any alias), you will get a confirmation and the ground truth appears in the dashboard.")
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
        """Show panel or parse & save a /truth ground truth command."""
        try:
            request_id = self._extract_request_id(body)
            if not request_id:
                for k in ("request_id", "chat_id", "id"):
                    v = kwargs.get(k)
                    if isinstance(v, str) and v.strip():
                        request_id = v.strip()
                        break
            # fallback to chat_id as request_id when POSTing
            fallback_request_id = request_id or self._extract_chat_id(body) or kwargs.get("chat_id")
            if isinstance(fallback_request_id, str) and not fallback_request_id.strip():
                fallback_request_id = None

            chat_id = self._extract_chat_id(body) or kwargs.get("chat_id")
            if isinstance(chat_id, str) and not chat_id.strip():
                chat_id = None

            message_preview = self._extract_message_content(body)
            user_query = self._extract_user_query(body)

            # Check if body already contains a ground truth command
            gt_cmd = self._find_ground_truth_command(body)

            # Fetch existing ground truths for panel display (also needed to show after POST)
            existing_ground_truths: list[dict] = []
            lookup_id = request_id or fallback_request_id
            if lookup_id:
                try:
                    rows = self._fetch_evaluations(lookup_id)
                    existing_ground_truths = self._filter_ground_truths(rows)
                except Exception:
                    existing_ground_truths = []

            if gt_cmd is not None:
                # need a request_id to POST — fall back to chat_id
                post_request_id = request_id or fallback_request_id
                if not post_request_id:
                    # cannot POST without identifier — show panel with error hint
                    base = self.valves.observability_endpoint.rstrip("/")
                    return (
                        f"Cannot save ground truth: no request_id or chat_id found in message.\n\n"
                        f"Detected text: `{gt_cmd['text'][:200]}`\n\n"
                        f"Endpoint: `{base}`\n"
                        + self._render_panel(request_id, chat_id, message_preview, user_query, existing_ground_truths)
                    )
                text = gt_cmd["text"]
                extracted_tags = gt_cmd.get("tags") or []
                # merge any explicit tags from body top-level if not already included
                if isinstance(body, dict):
                    tv = body.get("tags")
                    if isinstance(tv, list):
                        for t in tv:
                            tt = str(t).lstrip("#").strip()
                            if tt and tt not in extracted_tags:
                                extracted_tags.append(tt)
                all_tags = ["ground_truth"] + extracted_tags

                payload: dict = {
                    "request_id": post_request_id,
                    "user_query": user_query,
                    "comment": f"[GROUND_TRUTH] {text}".strip(),
                    "tags": all_tags,
                    "ground_truth": text,
                    "user_id": __user__.get("id") if isinstance(__user__, dict) else None,
                    "model": body.get("model", "") if isinstance(body, dict) else "",
                    "timestamp": time.time(),
                    "chat_id": chat_id,
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
                                        "description": "Ground truth saved" if ok else f"Ground truth failed: {msg[:80]}",
                                        "done": True,
                                    },
                                }
                            )
                    except Exception:
                        pass

                if ok:
                    # re-fetch to include newly saved entry; if search lags, merge locally
                    try:
                        rows = self._fetch_evaluations(post_request_id)
                        new_gts = self._filter_ground_truths(rows)
                        if new_gts:
                            existing_ground_truths = new_gts
                        else:
                            existing_ground_truths = [*existing_ground_truths, {"comment": f"[GROUND_TRUTH] {text}", "tags": all_tags, "ground_truth": text, "created_at": "just now"}]
                    except Exception:
                        existing_ground_truths = [*existing_ground_truths, {"comment": f"[GROUND_TRUTH] {text}", "tags": all_tags, "ground_truth": text, "created_at": "just now"}]
                    # spec-required confirmation line
                    preview = text[:500] + ("…" if len(text) > 500 else "")
                    confirmation = f"Ground truth saved for {post_request_id} (> {preview})\n\nView in dashboard: http://127.0.0.1:3000/dashboard/observability"
                    # include panel for context as well
                    panel = self._render_panel(post_request_id, chat_id, message_preview, user_query, existing_ground_truths)
                    return confirmation + "\n\n---\n\n" + panel
                else:
                    return (
                        f"Failed to save ground truth: {msg}\n\n"
                        f"Payload attempted: ground_truth=`{text[:200]}` tags={all_tags}\n\n"
                        + self._render_panel(post_request_id, chat_id, message_preview, user_query, existing_ground_truths)
                    )

            return self._render_panel(request_id or fallback_request_id, chat_id, message_preview, user_query, existing_ground_truths)

        except Exception as e:
            base = self.valves.observability_endpoint.rstrip("/")
            return (
                f"Error loading ground truth panel: {e}\n\n"
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
