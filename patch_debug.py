from pathlib import Path
path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()
old = """    allowed_ids = None
    if filter_path:
        allowed_ids = {cd[0] for cd in chunk_data if filter_path in cd[7]}"""
new = """    allowed_ids = None
    if filter_path:
        # Check if filter_path is a path (contains '/')
        if '/' in filter_path:
            parts = filter_path.split('/')
            # A chunk matches if its folder hierarchy contains ALL parts of the filter path IN ORDER
            # But the simplest way is just to join cd[7] back into a path
            allowed_ids = {cd[0] for cd in chunk_data if filter_path in "/".join(cd[7])}
        else:
            allowed_ids = {cd[0] for cd in chunk_data if filter_path in cd[7]}
        print(f"DEBUG: filter_path='{filter_path}', len(allowed_ids)={len(allowed_ids)}")"""
content = content.replace(old, new)
path.write_text(content)
