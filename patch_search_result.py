from pathlib import Path
path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()

old_res = """class SearchResult(BaseModel):
    chunk_id: str
    doc_id: str
    doc_title: str
    heading_path: str
    content_preview: str"""
new_res = """class SearchResult(BaseModel):
    chunk_id: str
    doc_id: str
    doc_title: str
    heading_path: str
    folder_hierarchy: list[str] = []
    content_preview: str"""
content = content.replace(old_res, new_res)

# Fix instantiation where SearchResult is created
old_inst = """        bm25_results.append(SearchResult(
            chunk_id=chunk_id,
            doc_id=cd[1],
            doc_title=cd[2],
            heading_path=cd[3],
            content_preview=cd[4][:150] + "...",
            bm25_score=score
        ))"""
new_inst = """        bm25_results.append(SearchResult(
            chunk_id=chunk_id,
            doc_id=cd[1],
            doc_title=cd[2],
            heading_path=cd[3],
            folder_hierarchy=cd[7],
            content_preview=cd[4][:150] + "...",
            bm25_score=score
        ))"""
content = content.replace(old_inst, new_inst)

old_inst2 = """        dense_results.append(SearchResult(
            chunk_id=chunk_id,
            doc_id=cd[1],
            doc_title=cd[2],
            heading_path=cd[3],
            content_preview=cd[4][:150] + "...",
            semantic_score=score,
            dense_score=score
        ))"""
new_inst2 = """        dense_results.append(SearchResult(
            chunk_id=chunk_id,
            doc_id=cd[1],
            doc_title=cd[2],
            heading_path=cd[3],
            folder_hierarchy=cd[7],
            content_preview=cd[4][:150] + "...",
            semantic_score=score,
            dense_score=score
        ))"""
content = content.replace(old_inst2, new_inst2)

path.write_text(content)
