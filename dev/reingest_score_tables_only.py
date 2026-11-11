"""Re-ingest only the three score Excel tables (no full rebuild)."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("reingest_scores")

ROOT = Path(os.environ.get("ZAMIME_ROOT", "/tmp/zamime_ingest/ضمیمه پایگاه دانش"))
SCORE_FILES = [
    "جدول امتیاز اعتبارسنجی چک.xlsx",
    "جدول امتیاز اعتباری اشخاص حقیقی.xlsx",
    "جدول امتیاز اعتباری اشخاص حقوقی.xlsx",
]


async def main() -> int:
    from sqlalchemy import select

    from kb_manager.chunker.semantic import SemanticChunker
    from kb_manager.embedder.registry import get_embedder
    from kb_manager.models.database import EntityList
    from kb_manager.pipeline.orchestrator import PipelineOrchestrator
    from kb_manager.web.deps import db

    model = os.environ.get(
        "KB_EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    embedder = get_embedder("local", model_name=model)
    orch = PipelineOrchestrator(
        database=db,
        chunker=SemanticChunker(max_tokens=512, min_tokens=100),
        embedder=embedder,
    )
    async with db.session() as session:
        for name in SCORE_FILES:
            path = ROOT / name
            if not path.is_file():
                log.error("missing %s", path)
                return 2
            result = await orch._process_file(
                str(path.resolve()), session, force=True, commit_hash="score-tables-v2"
            )
            log.info("processed %s -> %s", name, result)
        await session.commit()

    async with db.session() as session:
        for e in (await session.execute(select(EntityList))).scalars():
            meta = (e.content_json or {}).get("_meta") or {}
            if meta.get("kind") != "score_table":
                continue
            bands = e.content_json.get("bands") or []
            groups = e.content_json.get("color_groups") or []
            text = e.content_json.get("full_table_text") or ""
            log.info(
                "%s bands=%s color_groups=%s full_text_chars=%s",
                e.list_name,
                len(bands),
                len(groups),
                len(text),
            )
            if len(bands) != 15 or len(groups) != 5 or len(text) < 200:
                log.error("incomplete payload for %s", e.list_name)
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
