import re
from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()

# Add import
import_stmt = "from kb_manager.settings import load_settings\n"
if "from kb_manager.settings" not in content:
    content = content.replace("from kb_manager.dense import DenseSemanticIndex", import_stmt + "from kb_manager.dense import DenseSemanticIndex")

# Replace defaults logic inside search_knowledge_base
content = re.sub(
    r'_KEYWORD_BOOST_DEFAULT = float\(os\.getenv\("KB_KEYWORD_BOOST", "3\.0"\)\)',
    r'_KEYWORD_BOOST_DEFAULT = load_settings().keyword_boost',
    content
)

# Replace final = reranked_results[:top_k]
old_final = "    # --- Step 7: Final top-k ---\n    final = reranked_results[:top_k]"
new_final = """    # --- Step 7: Final top-k (DYNAMIC THRESHOLDING) ---
    settings = load_settings()
    final = []
    for r in reranked_results:
        if r.rerank_score >= settings.min_relevance_score:
            final.append(r)
    
    # Fallback to Top-1 if nothing passes the threshold but results exist
    if not final and reranked_results:
        final = [reranked_results[0]]
        
    # Cap at top_k if dynamic filter is still too large
    if len(final) > top_k:
        final = final[:top_k]"""
content = content.replace(old_final, new_final)

# Fix _RERANK_FUSION_ALPHA reference
content = re.sub(
    r'_alpha = float\(os\.getenv\("KB_RERANK_FUSION_ALPHA", str\(_RERANK_FUSION_ALPHA\)\)\)',
    r'_alpha = load_settings().fusion_alpha',
    content
)

# Fix keyword_boost fallback
content = content.replace("keyword_boost = keyword_boost if keyword_boost is not None else _KEYWORD_BOOST_DEFAULT", "keyword_boost = keyword_boost if keyword_boost is not None else load_settings().keyword_boost")

path.write_text(content)
print("search.py patched.")
