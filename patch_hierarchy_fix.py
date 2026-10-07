from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/pipeline/orchestrator.py")
content = path.read_text()

bad_logic = """        try:
            rel_path = Path(file_path).relative_to(Path(file_path).parents[Path(file_path).parts.index("kb-source")+1])
            # rel_path is e.g. "پایگاه دانش/اشخاص حقوقی/اعتبارسنجی تسهیلات/file.xlsx"
            hierarchy = list(rel_path.parent.parts)"""

good_logic = """        try:
            parts = Path(file_path).parts
            idx = parts.index("kb-source")
            base = Path(*parts[:idx+2])
            rel_path = Path(file_path).relative_to(base)
            hierarchy = list(rel_path.parent.parts)"""

content = content.replace(bad_logic, good_logic)
path.write_text(content)
print("fixed hierarchy extraction")
