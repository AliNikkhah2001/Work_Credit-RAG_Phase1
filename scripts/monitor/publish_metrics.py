#!/usr/bin/env python3
"""Append a compact health metrics point to Work_RAG_Metrics (no screenshots).

Also writes a copy under the HealthCheck Pages tree at ``metrics/`` so the
static dashboard can ingest status without cross-origin fetches.

Layout (metrics repo):
  metrics/latest.json     current status snapshot
  metrics/series.json     rolling window of points (hourly, last N days)
  metrics/status.json     machine-facing status for badges / ops
  README.md

No PNGs, no logs — only small JSON so hourly pushes stay under GitHub limits.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SERIES_SCHEMA = "metrics-series/v1"
POINT_SCHEMA = "metrics-point/v1"
DEFAULT_KEEP_DAYS = 14
DEFAULT_REMOTE = "https://github.com/AliNikkhah2001/Work_RAG_Metrics.git"
EXIT_REFUSED = 64


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def repo_slug(remote: str) -> str:
    value = (remote or "").strip()
    if value.startswith("git@"):
        value = value.split(":", 1)[-1]
    elif "://" in value:
        value = value.split("://", 1)[1].split("/", 1)[-1]
    if value.endswith(".git"):
        value = value[: -len(".git")]
    return "/".join(p for p in value.strip("/").split("/") if p).lower()


def refuse_metrics_target(remote: str) -> str | None:
    slug = repo_slug(remote)
    if not slug:
        return "no metrics remote configured"
    name = slug.rsplit("/", 1)[-1]
    if "metric" not in name:
        return f"target '{slug}' is not a metrics repo (expected '*metric*')"
    protected = (
        "work_credit-rag_phase1",
        "work_rag-server-setup",
        "work_rag-orchestrator",
        "work_rag-guardrails",
        "work_rag-kb",
    )
    if name in protected:
        return f"target '{slug}' is a production repo"
    return None


def git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        timeout=180,
    )


def ensure_repo(repo: Path, remote: str, branch: str, no_push: bool) -> None:
    if not (repo / ".git").exists():
        repo.parent.mkdir(parents=True, exist_ok=True)
        if repo.exists():
            import shutil
            shutil.rmtree(repo)
        if remote:
            cloned = subprocess.run(
                ["git", "clone", "--quiet", "--branch", branch, remote, str(repo)],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if cloned.returncode == 0:
                return
            if repo.exists():
                import shutil
                shutil.rmtree(repo)
        repo.mkdir(parents=True, exist_ok=True)
        git(["init", "-q"], repo)
        if remote:
            git(["remote", "add", "origin", remote], repo)
        git(["checkout", "-B", branch], repo)
        return
    if remote:
        git(["remote", "remove", "origin"], repo)
        git(["remote", "add", "origin", remote], repo)
    if no_push:
        return
    if git(["fetch", "origin", branch], repo).returncode == 0:
        if git(["merge-base", "HEAD", "FETCH_HEAD"], repo).returncode == 0:
            git(["rebase", "--autostash", "FETCH_HEAD"], repo)


def normalize_services(run_record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map service name → {state, http} from list or dict run-record shapes."""
    raw = run_record.get("services")
    out: dict[str, dict[str, Any]] = {}
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            state = item.get("status") or item.get("state")
            http = item.get("http_code")
            if http is None:
                http = item.get("http")
            out[str(item["name"])] = {"state": state, "http": http}
        return out
    if isinstance(raw, dict):
        for name, info in raw.items():
            if isinstance(info, str):
                out[str(name)] = {"state": info, "http": None}
            elif isinstance(info, dict):
                out[str(name)] = {
                    "state": info.get("state") or info.get("status"),
                    "http": info.get("http") if info.get("http") is not None else info.get("http_code"),
                }
    return out


