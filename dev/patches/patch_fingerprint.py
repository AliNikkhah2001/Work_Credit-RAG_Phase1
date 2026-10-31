import sys
from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/dense.py")
content = path.read_text()

old1 = "def fingerprint(texts: list[str],"
new1 = "def fingerprint(texts: list[str], ids: list[str] = [],"
if old1 in content:
    content = content.replace(old1, new1)

old2 = """    def fingerprint(texts: list[str],"""
new2 = """    def fingerprint(texts: list[str], ids: list[str] = [],"""
content = content.replace(old2, new2)

old3 = """        h.update(str(use_context).encode("utf-8"))
        for t in texts:"""
new3 = """        h.update(str(use_context).encode("utf-8"))
        if ids:
            for i in ids:
                h.update(i.encode("utf-8"))
        for t in texts:"""
if old3 in content:
    content = content.replace(old3, new3)

path.write_text(content)
