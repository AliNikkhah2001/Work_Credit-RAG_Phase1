#!/usr/bin/env bash
# Hourly watcher: detect Work_RAG-WebUI tip advances vs the umbrella gitlink.
#
# Jenkins Multibranch only polls the *parent* repo. A bare push to the WebUI
# submodule remote does not wake dana-rag-prod until the parent gitlink moves.
# This watcher:
#   1) records remote tip vs pinned SHA
#   2) writes /var/lib/dana-health/webui-watch.json for the health dashboard
#   3) asks Jenkins to scan dana-rag-prod (so a parent pin bump is picked up ASAP)
#   4) NEVER auto-pushes umbrella commits (safe for shared machines)
#
# Aligns with the hourly health-report timer. Does not start image rebuilds by
# itself — rebuilds still require a parent commit with [ci prod]/[ci auto] or
# an operator-triggered build after the gitlink is updated.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE_DIR="${STATE_DIR:-/var/lib/dana-health}"
JOB="${JENKINS_JOB:-dana-rag-prod}"
JENKINS_URL="${JENKINS_URL:-http://127.0.0.1:8085}"
USER="${JENKINS_USER:-admin}"
PASS_FILE="${JENKINS_PASS_FILE:-/splunk-data/production/.jenkins-admin-pass}"
WEBUI_PATH="components/webui"

mkdir -p "$STATE_DIR"
cd "$ROOT"

PINNED="$(git ls-tree HEAD "$WEBUI_PATH" 2>/dev/null | awk '{print $3}' || true)"
REMOTE_URL="$(git config -f .gitmodules --get submodule.components/webui.url 2>/dev/null || echo 'https://github.com/AliNikkhah2001/Work_RAG-WebUI.git')"
REMOTE_TIP="$(git ls-remote "$REMOTE_URL" refs/heads/main 2>/dev/null | awk '{print $1}' | head -1 || true)"

CHANGED=0
if [[ -n "$PINNED" && -n "$REMOTE_TIP" && "$PINNED" != "$REMOTE_TIP" ]]; then
  CHANGED=1
fi

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 - <<PY
import json
from pathlib import Path
Path("$STATE_DIR/webui-watch.json").write_text(json.dumps({
  "schema_version": "webui-watch/v1",
  "ts": "$TS",
  "submodule": "$WEBUI_PATH",
  "remote": "$REMOTE_URL",
  "pinned_sha": "$PINNED",
  "remote_tip": "$REMOTE_TIP",
  "ahead": bool($CHANGED),
  "action": "jenkins_scan" if $CHANGED else "none",
  "note": "Parent gitlink must advance (commit on umbrella with [ci prod]) before Jenkins builds the new WebUI tip. Watcher only scans Multibranch.",
}, indent=2) + "\n")
print(f"[webui-watch] pinned={('$PINNED')[:12]} tip={('$REMOTE_TIP')[:12]} ahead=$CHANGED")
PY

# Always nudge Jenkins Multibranch scan hourly (same cadence as health push).
# CSRF crumb requires a cookie jar — bare -H crumb returns 403.
if [[ -f "$PASS_FILE" ]]; then
  PASS="$(cat "$PASS_FILE")"
  JAR="$(mktemp /tmp/jenkins-crumb.XXXXXX)"
  CRUMB_JSON="$(curl -sS -c "$JAR" -u "$USER:$PASS" \
    "$JENKINS_URL/crumbIssuer/api/json" 2>/dev/null || true)"
  CRUMB="$(printf '%s' "$CRUMB_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('crumb',''))" 2>/dev/null || true)"
  FIELD="$(printf '%s' "$CRUMB_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('crumbRequestField','Jenkins-Crumb'))" 2>/dev/null || echo Jenkins-Crumb)"
  # Multibranch folder scan only (302 = accepted). Do NOT force-build main —
  # a bare WebUI tip advance without an umbrella gitlink bump would rebuild the
  # old pin. Parent commits with [ci prod]/[ci auto] are picked up by the scan.
  code="$(curl -sS -o /tmp/jenkins-scan.out -w '%{http_code}' -b "$JAR" -c "$JAR" -u "$USER:$PASS" \
    -H "$FIELD: $CRUMB" -X POST "$JENKINS_URL/job/$JOB/build?delay=0" 2>/dev/null || echo 000)"
  rm -f "$JAR"
  echo "[webui-watch] jenkins multibranch_scan=$code ahead=$CHANGED"
else
  echo "[webui-watch] no jenkins pass file — skip scan trigger"
fi

exit 0
