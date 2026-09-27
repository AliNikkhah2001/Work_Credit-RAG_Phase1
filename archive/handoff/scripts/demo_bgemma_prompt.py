"""Live demo: bge-reranker-v2-gemma with default vs detailed scoring prompt.
Scores 3 Persian pairs (gold / hard-negative / easy-negative) under each prompt.
Usage: KB_DB_URL=... HF_HOME=... HF_HUB_CACHE=... HF_HUB_OFFLINE=1 python demo_bgemma_prompt.py
"""
import json
import sys

sys.path.insert(0, "/workspace/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager")

import psycopg2
from kb_manager.reranker import DEFAULT_LLM_RERANK_PROMPT, FlagEmbeddingReranker

con = psycopg2.connect("host=127.0.0.1 dbname=kb_manager user=postgres password=postgres")
cur = con.cursor()
d = json.load(open("/tmp/opencode/eval_remapped.json"))
q = d[0]
query = q["query"]
gold_id = q["expected_chunk_ids"][0]
cur.execute("SELECT content FROM chunks WHERE id=%s", (gold_id,))
gold = cur.fetchone()[0][:600]
cur.execute("SELECT content FROM chunks WHERE id NOT IN %s ORDER BY RANDOM() LIMIT 2",
            (tuple(q["expected_chunk_ids"][:50]),))
negs = [r[0][:600] for r in cur.fetchall()]

pairs = [("GOLD", gold), ("NEG-A", negs[0]), ("NEG-B", negs[1])]
print("QUERY:", query[:150], "\n")

rr = FlagEmbeddingReranker(model_name="BAAI/bge-reranker-v2-gemma", batch_size=4)
rr._ensure_model()
print("model loaded:", type(rr._reranker).__name__)

for label, prompt in [("DEFAULT", None), ("DETAILED", DEFAULT_LLM_RERANK_PROMPT)]:
    scores = rr._reranker.compute_score([[query, p] for _, p in pairs], prompt=prompt)
    print(f"--- {label} ---")
    for (name, _), s in zip(pairs, scores):
        print(f"  {name}: {float(s):+.4f}")
    order = sorted(zip([n for n, _ in pairs], scores), key=lambda t: -t[1])
    print("  ranking:", " > ".join(n for n, _ in order))
