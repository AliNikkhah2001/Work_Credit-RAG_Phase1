import re
from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/pipeline/orchestrator.py")
content = path.read_text()

# Import EntityList at top
if "EntityList" not in content:
    content = content.replace("from kb_manager.models.database import Chunk, DBChunk, Document, IngestionJob, RetrievalLog", "from kb_manager.models.database import Chunk, DBChunk, Document, IngestionJob, RetrievalLog, EntityList")

old_entity_check = """        # --- Check for Entity Bypass ---
        is_entity_list = "ضمیمه پایگاه دانش" in file_path or "لیست" in file_path
        if is_entity_list:
            logger.info("Bypassing chunking/embedding for Entity List: %s", file_path)
            if hasattr(self, "artifact_mgr"):
                self.artifact_mgr.save("entity_lists", file_path, {"title": parsed.title, "sheets": parsed.sheets})
            result["skipped"] = 1
            return result"""

new_entity_check = """        # --- Check for Entity Bypass ---
        is_entity_list = "ضمیمه پایگاه دانش" in file_path or "لیست" in file_path
        if is_entity_list:
            logger.info("Processing Supplementary Entity List: %s", file_path)
            if "نامربوط" in file_path:
                logger.info("Ignoring guardrail file: %s", file_path)
                result["skipped"] = 1
                return result
                
            if hasattr(self, "artifact_mgr"):
                self.artifact_mgr.save("entity_lists", file_path, {"title": parsed.title, "sheets": parsed.sheets})
                
            if "واژگان" in file_path:
                logger.info("Synonym mapping file processed for BM25: %s", file_path)
                # Later: update synonyms.json
                result["skipped"] = 1
                return result
            
            # Save standard Entity List to SQLite
            import uuid
            import json
            
            # Combine all sheets into a single JSON object for content
            content_json = {}
            if parsed.sheets:
                for sheet in parsed.sheets:
                    content_json[sheet["name"]] = sheet["rows"]
                    
            desc = f"این لیست حاوی اطلاعات {parsed.title} است. "
            
            # Calculate dense embedding of the description for the Semantic Router
            emb = None
            if self._embedder:
                try:
                    emb_list = self._embedder.embed([desc])
                    if emb_list:
                        emb = emb_list[0]
                except Exception as e:
                    logger.warning("Failed to embed entity list %s: %s", parsed.title, e)

            # Store in DB
            db_ent = EntityList(
                id=str(uuid.uuid4()),
                list_name=parsed.title,
                description=desc,
                description_embedding=emb,
                content_json=content_json
            )
            
            # Delete old lists with the same name to prevent duplicates
            from sqlalchemy import delete
            await session.execute(delete(EntityList).where(EntityList.list_name == parsed.title))
            session.add(db_ent)
            await session.flush()
            
            result["skipped"] = 1
            return result"""

if old_entity_check in content:
    content = content.replace(old_entity_check, new_entity_check)
else:
    print("Could not find the target code to replace!")

path.write_text(content)
print("Orchestrator patched.")
