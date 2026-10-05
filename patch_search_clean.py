from pathlib import Path
path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()

old = """    print(f"DEBUG: use_pgvector={use_pgvector}")
    # --- Step 2: BM25"""
new = """    # --- Step 2: BM25"""
content = content.replace(old, new)

old2 = """    if dense_raw_base is None:
        dense_raw_base = dense.search(normalized, top_k=top_k * 3)
        print("DEBUG: dense_raw_base length:", len(dense_raw_base))
        print("DEBUG: is_built:", dense.is_built)"""
new2 = """    if dense_raw_base is None:
        dense_raw_base = dense.search(normalized, top_k=top_k * 3)"""
content = content.replace(old2, new2)

path.write_text(content)
