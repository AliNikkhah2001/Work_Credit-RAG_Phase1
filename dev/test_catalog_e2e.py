"""E2E questions for non-score ضمیمه catalogs."""
from __future__ import annotations

import json
import urllib.request

ORCH = "http://127.0.0.1:8100/v1/chat/completions"


def chat(q: str, filter_path: str | None, rid: str) -> str:
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
    return (d.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""


def body(ans: str) -> str:
    for sep in ("کمک می‌کنم.", "کمک ميکنم.", "\n\n"):
        if sep in ans:
            return ans.split(sep, 1)[-1]
    return ans


def main() -> int:
    cases = [
        {
            "id": "shareholders-list",
            "q": "سهامداران شرکت اعتبارسنجی ایران را نام ببر؛ چند بانک بین آن‌هاست؟",
            "fp": None,
            "must_any": ["بانک رفاه", "بانک تجارت", "بانک", "بیمه"],
        },
        {
            "id": "shareholders-type",
            "q": "آیا بانک مرکزی جزء سهامداران اعتبارسنجی ایران است؟",
            "fp": "پایگاه دانش عمومی",
            "must_any": ["بانک مرکزی", "بله", "سهامدار"],
        },
        {
            "id": "loans-types",
            "q": "چه نوع وام‌هایی در فهرست عناوین وام‌ها وجود دارد؟",
            "fp": "اشخاص حقیقی/اعتبارسنجی تسهیلات",
            "must_any": ["ازدواج", "قرض‌الحسنه", "قرض الحسنه", "نقدی", "خرید کالا", "بدون ضامن"],
        },
        {
            "id": "loans-lookup",
            "q": "در فهرست عناوین وام‌ها، وام ازدواج بانک تجارت هست یا نه؟",
            "fp": "اشخاص حقیقی/اعتبارسنجی تسهیلات",
            "must_all_any": [["ازدواج"], ["تجارت"], ["بله", "هست", "وجود دارد"]],
        },
        {
            "id": "providers-banks",
            "q": "شرکت اعتبارسنجی ایران داده را از چه تامین‌کنندگانی می‌گیرد؟ آیا بانک هم هست؟",
            "fp": "اشخاص حقوقی/عضویت در پایگاه داده اعتباری به عنوان تامین کننده اطلاعات",
            "must_any": ["بانک", "صندوق", "لندتک", "لیزینگ"],
        },
        {
            "id": "providers-neobank",
            "q": "در فهرست تامین‌کنندگان دیتای اعتبارسنجی ایران، کدام‌ها نئوبانک یا موبایل‌بانک دارند؟",
            "fp": "اشخاص حقوقی/عضویت در پایگاه داده اعتباری به عنوان تامین کننده اطلاعات",
            "must_any": ["نئو", "موبایل", "بانک"],
        },
        {
            "id": "consumers-landtech",
            "q": "استفاده‌کنندگان گزارش از نوع لندتک چه شرکت‌هایی هستند؟ چند مورد مثال بزن.",
            "fp": "اشخاص حقیقی/گزارش اعتبارسنجی مشتریان من (مرتبط با کسب‌وکارها)",
            "must_any": ["لندتک", "لندو", "دیجی", "قسطا", "اسنپ", "بالون", "تالون", "ازکی"],
        },
        {
            "id": "consumers-reseller",
            "q": "آیا قرارداد ریسلر در فهرست استفاده‌کنندگان گزارش وجود دارد؟",
            "fp": None,
            "must_any": ["ریسلر", "بله", "فروش"],
        },
        {
            "id": "consumers-negative",
            "q": "آیا شرکت فرضی «آژانس فضایی مریخ» استفاده‌کننده گزارش اعتبارسنجی است؟",
            "fp": None,
            "must_any": ["خیر", "نیست", "یافت نشد", "وجود ندارد", "ندارد", "وجود ندارد", "اطلاعاتی", "ذکر نشده", "نامی"],
        },
    ]
    failures = 0
    for c in cases:
        try:
            ans = chat(c["q"], c.get("fp"), c["id"])
        except Exception as exc:
            print(f"FAIL {c['id']}: {exc}")
            failures += 1
            continue
        b = body(ans)
        print(f"\n==== {c['id']} ====")
        print("Q:", c["q"])
        print("A:", ans.replace("\n", " | ")[:850])
        if "must_all_any" in c:
            ok = all(any(x in b for x in group) for group in c["must_all_any"])
            if not ok:
                print("  missing groups", c["must_all_any"])
        else:
            ok = any(x in b for x in c["must_any"])
            if not ok:
                print("  missing any of", c["must_any"])
        print("PASS" if ok else "FAIL")
        if not ok:
            failures += 1
    print(f"\nSummary failures={failures}/{len(cases)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
