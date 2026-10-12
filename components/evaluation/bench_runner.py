#!/usr/bin/env python3
"""
Benchmark conversation executor for Work Credit RAG.

Covers:
- 12 multi-turn conversations (4 subspaces x 3 + mixed/greeting/hallucination/supplement)
- 12 single-turn baselines (granular + edge variants)
- Total ~50 turns when combined
- Sticky subspace via X-Request-ID header + sequential messages array
- Direct KB retrieval probe (with vs without filter_path)
- Artifact saving to evaluation/artifacts/bench_results_<timestamp>.json

Usage:
    python -m evaluation.bench_runner --dry-run          # single turn smoke
    python -m evaluation.bench_runner                     # full run
    python -m evaluation.bench_runner --only conv_cheque_01
    python -m evaluation.bench_runner --skip-kb-probe

Endpoints (verified):
    POST http://127.0.0.1:8000/search/api
    POST http://127.0.0.1:8100/v1/chat/completions
    GET  http://127.0.0.1:3000/api/observability/pipeline/{request_id}
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants — endpoints (verified per spec)
# ---------------------------------------------------------------------------

ORCH_URL = "http://127.0.0.1:8100/v1/chat/completions"
KB_URL = "http://127.0.0.1:8000/search/api"
OBS_URL_TEMPLATE = "http://127.0.0.1:3000/api/observability/pipeline/{request_id}"

# Default model exposed by orchestrator (api.py:104 allows ics-helper-agent alias)
DEFAULT_MODEL = "ics-helper-agent"

# HTTP timeout in seconds — orchestrator does retrieval + Gemma generation
HTTP_TIMEOUT_S = 120.0

# Subspace -> KB filter_path mapping (matches config.py subspace_map)
SUBSPACE_TO_FILTER_PATH: Dict[str, Optional[str]] = {
    "cheque": "گزارش اعتباری چک",
    "facilities_person": "اشخاص حقیقی/اعتبارسنجی تسهیلات",
    "facilities_legal": "اشخاص حقوقی/اعتبارسنجی تسهیلات",
    "general": "پایگاه دانش عمومی",
    "greeting": None,  # no retrieval expected
    "mixed": None,
}

# ---------------------------------------------------------------------------
# Conversation definitions
# ---------------------------------------------------------------------------
# Each conversation is a dict with:
#   id, subspace (primary expected), turns: list of dicts
# Turns: user, expected_finish (stop|clarify|greeting), expected_subspace,
#        should_keep_sticky (bool), is_respec (bool), notes, filter_path
#
# Spec requires 12 multi-turn + 12 single-turn baselines (~50 turns)


CONVERSATIONS: List[Dict[str, Any]] = [
    # ---- cheque subspace (2 convs) ----
    {
        "id": "conv_cheque_01",
        "subspace": "cheque",
        "description": "greeting -> cheque granular -> cheque sticky follow-up",
        "turns": [
            {
                "user": "سلام",
                "expected_finish": "greeting",
                "expected_subspace": None,
                "should_keep_sticky": False,
                "is_respec": False,
                "notes": "greeting/no-retrieve shortcut",
            },
            {
                "user": "چک برگشتی چیست و چگونه رفع سوء اثر می‌شود؟",
                "expected_finish": "stop",
                "expected_subspace": "cheque",
                "should_keep_sticky": False,
                "is_respec": False,
                "notes": "first granular cheque query, sets sticky to cheque",
            },
            {
                "user": "اگر چکم بدون موجودی باشد چه کار کنم؟",
                "expected_finish": "stop",
                "expected_subspace": "cheque",
                "should_keep_sticky": True,
                "is_respec": False,
                "notes": "anaphoric follow-up — should stay cheque via sticky",
            },
        ],
    },
    {
        "id": "conv_cheque_02",
        "subspace": "cheque",
        "description": "scattered clarify -> cheque spec -> cheque sticky granular",
        "turns": [
            {
                "user": "وضعیت اعتباری چطور است",
                "expected_finish": "clarify",
                "expected_subspace": None,
                "should_keep_sticky": False,
                "is_respec": False,
                "notes": "scattered/ambiguous — expect clarify with options",
            },
            {
                "user": "چک",
                "expected_finish": "stop",
                "expected_subspace": "cheque",
                "should_keep_sticky": False,
                "is_respec": True,
                "notes": "short re-spec to cheque",
            },
            {
                "user": "تاثیر چک برگشتی بر امتیاز اعتباری چقدر است؟",
                "expected_finish": "stop",
                "expected_subspace": "cheque",
                "should_keep_sticky": True,
                "is_respec": False,
                "notes": "granular cheque — should keep sticky cheque",
            },
        ],
    },
    # ---- facilities_person (2 convs) ----
    {
        "id": "conv_facilities_person_01",
        "subspace": "facilities_person",
        "description": "clarify -> facilities_person -> sticky -> cheque re-spec",
        "turns": [
            {
                "user": "وضعیت اعتباری چطور است",
                "expected_finish": "clarify",
                "expected_subspace": None,
                "should_keep_sticky": False,
                "is_respec": False,
                "notes": "same scattered probe as cheque_02 T1",
            },
            {
                "user": "تسهیلات اشخاص حقیقی",
                "expected_finish": "stop",
                "expected_subspace": "facilities_person",
                "should_keep_sticky": False,
                "is_respec": True,
                "notes": "re-spec to facilities_person",
            },
            {
                "user": "آیا میزان درآمد یا گردش حساب من هم در بهبود رتبه اعتباری تاثیر دارد؟",
                "expected_finish": "stop",
                "expected_subspace": "facilities_person",
                "should_keep_sticky": True,
                "is_respec": False,
                "notes": "follow-up should stay facilities_person via sticky",
            },
            {
                "user": "چک",
                "expected_finish": "stop",
                "expected_subspace": "cheque",
                "should_keep_sticky": False,
                "is_respec": True,
                "notes": "explicit re-spec to cheque — sticky should switch",
            },
        ],
    },
    {
        "id": "conv_facilities_person_02",
        "subspace": "facilities_person",
        "description": "greeting -> scattered -> facilities_person granular",
        "turns": [
            {
                "user": "سلام خوبی؟",
                "expected_finish": "greeting",
                "expected_subspace": None,
                "should_keep_sticky": False,
                "is_respec": False,
                "notes": "informal greeting",
            },
            {
                "user": "بدهکار شدم چیکار کنم",
                "expected_finish": "clarify",
                "expected_subspace": None,
                "should_keep_sticky": False,
                "is_respec": False,
                "notes": "scattered informal — expect clarify",
            },
            {
                "user": "اعتبارسنجی تسهیلات برای اشخاص حقیقی",
                "expected_finish": "stop",
                "expected_subspace": "facilities_person",
                "should_keep_sticky": False,
                "is_respec": True,
                "notes": "explicit facilities_person granular",
            },
        ],
    },
    # ---- facilities_legal (2 convs) ----
    {
        "id": "conv_facilities_legal_01",
        "subspace": "facilities_legal",
        "description": "facilities_legal granular -> board-role re-spec to general",
        "turns": [
            {
                "user": "محدودیت‌های تسهیلات برای اشخاص حقوقی چیست؟",
                "expected_finish": "stop",
                "expected_subspace": "facilities_legal",
                "should_keep_sticky": False,
                "is_respec": False,
                "notes": "direct facilities_legal granular",
            },
            {
                "user": "هیات مدیره چه نقشی دارد؟",
                "expected_finish": "stop",
                "expected_subspace": "general",
                "should_keep_sticky": False,
                "is_respec": True,
                "notes": "board-member query — general subspace, tests re-spec away from facilities_legal",
            },
        ],
    },
    {
        "id": "conv_facilities_legal_02",
        "subspace": "facilities_legal",
        "description": "greeting -> facilities_legal short spec",
        "turns": [
            {
                "user": "سلام",
                "expected_finish": "greeting",
                "expected_subspace": None,
                "should_keep_sticky": False,
                "is_respec": False,
                "notes": "greeting",
            },
            {
                "user": "تسهیلات اشخاص حقوقی",
                "expected_finish": "stop",
                "expected_subspace": "facilities_legal",
                "should_keep_sticky": False,
                "is_respec": True,
                "notes": "short facilities_legal spec",
            },
        ],
    },
    # ---- general (2 convs) ----
    {
        "id": "conv_general_01",
        "subspace": "general",
        "description": "general entity -> general intro -> cheque re-spec",
        "turns": [
            {
                "user": "قاسم بور کیه",
                "expected_finish": "stop",
                "expected_subspace": "general",
                "should_keep_sticky": False,
                "is_respec": False,
                "notes": "named entity in general subspace — no clarify expected",
            },
            {
                "user": "معرفی شرکت اعتبارسنجی ایران",
                "expected_finish": "stop",
                "expected_subspace": "general",
                "should_keep_sticky": True,
                "is_respec": False,
                "notes": "general intro — should keep general sticky",
            },
            {
                "user": "چک برگشتی چیست",
                "expected_finish": "stop",
                "expected_subspace": "cheque",
                "should_keep_sticky": False,
                "is_respec": True,
                "notes": "explicit re-spec to cheque",
            },
        ],
    },
    {
        "id": "conv_general_02",
        "subspace": "general",
        "description": "clarify -> general rejection with manager query",
        "turns": [
            {
                "user": "وضعیت اعتباری چطور است",
                "expected_finish": "clarify",
                "expected_subspace": None,
                "should_keep_sticky": False,
                "is_respec": False,
                "notes": "scattered clarify",
            },
            {
                "user": "هیچکدوم موارد بالا نیست، مدیر عامل شرکت کیه؟",
                "expected_finish": "stop",
                "expected_subspace": "general",
                "should_keep_sticky": False,
                "is_respec": True,
                "notes": "reject clarify options, ask general board/manager",
            },
        ],
    },
    # ---- mixed / greeting / hallucination / supplement (4 convs) ----
    {
        "id": "conv_mixed_01",
        "subspace": "mixed",
        "description": "cheque -> facilities_person re-spec",
        "turns": [
            {
                "user": "چک",
                "expected_finish": "stop",
                "expected_subspace": "cheque",
                "should_keep_sticky": False,
                "is_respec": False,
                "notes": "single-token cheque spec",
            },
            {
                "user": "حالا درباره تسهیلات اشخاص حقیقی بگو",
                "expected_finish": "stop",
                "expected_subspace": "facilities_person",
                "should_keep_sticky": False,
                "is_respec": True,
                "notes": "explicit re-spec to facilities_person",
            },
        ],
    },
    {
        "id": "conv_greeting_01",
        "subspace": "greeting",
        "description": "greeting x2 -> scattered clarify",
        "turns": [
            {
                "user": "سلام",
                "expected_finish": "greeting",
                "expected_subspace": None,
                "should_keep_sticky": False,
                "is_respec": False,
                "notes": "greeting 1",
            },
            {
                "user": "سلام علیکم",
                "expected_finish": "greeting",
                "expected_subspace": None,
                "should_keep_sticky": False,
                "is_respec": False,
                "notes": "greeting 2 — still no retrieval",
            },
            {
                "user": "اعتبارسنجی چیست",
                "expected_finish": "clarify",
                "expected_subspace": None,
                "should_keep_sticky": False,
                "is_respec": False,
                "notes": "overly broad — expect clarify not direct answer",
            },
        ],
    },
    {
        "id": "conv_hallucination_01",
        "subspace": "general",
        "description": "hallucination guard: fake G5 grade must not be hallucinated",
        "turns": [
            {
                "user": "نمره اعتباری من G5 است چه امتیازی میگیرم",
                "expected_finish": "stop",
                "expected_subspace": None,
                "should_keep_sticky": False,
                "is_respec": False,
                "notes": "non-existent grade G5 — expect no hallucinated grade, top_score low or refusal/no-evidence message, no invented tier",
            },
        ],
    },
    {
        "id": "conv_supplement_01",
        "subspace": "general",
        "description": "supplemental entity list: shareholders",
        "turns": [
            {
                "user": "سهامداران شرکت اعتبارسنجی ایران چه کسانی هستند",
                "expected_finish": "stop",
                "expected_subspace": "general",
                "should_keep_sticky": False,
                "is_respec": False,
                "notes": "should return supplemental entity list (shareholders), not just chunks",
            },
        ],
    },
]

# Single-turn baselines — fresh X-Request-ID each, no sticky.
# Spec lists 4 granular; we include 12 to reach ~50 total turns as per
# requirement header (12 multi = ~29 turns + 12 singles = ~41 turns; with
# hallucination/supplement singles already counted, total approaches 50).
SINGLE_BASELINES: List[Dict[str, Any]] = [
    # 4 granular from spec
    {
        "id": "single_cheque_granular",
        "subspace": "cheque",
        "query": "چک برگشتی چیست و چگونه رفع اثر می‌شود؟",
        "expected_finish": "stop",
        "filter_path": SUBSPACE_TO_FILTER_PATH["cheque"],
        "notes": "granular cheque — direct retrieval with filter_path",
    },
    {
        "id": "single_facilities_person_granular",
        "subspace": "facilities_person",
        "query": "امتیاز اعتباری اشخاص حقیقی چگونه محاسبه می‌شود؟",
        "expected_finish": "stop",
        "filter_path": SUBSPACE_TO_FILTER_PATH["facilities_person"],
        "notes": "granular facilities_person",
    },
    {
        "id": "single_facilities_legal_granular",
        "subspace": "facilities_legal",
        "query": "الزامات وثایق برای اشخاص حقوقی چیست؟",
        "expected_finish": "stop",
        "filter_path": SUBSPACE_TO_FILTER_PATH["facilities_legal"],
        "notes": "granular facilities_legal",
    },
    {
        "id": "single_general_granular",
        "subspace": "general",
        "query": "تاریخچه شرکت اعتبارسنجی ایران را بگو",
        "expected_finish": "stop",
        "filter_path": SUBSPACE_TO_FILTER_PATH["general"],
        "notes": "granular general",
    },
    # 8 additional singles to hit ~50-turn target and broaden coverage
    {
        "id": "single_cheque_bounce_effect",
        "subspace": "cheque",
        "query": "تاثیر چک برگشتی بر امتیاز اعتباری چقدر است؟",
        "expected_finish": "stop",
        "filter_path": SUBSPACE_TO_FILTER_PATH["cheque"],
        "notes": "cheque score impact",
    },
    {
        "id": "single_facilities_person_income",
        "subspace": "facilities_person",
        "query": "آیا میزان درآمد یا گردش حساب در رتبه اعتباری تاثیر دارد؟",
        "expected_finish": "stop",
        "filter_path": SUBSPACE_TO_FILTER_PATH["facilities_person"],
        "notes": "income/turnover effect on credit rank",
    },
    {
        "id": "single_facilities_legal_board",
        "subspace": "general",
        "query": "هیات مدیره شرکت اعتبارسنجی ایران چه کسانی هستند؟",
        "expected_finish": "stop",
        "filter_path": SUBSPACE_TO_FILTER_PATH["general"],
        "notes": "board members — general not facilities_legal",
    },
    {
        "id": "single_general_shareholders",
        "subspace": "general",
        "query": "سهامداران شرکت اعتبارسنجی ایران چه کسانی هستند؟",
        "expected_finish": "stop",
        "filter_path": SUBSPACE_TO_FILTER_PATH["general"],
        "notes": "shareholders — supplement path",
    },
    {
        "id": "single_greeting",
        "subspace": "greeting",
        "query": "سلام",
        "expected_finish": "greeting",
        "filter_path": None,
        "notes": "bare greeting baseline",
    },
    {
        "id": "single_scattered",
        "subspace": "cheque",
        "query": "وضعیت اعتباری چطور است",
        "expected_finish": "clarify",
        "filter_path": None,
        "notes": "scattered ambiguous — expect clarify",
    },
    {
        "id": "single_hallucination_probe",
        "subspace": "general",
        "query": "نمره اعتباری من G5 است چه امتیازی میگیرم",
        "expected_finish": "stop",
        "filter_path": None,
        "notes": "hallucination guard probe — same as conv_hallucination_01 T1",
    },
    {
        "id": "single_qasem_bour",
        "subspace": "general",
        "query": "قاسم بور کیه",
        "expected_finish": "stop",
        "filter_path": SUBSPACE_TO_FILTER_PATH["general"],
        "notes": "entity Qasem Bour — general",
    },
]

# Complete turn count helper (for summary header)
TOTAL_TURNS_MULTI = sum(len(c["turns"]) for c in CONVERSATIONS)
TOTAL_TURNS_SINGLE = len(SINGLE_BASELINES)
TOTAL_TURNS = TOTAL_TURNS_MULTI + TOTAL_TURNS_SINGLE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Return current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def _new_request_id(prefix: str = "bench") -> str:
    """Generate a fresh X-Request-ID for sticky session or single turn."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _artifact_path(base_dir: Optional[Path] = None) -> Path:
    """Resolve artifact output path with timestamp."""
    # Prefer components/orchestrator/evaluation/artifacts then evaluation/artifacts
    # so both import styles find results.
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if base_dir is not None:
        return base_dir / f"bench_results_{ts}.json"
    # Default: alongside this file
    here = Path(__file__).resolve().parent
    return here / "artifacts" / f"bench_results_{ts}.json"


