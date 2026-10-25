#!/usr/bin/env python3
"""
RAGAS + Custom evaluators for Work Credit RAG benchmark suite.

Implements 8 metrics (each returns 0.0-1.0 with reasoning):
  - faithfulness:           is answer grounded in contexts? (LLM judge: claims support)
  - answer_relevancy:       does answer address question? (LLM judge: relevance)
  - context_relevancy:      are chunks relevant to question? (LLM + BM25/dense proxy)
  - context_recall:         fraction of expected answer covered by context (LLM if GT else overlap)
  - hallucination:          1.0 if answer has facts NOT in context (esp. fake G5), else 0.0
  - ambiguity_resolution:   1.0 if clarified when should vs expected_finish
  - sticky_persistence:     1.0 if kept subspace correctly across turns
  - retrieval_hit:          1.0 if expected subspace in top-K folder_hierarchy

LLM-as-judge:
  Tries POST http://127.0.0.1:9000/v1/chat/completions (then 8100)
  with trust_env=False, asks for JSON {"score": 0.0-1.0, "reason": "..."}.
  On timeout/parse error falls back to deterministic heuristics.

Provides:
  async evaluate_turn(turn, contexts, answer, question, expected) -> dict
  evaluate_bench_results(results_path) -> aggregates dict
  CLI: python3 -m evaluation.ragas_eval --input evaluation/artifacts/bench_results_latest.json

Mirrored to:
  components/orchestrator/evaluation/ragas_eval.py
  components/evaluation/ragas_eval.py
  evaluation/ragas_eval.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Orchestrator at 8100 returns audit.retrieved_chunks[].content[:500], citations, etc.
# KB at 8000 returns final_results[].content_preview, rerank_score, hybrid_score
# LLM judge endpoints in priority order (9000 preferred per spec)
JUDGE_ENDPOINTS: List[str] = [
    "http://127.0.0.1:9000/v1/chat/completions",
    "http://127.0.0.1:8100/v1/chat/completions",
]

# Model candidates for judge (H200 manager id routes to TRT :8010)
JUDGE_MODELS: List[str] = [
    os.getenv("RAGAS_JUDGE_MODEL", ""),
    "gemma-4-31b",
    "qwen2.5-7b",
    "local-llm",
]
JUDGE_MODELS = [m for m in JUDGE_MODELS if m]

JUDGE_TIMEOUT_S = float(os.getenv("RAGAS_JUDGE_TIMEOUT", "25"))
JUDGE_MAX_TOKENS = int(os.getenv("RAGAS_JUDGE_MAX_TOKENS", "256"))
JUDGE_TEMPERATURE = 0.0

# Subspace -> keyword/hierarchy cues
SUBSPACE_KEYWORDS: Dict[str, List[str]] = {
    "cheque": ["چک", "گزارش اعتباری چک", "برگشتی", "رفع سوء اثر", "cheque"],
    "facilities_person": ["اشخاص حقیقی", "تسهیلات", "حقیقی", "اعتبارسنجی تسهیلات"],
    "facilities_legal": ["اشخاص حقوقی", "حقوقی", "تسهیلات", "اعتبارسنجی تسهیلات"],
    "general": ["پایگاه دانش عمومی", "عمومی", "معرفی", "شرکت اعتبارسنجی", "سهامداران", "هیات مدیره", "هیئت مدیره", "قاسم بور"],
    # greeting/mixed have no single keyword
}

SUBSPACE_TO_FILTER_PATH: Dict[str, Optional[str]] = {
    "cheque": "گزارش اعتباری چک",
    "facilities_person": "اشخاص حقیقی/اعتبارسنجی تسهیلات",
    "facilities_legal": "اشخاص حقوقی/اعتبارسنجی تسهیلات",
    "general": "پایگاه دانش عمومی",
    "greeting": None,
    "mixed": None,
}

# Heuristic thresholds
RERANK_THRESHOLD_HIGH = 0.5
RERANK_THRESHOLD_MID = 0.15
NO_EVIDENCE_PHRASE = "پاسخی یافت نشد"
FAKE_GRADE_RE = re.compile(r"G\s*5\b|G5|گرید\s*5", re.IGNORECASE)
GRADE_RE = re.compile(r"\b[A-G]\s*[0-9]\b|\bامتیاز\s*\d+|\bرتبه\s*\d+|\bG\d\b", re.IGNORECASE)
PERSIAN_NORM_MAP = str.maketrans({"ي": "ی", "ك": "ک", "ة": "ه"})

# Module-level cache for discovered endpoint
_discovered_endpoint: Optional[str] = None
_discovered_model: Optional[str] = None

# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Normalize Persian/Arabic chars and whitespace for comparison."""
    if not text:
        return ""
    t = text.translate(PERSIAN_NORM_MAP)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _tokenize(text: str) -> List[str]:
    """Simple whitespace + punctuation tokenizer (Persian-safe)."""
    text = _normalize(text).lower()
    # Keep Persian letters / digits / latin
    text = re.sub(r"[^\w\u0600-\u06FF]+", " ", text)
    toks = [w for w in text.split() if len(w) > 1]
    return toks


def _tokens_set(text: str) -> set:
    return set(_tokenize(text))


def _jaccard(a: str, b: str) -> float:
    sa, sb = _tokens_set(a), _tokens_set(b)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def _overlap_ratio(answer: str, contexts: List[str]) -> float:
    """Max Jaccard between answer and any context."""
    if not answer or not contexts:
        return 0.0
    return max((_jaccard(answer, c) for c in contexts), default=0.0)


def _lexical_coverage(answer: str, contexts: List[str]) -> float:
    """Fraction of answer tokens that appear in at least one context."""
    ans_toks = _tokens_set(answer)
    if not ans_toks:
        return 0.0
    ctx_toks: set = set()
    for c in contexts:
        ctx_toks |= _tokens_set(c)
    if not ctx_toks:
        return 0.0
    covered = len(ans_toks & ctx_toks)
    return covered / len(ans_toks)


def _sentence_split(text: str) -> List[str]:
    """Split Persian text into sentence-like chunks."""
    parts = re.split(r"[.!?؟\n]+", text)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# LLM judge helpers (trust_env=False per AGENTS.md proxy gotcha)
# ---------------------------------------------------------------------------

async def _discover_endpoint() -> Tuple[Optional[str], Optional[str]]:
    """Probe JUDGE_ENDPOINTS for a reachable model; cache result."""
    global _discovered_endpoint, _discovered_model
    if _discovered_endpoint is not None:
        return _discovered_endpoint, _discovered_model

    try:
        import httpx
    except ImportError:
        return None, None

    # Try to list models at 9000 first to pick the best available
    for base_url in JUDGE_ENDPOINTS:
        # Derive /v1/models from /v1/chat/completions
        models_url = base_url.replace("/v1/chat/completions", "/v1/models")
        try:
            async with httpx.AsyncClient(timeout=5, trust_env=False) as cl:
                r = await cl.get(models_url)
                if r.status_code == 200:
                    data = r.json()
                    ids = [m.get("id", "") for m in data.get("data", [])]
                    # Prefer enrolled judge models that exist in registry
                    for cand in JUDGE_MODELS:
                        if cand in ids:
                            _discovered_endpoint = base_url
                            _discovered_model = cand
                            return _discovered_endpoint, _discovered_model
                    if ids:
                        _discovered_endpoint = base_url
                        _discovered_model = ids[0]
                        return _discovered_endpoint, _discovered_model
        except Exception:
            continue

    # Fallback: just try the first endpoint that accepts a tiny request
    for url in JUDGE_ENDPOINTS:
        for cand in JUDGE_MODELS:
            try:
                import httpx as _hx
                async with _hx.AsyncClient(timeout=5, trust_env=False) as cl:
                    r = await cl.post(
                        url,
                        json={
                            "model": cand,
                            "messages": [{"role": "user", "content": "ping"}],
                            "max_tokens": 4,
                            "temperature": 0.0,
                        },
                        headers={"Authorization": "Bearer sk-local-dev"},
                    )
                    if r.status_code < 500:
                        _discovered_endpoint = url
                        _discovered_model = cand
                        return _discovered_endpoint, _discovered_model
            except Exception:
                continue
    return None, None


