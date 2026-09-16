#!/usr/bin/env python3
"""Generate retrieval-training dataset from massive benchmark results.

Positives: remapped gold chunks (verified answer-token coverage).
Negatives with provenance (stage, rank, score):
  - bm25_neg: BM25 top-ranked non-gold
  - dense_neg: dense top-ranked non-gold
  - rrf_neg: RRF top-ranked non-gold (hard)
  - ce_neg: cross-encoder top-ranked non-gold (hardest - model was fooled)

Splits: dedupe by question text FIRST, then 80/10/10 (train/val/test).
All splits isolated; duplicates stay in the same split.

Outputs (benchmark/datasets/):
  retrieval_pairs_train.jsonl / _val / _test  (Format B: pairwise + metadata)
  retrieval_pairs_multi.jsonl                 (Format C: 1 pos + N neg)
  hard_negatives.jsonl                        (CE-fooled + RRF-top non-golds)
  dataset_statistics.json
"""
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(os.getenv("BENCH_ROOT", Path(__file__).resolve().parent.parent))
RAW = ROOT / "benchmark" / "raw" / "massive_results.jsonl"
OUT = ROOT / "benchmark" / "datasets"

NEG_PER_QUERY = 4  # 1 bm25 + 1 dense + 1 rrf + 1 ce (best available of each)


def doc_text(doc_id: str, doc_map: dict) -> str:
    return doc_map.get(doc_id, "")


def build_doc_map(rows: list) -> dict:
    """Chunk content is not stored in raw rows; fetch from DB lazily per need.

    To keep artifacts compact we store IDs/scores/ranks here and resolve text
    at write time from the live DB (same KB version as benchmark config).
    """
    return {}


