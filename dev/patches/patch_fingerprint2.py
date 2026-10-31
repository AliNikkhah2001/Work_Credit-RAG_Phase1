from pathlib import Path
path = Path("components/knowledgebase/kb-manager/kb_manager/dense.py")
content = path.read_text()

old = """    def fingerprint(
        texts: list[str],
        titles: Optional[list[str]] = None,"""
new = """    def fingerprint(
        texts: list[str],
        ids: list[str] = [],
        titles: Optional[list[str]] = None,"""
content = content.replace(old, new)
path.write_text(content)
