#!/usr/bin/env bash
# =============================================================================
# gpu_full_recover_report.sh — Complete GPU production recovery + evidence pack
#
# Run this on the GPU / production host where Work_Credit-RAG_Phase1 is cloned.
#
# Required directory:
#   /splunk-data/production/Work_Credit-RAG_Phase1   (or wherever the repo is)
#
# Sudo/root: Recommended (needed for docker, journalctl, /root/.bash_history).
# The script will detect if it's root and warn if not.
#
# Usage:
#   cd /splunk-data/production/Work_Credit-RAG_Phase1
#   git pull origin main
#   DANA_HOST_REPO=$(pwd) bash scripts/gpu_full_recover_report.sh
#
#   With options:
#   DANA_HOST_REPO=$(pwd) bash scripts/gpu_full_recover_report.sh \
#       --no-push --no-restart --no-screenshot --verbose
#
#   Help:
#   bash scripts/gpu_full_recover_report.sh --help
#
# Daemon mode:
#   The script supports a --daemon flag for the systemd timer:
#     DANA_HOST_REPO=/path bash scripts/gpu_full_recover_report.sh --daemon
#   Daily at 16:00 (4 PM); on failure retries every 3 hours.
# =============================================================================
set -uo pipefail

# --- Colors ------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# --- State -------------------------------------------------------------------
VERBOSE=0
NO_PUSH=0
NO_RESTART=0
NO_SCREENSHOT=0
DRY_RUN=0
DAEMON_MODE=0
DAILY_TIME="16:00"
RETRY_INTERVAL_HOURS=3
STEPS_TOTAL=20
STEP_CURRENT=0

# --- Status tracking (pass/fail for final report) ---------------------------
STATUS_RESTART="NOT_ATTEMPTED"
STATUS_SMOKE="NOT_ATTEMPTED"
STATUS_PUSH="NOT_ATTEMPTED"
STATUS_E2E="NOT_ATTEMPTED"
STATUS_HTML="NOT_ATTEMPTED"

# --- Paths -------------------------------------------------------------------
UMBRELLA="${DANA_HOST_REPO:-}"
SS_REPO="${SERVER_SETUP_REPO:-}"
RUN_LOG=""
REPO_ROOT=""
IS_ROOT=0
MACHINE_TYPE="unknown"

# --- CLI ---------------------------------------------------------------------
usage() {
  cat <<EOF
${BLUE}gpu_full_recover_report.sh${NC} — Complete GPU production recovery + evidence pack

${CYAN}USAGE:${NC}
  DANA_HOST_REPO=/path/to/repo bash $0 [OPTIONS]

${CYAN}OPTIONS:${NC}
  --no-push          Skip pushing the report to GitHub
  --no-restart       Skip attempting to restart services
  --no-screenshot    Skip headless screenshots
  --verbose          Show detailed command output
  --dry-run          Show what would be done without executing
  --daemon           Run in daemon mode (daily at $DAILY_TIME, retry every $RETRY_INTERVAL_HOURS h on failure)
  --daily-time HH:MM Set the daily run time (default: $DAILY_TIME)
  --retry-hours N    Set retry interval in hours on failure (default: $RETRY_INTERVAL_HOURS)
  -h, --help         Show this help

${CYAN}REQUIRED:${NC}
  DANA_HOST_REPO   Absolute path to the Work_Credit-RAG_Phase1 clone on this host
                   (e.g. /splunk-data/production/Work_Credit-RAG_Phase1)

${CYAN}EXAMPLE:${NC}
  cd /splunk-data/production/Work_Credit-RAG_Phase1
  git pull origin main
  DANA_HOST_REPO=$(pwd) bash scripts/gpu_full_recover_report.sh

${CYAN}DAEMON EXAMPLE:${NC}
  # Install systemd timer for daily 4 PM run with 3h retry on failure:
  sudo bash scripts/install_daemon.sh

${CYAN}PREREQUISITES:${NC}
  - docker (for container logs and restart)
  - git (for commit history and pushing to GitHub)
  - curl (for health checks)
  - chromium/google-chrome or playwright (for screenshots, optional)
  - gh CLI (for creating PR, optional)
  - Sudo/root recommended (docker, journalctl, bash history)

EOF
}

