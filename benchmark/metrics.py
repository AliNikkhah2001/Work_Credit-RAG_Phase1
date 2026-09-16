"""Multi-K retrieval metrics with explicit single/multi-gold semantics.

Ground-truth model: relevance dict {doc_id: grade} (binary if grades are 0/1,
graded if coverage ratios). Queries with NO golds are excluded from means
(caller must count them separately as NO_GOLD).
"""
from __future__ import annotations

import math

K_VALUES = [1, 3, 5, 10, 15, 20, 50, 100]


def _gold_set(relevance: dict) -> set:
    return {d for d, g in relevance.items() if g > 0}


def recall_at_k(retrieved: list, relevance: dict, k: int) -> float:
    gold = _gold_set(relevance)
    if not gold:
        raise ValueError("recall undefined with no golds")
    return len(set(retrieved[:k]) & gold) / len(gold)


def hit_at_k(retrieved: list, relevance: dict, k: int) -> float:
    gold = _gold_set(relevance)
    if not gold:
        raise ValueError("hit undefined with no golds")
    return 1.0 if (set(retrieved[:k]) & gold) else 0.0


def reciprocal_rank(retrieved: list, relevance: dict) -> float:
    gold = _gold_set(relevance)
    if not gold:
        raise ValueError("RR undefined with no golds")
    for i, doc in enumerate(retrieved, 1):
        if doc in gold:
            return 1.0 / i
    return 0.0


def dcg_at_k(retrieved: list, relevance: dict, k: int) -> float:
    return sum((2.0 ** relevance.get(doc, 0.0) - 1.0) / math.log2(i + 2)
               for i, doc in enumerate(retrieved[:k]))


def ndcg_at_k(retrieved: list, relevance: dict, k: int) -> float:
    ideal = sorted((g for g in relevance.values() if g > 0), reverse=True)[:k]
    idcg = sum((2.0 ** g - 1.0) / math.log2(i + 2) for i, g in enumerate(ideal))
    if idcg == 0:
        raise ValueError("NDCG undefined with no golds")
    return dcg_at_k(retrieved, relevance, k) / idcg


def gold_rank(retrieved: list, relevance: dict) -> int:
    """1-based rank of first gold; -1 if absent (documented convention)."""
    gold = _gold_set(relevance)
    for i, doc in enumerate(retrieved, 1):
        if doc in gold:
            return i
    return -1


def query_metrics(retrieved: list, relevance: dict, ks: list = K_VALUES) -> dict:
    """All metrics for one query; raises ValueError if no golds."""
    m = {"rr": reciprocal_rank(retrieved, relevance),
         "gold_rank": gold_rank(retrieved, relevance)}
    for k in ks:
        m[f"recall@{k}"] = recall_at_k(retrieved, relevance, k)
        m[f"hit@{k}"] = hit_at_k(retrieved, relevance, k)
        m[f"ndcg@{k}"] = ndcg_at_k(retrieved, relevance, k)
    return m
