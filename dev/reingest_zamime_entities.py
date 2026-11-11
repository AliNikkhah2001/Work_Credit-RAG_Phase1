"""Safe EntityList-only re-ingest for ضمیمه (no full rebuild / no orphan delete)."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger("reingest_zamime")

ROOT = Path(os.environ.get("ZAMIME_ROOT", "/tmp/zamime_ingest/ضمیمه پایگاه دانش"))

EXPECTED = {
    "جدول امتیاز اعتبارسنجی چک",
    "جدول امتیاز اعتباری اشخاص حقیقی",
    "جدول امتیاز اعتباری اشخاص حقوقی",
    "لیست و عناوین وام ها",
    "سهامداران",
    "تامین‌کنندگان دیتا",
    "استفاده کنندگان گزارش",
}


async def _make_embedder():
    from kb_manager.embedder.registry import get_embedder

    model = os.environ.get(
        "KB_EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    emb = get_embedder("local", model_name=model)
    log.info("embedder model=%s", model)
    return emb


async def main() -> int:
    from sqlalchemy import delete, select

    from kb_manager.chunker.semantic import SemanticChunker
    from kb_manager.models.database import EntityList
    from kb_manager.pipeline.orchestrator import PipelineOrchestrator
    from kb_manager.web.deps import db

    if not ROOT.is_dir():
        log.error("missing root %s", ROOT)
        return 2

    embedder = await _make_embedder()
    orch = PipelineOrchestrator(
        database=db,
        chunker=SemanticChunker(max_tokens=512, min_tokens=100),
        embedder=embedder,
    )

    # Clear ALL entity lists (stale Q&A wrongly stored as entities)
    async with db.session() as session:
        before = (await session.execute(select(EntityList))).scalars().all()
        log.info("before count=%s names=%s", len(before), [e.list_name for e in before])
        await session.execute(delete(EntityList))
        await session.commit()

    files = sorted(
        str(p.resolve())
        for p in ROOT.rglob("*")
        if p.is_file() and not p.name.startswith("~$") and p.suffix.lower() in {".xlsx", ".docx"}
    )
    log.info("candidate files=%s", len(files))
    for f in files:
        log.info("  %s", f)

    async with db.session() as session:
        for f in files:
            try:
                result = await orch._process_file(f, session, force=True, commit_hash="zamime-entities")
                log.info("processed %s -> %s", Path(f).name, result)
            except Exception as exc:
                log.exception("failed %s: %s", f, exc)
                return 1
        await session.commit()

    async with db.session() as session:
        ents = (await session.execute(select(EntityList))).scalars().all()
        log.info("after count=%s", len(ents))
        names = set()
        ok_scores = 0
        for e in ents:
            names.add(e.list_name)
            meta = (e.content_json or {}).get("_meta") or {}
            bands = (e.content_json or {}).get("bands")
            if meta.get("kind") == "score_table" and bands and len(bands) == 15:
                ok_scores += 1
            log.info(
                "  list=%r kind=%s model=%s bands=%s emb=%s subspaces=%s",
                e.list_name,
                meta.get("kind"),
                meta.get("model"),
                len(bands) if bands else "-",
                e.description_embedding is not None,
                meta.get("subspace_ids"),
            )
        missing = EXPECTED - names
        if missing:
            log.error("missing: %s", missing)
            return 1
        if ok_scores < 3:
            log.error("score tables incomplete: %s", ok_scores)
            return 1
        # Ensure no junk leftover names
        junk = names - EXPECTED
        if junk:
            log.warning("extra entity lists (ok if intentional): %s", junk)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
