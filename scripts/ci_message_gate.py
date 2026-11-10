#!/usr/bin/env python3
"""Parse commit message + changed paths into CI gate env vars for Jenkins.

Keys (case-insensitive):
  [ci skip] / [skip ci]
  [ci build]
  [ci stage]
  [ci auto]
  [ci prod]

Usage:
  python3 scripts/ci_message_gate.py --write-env .ci_gate.env
  python3 scripts/ci_message_gate.py --self-test
  echo '[ci stage] feat: x' | python3 scripts/ci_message_gate.py --msg-stdin
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


def parse(msg: str, changed: str) -> dict[str, str]:
    low = (msg or "").lower()
    skip = "[ci skip]" in low or "[skip ci]" in low
    build = "[ci build]" in low
    stage = "[ci stage]" in low
    prod = "[ci prod]" in low
    auto = "[ci auto]" in low
    heavy = any(HEAVY.search(line) for line in (changed or "").splitlines())
    return {
        "CI_SKIP": "1" if skip else "0",
        "CI_BUILD": "1" if build else "0",
        "CI_STAGE": "1" if stage else "0",
        "CI_PROD": "1" if prod else "0",
        "CI_AUTO": "1" if auto else "0",
        "CI_HEAVY_PATHS": "1" if heavy else "0",
    }


def write_env(path: Path, data: dict[str, str]) -> None:
    path.write_text("\n".join(f"{k}={v}" for k, v in data.items()) + "\n", encoding="utf-8")


def self_test() -> None:
    cases = [
        ("docs only", "docs: typo", "README.md", {"CI_SKIP": "0", "CI_STAGE": "0", "CI_HEAVY_PATHS": "0"}),
        ("skip", "chore: x [ci skip]", "deploy/compose/compose.base.yml", {"CI_SKIP": "1"}),
        ("stage", "feat: y [ci stage]", "docs/a.md", {"CI_STAGE": "1", "CI_SKIP": "0"}),
        ("prod auto", "release [ci prod]", "Jenkinsfile", {"CI_PROD": "1"}),
        ("auto", "ship [ci auto]", "components/orchestrator/Dockerfile", {"CI_AUTO": "1", "CI_HEAVY_PATHS": "1"}),
        ("build", "rebuild [ci build]", "eval/x.md", {"CI_BUILD": "1"}),
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
