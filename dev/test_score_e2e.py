"""E2E score Q&A across cheque / person / legal subspaces."""
from __future__ import annotations

import json
import re
import urllib.request

ORCH = "http://127.0.0.1:8100/v1/chat/completions"


def chat(q: str, filter_path: str | None = None, rid: str = "score-e2e") -> tuple[str, dict]:
    body = {
        "model": "ics-helper-agent",
        "messages": [{"role": "user", "content": q}],
        "request_id": rid,
        "stream": False,
    }
    if filter_path:
        body["filter_path"] = filter_path
    req = urllib.request.Request(
        ORCH,
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        d = json.loads(resp.read().decode())
    content = (d.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
    return content, d.get("rag") or {}


def has_any(text: str, needles: list[str]) -> list[str]:
    return [n for n in needles if n in text]


def main() -> int:
    cases = [
        {
            "id": "cheque-num",
            "q": "در گزارش اعتبارسنجی چک، امتیاز ۹۲ یعنی چه رتبه و رنگی؟",
            "fp": "گزارش اعتبارسنجی چک",
            "must": ["A2", "آبی"],
            "must_not": ["۶۶۰", "660", "۶۷۹", "679", "حقوقی"],
        },
        {
            "id": "cheque-letter",
            "q": "رتبه A1 در اعتبارسنجی چک چه بازه امتیازی و رنگی دارد؟",
            "fp": "گزارش اعتبارسنجی چک",
            "must": ["A1", "آبی"],
            "must_not": ["۶۸۰", "680", "۹۰۰", "حقوقی"],
        },
        {
            "id": "cheque-bad-color",
            "q": "آیا رنگ بنفش در جدول امتیاز چک وجود دارد؟",
            "fp": "گزارش اعتبارسنجی چک",
            "must_not_all_false_positive": True,
            "reject_patterns": [r"بله.*بنفش", r"رنگ بنفش وجود دارد"],
            "accept_any": ["وجود ندارد", "نیست", "آبی", "سبز", "زرد", "نارنجی", "قرمز", "پنج رنگ"],
        },
        {
            "id": "person-num",
            "q": "در اعتبارسنجی تسهیلات اشخاص حقیقی، امتیاز ۶۷۰ چه رتبه و رنگی است؟",
            "fp": "اشخاص حقیقی/اعتبارسنجی تسهیلات",
            "must": ["A2", "آبی"],
            # ignore canned greeting that mentions چک‌ها
            "must_not": ["۹۰ تا ۹۵", "بازه ۱ تا ۱۰۰"],
        },
        {
            "id": "person-letter",
            "q": "رتبه B1 در مدل حقیقی چه بازه امتیاز و رنگی دارد؟",
            "fp": "اشخاص حقیقی/اعتبارسنجی تسهیلات",
            "must": ["B1", "سبز"],
            "must_not": ["۸۰ تا ۸۵", "۷۵ تا ۸۰"],
            "must_body": ["۶۲۰", "۶۳۹", "620", "639"],
            "must_body_any": True,
        },
        {
            "id": "person-bad-letter",
            "q": "رتبه F9 در مدل حقیقی یعنی چه؟",
            "fp": "اشخاص حقیقی/اعتبارسنجی تسهیلات",
            "accept_any": ["وجود ندارد", "نیست", "نامعتبر", "تعریف نشده", "A1", "E3", "نداریم", "یافت نشد", "یافت نشد", "پاسخی"],
            "must_not": ["امتیاز F9 برابر"],
        },
        {
            "id": "legal-num",
            "q": "امتیاز ۶۱۰ برای شخص حقوقی چه رتبه و رنگی است؟",
            "fp": "اشخاص حقوقی/اعتبارسنجی تسهیلات",
            "must": ["B1", "سبز"],
            "must_not": ["۹۰ تا ۹۵", "بازه ۱ تا ۱۰۰"],
        },
        {
            "id": "legal-cross-scale",
            "q": "آیا امتیاز ۹۲ در مدل حقوقی یعنی رتبه A2 آبی مثل چک؟",
            "fp": "اشخاص حقوقی/اعتبارسنجی تسهیلات",
            "accept_any": ["خیر", "نیست", "مقیاس", "۲۵۰", "۹۰۰", "250", "900", "چک"],
            "must_not": ["بله، امتیاز ۹۲ در مدل حقوقی برابر A2"],
        },
        {
            "id": "cheque-cross-scale",
            "q": "امتیاز ۷۰۰ در گزارش چک چه رنگی است؟",
            "fp": "گزارش اعتبارسنجی چک",
            "accept_any": ["خارج", "نیست", "۱۰۰", "100", "معتبر نیست", "وجود ندارد", "بازه"],
            "must_not": ["آبی است", "رتبه A"],
        },
    ]

    failures = 0
    for c in cases:
        try:
            ans, rag = chat(c["q"], c.get("fp"), rid=c["id"])
        except Exception as exc:
            print(f"FAIL {c['id']}: request error {exc}")
            failures += 1
            continue
        print(f"\n==== {c['id']} ====")
        print("Q:", c["q"])
        print("A:", ans.replace("\n", " | ")[:700])
        ok = True
        for m in c.get("must") or []:
            if m not in ans:
                print(f"  missing must={m!r}")
                ok = False
        # Evaluate factual constraints on body after greeting
        body = ans
        for sep in ("کمک می‌کنم.", "کمک ميکنم.", "\n\n"):
            if sep in body:
                body = body.split(sep, 1)[-1]
                break
        for m in c.get("must_not") or []:
            if m in body:
                print(f"  unexpected must_not={m!r}")
                ok = False
        body_needles = c.get("must_body") or []
        if body_needles:
            hits = has_any(body, body_needles)
            if c.get("must_body_any"):
                if not hits:
                    print(f"  none of must_body matched: {body_needles}")
                    ok = False
            else:
                for m in body_needles:
                    if m not in body:
                        print(f"  missing must_body={m!r}")
                        ok = False
        accept = c.get("accept_any") or []
        if accept and not has_any(ans, accept):
            print(f"  none of accept_any matched: {accept}")
            ok = False
        for pat in c.get("reject_patterns") or []:
            if re.search(pat, ans):
                print(f"  hit reject_pattern={pat!r}")
                ok = False
        print("PASS" if ok else "FAIL")
        if not ok:
            failures += 1
    print(f"\nSummary failures={failures}/{len(cases)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
