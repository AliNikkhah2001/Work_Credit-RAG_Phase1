import re
from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()

# Extract filter_path from body
if 'filter_path = body.get("filter_path") if isinstance(body, dict) else None' not in content:
    content = content.replace(
        '    if not query:\n', 
        '    filter_path = body.get("filter_path") if isinstance(body, dict) else None\n    if not query:\n'
    )
    
# Update cache key to include filter_path
    content = content.replace(
        'c_key_str = f"{norm_q}:{top_k}:{keyword_boost or 0.0}"',
        'c_key_str = f"{norm_q}:{top_k}:{keyword_boost or 0.0}:{filter_path or \'\'}"'
    )

# Call search_knowledge_base with filter_path
    content = content.replace(
        'steps = await search_knowledge_base(query, top_k, keyword_boost=keyword_boost)',
        'steps = await search_knowledge_base(query, top_k, keyword_boost=keyword_boost, filter_path=filter_path)'
    )

path.write_text(content)
print("search_api updated")

path_html = Path("components/knowledgebase/kb-manager/kb_manager/web/templates/search.html")
html = path_html.read_text()

if 'id="filter-input"' not in html:
    new_input = """<input type="text" id="filter-input" class="form-control" placeholder="Sub-space Folder (e.g. اشخاص حقوقی)" style="max-width: 250px; font-size: 1.1rem; padding: 10px;">
            <input type="text" id="search-input" class="form-control" placeholder="Enter test query to observe..." required style="flex:1; font-size: 1.1rem; padding: 10px;">"""
    html = html.replace('<input type="text" id="search-input" class="form-control" placeholder="Enter test query to observe..." required style="flex:1; font-size: 1.1rem; padding: 10px;">', new_input)
    
    html = html.replace("var query = document.getElementById('search-input').value.trim();", 
        "var query = document.getElementById('search-input').value.trim();\n    var filter_path = document.getElementById('filter-input').value.trim();")
    
    html = html.replace("body: JSON.stringify({ query: query })", "body: JSON.stringify({ query: query, filter_path: filter_path || null })")

    path_html.write_text(html)
    print("search.html updated")

