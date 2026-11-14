#!/usr/bin/env bash
# =============================================================================
# ci_stage_evidence.sh — record which pipeline stages really ran, and report
# per-stage GitHub commit statuses.
#
# Why: a stage-only controller drops every prod stage, so a `main` build used to
# finish SUCCESS after running only Lint. GitHub then showed a green check for a
# commit no build/deploy/E2E ever touched (`dana-rag/main` #20, #21). Evidence
# files let scripts/ci_verify_coverage.py prove what actually happened, and the
# per-stage statuses make each claim individually visible on the commit.
#
# Subcommands
#   mark <stage>                       record that <stage> executed
#   list                               print executed stages (space separated)
#   report <stage> <success|failure> [description]
#                                      post a `dana/<stage>` commit status
#   contexts                           print the status contexts this file owns
#
# Reporting is opt-in: needs GITHUB_STATUS_ENABLED=1 AND GITHUB_TOKEN. Without
# either it prints why and exits 0, so a credential-less agent still builds.
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EVIDENCE_DIR="${CI_EVIDENCE_DIR:-.ci-evidence}"
REPORT_SCRIPT="${SCRIPT_DIR}/ci_github_status.sh"
REPO_DEFAULT="${GITHUB_REPO:-AliNikkhah2001/Work_Credit-RAG_Phase1}"

VALID_STAGES="lint build stage-deploy stage-e2e prod-deploy"

die() {
  echo "ci_stage_evidence: $*" >&2
  exit 2
}

is_valid_stage() {
  case " ${VALID_STAGES} " in
    *" $1 "*) return 0 ;;
    *) return 1 ;;
  esac
}

require_stage() {
  [[ $# -ge 1 && -n "${1:-}" ]] || die "missing <stage>"
  is_valid_stage "$1" || die "unknown stage '$1' (valid: ${VALID_STAGES})"
}

cmd_mark() {
  require_stage "$@"
  mkdir -p "$EVIDENCE_DIR"
  # Content is the Jenkins build tag when available — handy when inspecting a
  # workspace after the fact, but nothing parses it.
  printf '%s\n' "${BUILD_TAG:-local}" > "${EVIDENCE_DIR}/$1"
  echo "ci_stage_evidence: marked $1"
}

cmd_list() {
  local ran=""
  for stage in $VALID_STAGES; do
    if [[ -f "${EVIDENCE_DIR}/${stage}" ]]; then
      ran="${ran}${ran:+ }${stage}"
    fi
  done
  printf '%s\n' "$ran"
}

cmd_contexts() {
  for stage in $VALID_STAGES; do
    printf 'dana/%s\n' "$stage"
  done
  printf 'dana/verify\n'
}

cmd_report() {
  require_stage "$1"
  local stage="$1"
  local state="${2:-}"
  local description="${3:-Jenkins ${stage}}"

  case "$state" in
    success|failure|pending|error) ;;
    *) die "state must be success|failure|pending|error (got '${state:-<empty>}')" ;;
  esac

  if [[ "${GITHUB_STATUS_ENABLED:-0}" != "1" ]]; then
    echo "ci_stage_evidence: GITHUB_STATUS_ENABLED!=1 — not reporting dana/${stage}"
    return 0
  fi
  if [[ -z "${GITHUB_TOKEN:-}" ]]; then
    echo "ci_stage_evidence: GITHUB_TOKEN empty — not reporting dana/${stage}" >&2
    return 0
  fi
  if [[ -z "${GIT_COMMIT:-}" ]]; then
    echo "ci_stage_evidence: GIT_COMMIT empty — not reporting dana/${stage}" >&2
    return 0
  fi
  [[ -x "$REPORT_SCRIPT" ]] || [[ -f "$REPORT_SCRIPT" ]] || die "missing ${REPORT_SCRIPT}"

  bash "$REPORT_SCRIPT" \
    --sha "$GIT_COMMIT" \
    --state "$state" \
    --context "dana/${stage}" \
    --description "$description" \
    --target-url "${BUILD_URL:-}" \
    --repo "$REPO_DEFAULT"
}

main() {
  local sub="${1:-}"
  [[ $# -gt 0 ]] && shift
  case "$sub" in
    mark) cmd_mark "$@" ;;
    list) cmd_list ;;
    contexts) cmd_contexts ;;
    report) cmd_report "$@" ;;
    ""|-h|--help|help) sed -n '1,30p' "$0" ;;
    *) die "unknown subcommand '$sub'" ;;
  esac
}

main "$@"
