"""Hand-computed validation for benchmark/metrics.py. Must fail loudly if wrong."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from benchmark.metrics import recall_at_k, hit_at_k, reciprocal_rank, ndcg_at_k, gold_rank


def check(name, got, want, tol=1e-9):
    assert abs(got - want) < tol, f"{name}: got {got}, want {want}"
    print(f"  ok {name}={got:.6f}")


# Case 1: single gold at rank 1. ranking=[A,B,C], gold={A:1}
r = ["A", "B", "C"]
rel = {"A": 1.0}
check("recall@1", recall_at_k(r, rel, 1), 1.0)
check("hit@1", hit_at_k(r, rel, 1), 1.0)
check("rr", reciprocal_rank(r, rel), 1.0)
check("ndcg@1", ndcg_at_k(r, rel, 1), 1.0)
assert gold_rank(r, rel) == 1

# Case 2: single gold at rank 3. ranking=[B,C,A]
r = ["B", "C", "A"]
check("recall@1", recall_at_k(r, rel, 1), 0.0)
check("recall@3", recall_at_k(r, rel, 3), 1.0)
check("hit@3", hit_at_k(r, rel, 3), 1.0)
check("rr", reciprocal_rank(r, rel), 1.0 / 3)
check("ndcg@3", ndcg_at_k(r, rel, 3), (2**1 - 1) / math.log2(4))  # DCG=1/log2(4), IDCG=1
assert gold_rank(r, rel) == 3

# Case 3: gold absent
r = ["B", "C", "D"]
check("recall@3", recall_at_k(r, rel, 3), 0.0)
check("rr", reciprocal_rank(r, rel), 0.0)
check("ndcg@3", ndcg_at_k(r, rel, 3), 0.0)
assert gold_rank(r, rel) == -1

# Case 4: multi-gold {A:1,B:1}, ranking=[B,X,A] -> recall@3=1.0? golds found: B,A = 2/2
rel2 = {"A": 1.0, "B": 1.0}
r = ["B", "X", "A"]
check("recall@2", recall_at_k(r, rel2, 2), 0.5)
check("recall@3", recall_at_k(r, rel2, 3), 1.0)
check("rr", reciprocal_rank(r, rel2), 1.0)
# NDCG@3 graded check: DCG = 1/log2(2) + 0 + 1/log2(4); IDCG = 1/log2(2)+1/log2(3)
dcg = 1 / math.log2(2) + 1 / math.log2(4)
idcg = 1 / math.log2(2) + 1 / math.log2(3)
check("ndcg@3 multi", ndcg_at_k(r, rel2, 3), dcg / idcg)

# Case 5: graded relevance {A:1.0, B:0.5}, ranking=[B,A]
rel3 = {"A": 1.0, "B": 0.5}
r = ["B", "A"]
dcg = (2**0.5 - 1) / math.log2(2) + (2**1 - 1) / math.log2(3)
idcg = (2**1 - 1) / math.log2(2) + (2**0.5 - 1) / math.log2(3)
check("ndcg@2 graded", ndcg_at_k(r, rel3, 2), dcg / idcg)

# Case 6: empty retrieval
check("recall@5 empty", recall_at_k([], rel, 5), 0.0)
check("rr empty", reciprocal_rank([], rel), 0.0)
assert gold_rank([], rel) == -1

# Case 7: fewer than K candidates
check("recall@100 short", recall_at_k(["A"], rel, 100), 1.0)
check("hit@100 short", hit_at_k(["B"], rel, 100), 0.0)

# Case 8: duplicate IDs in ranking (degenerate but must not crash/inflate)
check("recall@3 dup", recall_at_k(["B", "B", "B"], rel, 3), 0.0)
check("recall@3 duphit", recall_at_k(["A", "A", "A"], rel, 3), 1.0)

# Case 9: no-gold queries raise (caller must exclude, not average as zero)
for fn in (lambda: recall_at_k(["A"], {}, 5), lambda: reciprocal_rank(["A"], {}),
           lambda: ndcg_at_k(["A"], {}, 5)):
    try:
        fn()
        raise AssertionError("expected ValueError for empty golds")
    except ValueError:
        pass
print("  ok no-gold raises ValueError")

# Case 10: cross-check vs kb_manager implementation at k=10
sys.path.insert(0, "components/knowledgebase/kb-manager")
from kb_manager.evaluation.metrics import RetrievalMetrics, RetrievalResult
rr = RetrievalResult(query="q", retrieved_ids=["B", "C", "A"],
                     retrieved_scores=[0.9, 0.8, 0.7],
                     expected_ids=["A"], relevance_scores={"A": 1.0})
assert abs(RetrievalMetrics.mrr([rr]) - 1 / 3) < 1e-9
assert abs(RetrievalMetrics.hit_rate_at_k([rr], 3) - 1.0) < 1e-9
assert abs(RetrievalMetrics.hit_rate_at_k([rr], 1) - 0.0) < 1e-9
assert abs(RetrievalMetrics.ndcg_at_k([rr], 3) - ((2**1 - 1) / math.log2(4))) < 1e-9
print("  ok cross-check vs kb_manager.metrics (mrr/hit/ndcg)")

print("ALL METRIC TESTS PASSED")
