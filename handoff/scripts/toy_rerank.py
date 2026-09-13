import os, sys, time, json
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HOME", "/tmp/hf_clean")
os.environ.setdefault("HF_HUB_CACHE", "/tmp/hf_clean")
model = sys.argv[1]
cls = sys.argv[2]  # FlagReranker | FlagLLMReranker | LayerWise
extra = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
import FlagEmbedding
print("FlagEmbedding attrs:", [a for a in dir(FlagEmbedding) if "Rerank" in a], flush=True)
from FlagEmbedding import FlagReranker
try:
    from FlagEmbedding import FlagLLMReranker, LayerWiseFlagLLMReranker
except Exception as e:
    print("llm import fail:", e, flush=True)
    FlagLLMReranker = None; LayerWiseFlagLLMReranker = None
QUERY = "اعتبارسنجی چیست"
REL = "اعتبارسنجی فرآیندی است که در آن اهلیت اعتباری مشتریان بانک با بررسی سابقه بازپرداخت، درآمد و بدهی‌ها ارزیابی می‌شود."
IRR = "طرز تهیه قرمه‌سبزی: ابتدا سبزی را سرخ کنید سپس لوبیا و گوشت را اضافه کنید و بگذارید آرام بپزد."
t0 = time.time()
if cls == "FlagReranker":
    r = FlagReranker(model, use_fp16=False, **extra)
elif cls == "FlagLLMReranker":
    r = FlagLLMReranker(model, use_fp16=False, **extra)
elif cls == "LayerWise":
    r = LayerWiseFlagLLMReranker(model, use_fp16=False, **extra)
else:
    raise SystemExit("bad cls")
t1 = time.time()
print(f"LOADED in {t1-t0:.1f}s: {type(r)}", flush=True)
scores = r.compute_score([[QUERY, REL], [QUERY, IRR]])
t2 = time.time()
print(f"SCORED in {t2-t1:.1f}s total {t2-t0:.1f}s", flush=True)
print(f"scores rel={scores[0]!r} irr={scores[1]!r} sensible={scores[0] > scores[1]}", flush=True)
