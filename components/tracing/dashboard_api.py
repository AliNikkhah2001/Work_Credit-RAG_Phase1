"""Observability dashboard API router."""
from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
from typing import Optional, List
import time
import json

router = APIRouter(prefix="/api/observability", tags=["observability"])

# Import eval_store lazily - allow both absolute and relative imports
try:
    import eval_store  # type: ignore
except ImportError:
    try:
        from . import eval_store  # type: ignore
    except ImportError:
        eval_store = None  # type: ignore

try:
    import observe as observer  # type: ignore
except Exception:
    try:
        from . import observe as observer  # type: ignore
    except Exception:
        observer = None

# Ensure DB initialized lazily
_db_initialized = False

def _ensure_db():
    global _db_initialized
    if eval_store is None:
        return
    if _db_initialized:
        return
    try:
        eval_store.init_db()
        _db_initialized = True
    except Exception:
        pass


class SaveTraceRequest(BaseModel):
    request_id: str
    chat_id: Optional[str] = None
    user_id: Optional[str] = None
    model: Optional[str] = None
    user_query: Optional[str] = None
    rewritten_query: Optional[str] = None
    response: Optional[str] = None
    stage_timing: Optional[dict] = None
    guardrail_input: Optional[dict] = None
    guardrail_output: Optional[dict] = None
    retrieved_chunks: Optional[list] = None
    citations: Optional[list] = None
    context_preview: Optional[str] = None
    latency_ms: Optional[int] = None

    class Config:
        extra = "allow"


class SaveEvaluationRequest(BaseModel):
    request_id: str
    chat_id: Optional[str] = None
    message_id: Optional[str] = None
    user_id: Optional[str] = None
    model: Optional[str] = None
    user_query: Optional[str] = None
    response: Optional[str] = None
    rating: Optional[int] = None
    thumbs: Optional[str] = None
    comment: Optional[str] = None
    tags: Optional[List[str]] = None
    latency_ms: Optional[int] = None

    class Config:
        extra = "allow"


# ---------------------------------------------------------------------------
# Traces
# ---------------------------------------------------------------------------

@router.post("/traces")
async def save_trace_endpoint(request: Request):
    _ensure_db()
    if eval_store is None:
        return JSONResponse({"error": "eval_store unavailable"}, status_code=500)
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"invalid JSON: {e}"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "body must be JSON object"}, status_code=400)
    if not body.get("request_id"):
        return JSONResponse({"error": "request_id is required"}, status_code=400)
    try:
        result = eval_store.save_trace(body)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/traces")
async def list_traces_endpoint(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    model: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    _ensure_db()
    if eval_store is None:
        return JSONResponse({"error": "eval_store unavailable"}, status_code=500)
    try:
        rows, total = eval_store.list_traces(limit=limit, offset=offset, model=model, search=search)
        return {"data": rows, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/traces/{request_id}")
async def get_trace_endpoint(request_id: str):
    _ensure_db()
    if eval_store is None:
        return JSONResponse({"error": "eval_store unavailable"}, status_code=500)
    try:
        trace = eval_store.get_trace(request_id)
        if trace is None:
            return JSONResponse({"error": f"trace not found: {request_id}"}, status_code=404)
        return trace
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/pipeline/{request_id}")
async def get_pipeline_endpoint(request_id: str):
    _ensure_db()
    if eval_store is None:
        return JSONResponse({"error": "eval_store unavailable"}, status_code=500)
    try:
        result = eval_store.get_trace_with_timeline(request_id)
        if result is None:
            return JSONResponse({"error": f"pipeline not found: {request_id}"}, status_code=404)
        return result
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Evaluations
# ---------------------------------------------------------------------------

@router.post("/evaluations")
async def save_evaluation_endpoint(request: Request):
    _ensure_db()
    if eval_store is None:
        return JSONResponse({"error": "eval_store unavailable"}, status_code=500)
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"invalid JSON: {e}"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "body must be JSON object"}, status_code=400)
    if not body.get("request_id"):
        return JSONResponse({"error": "request_id is required"}, status_code=400)
    # Validate rating if present
    rating = body.get("rating")
    if rating is not None:
        try:
            r = int(rating)
            if r < 1 or r > 5:
                return JSONResponse({"error": "rating must be 1-5"}, status_code=400)
        except Exception:
            return JSONResponse({"error": "rating must be integer 1-5"}, status_code=400)
    # Validate thumbs
    thumbs = body.get("thumbs")
    if thumbs is not None and thumbs not in ("up", "down"):
        return JSONResponse({"error": "thumbs must be up or down"}, status_code=400)
    try:
        result = eval_store.save_evaluation(body)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/evaluations")
