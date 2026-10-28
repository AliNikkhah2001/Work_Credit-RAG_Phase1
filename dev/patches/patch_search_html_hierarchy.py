from pathlib import Path
path = Path("components/knowledgebase/kb-manager/kb_manager/web/templates/search.html")
content = path.read_text()

old = """                <td><small style="color:gray;">${esc(r.doc_title)}</small><br>${esc(r.content_preview)}</td>"""
new = """                <td>
                    <small style="color:gray;">
                        ${r.folder_hierarchy && r.folder_hierarchy.length > 0 ? esc(r.folder_hierarchy.join(' / ')) + ' > ' : ''}
                        <strong>${esc(r.doc_title)}</strong>
                    </small>
                    <br>${esc(r.content_preview)}
                </td>"""
content = content.replace(old, new)

path.write_text(content)
