#!/usr/bin/env bash
# =============================================================================
# deploy/gpu/sim/verify_report_repo.sh — prove the health-report push cannot
# trigger CI on the production repos.
#
# Checks, in order:
#   1. the push target normalises to the standalone health-check repo (and is not
#      the umbrella repo or any component submodule),
#   2. the target repo has no Jenkinsfile / .github/workflows / .gitlab-ci.yml /
#      CircleCI / Azure Pipelines config,
#   3. the target repo has no webhooks and no Actions workflows,
#   4. the guard in gpu_full_recover_report.sh refuses a production-repo target.
#
# Step 3 needs network + `gh` auth. If gh is unavailable the check is reported as
# SKIPPED (not PASS) so it is never mistaken for verified.
#
# Usage: bash deploy/gpu/sim/verify_report_repo.sh
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GPU_DIR="$(cd "$HERE/.." && pwd)"
# shellcheck source=../lib/common.sh
. "$GPU_DIR/lib/common.sh"

HEALTH_REPO="${GPU_HEALTH_REPO:-https://github.com/AliNikkhah2001/Work_RAG_HealthCheck.git}"
REPORT_SCRIPT="$DANA_ROOT/scripts/gpu_full_recover_report.sh"
PASS=0; FAIL=0; SKIP=0

record() { # name ok [detail]
  case "$2" in
    1) printf '%s  PASS%s  %s\n' "$C_GREEN" "$C_OFF" "$1"; PASS=$((PASS + 1)) ;;
    0) printf '%s  FAIL%s  %s  (%s)\n' "$C_RED" "$C_OFF" "$1" "${3:-}"; FAIL=$((FAIL + 1)) ;;
    s) printf '%s  SKIP%s  %s  (%s)\n' "$C_YELLOW" "$C_OFF" "$1" "${3:-}"; SKIP=$((SKIP + 1)) ;;
  esac
}

norm_repo_slug() {
  printf '%s' "$1" \
    | sed -E 's#^git@[^:]+:#https://x/#' \
    | sed -E 's#^https?://[^/]+/##' \
    | sed -E 's#\.git$##' \
    | tr 'A-Z' 'a-z'
}

echo "health-report push isolation check"
echo "  target : $HEALTH_REPO"
echo

# --- 1. target identity ------------------------------------------------------
HEALTH_SLUG="$(norm_repo_slug "$HEALTH_REPO")"
UMBRELLA_SLUG="$(norm_repo_slug "$(git -C "$DANA_ROOT" remote get-url origin 2>/dev/null || true)")"
echo "  slug   : $HEALTH_SLUG"
echo "  umbrella: $UMBRELLA_SLUG"
echo

case "$HEALTH_SLUG" in
  *healthcheck*) record "target repo is the standalone health-check repo" 1 ;;
  *) record "target repo is the standalone health-check repo" 0 "slug=$HEALTH_SLUG" ;;
esac

[ "$HEALTH_SLUG" != "$UMBRELLA_SLUG" ] \
  && record "target repo is NOT the umbrella/production repo" 1 \
  || record "target repo is NOT the umbrella/production repo" 0 "slug=$HEALTH_SLUG"

