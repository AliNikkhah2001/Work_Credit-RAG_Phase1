import re
from pathlib import Path

path = Path("components/knowledgebase/kb-manager/run_benchmark.py")
content = path.read_text()

# Add argument
arg_code = """    parser.add_argument(
        "--use-subspace",
        action="store_true",
        help="Simulate a user selecting the correct folder sub-space for each query",
    )
    args = parser.parse_args()"""
content = content.replace("    args = parser.parse_args()", arg_code)

# Add DB lookup for chunk to get hierarchy
patch_loop = """
            print(f"\\n[{idx}/{len(queries)}] {q.get('format', 'unknown')} | {query_text[:60]}...")

            filter_path = None
            if args.use_subspace and expected_ids:
                import sqlite3
                import json
                try:
                    conn = sqlite3.connect("data/kb_test.db")
                    cur = conn.cursor()
                    cur.execute("SELECT metadata FROM chunks WHERE id = ?", (expected_ids[0],))
                    row = cur.fetchone()
                    if row:
                        metadata = json.loads(row[0])
                        hierarchy = metadata.get("folder_hierarchy", [])
                        if len(hierarchy) >= 2:
                            filter_path = hierarchy[1]  # e.g. "اشخاص حقوقی" or "اشخاص حقیقی"
                        elif len(hierarchy) >= 1:
                            filter_path = hierarchy[0]
                    conn.close()
                except Exception as e:
                    print(f"DB lookup failed: {e}")
                    pass
                if filter_path:
                    print(f"  -> Applying Subspace Filter: {filter_path}")

            steps = search_knowledge_base_sync(
                query=query_text,
                top_k=top_k,
                filter_path=filter_path
            )"""
            
if "steps = search_knowledge_base_sync(" in content:
    # We replace from print(f"\n[{idx}...") to steps = search_knowledge_base_sync(...)
    content = re.sub(r'print\(f"\\n\[\{idx\}/.*?steps = search_knowledge_base_sync\(\s*query=query_text,\s*top_k=top_k\s*\)', patch_loop, content, flags=re.DOTALL)

path.write_text(content)
print("run_benchmark.py patched")
