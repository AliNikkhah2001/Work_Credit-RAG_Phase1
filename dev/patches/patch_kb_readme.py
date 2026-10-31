from pathlib import Path

path = Path("components/knowledgebase/README.md")
if path.exists():
    content = path.read_text()
    if "Metadata Filtering" not in content:
        content += "\n## Metadata Filtering\nThe pipeline extracts the folder hierarchy from `kb-source` and attaches it as `folder_hierarchy` metadata to all chunks. Use the `filter_path` argument in the search API to restrict retrieval to specific directories (e.g. `filter_path='اشخاص حقوقی'`).\n\n## Supplementary Data\nSee `kb-manager/data/supplementary_architecture.md` for how `ضمیمه پایگاه دانش` files are handled via semantic injection instead of dense embedding."
        path.write_text(content)
        print("KB README updated")
