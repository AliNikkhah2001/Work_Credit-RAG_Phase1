import os, sys
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HOME"] = "/tmp/hf_clean"
os.environ["HF_HUB_CACHE"] = "/tmp/hf_clean"
sys.path.insert(0, "/workspace/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager")
device = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "NONE" else None
from kb_manager.reranker import get_reranker
CANDS = [
    {"id": "rel", "content": "اعتبارسنجی فرآیندی بانکی است.", "hybrid_score": 0.1},
    {"id": "irr", "content": "طرز تهیه قرمه‌سبزی.", "hybrid_score": 0.9},
]
r = get_reranker(model_name="Qwen/Qwen3-Reranker-0.6B", device=device)
out = r.rerank("اعتبارسنجی چیست", [dict(c) for c in CANDS], top_k=2)
print(f"device={device!r}:", [(c["id"], round(c["rerank_score"], 4)) for c in out], flush=True)
