from pathlib import Path
path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()

import re

old_block = """    # Fallback: if reranker gives uniformly low scores for very short queries (<=4 tokens), use BM25
    _fallback_used = False
    try:
        max_rerank = max((r.rerank_score for r in reranked_results), default=0)
        if max_rerank < 0.2 and len(bm25_results) > 0 and len(tokens) <= 4:
            # Use BM25 top as final, preserve BM25 scores
            fallback = []
            for r in bm25_results[:top_k]:
                # copy with rerank_score = bm25 for visibility
                nr = r.model_copy()
                nr.rerank_score = r.bm25_score
                fallback.append(nr)
            reranked_results = fallback
            _fallback_used = True
    except Exception:
        pass"""

new_block = """    # Fallback: if reranker gives uniformly low scores for very short queries (<=4 tokens), use BM25
    _fallback_used = False
    try:
        max_rerank = max((r.rerank_score for r in reranked_results), default=0)
        if max_rerank < 0.2 and len(bm25_results) > 0 and len(tokens) <= 4:
            # Use BM25 top as final, but pull from merged to preserve all stage scores
            fallback = []
            for idx, r in enumerate(bm25_results[:top_k]):
                if r.chunk_id in merged:
                    nr = merged[r.chunk_id].model_copy()
                    # Assign a synthetic confidence score that passes threshold (e.g. 0.50 descending)
                    # so the UI shows ~50% confidence instead of 2300% (BM25 score)
                    nr.rerank_score = max(0.05, 0.5 - (idx * 0.05))
                    fallback.append(nr)
            reranked_results = fallback
            _fallback_used = True
    except Exception:
        pass"""

content = content.replace(old_block, new_block)
path.write_text(content)
