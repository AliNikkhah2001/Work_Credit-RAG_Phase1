from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
lines = path.read_text().split("\n")
for i, line in enumerate(lines):
    if line.startswith("from kb_manager.settings import load_settings"):
        pass # we will re-insert it properly
    
# Better yet, just rewrite it cleanly
content = path.read_text()
content = content.replace("    from kb_manager.settings import load_settings\nfrom kb_manager.dense import DenseSemanticIndex", "    from kb_manager.settings import load_settings\n    from kb_manager.dense import DenseSemanticIndex")
content = content.replace("from kb_manager.settings import load_settings\nfrom kb_manager.dense import DenseSemanticIndex", "from kb_manager.settings import load_settings\nfrom kb_manager.dense import DenseSemanticIndex")
path.write_text(content)
