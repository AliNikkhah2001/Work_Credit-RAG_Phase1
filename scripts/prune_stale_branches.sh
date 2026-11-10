#!/usr/bin/env bash
# Tag-then-delete stale remote branches per docs/cleanup/stale-branch-inventory.json
# Usage: bash scripts/prune_stale_branches.sh [--dry-run]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1

prune_repo() {
  local path="$1" prod="$2"
  local cwd
  if [[ "$path" == "." ]]; then cwd="$ROOT"; else cwd="$ROOT/$path"; fi
  echo "=== $path (prod=$prod) ==="
  git -C "$cwd" fetch origin --prune
  local branches
  branches=$(git -C "$cwd" branch -r | sed 's|^ *||' | grep -E '^origin/(legacy/|Deprecated/|vast-|chore/|deepseek)' || true)
  while IFS= read -r b; do
    [[ -z "$b" ]] && continue
    local short="${b#origin/}"
    local tip
    tip=$(git -C "$cwd" rev-parse --short "$b")
    local tag="archive/${short//\//-}"
    echo "  $short @ $tip -> tag $tag then delete"
    if [[ $DRY -eq 1 ]]; then continue; fi
    git -C "$cwd" tag -f "$tag" "$b" || true
    git -C "$cwd" push -f origin "refs/tags/$tag" || true
    git -C "$cwd" push origin --delete "$short" || echo "  warn: could not delete $short"
  done <<< "$branches"
}

prune_repo "." main
prune_repo "agent-state" main
prune_repo "components/guardrails" main
prune_repo "components/knowledgebase" master
prune_repo "components/orchestrator" main
prune_repo "components/server-setup" main

echo "Done. Review tags archive/* if anything must be restored."
