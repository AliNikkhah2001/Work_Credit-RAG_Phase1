"""Remap stale expected_chunk_ids -> answer-grounded gold chunks from live PG KB.
For each QA pair: chunks whose content covers >= THRESH of expected_answer tokens
become the new expected_ids. Prints coverage stats for threshold selection.
Usage: remap_gold.py [threshold]  (default: analyze thresholds 0.3..0.8)
"""
import json
import re
import sys

import psycopg2

STOP = set("و در به از که با این است شد شده را برای آن یا ما شما ایشان آن‌ها yra می ها های تر ترین".split())


def toks(s):
    s = re.sub(r"[\u200c]", " ", s or "")
    s = s.replace("ي", "ی").replace("ك", "ک")
    words = re.findall(r"[\w\u0600-\u06FF]+", s)
    return {w for w in words if len(w) > 2 and w not in STOP}


def main():
    con = psycopg2.connect("host=127.0.0.1 dbname=kb_manager user=postgres password=postgres")
    cur = con.cursor()
    cur.execute("SELECT id, content FROM chunks")
    chunks = [(cid, toks(c)) for cid, c in cur.fetchall()]
    print(f"chunks: {len(chunks)}", flush=True)
    d = json.load(open("/workspace/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager/kb_manager/evaluation/datasets/eval_clean.json"))
    items = d if isinstance(d, list) else d.get("items", [])
    print(f"questions: {len(items)}", flush=True)
    ats = [toks(x.get("expected_answer", "")) for x in items]
    thresh_arg = float(sys.argv[1]) if len(sys.argv) > 1 else None
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
        import statistics
        print(f"th={th}: pairs_with_gold={sum(1 for c in counts if c>0)}/{len(counts)} "
              f"mean_gold={statistics.mean(counts):.1f} median={statistics.median(counts):.1f} "
              f"empty_answer={empty}", flush=True)
    if thresh_arg:
        th = thresh_arg
        out = []
        for x, at in zip(items, ats):
            gold = [cid for cid, ct in chunks if at and len(at & ct) / len(at) >= th]
            x2 = dict(x)
            x2["expected_chunk_ids"] = gold
            out.append(x2)
        json.dump(out, open("/tmp/opencode/eval_remapped.json", "w", encoding="utf-8"), ensure_ascii=False)
        print(f"saved /tmp/opencode/eval_remapped.json", flush=True)


if __name__ == "__main__":
    main()
