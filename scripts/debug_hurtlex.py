import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "components" / "guardrails" / "src"))
from work_rag_guardrails.actions import normalize_persian, load_hurtlex, load_swear  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "components" / "orchestrator" / "src"

queries = [
    "چگونه می‌توانم گزارش اعتباری خود را دریافت کنم؟",
    "امتیاز اعتباری چگونه محاسبه می‌شود؟",
    "برای دریافت تسهیلات بانکی چه مدارکی لازم است؟",
    "چک برگشتی چه تاثیری بر رتبه اعتباری دارد؟",
]

out = []
for q in queries:
    n = normalize_persian(q)
    hits = [w for w in load_hurtlex() if len(w) > 2 and re.search(rf"\b{re.escape(w)}\b", n)]
    swear_hits = [w for w in load_swear() if w and re.search(rf"\b{re.escape(w)}\b", n)]
    out.append({"query": q, "normalized": n, "hurtlex_hits": hits, "swear_hits": swear_hits})

(ROOT / "hurtlex_debug.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("written hurtlex_debug.json")
