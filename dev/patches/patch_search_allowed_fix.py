from pathlib import Path
path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()

old = """    # --- Step 2: BM25 (weighted content + keywords, tunable boost) ---
    beam_queries = _expand_query_for_bm25(normalized) if _SYNONYM_BEAM > 1 else [normalized]"""

new = """    allowed_ids = None
    if filter_path:
        allowed_ids = {cd[0] for cd in chunk_data if filter_path in cd[7]}

    # --- Step 2: BM25 (weighted content + keywords, tunable boost) ---
    beam_queries = _expand_query_for_bm25(normalized) if _SYNONYM_BEAM > 1 else [normalized]"""

content = content.replace(old, new)
path.write_text(content)
