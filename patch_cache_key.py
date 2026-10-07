from pathlib import Path
path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()

old = """def _cache_key(normalized_query: str, top_k: int, keyword_boost: float | None = None) -> str:
    \"\"\"Deterministic cache key = sha256(normalized_query | top_k | keyword_boost).\"\"\""""

new = """def _cache_key(normalized_query: str, top_k: int, keyword_boost: float | None = None, filter_path: str | None = None) -> str:
    \"\"\"Deterministic cache key = sha256(normalized_query | top_k | keyword_boost | filter_path).\"\"\""""
content = content.replace(old, new)

old2 = """    msg = f"{normalized_query}:{top_k}:{kb}" """
new2 = """    msg = f"{normalized_query}:{top_k}:{kb}:{filter_path or ''}" """
content = content.replace(old2, new2)

old3 = """        ckey = _cache_key(query, top_k, keyword_boost)"""
new3 = """        ckey = _cache_key(query, top_k, keyword_boost, filter_path)"""
content = content.replace(old3, new3)

path.write_text(content)
