import os, sys
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HOME"] = "/tmp/hf_clean"
os.environ["HF_HUB_CACHE"] = "/tmp/hf_clean"
sys.path.insert(0, "/workspace/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager")
import kb_manager.reranker as R
from kb_manager.reranker import get_reranker, FlagEmbeddingReranker

# 1. defaults unchanged: no env -> default MiniLM via CrossEncoderReranker
os.environ.pop("KB_RERANKER_MODEL", None)
r = get_reranker()
print("default:", repr(r), "| is CrossEncoder:", type(r).__name__ == "CrossEncoderReranker")

# 2. unknown id falls back to crossencoder path
r2 = get_reranker(model_name="some-unknown-model")
print("unknown:", repr(r2), "| is CrossEncoder:", type(r2).__name__ == "CrossEncoderReranker")

# 3. exercise 'flag' branch via monkeypatched spec (m3 weights, encoder-only FlagReranker)
orig = R.resolve_reranker_spec
R.resolve_reranker_spec = lambda name: {"loader": "flag", "needs_trust_remote_code": False}
try:
    rf = FlagEmbeddingReranker(model_name="BAAI/bge-reranker-v2-m3")
    out = rf.rerank("اعتبارسنجی چیست", [
        {"id": "rel", "content": "اعتبارسنجی فرآیندی بانکی است.", "hybrid_score": 0.1},
        {"id": "irr", "content": "طرز تهیه قرمه‌سبزی.", "hybrid_score": 0.9},
    ], top_k=2)
    print("flag-branch:", [(c["id"], round(c["rerank_score"], 3)) for c in out],
          "sensible:", out[0]["id"] == "rel", "ms:", round(rf.last_rerank_ms, 1))
finally:
    R.resolve_reranker_spec = orig

# 4. explicit device="cpu" passthrough on small model
rc = get_reranker(model_name="Qwen/Qwen3-Reranker-0.6B", device="cpu")
out = rc.rerank("اعتبارسنجی چیست", [
    {"id": "rel", "content": "اعتبارسنجی فرآیندی بانکی است.", "hybrid_score": 0.1},
    {"id": "irr", "content": "طرز تهیه قرمه‌سبزی.", "hybrid_score": 0.9},
], top_k=2)
print("device=cpu:", [(c["id"], round(c["rerank_score"], 3)) for c in out],
      "sensible:", out[0]["id"] == "rel")

# 5. pool override + score_key respected
rp = get_reranker(model_name="Qwen/Qwen3-Reranker-0.6B")
cands = [{"id": str(i), "content": f"متن آزمایشی شماره {i} درباره اعتبارسنجی بانکی", "hybrid_score": float(i)} for i in range(6)]
out = rp.rerank("اعتبارسنجی", cands, top_k=2, pool=4)
print("pool=4 top_k=2 ->", len(out) == 2, "| all floats:", all(isinstance(c["rerank_score"], float) for c in out))