def _resolve_artifact_dirs() -> List[Path]:
    """Return all artifact directories that should receive a copy."""
    here = Path(__file__).resolve().parent
    # Primary: components/orchestrator/evaluation/artifacts
    dirs = [here / "artifacts"]
    # Secondary: repo-level evaluation/artifacts (for `python -m evaluation.bench_runner`)
    repo_root = Path(__file__).resolve().parents[3]  # .../Work_Credit-RAG_Phase1
    dirs.append(repo_root / "evaluation" / "artifacts")
    # Tertiary: components/evaluation/artifacts if exists
    dirs.append(repo_root / "components" / "evaluation" / "artifacts")
    return dirs


# ---------------------------------------------------------------------------
# HTTP calls
# ---------------------------------------------------------------------------

async def call_orchestrator(
    messages: List[Dict[str, str]],
    request_id: str,
    model: str = DEFAULT_MODEL,
    timeout_s: float = HTTP_TIMEOUT_S,
) -> Dict[str, Any]:
    """
    Call orchestrator POST /v1/chat/completions.

    - Sends full messages history (sequential array) for LangGraph checkpoint
      plus X-Request-ID header for sticky thread_id.
    - Uses trust_env=False so localhost bypasses corporate Squid proxy.
    - Returns parsed JSON plus wall latency_ms and raw error if any.
    """
    import httpx  # local import so missing dep is reported per-call

    payload = {
        "model": model,
        "messages": messages,
    }
    headers = {"X-Request-ID": request_id}
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout_s, trust_env=False) as client:
            resp = await client.post(ORCH_URL, json=payload, headers=headers)
            latency_ms = int((time.monotonic() - t0) * 1000)
            # Try to parse JSON even on non-2xx so error detail is captured
            try:
                data = resp.json()
            except Exception:
                data = {"raw_text": resp.text[:2000], "status_code": resp.status_code}
            data["_http_status"] = resp.status_code
            data["_latency_ms_wall"] = latency_ms
            data["_request_id"] = request_id
            if resp.status_code >= 400:
                # Surface HTTP error but keep data for debugging
                data["_error"] = f"HTTP {resp.status_code}: {resp.text[:500]}"
            return data
    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        return {
            "_error": f"{type(exc).__name__}: {exc}",
            "_http_status": None,
            "_latency_ms_wall": latency_ms,
            "_request_id": request_id,
            "choices": [],
            "rag": {},
            "audit": None,
        }