def build_point(run_record: dict[str, Any]) -> dict[str, Any]:
    services = normalize_services(run_record)
    core = ("kb", "guardrails", "orchestrator", "webui")
    up = sum(1 for s in core if (services.get(s) or {}).get("state") == "up")
    ts = run_record.get("generated_at") or run_record.get("ts") or iso(utc_now())
    kb = run_record.get("kb") if isinstance(run_record.get("kb"), dict) else None
    kb_ver = run_record.get("kb_version") if isinstance(run_record.get("kb_version"), dict) else None
    kb_match = None
    if kb and isinstance(kb.get("verdict"), dict):
        kb_match = kb["verdict"].get("status")
    elif kb and isinstance(kb.get("verdict"), str):
        kb_match = kb.get("verdict")
    elif kb_ver and isinstance(kb_ver.get("verdict"), dict):
        kb_match = kb_ver["verdict"].get("status")
    e2e = run_record.get("e2e") if isinstance(run_record.get("e2e"), dict) else None
    qa = run_record.get("qa")
    if e2e and qa is None:
        qa = e2e.get("summary") or e2e.get("status")
    elif isinstance(qa, dict):
        qa = qa.get("summary")
    return {
        "schema_version": POINT_SCHEMA,
        "ts": ts,
        "run_id": run_record.get("run_id"),
        "machine": run_record.get("machine"),
        "status": run_record.get("status"),
        "core_up": up,
        "core_total": len(core),
        "services": {name: (info or {}).get("state") for name, info in services.items()},
        "http": {
            name: (info or {}).get("http")
            for name, info in services.items()
            if (info or {}).get("http") is not None
        },
        "qa": qa,
        "kb_match": kb_match,
        "latency_e2e_p50_ms": (
            ((run_record.get("latency") or {}).get("e2e") or {}).get("p50_ms")
            if isinstance(run_record.get("latency"), dict)
            else None
        ),
        "jenkins_healthy": (
            (run_record.get("jenkins") or {}).get("healthy")
            if isinstance(run_record.get("jenkins"), dict)
            else None
        ),
        "gpu_util_pct": _first_gpu_util(run_record.get("host")),
        "mem_used_mb": (
            ((run_record.get("host") or {}).get("memory") or {}).get("used_mb")
            if isinstance(run_record.get("host"), dict)
            else None
        ),
    }


def _first_gpu_util(host: Any) -> float | None:
    if not isinstance(host, dict):
        return None
    gpus = host.get("gpu") or []
    if not isinstance(gpus, list) or not gpus:
        return None
    u = gpus[0].get("util_pct") if isinstance(gpus[0], dict) else None
    return float(u) if isinstance(u, (int, float)) else None


