#!/usr/bin/env python3
"""Parse commit message + changed paths into CI gate env vars for Jenkins.

Keys (case-insensitive):
  [ci skip] / [skip ci]
  [ci build]
  [ci stage]
  [ci auto]
  [ci prod]
  [ci all]              → force full image set (Sprint B)
  [ci rollback]         → restore last-good prod SHA (Sprint C #10)

Sprint B — CI_SERVICES:
  space-separated compose service names, or "all".

Usage:
  python3 scripts/ci_message_gate.py --write-env .ci_gate.env
  python3 scripts/ci_message_gate.py --self-test
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEAVY = re.compile(
    r"(^|/)(components/|deploy/|Jenkinsfile|Dockerfile|\.dockerignore|compose\.[^/]+\.yml)",
    re.I,
)

# Path prefix → compose service (order matters for readability only)
SERVICE_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(^|/)components/knowledgebase(/|$)", re.I), "kb"),
    (re.compile(r"(^|/)components/guardrails(/|$)", re.I), "guardrails"),
    (re.compile(r"(^|/)components/orchestrator(/|$)", re.I), "orchestrator"),
    (re.compile(r"(^|/)components/tracing(/|$)", re.I), "tracing"),
    (re.compile(r"(^|/)components/webui(/|$)", re.I), "webui"),
]

FORCE_ALL = re.compile(
    r"(^|/)"
    r"(deploy/compose/|deploy/jenkins/|Jenkinsfile$|\.gitmodules$"
    r"|Dockerfile$|compose\.[^/]+\.yml)",
    re.I,
)

CORE_SERVICES = ("kb", "guardrails", "orchestrator", "tracing")


def services_for_paths(changed: str, force_all_key: bool) -> str:
    lines = [ln.strip() for ln in (changed or "").splitlines() if ln.strip()]
    if force_all_key:
        return "all"
    if not lines:
        return "all"
    if any(FORCE_ALL.search(ln) for ln in lines):
        return "all"
    found: list[str] = []
    for ln in lines:
        for pat, svc in SERVICE_MAP:
            if pat.search(ln) and svc not in found:
                found.append(svc)
    if not found:
        # docs-only / unrelated → no image build list (caller may still skip build)
        return "none"
    # webui alone is fine; if only non-core matched keep as-is
    return " ".join(found)


def parse(msg: str, changed: str) -> dict[str, str]:
    low = (msg or "").lower()
    skip = "[ci skip]" in low or "[skip ci]" in low
    build = "[ci build]" in low
    stage = "[ci stage]" in low
    prod = "[ci prod]" in low
    auto = "[ci auto]" in low
    force_all = "[ci all]" in low
    rollback = "[ci rollback]" in low
    heavy = any(HEAVY.search(line) for line in (changed or "").splitlines())
    services = "none" if skip else services_for_paths(changed, force_all)
    # Deploy keys with no service hit still need a stack refresh → all
    if not skip and services == "none" and (stage or prod or auto or build) and not rollback:
        services = "all"
    if rollback:
        # Rollback path: do not rebuild current tip; skip normal deploy keys
        services = "none"
    return {
        "CI_SKIP": "1" if skip else "0",
        "CI_BUILD": "1" if build else "0",
        "CI_STAGE": "1" if stage else "0",
        "CI_PROD": "1" if prod else "0",
        "CI_AUTO": "1" if auto else "0",
        "CI_ROLLBACK": "1" if rollback else "0",
        "CI_HEAVY_PATHS": "1" if heavy else "0",
        "CI_SERVICES": services,
    }


def write_env(path: Path, data: dict[str, str]) -> None:
    path.write_text("\n".join(f"{k}={v}" for k, v in data.items()) + "\n", encoding="utf-8")


def self_test() -> None:
    cases = [
        ("docs only", "docs: typo", "README.md", {"CI_SKIP": "0", "CI_STAGE": "0", "CI_HEAVY_PATHS": "0", "CI_SERVICES": "none"}),
        ("skip", "chore: x [ci skip]", "deploy/compose/compose.base.yml", {"CI_SKIP": "1", "CI_SERVICES": "none"}),
        ("stage docs", "feat: y [ci stage]", "docs/a.md", {"CI_STAGE": "1", "CI_SERVICES": "all"}),
        ("kb only", "fix: denser [ci stage]", "components/knowledgebase/kb-manager/foo.py", {"CI_STAGE": "1", "CI_SERVICES": "kb"}),
        ("guard+orch", "fix: x [ci build]", "components/guardrails/a.py\ncomponents/orchestrator/b.py", {"CI_SERVICES": "guardrails orchestrator"}),
        ("compose all", "chore: ports [ci stage]", "deploy/compose/compose.stage.yml", {"CI_SERVICES": "all"}),
        ("ci all key", "rebuild [ci all] [ci build]", "README.md", {"CI_SERVICES": "all"}),
        ("prod", "release [ci prod]", "Jenkinsfile", {"CI_PROD": "1", "CI_SERVICES": "all"}),
        ("rollback", "break glass [ci rollback]", "README.md", {"CI_ROLLBACK": "1", "CI_SERVICES": "none"}),
    ]
    for name, msg, changed, expect in cases:
        got = parse(msg, changed)
        for k, v in expect.items():
            assert got[k] == v, f"{name}: {k} want {v} got {got[k]} full={got}"
    print("ci_message_gate self-test OK")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-env", type=Path, default=None)
    ap.add_argument("--msg-file", type=Path, default=ROOT / ".ci_commit_msg.txt")
    ap.add_argument("--changed-file", type=Path, default=ROOT / ".ci_changed_files.txt")
    ap.add_argument("--msg-stdin", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.msg_stdin:
        msg = sys.stdin.read()
        changed = ""
    else:
        msg = args.msg_file.read_text(encoding="utf-8", errors="ignore") if args.msg_file.exists() else ""
        changed = (
            args.changed_file.read_text(encoding="utf-8", errors="ignore")
            if args.changed_file.exists()
            else ""
        )
    data = parse(msg, changed)
    if args.write_env:
        write_env(args.write_env, data)
    for k, v in data.items():
        print(f"{k}={v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