async def call_kb(
    query: str,
    top_k: int = 20,
    filter_path: Optional[str] = None,
    keyword_boost: Optional[float] = None,
    timeout_s: float = 30.0,
) -> Dict[str, Any]:
    """
    Direct KB POST /search/api probe.

    Used for Hit@K comparison with vs without filter_path.
    Returns raw SearchSteps JSON plus wall latency or error.
    """
    import httpx

    payload: Dict[str, Any] = {"query": query, "top_k": top_k}
    if filter_path is not None:
        payload["filter_path"] = filter_path
    if keyword_boost is not None:
        payload["keyword_boost"] = keyword_boost

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout_s, trust_env=False) as client:
            resp = await client.post(KB_URL, json=payload)
            latency_ms = int((time.monotonic() - t0) * 1000)
            try:
                data = resp.json()
            except Exception:
                data = {"raw_text": resp.text[:2000], "status_code": resp.status_code}
            data["_http_status"] = resp.status_code
            data["_latency_ms_wall"] = latency_ms
            data["_filter_path"] = filter_path
            if resp.status_code >= 400:
                data["_error"] = f"HTTP {resp.status_code}: {resp.text[:500]}"
            return data
    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        return {
            "_error": f"{type(exc).__name__}: {exc}",
            "_http_status": None,
            "_latency_ms_wall": latency_ms,
            "_filter_path": filter_path,
            "final_results": [],
            "merged_candidates": [],
        }


