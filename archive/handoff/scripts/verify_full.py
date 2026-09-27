import os, sys, time
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HOME"] = "/tmp/hf_clean"
os.environ["HF_HUB_CACHE"] = "/tmp/hf_clean"
sys.path.insert(0, "/workspace/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager")
model = sys.argv[1]
from kb_manager.reranker import get_reranker
QUERY = "اعتبارسنجی چیست"
cands = [
    {"id": "rel", "content": "اعتبارسنجی فرآیندی است که در آن اهلیت اعتباری مشتریان بانک با بررسی سابقه بازپرداخت، درآمد و بدهی‌ها ارزیابی می‌شود.", "hybrid_score": 0.5},
    {"id": "irr", "content": "طرز تهیه قرمه‌سبزی: ابتدا سبزی را سرخ کنید سپس لوبیا و گوشت را اضافه کنید و بگذارید آرام بپزد.", "hybrid_score": 0.9},
    {"id": "mid", "content": "بانک‌ها برای اعطای تسهیلات معمولا مدارک شناسایی و گردش حساب مشتری را درخواست می‌کنند.", "hybrid_score": 0.7},
]
r = get_reranker(model_name=model)
t0 = time.time()
out = r.rerank(QUERY, [dict(c) for c in cands], top_k=3)
dt = time.time() - t0
for c in out:
    print(f"  id={c['id']} rerank_score={c['rerank_score']!r}")
s = {c["id"]: c["rerank_score"] for c in out}
print(f"rel>irr: {s['rel'] > s['irr']}  total_time={dt:.1f}s")