async def _call_llm(prompt: str, timeout_s: float = JUDGE_TIMEOUT_S) -> Optional[str]:
    """Call LLM judge with structured JSON prompt; return content or None on failure."""
    try:
        import httpx
    except ImportError:
        return None

    endpoint, model = await _discover_endpoint()
    if endpoint is None or model is None:
        return None

    # Try discovered endpoint then remaining fallbacks
    ordered = [endpoint] + [u for u in JUDGE_ENDPOINTS if u != endpoint]
    for url in ordered:
        for m in ([model] + [x for x in JUDGE_MODELS if x != model]):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(timeout_s, connect=10.0, read=timeout_s, write=timeout_s, pool=10.0),
                    trust_env=False,
                ) as cl:
                    resp = await cl.post(
                        url,
                        json={
                            "model": m,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": JUDGE_MAX_TOKENS,
                            "temperature": JUDGE_TEMPERATURE,
                            "chat_template_kwargs": {"enable_thinking": False},
                        },
                        headers={"Authorization": "Bearer sk-local-dev"},
                    )
                    if resp.status_code == 404 and "model" in resp.text.lower():
                        continue  # try next model
                    resp.raise_for_status()
                    data = resp.json()
                    content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
                    if content.strip():
                        # cache successful endpoint/model for next calls
                        global _discovered_endpoint, _discovered_model
                        _discovered_endpoint = url
                        _discovered_model = m
                        return content
            except Exception:
                continue
    return None


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Try to parse JSON {"score": float, "reason": str} from free-form LLM output."""
    if not text:
        return None
    # Direct parse
    try:
        obj = json.loads(text.strip())
        if isinstance(obj, dict) and "score" in obj:
            return obj
    except Exception:
        pass
    # Extract JSON block
    for pat in [r"\{[^{}]*\"score\"[^{}]*\}", r"\{.*?\}"]:
        m = re.search(pat, text, re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(0))
                if isinstance(obj, dict) and "score" in obj:
                    return obj
            except Exception:
                continue
    # Loose score extraction
    m = re.search(r'"?score"?\s*[:=]\s*([0-9]*\.?[0-9]+)', text)
    if m:
        try:
            s = float(m.group(1))
            # Clamp
            s = max(0.0, min(1.0, s))
            # Extract reason heuristically
            reason_m = re.search(r'"?reason"?\s*[:=]\s*"(.*?)"', text, re.DOTALL)
            reason = reason_m.group(1) if reason_m else text.strip()[:300]
            return {"score": s, "reason": reason}
        except Exception:
            pass
    return None


async def _llm_score(prompt: str, fallback_score: float, fallback_reason: str) -> Tuple[float, str, str]:
    """
    Call LLM judge; return (score, reason, source).
    source is "llm" or "heuristic".
    """
    raw = await _call_llm(prompt)
    if raw is None:
        return fallback_score, fallback_reason, "heuristic"
    parsed = _extract_json(raw)
    if parsed is None:
        return fallback_score, f"heuristic (unparseable LLM: {raw[:120]!r}; {fallback_reason})", "heuristic"
    try:
        score = float(parsed.get("score", fallback_score))
        score = max(0.0, min(1.0, score))
        reason = str(parsed.get("reason", ""))[:500] or raw[:300]
        return score, reason, "llm"
    except Exception:
        return fallback_score, fallback_reason, "heuristic"


# ---------------------------------------------------------------------------
# Prompt builders (LLM-as-judge)
# ---------------------------------------------------------------------------

def _prompt_faithfulness(question: str, contexts: List[str], answer: str) -> str:
    ctx_block = "\n".join(f"[Context {i+1}] {c[:600]}" for i, c in enumerate(contexts[:5])) or "(no contexts retrieved)"
    return (
        "You are a RAG faithfulness judge. Determine if the ANSWER is grounded in the CONTEXTS.\n"
        "Extract claims from the answer and check if each is supported by the contexts.\n"
        "Score 1.0 if all claims are supported, 0.0 if no claims are supported, proportional otherwise.\n"
        'Return ONLY JSON: {"score": 0.0-1.0, "reason": "short explanation"}.\n'
        f"QUESTION: {question[:400]}\n"
        f"CONTEXTS:\n{ctx_block}\n"
        f"ANSWER: {answer[:1200]}\n"
        "JSON:"
    )


def _prompt_answer_relevancy(question: str, answer: str) -> str:
    return (
        "You are a RAG answer relevancy judge. Does the ANSWER directly address the QUESTION?\n"
        "Score 1.0 if fully relevant, 0.0 if completely irrelevant, proportional otherwise.\n"
        'Return ONLY JSON: {"score": 0.0-1.0, "reason": "short explanation"}.\n'
        f"QUESTION: {question[:400]}\n"
        f"ANSWER: {answer[:1200]}\n"
        "JSON:"
    )


def _prompt_context_relevancy(question: str, contexts: List[str]) -> str:
    ctx_block = "\n".join(f"[Chunk {i+1}] {c[:500]}" for i, c in enumerate(contexts[:5])) or "(no chunks)"
    return (
        "You are a RAG context relevancy judge. Are the retrieved CHUNKS relevant to the QUESTION?\n"
        "Score = relevant_chunks / total_chunks. 1.0 if all relevant, 0.0 if none.\n"
        'Return ONLY JSON: {"score": 0.0-1.0, "reason": "short explanation"}.\n'
        f"QUESTION: {question[:400]}\n"
        f"CHUNKS:\n{ctx_block}\n"
        "JSON:"
    )


def _prompt_context_recall(ground_truth: str, contexts: List[str]) -> str:
    ctx_block = "\n".join(f"[Context {i+1}] {c[:600]}" for i, c in enumerate(contexts[:5])) or "(no contexts)"
    return (
        "You are a RAG context recall judge. How much of the GROUND TRUTH is covered by the CONTEXTS?\n"
        "Score = covered_facts / total_facts. 1.0 if fully covered, 0.0 if not covered at all.\n"
        'Return ONLY JSON: {"score": 0.0-1.0, "reason": "short explanation"}.\n'
        f"GROUND TRUTH: {ground_truth[:800]}\n"
        f"CONTEXTS:\n{ctx_block}\n"
        "JSON:"
    )


# ---------------------------------------------------------------------------
# Deterministic / heuristic evaluators (fallbacks)
# ---------------------------------------------------------------------------

ABSTENTION_PHRASES = ["پاسخی یافت نشد", "وجود ندارد", "یافت نشد", "نامعتبر", "چنین رتبه", "چنین درجه"]

def _is_abstention(answer: str) -> bool:
    return any(p in answer for p in ABSTENTION_PHRASES)

def _heuristic_faithfulness(answer: str, contexts: List[str]) -> Tuple[float, str]:
    """Lexical overlap fallback for faithfulness."""
    if not answer or not answer.strip():
        return 0.0, "empty answer"
    if NO_EVIDENCE_PHRASE in answer or _is_abstention(answer):
        # Abstention / no-evidence is faithful (correct refusal) regardless of contexts
        if not contexts or all(not c.strip() for c in contexts):
            return 1.0, "abstention/no-evidence with no contexts -> faithful"
        return 0.9, "abstention/no-evidence -> mostly faithful"
    if not contexts:
        # No contexts but answer claims something -> ungrounded, except greeting/clarification
        if "سلام" in answer and len(answer) < 200:
            return 1.0, "greeting with no contexts -> faithful (no grounding needed)"
        if "لطفاً مشخص کنید" in answer or "کدام" in answer:
            return 0.9, "clarification with no contexts -> faithful"
        return 0.0, "no contexts but answer has content -> ungrounded"
    sents = _sentence_split(answer)
    if not sents:
        sents = [answer]
    # For each sentence, check if lexical coverage > 0.25 with any context
    supported = 0
    for s in sents:
        coverage = max((_lexical_coverage(s, [c]) for c in contexts), default=0.0)
        jacc = _overlap_ratio(s, contexts)
        if coverage >= 0.4 or jacc >= 0.25:
            supported += 1
        elif coverage >= 0.2 and len(s.split()) <= 8:
            supported += 0.5  # partial credit for short claims
    score = supported / len(sents) if sents else 0.0
    return max(0.0, min(1.0, score)), f"heuristic: {supported:.1f}/{len(sents)} claims supported (lexical overlap)"


def _heuristic_answer_relevancy(question: str, answer: str) -> Tuple[float, str]:
    """Lexical overlap fallback for answer relevancy."""
    if not answer or not answer.strip():
        return 0.0, "empty answer"
    if not question or not question.strip():
        return 0.5, "no question -> neutral"
    # Greeting shortcut
    if question.strip() in ("سلام", "سلام علیکم", "سلام خوبی؟") and "سلام" in answer:
        return 1.0, "greeting matched"
    if NO_EVIDENCE_PHRASE in answer or _is_abstention(answer) or "یافت نشد" in answer:
        # No-evidence can still be relevant if retrieval was empty
        # Score it as 0.6 (partial) rather than 0
        return 0.6, "no-evidence/abstention response -> partially relevant (abstained)"
    jacc = _jaccard(question, answer)
    # Boost if answer contains question keywords
    q_toks = _tokens_set(question)
    a_toks = _tokens_set(answer)
    keyword_recall = len(q_toks & a_toks) / len(q_toks) if q_toks else 0.0
    # Blend
    score = 0.5 * jacc + 0.5 * keyword_recall
    # Scale up: heuristic jaccard is naturally low (0.05-0.2) so map to 0-1
    # If answer is long and overlaps at least one keyword, give at least 0.5
    if keyword_recall > 0.3 and len(a_toks) > 10:
        score = max(score, 0.55)
    if keyword_recall > 0.5:
        score = max(score, 0.7)
    return max(0.0, min(1.0, score)), f"heuristic: jaccard={jacc:.2f} keyword_recall={keyword_recall:.2f}"


def _heuristic_context_relevancy(question: str, contexts: List[str], rerank_scores: Optional[List[float]] = None) -> Tuple[float, str]:
    """Hybrid: token overlap + rerank_score proxy."""
    if not contexts:
        # greeting has no context but is not irrelevant
        if question.strip() in ("سلام", "سلام علیکم"):
            return 1.0, "greeting needs no context"
        return 0.0, "no contexts -> 0 relevance"
    # Rerank score proxy (primary signal when available)
    if rerank_scores:
        valid = [float(s) for s in rerank_scores if isinstance(s, (int, float))]
        if valid:
            avg = sum(valid) / len(valid)
            mx = max(valid)
            if mx >= RERANK_THRESHOLD_HIGH:
                return 0.95, f"heuristic: max rerank_score {mx:.3f} >= {RERANK_THRESHOLD_HIGH} -> highly relevant"
            if avg >= RERANK_THRESHOLD_MID:
                return 0.75, f"heuristic: avg rerank_score {avg:.3f} >= {RERANK_THRESHOLD_MID} -> relevant"
            if avg >= 0.05:
                return 0.5, f"heuristic: avg rerank_score {avg:.3f} -> partially relevant"
            return 0.25, f"heuristic: low avg rerank_score {avg:.3f}"
    # Lexical fallback: overlap between question and each chunk
    relevant = 0
    for c in contexts:
        j = _jaccard(question, c)
        cov = _lexical_coverage(question, [c])
        if j >= 0.12 or cov >= 0.35:
            relevant += 1
        elif j >= 0.06 or cov >= 0.2:
            relevant += 0.5
    score = relevant / len(contexts) if contexts else 0.0
    return max(0.0, min(1.0, score)), f"heuristic: {relevant:.1f}/{len(contexts)} chunks relevant (lexical)"


def _heuristic_context_recall(question: str, contexts: List[str], ground_truth: Optional[str] = None, answer: str = "") -> Tuple[float, str]:
    """If GT provided, token recall vs contexts; else chunk overlap heuristic."""
    if ground_truth and ground_truth.strip():
        gt_toks = _tokens_set(ground_truth)
        if not gt_toks:
            return 0.5, "empty ground truth"
        ctx_toks: set = set()
        for c in contexts:
            ctx_toks |= _tokens_set(c)
        if not ctx_toks:
            return 0.0, "no contexts to cover ground truth"
        recall = len(gt_toks & ctx_toks) / len(gt_toks)
        return max(0.0, min(1.0, recall)), f"heuristic GT token recall {recall:.2f} vs contexts"
    # No GT: estimate from contexts existence and overlap with question/answer
    if not contexts:
        return 0.0, "no contexts -> no recall"
    # If answer is no-evidence, recall is low unless contexts truly empty
    if answer and NO_EVIDENCE_PHRASE in answer:
        return 0.2, "no-evidence answer -> low recall (contexts did not support answer)"
    # Proxy: how much of the question's intent is covered by contexts
    # Use max overlap between question and any chunk as recall signal
    max_overlap = _overlap_ratio(question, contexts)
    # Also consider answer-context overlap as recall signal when no GT
    if answer:
        ans_overlap = _lexical_coverage(answer, contexts)
        blended = 0.6 * max_overlap + 0.4 * ans_overlap
    else:
        blended = max_overlap
    # Map to 0-1 with some calibration
    if blended >= 0.4:
        return 0.85, f"heuristic max_overlap {max_overlap:.2f} blended {blended:.2f}"
    if blended >= 0.2:
        return 0.6, f"heuristic max_overlap {max_overlap:.2f} blended {blended:.2f}"
    if blended >= 0.08:
        return 0.35, f"heuristic max_overlap {max_overlap:.2f} blended {blended:.2f}"
    return 0.15, f"heuristic low coverage max_overlap {max_overlap:.2f}"


def _deterministic_hallucination(answer: str, contexts: List[str], question: str = "", expected: Optional[Dict[str, Any]] = None) -> Tuple[float, str]:
    """
    1.0 = hallucinated (bad), 0.0 = not hallucinated (good).
    Spec: hallucination is 1.0 if answer contains facts NOT in context (especially G5 fake grades).
    """
    if not answer or not answer.strip():
        return 0.0, "empty answer -> not hallucinated"
    if NO_EVIDENCE_PHRASE in answer or _is_abstention(answer):
        # Any abstention phrase that says "does not exist / not found" is not hallucinated
        # Check that it's not inventing a grade alongside the abstention
        if "وجود ندارد" in answer or "یافت نشد" in answer or "نامعتبر" in answer:
            # If it also invents a fake grade G5 with a score, still check
            if FAKE_GRADE_RE.search(answer) and "G5" in answer and "امتیاز" in answer and len(answer) > 120:
                # If answer says G5 doesn't exist but also gives a score, that's contradictory -> hallucinated
                if "وجود ندارد" in answer:
                    # The correct phrasing already abstains, so amount of invented content is low
                    pass
                else:
                    return 1.0, "abstention phrase but still invents G5 score -> hallucinated"
            return 0.0, "abstention phrase -> not hallucinated (correct abstention)"
        return 0.0, "no-evidence/abstention phrase -> not hallucinated"
    if not contexts or all(not c.strip() for c in contexts):
        # Has answer but no contexts -> likely hallucinated unless greeting/clarify/abstention
        if question.strip() in ("سلام", "سلام علیکم", "سلام خوبی؟"):
            return 0.0, "greeting with no contexts -> not hallucinated"
        if len(answer) < 120 and ("لطفاً مشخص کنید" in answer or "کدام" in answer):
            return 0.0, "clarification with no contexts -> not hallucinated"
        if _is_abstention(answer):
            return 0.0, "abstention with no contexts -> not hallucinated"
        return 1.0, "answer with no contexts -> hallucinated (no grounding)"

    ctx_text = " ".join(contexts)
    ctx_norm = _normalize(ctx_text)
    ans_norm = _normalize(answer)

    # Special: fake grade G5 probe
    is_g5_probe = False
    if expected:
        # bench_runner notes contain G5 hint
        notes = str(expected.get("notes", "")) + str(expected.get("expected_subspace", ""))
        if "G5" in question or "G5" in notes or "g5" in question.lower():
            is_g5_probe = True
    if FAKE_GRADE_RE.search(question) or FAKE_GRADE_RE.search(answer) or is_g5_probe:
        # If question asks about G5 and answer invents a grade/tier not in contexts
        if FAKE_GRADE_RE.search(answer):
            # Check if G5 appears in contexts (it shouldn't)
            if not FAKE_GRADE_RE.search(ctx_text):
                return 1.0, "G5 hallucination: fake grade G5 invented not in contexts"
        # Also catch invented numeric grades for G5 probe
        if is_g5_probe:
            # If answer gives a specific score/tier for the non-existent G5
            m = GRADE_RE.search(answer)
            if m and m.group(0) not in ctx_text and m.group(0) not in ctx_norm:
                # Be stricter: if contexts contain any grade, check if answer's grade not present
                return 1.0, f"G5 probe: grade {m.group(0)!r} invented not in contexts"
            # If answer is definitive about G5 without saying it doesn't exist
            if "G5" in answer and "وجود ندارد" not in answer and "یافت نشد" not in answer:
                # Check if it hallucinated a tier
                if re.search(r"امتیاز|رتبه|نمره", answer):
                    return 1.0, "G5 probe: answered fake grade as if real -> hallucinated"
            # If it correctly refuses or says no such grade, not hallucinated
            if any(kw in ans_norm for kw in ["وجود ندارد", "یافت نشد", "چنین", "نامعتبر"]):
                return 0.0, "G5 probe correctly identified as non-existent"
            # Default for G5: if answer length substantial and not abstaining, treat as hallucinated
            if len(answer) > 100 and "پاسخی یافت نشد" not in answer:
                # Check lexical grounding
                cov = _lexical_coverage(answer, contexts)
                if cov < 0.35:
                    return 1.0, "G5 probe answer not grounded in contexts"
        # Non-G5 but fake grade in answer not in contexts
        for g in GRADE_RE.findall(answer):
            if g.strip() not in ctx_text and g.strip() not in ctx_norm:
                # Only flag if the grade token is somewhat substantive
                if len(g.strip()) >= 2:
                    return 1.0, f"grade {g!r} in answer not in contexts -> hallucinated"

    # Generic: answer claims not covered by contexts
    # Extract numeric / entity claims and check presence
    cov = _lexical_coverage(answer, contexts)
    if cov < 0.25 and len(answer) > 80:
        return 0.8, f"low lexical coverage {cov:.2f} -> likely hallucinated"
    if cov < 0.15 and len(answer) > 40:
        return 0.9, f"very low coverage {cov:.2f} -> hallucinated"
    # If coverage is decent, not hallucinated
    return 0.0, f"coverage {cov:.2f} -> not hallucinated"


def _deterministic_ambiguity(expected: Dict[str, Any], actual_finish: str) -> Tuple[float, str]:
    """1.0 if clarified when should (expected_finish vs actual)."""
    exp = (expected.get("expected_finish") or "").strip().lower()
    actual = (actual_finish or "").strip().lower()
    # Normalize greeting: stop is acceptable for greeting
    if exp == "greeting":
        ok = actual in ("greeting", "stop")
        return (1.0, f"expected greeting, got {actual} -> {'pass' if ok else 'fail'}") if ok else (0.0, f"expected greeting, got {actual} -> fail")
    if exp == "clarify":
        if actual == "clarify":
            return 1.0, "expected clarify, got clarify -> correct"
        return 0.0, f"expected clarify, got {actual} -> should have clarified"
    # exp is stop or other definitive -> should NOT clarify
    if actual == "clarify":
        return 0.0, f"expected {exp}, got clarify -> incorrectly clarified"
    return 1.0, f"expected {exp}, got {actual} -> correct (no spurious clarify)"


def _deterministic_sticky(turn: Dict[str, Any], expected: Dict[str, Any], actual_subspace: Optional[str]) -> Tuple[float, str]:
    """1.0 if kept subspace correctly across turns."""
    should_keep = expected.get("should_keep_sticky")
    exp_sub = expected.get("expected_subspace")
    # Use bench_runner's subspace_match if present (most accurate)
    if "subspace_match" in turn and turn.get("subspace_match") is not None:
        val = turn["subspace_match"]
        return (1.0, "bench subspace_match true") if val else (0.0, f"subspace_match false (exp {exp_sub}, got {actual_subspace})")
    # Fall back to expected vs actual
    if exp_sub is None:
        return 1.0, "no expected subspace -> sticky N/A (pass)"
    if actual_subspace is None:
        # Applied subspace null often means greeting or no retrieval -> fail if expected is definitive
        if should_keep:
            return 0.0, f"should keep {exp_sub} but applied is null -> failed sticky"
        return 0.0, f"expected {exp_sub} but applied is null -> mismatch"
    if actual_subspace == exp_sub:
        return 1.0, f"sticky kept {exp_sub} correctly"
    # Allow partial: e.g. facilities_person vs facilities_legal share prefix but not equal
    return 0.0, f"sticky failed: expected {exp_sub}, got {actual_subspace}"


def _deterministic_retrieval_hit(
    contexts: List[Dict[str, Any]] | List[str],
    expected_subspace: Optional[str],
    expected_filter_path: Optional[str] = None,
) -> Tuple[float, str]:
    """1.0 if expected subspace appears in top-K folder_hierarchy."""
    if expected_subspace is None:
        return 1.0, "no expected subspace -> vacuously hit"
    if not contexts:
        return 0.0, f"no contexts -> miss for {expected_subspace}"
    # Build keyword list for expected subspace
    kws = SUBSPACE_KEYWORDS.get(expected_subspace, [])
    filter_path = expected_filter_path or SUBSPACE_TO_FILTER_PATH.get(expected_subspace, "") or ""
    all_kws = kws + ([filter_path] if filter_path else [])

    def _chunk_text(c: Any) -> str:
        if isinstance(c, dict):
            # folder_hierarchy is list of path segments
            parts: List[str] = []
            fh = c.get("folder_hierarchy") or c.get("folderHierarchy") or []
            if isinstance(fh, list):
                parts.extend(str(x) for x in fh)
            for key in ("content", "content_preview", "title", "heading", "doc_title", "path", "folder_path"):
                v = c.get(key)
                if isinstance(v, str) and v.strip():
                    parts.append(v)
            # also join all string values as fallback
            return " ".join(parts)
        return str(c)

    hits = 0
    for c in contexts:
        text = _chunk_text(c)
        text_norm = _normalize(text)
        for kw in all_kws:
            kw_norm = _normalize(kw)
            if kw_norm and kw_norm in text_norm:
                hits += 1
                break
            # Also try single token from subspace filter_path
            if expected_subspace == "cheque" and "چک" in text_norm:
                hits += 1
                break
            if expected_subspace == "facilities_person" and "حقیقی" in text_norm:
                hits += 1
                break
            if expected_subspace == "facilities_legal" and "حقوقی" in text_norm:
                hits += 1
                break

    if hits > 0:
        return 1.0, f"hit: {hits}/{len(contexts)} chunks contain {expected_subspace} keywords"
    return 0.0, f"miss: no chunk contains {expected_subspace} keywords ({all_kws[:2]})"


# ---------------------------------------------------------------------------
# Core evaluator
# ---------------------------------------------------------------------------

def _extract_context_texts(retrieved_chunks: List[Any]) -> List[str]:
    """Extract content strings from retrieved_chunks (orchestrator audit shape)."""
    out: List[str] = []
    for c in retrieved_chunks or []:
        if isinstance(c, dict):
            for key in ("content", "content_preview", "text", "chunk_text"):
                v = c.get(key)
                if isinstance(v, str) and v.strip():
                    out.append(v[:800])
                    break
            else:
                # Fallback: stringify
                if c:
                    out.append(json.dumps(c, ensure_ascii=False)[:500])
        elif isinstance(c, str):
            out.append(c[:800])
    return out


async def evaluate_turn(
    turn: Dict[str, Any],
    contexts: Optional[List[Any]] = None,
    answer: Optional[str] = None,
    question: Optional[str] = None,
    expected: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluate a single turn. Accepts both the bench_runner turn dict shape and
    explicit args (explicit args override turn fields when provided).

    turn: dict with at least {user, content, expected_finish, expected_subspace,
          finish_reason, applied_subspace, retrieved_chunks, reranker_scores}
    contexts: optional list of chunk dicts or strings (overrides turn.retrieved_chunks)
    answer: optional string (overrides turn.content)
    question: optional string (overrides turn.user / query)
    expected: optional dict with expected_* fields (overrides turn's expected_*)

    Returns dict with scores for all 8 metrics: each is {"score": 0.0-1.0, "reason": str, "source": str}
    plus a flat scores dict for aggregation.
    """
    # Resolve fields with fallbacks
    q = question if question is not None else turn.get("user") or turn.get("query") or turn.get("question") or ""
    ans = answer if answer is not None else turn.get("content") or turn.get("answer") or turn.get("final_answer") or ""
    exp: Dict[str, Any] = {}
    exp.update({k: turn.get(k) for k in ("expected_finish", "expected_subspace", "should_keep_sticky", "notes", "is_respec") if k in turn})
    if expected:
        exp.update(expected)
    # Also carry ground_truth if caller provides it
    if "ground_truth" not in exp and turn.get("ground_truth"):
        exp["ground_truth"] = turn["ground_truth"]
    if expected and "ground_truth" in expected:
        exp["ground_truth"] = expected["ground_truth"]

    retrieved: List[Any] = contexts if contexts is not None else turn.get("retrieved_chunks") or turn.get("final_results") or turn.get("contexts") or []
    # Also support audit.retrieved_chunks shape that is already a list
    ctx_texts = _extract_context_texts(retrieved) if retrieved and isinstance(retrieved[0] if retrieved else None, dict) else [str(c)[:800] for c in (retrieved or [])]
    # But _extract_context_texts handles dict; ensure ctx_texts is texts
    if retrieved and isinstance(retrieved[0], dict):
        ctx_texts = _extract_context_texts(retrieved)
    else:
        ctx_texts = [str(c)[:800] for c in (retrieved or [])]

    rerank_scores: Optional[List[float]] = None
    # Try multiple locations for rerank scores
    for key in ("reranker_scores", "rerank_scores", "top_scores"):
        v = turn.get(key)
        if isinstance(v, list) and v:
            rerank_scores = [float(x) for x in v if isinstance(x, (int, float))]
            break
    # Also infer from retrieved_chunks[].rerank_score
    if rerank_scores is None and retrieved and isinstance(retrieved[0], dict):
        rs = []
        for c in retrieved:
            for kk in ("rerank_score", "hybrid_score", "score"):
                vv = c.get(kk)
                if isinstance(vv, (int, float)):
                    rs.append(float(vv))
                    break
        if rs:
            rerank_scores = rs

    finish_reason = turn.get("finish_reason") or turn.get("finishReason") or turn.get("actual_finish") or ""
    applied_subspace = turn.get("applied_subspace")

    # ---- Compute heuristic fallbacks first (used if LLM fails) ----
    hf_faith_score, hf_faith_reason = _heuristic_faithfulness(ans, ctx_texts)
    hf_ans_rel_score, hf_ans_rel_reason = _heuristic_answer_relevancy(q, ans)
    hf_ctx_rel_score, hf_ctx_rel_reason = _heuristic_context_relevancy(q, ctx_texts, rerank_scores)
    # ground_truth for context_recall
    gt = exp.get("ground_truth") or exp.get("expected_answer") or turn.get("ground_truth")
    hf_ctx_rec_score, hf_ctx_rec_reason = _heuristic_context_recall(q, ctx_texts, gt, ans)

    # ---- LLM judge for 4 RAGAS metrics (with fallback) ----
    # faithfulness
    faith_score, faith_reason, faith_source = await _llm_score(
        _prompt_faithfulness(q, ctx_texts, ans), hf_faith_score, hf_faith_reason
    )
    # answer_relevancy
    ans_rel_score, ans_rel_reason, ans_rel_source = await _llm_score(
        _prompt_answer_relevancy(q, ans), hf_ans_rel_score, hf_ans_rel_reason
    )
    # context_relevancy
    ctx_rel_score, ctx_rel_reason, ctx_rel_source = await _llm_score(
        _prompt_context_relevancy(q, ctx_texts), hf_ctx_rel_score, hf_ctx_rel_reason
    )
    # context_recall (only use LLM when GT exists; else heuristic is more honest)
    if gt:
        ctx_rec_score, ctx_rec_reason, ctx_rec_source = await _llm_score(
            _prompt_context_recall(str(gt), ctx_texts), hf_ctx_rec_score, hf_ctx_rec_reason
        )
    else:
        ctx_rec_score, ctx_rec_reason, ctx_rec_source = hf_ctx_rec_score, hf_ctx_rec_reason, "heuristic"

    # ---- Deterministic metrics (no LLM) ----
    hall_score, hall_reason = _deterministic_hallucination(ans, ctx_texts, q, exp)
    # Invert hallucination for aggregation: keep as 1=hallucinated per spec,
    # but also provide non_hallucination = 1 - hallucination for "higher is better" views
    amb_score, amb_reason = _deterministic_ambiguity(exp, finish_reason)
    sticky_score, sticky_reason = _deterministic_sticky(turn, exp, applied_subspace)
    exp_filter = exp.get("filter_path") or turn.get("filter_path") or SUBSPACE_TO_FILTER_PATH.get(str(exp.get("expected_subspace") or ""), None)
    # retrieved for retrieval_hit should be original dicts if available
    ret_hit_score, ret_hit_reason = _deterministic_retrieval_hit(
        retrieved if retrieved and isinstance(retrieved[0], dict) else [{"content": t} for t in ctx_texts],
        exp.get("expected_subspace"),
        exp_filter,
    )

    # Package per-metric with reasoning + source
    metrics: Dict[str, Dict[str, Any]] = {
        "faithfulness": {"score": round(float(faith_score), 4), "reason": faith_reason, "source": faith_source},
        "answer_relevancy": {"score": round(float(ans_rel_score), 4), "reason": ans_rel_reason, "source": ans_rel_source},
        "context_relevancy": {"score": round(float(ctx_rel_score), 4), "reason": ctx_rel_reason, "source": ctx_rel_source},
        "context_recall": {"score": round(float(ctx_rec_score), 4), "reason": ctx_rec_reason, "source": ctx_rec_source},
        "hallucination": {"score": round(float(hall_score), 4), "reason": hall_reason, "source": "heuristic"},
        "ambiguity_resolution": {"score": round(float(amb_score), 4), "reason": amb_reason, "source": "heuristic"},
        "sticky_persistence": {"score": round(float(sticky_score), 4), "reason": sticky_reason, "source": "heuristic"},
        "retrieval_hit": {"score": round(float(ret_hit_score), 4), "reason": ret_hit_reason, "source": "heuristic"},
    }
    # Also provide derived non_hallucination for dashboards that expect higher=better
    metrics["non_hallucination"] = {
        "score": round(1.0 - float(hall_score), 4),
        "reason": f"1 - hallucination ({hall_reason})",
        "source": "heuristic",
    }

    # Flat scores for aggregation convenience
    flat_scores = {k: v["score"] for k, v in metrics.items()}

    return {
        "question": q[:300],
        "answer_preview": ans[:300],
        "expected": exp,
        "finish_reason": finish_reason,
        "applied_subspace": applied_subspace,
        "contexts_count": len(ctx_texts),
        "metrics": metrics,
        "scores": flat_scores,
    }


