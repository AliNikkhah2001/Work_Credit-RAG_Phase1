#!/usr/bin/env bash
# =============================================================================
# gpu_spof_full_recover.sh — Thin umbrella wrapper for GPU full recovery.
#
# Delegates to scripts/gpu_full_recover_report.sh which collects everything:
#   host metadata, all git commits, all shell commands, all container logs,
#   all builds/runs, restart attempt, health matrix, E2E QA, screenshots,
#   redaction, pack, and push to GitHub.
#
# Run on the GPU host:
#   bash scripts/gpu_spof_full_recover.sh
#   bash scripts/gpu_spof_full_recover.sh --no-push
#   bash scripts/gpu_spof_full_recover.sh --no-restart
#   DANA_HOST_REPO=/path/to/repo bash scripts/gpu_spof_full_recover.sh
# =============================================================================
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec bash "$ROOT/scripts/gpu_full_recover_report.sh" "$@"
