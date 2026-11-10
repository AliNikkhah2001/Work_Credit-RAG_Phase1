#!/usr/bin/env python3
"""Resolve and validate Jenkins controller role (Sprint A).

DANA_ROLE=stage  → laptop Multibranch (develop / feature); stage deploy only
DANA_ROLE=prod   → GPU Multibranch (main); prod deploy only

If DANA_ROLE unset: DANA_HOST=gpu → prod, else stage.
"""
from __future__ import annotations

import argparse
import os
import sys


def resolve(role: str | None, host: str | None) -> str:
    r = (role or "").strip().lower()
    if r in ("stage", "prod"):
        return r
    h = (host or "").strip().lower()
    return "prod" if h == "gpu" else "stage"


def may_deploy_stage(role: str) -> bool:
    return role == "stage"


def may_deploy_prod(role: str) -> bool:
    return role == "prod"


def self_test() -> None:
    assert resolve("stage", "gpu") == "stage"
    assert resolve("prod", "laptop") == "prod"
    assert resolve(None, "gpu") == "prod"
    assert resolve(None, "laptop") == "stage"
    assert resolve("", "") == "stage"
    assert may_deploy_stage("stage") and not may_deploy_stage("prod")
    assert may_deploy_prod("prod") and not may_deploy_prod("stage")
    print("ci_controller_role self-test OK")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--write-env", type=str, default="")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    role = resolve(os.environ.get("DANA_ROLE"), os.environ.get("DANA_HOST"))
    lines = [
        f"DANA_ROLE={role}",
        f"CI_MAY_DEPLOY_STAGE={'1' if may_deploy_stage(role) else '0'}",
        f"CI_MAY_DEPLOY_PROD={'1' if may_deploy_prod(role) else '0'}",
    ]
    text = "\n".join(lines) + "\n"
    if args.write_env:
        with open(args.write_env, "w", encoding="utf-8") as f:
            f.write(text)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
