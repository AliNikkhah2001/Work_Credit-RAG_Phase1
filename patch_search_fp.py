from pathlib import Path
path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()

lines = content.splitlines()
for i in range(len(lines)):
    if "cur_fp = DenseSemanticIndex.fingerprint(texts," in lines[i]:
        if "all_chunks" in lines[i-1]:
            lines[i] = lines[i].replace("[cd[0] for cd in chunk_data]", "[c.id for c in all_chunks]")

path.write_text("\n".join(lines) + "\n")
