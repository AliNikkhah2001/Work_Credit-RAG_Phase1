#!/bin/bash
# Start (or restart) the KB manager on :8000 with the optimized RAM/GPU
# profile — the configuration measured at ~44 ms p50 end-to-end retrieval
# (see kb-manager README, "Latency"). Idempotent: kills any instance that
# currently holds the port first. Usage: bash deploy/h200/start_kb.sh
set -u

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=kb_env.sh
source "$SCRIPT_DIR/kb_env.sh"

LOG_DIR=${KB_LOG_DIR:-/tmp/kb-logs}
mkdir -p "$LOG_DIR"

# Stop any current holder of :8000 (scoped to the port — never pkill python).
OWNER=$(ss -tlnp 2>/dev/null | grep ':8000 ' | grep -oP 'pid=\K[0-9]+' | head -1)
if [ -n "${OWNER:-}" ]; then
    echo "stopping current KB instance (pid $OWNER)"
    kill "$OWNER"
    for _ in $(seq 1 20); do
        ss -tlnp 2>/dev/null | grep -q ':8000 ' || break
        sleep 0.5
    done
fi

cd "$KB_CODE"
export PYTHONPATH="$KB_CODE"
setsid nohup "$KB_VENV/bin/python" -m uvicorn kb_manager.web.app:app \
    --host 0.0.0.0 --port 8000 > "$LOG_DIR/kb_8000.log" 2>&1 < /dev/null &
PID=$!
echo "launched KB manager pid $PID (log: $LOG_DIR/kb_8000.log)"

# Wait for bind + health (first boot includes GPU model pre-warm, ~60 s).
for i in $(seq 1 60); do
    CODE=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 3 \
        http://127.0.0.1:8000/health 2>/dev/null)
    [ "$CODE" = "200" ] && break
    sleep 2
done
if [ "$CODE" = "200" ]; then
    echo "health OK after ~$((i * 2))s"
else
    echo "WARNING: health check failed (code=${CODE:-none}); inspect $LOG_DIR/kb_8000.log" >&2
    exit 1
fi

# Warm-up query (one-time lazy GPU model load; subsequent queries ~44 ms p50).
curl -s --noproxy '*' --max-time 120 -X POST http://127.0.0.1:8000/search/api \
    -H 'Content-Type: application/json' \
    -d '{"query":"اعتبارسنجی چیست","top_k":5}' -o /dev/null
echo "warm-up query done."

# Post-conditions: GPU residency + no reranker fallbacks (must run AFTER the
# warm-up query — dense/reranker models load lazily on first search).
OWNER=$(ss -tlnp 2>/dev/null | grep ':8000 ' | grep -oP 'pid=\K[0-9]+' | head -1)
GPU=$(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader 2>/dev/null | grep -c "^$OWNER,")
if [ "$GPU" -ge 1 ]; then
    echo "GPU residency OK (pid $OWNER on nvidia-smi)"
else
    echo "WARNING: pid $OWNER has no GPU memory — dense/reranker fell back to CPU!" >&2
fi
if grep -q "reranker offline fallback" "$LOG_DIR/kb_8000.log" 2>/dev/null; then
    echo "WARNING: reranker offline fallback detected in log!" >&2
else
    echo "reranker online (no fallback lines in log)"
fi

echo "Verify with:"
echo "  curl --noproxy '*' -X POST http://127.0.0.1:8000/search/api -H 'Content-Type: application/json' -d '{\"query\":\"اعتبارسنجی چیست\",\"top_k\":5}' | jq .stage_ms"
