#!/usr/bin/env python3
"""Probe the knowledge-base version that is *actually* live vs the one the repo pins.

Three independent views are collected and compared:

``actual``   What is physically in the Postgres ``kb_manager`` database
             (``chunks`` / ``documents`` counts, embedding model, last completed
             ``ingestion_jobs`` row).
``served``   What the KB API on :8000 claims it is serving
             (``/health`` counts + ``/registry/api/active`` manifest, pack pins
             and the DVC snapshot pin written to ``packs/dvc_snapshot.json``).
``expected`` What the checked-out code says production *should* be
             (``kb-source/.dvc_pins/current.txt`` for the newest corpus and
             ``processed.txt`` / ``processed.json`` for the exported snapshot).

Every field that cannot be determined is emitted as ``null`` and the reason is
listed in ``unknown`` — the dashboard renders "unknown" rather than a fake
number.

The column/endpoint names here mirror the real implementation in
``components/knowledgebase``; do not rename them without re-reading:

* tables ``chunks``, ``documents``, ``ingestion_jobs``, ``entity_lists``
  → ``kb_manager/models/database.py``
* ``GET /health`` (``chunk_count``, ``doc_count``, ``db_mode``, ``reranker_ok``)
  → ``kb_manager/web/app.py``
* ``GET /registry/api/active`` (``manifest``, ``pins``, ``dvc``)
  → ``kb_manager/web/routes/registry.py``
* ``IndexManifest`` schema → ``contracts/index_manifest.schema.json``
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "kb-version/v1"
DEFAULT_KB_API = "http://127.0.0.1:8000"
DEFAULT_DB_URL = "postgresql://postgres:postgres@127.0.0.1:5432/kb_manager"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _unknown(field: str, reason: str, unknowns: list[dict[str, str]]) -> None:
    """Record a field we could not read so the UI can say 'unknown' honestly."""
    unknowns.append({"field": field, "reason": reason})


def _http_json(url: str, timeout: float = 8.0) -> dict[str, Any] | None:
    """GET a JSON document, returning ``None`` on any failure (never raises)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 - loopback only
            raw = resp.read().decode("utf-8", "replace")
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        return None


