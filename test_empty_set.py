import numpy as np

allowed_ids = set()
doc_ids = ["a", "b", "c"]
def score(q, i): return i

scored = [(doc_ids[i], score("q", i)) for i in range(len(doc_ids)) if doc_ids[i] in allowed_ids]
print("BM25 Scored with empty set:", scored)

sims = np.array([0.1, 0.2, 0.3])
mask = np.array([cid not in allowed_ids for cid in doc_ids])
sims[mask] = -np.inf
order = np.argsort(-sims)
res = [(doc_ids[i], float(sims[i])) for i in order if sims[i] != -np.inf]
print("Dense Scored with empty set:", res)
