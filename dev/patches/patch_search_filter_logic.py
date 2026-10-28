import re
from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()

# Find Step 3: Dense Retrieval and Step 4: Hybrid Merge
# I need to filter `valid_indices`.
filter_logic = """
    # --- Step 1.5: Metadata Filtering ---
    valid_indices = None
    if filter_path:
        valid_indices = set()
        for idx, row in enumerate(chunk_data):
            hierarchy = row[7]
            if filter_path in hierarchy:
                valid_indices.add(idx)
        # If strict path string matching is needed (e.g. 'پایگاه دانش/اشخاص حقوقی'):
        # filter_parts = [p for p in filter_path.split('/') if p]
        # if filter_parts == hierarchy[:len(filter_parts)]: valid_indices.add(idx)

"""

if "# --- Step 2: BM25" in content:
    content = content.replace("# --- Step 2: BM25", filter_logic + "    # --- Step 2: BM25")
    
# Now patch BM25 and Dense iteration to skip invalid indices!
# For BM25:
old_bm25_loop = """        for idx, score in bm25_scores:
            c_id, d_id, title, heading, text, c_type, ordinal, hierarchy = chunk_data[idx]"""

new_bm25_loop = """        for idx, score in bm25_scores:
            if valid_indices is not None and idx not in valid_indices:
                continue
            c_id, d_id, title, heading, text, c_type, ordinal, hierarchy = chunk_data[idx]"""
            
if "for idx, score in bm25_scores:" in content:
    content = content.replace(old_bm25_loop, new_bm25_loop)

# For Dense:
old_dense_loop = """        for idx, score in dense_raw:
            c_id, d_id, title, heading, text, c_type, ordinal, hierarchy = chunk_data[idx]"""

new_dense_loop = """        for idx, score in dense_raw:
            if valid_indices is not None and idx not in valid_indices:
                continue
            c_id, d_id, title, heading, text, c_type, ordinal, hierarchy = chunk_data[idx]"""

if "for idx, score in dense_raw:" in content:
    content = content.replace(old_dense_loop, new_dense_loop)

path.write_text(content)
print("search.py logic updated")
