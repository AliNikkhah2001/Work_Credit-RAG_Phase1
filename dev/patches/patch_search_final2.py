from pathlib import Path
path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()

old_allowed = """    allowed_ids = None
    if filter_path:
        f_parts = filter_path.split("/")
        allowed_ids = {cd[0] for cd in chunk_data if cd[7][:len(f_parts)] == f_parts}"""

new_allowed = """    allowed_ids = None
    if filter_path:
        # Match filter_path anywhere inside the folder hierarchy string
        allowed_ids = {cd[0] for cd in chunk_data if filter_path in "/".join(cd[7])}"""

content = content.replace(old_allowed, new_allowed)
path.write_text(content)
