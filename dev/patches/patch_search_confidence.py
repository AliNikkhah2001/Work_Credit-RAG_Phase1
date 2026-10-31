from pathlib import Path
path = Path("components/knowledgebase/kb-manager/kb_manager/web/templates/search.html")
content = path.read_text()

old = """            let finalScore = r.rerank_score !== undefined ? r.rerank_score.toFixed(4) : r.hybrid_score.toFixed(4);
            
            finalBody.innerHTML += `<tr class="${srcClass}">
                <td><strong>${i+1}</strong></td>
                <td>
                    <small style="color:gray;">
                        ${r.folder_hierarchy && r.folder_hierarchy.length > 0 ? esc(r.folder_hierarchy.join(' / ')) + ' > ' : ''}
                        <strong>${esc(r.doc_title)}</strong>
                    </small>
                    <br>${esc(r.content_preview)}
                </td>
                <td>${badges}</td>
                <td><div class="score-badge rerank" style="font-size:14px;">Score: ${finalScore}</div></td>
            </tr>`;"""

new = """            let confidence = r.rerank_score !== undefined ? (r.rerank_score * 100).toFixed(1) : (r.hybrid_score * 100).toFixed(1);
            let rawScore = r.rerank_score !== undefined ? r.rerank_score.toFixed(4) : r.hybrid_score.toFixed(4);
            
            finalBody.innerHTML += `<tr class="${srcClass}">
                <td><strong>${i+1}</strong></td>
                <td>
                    <small style="color:#2980b9; font-weight:bold;">
                        ${r.folder_hierarchy && r.folder_hierarchy.length > 0 ? '📁 ' + esc(r.folder_hierarchy.join(' / ')) + ' <br> 📄 ' : '📄 '}
                        <span style="color:gray;">${esc(r.doc_title)}</span>
                    </small>
                    <br><br>${esc(r.content_preview)}
                </td>
                <td>${badges}</td>
                <td>
                    <div class="score-badge rerank" style="font-size:16px; margin-bottom:5px;">Confidence: ${confidence}%</div>
                    <div style="font-size:11px; color:gray; text-align:center;">Raw Score: ${rawScore}</div>
                </td>
            </tr>`;"""

content = content.replace(old, new)
path.write_text(content)