def _percentiles(values: List[float]) -> Dict[str, Optional[float]]:
    """Compute p50/p95/avg/min/max from a list of numbers."""
    if not values:
        return {"p50": None, "p95": None, "avg": None, "min": None, "max": None, "count": 0}
    vals = sorted(float(v) for v in values)
    n = len(vals)
    p50 = vals[n // 2]
    p95_idx = int(n * 0.95)
    if p95_idx >= n:
        p95_idx = n - 1
    p95 = vals[p95_idx]
    return {
        "p50": round(p50, 2),
        "p95": round(p95, 2),
        "avg": round(sum(vals) / n, 2),
        "min": round(min(vals), 2),
        "max": round(max(vals), 2),
        "count": n,
    }


def _mean_by_metric(per_turn: List[Dict[str, Any]], metric: str) -> Optional[float]:
    vals = [t["scores"][metric] for t in per_turn if metric in t.get("scores", {}) and t["scores"][metric] is not None]
    vals = [float(v) for v in vals if isinstance(v, (int, float))]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 4)


def _flatten_bench(bench: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Flatten bench_results.json (conversations + single_baselines) into a list of
    turn dicts normalized for evaluate_turn.

    Each flattened entry has keys: conv_id, turn_index, turn (original dict), subspace
    """
    flat: List[Dict[str, Any]] = []
    for conv in bench.get("conversations", []) or []:
        conv_id = conv.get("id", "unknown_conv")
        subspace = conv.get("subspace")
        for t in conv.get("turns", []) or []:
            # Attach conv-level subspace as fallback for expected
            if "expected_subspace" not in t or t.get("expected_subspace") is None:
                # Keep None as-is for greeting/clarify, but remember conv subspace
                pass
            t_copy = dict(t)
            # Ensure conv_id and conv_subspace are traceable
            t_copy["_conv_id"] = conv_id
            t_copy["_conv_subspace"] = subspace
            flat.append({"conv_id": conv_id, "turn_index": t.get("turn_index", len(flat) + 1), "turn": t_copy})
    for s in bench.get("single_baselines", []) or []:
        # Singles are one turn each
        t = dict(s)
        # Normalize: bench singles use 'query' not 'user', and 'content' is the assistant answer
        # But evaluate_turn expects user/content; singles may not yet have content if bench didn't store it
        # Map: user = query, content = content/answer, finish_reason etc.
        if "user" not in t and "query" in t:
            t["user"] = t["query"]
        # Preserve single id as conv_id
        sid = t.get("id", "single")
        flat.append({"conv_id": sid, "turn_index": 1, "turn": t})
    return flat


async def evaluate_bench_results_async(
    results_path: str | Path,
    max_concurrency: int = 4,
    no_llm: bool = False,
) -> Dict[str, Any]:
    """
    Async core: read bench_results.json, evaluate each turn, aggregate.

    Returns aggregates dict:
      {
        overall: {metric: mean, latency: percentiles, error_rate},
        by_subspace: {cheque: {metric: mean, count}, ...},
        per_turn: [ {conv_id, turn_index, scores, latency_ms, ...}, ... ]
      }
    """
    # Allow disabling LLM for deterministic/fast evaluation
    global _discovered_endpoint
    if no_llm:
        _discovered_endpoint = "__disabled__"

    p = Path(results_path)
    if not p.exists():
        raise FileNotFoundError(f"bench results not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        bench = json.load(f)

    flat = _flatten_bench(bench)
    if not flat:
        return {"overall": {}, "by_subspace": {}, "per_turn": [], "meta": {"input": str(p), "turns": 0}}

    # Collect latencies and errors from raw turns
    all_latencies: List[float] = []
    error_count = 0
    for entry in flat:
        t = entry["turn"]
        for lk in ("latency_ms_wall", "latency_ms", "latency"):
            v = t.get(lk)
            if isinstance(v, (int, float)):
                all_latencies.append(float(v))
                break
        if t.get("error") or (isinstance(t.get("http_status"), int) and t["http_status"] >= 400):
            error_count += 1

    # Evaluate turns with limited concurrency (LLM calls)
    sem = asyncio.Semaphore(max_concurrency)

    async def _eval_one(entry: Dict[str, Any]) -> Dict[str, Any]:
        async with sem:
            turn = entry["turn"]
            try:
                res = await evaluate_turn(turn)
            except Exception as exc:
                res = {"scores": {}, "metrics": {}, "error": str(exc)}
            # Attach identity + raw fields for reporting
            out: Dict[str, Any] = {
                "conv_id": entry["conv_id"],
                "turn_index": entry["turn_index"],
                "user": (turn.get("user") or turn.get("query") or "")[:200],
                "expected_finish": turn.get("expected_finish"),
                "expected_subspace": turn.get("expected_subspace"),
                "finish_reason": turn.get("finish_reason"),
                "applied_subspace": turn.get("applied_subspace"),
                "latency_ms": turn.get("latency_ms_wall") or turn.get("latency_ms"),
                "http_status": turn.get("http_status"),
                "error": turn.get("error"),
                "retrieved_chunks_count": turn.get("retrieved_chunks_count") or len(turn.get("retrieved_chunks") or []),
                "citations_count": turn.get("citations_count", 0),
                "scores": res.get("scores", {}),
                "metrics": res.get("metrics", {}),
            }
            if res.get("error"):
                out["eval_error"] = res["error"]
            return out

    per_turn: List[Dict[str, Any]] = await asyncio.gather(*[_eval_one(e) for e in flat])

    # Overall aggregates: mean per metric
    metric_keys = ["faithfulness", "answer_relevancy", "context_relevancy", "context_recall", "hallucination", "non_hallucination", "ambiguity_resolution", "sticky_persistence", "retrieval_hit"]
    overall: Dict[str, Any] = {}
    for k in metric_keys:
        overall[k] = _mean_by_metric(per_turn, k)
    overall["latency_ms"] = _percentiles(all_latencies)
    overall["error_rate"] = round(error_count / len(flat), 4) if flat else 0.0
    overall["error_count"] = error_count
    overall["total_turns"] = len(flat)

    # By-subspace aggregates
    # Group by expected_subspace or conv subspace
    by_subspace: Dict[str, Any] = {}
    # Collect unique subspace labels from expected + conv
    labels: set = set()
    for pt in per_turn:
        lab = pt.get("expected_subspace") or pt.get("applied_subspace") or "unknown"
        if lab is None:
            lab = "none"  # greeting / no-subspace
        labels.add(str(lab))
    # Also ensure canonical subspaces appear even if no turns
    for canonical in ["cheque", "facilities_person", "facilities_legal", "general", "greeting", "mixed", "none", "unknown"]:
        if any(str(v).lower() == canonical for v in labels):
            continue
        # Not needed to add empty unless at least one turn maps there
        pass

    for lab in sorted(labels):
        group = [pt for pt in per_turn if str(pt.get("expected_subspace") or pt.get("applied_subspace") or "unknown") == lab or (lab == "none" and pt.get("expected_subspace") is None)]
        # The above grouping is imprecise for "none" - refine: use expected_subspace
        # Better: group strictly by expected_subspace string or "none"
        group2 = [pt for pt in per_turn if (str(pt.get("expected_subspace")) if pt.get("expected_subspace") is not None else "none") == lab]
        if not group2:
            continue
        agg: Dict[str, Any] = {"count": len(group2)}
        for k in metric_keys:
            agg[k] = _mean_by_metric(group2, k)
        # Latency for this subspace
        lat2 = [float(pt["latency_ms"]) for pt in group2 if isinstance(pt.get("latency_ms"), (int, float))]
        agg["latency_ms"] = _percentiles(lat2)
        agg["error_rate"] = round(sum(1 for pt in group2 if pt.get("error")) / len(group2), 4) if group2 else 0.0
        by_subspace[lab] = agg

    # Also provide stage_timing aggregates if available
    stage_keys = ["validate_input", "retrieve", "build_context", "guarded_generate", "format_response"]
    stage_vals: Dict[str, List[float]] = {k: [] for k in stage_keys}
    for entry in flat:
        st = entry["turn"].get("stage_timing_ms") or {}
        for k in stage_keys:
            v = st.get(k)
            if isinstance(v, (int, float)):
                stage_vals[k].append(float(v))
    overall["stage_timing_ms"] = {k: _percentiles(v) for k, v in stage_vals.items() if v}

    meta = {
        "input": str(p),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_judge": _discovered_model or "heuristic",
        "endpoint_judge": _discovered_endpoint or "heuristic",
        "total_turns": len(flat),
        "bench_meta": bench.get("meta", {}),
        "bench_summary": bench.get("summary", {}),
    }

    return {
        "meta": meta,
        "overall": overall,
        "by_subspace": by_subspace,
        "per_turn": per_turn,
    }


def evaluate_bench_results(
    results_path: str | Path,
    max_concurrency: int = 4,
    no_llm: bool = False,
) -> Dict[str, Any]:
    """
    Synchronous wrapper for evaluate_bench_results_async.
    Handles both direct path and list-of-turns input.

    If results_path is a list of turn dicts, evaluates that list directly
    (useful for programmatic batch without a file).
    """
    # Handle list input (batch of turn dicts)
    if isinstance(results_path, list):
        flat = [{"conv_id": t.get("_conv_id") or t.get("id") or f"turn_{i}", "turn_index": t.get("turn_index", i + 1), "turn": t} for i, t in enumerate(results_path)]

        async def _eval_list():
            global _discovered_endpoint
            if no_llm:
                _discovered_endpoint = "__disabled__"
            sem = asyncio.Semaphore(max_concurrency)

            async def _one(entry):
                async with sem:
                    try:
                        res = await evaluate_turn(entry["turn"])
                    except Exception as exc:
                        res = {"scores": {}, "metrics": {}, "error": str(exc)}
                    return {
                        "conv_id": entry["conv_id"],
                        "turn_index": entry["turn_index"],
                        "user": (entry["turn"].get("user") or entry["turn"].get("query") or "")[:200],
                        "expected_finish": entry["turn"].get("expected_finish"),
                        "expected_subspace": entry["turn"].get("expected_subspace"),
                        "finish_reason": entry["turn"].get("finish_reason"),
                        "applied_subspace": entry["turn"].get("applied_subspace"),
                        "latency_ms": entry["turn"].get("latency_ms_wall") or entry["turn"].get("latency_ms"),
                        "scores": res.get("scores", {}),
                        "metrics": res.get("metrics", {}),
                    }

            per_turn = await asyncio.gather(*[_one(e) for e in flat])
            metric_keys = ["faithfulness", "answer_relevancy", "context_relevancy", "context_recall", "hallucination", "non_hallucination", "ambiguity_resolution", "sticky_persistence", "retrieval_hit"]
            overall = {k: _mean_by_metric(per_turn, k) for k in metric_keys}
            overall["total_turns"] = len(flat)
            return {"meta": {"input": "list", "total_turns": len(flat)}, "overall": overall, "by_subspace": {}, "per_turn": per_turn}

        return asyncio.run(_eval_list())

    return asyncio.run(evaluate_bench_results_async(results_path, max_concurrency=max_concurrency, no_llm=no_llm))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="RAGAS + custom evaluators for Work Credit RAG benchmark")
    p.add_argument("--input", "-i", type=str, default="evaluation/artifacts/bench_results_latest.json", help="Path to bench_results JSON (or bench_results_latest.json)")
    p.add_argument("--output", "-o", type=str, default=None, help="Path to write ragas_results JSON (default: alongside input with ragas_ prefix and artifacts/ragas_results_latest.json)")
    p.add_argument("--no-llm", action="store_true", help="Disable LLM judge, use heuristics only (fast, deterministic)")
    p.add_argument("--model", type=str, default=None, help="Override judge model (default: auto-discover gemma-4-31b)")
    p.add_argument("--timeout", type=float, default=None, help="Override judge timeout seconds")
    p.add_argument("--concurrency", type=int, default=4, help="Max concurrent LLM judge calls")
    p.add_argument("--verbose", action="store_true", help="Print per-turn scores")
    p.add_argument("--mock-test", action="store_true", help="Run a dry test on a mock turn without needing bench file")
    return p


def _resolve_output_path(input_path: Path, output_arg: Optional[str]) -> List[Path]:
    """Resolve output paths: explicit or auto (same dir + latest + mirrors)."""
    if output_arg:
        return [Path(output_arg)]
    # Auto: <input_dir>/ragas_results_<timestamp>.json + ragas_results_latest.json
    # Also mirror to other evaluation artifact dirs if input is one of the known locations
    import datetime as _dt
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"ragas_results_{ts}.json"
    candidates: List[Path] = []
    # Primary: alongside input
    d = input_path.parent
    d.mkdir(parents=True, exist_ok=True)
    candidates.append(d / stem)
    # Mirror dirs (same logic as bench_runner _resolve_artifact_dirs)
    try:
        here = Path(__file__).resolve().parent
        repo_root = Path(__file__).resolve().parents[3] if "orchestrator" in str(Path(__file__).resolve()) else Path(__file__).resolve().parents[1]
        mirror_dirs = [
            here / "artifacts",
            repo_root / "evaluation" / "artifacts",
            repo_root / "components" / "evaluation" / "artifacts",
            repo_root / "components" / "orchestrator" / "evaluation" / "artifacts",
        ]
        for md in mirror_dirs:
            if md.resolve() != d.resolve():
                try:
                    md.mkdir(parents=True, exist_ok=True)
                    # Only add if this dir already has bench artifacts (avoid creating stray dirs)
                    if any(md.glob("bench_results_*.json")) or md == here / "artifacts":
                        candidates.append(md / stem)
                except Exception:
                    pass
    except Exception:
        pass
    # Deduplicate
    seen: set = set()
    uniq: List[Path] = []
    for c in candidates:
        s = str(c.resolve())
        if s not in seen:
            seen.add(s)
            uniq.append(c)
    return uniq


def _run_mock_test(no_llm: bool = False) -> Dict[str, Any]:
    """Run evaluator on a mock turn (no services required) to verify heuristics/LLM path."""
    mock_turn = {
        "user": "چک برگشتی چیست و چگونه رفع سوء اثر می‌شود؟",
        "content": "چک برگشتی چکی است که به دلیل عدم موجودی کافی برگشت می‌خورد. برای رفع سوء اثر باید مبلغ کسری را به حساب واریز کنید و از بانک گواهی رفع سوء اثر بگیرید.",
        "expected_finish": "stop",
        "expected_subspace": "cheque",
        "should_keep_sticky": False,
        "finish_reason": "stop",
        "applied_subspace": "cheque",
        "retrieved_chunks": [
            {"content": "چک برگشتی به چکی گفته می‌شود که به علت کسر موجودی یا مسدودی حساب برگشت داده می‌شود.", "rerank_score": 0.78, "folder_hierarchy": ["گزارش اعتباری چک", "چک برگشتی"]},
            {"content": "برای رفع سوء اثر چک برگشتی باید مبلغ چک را به حساب خود واریز نموده و از بانک تقاضای رفع سوء اثر کنید.", "rerank_score": 0.65, "folder_hierarchy": ["گزارش اعتباری چک", "رفع سوء اثر"]},
        ],
        "reranker_scores": [0.78, 0.65],
        "notes": "first granular cheque query",
    }
    mock_turn_g5 = {
        "user": "نمره اعتباری من G5 است چه امتیازی میگیرم",
        "content": "بر اساس اطلاعات موجود در پایگاه دانش، درجه G5 وجود ندارد. رتبه‌های اعتباری شامل A، B، C و D است.",
        "expected_finish": "stop",
        "expected_subspace": None,
        "should_keep_sticky": False,
        "finish_reason": "stop",
        "applied_subspace": None,
        "retrieved_chunks": [],
        "notes": "non-existent grade G5 — expect no hallucinated grade",
    }
    mock_turn_g5_hallu = {
        "user": "نمره اعتباری من G5 است چه امتیازی میگیرم",
        "content": "نمره G5 شما معادل امتیاز 850 و رتبه عالی است و می‌توانید 500 میلیون وام بگیرید.",
        "expected_finish": "stop",
        "expected_subspace": None,
        "should_keep_sticky": False,
        "finish_reason": "stop",
        "applied_subspace": None,
        "retrieved_chunks": [
            {"content": "رتبه‌های اعتباری شامل A، B، C است و هرکدام امتیاز متفاوتی دارد.", "rerank_score": 0.3, "folder_hierarchy": ["پایگاه دانش عمومی"]},
        ],
        "notes": "non-existent grade G5 — hallucinated",
    }

    async def _run():
        r1 = await evaluate_turn(mock_turn)
        r2 = await evaluate_turn(mock_turn_g5)
        r3 = await evaluate_turn(mock_turn_g5_hallu)
        return {"faithful_cheque": r1, "g5_correct": r2, "g5_hallucinated": r3}

    if no_llm:
        global _discovered_endpoint
        _discovered_endpoint = "__disabled__"
    result = asyncio.run(_run())
    print("\n=== MOCK TEST (dry, no services required) ===")
    for name, res in result.items():
        print(f"\n[{name}] Q: {res['question'][:60]!r}")
        for k, v in res["metrics"].items():
            src = v.get("source", "?")
            print(f"  {k:22s} {v['score']:.2f} ({src})  {v['reason'][:90]}")
    return result


def main() -> None:
    parser = _build_cli()
    args = parser.parse_args()

    global _discovered_endpoint, _discovered_model, JUDGE_TIMEOUT_S
    if args.model:
        JUDGE_MODELS.insert(0, args.model)
        _discovered_model = args.model
    if args.timeout:
        JUDGE_TIMEOUT_S = float(args.timeout)
    if args.no_llm:
        _discovered_endpoint = "__disabled__"

    if args.mock_test:
        _run_mock_test(no_llm=args.no_llm)
        return

    input_path = Path(args.input)
    # Resolve relative to repo root if not found alongside CWD
    if not input_path.exists():
        # Try alternative locations
        here = Path(__file__).resolve().parent
        repo_root = Path(__file__).resolve().parents[3] if "orchestrator" in str(here) else Path.cwd()
        candidates = [
            repo_root / args.input,
            here / "artifacts" / Path(args.input).name,
            repo_root / "evaluation" / "artifacts" / Path(args.input).name,
            repo_root / "components" / "orchestrator" / "evaluation" / "artifacts" / Path(args.input).name,
            repo_root / "components" / "evaluation" / "artifacts" / Path(args.input).name,
        ]
        for c in candidates:
            if c.exists():
                input_path = c
                break

    if not input_path.exists():
        print(f"[ERROR] input not found: {args.input} (resolved: {input_path})")
        print("  Hint: run with --mock-test for a dry test, or provide --input <path>")
        raise SystemExit(1)

    print(f"=== RAGAS eval ===")
    print(f"  input:    {input_path}")
    print(f"  judge:    {JUDGE_ENDPOINTS[0]} (fallback {JUDGE_ENDPOINTS[1:]}) model={_discovered_model or JUDGE_MODELS[0]} timeout={JUDGE_TIMEOUT_S}s no_llm={args.no_llm}")

    result = asyncio.run(evaluate_bench_results_async(input_path, max_concurrency=args.concurrency, no_llm=args.no_llm))

    # Print summary
    overall = result.get("overall", {})
    print("\n=== OVERALL (mean 0-1, higher is better except hallucination) ===")
    for k in ["faithfulness", "answer_relevancy", "context_relevancy", "context_recall", "hallucination", "non_hallucination", "ambiguity_resolution", "sticky_persistence", "retrieval_hit"]:
        v = overall.get(k)
        if v is not None:
            print(f"  {k:22s} {v:.3f}")
    lat = overall.get("latency_ms", {})
    if lat:
        print(f"  latency p50={lat.get('p50')}ms p95={lat.get('p95')}ms avg={lat.get('avg')}ms count={lat.get('count')}")
    print(f"  error_rate={overall.get('error_rate')} ({overall.get('error_count')}/{overall.get('total_turns')})")

    if result.get("by_subspace"):
        print("\n=== BY SUBSPACE ===")
        for sub, agg in result["by_subspace"].items():
            print(f"  {sub:20s} count={agg['count']}  faith={agg.get('faithfulness')} rel={agg.get('answer_relevancy')} ctx_rel={agg.get('context_relevancy')} hit={agg.get('retrieval_hit')} hall={agg.get('hallucination')}")

    if args.verbose:
        print("\n=== PER-TURN ===")
        for pt in result.get("per_turn", []):
            print(f"  {pt['conv_id']} T{pt['turn_index']} exp={pt['expected_finish']}/{pt['expected_subspace']} actual={pt['finish_reason']}/{pt['applied_subspace']} lat={pt.get('latency_ms')} scores={pt['scores']}")

    # Write outputs
    out_paths = _resolve_output_path(input_path, args.output)
    # Also add latest.json mirrors
    latest_paths: List[Path] = []
    for p in out_paths:
        latest_paths.append(p.parent / "ragas_results_latest.json")

    all_written: List[Path] = []
    for p in out_paths + latest_paths:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            all_written.append(p)
        except Exception as exc:
            print(f"[WARN] failed to write {p}: {exc}")

    # Deduplicate print
    seen = set()
    for p in all_written:
        s = str(p.resolve())
        if s not in seen:
            seen.add(s)
            try:
                sz = p.stat().st_size
                print(f"[ARTIFACT] wrote {p} ({sz} bytes)")
            except Exception:
                print(f"[ARTIFACT] wrote {p}")


if __name__ == "__main__":
    main()
