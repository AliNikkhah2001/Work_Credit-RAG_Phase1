from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()

# Insert allowed_ids computation
old_setup = """    stage_ms = {}
    
    # --- Step 2: BM25"""

new_setup = """    stage_ms = {}
    
    allowed_ids = None
    if filter_path:
        allowed_ids = {cd[0] for cd in chunk_data if filter_path in cd[7]}

    # --- Step 2: BM25"""
content = content.replace(old_setup, new_setup)

# Update bm25_content.search
old_bm25_1 = """        bm25_raw_content_all.extend(bm25_content.search(bq, top_k=top_k * 3))"""
new_bm25_1 = """        bm25_raw_content_all.extend(bm25_content.search(bq, top_k=top_k * 3, allowed_ids=allowed_ids))"""
content = content.replace(old_bm25_1, new_bm25_1)

old_bm25_2 = """            bm25_raw_kw_all.extend(bm25_kw.search(bq, top_k=top_k * 3))"""
new_bm25_2 = """            bm25_raw_kw_all.extend(bm25_kw.search(bq, top_k=top_k * 3, allowed_ids=allowed_ids))"""
content = content.replace(old_bm25_2, new_bm25_2)

old_bm25_3 = """        for cid, s in bm25_content.search(normalized, top_k=top_k * 3):"""
new_bm25_3 = """        for cid, s in bm25_content.search(normalized, top_k=top_k * 3, allowed_ids=allowed_ids):"""
content = content.replace(old_bm25_3, new_bm25_3)

old_bm25_4 = """        for cid, s in (bm25_kw.search(normalized, top_k=top_k * 3) if bm25_kw else []):"""
new_bm25_4 = """        for cid, s in (bm25_kw.search(normalized, top_k=top_k * 3, allowed_ids=allowed_ids) if bm25_kw else []):"""
content = content.replace(old_bm25_4, new_bm25_4)

# Update dense.search
old_dense_1 = """    if dense_raw_base is None:
        dense_raw_base = dense.search(normalized, top_k=top_k * 3)"""
new_dense_1 = """    if dense_raw_base is None:
        dense_raw_base = dense.search(normalized, top_k=top_k * 3, allowed_ids=allowed_ids)"""
content = content.replace(old_dense_1, new_dense_1)

old_dense_2 = """            for cid, sc in dense.search(bq, top_k=top_k * 3):"""
new_dense_2 = """            for cid, sc in dense.search(bq, top_k=top_k * 3, allowed_ids=allowed_ids):"""
content = content.replace(old_dense_2, new_dense_2)

# Now we should optionally remove the post-filtering loop logic (though leaving it is functionally a no-op now, removing it makes it clean)
# I'll just leave it as is to avoid tricky string replacements, it's harmless.

path.write_text(content)
