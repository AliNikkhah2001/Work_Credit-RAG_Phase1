#!/bin/bash
# stop.sh — stop RAG services by port. Never `pkill python`; port-scoped only.
set -u
PORTS="8000 8100 8200 13000 3000 3001 2024 18000"
for p in $PORTS; do
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${p}/tcp" 2>/dev/null || true
  else
    # fallback: exact-pattern kills only (never bare `pkill python`)
    case "$p" in
      18000) pkill -f "llama-server.*--port 18000" 2>/dev/null || true ;;
      8000)  pkill -f "uvicorn kb_manager.web.app:app.*--port 8000" 2>/dev/null || true ;;
      8100)  pkill -f "work_rag_orchestrator.api.*--port 8100" 2>/dev/null || true ;;
      8200)  pkill -f "work_rag_guardrails.api.*--port 8200" 2>/dev/null || true ;;
      13000) pkill -f "open-webui serve.*--port 13000" 2>/dev/null || true ;;
      3000)  pkill -f "uvicorn app:app.*--port 3000" 2>/dev/null || true ;;
      3001)  pkill -f "pnpm --filter web start.*-p 3001" 2>/dev/null || true ;;
      2024)  pkill -f "langgraph dev.*--port 2024" 2>/dev/null || true ;;
    esac
  fi
done
sleep 3
echo "remaining listeners on our ports (empty = all stopped):"
(ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null) | grep -E ":(8000|8100|8200|13000|3000|3001|2024|18000)" || echo "all stopped"
