#!/usr/bin/env bash
# Sprint B #2 — resilient submodule sync after Jenkins checkout scm.
# Retries fetch/update; fails loudly if a gitlink SHA is missing on the remote.
set -euo pipefail

MAX_ATTEMPTS="${CI_SUBMODULE_ATTEMPTS:-3}"
SLEEP_SECS="${CI_SUBMODULE_SLEEP:-5}"

attempt=1
while true; do
  echo "ci_submodule_sync: attempt ${attempt}/${MAX_ATTEMPTS}"
  set +e
  out="$(git submodule sync --recursive 2>&1)"
  rc1=$?
  out2="$(git submodule update --init --recursive --depth 1 2>&1)"
  rc2=$?
  # deepen if shallow miss (ignore failures)
  git submodule foreach --recursive 'git fetch --unshallow 2>/dev/null || git fetch --tags --force origin 2>/dev/null || true' >/dev/null 2>&1
  out3="$(git submodule update --init --recursive 2>&1)"
  rc3=$?
  set -e
  echo "$out"
  echo "$out2"
  echo "$out3"
  if [ "$rc1" -eq 0 ] && [ "$rc3" -eq 0 ]; then
    echo "ci_submodule_sync: OK"
    git submodule status --recursive | head -40
    exit 0
  fi
  combined="${out}${out2}${out3}"
  if echo "$combined" | grep -qiE 'not our ref|could not find remote ref|fatal: remote error'; then
    echo "ci_submodule_sync: ERROR — submodule gitlink SHA not reachable on remote."
    echo "Push the submodule commit first, then re-run. Details above."
    if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
      exit 2
    fi
  fi
  if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
    echo "ci_submodule_sync: ERROR — exhausted retries (rc sync=$rc1 update=$rc2/$rc3)"
    exit 1
  fi
  attempt=$((attempt + 1))
  sleep "$SLEEP_SECS"
done
