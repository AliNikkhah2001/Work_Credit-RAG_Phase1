from pathlib import Path
path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()
old = """    if dense_raw_base is None:
        dense_raw_base = dense.search(normalized, top_k=top_k * 3)"""
new = """    if dense_raw_base is None:
        dense_raw_base = dense.search(normalized, top_k=top_k * 3)
        print("DEBUG: dense_raw_base length:", len(dense_raw_base))
        print("DEBUG: is_built:", dense.is_built)"""
content = content.replace(old, new)
path.write_text(content)
