"""Mock Gemma LLM Inference Manager - stands in for the H200 server (port 9000).

OpenAI-compatible endpoints used by the MVP path:
  GET  /health
  GET  /v1/models
  POST /v1/chat/completions

Generation strategy: extractive grounding - parses the orchestrator's context block
and returns the best-matching chunk content as the answer, so the end-to-end
pipeline can be validated without GPUs.
"""
from __future__ import annotations

import re
import time
import uuid

from fastapi import FastAPI

app = FastAPI(title="Mock Gemma Manager", version="0.1.0")

STOP = set("از در به و با برای که این آن را شد است هستند بودند می باشد شود هر یا اگر ولی تا بر مانند خود کنید گردد شود باید یک the a an is are was be in on at to for of and or".split())


def _tokens(text: str) -> set:
    text = text.lower()
    text = (text.replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")
            .replace("\u200c", " "))
    words = re.findall(r"[a-zA-Z\u0600-\u06FF\d]{2,}", text)
    return {w for w in words if w not in STOP}


def _parse_context(user_msg: str):
    """Extract numbered chunks + question from orchestrator's build_context output."""
    chunks = re.findall(
        r"\[(\d+)\]\s*Title:\s*(.*?)\n(?:Heading:\s*(.*?)\n)?Content:\s*(.*?)(?=\n\n\[\d+\]|\n\nQuestion:|$)",
        user_msg, re.S)
    qmatch = re.search(r"Question:\s*(.*)$", user_msg, re.S)
    question = qmatch.group(1).strip() if qmatch else user_msg.strip()
    return [{"idx": int(c[0]), "title": c[1].strip(), "heading": (c[2] or "").strip(),
             "content": c[3].strip()} for c in chunks], question


@app.get("/health")
async def health():
    return {"status": "ok", "models_loaded": 1, "gpus": [{"id": 0, "mock": True}]}


@app.get("/v1/models")
async def models():
    return {"object": "list", "data": [{"id": "gemma-4-31b", "object": "model"}]}


@app.post("/v1/chat/completions")
async def chat(body: dict):
    t0 = time.time()
    msgs = body.get("messages", [])
    user_msg = next((m["content"] for m in reversed(msgs) if m.get("role") == "user"), "")
    chunks, question = _parse_context(user_msg)
    qtok = _tokens(question)

    best, best_score = None, 0.0
    for c in chunks:
        ctok = _tokens(c["content"] + " " + c["title"])
        score = len(qtok & ctok) / max(len(qtok), 1)
        if score > best_score:
            best, best_score = c, score

    if best and best_score > 0:
        ans = (f"بر اساس منابع دانش‌نامه، پاسخ پرسش شما: "
               f"{best['content'][:600]} (منبع: [{best['idx']}] {best['title']})")
    elif chunks:
        ans = ("با توجه به منابع موجود، اطلاعات کافی برای پاسخ دقیق به این پرسش "
               "در دانش‌نامه یافت نشد. لطفاً پرسش را واضح‌تر بپرسید.")
    else:
        ans = "پاسخ بر اساس دانش‌نامه: " + question[:100]

    return {
        "id": f"chatcmpl-mock-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "model": body.get("model", "gemma-4-31b"),
        "created": int(time.time()),
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": ans},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": len(user_msg.split()),
            "completion_tokens": len(ans.split()),
            "total_tokens": len(user_msg.split()) + len(ans.split()),
        },
        "mock_latency_ms": round((time.time() - t0) * 1000, 1),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=9000, log_level="info")