async def call_observability(request_id: str, timeout_s: float = 5.0) -> Dict[str, Any]:
    """
    Best-effort GET /api/observability/pipeline/{request_id}.

    The fallback collector may not have this route; failure is non-fatal.
    """
    import httpx

    url = OBS_URL_TEMPLATE.format(request_id=request_id)
    try:
        async with httpx.AsyncClient(timeout=timeout_s, trust_env=False) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                try:
                    return resp.json()
                except Exception:
                    return {"raw_text": resp.text[:1000], "_http_status": resp.status_code}
            return {"_http_status": resp.status_code, "_empty": resp.text[:500]}
    except Exception as exc:
        return {"_error": f"{type(exc).__name__}: {exc}", "_http_status": None}


# ---------------------------------------------------------------------------
# Conversation executor
# ---------------------------------------------------------------------------

def _extract_turn_result(
    raw: Dict[str, Any],
    user_text: str,
    turn_def: Dict[str, Any],
    request_id: str,
    messages_sent: List[Dict[str, str]],
) -> Dict[str, Any]:
    """Normalize orchestrator raw JSON into per-turn record for artifact."""
    # Orchestrator shape: {choices:[{message:{content}, finish_reason}], rag:{citations, supplemental, follow_ups}, audit:{...}}
    choices = raw.get("choices") or []
    first = choices[0] if choices else {}
    message = first.get("message") or {}
    content = message.get("content", "")
    finish_reason = first.get("finish_reason", raw.get("_error") and "error" or "unknown")

    rag = raw.get("rag") or {}
    audit = raw.get("audit") or {}

    # Prefer wall latency, fall back to audit.latency_ms
    latency_ms = raw.get("_latency_ms_wall")
    if latency_ms is None and isinstance(audit, dict):
        latency_ms = audit.get("latency_ms")

    stage_timing = {}
    if isinstance(audit, dict):
        stage_timing = audit.get("stage_timing_ms") or {}

    retrieved_chunks = []
    if isinstance(audit, dict):
        retrieved_chunks = audit.get("retrieved_chunks") or []

    applied_subspace = None
    if isinstance(audit, dict):
        applied_subspace = audit.get("applied_subspace")

    # Reranker scores from audit
    reranker_scores = []
    if isinstance(audit, dict):
        reranker_scores = audit.get("reranker_scores") or []

    citations = rag.get("citations") if isinstance(rag, dict) else []
    supplemental = rag.get("supplemental") if isinstance(rag, dict) else None

    return {
        "user": user_text,
        "expected_finish": turn_def.get("expected_finish"),
        "expected_subspace": turn_def.get("expected_subspace"),
        "should_keep_sticky": turn_def.get("should_keep_sticky"),
        "is_respec": turn_def.get("is_respec"),
        "notes": turn_def.get("notes"),
        "request_id": request_id,
        "http_status": raw.get("_http_status"),
        "error": raw.get("_error"),
        "finish_reason": finish_reason,
        "applied_subspace": applied_subspace,
        "latency_ms": latency_ms,
        "latency_ms_wall": raw.get("_latency_ms_wall"),
        "stage_timing_ms": stage_timing,
        "retrieval_method": audit.get("retrieval_method") if isinstance(audit, dict) else None,
        "retrieved_chunks": retrieved_chunks[:5],  # cap for artifact size
        "retrieved_chunks_count": len(retrieved_chunks) if isinstance(retrieved_chunks, list) else 0,
        "reranker_scores": reranker_scores[:5] if isinstance(reranker_scores, list) else [],
        "citations": citations if isinstance(citations, list) else [],
        "citations_count": len(citations) if isinstance(citations, list) else 0,
        "supplemental": supplemental,
        "supplemental_count": len(supplemental) if isinstance(supplemental, list) else 0,
        "follow_ups": rag.get("follow_ups") if isinstance(rag, dict) else None,
        "content": content,
        "content_preview": content[:400] if isinstance(content, str) else "",
        "messages_sent_count": len(messages_sent),
        "raw_audit": {k: v for k, v in audit.items() if k in ("query", "rewritten_query", "available_subspaces", "filter_path")} if isinstance(audit, dict) else {},
    }


