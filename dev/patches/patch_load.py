from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/dense.py")
content = path.read_text()

old = "fp = DenseSemanticIndex.fingerprint(texts, titles, headings, chunk_types, model_name, use_context)"
new = "fp = DenseSemanticIndex.fingerprint(texts, ids, titles, headings, chunk_types, model_name, use_context)"
content = content.replace(old, new)
path.write_text(content)

path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()

old = "cur_fp = DenseSemanticIndex.fingerprint(texts, titles, headings, ctypes, _DENSE_MODEL, False)"
new = "cur_fp = DenseSemanticIndex.fingerprint(texts, [cd[0] for cd in chunk_data], titles, headings, ctypes, _DENSE_MODEL, False)"
content = content.replace(old, new)
path.write_text(content)
