#!/usr/bin/env bash
# Sprint C #3 — promote develop → main with submodule pin report.
# Default: dry-run (print only). Use --execute to merge locally; --push to push main.
#
#   bash scripts/promote_stage_to_main.sh
#   bash scripts/promote_stage_to_main.sh --execute
#   bash scripts/promote_stage_to_main.sh --execute --push
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

EXECUTE=0
PUSH=0
for arg in "$@"; do
  case "$arg" in
    --execute) EXECUTE=1 ;;
    --push) PUSH=1 ;;
    -h|--help)
      sed -n '1,12p' "$0"
      exit 0
      ;;
  esac
done

echo "=== Promote stage → main (Sprint C #3) ==="
echo "repo: $ROOT"
echo

git fetch origin develop main 2>/dev/null || true

DEV_SHA="$(git rev-parse origin/develop 2>/dev/null || git rev-parse develop)"
MAIN_SHA="$(git rev-parse origin/main 2>/dev/null || git rev-parse main)"
echo "origin/develop: ${DEV_SHA:0:12}"
echo "origin/main:    ${MAIN_SHA:0:12}"
echo

echo "--- Submodule pins on origin/develop ---"
git ls-tree origin/develop components/knowledgebase components/guardrails \
  components/orchestrator components/server-setup components/webui agent-state 2>/dev/null \
  | awk '{print $3, $4}' || git submodule status
echo

AHEAD="$(git rev-list --count origin/main..origin/develop 2>/dev/null || echo "?")"
echo "commits on develop not in main: $AHEAD"
echo

MSG="chore: promote stage pins to main [ci prod]

Promoted from develop ${DEV_SHA:0:12}.
Submodule pins: see promote dry-run output / PR body."

echo "--- Suggested commit / PR title ---"
echo "chore: promote stage pins to main [ci prod]"
echo
echo "--- Suggested body ---"
cat <<EOF
## Summary
- Promote \`develop\` → \`main\` after stage green.
- develop tip: \`${DEV_SHA:0:12}\`

## Submodule pins (develop)
\`\`\`
$(git ls-tree origin/develop components/knowledgebase components/guardrails components/orchestrator components/server-setup components/webui agent-state 2>/dev/null | awk '{print $4, $3}' || true)
\`\`\`

## Test plan
- [ ] Stage Jenkins last build green on develop
- [ ] After merge: GPU/prod Jenkins picks up [ci prod] (or Scan Now)
EOF
echo

if [ "$EXECUTE" != "1" ]; then
  echo "Dry-run only. Re-run with --execute to merge develop into main locally."
  echo "Add --push to push origin/main (requires --execute)."
  exit 0
fi

git checkout main
git pull --ff-only origin main || true
git merge --no-ff origin/develop -m "$MSG" || git merge --no-ff develop -m "$MSG"
echo "Merged develop into main locally."

if [ "$PUSH" = "1" ]; then
  git push origin main
  echo "Pushed origin/main. GPU Jenkins should poll or Scan Multibranch Now."
else
  echo "Not pushed. Review, then: git push origin main"
fi