async def list_evaluations_endpoint(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    rating: Optional[int] = Query(None, ge=1, le=5),
    model: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    _ensure_db()
    if eval_store is None:
        return JSONResponse({"error": "eval_store unavailable"}, status_code=500)
    try:
        rows, total = eval_store.list_evaluations(limit=limit, offset=offset, rating=rating, model=model, tag=tag, search=search)
        return {"data": rows, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/evaluations/{eval_id}")
async def get_evaluation_endpoint(eval_id: str):
    _ensure_db()
    if eval_store is None:
        return JSONResponse({"error": "eval_store unavailable"}, status_code=500)
    try:
        ev = eval_store.get_evaluation(eval_id)
        if ev is None:
            return JSONResponse({"error": f"evaluation not found: {eval_id}"}, status_code=404)
        return ev
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.put("/evaluations/{eval_id}")
async def update_evaluation_endpoint(eval_id: str, request: Request):
    _ensure_db()
    if eval_store is None:
        return JSONResponse({"error": "eval_store unavailable"}, status_code=500)
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"invalid JSON: {e}"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "body must be JSON object"}, status_code=400)
    # Validate rating if present
    if "rating" in body and body["rating"] is not None:
        try:
            r = int(body["rating"])
            if r < 1 or r > 5:
                return JSONResponse({"error": "rating must be 1-5"}, status_code=400)
        except Exception:
            return JSONResponse({"error": "rating must be integer 1-5"}, status_code=400)
    if "thumbs" in body and body["thumbs"] is not None and body["thumbs"] not in ("up", "down"):
        return JSONResponse({"error": "thumbs must be up or down"}, status_code=400)
    try:
        result = eval_store.update_evaluation(eval_id, body)
        if result is None:
            return JSONResponse({"error": f"evaluation not found: {eval_id}"}, status_code=404)
        return result
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/evaluations/{eval_id}")
async def delete_evaluation_endpoint(eval_id: str):
    _ensure_db()
    if eval_store is None:
        return JSONResponse({"error": "eval_store unavailable"}, status_code=500)
    try:
        ok = eval_store.delete_evaluation(eval_id)
        if not ok:
            return JSONResponse({"error": f"evaluation not found: {eval_id}"}, status_code=404)
        return {"success": True, "deleted": eval_id}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Overview / Timeseries / Export
# ---------------------------------------------------------------------------

@router.get("/overview")
async def overview_endpoint():
    _ensure_db()
    if eval_store is None:
        return JSONResponse({"error": "eval_store unavailable"}, status_code=500)
    try:
        stats = eval_store.get_overview_stats()
        return stats
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/timeseries")
async def timeseries_endpoint(hours: int = Query(24, ge=1, le=168)):
    _ensure_db()
    if eval_store is None:
        return JSONResponse({"error": "eval_store unavailable"}, status_code=500)
    try:
        data = eval_store.get_timeseries(hours=hours)
        return {"data": data, "hours": hours}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/export")
async def export_endpoint(
    min_rating: Optional[int] = Query(None, ge=1, le=5),
    max_rating: Optional[int] = Query(None, ge=1, le=5),
    tags: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    format: str = Query("jsonl", pattern="^(jsonl|csv)$"),
):
    _ensure_db()
    if eval_store is None:
        return JSONResponse({"error": "eval_store unavailable"}, status_code=500)
    try:
        result = eval_store.export_evaluations(
            min_rating=min_rating,
            max_rating=max_rating,
            tags=tags,
            model=model,
            date_from=date_from,
            date_to=date_to,
            format=format,
        )
        if format == "csv":
            return PlainTextResponse(result, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=evaluations.csv"})
        else:
            return PlainTextResponse(result, media_type="application/jsonl; charset=utf-8", headers={"Content-Disposition": "attachment; filename=evaluations.jsonl"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
