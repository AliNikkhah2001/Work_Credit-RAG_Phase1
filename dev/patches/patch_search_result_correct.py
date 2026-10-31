from pathlib import Path
path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()

import re

# Patch bm25_results
content = re.sub(
    r'(bm25_results\.append\(SearchResult\(\s*chunk_id=chunk_id,\s*doc_id=cd\[1\],\s*doc_title=cd\[2\],\s*heading_path=cd\[3\],)',
    r'\1\n            folder_hierarchy=cd[7],',
    content
)

# Patch dense_results
content = re.sub(
    r'(dense_results\.append\(SearchResult\(\s*chunk_id=chunk_id,\s*doc_id=cd\[1\],\s*doc_title=cd\[2\],\s*heading_path=cd\[3\],)',
    r'\1\n            folder_hierarchy=cd[7],',
    content
)

# Patch merged
content = re.sub(
    r'(merged\[chunk_id\] = SearchResult\(\s*chunk_id=chunk_id,\s*doc_id=cd\[1\],\s*doc_title=cd\[2\],\s*heading_path=cd\[3\],)',
    r'\1\n                    folder_hierarchy=cd[7],',
    content
)

path.write_text(content)
