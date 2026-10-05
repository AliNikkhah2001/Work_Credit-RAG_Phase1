import re
from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()

# Revert previous failed patch attempts
if "# --- Step 1.5: Metadata Filtering ---" in content:
    # Just remove it
    content = re.sub(r'# --- Step 1\.5: Metadata Filtering ---.*?# --- Step 2: BM25', '# --- Step 2: BM25', content, flags=re.DOTALL)
    
if "if valid_indices is not None and idx not in valid_indices:" in content:
    content = re.sub(r'if valid_indices is not None and idx not in valid_indices:\s+continue', '', content)

# Now apply the clean patch to BM25
old_bm25_check = """        cd = bm25_id_map.get(chunk_id)
        if cd is None:
            continue"""
new_bm25_check = """        cd = bm25_id_map.get(chunk_id)
        if cd is None:
            continue
        if filter_path and filter_path not in cd[7]:
            continue"""
content = content.replace(old_bm25_check, new_bm25_check)

# The dense_raw loop happens to use the EXACT same check:
# wait, wait! replace will replace BOTH instances if I do it globally!
# Yes, both BM25 and Dense use the exact same variable `cd = bm25_id_map.get(chunk_id)` followed by `if cd is None: continue`.

path.write_text(content)
print("Clean filter logic applied!")
