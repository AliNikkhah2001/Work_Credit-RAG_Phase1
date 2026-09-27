import os, sys
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HOME"] = "/tmp/hf_clean"
os.environ["HF_HUB_CACHE"] = "/tmp/hf_clean"
sys.path.insert(0, "/workspace/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager")
from kb_manager.reranker import get_reranker
r = get_reranker(model_name="jinaai/jina-reranker-v3", batch_size=1)
print("pad_token:", r._tokenizer if False else "(lazy)")
r._ensure_model()
print("model:", type(r._model).__name__, "pad_token:", r._tokenizer.pad_token, "eos:", r._tokenizer.eos_token)
out = r.rerank("اعتبارسنجی چیست", [
    {"id": "rel", "content": "اعتبارسنجی فرآیندی بانکی است.", "hybrid_score": 0.5},
    {"id": "irr", "content": "طرز تهیه قرمه‌سبزی.", "hybrid_score": 0.9},
], top_k=2)
for c in out:
    print(f"  id={c['id']} rerank_score={c['rerank_score']!r}")
print("batch_size=1 OK")
