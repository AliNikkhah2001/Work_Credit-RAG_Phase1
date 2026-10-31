from pathlib import Path
path = Path("components/knowledgebase/kb-manager/kb_manager/web/templates/search.html")
content = path.read_text()

old = """        const t_sem = (data.stage_ms && data.stage_ms.semantic) || 0;
        const t_rrf = (data.stage_ms && data.stage_ms.hybrid) || 0;"""
new = """        const t_sem = (data.stage_ms && data.stage_ms.dense) || 0;
        const t_rrf = (data.stage_ms && data.stage_ms.rrf) || 0;"""

content = content.replace(old, new)
path.write_text(content)
