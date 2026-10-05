import re
from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()

# 1. Update _build_index return type and chunk_data type
content = content.replace(
    "tuple[list[tuple[str, str, str, str, str, str, int]],", 
    "tuple[list[tuple[str, str, str, str, str, str, int, list[str]]],"
)
content = content.replace(
    "chunk_data: list[tuple[str, str, str, str, str, str, int]] = []",
    "chunk_data: list[tuple[str, str, str, str, str, str, int, list[str]]] = []"
)

# 2. Extract hierarchy and append to chunk_data
old_append = "chunk_data.append((c.id, c.document_id, title, c.heading_path, c.content, c.chunk_type, c.ordinal))"
new_append = """hierarchy = docs[c.document_id].doc_metadata.get("folder_hierarchy", [])
        chunk_data.append((c.id, c.document_id, title, c.heading_path, c.content, c.chunk_type, c.ordinal, hierarchy))"""
content = content.replace(old_append, new_append)

# 3. Add filter_path to search_knowledge_base
old_sig = "async def search_knowledge_base(query: str, top_k: int = 10, keyword_boost: float | None = None, stage_depth: int | None = None) -> SearchSteps:"
new_sig = "async def search_knowledge_base(query: str, top_k: int = 10, keyword_boost: float | None = None, stage_depth: int | None = None, filter_path: str | None = None) -> SearchSteps:"
content = content.replace(old_sig, new_sig)
content = content.replace(
    "def search_knowledge_base_sync(query: str, top_k: int = 10, keyword_boost: float | None = None, stage_depth: int | None = None) -> SearchSteps:",
    "def search_knowledge_base_sync(query: str, top_k: int = 10, keyword_boost: float | None = None, stage_depth: int | None = None, filter_path: str | None = None) -> SearchSteps:"
)
content = content.replace(
    "search_knowledge_base(query, top_k, keyword_boost=keyword_boost, stage_depth=stage_depth)",
    "search_knowledge_base(query, top_k, keyword_boost=keyword_boost, stage_depth=stage_depth, filter_path=filter_path)"
)

path.write_text(content)
print("search.py updated for metadata filtering signature")
