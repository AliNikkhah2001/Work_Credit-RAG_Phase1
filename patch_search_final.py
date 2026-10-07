from pathlib import Path
import re

path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()

# 1. Fix cache key
old_raw = 'raw = f"{normalized_query.strip()}|{int(top_k)}|{kb}"'
new_raw = 'raw = f"{normalized_query.strip()}|{int(top_k)}|{kb}|{filter_path or \'\'}"'
content = content.replace(old_raw, new_raw)

# 2. Fix filter_path prefix logic
old_allowed = """    allowed_ids = None
    if filter_path:
        allowed_ids = {cd[0] for cd in chunk_data if filter_path in cd[7]}"""
new_allowed = """    allowed_ids = None
    if filter_path:
        f_parts = filter_path.split("/")
        allowed_ids = {cd[0] for cd in chunk_data if cd[7][:len(f_parts)] == f_parts}"""
content = content.replace(old_allowed, new_allowed)

path.write_text(content)