log()  { printf '%b[INFO]%b %s\n' "$BLUE" "$NC" "$*" | tee -a "$RUN_LOG" 2>/dev/null || printf '%b[INFO]%b %s\n' "$BLUE" "$NC" "$*"; }
ok()   { printf '%b[OK]%b   %s\n' "$GREEN" "$NC" "$*" | tee -a "$RUN_LOG" 2>/dev/null || printf '%b[OK]%b   %s\n' "$GREEN" "$NC" "$*"; }
warn() { printf '%b[WARN]%b %s\n' "$YELLOW" "$NC" "$*" | tee -a "$RUN_LOG" 2>/dev/null || printf '%b[WARN]%b %s\n' "$YELLOW" "$NC" "$*"; }
fail() { printf '%b[FAIL]%b %s\n' "$RED" "$NC" "$*" | tee -a "$RUN_LOG" 2>/dev/null || printf '%b[FAIL]%b %s\n' "$RED" "$NC" "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

# --- Progress bar ------------------------------------------------------------
progress() {
  local current="$1"
  local total="$2"
  local label="$3"
  local width=40
  local filled=$(( current * width / total ))
  local empty=$(( width - filled ))
  local percent=$(( current * 100 / total ))
  local bar=""
  for ((i=0; i<filled; i++)); do bar="${bar}█"; done
  for ((i=0; i<empty; i++)); do bar="${bar}░"; done
  printf '\r%b[%s]%b %3d%%  %s' "$CYAN" "$bar" "$NC" "$percent" "$label"
}

step() {
  STEP_CURRENT=$((STEP_CURRENT + 1))
  progress "$STEP_CURRENT" "$STEPS_TOTAL" "$1"
  echo ""  # newline after progress bar
  log "Step $STEP_CURRENT/$STEPS_TOTAL: $1"
}

# --- Parse arguments ---------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-push) NO_PUSH=1; shift ;;
    --no-restart) NO_RESTART=1; shift ;;
    --no-screenshot) NO_SCREENSHOT=1; shift ;;
    --verbose) VERBOSE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --daemon) DAEMON_MODE=1; shift ;;
    --daily-time) DAILY_TIME="$2"; shift 2 ;;
    --retry-hours) RETRY_INTERVAL_HOURS="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    --DANA_HOST_REPO=*) UMBRELLA="${1#*=}"; shift ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

# --- Validate DANA_HOST_REPO -------------------------------------------------
if [[ -z "$UMBRELLA" ]]; then
  echo "${RED}ERROR:${NC} DANA_HOST_REPO is required."
  echo ""
  echo "Example:"
  echo "  DANA_HOST_REPO=/splunk-data/production/Work_Credit-RAG_Phase1 bash $0"
  echo ""
  usage
  exit 2
fi

if [[ ! -d "$UMBRELLA" ]]; then
  fail "DANA_HOST_REPO directory does not exist: $UMBRELLA"
  exit 2
fi

if [[ ! -d "$UMBRELLA/.git" ]]; then
  fail "DANA_HOST_REPO is not a git repository: $UMBRELLA"
  exit 2
fi

# Set server-setup repo path
if [[ -z "$SS_REPO" ]]; then
  SS_REPO="$UMBRELLA/components/server-setup"
fi

# --- Check prerequisites -----------------------------------------------------
step "Checking prerequisites"
MISSING=0
for cmd in docker git curl; do
  if have "$cmd"; then
    ok "$cmd available"
  else
    fail "$cmd not found"
    MISSING=1
  fi
done
if [[ "$MISSING" -eq 1 ]]; then
  fail "Missing required prerequisites. Install docker, git, and curl first."
  exit 1
fi
have chromium || have chromium-browser || have google-chrome || have google-chrome-stable \
  && ok "Browser available for screenshots" || warn "No browser — screenshots will be URL stubs only"
have gh && ok "gh CLI available — PR creation enabled" || warn "gh CLI not found — will push branch only (no PR)"
have python3 && ok "python3 available" || warn "python3 not found — some screenshot fallbacks disabled"

# --- Pull updates ------------------------------------------------------------
step "Pulling latest updates from GitHub"
if [[ "$DRY_RUN" == "1" ]]; then
  log "[dry-run] would run: git -C $UMBRELLA pull origin main"
else
  if git -C "$UMBRELLA" fetch origin 2>&1 | tee -a "$RUN_LOG"; then
    ok "fetch origin complete"
  else
    warn "fetch origin failed — proceeding with local state"
  fi
  if git -C "$UMBRELLA" rev-parse --verify origin/main >/dev/null 2>&1; then
    LOCAL="$(git -C "$UMBRELLA" rev-parse HEAD)"
    REMOTE="$(git -C "$UMBRELLA" rev-parse origin/main)"
    if [[ "$LOCAL" != "$REMOTE" ]]; then
      log "Local HEAD ($LOCAL) differs from origin/main ($REMOTE) — merging"
      if git -C "$UMBRELLA" merge --ff-only origin/main 2>&1 | tee -a "$RUN_LOG"; then
        ok "merged origin/main"
      else
        warn "fast-forward merge failed — you may need to resolve conflicts manually"
      fi
    else
      ok "already up to date with origin/main"
    fi
  else
    warn "no origin/main branch found — skipping merge"
  fi
fi

# --- Setup output directory --------------------------------------------------
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$(hostname -s 2>/dev/null || echo host)"
OUT="${SPOF_OUT:-$SS_REPO/docs/ops/gpu-recover-reports/$RUN_ID}"
RUN_LOG="$OUT/run.log"

mkdir -p "$OUT"/{logs,containers,commits,commands,builds,meta,curl,e2e,screenshots,restart,redacted,kb,html}
exec > >(tee -a "$RUN_LOG") 2>&1

echo ""
echo "${CYAN}======================================================================${NC}"
echo "${CYAN}  GPU Full Recovery Report — $RUN_ID${NC}"
echo "${CYAN}======================================================================${NC}"
echo "  Host:        $(hostname -f 2>/dev/null || hostname)"
echo "  Repo:        $UMBRELLA"
echo "  Server-setup: $SS_REPO"
echo "  Output:      $OUT"
echo "  Root:        $([ "$IS_ROOT" -eq 1 ] && echo yes || echo no)"
echo "  Push:        $([ "$NO_PUSH" -eq 1 ] && echo disabled || echo enabled)"
echo "  Restart:     $([ "$NO_RESTART" -eq 1 ] && echo disabled || echo enabled)"
echo "  Screenshot:  $([ "$NO_SCREENSHOT" -eq 1 ] && echo disabled || echo enabled)"
echo "${CYAN}======================================================================${NC}"
echo ""

# --- Check sudo/root (after OUT is defined) ----------------------------------
if [[ "$EUID" -eq 0 ]]; then
  IS_ROOT=1
  ok "Running as root — full access to docker, journalctl, bash history"
else
  warn "Not running as root — docker, journalctl, and /root/.bash_history may be inaccessible"
  echo "  Recommended: sudo bash $0 (with DANA_HOST_REPO set)"
  echo ""
fi

# --- Detect machine type: dev (macOS laptop) vs production (GPU server) -----
if [[ "$(uname -s)" == "Darwin" ]]; then
  MACHINE_TYPE="dev_laptop"
  ok "Detected dev laptop (macOS) — dev mode: relaxed restarts, dev health checks"
elif [[ -f /etc/os-release ]] && grep -qiE 'ubuntu|centos|rhel|amzn|rocky|almalinux' /etc/os-release 2>/dev/null; then
  MACHINE_TYPE="production_gpu"
  ok "Detected production GPU server (Linux) — production mode: full restarts, production health checks"
else
  MACHINE_TYPE="generic_linux"
  ok "Detected generic Linux — hybrid mode"
fi
echo "machine_type=$MACHINE_TYPE" >>"$OUT/meta/host_metadata.txt" 2>/dev/null || true

# =============================================================================
# SECTION 0: Host metadata + user/shutdown/reboot info
# =============================================================================
step "Collecting host metadata"
{
  date -u +"utc=%Y-%m-%dT%H:%M:%SZ"
  echo "hostname=$(hostname -f 2>/dev/null || hostname)"
  echo "user=$(whoami 2>/dev/null || echo unknown)"
  echo "uid=$(id -u 2>/dev/null || echo unknown)"
  uname -a
  uptime
  echo "--- nvidia-smi ---"
  { have nvidia-smi && nvidia-smi || echo "nvidia-smi missing"; } 2>&1 || true
  echo "--- docker ps -a (all containers, up and down) ---"
  { have docker && docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}' || echo "docker missing"; } 2>&1 || true
  echo "--- df -h ---"
  df -h 2>&1 || true
  echo "--- free -h ---"
  free -h 2>/dev/null || true
  echo "--- git state ---"
  echo "git_umbrella=$(git -C "$UMBRELLA" rev-parse --short HEAD 2>/dev/null || echo n/a)"
  echo "git_ss=$(git -C "$SS_REPO" rev-parse --short HEAD 2>/dev/null || echo n/a)"
  echo "last_good=$(cat "$UMBRELLA/deploy/compose/.last_good_sha" 2>/dev/null || echo none)"
  echo "deployed=$(cat "$UMBRELLA/deploy/compose/.deployed_sha" 2>/dev/null || echo none)"
  echo "--- last reboots/shutdowns ---"
  { have last && last -x | head -n 30 || echo "last unavailable"; } 2>&1 || true
  echo "--- detected stack mode ---"
  MODE=unknown
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -qE 'dana-prod|rag-'; then
    MODE=compose
  elif [[ -f /tmp/kb.log ]] || [[ -x /tmp/kb-venv/bin/python ]]; then
    MODE=host_venv
  elif [[ -f "$UMBRELLA/deploy/compose/compose.gpu.yml" ]]; then
    MODE=compose
  fi
  echo "detected_mode=$MODE"
} >"$OUT/meta/host_metadata.txt" 2>&1 || true
ok "host metadata -> $OUT/meta/host_metadata.txt"

# =============================================================================
# SECTION 1: All local git commits (all branches, all submodules)
# =============================================================================
step "Collecting all git commits (last 3 days)"
{
  echo "=== UMBRELLA: $UMBRELLA ==="
  git -C "$UMBRELLA" log --all --since="3 days ago" \
    --format='%h | %an | %ad | %s' --date=format:'%Y-%m-%d %H:%M:%S %z' \
    2>&1 || echo "git log failed"
  echo ""
  echo "=== Current branch ==="
  git -C "$UMBRELLA" branch --show-current 2>&1 || true
  echo ""
  echo "=== Submodule status ==="
  git -C "$UMBRELLA" submodule status --recursive 2>&1 || true
} >"$OUT/commits/umbrella_commits.txt" 2>&1 || true
ok "umbrella commits -> $OUT/commits/umbrella_commits.txt"

for sub in components/knowledgebase components/orchestrator components/guardrails components/server-setup components/webui components/evaluation agent-state; do
  if [[ -d "$UMBRELLA/$sub/.git" ]]; then
    {
      echo "=== SUBMODULE: $sub ==="
      git -C "$UMBRELLA/$sub" log --all --since="3 days ago" \
        --format='%h | %an | %ad | %s' --date=format:'%Y-%m-%d %H:%M:%S %z' \
        2>&1 || echo "git log failed"
      echo ""
      echo "=== Branch ==="
      git -C "$UMBRELLA/$sub" branch --show-current 2>&1 || true
    } >"$OUT/commits/$(basename "$sub")_commits.txt" 2>&1 || true
    ok "$sub commits"
  fi
done

# =============================================================================
# SECTION 2: Shell command history (bash, zsh, journalctl)
# =============================================================================
step "Collecting shell command history (last 3 days)"
{
  echo "=== bash history (root) ==="
  cat /root/.bash_history 2>/dev/null || echo "no /root/.bash_history (need root)"
  echo ""
  echo "=== bash history (current user) ==="
  cat ~/.bash_history 2>/dev/null || echo "no ~/.bash_history"
  echo ""
  echo "=== zsh history ==="
  cat ~/.zsh_history 2>/dev/null || echo "no ~/.zsh_history"
  echo ""
  echo "=== journalctl (last 3 days) ==="
  { have journalctl && journalctl --since="3 days ago" --no-pager 2>/dev/null || echo "journalctl unavailable"; } | head -n 10000
} >"$OUT/commands/shell_history.txt" 2>&1 || true
ok "shell history -> $OUT/commands/shell_history.txt"

# =============================================================================
# SECTION 3: ALL container logs (up OR down) + docker events
# =============================================================================
step "Collecting all container logs"
CONTAINER_COUNT=0
if have docker; then
  while IFS= read -r c; do
    [[ -z "$c" ]] && continue
    CONTAINER_COUNT=$((CONTAINER_COUNT + 1))
    docker logs --timestamps --tail 5000 "$c" >"$OUT/containers/docker-${c}.log" 2>&1 || \
      echo "FAILED to get logs for $c" >"$OUT/containers/docker-${c}.log"
  done < <(docker ps -a --format '{{.Names}}')
  docker events --since="3 days ago" --until="now" \
    >"$OUT/containers/docker_events.txt" 2>&1 || true
  ok "collected logs from $CONTAINER_COUNT containers"
else
  warn "docker not available — skipping container logs"
fi

# =============================================================================
# SECTION 4: Database logs (PostgreSQL) + DVC logs for knowledgebase
# =============================================================================
step "Collecting database and DVC logs"
{
  echo "=== PostgreSQL logs ==="
  PG_LOG_DIRS=(
    "/var/log/postgresql"
    "/var/lib/postgresql/14/main/log"
    "/var/lib/postgresql/15/main/log"
    "/tmp/postgres.log"
    "/tmp/pg.log"
  )
  PG_FOUND=0
  for d in "${PG_LOG_DIRS[@]}"; do
    if [[ -d "$d" ]]; then
      echo "--- PG log dir: $d ---"
      ls -la "$d" 2>/dev/null || true
      for f in "$d"/*.log "$d"/*.csv; do
        [[ -f "$f" ]] || continue
        echo "=== $f ==="
        tail -n 2000 "$f" 2>/dev/null || true
      done
      PG_FOUND=1
    elif [[ -f "$d" ]]; then
      echo "=== $d ==="
      tail -n 2000 "$d" 2>/dev/null || true
      PG_FOUND=1
    fi
  done
  if [[ "$PG_FOUND" -eq 0 ]]; then
    echo "no postgresql log files found in standard locations"
  fi

  echo ""
  echo "=== Docker postgres container logs ==="
  if have docker; then
    for c in $(docker ps -a --format '{{.Names}}' | grep -iE 'postgres|pgvector|db|database'); do
      echo "=== container: $c ==="
      docker logs --timestamps --tail 5000 "$c" 2>&1 || true
    done
  fi

  echo ""
  echo "=== DVC logs (knowledgebase versioning) ==="
  DVC_FOUND=0
  for dvc_dir in "$UMBRELLA/components/knowledgebase" "$UMBRELLA/components/knowledgebase/.dvc" \
                 "$UMBRELLA/.dvc" "$UMBRELLA/dvc" /tmp/dvc; do
    if [[ -d "$dvc_dir" ]]; then
      echo "--- DVC dir: $dvc_dir ---"
      ls -la "$dvc_dir" 2>/dev/null || true
      DVC_FOUND=1
    fi
  done
  if [[ -d "$UMBRELLA/components/knowledgebase" ]] && have dvc; then
    echo "--- dvc status ---"
    (cd "$UMBRELLA/components/knowledgebase" && dvc status 2>&1 || true)
    echo "--- dvc list ---"
    (cd "$UMBRELLA/components/knowledgebase" && dvc list . 2>&1 || true)
  elif [[ "$DVC_FOUND" -eq 0 ]]; then
    echo "no dvc directories found"
  fi
} >"$OUT/logs/database_and_dvc.log" 2>&1 || true
ok "database and dvc logs -> $OUT/logs/database_and_dvc.log"

# =============================================================================
# SECTION 5: Host /tmp logs
# =============================================================================
step "Collecting host /tmp logs"
LOG_COUNT=0
for f in /tmp/kb.log /tmp/guard.log /tmp/orch.log /tmp/webui.log /tmp/llama-server.log \
         /tmp/langfuse.log /tmp/manager.log /tmp/embed*.log /tmp/*.log /tmp/postgres.log \
         /tmp/pg.log; do
  for g in $f; do
    [[ -f "$g" ]] || continue
    LOG_COUNT=$((LOG_COUNT + 1))
    base="$(basename "$g")"
    tail -n 5000 "$g" >"$OUT/logs/host-$base" 2>&1 || true
  done
done
ok "collected $LOG_COUNT host log files"

# =============================================================================
# SECTION 6: Builds and runs (Jenkins logs, compose logs)
# =============================================================================
step "Collecting builds and runs"
{
  echo "=== Jenkins container logs ==="
  if have docker && docker ps --format '{{.Names}}' | grep -qE 'dana-jenkins|jenkins'; then
    for c in $(docker ps --format '{{.Names}}' | grep -E 'dana-jenkins|jenkins'); do
      echo "=== jenkins: $c ==="
      docker logs --timestamps --tail 5000 "$c" >"$OUT/builds/jenkins-$c.log" 2>&1 || true
      echo "jenkins logs: $c"
    done
  else
    echo "no jenkins container found"
  fi
  echo ""
  echo "=== /tmp log files ==="
  ls -la /tmp/*.log 2>/dev/null || echo "no /tmp/*.log files"
  echo ""
  echo "=== Compose directory ==="
  ls -la "$UMBRELLA/deploy/compose/" 2>/dev/null || echo "no deploy/compose/"
  echo ""
  echo "=== Jenkins workspace/builds ==="
  ls -la "$UMBRELLA/deploy/jenkins/" 2>/dev/null || echo "no deploy/jenkins/"
} >"$OUT/builds/builds_and_runs.txt" 2>&1 || true
ok "builds/runs -> $OUT/builds/builds_and_runs.txt"

# =============================================================================
# SECTION 7: Knowledgebase details (current KB, chunks, version, history)
# =============================================================================
step "Collecting knowledgebase details"
KB_DIR="$OUT/kb"
mkdir -p "$KB_DIR"
{
  echo "=== Knowledgebase container ==="
  if have docker; then
    KB_CONTAINER=""
    for c in $(docker ps --format '{{.Names}}'); do
      if echo "$c" | grep -qiE 'kb|knowledgebase|kb-manager'; then
        KB_CONTAINER="$c"
        break
      fi
    done
    if [[ -n "$KB_CONTAINER" ]]; then
      echo "KB container: $KB_CONTAINER"
      echo "--- KB container env ---"
      docker exec "$KB_CONTAINER" env 2>/dev/null | grep -iE 'KB_|DATABASE|POSTGRES|DVC|EMBED|MODEL' || true
      echo ""
      echo "--- KB container processes ---"
      docker exec "$KB_CONTAINER" ps aux 2>/dev/null || true
    else
      echo "no KB container found running"
    fi
  fi

  echo ""
  echo "=== KB search API health ==="
  KB_HEALTH="$(curl -sS --max-time 10 http://127.0.0.1:8000/health 2>/dev/null || echo '{}')"
  echo "$KB_HEALTH" | python3 -m json.tool 2>/dev/null || echo "$KB_HEALTH"

  echo ""
  echo "=== KB search test (sample query) ==="
  KB_SEARCH="$(curl -sS --max-time 30 -X POST http://127.0.0.1:8000/search/api \
    -H 'Content-Type: application/json' \
    -d '{"query":"اعتبارسنجی","top_k":5}' 2>/dev/null || echo '{}')"
  echo "$KB_SEARCH" | python3 -m json.tool 2>/dev/null || echo "$KB_SEARCH"

  echo ""
  echo "=== KB document count / chunks ==="
  curl -sS --max-time 10 http://127.0.0.1:8000/stats 2>/dev/null || echo "stats endpoint unavailable"
  echo ""
  curl -sS --max-time 10 http://127.0.0.1:8000/documents 2>/dev/null || echo "documents endpoint unavailable"

  echo ""
  echo "=== KB version from git ==="
  if [[ -d "$UMBRELLA/components/knowledgebase/.git" ]]; then
    echo "KB HEAD: $(git -C "$UMBRELLA/components/knowledgebase" rev-parse --short HEAD 2>/dev/null || echo n/a)"
    echo "KB branch: $(git -C "$UMBRELLA/components/knowledgebase" branch --show-current 2>/dev/null || echo n/a)"
    echo "KB last 10 commits:"
    git -C "$UMBRELLA/components/knowledgebase" log --oneline -10 2>/dev/null || true
  else
    echo "KB is not a git checkout"
  fi

  echo ""
  echo "=== KB entity lists ==="
  ls -la "$UMBRELLA/components/knowledgebase/entity_lists/" 2>/dev/null || echo "no entity_lists dir"
  ls -la "$UMBRELLA/components/knowledgebase/data/" 2>/dev/null || echo "no data dir"
} >"$KB_DIR/kb_details.txt" 2>&1 || true
ok "knowledgebase details -> $KB_DIR/kb_details.txt"

# =============================================================================
# SECTION 8: Restart services (machine-aware)
# =============================================================================
step "Attempting service restart"
RESTART_LOG="$OUT/restart/restart.log"
STATUS_RESTART="FAILED"

if [[ "$NO_RESTART" == "1" ]]; then
  echo "skip" >"$OUT/restart/action.txt"
  STATUS_RESTART="SKIPPED"
  warn "restart disabled (--no-restart)"
else
  {
    echo "Restart attempt at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "Machine type: $MACHINE_TYPE"
    echo "Detected stack mode: $MODE"
    echo ""

    RESTART_OK=0

    if [[ "$MACHINE_TYPE" == "dev_laptop" ]]; then
      echo "--- Dev laptop mode: attempting lightweight service start ---"
      # On dev laptop: try to start services via docker compose if available
      if have docker && docker ps --format '{{.Names}}' 2>/dev/null | grep -qE 'kb|orchestrator|guardrails|webui|jenkins|postgres'; then
        echo "Found running containers — attempting docker compose restart"
        # IMPORTANT: compose.base.yml has NO port mappings. Ports (13000/8100/8000/8200)
        # only exist in compose.local.yml. Always layer base+local or nothing is reachable.
        if [[ -f "$UMBRELLA/deploy/compose/compose.base.yml" ]]; then
          COMPOSE_ARGS=(-f "$UMBRELLA/deploy/compose/compose.base.yml")
          if [[ -f "$UMBRELLA/deploy/compose/compose.local.yml" ]]; then
            COMPOSE_ARGS+=(-f "$UMBRELLA/deploy/compose/compose.local.yml")
          fi
          [[ -f "$UMBRELLA/deploy/compose/.env" ]] && COMPOSE_ARGS+=(--env-file "$UMBRELLA/deploy/compose/.env")
          if docker compose -p dana-local "${COMPOSE_ARGS[@]}" \
            up -d 2>&1 | tee -a "$RESTART_LOG"; then
            ok "dev compose up succeeded (base + local, ports published)"
            RESTART_OK=1
          else
            warn "dev compose up returned non-zero"
          fi
        else
          warn "no compose.base.yml — skipping compose restart on dev"
        fi
      else
        echo "No docker services found running on dev laptop"
        echo "To start services manually on dev:"
        echo "  cd $UMBRELLA && DANA_HOST_REPO=$(pwd) bash deploy/gpu/start.sh"
        # On dev, services may be running as host processes (not docker)
        # Check for host-process services
        if pgrep -f 'uvicorn|llama-server|open-webui' >/dev/null 2>&1; then
          ok "dev laptop: host-process services detected (uvicorn/llama/open-webui running)"
          RESTART_OK=1
        else
          warn "dev laptop: no services running — restart will not bring them up"
          RESTART_OK=0
        fi
      fi

    elif [[ "$MODE" == "compose" && -f "$UMBRELLA/deploy/compose/compose.gpu.yml" ]]; then
      echo "--- Production GPU mode: compose stack restart ---"
      ENVF="$UMBRELLA/deploy/compose/.env.prod"
      [[ -f "$ENVF" ]] || ENVF="$UMBRELLA/deploy/compose/.env"
      if [[ -f "$ENVF" ]]; then
        echo "Bringing up compose stack dana-prod with $ENVF"
        # compose.base.yml has NO ports — compose.gpu.yml supplies them (13000 etc.)
        if docker compose -p dana-prod \
          -f "$UMBRELLA/deploy/compose/compose.base.yml" \
          -f "$UMBRELLA/deploy/compose/compose.gpu.yml" \
          --env-file "$ENVF" \
          up -d 2>&1 | tee -a "$RESTART_LOG"; then
          ok "compose up succeeded"
          RESTART_OK=1
        else
          warn "compose up returned non-zero"
        fi
      else
        warn "no .env.prod/.env — cannot compose up"
      fi
      if [[ -f "$UMBRELLA/deploy/jenkins/docker-compose.gpu.yml" ]]; then
        if docker compose -f "$UMBRELLA/deploy/jenkins/docker-compose.yml" \
          -f "$UMBRELLA/deploy/jenkins/docker-compose.gpu.yml" \
          up -d 2>&1 | tee -a "$RESTART_LOG"; then
          ok "jenkins compose up succeeded"
        else
          warn "jenkins compose up failed"
        fi
      fi

    elif [[ "$MODE" == "host_venv" || -x /tmp/kb-venv/bin/python || -f /tmp/kb.log ]]; then
      echo "--- Production GPU mode: host-venv fallback ---"
      echo "Falling back to host-venv stack (deploy/gpu/start.sh)"
      if [[ -x "$UMBRELLA/deploy/gpu/start.sh" ]]; then
        nohup bash "$UMBRELLA/deploy/gpu/start.sh" >>"$RESTART_LOG" 2>&1 &
        START_PID=$!
        echo "deploy/gpu/start.sh launched (PID $START_PID)"
        RESTART_OK=1
      else
        warn "deploy/gpu/start.sh not found or not executable"
      fi

    else
      warn "no recognized stack mode — cannot restart"
    fi

    if [[ "$RESTART_OK" -eq 1 ]]; then
      STATUS_RESTART="PASSED"
    fi
  } >"$RESTART_LOG" 2>&1 || true

  ok "restart log -> $OUT/restart/restart.log"

  sleep 30
  echo "--- Post-restart processes ---"
  ps aux | grep -E 'uvicorn|llama-server|open-webui|jenkins|postgres' | grep -v grep \
    >"$OUT/restart/processes.txt" 2>&1 || true
  cat "$OUT/restart/processes.txt"
  ok "post-restart process check"
fi

# =============================================================================
# SECTION 9: Curl health matrix (all endpoints each service serves)
# =============================================================================
step "Testing all service endpoints (curl health matrix)"
CURLDIR="$OUT/curl"

# Diagnose the classic "stack up but nothing reachable" failure:
# compose.base.yml has NO port mappings, so running it WITHOUT compose.local.yml
# (dev) or compose.gpu.yml (prod) starts healthy containers with zero published
# ports — WebUI :13000 appears "down" while the container is actually fine.
if have docker; then
  PUBLISHED_TOTAL="$(docker ps --format '{{.Ports}}' 2>/dev/null | grep -c '127.0.0.1:\|0.0.0.0:' || true)"
  WEBUI_PUBLISHED="$(docker ps --format '{{.Names}} {{.Ports}}' 2>/dev/null | grep -c 'webui.*:13000->' || true)"
  {
    echo "=== RESTART/REACHABILITY DIAGNOSIS ($(date -u +%Y-%m-%dT%H:%M:%SZ)) ==="
    echo "containers_with_published_ports=$PUBLISHED_TOTAL"
    echo "webui_publishes_13000=$WEBUI_PUBLISHED"
    docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null | grep -i 'dana\|webui' || true
    echo ""
    echo "NOTE: compose.base.yml declares no ports. A stack started with base-only"
    echo "      runs healthy but publishes nothing -> WebUI :13000 unreachable."
    echo "      Correct: base + compose.local.yml (dev) or base + compose.gpu.yml (prod)."
  } >"$OUT/meta/port_publishing.txt" 2>&1 || true

  if [[ "$WEBUI_PUBLISHED" == "0" ]]; then
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q 'webui'; then
      warn "WebUI container is UP but does NOT publish :13000 — started without the port overlay"
      warn "  fix: docker compose -p dana-local -f deploy/compose/compose.base.yml -f deploy/compose/compose.local.yml up -d"
    else
      warn "no WebUI container running at all"
    fi
  else
    ok "WebUI publishes :13000 (port overlay applied correctly)"
  fi
fi

PORTS=(18000 9000 8000 8200 8100 3000 3001 13000 8085 8010 8001 8002 8003)
: >"$CURLDIR/matrix.tsv"
echo -e "port\tservice\thttp_code\tbody_preview" >>"$CURLDIR/matrix.tsv"
HEALTH_FAIL=0
STATUS_SMOKE="PASSED"
PORT_COUNT=${#PORTS[@]}
PORT_IDX=0

# Define expected endpoints per service (compatible with bash 3.2 — no associative arrays)
SERVICE_ENDPOINTS_LIST="
8000|/health /search/api /stats /documents
8100|/health /ready /v1/chat/completions
8200|/health /ready /v1/rails/check
13000|/ /health /api/health
8085|/ /login /health
18000|/health /v1/models
3000|/health /api/public/health
3001|/health /api/public/health
9000|/health /
8010|/health /
8001|/health /
8002|/health /
8003|/health /
"

get_endpoints_for_port() {
  local p="$1"
  echo "$SERVICE_ENDPOINTS_LIST" | grep "^${p}|" | cut -d'|' -f2- || echo "/"
}

# Map port to container name for docker exec fallback
port_to_container() {
  local p="$1"
  case "$p" in
    8000) echo "dana-local-kb-1" ;;
    8100) echo "dana-local-orchestrator-1" ;;
    8200) echo "dana-local-guardrails-1" ;;
    13000) echo "dana-local-webui-1" ;;
    8085) echo "dana-jenkins" ;;
    18000) echo "" ;; # llama-server usually on host
    *) echo "" ;;
  esac
}

# Try localhost first (with dev port-offset fallback), then docker exec internal health
probe_port() {
  local p="$1"
  local body code
  # Candidate host ports: logical port + dev stage offsets
  local cands=("$p")
  case "$p" in
    13000) cands+=(13100) ;;
    8000)  cands+=(18000) ;;
    8100)  cands+=(18100) ;;
    8200)  cands+=(18200) ;;
  esac
  code="000"; body=""
  local cp
  for cp in "${cands[@]}"; do
    body="$(curl -sS --max-time 8 "http://127.0.0.1:$cp/health" 2>/dev/null || true)"
    if [[ -n "$body" ]]; then code="200"; break; fi
    body="$(curl -sS --max-time 8 "http://127.0.0.1:$cp/health/liveliness" 2>/dev/null || true)"
    if [[ -n "$body" ]]; then code="200"; break; fi
    code="$(curl -sS -o /tmp/spof_curl_body.txt -w '%{http_code}' --max-time 5 "http://127.0.0.1:$cp/" 2>/dev/null)" || code="000"
    body="$(head -c 120 /tmp/spof_curl_body.txt 2>/dev/null || true)"
    [[ "$code" == "200" ]] && break
  done
  # Docker internal fallback (macOS: ports may not publish to localhost)
  if [[ "$code" != "200" && -n "$(port_to_container "$p")" ]] && have docker; then
    local cname internal_port
    cname="$(port_to_container "$p")"
    case "$p" in
      13000) internal_port=8080 ;;
      *) internal_port="$p" ;;
    esac
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$cname"; then
      local internal
      internal="$(docker exec "$cname" curl -sS --max-time 5 "http://localhost:$internal_port/health" 2>/dev/null || true)"
      if ! printf '%s' "$internal" | grep -qE '^\{|ok|status|healthy|"'; then
        internal="$(docker exec -i "$cname" python3 -c "
import sys,urllib.request
try:
    sys.stdout.write(urllib.request.urlopen('http://localhost:$internal_port/health', timeout=5).read().decode())
except Exception:
    sys.exit(1)
" 2>/dev/null || true)"
      fi
      if printf '%s' "$internal" | grep -qE '^\{|ok|status|healthy|"'; then
        code="200"
        body="$internal"
        echo "[docker-internal] $cname responds internally" >>"$OUT/meta/docker_internal_fallback.txt"
      fi
    fi
  fi
  printf '%s\n%s\n' "$code" "$body"
}

for p in "${PORTS[@]}"; do
  PORT_IDX=$((PORT_IDX + 1))
  progress "$PORT_IDX" "$PORT_COUNT" "probing port $p"

  # Service name guess
  svc="unknown"
  case "$p" in
    18000) svc="gemma" ;;
    8000) svc="kb" ;;
    8100) svc="orchestrator" ;;
    8200) svc="guardrails" ;;
    13000) svc="webui" ;;
    8085) svc="jenkins" ;;
    3000) svc="trace-collector" ;;
    3001) svc="langfuse" ;;
    9000) svc="manager" ;;
    *) svc="service:$p" ;;
  esac

  # Probe via localhost, with docker internal fallback
  read -r code body < <(probe_port "$p")
  preview="$(printf '%s' "$body" | tr '\n' ' ' | head -c 160)"
  echo -e "${p}\t${svc}\t${code}\t${preview}" | tee -a "$CURLDIR/matrix.tsv"
  printf '%s\n' "$body" >"$CURLDIR/port-${p}.txt"

  # Also probe all known endpoints for this service
  for ep in $(get_endpoints_for_port "$p"); do
    ep_body="$(curl -sS --max-time 8 "http://127.0.0.1:$p$ep" 2>/dev/null || true)"
    ep_code="000"
    if [[ -n "$ep_body" ]]; then ep_code="200"; fi
    echo -e "${p}\t${svc}[${ep}]\t${ep_code}\t$(printf '%s' "$ep_body" | tr '\n' ' ' | head -c 120)" >>"$CURLDIR/endpoints_${p}.tsv"
  done

  case "$p" in
    8000|8100|8200)
      if [[ "$code" != "200" ]]; then
        HEALTH_FAIL=1
        STATUS_SMOKE="FAILED"
        fail "critical :$p ($svc) down"
      else
        ok ":$p ($svc) up"
      fi
      ;;
    13000)
      [[ "$code" == "200" ]] && ok "webui :$p up" || { warn "webui :$p not responding"; STATUS_SMOKE="FAILED"; }
      ;;
    8085)
      [[ "$code" == "200" ]] && ok "jenkins :$p up" || { warn "jenkins :$p not responding"; STATUS_SMOKE="FAILED"; }
      ;;
  esac
done
echo ""  # newline after progress bar

for url in http://127.0.0.1:8100/ready http://127.0.0.1:8200/ready; do
  curl -sS --max-time 10 "$url" | tee "$CURLDIR/$(echo "$url" | tr '/:' '__').txt" | head -c 300; echo
done

# =============================================================================
# SECTION 10: E2E chat QA tests (incl. OpenWebUI direct)
# =============================================================================
step "Running E2E chat QA tests"
E2E="$OUT/e2e"
QA_PASS=0
QA_TOTAL=0
STATUS_E2E="PASSED"
mkdir -p "$E2E"
: >"$E2E/summary.txt"

# Container-aware POST helper: tries published localhost port first, then docker exec
# (dev macOS does not publish container ports to 127.0.0.1, but prod Linux does)
curl_post_svc() {
  local port="$1" path="$2" payload="$3" outf="$4"
  local container internal_port
  container="$(port_to_container "$port")"
  case "$port" in
    8000) internal_port=8000 ;;
    8100) internal_port=8100 ;;
    8200) internal_port=8200 ;;
    13000) internal_port=8080 ;;
    *) internal_port="$port" ;;
  esac
  local code="000"
  # Attempt 1: direct localhost (works on prod Linux where ports are published)
  code="$(curl -sS -o "$outf" -w '%{http_code}' --max-time 120 \
    -H 'Content-Type: application/json' -d "$payload" \
    "http://127.0.0.1:$port$path" 2>/dev/null)" || code="000"
  if [[ "$code" == "200" ]] && grep -qE '"content"|"choices"|"delta"|"final_results"|^data:' "$outf" 2>/dev/null; then
    echo "200"; return 0
  fi
  # Attempt 2: docker exec (curl then python3); validate output, reject OCI/runtime errors
  if have docker && [[ -n "$container" ]] && docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$container"; then
    local tmp=""
    tmp="$(docker exec "$container" curl -sS --max-time 120 \
      -H 'Content-Type: application/json' -d "$payload" \
      "http://localhost:$internal_port$path" 2>/dev/null || true)"
    if ! printf '%s' "$tmp" | grep -qE '"content"|"choices"|"delta"|"final_results"|^data:'; then
      tmp="$(docker exec -i "$container" python3 -c "
import sys,urllib.request,urllib.error
payload=sys.stdin.read()
req=urllib.request.Request('http://localhost:$internal_port$path', data=payload.encode(), headers={'Content-Type':'application/json'})
try:
    sys.stdout.write(urllib.request.urlopen(req, timeout=120).read().decode())
except urllib.error.HTTPError as e:
    body=e.read().decode(errors='replace')
    sys.stdout.write('{\"_http_status\": %d, \"_body\": %s}' % (e.code, __import__('json').dumps(body)))
except Exception:
    sys.exit(1)
" <<<"$payload" 2>/dev/null || true)"
    fi
    if printf '%s' "$tmp" | grep -qE '"content"|"choices"|"delta"|"final_results"|^data:'; then
      printf '%s' "$tmp" >"$outf"
      echo "200"; return 0
    fi
    # Detect auth/HTTP errors so caller can classify (e.g. WebUI 401 on dev)
    if printf '%s' "$tmp" | grep -qE 'Not authenticated|"_http_status"'; then
      printf '%s' "$tmp" >"$outf"
      local st
      st="$(printf '%s' "$tmp" | grep -o '"_http_status": *[0-9]*' | grep -o '[0-9]*' | head -1)"
      echo "${st:-401}"; return 0
    fi
  fi
  # Nothing worked — write a clear marker (not a stale/error body)
  printf '{"error":"unreachable","port":"%s","path":"%s"}' "$port" "$path" >"$outf"
  echo "$code"
}

run_chat() {
  local name="$1" payload="$2"
  QA_TOTAL=$((QA_TOTAL + 1))
  local outf="$E2E/${name}.json"
  local code
  code="$(curl_post_svc 8100 "/v1/chat/completions" "$payload" "$outf")"
  echo "${name} http=$code" | tee -a "$E2E/summary.txt"
  if [[ "$code" == "200" ]] && grep -qE '"content"|"choices"|"delta"|^data:' "$outf" 2>/dev/null; then
    QA_PASS=$((QA_PASS + 1))
    ok "E2E $name pass"
  else
    STATUS_E2E="FAILED"
    fail "E2E $name fail (http=$code)"
    head -c 400 "$outf"; echo
  fi
}

run_chat chat_greeting '{"model":"gemma-4-31b","messages":[{"role":"user","content":"سلام"}]}'
run_chat chat_credit_qa '{"model":"gemma-4-31b","messages":[{"role":"user","content":"اعتبارسنجی چیست؟"}]}'

# Direct OpenWebUI E2E test — sign in, discover model, chat with Bearer token.
# OpenWebUI is NOT "down" when it returns 401; it just needs auth + the served model name.
WEBUI_E2E_PY="$OUT/meta/webui_e2e.py"
cat >"$WEBUI_E2E_PY" <<'PYEOF'
import sys, json, urllib.request, urllib.error
base = sys.argv[1].rstrip("/")
email = sys.argv[2] if len(sys.argv) > 2 else "admin@localhost"
password = sys.argv[3] if len(sys.argv) > 3 else "admin"
question = sys.argv[4] if len(sys.argv) > 4 else "اعتبارسنجی چیست؟"

def call(path, data=None, token=None, timeout=120):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(base + path, data=body, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout)

res = {"signin": "none", "model": "", "chat_http": 0, "answer": "", "error": ""}
token = ""
# 1) sign in
try:
    d = json.loads(call("/api/v1/auths/signin", {"email": email, "password": password}).read().decode())
    token = d.get("token", "")
    res["signin"] = "ok" if token else "no-token"
except urllib.error.HTTPError as e:
    res["signin"] = "http-%d" % e.code
except Exception as e:
    res["signin"] = "err"
    res["error"] = str(e)[:200]
# 2) discover served model
model = ""
try:
    d = json.loads(call("/api/models", token=token, timeout=30).read().decode())
    ids = [m.get("id") for m in (d.get("data") or []) if m.get("id")]
    if ids:
        model = ids[0]
except Exception:
    pass
if not model:
    model = "ics-helper-agent"
res["model"] = model
# 3) chat
try:
    raw = call("/api/chat/completions",
               {"model": model, "messages": [{"role": "user", "content": question}], "stream": False},
               token=token).read().decode()
    res["chat_http"] = 200
    try:
        d = json.loads(raw)
        res["answer"] = ((d.get("choices") or [{}])[0].get("message") or {}).get("content", "") or raw[:2000]
    except Exception:
        res["answer"] = raw[:2000]
except urllib.error.HTTPError as e:
    res["chat_http"] = e.code
    res["error"] = e.read().decode(errors="replace")[:300]
except Exception as e:
    res["error"] = str(e)[:300]
print(json.dumps(res, ensure_ascii=False))
PYEOF

QA_TOTAL=$((QA_TOTAL + 1))
WEBUI_JSON=""
WEBUI_CONTAINER="$(port_to_container 13000)"
# Try host-side first (prod publishes 127.0.0.1:13000), then inside the container (dev)
if curl -s -o /dev/null --max-time 3 "http://127.0.0.1:13000/health" 2>/dev/null; then
  WEBUI_JSON="$(python3 "$WEBUI_E2E_PY" "http://127.0.0.1:13000" 2>/dev/null || true)"
elif have docker && [[ -n "$WEBUI_CONTAINER" ]] && docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$WEBUI_CONTAINER"; then
  WEBUI_JSON="$(docker exec -i "$WEBUI_CONTAINER" python3 - "http://localhost:8080" < "$WEBUI_E2E_PY" 2>/dev/null || true)"
fi
[[ -z "$WEBUI_JSON" ]] && WEBUI_JSON='{"signin":"unreachable","chat_http":0,"error":"webui unreachable"}'
printf '%s' "$WEBUI_JSON" >"$E2E/chat_webui.json"
WEBUI_CODE="$(printf '%s' "$WEBUI_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('chat_http',0))" 2>/dev/null || echo 0)"
echo "chat_webui http=$WEBUI_CODE" | tee -a "$E2E/summary.txt"
if [[ "$WEBUI_CODE" == "200" ]] && grep -qE '"answer"' "$E2E/chat_webui.json" 2>/dev/null && ! grep -q '"answer": ""' "$E2E/chat_webui.json" 2>/dev/null; then
  QA_PASS=$((QA_PASS + 1))
  ok "E2E webui pass (signed in, model=$(printf '%s' "$WEBUI_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('model',''))" 2>/dev/null))"
else
  STATUS_E2E="FAILED"
  fail "E2E webui fail (http=$WEBUI_CODE)"
  printf '%s\n' "$WEBUI_JSON" | head -c 400; echo
fi

# KB search (container-aware, with retry for transient reranker/DNS hiccups)
KB_SEARCH_CODE="000"
for attempt in 1 2 3; do
  KB_SEARCH_CODE="$(curl_post_svc 8000 "/search/api" '{"query":"اعتبارسنجی چیست","top_k":3}' "$E2E/kb_search.json")"
  if grep -q 'final_results' "$E2E/kb_search.json" 2>/dev/null; then break; fi
  [[ "$attempt" -lt 3 ]] && { warn "kb_search attempt $attempt failed (http=$KB_SEARCH_CODE) — retrying"; sleep 3; }
done
echo "kb_search http=$KB_SEARCH_CODE" | tee -a "$E2E/summary.txt"
if grep -q 'final_results' "$E2E/kb_search.json" 2>/dev/null; then
  ok "KB search returned results"
else
  STATUS_E2E="FAILED"
  fail "KB search empty/failed"
fi
echo "qa_pass=$QA_PASS/$QA_TOTAL" | tee "$E2E/score.txt"

# =============================================================================
# SECTION 11: Screenshots of all endpoints each service serves
# =============================================================================
step "Capturing headless screenshots"
SHOT="$OUT/screenshots"
mkdir -p "$SHOT"
if [[ "$NO_SCREENSHOT" == "1" ]]; then
  warn "screenshots disabled (--no-screenshot)"
else
  CHROME=""
  for c in chromium chromium-browser google-chrome google-chrome-stable; do
    if have "$c"; then CHROME="$c"; break; fi
  done
  # macOS: Chrome lives inside the .app bundle (not on PATH)
  if [[ -z "$CHROME" && -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]]; then
    CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  fi
  if [[ -z "$CHROME" && -x "$HOME/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]]; then
    CHROME="$HOME/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  fi
  if [[ -n "$CHROME" ]]; then
    ok "browser for screenshots: $CHROME"
  else
    warn "no Chrome/Chromium found — screenshots will be URL stubs"
  fi
  shoot() {
    local url="$1" name="$2"
    if [[ -n "$CHROME" ]]; then
      "$CHROME" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
        --window-size=1400,900 --virtual-time-budget=8000 \
        --screenshot="$SHOT/${name}.png" "$url" 2>"$SHOT/${name}.chrome.log" && [[ -f "$SHOT/${name}.png" ]] && ok "shot $name" && return 0
    fi
    if have python3; then
      python3 - "$url" "$SHOT/${name}.png" <<'PY' 2>"$SHOT/${name}.py.log" && ok "shot $name (playwright)" && return 0
import sys
url, out = sys.argv[1], sys.argv[2]
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1400, "height": 900})
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.screenshot(path=out, full_page=True)
        b.close()
    sys.exit(0)
except Exception as e:
    sys.exit(1)
PY
    fi
    warn "no browser for $name — wrote URL stub"
    echo "$url" >"$SHOT/${name}.url.txt"
  }

  # Resolve a logical service port to a reachable URL (prod publishes to 127.0.0.1;
  # dev macOS uses the dana-stage stack on +13100/+10100 offsets)
  resolve_base() {
    local port="$1" path="$2"
    local candidates=()
    candidates+=("$port")
    case "$port" in
      13000) candidates+=(13100) ;;
      8000)  candidates+=(18000) ;;
      8100)  candidates+=(18100) ;;
      8200)  candidates+=(18200) ;;
      18000) candidates+=(18000) ;;
    esac
    local c
    for c in "${candidates[@]}"; do
      if curl -s -o /dev/null --max-time 3 "http://127.0.0.1:$c$path" 2>/dev/null; then
        echo "http://127.0.0.1:$c"; return 0
      fi
    done
    echo "http://127.0.0.1:$port"  # fall back to logical port
  }

  # Health pages (auto-resolve reachable base)
  shoot "$(resolve_base 8000 /health)/health" "kb-health"
  shoot "$(resolve_base 8100 /health)/health" "orch-health"
  shoot "$(resolve_base 8200 /health)/health" "guard-health"
  shoot "$(resolve_base 13000 /)/" "webui-home"
  shoot "http://127.0.0.1:8085/login" "jenkins-login"
  shoot "http://127.0.0.1:18000/health" "gemma-health"
  shoot "$(resolve_base 3000 /health)/health" "collector-health"

  # WebUI chat page (E2E visual)
  shoot "$(resolve_base 13000 /)/" "webui-chat"

  # Service endpoints screenshots
  for p in 8000 8100 8200 13000 8085 18000; do
    shoot "$(resolve_base "$p" /health)/health" "endpoint_${p}_health" 2>/dev/null || true
  done
fi
ls -la "$SHOT" | tee "$SHOT/listing.txt"

# =============================================================================
# SECTION 12: Collect all ran commands, shutdown, reboot, user metadata
# =============================================================================
step "Collecting command/shutdown/reboot/user metadata"
{
  echo "=== All commands run (from shell history) ==="
  cat ~/.bash_history 2>/dev/null || echo "no bash history"
  cat ~/.zsh_history 2>/dev/null || echo "no zsh history"
  echo ""
  echo "=== Shutdown/reboot events (last) ==="
  { have last && last -x | head -n 50 || echo "last unavailable"; } 2>&1 || true
  echo ""
  echo "=== User metadata ==="
  echo "Current user: $(whoami 2>/dev/null || echo unknown)"
  echo "UID: $(id -u 2>/dev/null || echo unknown)"
  echo "Groups: $(id -Gn 2>/dev/null || echo unknown)"
  echo "Home: $HOME"
  echo "Shell: $SHELL"
  echo ""
  echo "=== Systemd services status ==="
  { have systemctl && systemctl list-units --type=service --state=running,failed 2>/dev/null || echo "systemctl unavailable"; } | head -n 100
  echo ""
  echo "=== Cron jobs ==="
  { crontab -l 2>/dev/null || echo "no crontab"; }
  echo ""
  echo "=== Systemd timers ==="
  { have systemctl && systemctl list-timers --all 2>/dev/null || echo "systemd timers unavailable"; } | head -n 50
} >"$OUT/logs/command_shutdown_reboot_user.log" 2>&1 || true
ok "command/shutdown/reboot/user metadata -> $OUT/logs/command_shutdown_reboot_user.log"

# =============================================================================
# SECTION 13: Write REPORT.md
# =============================================================================
step "Writing REPORT.md"
REPORT="$OUT/REPORT.md"
STATUS="DEGRADED"
if [[ "$HEALTH_FAIL" == "0" && "$QA_PASS" -ge 1 ]]; then STATUS="HEALTHY"; fi
if [[ "$HEALTH_FAIL" == "1" && "$QA_PASS" -eq 0 ]]; then STATUS="DOWN"; fi

cat >"$REPORT" <<REPORTEOF
# GPU Full Recovery Report — \`$RUN_ID\`

| Field | Value |
|------|------|
| UTC | $(date -u +%Y-%m-%dT%H:%M:%SZ) |
| Host | $(hostname -f 2>/dev/null || hostname) |
| Status | **$STATUS** |
| Mode | \`$MODE\` |
| Umbrella HEAD | $(git -C "$UMBRELLA" rev-parse --short HEAD 2>/dev/null || echo n/a) |
| last_good | $(cat "$UMBRELLA/deploy/compose/.last_good_sha" 2>/dev/null || echo none) |
| deployed | $(cat "$UMBRELLA/deploy/compose/.deployed_sha" 2>/dev/null || echo none) |
| QA | $QA_PASS / $QA_TOTAL chat passes |
| Health failures | $HEALTH_FAIL |

## What this run did
1. Host metadata (uptime, nvidia-smi, docker ps, df, free, journal, shutdown/reboot events)
2. ALL git commits (last 3 days, all branches, all submodules)
3. ALL shell commands run (last 3 days, bash history + journalctl)
4. ALL container logs (docker logs --timestamps --tail 5000 per container, up or down)
5. Database (PostgreSQL) logs + DVC knowledgebase logs
6. All host /tmp logs
7. Knowledgebase details (current KB, chunks, version, commit history, entity lists)
8. All builds/runs (Jenkins logs, compose logs)
9. Command/shutdown/reboot/user metadata
10. Attempted restart of last known services
11. Curl health matrix (all endpoints each service serves)
12. E2E chat QA + KB search + OpenWebUI direct test
13. Headless screenshots of all service endpoints
14. HTML dashboard

## Health matrix
\`\`\`
$(column -t -s $'\t' "$CURLDIR/matrix.tsv" 2>/dev/null || cat "$CURLDIR/matrix.tsv")
\`\`\`

## E2E summary
\`\`\`
$(cat "$E2E/summary.txt" 2>/dev/null)
$(cat "$E2E/score.txt" 2>/dev/null)
\`\`\`

## Knowledgebase details
\`\`\`
$(cat "$KB_DIR/kb_details.txt" 2>/dev/null | head -n 80)
\`\`\`

## Screenshots
$(ls "$SHOT"/*.png 2>/dev/null | while read -r f; do echo "- ![]($(basename "$f"))"; done || echo "_none_")

## Post-restart processes
\`\`\`
$(cat "$OUT/restart/processes.txt" 2>/dev/null || echo "no restart data")
\`\`\`

## How to re-run
\`\`\`bash
DANA_HOST_REPO=$UMBRELLA bash $SS_REPO/scripts/gpu_full_recover_report.sh
\`\`\`

Artifacts live under \`docs/ops/gpu-recover-reports/$RUN_ID/\` in Work_RAG-Server-Setup.
REPORTEOF
ok "wrote $REPORT"

# =============================================================================
# SECTION 14: Generate HTML dashboard
# =============================================================================
step "Generating HTML dashboard"
HTML_DASH="$OUT/html/dashboard.html"

# Gather QA details for HTML — parse into structured Q&A blocks
QA_DETAILS="$(cat "$E2E/summary.txt" 2>/dev/null || echo "no e2e data")"
QA_SCORE="$(cat "$E2E/score.txt" 2>/dev/null || echo "qa_pass=0/0")"

# Build Q&A dialogue HTML from summary file
# Write a standalone extractor (avoids nested heredoc in command substitution)
QA_EXTRACT="$OUT/meta/qa_extract.py"
cat >"$QA_EXTRACT" <<'PYEOF'
import sys, json, re
p = sys.argv[1]
try:
    raw = open(p, encoding="utf-8", errors="replace").read()
except Exception:
    print("Q\t"); print("A\t"); sys.exit(0)
q, a = "", ""
try:
    d = json.loads(raw)
    # WebUI E2E shape: {"signin":..,"model":..,"chat_http":..,"answer":..}
    if "answer" in d or "signin" in d:
        a = d.get("answer", "") or ""
        q = d.get("question", "") or ""
    else:
        q = (d.get("messages") or [{}])[0].get("content", "") or d.get("query", "")
        ch = d.get("choices") or []
        if ch:
            a = (ch[0].get("message") or {}).get("content", "") or (ch[0].get("delta") or {}).get("content", "")
except Exception:
    pass
if not a and "data:" in raw:
    parts = []
    for m in re.finditer(r'^data:\s*(\{.*\})\s*$', raw, re.M):
        try:
            obj = json.loads(m.group(1))
            for c in (obj.get("choices") or []):
                delta = c.get("delta") or {}
                if delta.get("content"):
                    parts.append(delta["content"])
                msg = c.get("message") or {}
                if msg.get("content"):
                    parts.append(msg["content"])
        except Exception:
            continue
    a = "".join(parts)
if not a:
    m = re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
    if m:
        a = m.group(1)
print("Q\t" + q.replace("\n", " "))
print("A\t" + a.replace("\n", " "))
PYEOF

QA_HTML=""
if [[ -f "$E2E/summary.txt" ]]; then
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    [[ "$line" == \#* ]] && continue
    # Parse lines like: chat_greeting http=200  |  kb_search http=200
    name="$(echo "$line" | cut -d' ' -f1)"
    code="$(echo "$line" | grep -o 'http=[0-9]*' | cut -d'=' -f2)"
    qfile="$E2E/${name}.json"
    question=""
    answer=""
    if [[ -f "$qfile" ]]; then
      extracted="$(python3 "$QA_EXTRACT" "$qfile" 2>/dev/null || true)"
      question="$(printf '%s\n' "$extracted" | sed -n 's/^Q\t//p' | head -1)"
      answer="$(printf '%s\n' "$extracted" | sed -n 's/^A\t//p' | head -1)"
    fi
    # Fallback: known prompt by test name
    if [[ -z "$question" ]]; then
      case "$name" in
        chat_greeting) question="سلام" ;;
        chat_credit_qa) question="اعتبارسنجی چیست؟" ;;
        chat_webui) question="سلام، آیا سرویس فعال است؟" ;;
        kb_search) question="اعتبارسنجی چیست (KB search)" ;;
      esac
    fi
    # HTML-escape to avoid breaking the page on <, >, & in answers
    question="$(printf '%s' "$question" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g')"
    answer="$(printf '%s' "$answer" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g')"
    passed="passed"
    [[ "$code" != "200" ]] && passed="failed"
    QA_HTML+="<div class=\"qa-item\"><h4>$name</h4>"
    [[ -n "$question" ]] && QA_HTML+="<div class=\"qa-question\">❓ $question</div>"
    [[ -n "$answer" ]] && QA_HTML+="<div class=\"qa-answer\">🤖 $answer</div>"
    [[ -z "$answer" ]] && QA_HTML+="<div class=\"qa-answer\" style=\"color:#888;\">(no answer captured — service down or request failed)</div>"
    QA_HTML+="<div class=\"qa-status\">HTTP: $code — <span class=\"$([ "$code" = "200" ] && echo 'status-passed' || echo 'status-failed')\">$([ "$code" = "200" ] && echo 'PASS' || echo 'FAIL')</span></div></div>"
  done < "$E2E/summary.txt"
fi
if [[ -z "$QA_HTML" ]]; then
  QA_HTML="<div style=\"color:#666;\">No QA tests were run (services may be down).</div>"
fi

# Gather KB details
KB_DETAILS="$(cat "$KB_DIR/kb_details.txt" 2>/dev/null | head -n 100 || echo "no kb data")"

# Gather all log files for collapsible sections
LOG_FILES=""
for f in \
  "$OUT/meta/host_metadata.txt" \
  "$OUT/logs/command_shutdown_reboot_user.log" \
  "$OUT/logs/database_and_dvc.log" \
  "$OUT/curl/matrix.tsv" \
  "$OUT/restart/restart.log" \
  "$OUT/run.log"; do
  if [[ -f "$f" ]]; then
    LOG_FILES+="$f"$'\n'
  fi
done

cat >"$HTML_DASH" <<HTMLEOF
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GPU Recovery Dashboard — $RUN_ID</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f7; color: #1d1d1f; line-height: 1.5; }
  .container { max-width: 1400px; margin: 0 auto; }
  header { background: linear-gradient(135deg, #1d1d1f 0%, #0a84ff 100%); color: #fff; padding: 32px; border-radius: 16px; margin-bottom: 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
  header h1 { margin: 0 0 12px 0; font-size: 28px; font-weight: 600; }
  header .meta { font-size: 14px; opacity: 0.9; line-height: 1.6; }
  header .meta strong { color: #ffffff; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card { background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); border: 1px solid #e5e5ea; }
  .card h2 { margin-top: 0; font-size: 16px; color: #0a84ff; border-bottom: 2px solid #0a84ff; padding-bottom: 8px; margin-bottom: 12px; }
  .status-healthy { color: #34c759; font-weight: 700; }
  .status-degraded { color: #ff9500; font-weight: 700; }
  .status-down { color: #ff3b30; font-weight: 700; }
  .status-passed { color: #34c759; font-weight: 700; }
  .status-failed { color: #ff3b30; font-weight: 700; }
  .status-skipped { color: #ff9500; font-weight: 700; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 16px; }
  th, td { text-align: left; padding: 10px; border-bottom: 1px solid #e5e5ea; }
  th { background: #f2f2f7; font-weight: 600; color: #1d1d1f; }
  tr:hover { background: #fafafa; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
  .badge-pass { background: #e6f7e6; color: #2e7d32; }
  .badge-fail { background: #fdecea; color: #c62828; }
  .badge-skip { background: #fff4e6; color: #e6a200; }
  .screenshot-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
  .screenshot-item { border: 1px solid #e5e5ea; border-radius: 8px; overflow: hidden; background: #fff; }
  .screenshot-item img { width: 100%; height: auto; display: block; }
  .screenshot-item .caption { padding: 8px; font-size: 12px; background: #f2f2f7; color: #666; }
  pre { background: #1e1e1e; color: #d4d4d4; padding: 14px; border-radius: 8px; overflow-x: auto; font-size: 12px; margin: 12px 0; }
  .section { margin-bottom: 24px; }
  .section h3 { color: #1d1d1f; margin-bottom: 12px; font-size: 18px; border-left: 4px solid #0a84ff; padding-left: 12px; }
  .collapsible { background: #fff; border: 1px solid #e5e5ea; border-radius: 8px; margin: 12px 0; overflow: hidden; }
  .collapsible-header { background: #f2f2f7; padding: 14px 18px; font-weight: 600; color: #1d1d1f; cursor: pointer; border-bottom: 1px solid #e5e5ea; user-select: none; display: flex; justify-content: space-between; align-items: center; }
  .collapsible-header:hover { background: #e8e8ed; }
  .collapsible-header .arrow { display: inline-block; width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-bottom: 5px solid #666; transition: transform 0.2s; }
  .collapsible-header.expanded .arrow { transform: rotate(-90deg); }
  .collapsible-content { padding: 0; max-height: 0; overflow: hidden; transition: max-height 0.3s ease; background: #fff; }
  .collapsible-content.expanded { max-height: 2000px; padding: 18px; }
  .qa-item { background: #fff; border: 1px solid #e5e5ea; border-radius: 8px; margin: 12px 0; padding: 16px; }
  .qa-item h4 { margin: 0 0 8px 0; color: #0a84ff; font-size: 15px; }
  .qa-question { font-weight: 600; color: #1d1d1f; margin-bottom: 6px; }
  .qa-answer { background: #f2f2f7; padding: 12px; border-radius: 6px; color: #333; white-space: pre-wrap; font-size: 13px; }
  .qa-status { display: inline-block; margin-top: 8px; font-size: 12px; font-weight: 600; }
  .artifact-list { list-style: none; padding: 0; }
  .artifact-list li { padding: 8px 0; border-bottom: 1px solid #f2f2f7; }
  .artifact-list li a { color: #0a84ff; text-decoration: none; }
  .artifact-list li a:hover { text-decoration: underline; }
  .artifact-list li:last-child { border-bottom: none; }
  .auto-open { position: fixed; top: 20px; right: 20px; background: #0a84ff; color: #fff; padding: 12px 20px; border-radius: 8px; font-weight: 600; z-index: 1000; box-shadow: 0 4px 12px rgba(10,132,255,0.3); }
  .auto-open.hidden { display: none; }
</style>
</head>
<body>
<div class="container">
<header>
  <h1>🖥️ GPU Full Recovery Dashboard</h1>
  <div class="meta">
    <strong>Run ID:</strong> $RUN_ID<br>
    <strong>Host:</strong> $(hostname -f 2>/dev/null || hostname)<br>
    <strong>Machine:</strong> $MACHINE_TYPE<br>
    <strong>UTC:</strong> $(date -u +%Y-%m-%dT%H:%M:%SZ)<br>
    <strong>Mode:</strong> $MODE<br>
    <strong>Umbrella HEAD:</strong> $(git -C "$UMBRELLA" rev-parse --short HEAD 2>/dev/null || echo n/a)<br>
    <strong>Overall Status:</strong> <span class="status-$STATUS">$STATUS</span>
  </div>
</header>

<div class="grid">
  <div class="card">
    <h2>Overall Status</h2>
    <div class="badge status-$STATUS">$STATUS</div>
  </div>
  <div class="card">
    <h2>QA Results</h2>
    <div class="badge $([ "$STATUS_E2E" = "PASSED" ] && echo badge-pass || echo badge-fail)">E2E: $QA_PASS / $QA_TOTAL</div>
    <div class="badge $([ "$STATUS_SMOKE" = "PASSED" ] && echo badge-pass || echo badge-fail)">Smoke: $STATUS_SMOKE</div>
  </div>
  <div class="card">
    <h2>Restart</h2>
    <div class="badge $([ "$STATUS_RESTART" = "PASSED" ] && echo badge-pass || echo badge-skip)">$STATUS_RESTART</div>
  </div>
  <div class="card">
    <h2>GitHub Push</h2>
    <div class="badge $([ "$STATUS_PUSH" = "PASSED" ] && echo badge-pass || echo badge-skip)">$STATUS_PUSH</div>
  </div>
</div>

<!-- QA Test Results Section -->
<div class="section">
  <div class="card">
    <h2>💬 End-to-End QA Test Results</h2>
    <div class="qa-results">
$QA_HTML
    </div>
    <div style="margin-top:16px; font-family:monospace; font-size:13px; white-space:pre-wrap; background:#f2f2f7; padding:12px; border-radius:8px;">$QA_SCORE</div>
  </div>
</div>

<!-- Health Matrix Section -->
<div class="section">
  <div class="card">
    <h2>🌐 Health Matrix (All Endpoints)</h2>
    <table>
      <thead><tr><th>Port</th><th>Service</th><th>Code</th><th>Preview</th></tr></thead>
      <tbody>
HTMLEOF

  # Add health matrix rows
  if [[ -f "$CURLDIR/matrix.tsv" ]]; then
    tail -n +2 "$CURLDIR/matrix.tsv" | while IFS=$'\t' read -r port svc code preview; do
      badge_class="badge-pass"
      [[ "$code" != "200" ]] && badge_class="badge-fail"
      echo "      <tr><td>$port</td><td>$svc</td><td><span class=\"badge $badge_class\">$code</span></td><td>$(printf '%s' "$preview" | head -c 80)</td></tr>"
    done >>"$HTML_DASH"
  fi

  cat >>"$HTML_DASH" <<HTMLEOF
      </tbody>
    </table>
  </div>
</div>

<!-- Knowledgebase Section -->
<div class="section">
  <div class="card">
    <h2>📚 Knowledgebase Details</h2>
    <pre>$KB_DETAILS</pre>
  </div>
</div>

<!-- Collapsible Logs Section -->
<div class="section">
  <div class="card">
    <h2>📋 All Logs &amp; Artifacts (Expand/Collapse)</h2>
HTMLEOF

  # Add collapsible log sections
  while IFS= read -r logfile; do
    [[ -z "$logfile" ]] && continue
    lname="$(basename "$logfile")"
    echo "    <div class=\"collapsible\">"
    echo "      <div class=\"collapsible-header\" onclick=\"toggleCollapsible(this)\">📄 $lname <span class=\"arrow\"></span></div>"
    echo "      <div class=\"collapsible-content\" id=\"log-$(echo "$lname" | tr '.' '_')\">"
    echo "        <pre>$(cat "$logfile" 2>/dev/null | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g')</pre>"
    echo "      </div>"
    echo "    </div>"
  done <<< "$LOG_FILES" >>"$HTML_DASH"

  cat >>"$HTML_DASH" <<HTMLEOF
  </div>
</div>

<!-- Screenshots Section -->
<div class="section">
  <div class="card">
    <h2>📸 Screenshots</h2>
    <div class="screenshot-grid">
HTMLEOF

  # Add screenshots
  for img in "$SHOT"/*.png; do
    [[ -f "$img" ]] || continue
    name="$(basename "$img")"
    echo "      <div class=\"screenshot-item\"><img src=\"../screenshots/$name\" alt=\"$name\"><div class=\"caption\">$name</div></div>"
  done >>"$HTML_DASH"

  cat >>"$HTML_DASH" <<HTMLEOF
    </div>
    <p style="font-size: 12px; color: #666;">Screenshots captured for all service endpoints (WebUI, health pages, Jenkins login).</p>
  </div>
</div>

<!-- Artifacts Section -->
<div class="section">
  <div class="card">
    <h2>📁 All Artifacts</h2>
    <ul class="artifact-list">
      <li><a href="../REPORT.md">REPORT.md</a> — Full text report</li>
      <li><a href="../run.log">run.log</a> — Complete execution log</li>
      <li><a href="../meta/host_metadata.txt">Host Metadata</a> — System info, uptime, docker state</li>
      <li><a href="../commits/umbrella_commits.txt">Git Commits</a> — All commits (last 3 days)</li>
      <li><a href="../commands/shell_history.txt">Command History</a> — Shell commands, shutdown/reboot events</li>
      <li><a href="../logs/database_and_dvc.log">Database + DVC Logs</a> — PostgreSQL and KB versioning</li>
      <li><a href="../curl/matrix.tsv">Health Matrix (TSV)</a> — Raw health check data</li>
      <li><a href="../e2e/summary.txt">E2E Summary</a> — Chat QA test results</li>
      <li><a href="../kb/kb_details.txt">KB Details</a> — Knowledgebase version, chunks, entity lists</li>
    </ul>
  </div>
</div>

</div>
</body>
<script>
function toggleCollapsible(header) {
  const content = header.nextElementSibling;
  const arrow = header.querySelector('.arrow');
  const isExpanded = header.classList.contains('expanded');
  if (isExpanded) {
    header.classList.remove('expanded');
    content.classList.remove('expanded');
    arrow.style.transform = 'rotate(0deg)';
  } else {
    header.classList.add('expanded');
    content.classList.add('expanded');
    arrow.style.transform = 'rotate(-90deg)';
  }
}
</script>
</html>
HTMLEOF
ok "html dashboard -> $HTML_DASH"
STATUS_HTML="PASSED"

# =============================================================================
# SECTION 15: Redact secrets + pack + push
# =============================================================================
step "Redacting secrets and pushing to GitHub"
find "$OUT" -type f \( -name '*.txt' -o -name '*.log' -o -name '*.json' -o -name '*.md' -o -name '*.tsv' -o -name '*.html' \) -print0 \
    | while IFS= read -r -d '' f; do
      LC_ALL=C sed -E -i.bak \
        -e 's~sk-[A-Za-z0-9_-]+~sk-REDACTED~g' \
        -e 's~(API_KEY|SECRET|PASSWORD|TOKEN|CREDENTIAL|PRIVATE_KEY)[[:space:]]*=[[:space:]]*[^[:space:]]+~\1=REDACTED~g' \
        -e 's~postgresql(\+asyncpg)?://[^[:space:]]+~postgresql://REDACTED~g' \
        -e 's~mysql://[^[:space:]]+~mysql://REDACTED~g' \
        -e 's~redis://[^[:space:]]+~redis://REDACTED~g' \
        "$f" 2>/dev/null || true
      rm -f "$f.bak"
    done

INDEX="$SS_REPO/docs/ops/gpu-recover-reports/README.md"
mkdir -p "$(dirname "$INDEX")"
if [[ ! -f "$INDEX" ]]; then
  cat >"$INDEX" <<'EOF'
# GPU Full Recovery Reports

Generated by `scripts/gpu_full_recover_report.sh` on the production GPU host.
Each subdirectory is one run (UTC timestamp + hostname).
Open `REPORT.md` inside a run for the summary; logs, commits, commands, screenshots, E2E results, and HTML dashboard are alongside.
EOF
fi
{
  echo "- [$RUN_ID](./$RUN_ID/REPORT.md) — **$STATUS** — QA $QA_PASS/$QA_TOTAL — mode $MODE"
} >>"$INDEX"

# =============================================================================
# SECTION 16: Push to standalone health check repo
#
# SAFETY: this push must never be able to trigger CI/builds on the production
# repos. Verified properties (see deploy/gpu/README.md "Health report push"):
#   * target is a SEPARATE repo (Work_RAG_HealthCheck), never the umbrella repo,
#     a component submodule, or the Jenkins multibranch project;
#   * that repo has NO Jenkinsfile, NO .github/workflows, NO .gitlab-ci.yml and
#     NO webhooks (verified via gh api), so a push cannot start a build anywhere;
#   * the remote URL is force-set below, so a stale `origin` from a previous run
#     can never redirect the push into the production repo;
#   * a guard aborts if the resolved origin is the umbrella/production repo.
# =============================================================================
step "Pushing recovery report to standalone repo"
HEALTH_REPO="${GPU_HEALTH_REPO:-https://github.com/AliNikkhah2001/Work_RAG_HealthCheck.git}"
HEALTH_REPO_DIR="${GPU_HEALTH_REPO_DIR:-$HOME/Work_RAG_HealthCheck}"
STATUS_PUSH="FAILED"

# --- Guard: never push into a production repo -------------------------------
# Normalise both URLs to owner/repo for a robust comparison (https vs ssh forms).
norm_repo_slug() {
  printf '%s' "$1" \
    | sed -E 's#^git@[^:]+:#https://x/#' \
    | sed -E 's#^https?://[^/]+/##' \
    | sed -E 's#\.git$##' \
    | tr 'A-Z' 'a-z'
}
HEALTH_SLUG="$(norm_repo_slug "$HEALTH_REPO")"
UMBRELLA_SLUG="$(norm_repo_slug "$(git -C "$UMBRELLA" remote get-url origin 2>/dev/null || echo '')")"
PROTECTED_SLUGS="$UMBRELLA_SLUG"
for sub in "$UMBRELLA"/components/*/; do
  [ -d "$sub/.git" ] || continue
  s="$(norm_repo_slug "$(git -C "$sub" remote get-url origin 2>/dev/null || echo '')")"
  [ -n "$s" ] && PROTECTED_SLUGS="$PROTECTED_SLUGS $s"
done

push_target_is_safe() {
  local slug="$1" p
  [ -n "$slug" ] || return 1
  case "$slug" in
    *healthcheck*) return 0 ;;
  esac
  for p in $PROTECTED_SLUGS; do
    [ "$slug" = "$p" ] && return 1
  done
  return 0
}

if ! push_target_is_safe "$HEALTH_SLUG"; then
  STATUS_PUSH="REFUSED"
  fail "refusing to push: target '$HEALTH_SLUG' is a production repo (protected: $PROTECTED_SLUGS)"
  warn "set GPU_HEALTH_REPO to the standalone health-check repo"
elif [[ "$NO_PUSH" == "1" ]]; then
  STATUS_PUSH="SKIPPED"
  warn "push disabled (--no-push). Report at: $OUT"
else
  PUSH_OK=0
  (
    echo "=== Setting up health check repo ==="
    # Fresh local repo (no clone) to avoid pulling in secret-laden remote history from previous failed pushes
    rm -rf "$HEALTH_REPO_DIR" 2>/dev/null || true
    mkdir -p "$(dirname "$HEALTH_REPO_DIR")"
    git init "$HEALTH_REPO_DIR" 2>&1 | tee -a "$OUT/meta/git-push.log" || true
    git -C "$HEALTH_REPO_DIR" checkout -B main 2>&1 | tee -a "$OUT/meta/git-push.log" || true
    # Force-set the correct remote URL (never push to umbrella repo by accident)
    git -C "$HEALTH_REPO_DIR" remote remove origin 2>/dev/null || true
    git -C "$HEALTH_REPO_DIR" remote add origin "$HEALTH_REPO" 2>&1 | tee -a "$OUT/meta/git-push.log" || true
    # Large multi-MB reports fail with HTTP 400 on HTTP/2 + small postBuffer — force HTTP/1.1 + big buffer
    git -C "$HEALTH_REPO_DIR" config http.version HTTP/1.1
    git -C "$HEALTH_REPO_DIR" config http.postBuffer 524288000
    git -C "$HEALTH_REPO_DIR" config user.name "$(git config user.name 2>/dev/null || echo 'GPU Health Bot')"
    git -C "$HEALTH_REPO_DIR" config user.email "$(git config user.email 2>/dev/null || echo 'health@local')"
    echo "DEBUG: origin URL = $(git -C "$HEALTH_REPO_DIR" config --get remote.origin.url 2>/dev/null || echo 'none')"
    cd "$HEALTH_REPO_DIR"

    # Create a clean branch for this run (does not exist on remote yet)
    git checkout -B "ops/gpu-recover-$RUN_ID" 2>&1 | tee -a "$OUT/meta/git-push.log" || true

    # Organize into dated folder: reports/YYYY/MM/DD/HH-MM/
    REPORT_DATE="$(date -u +%Y/%m/%d/%H-%M)"
    DEST_DIR="reports/$REPORT_DATE-$(hostname -s 2>/dev/null || echo host)"
    rm -rf "$DEST_DIR" 2>/dev/null || true
    mkdir -p "$DEST_DIR"
    cp -r "$OUT"/* "$DEST_DIR/" 2>/dev/null || true

    # Update index README
    echo "- [$RUN_ID](./$DEST_DIR/REPORT.md) — **$STATUS** — QA $QA_PASS/$QA_TOTAL — machine: $(hostname -s 2>/dev/null || echo host) — $(date -u +%Y-%m-%dT%H:%M:%SZ)Z" >> reports/README.md 2>/dev/null || true

    # --- Aggressive secret scrubbing before git add/commit/push ---
    echo "=== Scrubbing secrets from all files before commit ==="
    SCRUB_FILES="$(find "$DEST_DIR" reports/README.md -type f \( -name '*.txt' -o -name '*.log' -o -name '*.json' -o -name '*.md' -o -name '*.tsv' -o -name '*.html' -o -name '*.yaml' -o -name '*.yml' -o -name '*.env' -o -name '*.conf' -o -name '*.cfg' -o -name '*.ini' -o -name '*.sh' -o -name '*.toml' \) ! -name '*.bak' 2>/dev/null || true)"
    echo "DEBUG: SCRUB_FILES count: $(echo "$SCRUB_FILES" | wc -l | tr -d ' ')"

    if [[ -n "$SCRUB_FILES" ]]; then
      echo "$SCRUB_FILES" | while IFS= read -r sf; do
        [[ -f "$sf" ]] || continue
        # LC_ALL=C handles files with invalid UTF-8 bytes (shell history, logs)
        # Use ~ as delimiter to avoid / collisions and | conflicts with alternation
        LC_ALL=C sed -E -i.bak \
          -e 's~sk-[A-Za-z0-9_-]+~sk-REDACTED~g' \
          -e 's~(API_KEY|SECRET|PASSWORD|TOKEN|CREDENTIAL|PRIVATE_KEY|CLIENT_SECRET|ACCESS_TOKEN|REFRESH_TOKEN|AUTH|BEARER)[[:space:]]*=[[:space:]]*[^[:space:]]+~\1=REDACTED~g' \
          -e 's~(https?://)[^/:]+:[^@]+@~\1REDACTED:REDACTED@~g' \
          -e 's~postgresql(\+asyncpg)?://[^[:space:]]+~postgresql://REDACTED~g' \
          -e 's~mysql://[^[:space:]]+~mysql://REDACTED~g' \
          -e 's~redis://[^[:space:]]+~redis://REDACTED~g' \
          -e 's~OPENROUTER_API_KEY=[^[:space:]]+~OPENROUTER_API_KEY=REDACTED~g' \
          -e 's~LANGFUSE_SECRET_KEY=[^[:space:]]+~LANGFUSE_SECRET_KEY=REDACTED~g' \
          -e 's~LANGFUSE_PUBLIC_KEY=[^[:space:]]+~LANGFUSE_PUBLIC_KEY=REDACTED~g' \
          -e 's~ghp_[A-Za-z0-9]{20,}~ghp_REDACTED~g' \
          -e 's~github_pat_[A-Za-z0-9_]{20,}~github_pat_REDACTED~g' \
          -e 's~eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+~JWT_REDACTED~g' \
          "$sf" 2>/dev/null || true
        rm -f "$sf.bak"
      done
    fi

    # Verification: count real (non-placeholder) sk- secrets remaining
    REMAINING_COUNT="$(find "$DEST_DIR" reports/README.md -type f \( -name '*.txt' -o -name '*.log' -o -name '*.json' -o -name '*.md' -o -name '*.tsv' -o -name '*.html' \) ! -name '*.bak' -print0 2>/dev/null | xargs -0 grep -lE 'sk-[A-Za-z0-9_-]{12,}' 2>/dev/null | grep -v 'sk-REDACTED' | wc -l | tr -d ' ')"
    echo "DEBUG: Files with real sk- secrets after scrub: $REMAINING_COUNT"

    # Stage everything (reports/ holds the dated dir + README index)
    git add -A reports 2>&1 | tee -a "$OUT/meta/git-push.log" || true
    git status --short | tee -a "$OUT/meta/git-push.log"

    if git diff --cached --quiet; then
      warn "nothing to commit in health check repo"
    else
      COMMIT_MSG="docs(ops): GPU full recovery report — $(date -u +%Y-%m-%dT%H:%M:%SZ)Z — machine: $(hostname -s 2>/dev/null || echo host) — $MACHINE_TYPE — status: $STATUS"
      git commit -m "$COMMIT_MSG" 2>&1 | tee -a "$OUT/meta/git-push.log"
    fi

    if git push -u origin "ops/gpu-recover-$RUN_ID" 2>&1 | tee -a "$OUT/meta/git-push.log"; then
      echo "PUSH_OK=1" >"$OUT/meta/push_status"
      ok "pushed health check repo: ops/gpu-recover-$RUN_ID"
    else
      echo "PUSH_OK=0" >"$OUT/meta/push_status"
      fail "health check repo push failed — report remains at $OUT"
    fi
  ) || fail "could not operate on health check repo"

  # PUSH_OK is set inside the subshell above, so read it back from disk
  PUSH_OK=0
  [[ -f "$OUT/meta/push_status" ]] && . "$OUT/meta/push_status" 2>/dev/null || true
  if [[ "$PUSH_OK" -eq 1 ]]; then
    STATUS_PUSH="PASSED"
  fi
fi

# =============================================================================
# SECTION 17: Final pass/fail summary
# =============================================================================
step "Final status summary"
echo ""
echo "${CYAN}======================================================================${NC}"
echo "${CYAN}  FINAL PASS/FAIL STATUS — $RUN_ID${NC}"
echo "${CYAN}======================================================================${NC}"
printf "  %-30s %s\n" "Server restart:"   "$([ "$STATUS_RESTART" = "PASSED" ] && echo "${GREEN}PASSED${NC}" || [ "$STATUS_RESTART" = "SKIPPED" ] && echo "${YELLOW}SKIPPED${NC}" || echo "${RED}FAILED${NC}")"
printf "  %-30s %s\n" "Smoke tests:"    "$([ "$STATUS_SMOKE" = "PASSED" ] && echo "${GREEN}PASSED${NC}" || echo "${RED}FAILED${NC}")"
printf "  %-30s %s\n" "E2E QA tests:"   "$([ "$STATUS_E2E" = "PASSED" ] && echo "${GREEN}PASSED${NC}" || echo "${RED}FAILED${NC}")"
printf "  %-30s %s\n" "HTML dashboard:" "$([ "$STATUS_HTML" = "PASSED" ] && echo "${GREEN}PASSED${NC}" || echo "${RED}FAILED${NC}")"
printf "  %-30s %s\n" "GitHub push:"    "$([ "$STATUS_PUSH" = "PASSED" ] && echo "${GREEN}PASSED${NC}" || [ "$STATUS_PUSH" = "SKIPPED" ] && echo "${YELLOW}SKIPPED${NC}" || echo "${RED}FAILED${NC}")"
echo "${CYAN}======================================================================${NC}"
echo ""

ok "wrote $REPORT"
echo ""
echo "${GREEN}======================================================================${NC}"
echo "${GREEN}  Recovery report complete — $RUN_ID${NC}"
echo "${GREEN}======================================================================${NC}"
echo "  Report:      $REPORT"
echo "  Dashboard:   $HTML_DASH"
echo "  Output dir:  $OUT"
echo "  Overall:     $STATUS"
if [[ -n "${BRANCH:-}" ]]; then
  echo "  Branch:      $BRANCH"
fi
echo ""

# --- Auto-open HTML dashboard after run completes ---
if [[ "$DAEMON_MODE" != "1" ]]; then
  echo "${CYAN}Opening HTML dashboard...${NC}"
  if [[ "$(uname -s)" == "Darwin" ]]; then
    open "$HTML_DASH" 2>/dev/null && ok "dashboard opened in browser" || warn "could not auto-open dashboard"
  elif have xdg-open; then
    xdg-open "$HTML_DASH" 2>/dev/null && ok "dashboard opened in browser" || warn "could not auto-open dashboard"
  else
    warn "no browser opener available — open manually: $HTML_DASH"
  fi
fi

echo "View the summary from your laptop:"
echo "  cat $REPORT"
echo ""