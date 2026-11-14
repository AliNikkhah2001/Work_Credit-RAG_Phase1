#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 scripts/assemble_report.py
ls -la out/Work_Credit_RAG_Technical_Report.pdf out/Work_Credit_RAG_Security_Networking_Brief.pdf
