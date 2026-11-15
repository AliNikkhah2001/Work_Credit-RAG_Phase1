#!/usr/bin/env bash
# Capture CI failure forensics into .ci-evidence/ (archived by Jenkins + HC publish).
# Safe to run under dash or bash; never exits non-zero.
set +e
EVID="${1:-.ci-evidence}"
mkdir -p "$EVID" 2>/dev/null || exit 0

{
  echo "=== ci_capture_build_evidence ==="
  echo "ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "pwd=$(pwd)"
  echo "shell=${SHELL:-unknown} bash=${BASH_VERSION:-n/a}"
  echo "sh_path=$(command -v sh 2>/dev/null)"
  ls -la /bin/sh 2>/dev/null
  echo "PATH=$PATH"
  echo "which docker: $(command -v docker 2>/dev/null || echo MISSING)"
  for c in /usr/local/bin/docker /usr/bin/docker; do
    [ -x "$c" ] && echo "found_docker=$c"
  done
  docker version 2>&1 | head -20
  echo "--- env (package mirrors / role) ---"
  env 2>/dev/null | grep -E '^(DANA_|CI_|PIP_|UV_|NPM_|npm_config_|IRAN_|HTTP_PROXY|HTTPS_PROXY|NO_PROXY)=' | sort
  echo "--- docker images (rag-*) ---"
  docker images --format '{{.Repository}}:{{.Tag}} {{.ID}} {{.CreatedSince}}' 2>/dev/null | grep -E '^rag-|^dana-' | head -40
} >"$EVID/agent_context.txt" 2>&1

# Keep a short shell self-test: proves whether `source` works on this agent sh.
{
  echo "=== shell builtin probe ==="
  /bin/sh -c 'source /dev/null' 2>&1
  echo "sh_source_exit=$?"
  /bin/bash -c 'source /dev/null' 2>&1
  echo "bash_source_exit=$?"
} >"$EVID/shell_probe.txt" 2>&1

# Preserve mirror export file if present
[ -f .ci_iran_mirrors.env ] && cp -f .ci_iran_mirrors.env "$EVID/iran_mirrors.env" 2>/dev/null
[ -f .ci_coverage.env ] && cp -f .ci_coverage.env "$EVID/coverage.env" 2>/dev/null

# Compose build tee log (written by Build stage when present)
[ -f .ci-evidence/compose-build.log ] || true

echo "ci_capture_build_evidence: wrote $EVID"
exit 0
