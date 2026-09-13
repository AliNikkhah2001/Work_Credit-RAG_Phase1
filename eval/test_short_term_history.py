"""Short-term history test — does the RAG agent remember prior turns?

Two scenarios modeled on how a real user chats in Persian via Open WebUI:
  A) Separate requests (Open WebUI sends each user message as its own
     /v1/chat/completions call unless conversation history is threaded in).
  B) One request containing multiple prior turns in `messages`.

First we must discover whether the agent answered with the remembered token
in Persian.
"""

from __future__ import annotations

import json

import httpx

ORCH_URL = "http://127.0.0.1:8100/v1/chat/completions"
MODEL = "gemma-4-31b"


def chat(messages: list[dict], label: str) -> str:
    r = httpx.post(ORCH_URL, json={
        "model": MODEL,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 256,
    }, timeout=180)
    r.raise_for_status()
    j = r.json()
    answer = j["choices"][0]["message"]["content"]
    print(f"\n### {label}\n messages: {[m['content'][:60] for m in messages]}\n answer: {answer[:300]}\n")
    return answer


REMEMBER_TOKEN = "علی"
T1 = "سلام! اسم من علی است و برای دریافت وام، مشاوره اعتباری می‌خواهم."
T2 = "اسم من چیست؟"


def check(tag: str, answer: str, expect: str) -> None:
    hit = expect in answer
    print(f"[{tag}] remembers '{expect}'? -> {hit}")
    return hit


if __name__ == "__main__":
    results = {}
    # Scenario A: two independent requests
    a1 = chat([{"role": "user", "content": T1}], "A. request #1 (introduce self)")
    a2 = chat([{"role": "user", "content": T2}], "A. request #2 (ask name)")
    results["A_stateless"] = check("A", a2, REMEMBER_TOKEN)

    # Scenario B: single request with prior turns threaded in messages
    b = chat([
        {"role": "user", "content": T1},
        {"role": "assistant", "content": "سلام علی جان! خوش آمدید."},
        {"role": "user", "content": T2},
    ], "B. one request, prior turns in messages")

    # Ground truth: does the raw model even answer 'علی' when told in the request body?
    g = chat([
        {"role": "user", "content": T1},
        {"role": "assistant", "content": "سلام علی جان! خوش آمدید."},
        {"role": "user", "content": T2},
    ], "C. control (same as B, to confirm raw-message behavior)")

    print("\n=== RESULTS ===")
    print(json.dumps({
        "A_separate_requests": results.get("A_stateless"),
        "B_single_request_with_history": REMEMBER_TOKEN in b,
        "C_control": REMEMBER_TOKEN in g,
    }, ensure_ascii=False, indent=2))