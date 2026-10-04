"""SQLite store for evaluations and pipeline traces."""
import sqlite3
import json
import time
import uuid
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

DB_PATH = Path(os.getenv("EVAL_DB_PATH", "/tmp/observability.db"))
TRACE_JSONL = Path(os.getenv("TRACE_JSONL", "/tmp/langfuse_traces.jsonl"))


def get_db() -> sqlite3.Connection:
    """Open SQLite connection with WAL mode and thread-safe settings."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=10.0)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for concurrent access
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=10000;")
    except Exception:
        pass
    return conn


def init_db():
    """Create tables and indexes if not exist."""
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id TEXT PRIMARY KEY,
                request_id TEXT,
                chat_id TEXT,
                message_id TEXT,
                user_id TEXT,
                model TEXT,
                user_query TEXT,
                response TEXT,
                rating INTEGER,
                thumbs TEXT,
                comment TEXT,
                tags TEXT,
                latency_ms INTEGER,
                created_at REAL,
                updated_at REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS traces (
                id TEXT PRIMARY KEY,
                request_id TEXT UNIQUE,
                chat_id TEXT,
                user_id TEXT,
                model TEXT,
                user_query TEXT,
                rewritten_query TEXT,
                response TEXT,
                stage_timing TEXT,
                guardrail_input TEXT,
                guardrail_output TEXT,
                retrieved_chunks TEXT,
                citations TEXT,
                context_preview TEXT,
                latency_ms INTEGER,
                created_at REAL
            )
        """)
        # Indexes for evaluations
        conn.execute("CREATE INDEX IF NOT EXISTS idx_eval_request_id ON evaluations(request_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_eval_rating ON evaluations(rating)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_eval_model ON evaluations(model)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_eval_created_at ON evaluations(created_at)")
        # Indexes for traces
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trace_request_id ON traces(request_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trace_model ON traces(model)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trace_created_at ON traces(created_at)")
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> float:
    return time.time()


def _dumps(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    return json.dumps(obj, ensure_ascii=False)


def _loads(s: Optional[str], default=None):
    if s is None or s == "":
        return default
    try:
        return json.loads(s)
    except Exception:
        return default


def _eval_row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    # tags stored as JSON array string -> return as list
    tags_raw = d.get("tags")
    if tags_raw is None:
        d["tags"] = []
    else:
        try:
            parsed = json.loads(tags_raw)
            d["tags"] = parsed if isinstance(parsed, list) else []
        except Exception:
            d["tags"] = []
    return d


def _trace_row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for field in ("stage_timing", "guardrail_input", "guardrail_output", "retrieved_chunks", "citations"):
        raw = d.get(field)
        if raw is None:
            # default for array fields
            if field in ("retrieved_chunks", "citations"):
                d[field] = []
            else:
                d[field] = None
                # for stage_timing we prefer dict or None
                if field == "stage_timing":
                    d[field] = {}
                    # keep empty dict if not present? spec says JSON, so keep {}
                    # but if original was None we leave as {} or None depending on expected
                    # Use {} for timing, None for guardrails
                    if field in ("guardrail_input", "guardrail_output"):
                        d[field] = None
                continue
        else:
            try:
                parsed = json.loads(raw)
                d[field] = parsed
            except Exception:
                # keep raw if parse fails
                d[field] = raw
    # Ensure retrieved_chunks / citations are lists
    if d.get("retrieved_chunks") is None:
        d["retrieved_chunks"] = []
    if d.get("citations") is None:
        d["citations"] = []
    if d.get("stage_timing") is None:
        d["stage_timing"] = {}
    return d


# ---------------------------------------------------------------------------
# Evaluations
# ---------------------------------------------------------------------------

def save_evaluation(data: dict) -> dict:
    """Insert or update evaluation. Generate id if not provided."""
    init_db()
    conn = get_db()
    try:
        eval_id = data.get("id") or uuid.uuid4().hex[:12]
        now = _now()
        # Handle tags conversion
        tags_val = data.get("tags")
        if isinstance(tags_val, list):
            tags_str = json.dumps(tags_val, ensure_ascii=False)
        elif isinstance(tags_val, str):
            # if already string, try to keep as JSON array string
            try:
                parsed = json.loads(tags_val)
                if isinstance(parsed, list):
                    tags_str = json.dumps(parsed, ensure_ascii=False)
                else:
                    tags_str = json.dumps([tags_val], ensure_ascii=False)
            except Exception:
                tags_str = json.dumps([tags_val], ensure_ascii=False)
        elif tags_val is None:
            tags_str = json.dumps([], ensure_ascii=False)
        else:
            tags_str = json.dumps([], ensure_ascii=False)

        # Check if id exists
        cur = conn.execute("SELECT id, created_at FROM evaluations WHERE id=?", (eval_id,))
        existing = cur.fetchone()
        if existing:
            created_at = existing["created_at"]
            conn.execute("""
                UPDATE evaluations SET
                    request_id=?, chat_id=?, message_id=?, user_id=?, model=?,
                    user_query=?, response=?, rating=?, thumbs=?, comment=?,
                    tags=?, latency_ms=?, updated_at=?
                WHERE id=?
            """, (
                data.get("request_id"),
                data.get("chat_id"),
                data.get("message_id"),
                data.get("user_id"),
                data.get("model"),
                data.get("user_query"),
                data.get("response"),
                data.get("rating"),
                data.get("thumbs"),
                data.get("comment"),
                tags_str,
                data.get("latency_ms"),
                now,
                eval_id,
            ))
        else:
            created_at = data.get("created_at") or now
            conn.execute("""
                INSERT INTO evaluations
                (id, request_id, chat_id, message_id, user_id, model, user_query, response, rating, thumbs, comment, tags, latency_ms, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                eval_id,
                data.get("request_id"),
                data.get("chat_id"),
                data.get("message_id"),
                data.get("user_id"),
                data.get("model"),
                data.get("user_query"),
                data.get("response"),
                data.get("rating"),
                data.get("thumbs"),
                data.get("comment"),
                tags_str,
                data.get("latency_ms"),
                created_at,
                now,
            ))
        conn.commit()
        row = conn.execute("SELECT * FROM evaluations WHERE id=?", (eval_id,)).fetchone()
        if row is not None:
            return _eval_row_to_dict(row)
        # fallback
        return {"id": eval_id, **data, "tags": _loads(tags_str, []), "created_at": created_at, "updated_at": now}
    finally:
        conn.close()


def list_evaluations(limit=50, offset=0, rating=None, model=None, tag=None, search=None) -> tuple[list[dict], int]:
    """Filtered + paginated list, returns (rows, total_count). search matches user_query, response, comment."""
    init_db()
    conn = get_db()
    try:
        where_clauses = []
        params: list[Any] = []
        if rating is not None:
            where_clauses.append("rating = ?")
            params.append(rating)
        if model is not None:
            where_clauses.append("model = ?")
            params.append(model)
        if tag is not None:
            # tags stored as JSON array string, use LIKE for simple containment
            # match with json pattern: search for tag string inside JSON
            where_clauses.append("tags LIKE ?")
            params.append(f'%"{tag}"%')
        if search is not None and search.strip() != "":
            where_clauses.append("(user_query LIKE ? OR response LIKE ? OR comment LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like])
        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # total count
        count_sql = f"SELECT COUNT(*) FROM evaluations{where_sql}"
        total = conn.execute(count_sql, params).fetchone()[0]

        # paginated rows
        query_sql = f"SELECT * FROM evaluations{where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        paginated_params = params + [limit, offset]
        cur = conn.execute(query_sql, paginated_params)
        rows = [_eval_row_to_dict(r) for r in cur.fetchall()]
        return rows, total
    finally:
        conn.close()


def get_evaluation(eval_id: str) -> Optional[dict]:
    init_db()
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM evaluations WHERE id=?", (eval_id,)).fetchone()
        if row is None:
            return None
        return _eval_row_to_dict(row)
    finally:
        conn.close()


def update_evaluation(eval_id: str, data: dict) -> Optional[dict]:
    init_db()
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM evaluations WHERE id=?", (eval_id,)).fetchone()
        if row is None:
            return None
        existing = _eval_row_to_dict(row)
        # Merge existing with new data (excluding id)
        merged = {**existing, **{k: v for k, v in data.items() if k != "id"}}
        # Ensure tags handling
        tags_val = merged.get("tags")
        if isinstance(tags_val, list):
            tags_str = json.dumps(tags_val, ensure_ascii=False)
        elif isinstance(tags_val, str):
            try:
                parsed = json.loads(tags_val)
                tags_str = json.dumps(parsed, ensure_ascii=False) if isinstance(parsed, list) else json.dumps([tags_val], ensure_ascii=False)
            except Exception:
                tags_str = json.dumps([tags_val], ensure_ascii=False)
        else:
            tags_str = json.dumps([], ensure_ascii=False)

        now = _now()
        conn.execute("""
            UPDATE evaluations SET
                request_id=?, chat_id=?, message_id=?, user_id=?, model=?,
                user_query=?, response=?, rating=?, thumbs=?, comment=?,
                tags=?, latency_ms=?, updated_at=?
            WHERE id=?
        """, (
            merged.get("request_id"),
            merged.get("chat_id"),
            merged.get("message_id"),
            merged.get("user_id"),
            merged.get("model"),
            merged.get("user_query"),
            merged.get("response"),
            merged.get("rating"),
            merged.get("thumbs"),
            merged.get("comment"),
            tags_str,
            merged.get("latency_ms"),
            now,
            eval_id,
        ))
        conn.commit()
        updated_row = conn.execute("SELECT * FROM evaluations WHERE id=?", (eval_id,)).fetchone()
        return _eval_row_to_dict(updated_row) if updated_row else None
    finally:
        conn.close()


def delete_evaluation(eval_id: str) -> bool:
    init_db()
    conn = get_db()
    try:
        cur = conn.execute("DELETE FROM evaluations WHERE id=?", (eval_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Traces
# ---------------------------------------------------------------------------

def append_trace_jsonl(data: dict):
    """Append to TRACE_JSONL file."""
    try:
        TRACE_JSONL.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_JSONL.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read_traces_jsonl(limit=100) -> list[dict]:
    """Read last N from JSONL."""
    if not TRACE_JSONL.exists():
        return []
    try:
        lines = TRACE_JSONL.read_text(encoding="utf-8").splitlines()
        # take last N
        selected = lines[-limit:] if limit else lines
        out = []
        for ln in selected:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out
    except Exception:
        return []


def save_trace(data: dict) -> dict:
    """Upsert by request_id. Also append to JSONL file."""
    init_db()
    request_id = data.get("request_id")
    if not request_id:
        request_id = uuid.uuid4().hex[:12]
        data["request_id"] = request_id
    trace_id = data.get("id") or request_id

    # Prepare JSON fields
    stage_timing_str = _dumps(data.get("stage_timing")) if data.get("stage_timing") is not None else _dumps({})
    guardrail_input_str = _dumps(data.get("guardrail_input"))
    guardrail_output_str = _dumps(data.get("guardrail_output"))
    # retrieved_chunks and citations should be JSON arrays
    rc = data.get("retrieved_chunks")
    if rc is None:
        rc_str = _dumps([])
    else:
        rc_str = _dumps(rc)
    cit = data.get("citations")
    if cit is None:
        cit_str = _dumps([])
    else:
        cit_str = _dumps(cit)

    conn = get_db()
    try:
        # Check existing by request_id
        cur = conn.execute("SELECT id, created_at FROM traces WHERE request_id=?", (request_id,))
        existing = cur.fetchone()
        now = _now()
        if existing:
            created_at = existing["created_at"]
            # Keep original id
            trace_id = existing["id"]
            conn.execute("""
                UPDATE traces SET
                    chat_id=?, user_id=?, model=?, user_query=?, rewritten_query=?,
                    response=?, stage_timing=?, guardrail_input=?, guardrail_output=?,
                    retrieved_chunks=?, citations=?, context_preview=?, latency_ms=?
                WHERE request_id=?
            """, (
                data.get("chat_id"),
                data.get("user_id"),
                data.get("model"),
                data.get("user_query"),
                data.get("rewritten_query"),
                data.get("response"),
                stage_timing_str,
                guardrail_input_str,
                guardrail_output_str,
                rc_str,
                cit_str,
                data.get("context_preview"),
                data.get("latency_ms"),
                request_id,
            ))
        else:
            created_at = data.get("created_at") or now
            conn.execute("""
                INSERT INTO traces
                (id, request_id, chat_id, user_id, model, user_query, rewritten_query, response, stage_timing, guardrail_input, guardrail_output, retrieved_chunks, citations, context_preview, latency_ms, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                trace_id,
                request_id,
                data.get("chat_id"),
                data.get("user_id"),
                data.get("model"),
                data.get("user_query"),
                data.get("rewritten_query"),
                data.get("response"),
                stage_timing_str,
                guardrail_input_str,
                guardrail_output_str,
                rc_str,
                cit_str,
                data.get("context_preview"),
                data.get("latency_ms"),
                created_at,
            ))
        conn.commit()
        row = conn.execute("SELECT * FROM traces WHERE request_id=?", (request_id,)).fetchone()
        result = _trace_row_to_dict(row) if row else {**data, "id": trace_id, "created_at": created_at}
        # Also append to JSONL
        try:
            append_trace_jsonl(result)
        except Exception:
            pass
        return result
    finally:
        conn.close()


def list_traces(limit=50, offset=0, model=None, search=None) -> tuple[list[dict], int]:
    init_db()
    conn = get_db()
    try:
        where_clauses = []
        params: list[Any] = []
        if model is not None:
            where_clauses.append("model = ?")
            params.append(model)
        if search is not None and search.strip() != "":
            where_clauses.append("(user_query LIKE ? OR response LIKE ? OR request_id LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like])
        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        count_sql = f"SELECT COUNT(*) FROM traces{where_sql}"
        total = conn.execute(count_sql, params).fetchone()[0]
        query_sql = f"SELECT * FROM traces{where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        paginated_params = params + [limit, offset]
        cur = conn.execute(query_sql, paginated_params)
        rows = [_trace_row_to_dict(r) for r in cur.fetchall()]
        return rows, total
    finally:
        conn.close()


def get_trace(request_id: str) -> Optional[dict]:
    init_db()
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM traces WHERE request_id=?", (request_id,)).fetchone()
        if row is None:
            return None
        return _trace_row_to_dict(row)
    finally:
        conn.close()


def get_trace_with_timeline(request_id: str) -> Optional[dict]:
    """Combines SQLite trace + observer.py timeline if available. Tries to enrich with observer.get_timeline()."""
    trace = get_trace(request_id)
    if trace is None:
        # still try to get observer timeline alone
        trace = {}
    timeline = None
    try:
        import observe as observer  # type: ignore
        try:
            tl = observer.get_timeline(request_id)
            # consider empty timeline as no data
            if tl and (tl.get("spans") or tl.get("input") is not None or tl.get("output") is not None):
                timeline = tl
            else:
                # try fallback host / file
                try:
                    tl2 = observer.get_timeline(request_id, observer.FALLBACK_HOST)
                    if tl2 and (tl2.get("spans") or tl2.get("input") is not None or tl2.get("output") is not None):
                        timeline = tl2
                    else:
                        tl3 = observer.get_timeline(request_id, None)
                        if tl3 and (tl3.get("spans") or tl3.get("input") is not None or tl3.get("output") is not None):
                            timeline = tl3
                except Exception:
                    pass
        except Exception:
            pass
    except ImportError:
        try:
            from . import observe as observer2  # type: ignore
            try:
                tl = observer2.get_timeline(request_id)
                if tl and (tl.get("spans") or tl.get("input") is not None or tl.get("output") is not None):
                    timeline = tl
            except Exception:
                pass
        except Exception:
            pass
    except Exception:
        pass

    if not trace and timeline is None:
        return None
    # If no trace in DB but timeline exists, create minimal trace dict
    if not trace:
        trace = {"request_id": request_id}
    result = dict(trace)
    result["timeline"] = timeline
    # Also include observer alias if timeline present
    if timeline:
        result["observer_timeline"] = timeline
    return result


def get_overview_stats() -> dict:
    """Returns aggregate stats."""
    init_db()
    conn = get_db()
    try:
        total_requests = conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
        total_evaluations = conn.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0]

        # avg latency from traces
        row = conn.execute("SELECT AVG(latency_ms) FROM traces WHERE latency_ms IS NOT NULL").fetchone()
        avg_latency = row[0] if row[0] is not None else 0
        # also consider evaluations latency if traces empty
        if (avg_latency == 0 or avg_latency is None) and total_evaluations > 0:
            r2 = conn.execute("SELECT AVG(latency_ms) FROM evaluations WHERE latency_ms IS NOT NULL").fetchone()
            if r2[0] is not None:
                avg_latency = r2[0]

        # latency percentiles
        latencies = []
        try:
            cur = conn.execute("SELECT latency_ms FROM traces WHERE latency_ms IS NOT NULL ORDER BY latency_ms")
            latencies = [r[0] for r in cur.fetchall() if r[0] is not None]
        except Exception:
            latencies = []
        p50 = p95 = 0
        if latencies:
            latencies_sorted = sorted(latencies)
            n = len(latencies_sorted)
            # p50 median
            mid = n // 2
            if n % 2 == 1:
                p50 = latencies_sorted[mid]
            else:
                p50 = (latencies_sorted[mid - 1] + latencies_sorted[mid]) / 2
            # p95
            idx95 = int(n * 0.95)
            if idx95 >= n:
                idx95 = n - 1
            p95 = latencies_sorted[idx95]

        # rating distribution
        rating_dist: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        try:
            cur = conn.execute("SELECT rating, COUNT(*) as cnt FROM evaluations WHERE rating IS NOT NULL GROUP BY rating")
            for r in cur.fetchall():
                rating = r[0]
                cnt = r[1]
                if rating in rating_dist:
                    rating_dist[rating] = cnt
                else:
                    rating_dist[int(rating)] = cnt
        except Exception:
            pass

        # thumbs up/down
        thumbs_up = conn.execute("SELECT COUNT(*) FROM evaluations WHERE thumbs='up'").fetchone()[0]
        thumbs_down = conn.execute("SELECT COUNT(*) FROM evaluations WHERE thumbs='down'").fetchone()[0]

        # block_rate from traces guardrail fields if available? Fallback try to count blocked from guardrail_output
        block_rate = 0.0
        try:
            # Count traces where guardrail output indicates blocked
            total_with_guard = conn.execute("SELECT COUNT(*) FROM traces WHERE guardrail_output IS NOT NULL").fetchone()[0]
            blocked = 0
            if total_with_guard:
                cur = conn.execute("SELECT guardrail_output FROM traces WHERE guardrail_output IS NOT NULL")
                for r in cur.fetchall():
                    raw = r[0]
                    try:
                        obj = json.loads(raw)
                        # check allowed field
                        if isinstance(obj, dict):
                            if obj.get("allowed") is False or obj.get("blocked") is True or obj.get("action") == "block":
                                blocked += 1
                            elif isinstance(obj.get("guardrail_output"), dict) and obj["guardrail_output"].get("allowed") is False:
                                blocked += 1
                    except Exception:
                        continue
                block_rate = round(blocked / total_with_guard, 4) if total_with_guard else 0.0
        except Exception:
            block_rate = 0.0

        # model_distribution
        model_dist: Dict[str, int] = {}
        try:
            cur = conn.execute("SELECT model, COUNT(*) as cnt FROM traces WHERE model IS NOT NULL GROUP BY model")
            for r in cur.fetchall():
                model_dist[str(r[0])] = r[1]
            # also add evaluations model distribution if traces empty for that model
            cur2 = conn.execute("SELECT model, COUNT(*) as cnt FROM evaluations WHERE model IS NOT NULL GROUP BY model")
            for r in cur2.fetchall():
                m = str(r[0])
                if m not in model_dist:
                    model_dist[m] = r[1]
        except Exception:
            pass

        # requests_per_hour last 24h buckets
        import datetime as _dt
        now_ts = _now()
        requests_per_hour = []
        try:
            for i in range(24):
                bucket_start = now_ts - (23 - i) * 3600
                bucket_end = bucket_start + 3600
                cnt = conn.execute("SELECT COUNT(*) FROM traces WHERE created_at >= ? AND created_at < ?", (bucket_start, bucket_end)).fetchone()[0]
                hour_label = _dt.datetime.fromtimestamp(bucket_start).strftime("%Y-%m-%dT%H:00")
                requests_per_hour.append({"hour": hour_label, "count": cnt})
        except Exception:
            requests_per_hour = []

        evaluations_per_rating = dict(rating_dist)

        return {
            "total_requests": total_requests,
            "total_evaluations": total_evaluations,
            "avg_latency_ms": round(float(avg_latency), 2) if avg_latency else 0,
            "p50_latency_ms": p50,
            "p95_latency_ms": p95,
            "rating_distribution": rating_dist,
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down,
            "block_rate": block_rate,
            "model_distribution": model_dist,
            "requests_per_hour": requests_per_hour,
            "evaluations_per_rating": evaluations_per_rating,
        }
    finally:
        conn.close()


def get_timeseries(hours=24) -> list[dict]:
    """Hourly buckets: {hour: "2026-09-23T10:00", requests: N, evaluations: N, avg_latency: M, avg_rating: R}"""
    init_db()
    conn = get_db()
    try:
        import datetime as _dt
        now_ts = _now()
        buckets: list[dict] = []
        for i in range(hours):
            bucket_start = now_ts - (hours - 1 - i) * 3600
            bucket_end = bucket_start + 3600
            hour_label = _dt.datetime.fromtimestamp(bucket_start).strftime("%Y-%m-%dT%H:00")
            # requests count
            cnt_req = conn.execute("SELECT COUNT(*) FROM traces WHERE created_at >= ? AND created_at < ?", (bucket_start, bucket_end)).fetchone()[0]
            cnt_eval = conn.execute("SELECT COUNT(*) FROM evaluations WHERE created_at >= ? AND created_at < ?", (bucket_start, bucket_end)).fetchone()[0]
            # avg latency in bucket
            row_lat = conn.execute("SELECT AVG(latency_ms) FROM traces WHERE created_at >= ? AND created_at < ? AND latency_ms IS NOT NULL", (bucket_start, bucket_end)).fetchone()
            avg_lat = round(float(row_lat[0]), 2) if row_lat[0] is not None else 0
            # avg rating in bucket
            row_rat = conn.execute("SELECT AVG(rating) FROM evaluations WHERE created_at >= ? AND created_at < ? AND rating IS NOT NULL", (bucket_start, bucket_end)).fetchone()
            avg_rat = round(float(row_rat[0]), 2) if row_rat[0] is not None else 0
            buckets.append({
                "hour": hour_label,
                "requests": cnt_req,
                "evaluations": cnt_eval,
                "avg_latency": avg_lat,
                "avg_rating": avg_rat,
            })
        return buckets
    finally:
        conn.close()


def export_evaluations(min_rating=None, max_rating=None, tags=None, model=None, date_from=None, date_to=None, format="jsonl") -> str:
    """Returns JSONL string or CSV string of filtered evaluations."""
    init_db()
    conn = get_db()
    try:
        where_clauses: list[str] = []
        params: list[Any] = []
        if min_rating is not None:
            where_clauses.append("rating >= ?")
            params.append(min_rating)
        if max_rating is not None:
            where_clauses.append("rating <= ?")
            params.append(max_rating)
        if model is not None:
            where_clauses.append("model = ?")
            params.append(model)
        if tags is not None:
            # tags can be comma-separated string or list
            if isinstance(tags, str):
                tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            elif isinstance(tags, list):
                tag_list = tags
            else:
                tag_list = []
            for t in tag_list:
                where_clauses.append("tags LIKE ?")
                params.append(f'%"{t}"%')
        if date_from is not None:
            # accept timestamp float or ISO string
            try:
                ts_from = float(date_from)
            except Exception:
                try:
                    import datetime as _dt
                    ts_from = _dt.datetime.fromisoformat(str(date_from)).timestamp()
                except Exception:
                    ts_from = None
            if ts_from is not None:
                where_clauses.append("created_at >= ?")
                params.append(ts_from)
        if date_to is not None:
            try:
                ts_to = float(date_to)
            except Exception:
                try:
                    import datetime as _dt
                    ts_to = _dt.datetime.fromisoformat(str(date_to)).timestamp()
                except Exception:
                    ts_to = None
            if ts_to is not None:
                where_clauses.append("created_at <= ?")
                params.append(ts_to)
        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        cur = conn.execute(f"SELECT * FROM evaluations{where_sql} ORDER BY created_at DESC", params)
        rows = [_eval_row_to_dict(r) for r in cur.fetchall()]

        if format == "csv":
            import csv
            import io
            output = io.StringIO()
            if not rows:
                # header only
                writer = csv.DictWriter(output, fieldnames=["id","request_id","chat_id","message_id","user_id","model","user_query","response","rating","thumbs","comment","tags","latency_ms","created_at","updated_at"])
                writer.writeheader()
                return output.getvalue()
            # flatten tags as JSON string for CSV
            fieldnames = list(rows[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                # ensure tags is json string for CSV readability
                rc = dict(r)
                if isinstance(rc.get("tags"), list):
                    rc["tags"] = json.dumps(rc["tags"], ensure_ascii=False)
                writer.writerow(rc)
            return output.getvalue()
        else:
            # jsonl
            lines = [json.dumps(r, ensure_ascii=False) for r in rows]
            return "\n".join(lines)
    finally:
        conn.close()
