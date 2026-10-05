import re
from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()

bad = "if q_emb is not None and entity_lists:"
good = """
            q_emb = None
            try:
                if dense is not None and hasattr(dense, 'model') and dense.model is not None:
                    q_emb = dense.model.encode([query], normalize_embeddings=True)[0]
            except Exception:
                pass
            if q_emb is not None and entity_lists:
"""
content = content.replace(bad, good)
path.write_text(content)
