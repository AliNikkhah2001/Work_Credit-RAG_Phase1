"""Re-ingest non-score ضمیمه catalog EntityLists (+ glossary synonyms)."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("reingest_catalogs")

ROOT = Path(os.environ.get("ZAMIME_ROOT", "/tmp/zamime_ingest/ضمیمه پایگاه دانش"))
FILES = [
    "لیست/استفاده کنندگان گزارش.xlsx",
    "لیست/تامین‌کنندگان دیتا.xlsx",
    "لیست/سهامداران.xlsx",
    "لیست/لیست و عناوین وام ها.xlsx",
    "لیست/واژگان معادل.xlsx",
]

EXPECTED = {
    "report_consumers": {"min": 100, "group_field_sample": "لندتک"},
    "data_providers": {"min": 60, "group_field_sample": "بانک"},
    "shareholders": {"min": 20, "group_field_sample": "بانک"},
    "loan_catalog": {"min": 500, "group_field_sample": "وام"},
}


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
    orch = PipelineOrchestrator(
        database=db,
        chunker=SemanticChunker(max_tokens=512, min_tokens=100),
        embedder=get_embedder("local", model_name=model),
    )
    async with db.session() as session:
        for rel in FILES:
            path = ROOT / rel
            if not path.is_file():
                log.error("missing %s", path)
                return 2
            result = await orch._process_file(
                str(path.resolve()), session, force=True, commit_hash="catalogs-v2"
            )
            log.info("processed %s -> %s", rel, result)
        await session.commit()

    async with db.session() as session:
        by_kind = {}
        for e in (await session.execute(select(EntityList))).scalars():
            meta = (e.content_json or {}).get("_meta") or {}
            kind = meta.get("kind")
            if kind in EXPECTED:
                by_kind[kind] = e
                recs = e.content_json.get("records") or []
                groups = e.content_json.get("groups") or []
                fields = meta.get("fields") or []
                log.info(
                    "%s kind=%s count=%s fields=%s groups=%s text_chars=%s",
                    e.list_name,
                    kind,
                    len(recs),
                    fields,
                    groups[:6],
                    len(e.content_json.get("full_list_text") or ""),
                )
                exp = EXPECTED[kind]
                if len(recs) < exp["min"]:
                    log.error("too few records for %s", kind)
                    return 1
                if not fields or "Column" in " ".join(fields):
                    log.error("bad fields for %s: %s", kind, fields)
                    return 1
                blob = str(groups)
                if exp["group_field_sample"] not in blob and exp["group_field_sample"] not in str(recs[:5]):
                    # soft: data_providers empty type exists
                    log.warning("sample group token %r not obvious in %s", exp["group_field_sample"], kind)
        missing = set(EXPECTED) - set(by_kind)
        if missing:
            log.error("missing kinds %s", missing)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
