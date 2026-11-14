#!/usr/bin/env python3
"""Decide whether a Jenkins build actually verified anything (true-green gate).

Problem this solves
-------------------
A stage-only controller sets ``CI_MAY_DEPLOY_PROD=0``, so every prod stage is
dropped by its ``when`` guard. A ``main`` build then finishes ``SUCCESS`` after
running only Lint, and GitHub shows a green commit check for a commit that no
build, deploy or E2E probe ever touched (observed on ``dana-rag/main`` #20 and
#21). That is a false green.

This module turns "which stages really ran" into an explicit verdict plus a
guard action, so the Jenkinsfile can stop claiming success it did not earn.

Verdicts
--------
covered              The stages this branch/trigger expected all ran.
unexpected-missing   A stage that should have run did not -> real failure.
structurally-skipped The controller cannot run the required stage at all
                     (e.g. ``main`` on a stage-only controller). Truthful but
                     configurable: the laptop is not forced to go red.
opted-out            The commit said ``[ci skip]`` / ``[skip ci]``.

Exit status is always 0 unless the caller asked for ``--strict``; the verdict
is consumed through ``--write-env`` so a failed gate is a Jenkins decision, not
a shell quirk.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable

LINT = "lint"
BUILD = "build"
STAGE_DEPLOY = "stage-deploy"
STAGE_E2E = "stage-e2e"
PROD_DEPLOY = "prod-deploy"

VALID_STAGES = (LINT, BUILD, STAGE_DEPLOY, STAGE_E2E, PROD_DEPLOY)

COVERED = "covered"
UNEXPECTED_MISSING = "unexpected-missing"
STRUCTURALLY_SKIPPED = "structurally-skipped"
OPTED_OUT = "opted-out"

GUARD_PASS = "pass"
GUARD_UNSTABLE = "unstable"
GUARD_FAIL = "fail"

# GitHub commit-status descriptions are capped at 140 chars.
DESC_LIMIT = 140


def parse_executed(raw: str) -> frozenset[str]:
    """Parse a comma/space separated stage list into a set of known stages.

    Args:
        raw: e.g. ``"lint build prod-deploy"`` or ``"lint,build"``.

    Returns:
        Recognised stage names only (unknown tokens are dropped).
    """
    tokens = {t.strip() for part in (raw or "").replace(",", " ").split() for t in [part]}
    return frozenset(t for t in tokens if t in VALID_STAGES)


def _fmt(stages: Iterable[str]) -> str:
    """Render stage names in canonical order for stable, readable output."""
    present = set(stages)
    ordered = [s for s in VALID_STAGES if s in present]
    return ",".join(ordered) if ordered else "none"


def decide(
    branch: str,
    executed: frozenset[str],
    *,
    may_deploy_stage: bool,
    may_deploy_prod: bool,
    ci_skip: bool,
    ci_stage: bool,
    ci_prod: bool,
    ci_auto: bool,
    ci_build: bool,
    heavy_paths: bool,
    require_prod_controller: bool,
) -> dict[str, str]:
    """Compute the verification verdict for one build.

    Args:
        branch: Jenkins ``BRANCH_NAME`` (``main``, ``develop``, ``PR-12``...).
        executed: Stages that really ran, from stage-level ``post`` markers.
        may_deploy_stage: Controller is allowed to deploy stage.
        may_deploy_prod: Controller is allowed to deploy prod.
        ci_skip: Commit asked to skip CI.
        ci_stage: Commit asked for a stage deploy.
        ci_prod: Commit asked for a prod deploy.
        ci_auto: Commit asked for unattended deploy.
        ci_build: Commit asked for an image build.
        heavy_paths: Changed paths force a build.
        require_prod_controller: This controller is expected to verify prod
            (set on the GPU/prod host). Turns a missing prod proof into a hard
            failure instead of a configurable warning.

    Returns:
        Mapping with ``verdict``, ``ran``, ``expected``, ``missing``,
        ``state`` (GitHub commit-status state), ``description`` and ``guard``
        (``pass`` / ``unstable`` / ``fail``).
    """
    branch = (branch or "").strip()
    ran = frozenset(executed) & frozenset(VALID_STAGES)

    def result(verdict: str, expected: Iterable[str], guard: str, description: str) -> dict[str, str]:
        expected_set = frozenset(expected)
        missing = expected_set - ran
        # The commit status must never claim success unless the build is either
        # fully covered or the commit explicitly opted out of verification.
        state = "success" if verdict in (COVERED, OPTED_OUT) else "failure"
        return {
            "verdict": verdict,
            "ran": _fmt(ran),
            "expected": _fmt(expected_set),
            "missing": _fmt(missing),
            "state": state,
            "description": description[:DESC_LIMIT],
            "guard": guard,
        }

    if ci_skip:
        return result(
            OPTED_OUT,
            (),
            GUARD_PASS,
            "no verification requested ([ci skip])",
        )

    # ---- production branch -------------------------------------------------
    if branch == "main":
        if not may_deploy_prod:
            # The structural false green: prod stages are unreachable here.
            expected = [LINT]
            if ci_prod or ci_auto or ci_build or heavy_paths:
                expected = [LINT, BUILD, PROD_DEPLOY]
            guard = GUARD_FAIL if require_prod_controller else GUARD_UNSTABLE
            return result(
                STRUCTURALLY_SKIPPED,
                expected,
                guard,
                "main NOT verified: no prod controller (DANA_ROLE=stage)",
            )

        # Real prod controller: a main tip is only proven by a prod deploy.
        expected = [LINT, BUILD, PROD_DEPLOY]
        missing = frozenset(expected) - ran
        if missing:
            return result(
                UNEXPECTED_MISSING,
                expected,
                GUARD_FAIL,
                "main missing prod verification: " + _fmt(missing),
            )
        return result(COVERED, expected, GUARD_PASS, "verified: " + _fmt(ran))

    # ---- integration branch ------------------------------------------------
    if branch == "develop":
        if not may_deploy_stage:
            return result(
                STRUCTURALLY_SKIPPED,
                (LINT,),
                GUARD_UNSTABLE,
                "develop not verified: controller cannot deploy stage",
            )
        wants_deploy = ci_stage or ci_auto
        expected = [LINT, BUILD, STAGE_DEPLOY, STAGE_E2E] if wants_deploy else [LINT]
        missing = frozenset(expected) - ran
        if missing:
            trigger = "[ci stage]" if ci_stage else "[ci auto]"
            return result(
                UNEXPECTED_MISSING,
                expected,
                GUARD_FAIL,
                f"requested {trigger} but missing: " + _fmt(missing),
            )
        return result(COVERED, expected, GUARD_PASS, "verified: " + _fmt(ran))

    # ---- feature branches / pull requests ----------------------------------
    expected = [LINT, BUILD] if (ci_build or heavy_paths) else [LINT]
    missing = frozenset(expected) - ran
    if missing:
        return result(
            UNEXPECTED_MISSING,
            expected,
            GUARD_FAIL,
            "pr/feature build missing: " + _fmt(missing),
        )
    return result(COVERED, expected, GUARD_PASS, "verified: " + _fmt(ran))


def _flag(value: str | bool | None) -> bool:
    """Coerce the many ways Jenkins/env express a boolean to ``True``/``False``."""
    if isinstance(value, bool):
        return value
    return str(value or "").strip() in ("1", "true", "True", "yes", "on")


def to_env(verdict: dict[str, str]) -> str:
    """Render the verdict as ``KEY=value`` lines for Jenkins ``readFile``."""
    lines = [
        f"COVERAGE_VERDICT={verdict['verdict']}",
        f"COVERAGE_RAN={verdict['ran']}",
        f"COVERAGE_EXPECTED={verdict['expected']}",
        f"COVERAGE_MISSING={verdict['missing']}",
        f"COVERAGE_STATE={verdict['state']}",
        f"COVERAGE_DESCRIPTION={verdict['description']}",
        f"COVERAGE_GUARD={verdict['guard']}",
    ]
    return "\n".join(lines) + "\n"


def self_test() -> None:
    """Assert the decision table that the Jenkinsfile depends on."""
    ok = decide(
        "main",
        frozenset({LINT, BUILD, PROD_DEPLOY}),
        may_deploy_stage=False,
        may_deploy_prod=True,
        ci_skip=False,
        ci_stage=False,
        ci_prod=True,
        ci_auto=False,
        ci_build=False,
        heavy_paths=False,
        require_prod_controller=True,
    )
    assert ok["verdict"] == COVERED and ok["guard"] == GUARD_PASS, ok

    # The exact #20/#21 shape: main, stage controller, nothing but lint.
    false_green = decide(
        "main",
        frozenset({LINT}),
        may_deploy_stage=True,
        may_deploy_prod=False,
        ci_skip=False,
        ci_stage=False,
        ci_prod=True,
        ci_auto=False,
        ci_build=False,
        heavy_paths=True,
        require_prod_controller=False,
    )
    assert false_green["verdict"] == STRUCTURALLY_SKIPPED, false_green
    assert false_green["state"] == "failure", false_green
    assert false_green["guard"] == GUARD_UNSTABLE, false_green
    assert false_green["missing"] == "build,prod-deploy", false_green

    # Same shape but the host is supposed to own prod -> loud failure.
    loud = decide(
        "main",
        frozenset({LINT}),
        may_deploy_stage=False,
        may_deploy_prod=False,
        ci_skip=False,
        ci_stage=False,
        ci_prod=True,
        ci_auto=False,
        ci_build=False,
        heavy_paths=False,
        require_prod_controller=True,
    )
    assert loud["guard"] == GUARD_FAIL, loud

    # Prod controller that skipped the deploy entirely: real failure.
    broken = decide(
        "main",
        frozenset({LINT, BUILD}),
        may_deploy_stage=False,
        may_deploy_prod=True,
        ci_skip=False,
        ci_stage=False,
        ci_prod=True,
        ci_auto=False,
        ci_build=False,
        heavy_paths=False,
        require_prod_controller=True,
    )
    assert broken["verdict"] == UNEXPECTED_MISSING and broken["missing"] == "prod-deploy", broken
    assert broken["guard"] == GUARD_FAIL and broken["state"] == "failure", broken

    stage_ok = decide(
        "develop",
        frozenset({LINT, BUILD, STAGE_DEPLOY, STAGE_E2E}),
        may_deploy_stage=True,
        may_deploy_prod=False,
        ci_skip=False,
        ci_stage=True,
        ci_prod=False,
        ci_auto=False,
        ci_build=False,
        heavy_paths=False,
        require_prod_controller=False,
    )
    assert stage_ok["verdict"] == COVERED and stage_ok["guard"] == GUARD_PASS, stage_ok

    stage_short = decide(
        "develop",
        frozenset({LINT, BUILD}),
        may_deploy_stage=True,
        may_deploy_prod=False,
        ci_skip=False,
        ci_stage=True,
        ci_prod=False,
        ci_auto=False,
        ci_build=False,
        heavy_paths=False,
        require_prod_controller=False,
    )
    assert stage_short["verdict"] == UNEXPECTED_MISSING, stage_short
    assert stage_short["missing"] == "stage-deploy,stage-e2e", stage_short
    assert stage_short["guard"] == GUARD_FAIL, stage_short

    skipped = decide(
        "main",
        frozenset(),
        may_deploy_stage=True,
        may_deploy_prod=False,
        ci_skip=True,
        ci_stage=False,
        ci_prod=False,
        ci_auto=False,
        ci_build=False,
        heavy_paths=False,
        require_prod_controller=True,
    )
    assert skipped["verdict"] == OPTED_OUT and skipped["state"] == "success", skipped

    feature = decide(
        "feature/x",
        frozenset({LINT, BUILD}),
        may_deploy_stage=True,
        may_deploy_prod=False,
        ci_skip=False,
        ci_stage=False,
        ci_prod=False,
        ci_auto=False,
        ci_build=True,
        heavy_paths=False,
        require_prod_controller=False,
    )
    assert feature["verdict"] == COVERED, feature

    # Regression: a docs-only feature commit asked for nothing (CI_SERVICES=none,
    # no [ci ...] markers), so the Lint stage's old guard dropped it too and the
    # build ran zero stages -> red `dana/validate` on a perfectly good commit
    # (build #3 of feature/lastgood-retention). The Jenkinsfile now runs Lint
    # unconditionally; the verifier still owes `lint` here, and that is
    # satisfiable. Guard against anyone re-narrowing the Lint stage.
    docs_only = decide(
        "feature/docs-only",
        frozenset({LINT}),
        may_deploy_stage=True,
        may_deploy_prod=False,
        ci_skip=False,
        ci_stage=False,
        ci_prod=False,
        ci_auto=False,
        ci_build=False,
        heavy_paths=False,
        require_prod_controller=False,
    )
    assert docs_only["verdict"] == COVERED, docs_only
    assert docs_only["state"] == "success", docs_only

    # And if Lint really did not run, the verdict must stay red (no silent pass).
    docs_only_unrun = decide(
        "feature/docs-only",
        frozenset(),
        may_deploy_stage=True,
        may_deploy_prod=False,
        ci_skip=False,
        ci_stage=False,
        ci_prod=False,
        ci_auto=False,
        ci_build=False,
        heavy_paths=False,
        require_prod_controller=False,
    )
    assert docs_only_unrun["verdict"] == UNEXPECTED_MISSING, docs_only_unrun
    assert docs_only_unrun["state"] == "failure", docs_only_unrun
    assert docs_only_unrun["missing"] == "lint", docs_only_unrun

    assert len(long_desc_guard()) <= DESC_LIMIT
    assert parse_executed("lint, build  bogus prod-deploy") == frozenset({LINT, BUILD, PROD_DEPLOY})

    # A structurally-skipped build must never publish `success`, on any branch.
    for branch, kwargs in (
        ("develop", dict(may_deploy_stage=False, may_deploy_prod=False, ci_stage=True)),
        ("main", dict(may_deploy_stage=True, may_deploy_prod=False, ci_prod=True)),
    ):
        verdict = decide(
            branch,
            frozenset({LINT}),
            ci_skip=False,
            ci_prod=kwargs.get("ci_prod", False),
            ci_stage=kwargs.get("ci_stage", False),
            ci_auto=False,
            ci_build=False,
            heavy_paths=False,
            require_prod_controller=False,
            **{k: v for k, v in kwargs.items() if k.startswith("may_")},
        )
        assert verdict["state"] == "failure", (branch, verdict)
        assert verdict["guard"] == GUARD_UNSTABLE, (branch, verdict)

    print("ci_verify_coverage self-test OK")


def long_desc_guard() -> str:
    """Return the longest description this module can emit (for the length assert)."""
    worst = decide(
        "develop",
        frozenset({LINT}),
        may_deploy_stage=True,
        may_deploy_prod=False,
        ci_skip=False,
        ci_stage=True,
        ci_prod=False,
        ci_auto=False,
        ci_build=False,
        heavy_paths=False,
        require_prod_controller=False,
    )
    return worst["description"]


def main() -> int:
    """CLI entry point used by the Jenkinsfile."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--branch", default=os.environ.get("BRANCH_NAME", ""))
    ap.add_argument("--executed", default="", help="stages that ran, comma/space separated")
    ap.add_argument("--may-deploy-stage", default=os.environ.get("CI_MAY_DEPLOY_STAGE", "0"))
    ap.add_argument("--may-deploy-prod", default=os.environ.get("CI_MAY_DEPLOY_PROD", "0"))
    ap.add_argument("--ci-skip", default=os.environ.get("CI_SKIP", "0"))
    ap.add_argument("--ci-stage", default=os.environ.get("CI_STAGE", "0"))
    ap.add_argument("--ci-prod", default=os.environ.get("CI_PROD", "0"))
    ap.add_argument("--ci-auto", default=os.environ.get("CI_AUTO", "0"))
    ap.add_argument("--ci-build", default=os.environ.get("CI_BUILD", "0"))
    ap.add_argument("--heavy-paths", default=os.environ.get("CI_HEAVY_PATHS", "0"))
    ap.add_argument(
        "--require-prod-controller",
        default=os.environ.get("CI_REQUIRE_PROD_CONTROLLER", "0"),
        help="this host is expected to verify prod",
    )
    ap.add_argument("--write-env", default="")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 when the guard is 'fail'")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    verdict = decide(
        args.branch,
        parse_executed(args.executed),
        may_deploy_stage=_flag(args.may_deploy_stage),
        may_deploy_prod=_flag(args.may_deploy_prod),
        ci_skip=_flag(args.ci_skip),
        ci_stage=_flag(args.ci_stage),
        ci_prod=_flag(args.ci_prod),
        ci_auto=_flag(args.ci_auto),
        ci_build=_flag(args.ci_build),
        heavy_paths=_flag(args.heavy_paths),
        require_prod_controller=_flag(args.require_prod_controller),
    )
    text = to_env(verdict)
    if args.write_env:
        with open(args.write_env, "w", encoding="utf-8") as fh:
            fh.write(text)
    sys.stdout.write(text)
    if args.strict and verdict["guard"] == GUARD_FAIL:
        print(
            f"ci_verify_coverage: GUARD FAIL — {verdict['description']}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
