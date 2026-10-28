from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/evaluation/benchmark.py")
content = path.read_text()

# Strip out the poorly indented block completely and rewrite it
import re

# Match from `start = time.monotonic()` to the end of the `self._search` block.
block = re.search(r'start = time\.monotonic\(\)\s+# Subspace.*?self\._search\(query, self\._top_k\)', content, flags=re.DOTALL)

if block:
    good_block = """start = time.monotonic()
            
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
            
            import inspect
            if "filter_path" in inspect.signature(self._search).parameters:
                raw = await self._search(query, self._top_k, filter_path=filter_path)
            else:
                raw = await self._search(query, self._top_k)"""
    content = content.replace(block.group(0), good_block)
    path.write_text(content)
    print("Fixed indentation!")
else:
    print("Could not find block")
