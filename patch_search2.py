from pathlib import Path
path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()
old = """    # --- Step 2: BM25"""
new = """    print(f"DEBUG: use_pgvector={use_pgvector}")
    # --- Step 2: BM25"""
content = content.replace(old, new)
path.write_text(content)