def _run(cmd: list[str], timeout: float = 20.0) -> tuple[int, str]:
    """Run a command and return ``(returncode, stdout)``; never raises."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, (proc.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        return 127, ""


# --------------------------------------------------------------------------- #
# Postgres access (layered fallbacks, all read-only)
# --------------------------------------------------------------------------- #
COUNT_SQL = {
    "chunks": "SELECT count(*) FROM chunks",
    "documents": "SELECT count(*) FROM documents",
    "entity_lists": "SELECT count(*) FROM entity_lists",
    "embedded_chunks": "SELECT count(*) FROM chunks WHERE embedding IS NOT NULL",
}

MODEL_SQL = (
    "SELECT embedding_model || '|' || count(*) AS model_chunks FROM chunks "
    "WHERE embedding_model IS NOT NULL GROUP BY embedding_model ORDER BY count(*) DESC"
)

LAST_JOB_SQL = (
    "SELECT job_type || '|' || status || '|' || documents_ok || '|' || chunks_total "
    "|| '|' || coalesce(to_char(completed_at, 'YYYY-MM-DD\"T\"HH24:MI:SSOF'), '') "
    "FROM ingestion_jobs ORDER BY created_at DESC LIMIT 1"
)

BASE_TABLE_SQL = (
    "SELECT coalesce(sum(n_live_tup), 0) FROM pg_stat_user_tables "
    "WHERE relname IN ('chunks','documents','entity_lists')"
)


def _psql_query(sql: str, db_url: str, psql_bin: str) -> str | None:
    """Query with the ``psql`` client. Returns a single scalar string."""
    broken = _split_db_url(db_url)
    if not broken:
        return None
    env = dict(os.environ, PGPASSWORD=broken["password"])
    rc, out = _run(
        [
            psql_bin,
            "-h", broken["host"],
            "-p", broken["port"],
            "-U", broken["user"],
            "-d", broken["database"],
            "-tAc", sql,
        ],
        timeout=20,
    )
    if rc != 0 or not out:
        return None
    return out.splitlines()[0].strip()


def _find_pg_container(db_url: str) -> tuple[str, dict[str, str]] | None:
    """Locate a postgres container that holds the requested database.

    Returns ``(container, broken_url)`` or ``None``. The published-port match is
    tried first (fast path). When the caller's URL points at a port nothing
    publishes — e.g. probing ``127.0.0.1:5432`` on the dev compose host where
    postgres is published on ``15432`` — every ``*->5432`` container is probed
    for the target database name instead, so the same code works on both the
    GPU host (host postgres on 5432) and the laptop compose stack.
    """
    if shutil.which("docker") is None:
        return None
    broken = _split_db_url(db_url)
    if not broken:
        return None
    rc, containers = _run(["docker", "ps", "--format", "{{.Names}}\t{{.Ports}}"], timeout=15)
    if rc != 0 or not containers:
        return None

    candidates: list[str] = []
    target = f":{broken['port']}->5432"
    for line in containers.splitlines():
        if "\t" not in line:
            continue
        name, ports = line.split("\t", 1)
        if target in ports:
            candidates.insert(0, name)
        elif "->5432" in ports:
            candidates.append(name)
    for name in candidates:
        rc, out = _run(
            [
                "docker", "exec", name,
                "psql", "-U", broken["user"], "-d", "postgres", "-tAc",
                "SELECT 1 FROM pg_database WHERE datname = "
                f"'{broken['database']}'",
            ],
            timeout=15,
        )
        if rc == 0 and out.strip() == "1":
            return name, broken
    return None


def _psql_via_docker(sql: str, db_url: str) -> tuple[str, str] | None:
    """Query through ``docker exec`` against a postgres container.

    Returns ``(container, scalar)``. Finds a container whose published ports
    include the target DB port, so it works on the dev compose stack
    (15432) as well as a host postgres (5432).
    """
    hit = _find_pg_container(db_url)
    if hit is None:
        return None
    chosen, broken = hit
    rc, out = _run(
        [
            "docker", "exec", chosen,
            "psql", "-U", broken["user"], "-d", broken["database"], "-tAc", sql,
        ],
        timeout=20,
    )
    if rc != 0 or not out:
        return None
    return chosen, out.splitlines()[0].strip()


def _split_db_url(db_url: str) -> dict[str, str] | None:
    """Minimal postgres URL splitter (no external deps)."""
    url = (db_url or "").replace("postgresql+asyncpg://", "postgresql://")
    if not url.startswith("postgresql://"):
        return None
    body = url[len("postgresql://"):]
    if "@" in body:
        creds, hostpart = body.rsplit("@", 1)
        user, _, password = creds.partition(":")
    else:
        user, password = "postgres", ""
        hostpart = body
    database = ""
    if "/" in hostpart:
        hostpart, database = hostpart.split("/", 1)
        database = database.split("?", 1)[0]
    host, _, port = hostpart.partition(":")
    return {
        "user": user or "postgres",
        "password": password,
        "host": host or "127.0.0.1",
        "port": port or "5432",
        "database": database or "kb_manager",
    }


def _scalar(sql: str, db_url: str, psql_bin: str | None) -> tuple[str | None, str]:
    """Fetch one scalar via psql → docker → python driver. Returns (value, method)."""
    if psql_bin:
        value = _psql_query(sql, db_url, psql_bin)
        if value is not None:
            return value, "psql"
    docker_hit = _psql_via_docker(sql, db_url)
    if docker_hit is not None:
        container, value = docker_hit
        return value, f"docker:{container}"
    value = _psycopg_scalar(sql, db_url)
    if value is not None:
        return value, "psycopg2"
    return None, "unavailable"


def _rows(sql: str, db_url: str, psql_bin: str | None) -> list[str]:
    """Fetch *all* rows of a single-column query (multi-line safe).

    ``_scalar`` keeps only the first line, which is correct for ``count(*)`` but
    truncates GROUP BY results. This variant keeps every line.
    """
    broken = _split_db_url(db_url)
    if psql_bin and broken:
        env = dict(os.environ, PGPASSWORD=broken["password"])
        rc, out = _run(
            [
                psql_bin,
                "-h", broken["host"],
                "-p", broken["port"],
                "-U", broken["user"],
                "-d", broken["database"],
                "-tAc", sql,
            ],
            timeout=20,
        )
        if rc == 0 and out:
            return [line.strip() for line in out.splitlines() if line.strip()]
    hit = _find_pg_container(db_url)
    if hit is not None:
        name, url = hit
        rc, out = _run(
            [
                "docker", "exec", name,
                "psql", "-U", url["user"], "-d", url["database"], "-tAc", sql,
            ],
            timeout=20,
        )
        if rc == 0 and out:
            return [ln.strip() for ln in out.splitlines() if ln.strip()]
    value = _psycopg_scalar(sql, db_url)
    return [ln.strip() for ln in value.splitlines() if ln.strip()] if value else []


def _psycopg_scalar(sql: str, db_url: str) -> str | None:
    """Last-resort direct driver access (only if psycopg2/asyncpg is installed)."""
    sync_url = (db_url or "").replace("postgresql+asyncpg://", "postgresql://")
    try:
        import psycopg2  # type: ignore[import-not-found]
    except Exception:
        return None
    try:
        conn = psycopg2.connect(sync_url)
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                row = cur.fetchone()
                return "" if row is None or row[0] is None else str(row[0])
        finally:
            conn.close()
    except Exception:
        return None


def _as_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# collectors
# --------------------------------------------------------------------------- #
def collect_actual(db_url: str, psql_bin: str | None, unknowns: list[dict[str, str]]) -> dict[str, Any]:
    """Read the live database state."""
    broken = _split_db_url(db_url)
    out: dict[str, Any] = {
        "source": "postgres",
        # Never publish credentials: the report JSON lands in a public repo.
        "db_url": (
            {
                "user": broken["user"],
                "password": "REDACTED" if broken.get("password") else "",
                "host": broken["host"],
                "port": broken["port"],
                "database": broken["database"],
            }
            if broken
            else None
        ),
        "chunk_count": None,
        "document_count": None,
        "entity_list_count": None,
        "embedded_chunk_count": None,
        "embedding_models": [],
        "last_ingestion_job": None,
        "method": None,
    }
    methods: set[str] = set()
    for field, sql in COUNT_SQL.items():
        value, method = _scalar(sql, db_url, psql_bin)
        methods.add(method)
        key = {
            "chunks": "chunk_count",
            "documents": "document_count",
            "entity_lists": "entity_list_count",
            "embedded_chunks": "embedded_chunk_count",
        }[field]
        out[key] = _as_int(value)
        if out[key] is None:
            _unknown(f"actual.{key}", f"db unavailable ({method})", unknowns)

    models_raw = _rows(MODEL_SQL, db_url, psql_bin)
    for line in models_raw:
        model, _, count = line.partition("|")
        out["embedding_models"].append(
            {"model": model.strip(), "chunks": _as_int(count)}
        )
    if not out["embedding_models"] and out["chunk_count"]:
        _unknown("actual.embedding_models", "no embedding_model values in chunks", unknowns)

    job_raw, _ = _scalar(LAST_JOB_SQL, db_url, psql_bin)
    if job_raw:
        parts = job_raw.split("|")
        out["last_ingestion_job"] = {
            "job_type": parts[0] if len(parts) > 0 else None,
            "status": parts[1] if len(parts) > 1 else None,
            "documents_ok": _as_int(parts[2]) if len(parts) > 2 else None,
            "chunks_total": _as_int(parts[3]) if len(parts) > 3 else None,
            "completed_at": parts[4] if len(parts) > 4 and parts[4] else None,
        }
    else:
        _unknown("actual.last_ingestion_job", "no ingestion_jobs rows readable", unknowns)

    usable = sorted(m for m in methods if m not in ("unavailable",))
    out["method"] = usable[0] if usable else "unavailable"
    return out


def collect_served(kb_api: str, unknowns: list[dict[str, str]]) -> dict[str, Any]:
    """Read what the KB API reports it is serving."""
    out: dict[str, Any] = {
        "source": "kb-api",
        "api": kb_api,
        "reachable": False,
        "status": None,
        "db_mode": None,
        "chunk_count": None,
        "document_count": None,
        "reranker_ok": None,
        "manifest_id": None,
        "manifest": None,
        "packs": {},
        "dvc_pin": None,
        "corpus_date": None,
    }
    health = _http_json(f"{kb_api}/health")
    if health is None:
        _unknown("served", f"{kb_api}/health unreachable", unknowns)
        return out
    out["reachable"] = True
    out["status"] = health.get("status")
    out["db_mode"] = health.get("db_mode")
    out["chunk_count"] = _as_int(health.get("chunk_count"))
    out["document_count"] = _as_int(health.get("doc_count"))
    out["reranker_ok"] = health.get("reranker_ok")

    active = _http_json(f"{kb_api}/registry/api/active")
    if active is None:
        _unknown("served.manifest", f"{kb_api}/registry/api/active unreachable", unknowns)
        return out

    manifest = active.get("manifest")
    if isinstance(manifest, dict):
        out["manifest"] = manifest
        out["manifest_id"] = manifest.get("manifest_id")
        corpus = manifest.get("corpus") or {}
        out["corpus_date"] = corpus.get("corpus_date") or corpus.get("dvc_rev")
    else:
        _unknown(
            "served.manifest",
            "no active IndexManifest "
            "(POST /registry/api/manifests/build?activate=true never run on this host)",
            unknowns,
        )

    pins = active.get("pins")
    if isinstance(pins, dict) and pins:
        out["packs"] = {str(k): str(v) for k, v in pins.items()}
    else:
        _unknown("served.packs", "registry returned no active pins", unknowns)

    dvc = active.get("dvc")
    if isinstance(dvc, dict) and dvc:
        out["dvc_pin"] = dvc
        if out["corpus_date"] is None:
            out["corpus_date"] = dvc.get("corpus_date")
        if out["chunk_count"] is None:
            out["chunk_count"] = _as_int(dvc.get("chunks"))
        if out["document_count"] is None:
            out["document_count"] = _as_int(dvc.get("documents"))
    else:
        _unknown(
            "served.dvc_pin",
            "packs/dvc_snapshot.json not present in the KB container",
            unknowns,
        )
    return out


def _read_text(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
        return text or None
    except OSError:
        return None


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def collect_expected(
    repo_root: Path,
    unknowns: list[dict[str, str]],
    kb_source_override: Path | None = None,
) -> dict[str, Any]:
    """Read the version this checkout pins as production truth."""
    out: dict[str, Any] = {
        "source": "repo-pin",
        "repo_root": str(repo_root),
        "corpus_pin": None,
        "processed_corpus": None,
        "manifest_id": None,
        "chunk_count": None,
        "document_count": None,
        "entity_list_count": None,
        "embedding_model": None,
        "packs": {},
        "kb_git_head": None,
        "kb_branch": None,
        "pin_details": {},
        "corpus_history": [],
    }
    kb_source = kb_source_override or (
        repo_root / "components" / "knowledgebase" / "kb-source"
    )
    pins_dir = kb_source / ".dvc_pins"

    current = _read_text(pins_dir / "current.txt")
    if current is not None:
        out["corpus_pin"] = current
    else:
        _unknown(
            "expected.corpus_pin",
            f"missing {pins_dir / 'current.txt'}",
            unknowns,
        )

    processed = _read_text(pins_dir / "processed.txt")
    if processed is not None:
        out["processed_corpus"] = processed
    else:
        _unknown(
            "expected.processed_corpus",
            f"missing {pins_dir / 'processed.txt'}",
            unknowns,
        )

    details = _read_json(pins_dir / "processed.json")
    if details is not None:
        out["pin_details"] = details
        out["manifest_id"] = details.get("manifest_id")
        out["chunk_count"] = _as_int(details.get("chunks"))
        out["document_count"] = _as_int(details.get("documents"))
        out["entity_list_count"] = _as_int(details.get("entity_lists"))
        out["embedding_model"] = details.get("embedding_model")
        packs = details.get("packs")
        if isinstance(packs, dict):
            out["packs"] = {str(k): str(v) for k, v in packs.items()}
        if out["processed_corpus"] is None:
            out["processed_corpus"] = details.get("corpus_date")
    else:
        _unknown(
            "expected.processed",
            f"missing {pins_dir / 'processed.json'} (no DVC snapshot exported here)",
            unknowns,
        )

    kb_repo = repo_root / "components" / "knowledgebase"
    if (kb_repo / ".git").exists():
        rc, head = _run(["git", "-C", str(kb_repo), "rev-parse", "--short", "HEAD"], timeout=10)
        out["kb_git_head"] = (head or None) if rc == 0 else None
        rc, branch = _run(["git", "-C", str(kb_repo), "rev-parse", "--abbrev-ref", "HEAD"], timeout=10)
        out["kb_branch"] = (branch or None) if rc == 0 else None
        if out["kb_git_head"] is None:
            _unknown("expected.kb_git_head", "git rev-parse HEAD failed in KB checkout", unknowns)
        out["corpus_history"] = _corpus_history(kb_repo, "kb-source/.dvc_pins")
    else:
        _unknown(
            "expected.kb_git_head",
            "components/knowledgebase not checked out (git submodule not initialised)",
            unknowns,
        )
        # Fall back to whichever repo actually owns the kb-source checkout so the
        # corpus-change history still works when only kb-source is present.
        if (kb_source / ".git").exists():
            out["corpus_history"] = _corpus_history(kb_source, ".dvc_pins")
        elif (kb_source.parent / ".git").exists():
            out["corpus_history"] = _corpus_history(kb_source.parent, "kb-source/.dvc_pins")
    return out


def _corpus_history(git_root: Path, pins_rel: str) -> list[dict[str, Any]]:
    """When did the pinned corpus change? One entry per commit touching the pin."""
    current_path = f"{pins_rel}/current.txt"
    processed_path = f"{pins_rel}/processed.txt"
    rc, raw = _run(
        [
            "git", "-C", str(git_root), "log",
            "--format=%H%x1f%aI%x1f%s",
            "-n", "40",
            "--", current_path, processed_path,
        ],
        timeout=15,
    )
    if rc != 0 or not raw:
        return []
    history: list[dict[str, Any]] = []
    for line in raw.splitlines():
        sha, _, rest = line.partition("\x1f")
        iso, _, subject = rest.partition("\x1f")
        corpus = None
        rc_c, out_c = _run(
            ["git", "-C", str(git_root), "show", f"{sha}:{current_path}"], timeout=10
        )
        if rc_c == 0 and out_c:
            corpus = out_c.splitlines()[0].strip()
        else:
            rc_p, out_p = _run(
                ["git", "-C", str(git_root), "show", f"{sha}:{processed_path}"], timeout=10
            )
            if rc_p == 0 and out_p:
                corpus = out_p.splitlines()[0].strip()
        history.append(
            {
                "sha": sha[:10],
                "when": iso or None,
                "subject": subject or None,
                "corpus": corpus,
            }
        )
    return history


def compare(actual: dict[str, Any], served: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """Compute the match/mismatch verdict between DB, API and repo pin."""
    checks: list[dict[str, Any]] = []

    def check(name: str, left: Any, right: Any, note: str) -> None:
        comparable = left is not None and right is not None
        checks.append(
            {
                "check": name,
                "actual": left,
                "expected": right,
                "match": (left == right) if comparable else None,
                "note": note,
            }
        )

    check(
        "chunk_count",
        actual.get("chunk_count"),
        expected.get("chunk_count"),
        "chunks in Postgres vs chunks in the DVC pin",
    )
    check(
        "document_count",
        actual.get("document_count"),
        expected.get("document_count"),
        "documents in Postgres vs documents in the DVC pin",
    )
    check(
        "corpus_date",
        served.get("corpus_date"),
        expected.get("processed_corpus"),
        "corpus the running API serves vs the exported snapshot pin",
    )
    check(
        "chunks_in_db_vs_dvc_pin",
        actual.get("chunk_count"),
        (served.get("dvc_pin") or {}).get("chunks"),
        "chunks in Postgres vs the DVC snapshot pin the API advertises",
    )
    check(
        "chunks_vs_api_health",
        actual.get("chunk_count"),
        served.get("chunk_count"),
        "chunks in Postgres vs chunk_count from /health",
    )
    check(
        "packs",
        served.get("packs") or None,
        expected.get("packs") or None,
        "active registry pack versions served vs pinned",
    )

    comparable = [c for c in checks if c["match"] is not None]
    mismatches = [c["check"] for c in comparable if c["match"] is False]
    if not comparable:
        status = "unknown"
    elif mismatches:
        status = "mismatch"
    else:
        status = "match"

    # The newest corpus available in the repo is a *forward-looking* signal: if
    # the DB/API has not caught up with it, production is behind on ingestion.
    latest_corpus = expected.get("corpus_pin")
    live_corpus = served.get("corpus_date") or expected.get("processed_corpus")
    corpus_lagging = (
        bool(latest_corpus and live_corpus and latest_corpus != live_corpus)
        if latest_corpus and live_corpus
        else None
    )

    return {
        "status": status,
        "checks": checks,
        "mismatches": mismatches,
        "latest_available_corpus": latest_corpus,
        "live_corpus": live_corpus,
        "corpus_lagging": corpus_lagging,
    }


def build_report(
    repo_root: Path,
    db_url: str,
    kb_api: str,
    kb_source: Path | None = None,
) -> dict[str, Any]:
    """Assemble the full kb-version/v1 record."""
    unknowns: list[dict[str, str]] = []
    psql_bin = shutil.which("psql")
    if psql_bin is None:
        _unknown("actual", "psql client not installed — trying docker/driver", unknowns)

    actual = collect_actual(db_url, psql_bin, unknowns)
    served = collect_served(kb_api, unknowns)
    expected = collect_expected(repo_root, unknowns, kb_source)
    verdict = compare(actual, served, expected)

    return {
        "schema_version": SCHEMA_VERSION,
        "actual": actual,
        "served": served,
        "expected": expected,
        "verdict": verdict,
        "unknown": unknowns,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe live KB version (DB + API) vs the pinned expected version",
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--db-url", default=os.environ.get("KB_DB_URL", DEFAULT_DB_URL))
    parser.add_argument("--kb-api", default=os.environ.get("KB_BASE_URL", DEFAULT_KB_API))
    parser.add_argument(
        "--kb-source",
        type=Path,
        default=None,
        help="kb-source checkout holding .dvc_pins/ (default: <repo-root>/components/knowledgebase/kb-source)",
    )
    parser.add_argument("--out", type=Path, default=None, help="Write JSON here (default: stdout)")
    parser.add_argument("--quiet", action="store_true", help="Do not print a summary")
    args = parser.parse_args(argv)

    report = build_report(
        args.repo_root.resolve(),
        args.db_url,
        args.kb_api.rstrip("/"),
        args.kb_source.resolve() if args.kb_source else None,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    if not args.quiet:
        print(payload if not args.out else f"kb_version -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
