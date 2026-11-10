#!/bin/bash
# LangGraph Studio for the orchestrator `rag` graph (no Docker needed).
# Serves the LangGraph API on :2024; open the visual panel at:
#   https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
# Remote browser: ssh -L 2024:localhost:2024 <vast-host>, then open the URL above.
# NOTE: Studio run inputs must include "request_id" (prod API injects it; Studio does not).
#   e.g. {"request_id": "studio-001", "messages": [{"role": "user", "content": "سلام"}]}
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT/components/orchestrator"

[ -f .env ] || touch .env  # langgraph.json references it; empty is fine
/tmp/orch-venv/bin/pip install -q 'langgraph-cli[inmem]' 2>&1 | tail -1

setsid nohup /tmp/orch-venv/bin/langgraph dev --host 0.0.0.0 --port 2024 \
  --config ./langgraph.json --no-browser > /tmp/langgraph-studio.log 2>&1 < /dev/null &
sleep 8
curl -s --max-time 10 http://127.0.0.1:2024/ok; echo
echo "panel: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024"