async def run_conversation(conv: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute one multi-turn conversation.

    - Reuses X-Request-ID across turns for LangGraph sticky checkpoint.
    - Sends full messages history each turn (user+assistant).
    - Records per-turn details plus pass/fail vs expected.
    """
    conv_id = conv["id"]
    request_id = _new_request_id(prefix=f"bench-{conv_id}")
    # History sent as OpenAI messages array — starts empty, grows per turn
    messages: List[Dict[str, str]] = []
    turn_results: List[Dict[str, Any]] = []
    t_conv0 = time.monotonic()

    print(f"\n[CONV] {conv_id} ({conv.get('description','')})  thread={request_id}  turns={len(conv['turns'])}")

    for idx, turn in enumerate(conv["turns"], start=1):
        user_text = turn["user"]
        messages.append({"role": "user", "content": user_text})

        # Call orchestrator with full history + sticky header
        raw = await call_orchestrator(messages=messages, request_id=request_id)

        result = _extract_turn_result(raw, user_text, turn, request_id, list(messages))
        result["turn_index"] = idx

        # Simple pass/fail vs expected (informational, not hard assert)
        expected = turn.get("expected_finish")
        actual = result["finish_reason"]
        # greeting is implemented as stop with greeting content; accept either
        if expected == "greeting" and actual in ("stop", "greeting"):
            result["finish_match"] = True
        else:
            result["finish_match"] = (expected == actual)

        # Subspace sticky check
        exp_sub = turn.get("expected_subspace")
        if exp_sub is not None:
            result["subspace_match"] = (result["applied_subspace"] == exp_sub)
        else:
            result["subspace_match"] = None  # not applicable

        # Observability best-effort (non-blocking, short timeout)
        try:
            obs = await call_observability(request_id)
            result["observability"] = {"ok": obs.get("_http_status") == 200, "data_preview": str(obs)[:400]}
        except Exception:
            result["observability"] = {"ok": False}

        turn_results.append(result)

        # Log one-liner per turn
        status = "PASS" if result["finish_match"] else "MISMATCH"
        sub_status = ""
        if result["subspace_match"] is not None:
            sub_status = f" subspace={'PASS' if result['subspace_match'] else 'MISMATCH'}({result['applied_subspace']})"
        print(
            f"  T{idx} [{status}]{sub_status} finish={actual} (exp {expected})  "
            f"lat={result['latency_ms']}ms  chunks={result['retrieved_chunks_count']}  "
            f"cit={result['citations_count']}  sup={result['supplemental_count']}  q={user_text[:50]!r}"
        )
        if result.get("error"):
            print(f"       ERROR: {result['error'][:200]}")

        # Append assistant reply to history for next turn (sticky messages array)
        content = result.get("content") or ""
        # Even on error/clarify, add assistant turn so history is faithful
        messages.append({"role": "assistant", "content": content})

        # Small pacing to avoid overwhelming local Gemma (optional)
        await asyncio.sleep(0.05)

    elapsed_ms = int((time.monotonic() - t_conv0) * 1000)
    return {
        "id": conv_id,
        "subspace": conv.get("subspace"),
        "description": conv.get("description"),
        "request_id": request_id,
        "turns": turn_results,
        "elapsed_ms": elapsed_ms,
        "turns_count": len(turn_results),
    }


async def run_single_baseline(item: Dict[str, Any]) -> Dict[str, Any]:
    """Execute one single-turn baseline with fresh X-Request-ID."""
    request_id = _new_request_id(prefix=f"bench-{item['id']}")
    query = item["query"]
    messages = [{"role": "user", "content": query}]
    raw = await call_orchestrator(messages=messages, request_id=request_id)
    turn_def = {
        "expected_finish": item.get("expected_finish"),
        "expected_subspace": item.get("subspace") if item.get("expected_finish") not in ("greeting", "clarify") else None,
        "should_keep_sticky": False,
        "is_respec": False,
        "notes": item.get("notes"),
    }
    result = _extract_turn_result(raw, query, turn_def, request_id, messages)
    result["id"] = item["id"]
    result["subspace"] = item.get("subspace")
    result["query"] = query
    result["filter_path"] = item.get("filter_path")
    # finish match
    expected = item.get("expected_finish")
    actual = result["finish_reason"]
    if expected == "greeting" and actual in ("stop", "greeting"):
        result["finish_match"] = True
    else:
        result["finish_match"] = (expected == actual)
    # subspace match (only when not greeting/clarify)
    if item.get("subspace") and expected not in ("greeting", "clarify"):
        # For greeting/clarify we don't expect a subspace; for others compare
        # but single baselines are fresh so applied_subspace should equal query subspace
        result["subspace_match"] = (result["applied_subspace"] == item.get("subspace"))
    else:
        result["subspace_match"] = None

    print(
        f"  [SINGLE] {item['id']} finish={actual} (exp {expected}) "
        f"{'PASS' if result['finish_match'] else 'MISMATCH'}  "
        f"lat={result['latency_ms']}ms  chunks={result['retrieved_chunks_count']}  q={query[:45]!r}"
    )
    if result.get("error"):
        print(f"           ERROR: {result['error'][:200]}")
    return result


async def run_kb_probe_for_singles(
    singles: List[Dict[str, Any]], top_k: int = 20
) -> List[Dict[str, Any]]:
    """
    Direct KB retrieval probe for each single-turn query.

    Calls KB twice: with filter_path and without, to compute Hit@K comparison.
    """
    probe_results: List[Dict[str, Any]] = []
    for item in singles:
        query = item["query"]
        fid = item["id"]
        print(f"  [KB-PROBE] {fid}  q={query[:45]!r}")

        # Without filter (global search)
        no_filter = await call_kb(query=query, top_k=top_k, filter_path=None)
        # With filter_path (if defined)
        with_filter = await call_kb(query=query, top_k=top_k, filter_path=item.get("filter_path"))

        def _summarize(kb_raw: Dict[str, Any]) -> Dict[str, Any]:
            final = kb_raw.get("final_results") or []
            merged = kb_raw.get("merged_candidates") or []
            return {
                "http_status": kb_raw.get("_http_status"),
                "error": kb_raw.get("_error"),
                "latency_ms": kb_raw.get("_latency_ms_wall"),
                "final_count": len(final),
                "merged_count": len(merged),
                "top1_preview": (final[0].get("content_preview") or final[0].get("content") or "")[:180] if final else "",
                "top1_score": final[0].get("rerank_score") if final and isinstance(final[0], dict) else None,
                "top1_doc": final[0].get("doc_title") if final and isinstance(final[0], dict) else None,
                "top_scores": [r.get("rerank_score", r.get("hybrid_score")) for r in final[:3]] if final else [],
                "has_results": len(final) > 0,
            }

        probe_results.append({
            "id": fid,
            "query": query,
            "filter_path": item.get("filter_path"),
            "no_filter": _summarize(no_filter),
            "with_filter": _summarize(with_filter),
            "filter_improves": None,  # manual inspection; could compare scores
        })
        # Heuristic: with_filter should have >= relevance if subspace matches
        nf_score = probe_results[-1]["no_filter"]["top1_score"]
        wf_score = probe_results[-1]["with_filter"]["top1_score"]
        if isinstance(nf_score, (int, float)) and isinstance(wf_score, (int, float)):
            probe_results[-1]["filter_improves"] = wf_score >= nf_score

        await asyncio.sleep(0.05)

    return probe_results


# ---------------------------------------------------------------------------
# Summary + artifact
# ---------------------------------------------------------------------------

def build_summary(
    conv_results: List[Dict[str, Any]],
    single_results: List[Dict[str, Any]],
    kb_probes: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build human-readable summary counters."""
    total_turns = sum(len(c["turns"]) for c in conv_results) + len(single_results)
    # Count finish mismatches
    finish_mismatches = 0
    subspace_mismatches = 0
    total_finish_checked = 0
    total_subspace_checked = 0
    errors = 0
    for c in conv_results:
        for t in c["turns"]:
            total_finish_checked += 1
            if not t.get("finish_match"):
                finish_mismatches += 1
            if t.get("subspace_match") is not None:
                total_subspace_checked += 1
                if not t["subspace_match"]:
                    subspace_mismatches += 1
            if t.get("error"):
                errors += 1
    for s in single_results:
        total_finish_checked += 1
        if not s.get("finish_match"):
            finish_mismatches += 1
        if s.get("subspace_match") is not None:
            total_subspace_checked += 1
            if not s["subspace_match"]:
                subspace_mismatches += 1
        if s.get("error"):
            errors += 1

    # Latency stats (wall)
    latencies = []
    for c in conv_results:
        for t in c["turns"]:
            if isinstance(t.get("latency_ms_wall"), int):
                latencies.append(t["latency_ms_wall"])
    for s in single_results:
        if isinstance(s.get("latency_ms_wall"), int):
            latencies.append(s["latency_ms_wall"])
    lat_sorted = sorted(latencies)
    p50 = lat_sorted[len(lat_sorted)//2] if lat_sorted else None
    p95 = lat_sorted[int(len(lat_sorted)*0.95)] if lat_sorted and len(lat_sorted) > 1 else (lat_sorted[0] if lat_sorted else None)

    return {
        "total_conversations": len(conv_results),
        "total_single_baselines": len(single_results),
        "total_turns": total_turns,
        "total_turns_multi": sum(len(c["turns"]) for c in conv_results),
        "finish_mismatches": finish_mismatches,
        "finish_checked": total_finish_checked,
        "subspace_mismatches": subspace_mismatches,
        "subspace_checked": total_subspace_checked,
        "errors": errors,
        "latency_ms": {
            "p50": p50,
            "p95": p95,
            "avg": int(sum(latencies)/len(latencies)) if latencies else None,
            "min": min(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "kb_probes": len(kb_probes) if kb_probes else 0,
    }


async def run_all(
    only_ids: Optional[List[str]] = None,
    skip_kb_probe: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Run full benchmark suite.

    - only_ids: filter to specific conversation/single ids
    - skip_kb_probe: skip direct KB Hit@K probe
    - dry_run: only first turn of first conversation + one KB probe
    """
    t0 = time.monotonic()
    ts = _now_iso()

    # Filter conversations if requested
    convs = CONVERSATIONS
    singles = SINGLE_BASELINES
    if only_ids:
        only_set = set(only_ids)
        convs = [c for c in CONVERSATIONS if c["id"] in only_set]
        singles = [s for s in SINGLE_BASELINES if s["id"] in only_set]
        # If filter matched nothing in one list, keep original for the other? No, respect filter strictly.
        if not convs and not singles:
            print(f"[WARN] --only filter {only_ids} matched nothing; running nothing")

    if dry_run:
        # Single turn smoke: first turn of first conv + one KB probe
        print("=== DRY-RUN: single turn smoke ===")
        conv = (convs or CONVERSATIONS)[0]
        # Truncate to first turn only
        conv_dry = {**conv, "turns": conv["turns"][:1]}
        conv_results = [await run_conversation(conv_dry)]
        # One single baseline dry
        single_results: List[Dict[str, Any]] = []
        if singles:
            single_results = [await run_single_baseline(singles[0])]
        # One KB probe
        kb_probes: Optional[List[Dict[str, Any]]] = None
        if not skip_kb_probe:
            kb_probes = await run_kb_probe_for_singles(singles[:1] if singles else [])
    else:
        conv_results = []
        for conv in convs:
            try:
                cr = await run_conversation(conv)
                conv_results.append(cr)
            except Exception as exc:
                print(f"[ERROR] conversation {conv['id']} failed: {exc}")
                conv_results.append({"id": conv["id"], "error": str(exc), "turns": []})

        single_results = []
        for s in singles:
            try:
                sr = await run_single_baseline(s)
                single_results.append(sr)
            except Exception as exc:
                print(f"[ERROR] single {s['id']} failed: {exc}")
                single_results.append({"id": s["id"], "error": str(exc), "query": s.get("query")})

        kb_probes = None
        if not skip_kb_probe:
            print("\n[KB-PROBE] direct retrieval with vs without filter_path ...")
            singles_for_probe = singles if singles else SINGLE_BASELINES
            kb_probes = await run_kb_probe_for_singles(singles_for_probe)

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    summary = build_summary(conv_results, single_results, kb_probes)

    result: Dict[str, Any] = {
        "meta": {
            "timestamp": ts,
            "elapsed_ms": elapsed_ms,
            "endpoints": {"orch": ORCH_URL, "kb": KB_URL, "obs_template": OBS_URL_TEMPLATE},
            "model": DEFAULT_MODEL,
            "http_timeout_s": HTTP_TIMEOUT_S,
            "dry_run": dry_run,
            "only_ids": only_ids,
            "total_turns_expected": TOTAL_TURNS,
            "total_turns_multi_expected": TOTAL_TURNS_MULTI,
            "total_turns_single_expected": TOTAL_TURNS_SINGLE,
        },
        "summary": summary,
        "conversations": conv_results,
        "single_baselines": single_results,
        "kb_probes": kb_probes,
        # Keep definitions for reproducibility
        "definitions": {
            "conversations": CONVERSATIONS,
            "single_baselines": SINGLE_BASELINES,
        },
    }
    return result


def save_artifact(data: Dict[str, Any], out_path: Optional[Path] = None) -> List[Path]:
    """
    Save artifact JSON to all resolved artifact dirs.

    Returns list of written paths.
    """
    written: List[Path] = []

    if out_path is not None:
        # Explicit path — write only there
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        written.append(out_path)
        print(f"[ARTIFACT] wrote {out_path}  ({out_path.stat().st_size} bytes)")
        return written

    # Default: write to all artifact dirs with same timestamped filename
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"bench_results_{ts}.json"
    # Also write latest.json for convenience
    for d in _resolve_artifact_dirs():
        try:
            d.mkdir(parents=True, exist_ok=True)
            p = d / filename
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            written.append(p)
            # Update latest.json symlink/copy
            latest = d / "bench_results_latest.json"
            with open(latest, "w", encoding="utf-8") as lf:
                json.dump(data, lf, ensure_ascii=False, indent=2)
        except Exception as exc:
            print(f"[WARN] failed to write artifact to {d}: {exc}")

    for p in written:
        try:
            print(f"[ARTIFACT] wrote {p}  ({p.stat().st_size} bytes)")
        except Exception:
            print(f"[ARTIFACT] wrote {p}")

    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Work Credit RAG benchmark conversation executor")
    parser.add_argument("--dry-run", action="store_true", help="single turn smoke test (first turn + one KB probe)")
    parser.add_argument("--only", nargs="*", default=None, help="only run these conversation/single ids")
    parser.add_argument("--skip-kb-probe", action="store_true", help="skip direct KB retrieval probe")
    parser.add_argument("--out", type=str, default=None, help="explicit output path for artifact JSON")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="orchestrator model id")
    return parser.parse_args()


async def _amain() -> None:
    args = parse_args()
    global DEFAULT_MODEL
    if args.model:
        DEFAULT_MODEL = args.model

    print(f"=== Work Credit RAG bench_runner ===")
    print(f"  ORCH={ORCH_URL}  KB={KB_URL}  model={DEFAULT_MODEL}  dry_run={args.dry_run}")
    print(f"  Conversations: {len(CONVERSATIONS)} multi ({TOTAL_TURNS_MULTI} turns) + {len(SINGLE_BASELINES)} singles = {TOTAL_TURNS} turns")
    if args.only:
        print(f"  Filter --only: {args.only}")
    # Quick health check before heavy run
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            for name, url in [("KB", "http://127.0.0.1:8000/health"), ("ORCH", "http://127.0.0.1:8100/health")]:
                try:
                    r = await client.get(url)
                    print(f"  Health {name} {url}: {r.status_code} {r.text[:120]}")
                except Exception as e:
                    print(f"  Health {name} {url}: FAILED {e}")
    except Exception:
        pass

    data = await run_all(only_ids=args.only, skip_kb_probe=args.skip_kb_probe, dry_run=args.dry_run)

    # Summary log
    s = data["summary"]
    print("\n=== SUMMARY ===")
    print(f"  total_turns={s['total_turns']}  conv={s['total_conversations']}  singles={s['total_single_baselines']}")
    print(f"  finish mismatches: {s['finish_mismatches']}/{s['finish_checked']}")
    print(f"  subspace mismatches: {s['subspace_mismatches']}/{s['subspace_checked']}")
    print(f"  errors: {s['errors']}")
    print(f"  latency p50={s['latency_ms']['p50']}ms p95={s['latency_ms']['p95']}ms avg={s['latency_ms']['avg']}ms")
    print(f"  elapsed wall: {data['meta']['elapsed_ms']}ms")

    out_path = Path(args.out) if args.out else None
    save_artifact(data, out_path=out_path)


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
