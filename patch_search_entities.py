import re
from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()

if "injected_entities" not in content:
    content = content.replace("    final_results: list[SearchResult]\n", "    final_results: list[SearchResult]\n    injected_entities: list[dict] = []\n")

if "EntityList" not in content:
    content = content.replace("from kb_manager.models.database import Chunk, Document", "from kb_manager.models.database import Chunk, Document, EntityList")

inject_logic = """
    # --- Step 8: Semantic Intent Entity Injection ---
    injected_entities = []
    try:
        from kb_manager.web.deps import db
        import numpy as np
        async with db.session() as session:
            from sqlalchemy import select
            from kb_manager.models.database import EntityList
            ents_res = await session.execute(select(EntityList))
            entity_lists = ents_res.scalars().all()
            
            if q_emb is not None and entity_lists:
                q_vec = np.array(q_emb)
                q_norm = np.linalg.norm(q_vec)
                for ent in entity_lists:
                    if not ent.description_embedding: continue
                    ent_vec = np.array(ent.description_embedding)
                    ent_norm = np.linalg.norm(ent_vec)
                    if q_norm > 0 and ent_norm > 0:
                        sim = np.dot(q_vec, ent_vec) / (q_norm * ent_norm)
                        if sim > 0.6:  # Threshold for triggering the list
                            injected_entities.append({
                                "list_name": ent.list_name,
                                "description": ent.description,
                                "content": ent.content_json,
                                "similarity": float(sim)
                            })
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Failed to inject entities: %s", e)

    return SearchSteps("""

content = content.replace("    return SearchSteps(", inject_logic)

if "injected_entities=injected_entities," not in content:
    content = content.replace("config=config,\n    )", "config=config,\n        injected_entities=injected_entities,\n    )")

path.write_text(content)
print("search.py updated with entity injection")
