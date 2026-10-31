from pathlib import Path

path = Path("README.md")
content = path.read_text()

update_text = """## 📂 Metadata Filtering & Folder Hierarchy
The chunking pipeline now deeply integrates with the physical directory structure of the knowledge base. 
During ingestion, the orchestrator parses the path (e.g. `kb-source/1405-07-06/پایگاه دانش/اشخاص حقوقی/...`) and injects the folder hierarchy as dynamic metadata tags on every single chunk.
When querying the system, you can pass a `filter_path` parameter (e.g. `filter_path="اشخاص حقوقی"`) to instantly restrict the search radius. This guarantees perfect separation of contexts and ensures the RAG pipeline only pulls from the designated semantic sub-tree.

## 🔗 Supplementary Data Architecture (`ضمیمه پایگاه دانش`)
Not all knowledge is suited for Dense Vector embeddings (e.g. list of bank names, reason codes, shareholder tables). 
These are now intercepted during ingestion and treated separately:
*   **System Configurations (`واژگان معادل.xlsx`):** Passed directly to BM25 query expansion as synonyms.
*   **Guardrails (`سوالات نامربوط.xlsx`):** Ignored from RAG injection to prevent hallucination.
*   **Entity Lists:** Converted to structured JSON. A MiniLM vector embedding of the *list description* is cached in memory. During search, if the user's query vector is semantically similar to an Entity List description (Cosine > 0.6), the *entire* raw JSON list is injected perfectly intact into the final LLM payload.

For deeper architectural details, see [`data/supplementary_architecture.md`](data/supplementary_architecture.md).
"""

if "## 📂 Metadata Filtering & Folder Hierarchy" not in content:
    content = content.replace("## Evaluation", update_text + "\n## Evaluation")
    path.write_text(content)
    print("README updated")
else:
    print("Already updated")
