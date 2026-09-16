"""Rule-based Persian query buckets for per-category retrieval analysis.

Buckets are lexical/heuristic (no model): length, interrogative, entities
(bank names), topics (cheque/score/rank/loan/report/tax/insurance/customs),
numeric content. Applied post-baseline in analyze (reads metrics_by_query).
"""
import re

BANKS = ["بانک ملت", "بانک ملی", "بانک صادرات", "بانک تجارت", "پارسیان",
         "بانک سپه", "مسکن", "کشاورزی", "رفاه", "بانک شهر", "بانک دی",
         "سینا", "اقتصاد نوین", "کارآفرین", "سامان", "پاسارگاد",
         "آینده", "گردشگری", "خاورمیانه", "سرمایه"]
TOPICS = {
    "cheque": ["چک", "برگشتی", "سوء اثر", "دسته‌چک"],
    "score": ["امتیاز", "رتبه", "اسکور"],
    "loan": ["وام", "تسهیلات", "قسط", "بازپرداخت"],
    "report": ["گزارش", "استعلام"],
    "tax": ["مالیات", "مالیاتی"],
    "insurance": ["بیمه", "تامین اجتماعی", "تأمین اجتماعی"],
    "customs": ["گمرک", "گمرکی"],
    "court": ["دادگاه", "محکومیت", "قضایی", "قوه"],
    "bank_ops": ["شعبه", "حساب", "کارت"],
}
INTERROGATIVE = ["آیا", "چگونه", "چطور", "چرا", "چه", "کی", "کجا", "چقدر",
                 "کدام", "چند", "مگر", "میشه", "میشود", "می‌شود"]


def qtoks(s):
    return re.findall(r"[\w\u0600-\u06FF]+", (s or ""))


def classify_query(q: str) -> dict:
    toks = qtoks(q)
    n = len(toks)
    buckets = []
    buckets.append("short" if n <= 10 else ("long" if n > 25 else "medium"))
    if toks and toks[0] in INTERROGATIVE:
        buckets.append("interrogative")
    if any(b in q for b in BANKS):
        buckets.append("entity_bank")
    if re.search(r"[0-9۰-۹]", q):
        buckets.append("numeric")
    for topic, kws in TOPICS.items():
        if any(k in q for k in kws):
            buckets.append(f"topic_{topic}")
    return {"n_tokens": n, "buckets": buckets}
