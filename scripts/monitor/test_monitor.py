#!/usr/bin/env python3
"""Self-checks for the monitoring pipeline (runs offline, no git, no network).

Validates:
  * the ``health-run/v1`` record schema produced by ``publish_report``
  * ``runs/index.json`` self-healing rebuild (corrupt + deleted records)
  * retention (logs and screenshots pruned to the newest N)
  * relative links inside the published tree resolve to real files
  * the dashboard template contains every required panel and no ``file://`` paths

Usage:
    python3 scripts/monitor/test_monitor.py
Exit code 0 = all checks passed.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import publish_report as pr  # noqa: E402

FAILS: list[str] = []
PASSES = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSES
    if condition:
        PASSES += 1
        print(f"  ok   {label}")
    else:
        FAILS.append(f"{label}{(' — ' + detail) if detail else ''}")
        print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")


def section(name: str) -> None:
    print(f"\n== {name} ==")


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
def make_fixture(root: Path, run_id: str, *, down: tuple[str, ...] = ()) -> Path:
    """Minimal but realistic report output directory."""
    out = root / run_id
    for sub in ("curl", "e2e", "meta", "kb", "html", "screenshots", "restart", "logs"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    rows = ["port\tservice\thttp_code\tbody_preview"]
    for port, name in (
        (8000, "kb"), (8200, "guardrails"), (8100, "orchestrator"),
        (13000, "webui"), (18000, "gemma"), (9000, "manager"),
    ):
        code = "000" if name in down else "200"
        rows.append(f"{port}\t{name}\t{code}\t")
    (out / "curl" / "matrix.tsv").write_text("\n".join(rows) + "\n")

    (out / "e2e" / "summary.txt").write_text(
        "chat_greeting http=200\nchat_credit_qa http=200\nkb_search http=200\n"
    )
    (out / "e2e" / "score.txt").write_text("qa_pass=3/3\n")
    (out / "meta" / "host_metadata.txt").write_text("hostname=test-host.local\nmachine_type=production_gpu\n")
    (out / "run.log").write_text("log line\n" * 50)
    (out / "REPORT.md").write_text("# Report\n")
    (out / "html" / "dashboard.html").write_text(
        '<!doctype html><html><body>'
        '<img src="../screenshots/a.png">'
        '<a href="../REPORT.md">report</a>'
        "</body></html>"
    )
    (out / "screenshots" / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 32)
    return out


KB_FIXTURE = {
    "schema_version": "kb-version/v1",
    "actual": {
        "chunk_count": 1319,
        "document_count": 21,
        "embedding_models": [{"model": "MiniLM", "chunks": 1319}],
        "last_ingestion_job": {"job_type": "full_rebuild", "status": "completed"},
        "method": "docker:pg",
    },
    "served": {
        "chunks": 1319,
        "chunk_count": 1319,
        "document_count": 21,
        "manifest_id": None,
        "packs": {"schemas": "1.0.1"},
        "dvc_pin": {"chunks": 1471},
        "corpus_date": "1405-06-23",
    },
    "expected": {
        "corpus_pin": "1405-08-20",
        "processed_corpus": "1405-06-23",
        "chunk_count": 1471,
        "document_count": 28,
        "packs": {"schemas": "1.0.0"},
    },
    "verdict": {
        "status": "mismatch",
        "mismatches": ["chunk_count", "document_count"],
        "checks": [
            {"check": "chunk_count", "actual": 1319, "expected": 1471, "match": False},
        ],
        "live_corpus": "1405-06-23",
        "latest_available_corpus": "1405-08-20",
        "corpus_lagging": True,
    },
    "unknown": [{"field": "served.manifest", "reason": "no active manifest"}],
}


# --------------------------------------------------------------------------- #
# checks
# --------------------------------------------------------------------------- #
def _run_record_schema(tmp: Path) -> dict:
    section("run record schema (health-run/v1)")
    out = make_fixture(tmp, "20261114T160000Z-test-host", down=("manager",))
    rec = pr.build_run_record(
        out_dir=out,
        run_id="20261114T160000Z-test-host",
        machine="test-host",
        machine_type="production_gpu",
        mode="compose",
        status="",
        kb_version=KB_FIXTURE,
    )
    required = {
        "schema_version", "run_id", "generated_at", "machine", "machine_type",
        "host", "mode", "origin", "status", "core_services_down", "services",
        "e2e", "gate", "kb", "links",
    }
    check("all required top-level keys", required <= set(rec), f"missing {required - set(rec)}")
    check("schema_version pinned", rec["schema_version"] == "health-run/v1")
    check("run_id echoes input", rec["run_id"] == "20261114T160000Z-test-host")
    check("generated_at from run id (UTC)", rec["generated_at"] == "2026-11-14T16:00:00Z",
          rec["generated_at"])
    check("status derived when not supplied", rec["status"] == "HEALTHY", rec["status"])
    check("services is a non-empty list", isinstance(rec["services"], list) and len(rec["services"]) == 6)
    check("service entries carry name/status",
          all({"name", "status"} <= set(s) for s in rec["services"]))
    check("unknown HTTP maps to down",
          next(s for s in rec["services"] if s["name"] == "manager")["status"] == "down")
    check("qa passed/total parsed", rec["e2e"]["passed"] == 3 and rec["e2e"]["total"] == 3)
    check("kb verdict propagated", rec["kb"]["verdict"] == "mismatch")
    check("kb checks preserved", len(rec["kb"]["checks"]) == 1)
    check("kb unknown fields listed", rec["kb"]["unknown"] == ["served.manifest"])
    check("no raw logs embedded in record",
          "CONTAINER" not in json.dumps(rec) and len(json.dumps(rec)) < 20000,
          f"{len(json.dumps(rec))} bytes")
    check("detail link is relative", not rec["links"]["detail"].startswith(("/", "http")),
          rec["links"]["detail"])
    return rec


def _run_status_derivation(tmp: Path) -> None:
    section("status derivation from core services")
    out = make_fixture(tmp, "20261114T170000Z-down", down=("orchestrator",))
    rec = pr.build_run_record(
        out_dir=out, run_id="20261114T170000Z-down", machine="m",
        machine_type="production_gpu", mode="compose", status="", kb_version=None,
    )
    check("one core service down → DEGRADED", rec["status"] == "DEGRADED", rec["status"])
    check("core_services_down lists it", rec["core_services_down"] == ["orchestrator"])

    out2 = make_fixture(tmp, "20261114T180000Z-full", down=("kb", "guardrails", "orchestrator", "webui"))
    rec2 = pr.build_run_record(
        out_dir=out2, run_id="20261114T180000Z-full", machine="m",
        machine_type="production_gpu", mode="compose", status="", kb_version=None,
    )
    check("all core services down → DOWN", rec2["status"] == "DOWN", rec2["status"])


def _run_index(tmp: Path) -> None:
    section("runs/index.json rebuild is self-healing")
    root = tmp / "site"
    (root / "runs").mkdir(parents=True)
    for i in range(3):
        rid = f"2026111{i}T160000Z-host"
        (root / "runs" / f"{rid}.json").write_text(json.dumps({
            "schema_version": "health-run/v1", "run_id": rid,
            "generated_at": f"2026-11-1{i}T16:00:00Z", "machine": "host",
            "machine_type": "production_gpu", "status": "HEALTHY",
            "services": [{"name": "kb", "status": "up"}], "e2e": {"passed": 3, "total": 3},
            "kb": {"verdict": "match"},
        }))
    # A corrupt record must be reported, not crash the rebuild.
    (root / "runs" / "20261113T160000Z-broken.json").write_text("{not json")
    idx = pr.rebuild_index(root)
    check("counts only valid records", idx["count"] == 3, str(idx["count"]))
    check("corrupt record reported", idx["corrupt_records"] == ["20261113T160000Z-broken.json"],
          str(idx["corrupt_records"]))
    check("entries sorted by time",
          [e["ts"] for e in idx["entries"]] == sorted(e["ts"] for e in idx["entries"]))
    check("index file written", (root / "runs" / "index.json").is_file())

    # Deleting a record and re-running must drop it (self-healing, not append-only-stale).
    (root / "runs" / "20261110T160000Z-host.json").unlink()
    idx2 = pr.rebuild_index(root)
    check("deleted record disappears from index", idx2["count"] == 2, str(idx2["count"]))
    check("machines deduplicated", idx2["machines"] == ["host"], str(idx2["machines"]))


def _run_retention(tmp: Path) -> None:
    section("retention (logs + screenshots)")
    root = tmp / "retain"
    for i in range(5):
        d = root / "logs" / f"run-{i}"
        (d / "screenshots").mkdir(parents=True)
        (d / "run.log").write_text("x")
        (d / "screenshots" / "s.png").write_bytes(b"png")
    removed = pr.prune_logs(root, keep=2)
    check("prunes log dirs beyond keep", len(removed) == 3, str(removed))
    check("newest logs survive", (root / "logs" / "run-4" / "run.log").is_file())
    check("oldest log dir gone", not (root / "logs" / "run-0").exists())

    # Screenshot pruning only removes PNGs, keeping text logs.
    for i in range(5):
        d = root / "logs" / f"run-{i}"
        (d / "screenshots").mkdir(parents=True, exist_ok=True)
        (d / "run.log").write_text("x")
        (d / "screenshots" / "s.png").write_bytes(b"png")
    pruned = pr.prune_screenshots(root, keep=1, keep_hours=0)
    check("screenshot pruning reported", len(pruned) == 4, str(pruned))
    check("screenshots removed for old runs",
          not (root / "logs" / "run-0" / "screenshots").exists())
    check("text logs kept after screenshot pruning",
          (root / "logs" / "run-0" / "run.log").is_file())

    # Age window: timestamped run ids older than keep_hours lose screenshots
    # even when they are inside the count window.
    for stamp, name in (
        ("20260101T000000Z", "old"),
        ("20990101T000000Z", "future"),
    ):
        d = root / "logs" / f"{stamp}-{name}"
        (d / "screenshots").mkdir(parents=True, exist_ok=True)
        (d / "screenshots" / "s.png").write_bytes(b"png")
    aged = pr.prune_screenshots(root, keep=99, keep_hours=1)
    check("age prune drops old screenshots",
          "20260101T000000Z-old" in aged, str(aged))
    check("age prune keeps fresh screenshots",
          (root / "logs" / "20990101T000000Z-future" / "screenshots").is_dir())


def _run_links(tmp: Path) -> None:
    section("published tree links resolve")
    root = tmp / "links"
    out = make_fixture(tmp, "20261114T190000Z-link")
    rec = pr.build_run_record(
        out_dir=out, run_id="20261114T190000Z-link", machine="m",
        machine_type="production_gpu", mode="compose", status="HEALTHY",
        kb_version=KB_FIXTURE,
    )
    (root / "runs").mkdir(parents=True)
    (root / "runs" / f"{rec['run_id']}.json").write_text(json.dumps(rec))
    pr.write_logs(root, out, rec["run_id"])
    pr.write_latest(root, out, rec, rec["links"]["detail"])
    pr.rebuild_index(root)
    pr.render_site(root)

    check("runs/index.json exists", (root / "runs" / "index.json").is_file())
    check(".nojekyll exists", (root / ".nojekyll").is_file())
    check("index.html exists", (root / "index.html").is_file())
    check("run record exists", (root / "runs" / f"{rec['run_id']}.json").is_file())
    check("detail link target exists", (root / rec["links"]["detail"]).is_file(),
          rec["links"]["detail"])
    check("latest redirect written", (root / "latest" / "dashboard.html").is_file())
    check("latest has no duplicated screenshots dir",
          not (root / "latest" / "screenshots").exists())

    page = (root / rec["links"]["detail"]).read_text()
    rel_srcs = re.findall(r'src="([^"]+)"', page)
    resolved = [(root / rec["links"]["detail"]).parent / s for s in rel_srcs]
    check("detail page screenshot links resolve",
          bool(resolved) and all(p.is_file() for p in resolved),
          str([str(p) for p in resolved if not p.is_file()]))

    redir = (root / "latest" / "dashboard.html").read_text()
    m = re.search(r'url=\.\./([^"]+)"', redir)
    check("latest redirect points at a real file", bool(m) and (root / m.group(1)).is_file(),
          m.group(1) if m else "no redirect found")


def _run_no_secret_artifacts(tmp: Path) -> None:
    section("sensitive artifacts are never published")
    out = make_fixture(tmp, "20261114T200000Z-secrets")
    (out / "logs" / "command_shutdown_reboot_user.log").write_text(
        "LANGFUSE_SECRET_KEY=sk-live-abc123\n"
    )
    (out / "logs" / "host-orch.log").write_text("OPENAI_API_KEY=sk-xyz\n")
    (out / "logs" / "database_and_dvc.log").write_text("safe: chunk counts\n")
    root = tmp / "secret-site"
    n = pr.write_logs(root, out, "20261114T200000Z-secrets")
    dest = root / "logs" / "20261114T200000Z-secrets"
    check("write_logs copied something", n > 0, str(n))
    check("shell history excluded",
          not (dest / "logs" / "command_shutdown_reboot_user.log").exists())
    check("host-*.log excluded", not (dest / "logs" / "host-orch.log").exists())
    check("safe evidence still copied", (dest / "logs" / "database_and_dvc.log").is_file())

    leaked = [
        p for p in dest.rglob("*")
        if p.is_file() and "sk-live-abc123" in p.read_text(errors="replace")
    ]
    check("no published file contains the sentinel secret", not leaked, str(leaked))


def _run_status_casing(tmp: Path) -> None:
    section("run status casing (dashboard compares uppercase literals)")
    # The template compares `r.status === "HEALTHY"` literally. A lowercase
    # `--status healthy` used to slip through and render as a red stack —
    # "0.0 % uptime · 0 healthy / N runs" on an all-healthy fleet. Emitting a
    # fabricated downtime number must be impossible.
    seen: dict[str, str] = {}

    def record_for(status: str, run_id: str) -> dict:
        out = make_fixture(tmp, run_id)
        rec = pr.build_run_record(
            out_dir=out,
            run_id=run_id,
            machine="m",
            machine_type="production_gpu",
            mode="compose",
            status=status,
            kb_version=None,
        )
        return rec

    for given in ("healthy", "HEALTHY", " Healthy ", "Healthy"):
        rec = record_for(given, "20261114T01010" + "0Z")
        seen[given] = rec["status"]
        check(f"status {given!r} normalised to HEALTHY", rec["status"] == "HEALTHY", rec["status"])

    for given, want in (("down", "DOWN"), ("degraded", "DEGRADED"), ("Degraded", "DEGRADED")):
        rec = record_for(given, "20261114T01020" + "0Z")
        check(f"status {given!r} normalised to {want}", rec["status"] == want, rec["status"])

    # An unrecognised word must never be reported as healthy.
    rec = record_for("banana", "20261114T010300Z")
    check("unknown status is not HEALTHY", rec["status"] != "HEALTHY", rec["status"])
    check("unknown status falls back to DEGRADED", rec["status"] == "DEGRADED", rec["status"])
    check("template literals match KNOWN_STATUSES",
          "HEALTHY" in pr.KNOWN_STATUSES and "DOWN" in pr.KNOWN_STATUSES)


def _run_dashboard_template() -> None:
    section("dashboard template")
    tpl = Path(__file__).resolve().parent / "site" / "index.html"
    check("template exists", tpl.is_file())
    html = tpl.read_text(encoding="utf-8")
    for panel in ("Historical uptime", "Downtime percentage", "Failures — last 24 hours",
                  "Knowledge base version", "Single reports", "Endpoints — what each check means"):
        check(f"panel present: {panel}", panel in html)
    check("separates devices in history", "deviceGroups" in html or "per device" in html.lower())
    check("reports default collapsed", 'details class="fold report-fold"' in html or "report-fold" in html)
    check("reads runs/index.json", 'getJSON("runs/index.json")' in html)
    check("no absolute file paths", "file://" not in html)
    check("no build step / bundler import", "import(" not in html and "require(" not in html)
    check("uses relative data paths only",
          not re.search(r'fetch\(\s*["\']/(?!/)', html), "absolute fetch path found")
    check("window selectors present", html.count('data-window=') >= 8)
    check("no leftover placeholder domain", "placeholder" not in html.lower())


def _run_run_id_time() -> None:
    section("run id → timestamp")
    dt = pr.run_id_time("20261114T145307Z-Ali-Nikkhah-4")
    check("parses standard run id", dt is not None and pr.iso(dt) == "2026-11-14T14:53:07Z",
          pr.iso(dt) if dt else "None")
    check("unparseable id returns None", pr.run_id_time("not-a-run") is None)


def _run_push_guard() -> None:
    section("push-target guard (reports must never reach a production repo)")
    refusal = pr.push_target_refusal
    check("production umbrella repo refused",
          refusal("https://github.com/AliNikkhah2001/Work_Credit-RAG_Phase1.git") is not None)
    check("virtual-server-setup repo refused",
          refusal("https://github.com/AliNikkhah2001/Work_RAG-Server-Setup.git") is not None)
    check("component submodule repo refused",
          refusal("git@github.com:AliNikkhah2001/Work_RAG-Orchestrator.git") is not None)
    check("health-check repo allowed",
          refusal("https://github.com/AliNikkhah2001/Work_RAG_HealthCheck.git") is None)
    check("health-check repo allowed with different case",
          refusal("https://github.com/AliNikkhah2001/work_rag_healthcheck") is None)
    check("unrelated repo refused", refusal("https://github.com/someone/random.git") is not None)
    check("empty remote refused", refusal("") is not None)
    check("slug normalisation strips transport and .git",
          pr.repo_slug("git@github.com:Owner/Repo.git") == "owner/repo",
          pr.repo_slug("git@github.com:Owner/Repo.git"))
    check("exit code is the refusal code, not a failure code", pr.EXIT_REFUSED == 64,
          str(pr.EXIT_REFUSED))


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="monitor-test-"))
    try:
        _run_run_id_time()
        _run_record_schema(tmp)
        _run_status_derivation(tmp)
        _run_index(tmp)
        _run_retention(tmp)
        _run_links(tmp)
        _run_no_secret_artifacts(tmp)
        _run_status_casing(tmp)
        _run_dashboard_template()
        _run_push_guard()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 60)
    if FAILS:
        print(f"FAILED — {len(FAILS)} check(s):")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print(f"PASSED — {PASSES} checks")
    return 0


# --------------------------------------------------------------------------- #
# pytest entry points
#
# The ``_run_*`` helpers above are driven by ``main()`` (the standalone runner
# used by the GPU host, where pytest is not installed). These thin wrappers let
# CI collect the same checks with ``pytest``; both paths share one code path, so
# a check can never pass under one runner and fail under the other.
# --------------------------------------------------------------------------- #
def _assert_clean(fn, *args) -> None:
    """Run one check group and fail the pytest test if it added any FAILS."""
    before = len(FAILS)
    fn(*args)
    new = FAILS[before:]
    assert not new, "failed checks:\n  - " + "\n  - ".join(new)


def test_run_id_parsing() -> None:
    _assert_clean(_run_run_id_time)


def test_record_schema(tmp_path: Path) -> None:
    _assert_clean(_run_record_schema, tmp_path)


def test_status_derivation(tmp_path: Path) -> None:
    _assert_clean(_run_status_derivation, tmp_path)


def test_index(tmp_path: Path) -> None:
    _assert_clean(_run_index, tmp_path)


def test_retention(tmp_path: Path) -> None:
    _assert_clean(_run_retention, tmp_path)


def test_published_links(tmp_path: Path) -> None:
    _assert_clean(_run_links, tmp_path)


def test_no_secret_artifacts(tmp_path: Path) -> None:
    _assert_clean(_run_no_secret_artifacts, tmp_path)


def test_status_casing(tmp_path: Path) -> None:
    _assert_clean(_run_status_casing, tmp_path)


def test_dashboard_template() -> None:
    _assert_clean(_run_dashboard_template)


def test_push_guard() -> None:
    _assert_clean(_run_push_guard)


if __name__ == "__main__":
    raise SystemExit(main())
