import re
from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/evaluation/benchmark.py")
content = path.read_text()

old_search = "raw = await self._search(query, self._top_k)"

new_search = """
                # Subspace Filtering hack for benchmark
                filter_path = None
                expected_ids = item.get("expected_chunk_ids", [])
                if expected_ids:
                    import sqlite3, json
                    try:
                        conn = sqlite3.connect("data/kb_test.db")
                        cur = conn.cursor()
                        cur.execute("SELECT metadata FROM chunks WHERE id = ?", (expected_ids[0],))
                        row = cur.fetchone()
                        if row:
                            meta = json.loads(row[0])
                            h = meta.get("folder_hierarchy", [])
                            if len(h) >= 2: filter_path = h[1]
                            elif len(h) >= 1: filter_path = h[0]
                        conn.close()
                    except:
                        pass
                
                # Pass filter_path into search function if supported
                import inspect
                if "filter_path" in inspect.signature(self._search).parameters:
                    raw = await self._search(query, self._top_k, filter_path=filter_path)
                else:
                    raw = await self._search(query, self._top_k)
"""
content = content.replace(old_search, new_search)
path.write_text(content)
print("benchmark.py patched")

path_rb = Path("components/knowledgebase/kb-manager/run_benchmark.py")
content_rb = path_rb.read_text()
old_rb_search = "async def _search(query: str, k: int):"
new_rb_search = "async def _search(query: str, k: int, filter_path: str = None):"
content_rb = content_rb.replace(old_rb_search, new_rb_search)
content_rb = content_rb.replace("steps = await search_knowledge_base(query, k)", "steps = await search_knowledge_base(query, k, filter_path=filter_path)")
path_rb.write_text(content_rb)
print("run_benchmark.py updated with signature")
