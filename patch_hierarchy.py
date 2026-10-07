from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/pipeline/orchestrator.py")
content = path.read_text()

hierarchy_logic = """        # --- Extract Folder Hierarchy ---
        try:
            rel_path = Path(file_path).relative_to(Path(file_path).parents[Path(file_path).parts.index("kb-source")+1])
            # rel_path is e.g. "پایگاه دانش/اشخاص حقوقی/اعتبارسنجی تسهیلات/file.xlsx"
            hierarchy = list(rel_path.parent.parts)
            parsed.metadata["folder_hierarchy"] = hierarchy
            if len(hierarchy) > 0:
                parsed.metadata["domain"] = hierarchy[0]
            if len(hierarchy) > 1:
                parsed.metadata["category"] = hierarchy[1]
        except Exception:
            pass

        if hasattr(self, "artifact_mgr"):"""

content = content.replace('        if hasattr(self, "artifact_mgr"):', hierarchy_logic, 1)
path.write_text(content)
print("orchestrator patched with hierarchy extraction")
