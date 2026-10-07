from pathlib import Path

path = Path("README.md")
content = path.read_text()

update_text = """
## 🚀 Production Scaling (1 Million+ Users)
For deploying this RAG engine to millions of concurrent users, the native Python execution (FastAPI locking) and `RankBM25` memory constraints become bottlenecks.
We have architected a **Million-User Scale Plan** that replaces `RankBM25` with SPLADE, migrates ML execution to NVIDIA Triton + TensorRT, and introduces Semantic Caching.

See the complete architectural design and scaling strategy here:
👉 [**Million-User Scale Plan**](million-user-scale-plan.md)
"""

if "Million-User Scale Plan" not in content:
    content = content + "\n" + update_text
    path.write_text(content)
    print("README updated with Scale Plan")
    
    # Also copy the artifact into the project directory so the link works!
    import shutil
    shutil.copy("/Users/alinikkhah/.gemini/antigravity/brain/47bebd39-9906-4294-834a-c702b7cc71bc/million-user-scale-plan.md", "million-user-scale-plan.md")
    print("Scale plan file copied to project root")
else:
    print("Already updated")