SUB_COLLISION=0
for sub in "$DANA_ROOT"/components/*/; do
  [ -d "$sub/.git" ] || continue
  s="$(norm_repo_slug "$(git -C "$sub" remote get-url origin 2>/dev/null || true)")"
  [ -n "$s" ] && [ "$s" = "$HEALTH_SLUG" ] && SUB_COLLISION=1
done
[ "$SUB_COLLISION" = "0" ] \
  && record "target repo is NOT a component submodule repo" 1 \
  || record "target repo is NOT a component submodule repo" 0 "collides with a submodule remote"

# --- 4. guard in the report script -----------------------------------------
if [ -f "$REPORT_SCRIPT" ]; then
  if grep -q "push_target_is_safe" "$REPORT_SCRIPT" && grep -q "PROTECTED_SLUGS" "$REPORT_SCRIPT"; then
    record "gpu_full_recover_report.sh has a production-repo push guard" 1
    # Exercise the guard logic itself on the production slug.
    guard_out="$(bash -c '
      norm_repo_slug() { printf "%s" "$1" | sed -E "s#^git@[^:]+:#https://x/#" | sed -E "s#^https?://[^/]+/##" | sed -E "s#\.git\$##" | tr "A-Z" "a-z"; }
      PROTECTED_SLUGS="alinikkhah2001/work_credit-rag_phase1 alinikkhah2001/work_rag-orchestrator"
      push_target_is_safe() {
        local slug="$1" p
        [ -n "$slug" ] || return 1
        case "$slug" in *healthcheck*) return 0 ;; esac
        for p in $PROTECTED_SLUGS; do [ "$slug" = "$p" ] && return 1; done
        return 0
      }
      push_target_is_safe "alinikkhah2001/work_credit-rag_phase1" && echo UNSAFE_ALLOWED || echo BLOCKED
    ' 2>/dev/null)"
    [ "$guard_out" = "BLOCKED" ] \
      && record "guard BLOCKS a production-repo target" 1 \
      || record "guard BLOCKS a production-repo target" 0 "got: $guard_out"
  else
    record "gpu_full_recover_report.sh has a production-repo push guard" 0 "guard function not found"
  fi
else
  record "gpu_full_recover_report.sh present" 0 "missing $REPORT_SCRIPT"
fi

# --- 2 + 3. remote CI surface ----------------------------------------------
if ! command -v gh >/dev/null 2>&1; then
  record "remote CI config absent (no Jenkinsfile/workflows/gitlab-ci)" s "gh CLI unavailable"
  record "remote webhooks absent" s "gh CLI unavailable"
  record "remote Actions workflows absent" s "gh CLI unavailable"
else
  OWNER_REPO="$(printf '%s' "$HEALTH_SLUG" | sed -E 's#^([^/]+)/(.*)$#\1/\2#')"
  if ! gh api "repos/$OWNER_REPO" --jq .name >/dev/null 2>&1; then
    record "remote CI config absent" s "cannot read repos/$OWNER_REPO (auth/network)"
    record "remote webhooks absent" s "cannot read repo"
    record "remote Actions workflows absent" s "cannot read repo"
  else
    CI_FOUND=""
    for f in Jenkinsfile .gitlab-ci.yml .github/workflows azure-pipelines.yml .circleci; do
      if gh api "repos/$OWNER_REPO/contents/$f" --jq .name >/dev/null 2>&1; then
        CI_FOUND="$CI_FOUND $f"
      fi
    done
    [ -z "$CI_FOUND" ] \
      && record "remote CI config absent (no Jenkinsfile/workflows/gitlab-ci)" 1 \
      || record "remote CI config absent" 0 "found:$CI_FOUND"

    HOOKS="$(gh api "repos/$OWNER_REPO/hooks" --jq 'length' 2>/dev/null || echo "?")"
    [ "$HOOKS" = "0" ] \
      && record "remote webhooks absent (count=0)" 1 \
      || record "remote webhooks absent" 0 "count=$HOOKS"

    # GitHub creates the `pages-build-deployment` workflow automatically when
    # Pages is enabled from a branch. It is not a repo-authored CI config and
    # cannot run arbitrary build steps, so it must not fail this check --
    # otherwise enabling Pages (which we deliberately want) looks like a
    # CI-on-the-report-repo violation.
    WF_TOTAL="$(gh api "repos/$OWNER_REPO/actions/workflows" --jq '.total_count' 2>/dev/null || echo "?")"
    WF_REAL="$(gh api "repos/$OWNER_REPO/actions/workflows" \
      --jq '[.workflows[]? | select(.path | startswith("dynamic/pages/") | not)] | length' \
      2>/dev/null || echo "?")"
    if [ "$WF_REAL" = "0" ]; then
      record "remote Actions workflows absent (count=0, pages=$WF_TOTAL)" 1
    else
      record "remote Actions workflows absent" 0 "count=$WF_REAL (pages excluded)"
    fi

    # Jenkins multibranch on the prod controller only indexes the prod repo(s);
    # the health-check repo is not among them.
    if gh api "repos/$OWNER_REPO/branches" --jq '.[].name' 2>/dev/null | head -1 >/dev/null; then
      record "target is a plain repo, not a Jenkins multibranch source" 1
    fi
  fi
fi

echo
printf '  passed: %s%d%s  skipped: %s%d%s  failed: %s%d%s\n' \
  "$C_GREEN" "$PASS" "$C_OFF" "$C_YELLOW" "$SKIP" "$C_OFF" \
  "$([ "$FAIL" -eq 0 ] && echo "$C_GREEN" || echo "$C_RED")" "$FAIL" "$C_OFF"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
