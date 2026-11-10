#!/usr/bin/env bash
# Sprint B #2 — resilient submodule sync after Jenkins checkout scm.
# Retries fetch/update; fails loudly if a *required* (top-level) gitlink SHA is missing.
#
# Nested corpus `components/knowledgebase/kb-source` is optional for CI image builds
# (KB Dockerfile does not COPY it). Unreachable kb-source pins warn but do not fail CI.
set -euo pipefail

MAX_ATTEMPTS="${CI_SUBMODULE_ATTEMPTS:-3}"
SLEEP_SECS="${CI_SUBMODULE_SLEEP:-5}"

is_only_optional_nested_failure() {
  # True when failure text is about kb-source / recurse into knowledgebase for that pin.
  local text="$1"
  echo "$text" | grep -qiE 'not our ref|could not find remote ref|fatal: remote error|Failed to recurse|fatal:' || return 1
  # Must mention kb-source (the optional nested pin)
  echo "$text" | grep -q 'kb-source' || return 1
  # Strip kb-source / knowledgebase recurse lines; any remaining fatal → not optional-only
  local rest
  rest="$(echo "$text" | grep -viE 'kb-source|Failed to recurse into submodule path .components/knowledgebase' || true)"
  if echo "$rest" | grep -qiE 'not our ref|could not find remote ref|fatal: remote error|Failed to recurse|fatal:'; then
    return 1
  fi
  return 0
}

# CI workspace is disposable. Local edits (docker cp, hotpatches, interrupted
# checkouts) otherwise block `submodule update` and leave stage on a stale pin
# while the parent gitlink already advanced — classic laptop Jenkins race.
reset_dirty_submodules() {
  echo "ci_submodule_sync: resetting dirty submodule worktrees (CI_FORCE_CLEAN=${CI_FORCE_CLEAN:-1})"
  if [ "${CI_FORCE_CLEAN:-1}" != "1" ]; then
    return 0
  fi
  git submodule foreach --recursive '
    git reset --hard HEAD >/dev/null 2>&1 || true
    git clean -fd >/dev/null 2>&1 || true
  ' || true
}

attempt=1
while true; do
  echo "ci_submodule_sync: attempt ${attempt}/${MAX_ATTEMPTS}"
  set +e
  out_sync="$(git submodule sync --recursive 2>&1)"
  rc_sync=$?

  reset_dirty_submodules

  # Required: top-level component pins (kb, orchestrator, guardrails, webui, …)
  # --force: discard checked-out divergence so parent pins always win in CI.
  out_top="$(git submodule update --init --force --depth 1 2>&1)"
  rc_top=$?

  # Optional: full recurse (includes kb-source corpus). Soft-fail if only that pin breaks.
  git submodule foreach --recursive \
    'git fetch --unshallow 2>/dev/null || git fetch --tags --force origin 2>/dev/null || true' \
    >/dev/null 2>&1
  out_nest="$(git submodule update --init --force --recursive --depth 1 2>&1; git submodule update --init --force --recursive 2>&1)"
  rc_nest=$?
  set -e

  echo "$out_sync"
  echo "$out_top"
  echo "$out_nest"

  if [ "$rc_sync" -eq 0 ] && [ "$rc_top" -eq 0 ]; then
    if [ "$rc_nest" -eq 0 ]; then
      echo "ci_submodule_sync: OK"
      git submodule status | head -40
      git submodule status --recursive 2>/dev/null | head -60 || true
      exit 0
    fi
    if is_only_optional_nested_failure "$out_nest"; then
      echo "ci_submodule_sync: WARNING — optional nested kb-source unreachable; continuing (CI images do not need corpus)."
      echo "ci_submodule_sync: OK (top-level)"
      git submodule status | head -40
      exit 0
    fi
  fi

  combined="${out_sync}${out_top}${out_nest}"
  if echo "$combined" | grep -qiE 'not our ref|could not find remote ref|fatal: remote error'; then
    echo "ci_submodule_sync: ERROR — submodule gitlink SHA not reachable on remote."
    echo "Push the submodule commit first, then re-run. Details above."
    if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
      exit 2
    fi
  fi
  if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
    echo "ci_submodule_sync: ERROR — exhausted retries (rc sync=$rc_sync top=$rc_top nest=$rc_nest)"
    exit 1
  fi
  attempt=$((attempt + 1))
  sleep "$SLEEP_SECS"
done
