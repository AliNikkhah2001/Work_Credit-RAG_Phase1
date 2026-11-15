#!/usr/bin/env bash
# Tag-then-delete stale remote branches. Keep only main + develop (or master).
# Usage: bash scripts/prune_stale_branches.sh [--dry-run]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1

# Branches we always keep on the umbrella repo.
KEEP_RE='^(main|develop|master)$'

prune_repo() {
  local path="$1" prod="$2"
  local cwd
  if [[ "$path" == "." ]]; then cwd="$ROOT"; else cwd="$ROOT/$path"; fi
  if [[ ! -d "$cwd/.git" && ! -f "$cwd/.git" ]]; then
    echo "=== $path (skip: not a git checkout) ==="
    return 0
  fi
  echo "=== $path (prod=$prod) ==="
  git -C "$cwd" fetch origin --prune
  local branches
  # Delete feature/*, chore/*, fix/*, release/*, sync/*, legacy/*, Deprecated/*, vast-*, deepseek*
  # after archiving as tags. Never delete main/develop/master.
  branches=$(git -C "$cwd" branch -r | sed 's|^ *||' | grep -E '^origin/' | grep -v 'origin/HEAD' || true)
  while IFS= read -r b; do
    [[ -z "$b" ]] && continue
    local short="${b#origin/}"
    if [[ "$short" =~ $KEEP_RE ]]; then
      echo "  keep $short"
      continue
    fi
    # Only prune known ephemeral prefixes (avoid deleting unexpected protected names).
    if ! [[ "$short" =~ ^(feature/|chore/|fix/|release/|sync/|legacy/|Deprecated/|vast-|deepseek|ops/) ]]; then
      echo "  skip (unknown prefix): $short"
      continue
    fi
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
prune_repo "components/webui" main 2>/dev/null || true

echo "Done. Review tags archive/* if anything must be restored."
