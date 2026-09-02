#!/bin/bash
# MVP RAG Pipeline Runner (Linux/macOS)
# 
# Starts all components in dependency order with health checks.
# Requires: Gemma Manager running at port 9000 (from server-setup)

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HEALTH_CHECK_TIMEOUT=120
HEALTH_CHECK_INTERVAL=5

PIDS=()

log() {
    echo -e "${CYAN}[$(date '+%H:%M:%S')]${NC} $*"
}

success() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')] ✓${NC} $*"
}

warning() {
    echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠${NC} $*"
}

error() {
    echo -e "${RED}[$(date '+%H:%M:%S')] ✗${NC} $*"
}

cleanup() {
    log "Shutting down services..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
    success "All services stopped"
}

trap cleanup EXIT INT TERM

wait_for_health() {
    local url="$1"
    local name="$2"
    local timeout="${3:-$HEALTH_CHECK_TIMEOUT}"
    local interval="${4:-$HEALTH_CHECK_INTERVAL}"
    
    log "Waiting for $name at $url..."
    local deadline=$(($(date +%s) + timeout))
    
    while [[ $(date +%s) -lt $deadline ]]; do
        if curl -sf "$url" >/dev/null 2>&1; then
            success "$name is healthy"
            return 0
        fi
        sleep "$interval"
    done
    
    error "$name health check timed out after ${timeout}s"
    return 1
}

wait_for_readiness() {
    local url="$1"
    local name="$2"
    local timeout="${3:-$HEALTH_CHECK_TIMEOUT}"
    local interval="${4:-$HEALTH_CHECK_INTERVAL}"
    
    log "Waiting for $name readiness at $url..."
    local deadline=$(($(date +%s) + timeout))
    
    while [[ $(date +%s) -lt $deadline ]]; do
        if response=$(curl -sf "$url" 2>/dev/null); then
            if echo "$response" | grep -q '"status":"ready"'; then
                success "$name is ready"
                return 0
            elif echo "$response" | grep -q '"status":"not_ready"'; then
                local not_ready=$(echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdeps)
for dep in data.get('dependencies', []):
    if dep['status'] != 'ready':
        print(dep['name'], end=' ')
" 2>/dev/null || echo "unknown")
                warning "$name not ready yet: $not_ready"
            fi
        fi
        sleep "$interval"
    done
    
    error "$name readiness check timed out after ${timeout}s"
    return 1
}

# Check submodules
log "Checking submodule status..."
if git -C "$REPO_ROOT" submodule status --recursive | grep -q '^-'; then
    error "Submodules not initialized. Run: git submodule update --init --recursive"
    exit 1
fi
success "Submodules initialized"

# Check .env files
for env_file in \
    "$REPO_ROOT/components/guardrails/.env" \
    "$REPO_ROOT/components/orchestrator/.env"; do
    if [[ ! -f "$env_file" ]]; then
        example="${env_file%.env}.env.example"
        if [[ -f "$example" ]]; then
            cp "$example" "$env_file"
            warning "Created $env_file from example. Please review and update if needed."
        else
            warning "No .env file found at $env_file and no example to copy from"
        fi
    fi
done

# Start KB Manager
if [[ "${SKIP_KB:-false}" != "true" ]]; then
    log "Starting KB Manager..."
    cd "$REPO_ROOT/components/knowledgebase/kb-manager"
    export KB_DB_URL="sqlite+aiosqlite:///$(pwd)/data/kb_test.db"
    export KB_SOURCE_DIR="$REPO_ROOT/components/knowledgebase/kb-source"
    export KB_WEB_PORT=8000
    
    python run_server.py &
    KB_PID=$!
    PIDS+=("$KB_PID")
    log "KB Manager started with PID $KB_PID"
    
    if ! wait_for_health "http://127.0.0.1:8000/" "KB Manager"; then
        exit 1
    fi
else
    log "Skipping KB Manager (assumed running)"
    if ! wait_for_health "http://127.0.0.1:8000/" "KB Manager" 10 2; then
        error "KB Manager not accessible at http://127.0.0.1:8000/"
        exit 1
    fi
fi

# Start Guardrails
if [[ "${SKIP_GUARDRAILS:-false}" != "true" ]]; then
    log "Starting Guardrails..."
    cd "$REPO_ROOT/components/guardrails"
    export GUARDRAILS_PORT=8200
    export UPSTREAM_LLM_BASE_URL="http://127.0.0.1:9000/v1"
    export UPSTREAM_LLM_MODEL="gemma-4-31b"
    export UPSTREAM_LLM_API_KEY="sk-local-dev"
    
    python -m work_rag_guardrails.api &
    GR_PID=$!
    PIDS+=("$GR_PID")
    log "Guardrails started with PID $GR_PID"
    
    if ! wait_for_readiness "http://127.0.0.1:8200/ready" "Guardrails"; then
        exit 1
    fi
else
    log "Skipping Guardrails (assumed running)"
    if ! wait_for_readiness "http://127.0.0.1:8200/ready" "Guardrails" 10 2; then
        error "Guardrails not accessible at http://127.0.0.1:8200/ready"
        exit 1
    fi
fi

# Start Orchestrator
if [[ "${SKIP_ORCHESTRATOR:-false}" != "true" ]]; then
    log "Starting Orchestrator..."
    cd "$REPO_ROOT/components/orchestrator"
    export ORCHESTRATOR_PORT=8100
    export KB_BASE_URL="http://127.0.0.1:8000"
    export GUARDRAILS_BASE_URL="http://127.0.0.1:8200"
    export REQUEST_TIMEOUT_SECONDS=120
    export RETRIEVAL_TOP_K=5
    
    python -m work_rag_orchestrator.api &
    ORCH_PID=$!
    PIDS+=("$ORCH_PID")
    log "Orchestrator started with PID $ORCH_PID"
    
    if ! wait_for_readiness "http://127.0.0.1:8100/ready" "Orchestrator"; then
        exit 1
    fi
else
    log "Skipping Orchestrator (assumed running)"
    if ! wait_for_readiness "http://127.0.0.1:8100/ready" "Orchestrator" 10 2; then
        error "Orchestrator not accessible at http://127.0.0.1:8100/ready"
        exit 1
    fi
fi

success "All MVP services started successfully!"
echo
echo "Service endpoints:"
echo "  KB Manager:       http://127.0.0.1:8000"
echo "  Orchestrator:     http://127.0.0.1:8100"
echo "  Guardrails:       http://127.0.0.1:8200"
echo "  Gemma Manager:    http://127.0.0.1:9000 (from server-setup)"
echo "  Open WebUI:       http://127.0.0.1:13000 (configure separately)"
echo
log "Press Ctrl+C to stop all services..."

# Keep running
wait