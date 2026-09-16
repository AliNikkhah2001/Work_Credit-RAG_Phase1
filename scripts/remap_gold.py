#!/usr/bin/env python3
"""Remap stale expected_chunk_ids -> answer-grounded gold chunks from the live PG KB.

Method (same as wave-1 handoff/scripts/remap_gold.py): for each QA pair, chunks
whose content covers >= THRESH of expected_answer tokens become gold. Additionally
records per-gold coverage as graded relevance for NDCG.

Ground-truth semantics (documented explicitly):
- relevance_scores: {chunk_id: coverage_ratio} for coverage >= THRESH (binary
  view: all listed chunks are relevant; graded view: value = coverage).
- expected_chunk_ids: sorted gold IDs (coverage desc).
- 4 queries have empty expected_answer -> excluded (no ground truth possible).

Usage: KB_DB_URL=... /tmp/kb-venv/bin/python scripts/remap_gold.py [threshold] [out_json]
"""
import json
import os
import re
import statistics
import sys
from datetime import datetime, timezone

STOP = set("و در به از که با این است شد شده را برای آن یا ما شما ایشان آنها yra می ها های تر ترین".split())


def toks(s):
    s = re.sub(r"[\u200c]", " ", s or "")
    s = s.replace("ي", "ی").replace("ك", "ک")
    words = re.findall(r"[\w\u0600-\u06FF]+", s)
    return {w for w in words if len(w) > 2 and w not in STOP}


def main():
    import psycopg2
    thresh_arg = float(sys.argv[1]) if len(sys.argv) > 1 else None
    out_path = sys.argv[2] if len(sys.argv) > 2 else "benchmark/datasets/eval_remapped.json"

    con = psycopg2.connect("host=127.0.0.1 dbname=kb_manager user=postgres password=postgres")
    cur = con.cursor()
    cur.execute("SELECT id, content FROM chunks")
    chunks = [(cid, toks(c)) for cid, c in cur.fetchall()]
    print(f"chunks: {len(chunks)}", flush=True)

    src = "components/knowledgebase/kb-manager/kb_manager/evaluation/datasets/eval_clean.json"
    d = json.load(open(src, encoding="utf-8"))
    items = d if isinstance(d, list) else d.get("items", [])
    print(f"questions: {len(items)}", flush=True)
    ats = [toks(x.get("expected_answer", "")) for x in items]

    thresh_list = [thresh_arg] if thresh_arg else [0.3, 0.4, 0.5, 0.6, 0.7]
    for th in thresh_list:
        counts, empty = [], 0
        for at in ats:
            if not at:
                empty += 1
                counts.append(0)
                continue
            gold = [cid for cid, ct in chunks if len(at & ct) / len(at) >= th]
            counts.append(len(gold))
        print(f"th={th}: pairs_with_gold={sum(1 for c in counts if c > 0)}/{len(counts)} "
              f"mean_gold={statistics.mean(counts):.1f} median={statistics.median(counts):.1f} "
              f"empty_answer={empty}", flush=True)

    if thresh_arg:
        th = thresh_arg
        out, excluded = [], []
        for i, (x, at) in enumerate(zip(items, ats)):
            if not at:
                excluded.append(i)
                continue
            scored = sorted(((len(at & ct) / len(at), cid) for cid, ct in chunks if len(at & ct) / len(at) >= th),
                            reverse=True)
            x2 = dict(x)
            x2["expected_chunk_ids"] = [cid for _, cid in scored]
            x2["relevance_scores"] = {cid: round(cov, 4) for cov, cid in scored}
            x2["remap_threshold"] = th
            out.append(x2)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        meta = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_dataset": src,
            "threshold": th,
            "n_input": len(items),
            "n_kept": len(out),
            "n_excluded_empty_answer": len(excluded),
            "excluded_indices": excluded,
            "db_chunks": len(chunks),
        }
        json.dump({"meta": meta, "items": out}, open(out_path, "w", encoding="utf-8"),
                  ensure_ascii=False)
        print(f"saved {out_path} ({len(out)} items, {len(excluded)} excluded)", flush=True)


if __name__ == "__main__":
    main()