def load_series(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if isinstance(data, dict):
        pts = data.get("points") or []
        return pts if isinstance(pts, list) else []
    return []


def prune_series(points: list[dict[str, Any]], keep_days: int) -> list[dict[str, Any]]:
    if keep_days <= 0:
        return points[-24 * 30 :]  # hard cap ~30d hourly
    cutoff = utc_now() - timedelta(days=keep_days)
    kept: list[dict[str, Any]] = []
    for p in points:
        ts = p.get("ts") or ""
        try:
            dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        except ValueError:
            kept.append(p)
            continue
        if dt >= cutoff:
            kept.append(p)
    # Cap absolute size even inside the window (hourly * days + buffer)
    max_points = keep_days * 24 + 48
    return kept[-max_points:]


def write_tree(repo: Path, point: dict[str, Any], keep_days: int) -> Path:
    mdir = repo / "metrics"
    mdir.mkdir(parents=True, exist_ok=True)
    series_path = mdir / "series.json"
    points = load_series(series_path)
    # de-dupe same run_id
    rid = point.get("run_id")
    points = [p for p in points if p.get("run_id") != rid]
    points.append(point)
    points = prune_series(points, keep_days)
    series = {
        "schema_version": SERIES_SCHEMA,
        "generated_at": iso(utc_now()),
        "keep_days": keep_days,
        "count": len(points),
        "points": points,
    }
    series_path.write_text(json.dumps(series, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    (mdir / "latest.json").write_text(
        json.dumps(point, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    status = {
        "schema_version": "metrics-status/v1",
        "updated_at": iso(utc_now()),
        "status": point.get("status"),
        "machine": point.get("machine"),
        "run_id": point.get("run_id"),
        "core_up": point.get("core_up"),
        "core_total": point.get("core_total"),
        "ok": point.get("status") == "HEALTHY",
    }
    (mdir / "status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    readme = repo / "README.md"
    if not readme.is_file():
        readme.write_text(
            "# Work_RAG_Metrics\n\n"
            "Append-only hourly health metrics for Dana RAG (no screenshots).\n\n"
            "- `metrics/latest.json` — last point\n"
            "- `metrics/series.json` — rolling window\n"
            "- `metrics/status.json` — badge-friendly status\n\n"
            "Dashboard: https://alinikkhah2001.github.io/Work_RAG_HealthCheck/\n",
            encoding="utf-8",
        )
    (repo / ".nojekyll").write_text("", encoding="utf-8")
    return series_path


def sync_into_pages(pages_repo: Path, metrics_repo: Path) -> None:
    """Copy metrics JSON into the HealthCheck Pages tree (same origin)."""
    src = metrics_repo / "metrics"
    if not src.is_dir() or not pages_repo.is_dir():
        return
    dest = pages_repo / "metrics"
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("latest.json", "series.json", "status.json"):
        s = src / name
        if s.is_file():
            (dest / name).write_text(s.read_text(encoding="utf-8"), encoding="utf-8")


def push_repo(repo: Path, remote: str, branch: str, message: str, no_push: bool) -> tuple[bool, str]:
    git(["config", "user.name", os.environ.get("GIT_AUTHOR_NAME", "Dana Metrics Bot")], repo)
    git(["config", "user.email", os.environ.get("GIT_AUTHOR_EMAIL", "metrics@local")], repo)
    git(["add", "-A"], repo)
    if not git(["diff", "--cached", "--name-only"], repo).stdout.strip():
        return True, "no metrics changes"
    commit = git(["-c", "commit.gpgsign=false", "commit", "-m", message], repo)
    if commit.returncode != 0:
        return False, (commit.stderr or "")[:300]
    if no_push:
        return True, "committed locally (--no-push)"
    push = git(["push", "origin", f"HEAD:{branch}"], repo)
    if push.returncode == 0:
        return True, f"pushed metrics to {branch}"
    # one rebase retry
    git(["fetch", "origin", branch], repo)
    git(["rebase", "--autostash", "FETCH_HEAD"], repo)
    push2 = git(["push", "origin", f"HEAD:{branch}"], repo)
    if push2.returncode == 0:
        return True, f"pushed metrics to {branch} after rebase"
    return False, (push2.stderr or push.stderr or "")[:400]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-json", type=Path, required=True, help="health run record JSON")
    p.add_argument("--repo", type=Path,
                   default=Path(os.environ.get("GPU_METRICS_REPO_DIR", "/var/lib/dana-health/Work_RAG_Metrics")))
    p.add_argument("--remote", default=os.environ.get("GPU_METRICS_REPO", DEFAULT_REMOTE))
    p.add_argument("--branch", default="main")
    p.add_argument("--keep-days", type=int, default=int(os.environ.get("GPU_METRICS_KEEP_DAYS", DEFAULT_KEEP_DAYS)))
    p.add_argument("--pages-repo", type=Path,
                   default=Path(os.environ.get("GPU_HEALTH_REPO_DIR", "/var/lib/dana-health/Work_RAG_HealthCheck")))
    p.add_argument("--no-push", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    if not args.run_json.is_file():
        print(f"ERROR: missing run json {args.run_json}", file=sys.stderr)
        return 2
    record = json.loads(args.run_json.read_text(encoding="utf-8"))
    point = build_point(record)

    refusal = refuse_metrics_target(args.remote)
    if refusal and not (args.dry_run or args.no_push):
        print(f"[metrics] REFUSED: {refusal}", file=sys.stderr)
        return EXIT_REFUSED

    repo = args.repo.resolve()
    if not args.dry_run:
        ensure_repo(repo, args.remote, args.branch, args.no_push)
    else:
        repo.mkdir(parents=True, exist_ok=True)

    write_tree(repo, point, args.keep_days)
    sync_into_pages(args.pages_repo.resolve(), repo)
    # Also write host-local status for ops
    status_host = Path("/var/lib/dana-health/status.json")
    try:
        status_host.parent.mkdir(parents=True, exist_ok=True)
        status_host.write_text(
            (repo / "metrics" / "status.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    except OSError:
        pass

    print(f"[metrics] point status={point.get('status')} run={point.get('run_id')}")
    if args.dry_run:
        print("[metrics] --dry-run: skip push")
        return 0

    ok, detail = push_repo(
        repo,
        args.remote,
        args.branch,
        f"chore(metrics): {point.get('ts')} {point.get('machine')} {point.get('status')}",
        args.no_push,
    )
    print(f"[metrics] {'OK' if ok else 'FAILED'}: {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
