#!/usr/bin/env python3
"""Publish one health-check run into the Work_RAG_HealthCheck GitHub Pages repo.

Layout written to the repo root (all paths relative, so Pages serves them):

    index.html                       static dashboard (no build step)
    .nojekyll                        keep _underscore_ and dot paths
    runs/<RUN_ID>.json               one compact record per run (never logs)
    runs/index.json                  manifest rebuilt from the directory listing
    latest/run.json                  newest record (stable URL)
    latest/dashboard.html            newest per-run detail page (from the report)
    latest/screenshots/*.png         newest screenshots only
    logs/<RUN_ID>/*                  raw logs, retained for the last N runs

Design constraints handled here
-------------------------------
* Append-only on a single ``main`` branch. No per-run branches (the old script
  created ``ops/gpu-recover-<id>`` and the repo accumulated ~8 orphan branches
  with no ``main`` at all).
* ``runs/index.json`` is regenerated from the directory listing on every publish,
  so a bad merge or a dropped file self-heals on the next run.
* Concurrent pushes from the laptop and the GPU host are reconciled with
  ``git pull --rebase`` in a retry loop. Force-push is never used.
* Retention: only the newest ``--keep-logs`` runs keep a ``logs/`` tree; older
  runs keep their JSON record only, so repo growth stays dominated by small
  records rather than 9 MB log bundles.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

RUN_SCHEMA_VERSION = "health-run/v1"
INDEX_SCHEMA_VERSION = "health-index/v1"
DEFAULT_KEEP_LOGS = 30
SITE_TEMPLATE = Path(__file__).resolve().parent / "site" / "index.html"

# Port -> service identity. Mirrors the service table in AGENTS.md and the
# PORTS list in gpu_full_recover_report.sh.
SERVICE_PORTS: dict[str, str] = {
    "18000": "gemma",
    "9000": "manager",
    "8000": "kb",
    "8200": "guardrails",
    "8100": "orchestrator",
    "3000": "trace-collector",
    "3001": "langfuse",
    "13000": "webui",
    "8085": "jenkins",
    "8010": "service-8010",
    "8001": "service-8001",
    "8002": "service-8002",
    "8003": "service-8003",
}

# Services that decide the overall verdict. Auxiliary ports (langfuse UI, empty
# 80xx placeholders) must not flip a run to DEGRADED.
CORE_SERVICES = ("kb", "guardrails", "orchestrator", "webui")


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def read_kv(path: Path) -> dict[str, str]:
    """Parse the ``key=value`` files the report script writes."""
    out: dict[str, str] = {}
    for line in read_text(path).splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip():
            out[key.strip()] = value.strip()
    return out


def classify_http(code: str) -> str:
    """Map an HTTP status code string to up / degraded / down / no-data."""
    if not code or code in ("000", "---"):
        return "down"
    try:
        value = int(code)
    except ValueError:
        return "no-data"
    if 200 <= value < 400:
        return "up"
    if 400 <= value < 600:
        return "degraded"
    return "no-data"


# --------------------------------------------------------------------------- #
# extract the record from a report run directory
# --------------------------------------------------------------------------- #
def load_matrix(out_dir: Path) -> list[dict[str, Any]]:
    """Read ``curl/matrix.tsv`` (port, service, http_code, body_preview)."""
    matrix = out_dir / "curl" / "matrix.tsv"
    services: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in read_text(matrix).splitlines():
        if not line.strip() or line.startswith("port\t"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        port, name, code = parts[0].strip(), parts[1].strip(), parts[2].strip()
        preview = parts[3].strip() if len(parts) > 3 else ""
        key = port or name
        if key in seen:
            continue
        seen.add(key)
        services.append(
            {
                "name": SERVICE_PORTS.get(port, name or f"port-{port}"),
                "port": int(port) if port.isdigit() else None,
                "status": classify_http(code),
                "http_code": code or "000",
                "detail": preview[:180] or None,
            }
        )
    return services


def load_e2e(out_dir: Path) -> dict[str, Any]:
    """Read the E2E summary/score files the report script writes."""
    summary: list[dict[str, Any]] = []
    for line in read_text(out_dir / "e2e" / "summary.txt").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = line.split(" ", 1)[0]
        code = ""
        if "http=" in line:
            code = line.split("http=", 1)[1].split()[0]
        summary.append(
            {
                "test": name,
                "http_code": code or None,
                "passed": classify_http(code) == "up",
            }
        )
    score = read_kv(out_dir / "e2e" / "score.txt")
    passed = total = None
    raw = score.get("qa_pass", "")
    if "/" in raw:
        left, _, right = raw.partition("/")
        passed = int(left) if left.isdigit() else None
        total = int(right) if right.isdigit() else None
    return {
        "tests": summary,
        "passed": passed,
        "total": total,
        "kb_search_ok": next(
            (t["passed"] for t in summary if t["test"] == "kb_search"), None
        ),
    }


def load_gate(out_dir: Path) -> dict[str, Any]:
    """Read pass/fail markers the report script leaves on disk."""
    statuses: dict[str, str] = {}
    push_status = read_text(out_dir / "meta" / "push_status").strip()
    if push_status:
        statuses["push"] = "PASSED" if "=1" in push_status else "FAILED"
    return statuses


def load_links(out_dir: Path, run_id: str, keep_logs: bool) -> dict[str, Any]:
    """Build the relative links a dashboard row needs."""
    screenshots: list[str] = []
    shot_dir = out_dir / "screenshots"
    if shot_dir.is_dir():
        screenshots = sorted(p.name for p in shot_dir.glob("*.png"))
    links: dict[str, Any] = {
        "detail": f"latest/dashboard.html",
        "logs": f"logs/{run_id}/" if keep_logs else None,
        "screenshots": screenshots,
        "screenshots_dir": f"latest/screenshots" if screenshots else None,
        "record": f"runs/{run_id}.json",
    }
    return links


def run_id_time(run_id: str) -> datetime | None:
    """Extract the UTC timestamp embedded in ``YYYYMMDDTHHMMSSZ-<machine>``."""
    head = run_id.split("-", 1)[0]
    try:
        return datetime.strptime(head, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def build_run_record(
    *,
    out_dir: Path,
    run_id: str,
    machine: str,
    machine_type: str,
    mode: str,
    status: str,
    kb_version: dict[str, Any] | None,
    origin: str = "report",
    now: datetime | None = None,
    keep_detail: bool = True,
) -> dict[str, Any]:
    """Assemble a ``health-run/v1`` record from the report artifacts."""
    # Prefer the timestamp baked into the run id: it is when the checks ran,
    # which is what the heatmap plots. Publishing can lag by minutes.
    now = now or run_id_time(run_id) or utc_now()
    services = load_matrix(out_dir)
    e2e = load_e2e(out_dir)
    meta = read_kv(out_dir / "meta" / "host_metadata.txt")

    core_down = [
        s["name"] for s in services if s["name"] in CORE_SERVICES and s["status"] != "up"
    ]
    core_count = sum(1 for s in services if s["name"] in CORE_SERVICES)

    # The report script decides STATUS from the health matrix + QA; trust it when
    # supplied, otherwise derive an equivalent verdict from the core services.
    if not status:
        if core_down and len(core_down) == core_count:
            status = "DOWN"
        elif core_down:
            status = "DEGRADED"
        else:
            status = "HEALTHY"

    kb_compact: dict[str, Any] | None = None
    if kb_version:
        actual = kb_version.get("actual") or {}
        served = kb_version.get("served") or {}
        expected = kb_version.get("expected") or {}
        verdict = kb_version.get("verdict") or {}
        kb_compact = {
            "verdict": verdict.get("status"),
            "mismatches": verdict.get("mismatches") or [],
            "checks": verdict.get("checks") or [],
            "chunks_in_db": actual.get("chunk_count"),
            "documents_in_db": actual.get("document_count"),
            "chunks_in_pin": (served.get("dvc_pin") or {}).get("chunks")
            or expected.get("chunk_count"),
            "corpus_live": verdict.get("live_corpus"),
            "corpus_latest": verdict.get("latest_available_corpus"),
            "corpus_lagging": verdict.get("corpus_lagging"),
            "manifest_id": served.get("manifest_id") or expected.get("manifest_id"),
            "packs": served.get("packs") or {},
            "embedding_models": actual.get("embedding_models") or [],
            "last_ingestion_job": actual.get("last_ingestion_job"),
            "unknown": [u.get("field") for u in (kb_version.get("unknown") or [])],
        }

    return {
        "schema_version": RUN_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": iso(now),
        "machine": machine,
        "machine_type": machine_type,
        "host": meta.get("hostname") or machine,
        "mode": mode or meta.get("detected_mode") or "unknown",
        "origin": origin,
        "status": status,
        "core_services_down": core_down,
        "services": services,
        "e2e": e2e,
        "gate": load_gate(out_dir),
        "kb": kb_compact,
        "links": {
            # Per-run detail page lives inside the retained logs dir so its
            # ../screenshots/ links resolve; falls back to the newest snapshot.
            "detail": (
                f"logs/{run_id}/dashboard.html" if keep_detail else "latest/dashboard.html"
            ),
            "record": f"runs/{run_id}.json",
        },
    }


# --------------------------------------------------------------------------- #
# index
# --------------------------------------------------------------------------- #
def compact_entry(record: dict[str, Any]) -> dict[str, Any]:
    """One row of ``runs/index.json`` — deliberately small (never embeds logs)."""
    kb = record.get("kb") or {}
    return {
        "id": record.get("run_id"),
        "ts": record.get("generated_at"),
        "machine": record.get("machine"),
        "machine_type": record.get("machine_type"),
        "status": record.get("status"),
        "mode": record.get("mode"),
        "origin": record.get("origin"),
        "services": {
            s.get("name"): s.get("status") for s in (record.get("services") or [])
        },
        "qa": (
            f"{record['e2e'].get('passed')}/{record['e2e'].get('total')}"
            if (record.get("e2e") or {}).get("total") is not None
            else None
        ),
        "kb_verdict": kb.get("verdict"),
        "kb_chunks": kb.get("chunks_in_db"),
        "kb_corpus": kb.get("corpus_live"),
        "kb_lagging": kb.get("corpus_lagging"),    }


def rebuild_index(root: Path) -> dict[str, Any]:
    """Regenerate ``runs/index.json`` from what is actually on disk.

    Directory-listing driven so a failed merge or a deleted file is repaired by
    the next publish instead of leaving a stale manifest behind.
    """
    runs_dir = root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    corrupt: list[str] = []
    for path in sorted(runs_dir.glob("*.json")):
        if path.name == "index.json":
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            corrupt.append(path.name)
            continue
        if not isinstance(record, dict) or record.get("schema_version") != RUN_SCHEMA_VERSION:
            corrupt.append(path.name)
            continue
        entries.append(compact_entry(record))

    entries.sort(key=lambda e: (e.get("ts") or "", e.get("id") or ""))
    machines = sorted({e.get("machine") for e in entries if e.get("machine")})
    index = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "generated_at": iso(utc_now()),
        "count": len(entries),
        "machines": machines,
        "first_run": entries[0]["ts"] if entries else None,
        "last_run": entries[-1]["ts"] if entries else None,
        "corrupt_records": corrupt,
        "entries": entries,
    }
    (runs_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return index


# --------------------------------------------------------------------------- #
# latest/ + logs/ retention
# --------------------------------------------------------------------------- #
def write_latest(root: Path, out_dir: Path, record: dict[str, Any], detail_rel: str | None) -> None:
    """Refresh the ``latest/`` snapshot (record, detail redirect, report).

    Screenshots are *not* duplicated here: they live once under
    ``logs/<run_id>/screenshots/``. ``latest/dashboard.html`` is a tiny redirect
    to that run's detail page, which keeps the stable URL working without
    doubling the PNG payload on every publish.
    """
    latest = root / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    (latest / "run.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report = out_dir / "REPORT.md"
    if report.is_file():
        shutil.copy2(report, latest / "REPORT.md")

    # Remove any screenshots dir left by an older publisher version.
    stale = latest / "screenshots"
    if stale.is_dir():
        shutil.rmtree(stale, ignore_errors=True)

    target = detail_rel or "dashboard.html"
    if detail_rel:
        (latest / "dashboard.html").write_text(
            "<!DOCTYPE html>\n"
            '<html lang="en"><head><meta charset="utf-8">\n'
            f'<meta http-equiv="refresh" content="0; url=../{target}">\n'
            f'<link rel="canonical" href="../{target}">\n'
            f"<title>Latest run — {record.get('run_id')}</title>\n"
            "</head><body>\n"
            f'<p>Redirecting to the latest run detail page… '
            f'<a href="../{target}">open</a></p>\n'
            "</body></html>\n",
            encoding="utf-8",
        )
    else:
        detail = out_dir / "html" / "dashboard.html"
        if detail.is_file():
            shutil.copy2(detail, latest / "dashboard.html")


# Directories worth publishing as evidence. Everything else (container dumps,
# shell history, builds) stays local — those were ~90% of a 9.4 MB run and are
# exactly what made log retention untenable in git.
LOG_SUBDIRS = ("meta", "curl", "e2e", "kb", "logs", "restart")
LOG_FILES = ("REPORT.md", "run.log")

# Never publish these, even inside an allowed subdir. The monitoring repo is
# public, and shell history / verbose host logs are the one artifact that
# reliably contains credentials in a form sed redaction cannot catch (env
# exports split across continuation lines, aliases, tokens pasted inline).
LOG_EXCLUDE_NAMES = {
    "command_shutdown_reboot_user.log",
    "commands.txt",
    "bash_history.txt",
    "shell_history.txt",
    "docker_inspect.txt",
}
LOG_EXCLUDE_PREFIXES = ("host-", "env", "docker-env")
# The per-run detail page from the report is copied to ``logs/<run_id>/dashboard.html``
# so its ``../screenshots/`` links resolve inside the same run directory.
DETAIL_PAGE = Path("html") / "dashboard.html"
# Screenshots are the heaviest part of a run (~1.5 MB). They are retained for a
# shorter window than text logs so the repo does not grow by tens of MB/month.
SCREENSHOT_KEEP = 7


def _is_sensitive_name(name: str) -> bool:
    """True for artifacts that must never be published from a run directory."""
    if name in LOG_EXCLUDE_NAMES:
        return True
    return any(name.startswith(prefix) for prefix in LOG_EXCLUDE_PREFIXES)


def write_logs(root: Path, out_dir: Path, run_id: str, max_bytes: int = 2_000_000) -> int:
    """Copy the raw evidence for this run under ``logs/<run_id>/``.

    Returns the number of files written. Individual files are truncated to
    ``max_bytes`` so a runaway container log cannot bloat the repo.
    """
    dest = root / "logs" / run_id
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    written = 0

    def copy_capped(src: Path, target: Path) -> None:
        nonlocal written
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            size = src.stat().st_size
            if size <= max_bytes:
                shutil.copy2(src, target)
            else:
                with src.open("rb") as fh:
                    head = fh.read(max_bytes)
                with target.open("wb") as fh:
                    fh.write(head)
                    fh.write(b"\n\n[truncated by monitor publisher]\n")
            written += 1
        except OSError:
            pass

    for name in LOG_FILES:
        src = out_dir / name
        if src.is_file():
            copy_capped(src, dest / name)

    for sub in LOG_SUBDIRS:
        src_dir = out_dir / sub
        if not src_dir.is_dir():
            continue
        for src in sorted(src_dir.rglob("*")):
            if not src.is_file():
                continue
            if src.suffix in {".png", ".jpg", ".jpeg"}:
                continue  # screenshots are handled separately, with their own keep-window
            if _is_sensitive_name(src.name):
                # Redaction cannot reliably strip secrets out of shell history
                # and verbose host logs, so they simply never leave the host.
                continue
            copy_capped(src, dest / sub / src.relative_to(src_dir))

    # Per-run detail page + its screenshots, kept together so relative links work.
    # The report writes the page at html/dashboard.html using ../x links; once the
    # page sits at logs/<run>/dashboard.html the siblings are one level up, not two,
    # so strip exactly one "../" prefix.
    detail = out_dir / DETAIL_PAGE
    if detail.is_file():
        try:
            html = detail.read_text(encoding="utf-8", errors="replace")
            html = html.replace('src="../screenshots/', 'src="screenshots/')
            html = html.replace('href="../screenshots/', 'href="screenshots/')
            html = re.sub(r'((?:src|href)=")\.\./(?!screenshots/)', r"\1", html)
            (dest / "dashboard.html").write_text(html, encoding="utf-8")
            written += 1
        except OSError:
            pass
    shot_dir = out_dir / "screenshots"
    if shot_dir.is_dir():
        for png in sorted(shot_dir.glob("*.png")):
            copy_capped(png, dest / "screenshots" / png.name)

    return written


def prune_logs(root: Path, keep: int = DEFAULT_KEEP_LOGS) -> list[str]:
    """Delete ``logs/`` trees older than the newest ``keep`` runs."""
    logs_dir = root / "logs"
    if not logs_dir.is_dir():
        return []
    dirs = sorted((p for p in logs_dir.iterdir() if p.is_dir()), key=lambda p: p.name)
    removed: list[str] = []
    if keep <= 0 or len(dirs) <= keep:
        return removed
    for path in dirs[:-keep]:
        shutil.rmtree(path, ignore_errors=True)
        removed.append(path.name)
    return removed


def prune_screenshots(root: Path, keep: int = SCREENSHOT_KEEP) -> list[str]:
    """Drop per-run ``screenshots/`` dirs belonging to runs older than ``keep``.

    The run record and text logs survive; only the PNGs go, because they are
    ~100x larger than everything else per run.
    """
    logs_dir = root / "logs"
    if not logs_dir.is_dir():
        return []
    dirs = sorted((p for p in logs_dir.iterdir() if p.is_dir()), key=lambda p: p.name)
    pruned: list[str] = []
    if keep <= 0 or len(dirs) <= keep:
        return pruned
    for path in dirs[:-keep]:
        shot = path / "screenshots"
        if shot.is_dir():
            shutil.rmtree(shot, ignore_errors=True)
            pruned.append(path.name)
    return pruned


# --------------------------------------------------------------------------- #
# dashboard
# --------------------------------------------------------------------------- #
def render_site(root: Path) -> Path:
    """Copy the versioned dashboard template to the repo root."""
    target = root / "index.html"
    if SITE_TEMPLATE.is_file():
        shutil.copy2(SITE_TEMPLATE, target)
    elif not target.is_file():
        target.write_text(
            "<!doctype html><meta charset=utf-8><title>Health</title>"
            "<p>dashboard template missing</p>\n",
            encoding="utf-8",
        )
    (root / ".nojekyll").write_text("", encoding="utf-8")
    return target


# --------------------------------------------------------------------------- #
# git publish (rebase + retry, never force)
# --------------------------------------------------------------------------- #
def git(args: list[str], cwd: Path, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=check,
        timeout=180,
    )


def ensure_repo(repo: Path, remote: str, branch: str, no_push: bool) -> None:
    """Create or refresh the local clone of the monitoring repo.

    A brand-new local directory is cloned from the remote when ``branch``
    already exists there. Losing that history and starting from an orphan branch
    would make every later push non-fast-forward, and no amount of rebasing can
    reconcile unrelated histories — so the clone path matters, not just tidiness.
    """
    if not (repo / ".git").exists():
        repo.parent.mkdir(parents=True, exist_ok=True)
        if repo.exists():
            shutil.rmtree(repo)
        if remote:
            cloned = subprocess.run(
                ["git", "clone", "--quiet", "--branch", branch, remote, str(repo)],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if cloned.returncode == 0:
                git(["config", "http.version", "HTTP/1.1"], repo)
                git(["config", "http.postBuffer", "524288000"], repo)
                return
            # Remote branch missing (first ever publish) or clone failed: start
            # an orphan branch and let the first push create it.
            if repo.exists():
                shutil.rmtree(repo)
        repo.mkdir(parents=True, exist_ok=True)
        git(["init", "-q"], repo)
        if remote:
            git(["remote", "add", "origin", remote], repo)
        git(["-c", "advice.detachedHead=false", "checkout", "-B", branch], repo)
        return

    if remote:
        git(["remote", "remove", "origin"], repo)
        git(["remote", "add", "origin", remote], repo)
    git(["config", "http.version", "HTTP/1.1"], repo)
    git(["config", "http.postBuffer", "524288000"], repo)

    if no_push:
        return
    # Adopt whatever main currently is; a repo with no main yet is normal.
    if git(["fetch", "origin", branch], repo).returncode == 0:
        if git(["merge-base", "HEAD", "FETCH_HEAD"], repo).returncode == 0:
            git(["rebase", "--autostash", "FETCH_HEAD"], repo)
        else:
            # Local history is unrelated to the remote (an older publisher
            # initialised the repo instead of cloning it). Merge instead of
            # rebasing; derived files are regenerated after this call.
            git(
                ["-c", "commit.gpgsign=false", "merge", "--allow-unrelated-histories",
                 "--no-edit", "-X", "ours", "FETCH_HEAD"],
                repo,
            )


def absorb_remote(repo: Path, branch: str) -> tuple[bool, str]:
    """Pull the remote branch into the local one, related or not.

    Returns ``(ok, detail)``. Rebase is used when the histories share an
    ancestor; otherwise an allow-unrelated merge with ``-X ours`` wins the
    derived-file conflicts (``runs/index.json``, ``index.html``, ``latest/``),
    which are regenerated from the run records right after the merge.
    """
    fetch = git(["fetch", "origin", branch], repo)
    if fetch.returncode != 0:
        return False, f"fetch failed: {(fetch.stderr or '').strip()[:200]}"

    if git(["merge-base", "HEAD", "FETCH_HEAD"], repo).returncode == 0:
        # ``-X theirs`` during a rebase keeps the commit being replayed (our new
        # run) when a hunk conflicts. Only the derived files can conflict —
        # ``runs/index.json``, ``index.html`` — and ``regenerate()`` rewrites them
        # from the merged record set immediately afterwards.
        rebase = git(["rebase", "--autostash", "--strategy-option=theirs", "FETCH_HEAD"], repo)
        if rebase.returncode == 0:
            return True, "rebased onto remote"
        git(["rebase", "--abort"], repo)
        return False, f"rebase failed: {(rebase.stderr or '').strip()[:200]}"

    merge = git(
        ["-c", "commit.gpgsign=false", "merge", "--allow-unrelated-histories",
         "--no-edit", "-X", "ours", "FETCH_HEAD"],
        repo,
    )
    if merge.returncode == 0:
        return True, "merged unrelated remote history"
    git(["merge", "--abort"], repo)
    return False, f"merge failed: {(merge.stderr or '').strip()[:200]}"


def publish(
    *,
    repo: Path,
    remote: str,
    branch: str,
    message: str,
    retries: int,
    no_push: bool,
    author_name: str,
    author_email: str,
    regenerate: Callable[[], None] | None = None,
) -> tuple[bool, str]:
    """Commit everything and push to ``branch`` with rebase-and-retry."""
    git(["config", "user.name", author_name], repo)
    git(["config", "user.email", author_email], repo)
    git(["add", "-A"], repo)

    staged = git(["diff", "--cached", "--name-only"], repo)
    if not staged.stdout.strip():
        return True, "no changes to publish"

    commit = git(["-c", "commit.gpgsign=false", "commit", "-m", message], repo)
    if commit.returncode != 0:
        return False, f"commit failed: {commit.stderr.strip()[:400]}"

    if no_push:
        return True, "committed locally (--no-push)"

    last_error = ""
    for attempt in range(1, retries + 1):
        push = git(["push", "origin", f"HEAD:{branch}"], repo)
        if push.returncode == 0:
            return True, f"pushed to {branch} on attempt {attempt}"

        last_error = (push.stderr or push.stdout).strip()[:400]
        if attempt == retries:
            break
        backoff = min(30, 2 ** attempt) + random.uniform(0, 1.5)
        print(
            f"[publish] push rejected (attempt {attempt}/{retries}) — "
            f"rebase and retry in {backoff:.1f}s: {last_error.splitlines()[-1] if last_error else ''}",
            file=sys.stderr,
        )
        time.sleep(backoff)

        ok, detail = absorb_remote(repo, branch)
        if not ok:
            # A conflicting pull means our derived files lost a race. They are a
            # pure function of the run records, so rebuild and retry is safe.
            last_error = detail
            if regenerate is not None:
                regenerate()
                git(["add", "-A"], repo)
                if git(["diff", "--cached", "--name-only"], repo).stdout.strip():
                    git(["-c", "commit.gpgsign=false", "commit", "-m", message], repo)
            continue
        if regenerate is not None:
            # index.html / runs/index.json / latest/ must reflect the merged
            # record set, not whichever side won the conflict.
            regenerate()
            if git(["status", "--porcelain"], repo).stdout.strip():
                git(["add", "-A"], repo)
                git(["-c", "commit.gpgsign=false", "commit", "-m", message], repo)
    return False, last_error or "push failed"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Publish a health-check run to the monitoring Pages repo",
    )
    parser.add_argument("--run-dir", type=Path, required=True, help="report output directory")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--machine-name", default=None)
    parser.add_argument("--machine-type", default="unknown")
    parser.add_argument("--mode", default="")
    parser.add_argument("--status", default="")
    parser.add_argument("--origin", default="report", choices=("report", "auto-heal", "manual"))
    parser.add_argument("--kb-version", type=Path, default=None, help="kb-version/v1 JSON")
    parser.add_argument("--repo", type=Path, default=Path(os.path.expanduser("~/Work_RAG_HealthCheck")))
    parser.add_argument(
        "--remote",
        default=os.environ.get(
            "GPU_HEALTH_REPO", "https://github.com/AliNikkhah2001/Work_RAG_HealthCheck.git"
        ),
    )
    parser.add_argument("--branch", default="main")
    parser.add_argument("--keep-logs", type=int, default=DEFAULT_KEEP_LOGS)
    parser.add_argument("--keep-screenshots", type=int, default=SCREENSHOT_KEEP,
                        help="retain per-run screenshots for the newest N runs only")
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--no-push", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Build the tree, skip all git writes")
    parser.add_argument("--no-logs", action="store_true", help="Skip copying raw logs for this run")
    args = parser.parse_args(argv)

    out_dir = args.run_dir.resolve()
    if not out_dir.is_dir():
        print(f"ERROR: run dir not found: {out_dir}", file=sys.stderr)
        return 2

    machine = args.machine_name or os.uname().nodename.split(".")[0]
    run_id = args.run_id

    kb_version: dict[str, Any] | None = None
    if args.kb_version and args.kb_version.is_file():
        try:
            kb_version = json.loads(args.kb_version.read_text(encoding="utf-8"))
        except ValueError as exc:
            print(f"[publish] WARN: unreadable kb-version file: {exc}", file=sys.stderr)

    record = build_run_record(
        out_dir=out_dir,
        run_id=run_id,
        machine=machine,
        machine_type=args.machine_type,
        mode=args.mode,
        status=args.status,
        kb_version=kb_version,
        origin=args.origin,
        keep_detail=not args.no_logs,
    )

    repo = args.repo.resolve()
    print(f"[publish] repo={repo} run={run_id} status={record['status']} machine={machine}")

    if not args.dry_run:
        ensure_repo(repo, args.remote, args.branch, args.no_push)

    (repo / "runs").mkdir(parents=True, exist_ok=True)
    (repo / "runs" / f"{run_id}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    detail_rel = (record.get("links") or {}).get("detail")
    write_latest(repo, out_dir, record, detail_rel)
    if not args.no_logs:
        n = write_logs(repo, out_dir, run_id)
        print(f"[publish] logs/{run_id}: {n} files")
    removed = prune_logs(repo, args.keep_logs)
    if removed:
        print(f"[publish] pruned {len(removed)} old log dirs: {', '.join(removed[:5])}"
              f"{' …' if len(removed) > 5 else ''}")
    pruned_shots = prune_screenshots(repo, args.keep_screenshots)
    if pruned_shots:
        print(f"[publish] pruned screenshots for {len(pruned_shots)} old runs "
              f"(keep={args.keep_screenshots})")

    def regenerate() -> None:
        """Rebuild everything derived from the run records on disk.

        Called after a concurrent-push merge: ``runs/index.json``, ``index.html``
        and the retention decisions must describe the merged record set, not
        whichever side happened to win the conflict.
        """
        prune_logs(repo, args.keep_logs)
        prune_screenshots(repo, args.keep_screenshots)
        again = rebuild_index(repo)
        render_site(repo)
        print(f"[publish] regenerated derived files: {again['count']} records")

    index = rebuild_index(repo)
    render_site(repo)
    print(f"[publish] runs/index.json: {index['count']} records, {len(index['machines'])} machines")

    if args.dry_run:
        print("[publish] --dry-run: skipping git commit/push")
        print(f"[publish] tree ready at {repo}")
        return 0

    stamp = iso(utc_now())
    message = (
        f"chore(monitor): {stamp} {machine} {record['status']} "
        f"({run_id})"
    )
    ok, detail = publish(
        repo=repo,
        remote=args.remote,
        branch=args.branch,
        message=message,
        retries=args.retries,
        no_push=args.no_push,
        author_name=os.environ.get("GIT_AUTHOR_NAME", "Dana Health Bot"),
        author_email=os.environ.get("GIT_AUTHOR_EMAIL", "health@local"),
        regenerate=regenerate,
    )
    print(f"[publish] {'OK' if ok else 'FAILED'}: {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
