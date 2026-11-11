"""E2E: model can list all colors and full score/grade tables per subspace."""
from __future__ import annotations

import json
import urllib.request

ORCH = "http://127.0.0.1:8100/v1/chat/completions"
COLORS = ["آبی", "سبز", "زرد", "نارنجی", "قرمز"]
GRADES = [
    "A1", "A2", "A3", "B1", "B2", "B3",
    "C1", "C2", "C3", "D1", "D2", "D3",
    "E1", "E2", "E3",
]


def chat(q: str, filter_path: str, rid: str) -> str:
    body = {
        "model": "ics-helper-agent",
        "messages": [{"role": "user", "content": q}],
        "request_id": rid,
        "stream": False,
        "filter_path": filter_path,
    }
    req = urllib.request.Request(
        ORCH,
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        d = json.loads(resp.read().decode())
    return (d.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""


def body_after_greeting(ans: str) -> str:
    for sep in ("کمک می‌کنم.", "کمک ميکنم.", "\n\n"):
        if sep in ans:
            return ans.split(sep, 1)[-1]
    return ans


def main() -> int:
    cases = [
        {
            "id": "cheque-colors",
            "q": "در مدل اعتبارسنجی چک چه رنگ‌هایی برای امتیاز تعریف شده و هر رنگ مربوط به چه گروه رتبه‌ای است؟",
            "fp": "گزارش اعتبارسنجی چک",
            "must_colors": COLORS,
            "must_any_grades": ["A1", "B1", "C1", "D1", "E1"],
            "must_not": ["۶۶۰", "۶۸۰", "۹۰۰"],
        },
        {
            "id": "cheque-full-table",
            "q": "لطفا جدول کامل امتیاز و رتبه و رنگ مدل چک را فهرست کن.",
            "fp": "گزارش اعتبارسنجی چک",
            "must_grades": GRADES,
            "must_colors": COLORS,
            "must_any": ["۱۰۰", "100", "۹۵", "95"],
        },
        {
            "id": "person-colors",
            "q": "رنگ‌های جدول امتیاز اشخاص حقیقی کدام‌اند و بازه امتیازی هر رنگ چیست؟",
            "fp": "اشخاص حقیقی/اعتبارسنجی تسهیلات",
            "must_colors": COLORS,
            "must_any": ["۹۰۰", "900", "۲۵۰", "250", "۶۸۰", "680"],
            "must_not": ["۱ تا ۱۰۰", "بازه ۱ تا ۱۰۰"],
        },
        {
            "id": "person-full-table",
            "q": "همه رتبه‌های A1 تا E3 مدل حقیقی را با بازه امتیاز و رنگ بگو.",
            "fp": "اشخاص حقیقی/اعتبارسنجی تسهیلات",
            "must_grades": GRADES,
            "must_colors": COLORS,
        },
        {
            "id": "legal-full-table",
            "q": "جدول کامل رنگ و رتبه و بازه امتیاز مدل حقوقی را لیست کن.",
            "fp": "اشخاص حقوقی/اعتبارسنجی تسهیلات",
            "must_grades": GRADES,
            "must_colors": COLORS,
            "must_any": ["۶۵۰", "650", "۶۱۹", "619"],
        },
        {
            "id": "cheque-vs-person-scale",
            "q": "آیا رنگ قرمز در چک همان بازه امتیازی رنگ قرمز در حقیقی است؟",
            "fp": "گزارش اعتبارسنجی چک",
            "must_any": ["خیر", "متفاوت", "۱۰۰", "100", "۲۵۰", "250", "۹۰۰", "900"],
        },
    ]
    failures = 0
    for c in cases:
        try:
            ans = chat(c["q"], c["fp"], c["id"])
        except Exception as exc:
            print(f"FAIL {c['id']}: {exc}")
            failures += 1
            continue
        body = body_after_greeting(ans)
        print(f"\n==== {c['id']} ====")
        print("Q:", c["q"])
        print("A:", ans.replace("\n", " | ")[:900])
        ok = True
        for color in c.get("must_colors") or []:
            if color not in body:
                print(f"  missing color {color!r}")
                ok = False
        for g in c.get("must_grades") or []:
            if g not in body:
                print(f"  missing grade {g!r}")
                ok = False
        need_any_g = c.get("must_any_grades") or []
        if need_any_g and not any(g in body for g in need_any_g):
            print(f"  none of grades {need_any_g}")
            ok = False
        need_any = c.get("must_any") or []
        if need_any and not any(x in body for x in need_any):
            print(f"  none of {need_any}")
            ok = False
        for bad in c.get("must_not") or []:
            if bad in body:
                print(f"  unexpected {bad!r}")
                ok = False
        print("PASS" if ok else "FAIL")
        if not ok:
            failures += 1
    print(f"\nSummary failures={failures}/{len(cases)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
