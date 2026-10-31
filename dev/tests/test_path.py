from pathlib import Path
file_path = "/Users/alinikkhah/Documents/Work/RAG ICS/work_credit-rag_phase1/components/knowledgebase/kb-source/1405-07-06/پایگاه دانش/اشخاص حقوقی/اعتبارسنجی تسهیلات/file.xlsx"
parts = Path(file_path).parts
idx = parts.index("kb-source")
base = Path(*parts[:idx+2]) # kb-source/1405-07-06
rel = Path(file_path).relative_to(base)
print(list(rel.parent.parts))