def main():
    sys.path.insert(0, str(ROOT / "components" / "knowledgebase" / "kb-manager"))
    os.chdir(str(ROOT / "components" / "knowledgebase" / "kb-manager"))
    from sqlalchemy import text as sqltext
    from kb_manager.config import load_config
    from kb_manager.models.database import Database
    import asyncio

    rows = [json.loads(l) for l in open(RAW, encoding="utf-8")]
    ok = [r for r in rows if r.get("status") == "SUCCESS" and r.get("n_gold", 0) > 0]
    print(f"usable rows: {len(ok)}/{len(rows)}")

    async def fetch_texts(ids: set) -> dict:
        cfg = load_config()
        db = Database(cfg.db)
        out = {}
        ids = list(ids)
        async with db.session() as s:
            for i in range(0, len(ids), 500):
                chunk = ids[i:i + 500]
                r = await s.execute(
                    sqltext("SELECT id, content FROM chunks WHERE id = ANY(:ids)"
                            if "postgres" in cfg.db.async_url else
                            "SELECT id, content FROM chunks WHERE id IN (%s)" % ",".join("?" * len(chunk))),
                    {"ids": chunk} if "postgres" in cfg.db.async_url else tuple(chunk))
                for cid, content in r.fetchall():
                    out[cid] = content or ""
        await db.close()
        return out

    # collect all needed IDs
    need: set = set()
    cand_rows = []
    for r in ok:
        golds = sorted(r["relevance"], key=lambda c: -r["relevance"][c])
        pos_id = golds[0]
        need.add(pos_id)
        stages = r["stages"]
        picks = {}
        for stage, key in (("bm25", "bm25_neg"), ("dense", "dense_neg"),
                           ("rrf", "rrf_neg"), ("final", "ce_neg")):
            for rank, d in enumerate(stages[stage], 1):
                if d["id"] not in r["relevance"]:
                    picks[key] = {"id": d["id"], "rank": rank,
                                  "score": d["scores"].get(
                                      {"bm25": "bm25_score", "dense": "dense_score",
                                       "rrf": "hybrid_score", "final": "rerank_score"}[stage])}
                    need.add(d["id"])
                    break
        cand_rows.append((r, pos_id, picks))

    texts = asyncio.run(fetch_texts(need))
    print(f"fetched {len(texts)}/{len(need)} chunk texts")

    # dedupe by question text BEFORE splitting (leakage protection)
    groups: dict = defaultdict(list)
    for r, pos_id, picks in cand_rows:
        groups[r["query"].strip()].append((r, pos_id, picks))
    gkeys = sorted(groups)
    n = len(gkeys)
    n_train = int(n * 0.8)
    n_val = int(n * 0.1)
    splits = {"train": set(gkeys[:n_train]), "val": set(gkeys[n_train:n_train + n_val]),
              "test": set(gkeys[n_train + n_val:])}
    print(f"groups: {n} train={len(splits['train'])} val={len(splits['val'])} test={len(splits['test'])}")

    OUT.mkdir(parents=True, exist_ok=True)
    stats = {"splits": {}, "neg_source_counts": {s: 0 for s in
             ["bm25_neg", "dense_neg", "rrf_neg", "ce_neg"]}}
    fhs = {s: open(OUT / f"retrieval_pairs_{s}.jsonl", "w", encoding="utf-8")
           for s in splits}
    fh_multi = open(OUT / "retrieval_pairs_multi.jsonl", "w", encoding="utf-8")
    fh_hard = open(OUT / "hard_negatives.jsonl", "w", encoding="utf-8")

    for qtext, items in groups.items():
        split = next(s for s, ks in splits.items() if qtext in ks)
        for r, pos_id, picks in items:
            pos_text = texts.get(pos_id, "")
            if not pos_text:
                continue
            negs = []
            for ntype, pk in picks.items():
                nt = texts.get(pk["id"], "")
                if not nt:
                    continue
                negs.append((ntype, pk, nt))
                stats["neg_source_counts"][ntype] += 1
            if not negs:
                continue
            # Format B: one row per (query, pos, neg)
            for ntype, pk, nt in negs:
                fhs[split].write(json.dumps({
                    "query": r["query"], "query_idx": r["idx"],
                    "pos": {"id": pos_id, "text": pos_text,
                            "grade": r["relevance"][pos_id]},
                    "neg": {"id": pk["id"], "text": nt, "source": ntype,
                            "rank": pk["rank"], "score": pk["score"]},
                    "split": split}, ensure_ascii=False) + "\n")
            # Format C: multi
            fh_multi.write(json.dumps({
                "query": r["query"], "query_idx": r["idx"], "split": split,
                "pos": {"id": pos_id, "text": pos_text},
                "neg": [{"id": pk["id"], "text": nt, "source": ntype,
                         "rank": pk["rank"], "score": pk["score"]}
                        for ntype, pk, nt in negs]}, ensure_ascii=False) + "\n")
            # hard negatives: CE-fooled (rank<=3) or RRF-top non-gold
            for ntype, pk, nt in negs:
                if (ntype == "ce_neg" and pk["rank"] <= 3) or \
                   (ntype == "rrf_neg" and pk["rank"] <= 3):
                    fh_hard.write(json.dumps({
                        "query": r["query"], "query_idx": r["idx"], "split": split,
                        "pos_id": pos_id, "neg_id": pk["id"], "neg_text": nt,
                        "source": ntype, "rank": pk["rank"], "score": pk["score"]},
                        ensure_ascii=False) + "\n")
    for fh in list(fhs.values()) + [fh_multi, fh_hard]:
        fh.close()
    for s, fh in fhs.items():
        pass
    import subprocess as sp
    stats["splits"] = {s: sum(1 for _ in open(OUT / f"retrieval_pairs_{s}.jsonl", encoding="utf-8"))
                       for s in splits}
    stats["generated_at"] = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).isoformat()
    try:
        stats["git_sha"] = sp.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                                           text=True).strip()
    except Exception:
        stats["git_sha"] = "unknown"
    json.dump(stats, open(OUT / "dataset_statistics.json", "w"), indent=2)
    print("stats:", json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
