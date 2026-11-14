#!/usr/bin/env bash
# Bootstrap Dana / Work Credit RAG on this host (laptop test by default).
#
#   bash scripts/setup_project.sh              # docker + submodules + env + jenkins + local stack
#   bash scripts/setup_project.sh --with-stage # also bring up dana-stage
#   bash scripts/setup_project.sh --jenkins-only
#   bash scripts/setup_project.sh --stack-only
#   bash scripts/setup_project.sh --gpu        # GPU host: jenkins prod + compose.gpu (no OpenRouter)
#   bash scripts/setup_project.sh --check      # health only
#
# Does NOT start Gemma/Manager/TRT (those are managed under server-setup).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

WITH_STAGE=0
JENKINS_ONLY=0
STACK_ONLY=0
GPU=0
CHECK_ONLY=0
SKIP_BUILD=0

for arg in "$@"; do
  case "$arg" in
    --with-stage) WITH_STAGE=1 ;;
    --jenkins-only) JENKINS_ONLY=1 ;;
    --stack-only) STACK_ONLY=1 ;;
    --gpu) GPU=1 ;;
    --check) CHECK_ONLY=1 ;;
    --skip-build) SKIP_BUILD=1 ;;
    -h|--help)
      sed -n '1,20p' "$0"
      exit 0
      ;;
    *)
      echo "unknown arg: $arg" >&2
      exit 2
      ;;
  esac
done

log()  { printf '[setup] %s\n' "$*"; }
ok()   { printf '[ok]    %s\n' "$*"; }
warn() { printf '[warn]  %s\n' "$*"; }
fail() { printf '[fail]  %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"
}

wait_docker() {
  local i
  if docker info >/dev/null 2>&1; then
    ok "Docker daemon reachable"
    return 0
  fi
  if [[ "$(uname -s)" == "Darwin" ]]; then
    log "Starting Docker Desktop…"
    open -a Docker 2>/dev/null || true
  fi
  for i in $(seq 1 60); do
    if docker info >/dev/null 2>&1; then
      ok "Docker ready (after ${i}s)"
      return 0
    fi
    sleep 2
  done
  fail "Docker daemon not available — start Docker Desktop / dockerd and retry"
}

ensure_env_laptop() {
  local envf="$ROOT/deploy/compose/.env"
  local ex="$ROOT/deploy/compose/.env.example"
  if [[ ! -f "$envf" ]]; then
    [[ -f "$ex" ]] || fail "missing $ex"
    cp "$ex" "$envf"
    chmod 600 "$envf" || true
    warn "created $envf — set OPENROUTER_API_KEY before chat works"
  else
    ok "found deploy/compose/.env"
  fi
  if ! grep -q '^OPENROUTER_API_KEY=.\+' "$envf" 2>/dev/null; then
    warn "OPENROUTER_API_KEY looks empty in .env (LiteLLM/OpenRouter chat will fail)"
  fi
  # Keep laptop selectors consistent
  if ! grep -q '^DANA_ENV=test' "$envf"; then
    warn "DANA_ENV should be test on laptop (see deploy/compose/README.md)"
  fi
}

ensure_env_gpu() {
  local envf="$ROOT/deploy/compose/.env.prod"
  local ex="$ROOT/deploy/compose/.env.example"
  if [[ ! -f "$envf" ]]; then
    [[ -f "$ex" ]] || fail "missing $ex"
    cp "$ex" "$envf"
    chmod 600 "$envf" || true
    # Force prod selectors (edit URLs for Manager/Gemma on this host)
    if command -v python3 >/dev/null 2>&1; then
      python3 - <<'PY'
from pathlib import Path
p = Path("deploy/compose/.env.prod")
lines = []
seen = set()
repl = {
    "DANA_ENV": "prod",
    "LLM_UPSTREAM_MODE": "self_hosted",
    "KB_EMBED_DEVICE": "cuda",
    "KB_RERANKER_DEVICE": "cuda",
    "UPSTREAM_LLM_BASE_URL": "http://127.0.0.1:18000/v1",
}
for raw in p.read_text().splitlines():
    if not raw or raw.lstrip().startswith("#") or "=" not in raw:
        lines.append(raw)
        continue
    k, _, v = raw.partition("=")
    if k in repl:
        lines.append(f"{k}={repl[k]}")
        seen.add(k)
    else:
        lines.append(raw)
for k, v in repl.items():
    if k not in seen:
        lines.append(f"{k}={v}")
p.write_text("\n".join(lines) + "\n")
PY
    fi
    warn "created $envf — confirm UPSTREAM_LLM_BASE_URL / no OpenRouter keys on GPU"
  else
    ok "found deploy/compose/.env.prod"
  fi
  if grep -q '^LLM_UPSTREAM_MODE=openrouter' "$envf" 2>/dev/null; then
    fail "GPU .env.prod must NOT use LLM_UPSTREAM_MODE=openrouter"
  fi
}

sync_submodules() {
  log "Syncing git submodules…"
  git submodule sync --recursive || true
  # Top-level required; nested kb-source optional for runtime images
  git submodule update --init --depth 1
  bash "$ROOT/scripts/ci_submodule_sync.sh" || warn "ci_submodule_sync reported issues (optional nested pins may be soft-failed)"
  ok "submodules updated"
}

start_jenkins_laptop() {
  log "Starting Jenkins (stage controller)…"
  # Patch host path in compose is already absolute for this Mac clone
  docker compose -f deploy/jenkins/docker-compose.yml up -d --build
  ok "Jenkins → http://127.0.0.1:8085"
  if docker exec dana-jenkins test -f /var/jenkins_home/secrets/initialAdminPassword 2>/dev/null; then
    warn "fresh Jenkins password: docker exec dana-jenkins cat /var/jenkins_home/secrets/initialAdminPassword"
  fi
}

start_jenkins_gpu() {
  log "Starting Jenkins (prod controller)…"
  # Expect operator to have fixed DANA_HOST_REPO bind in compose / gpu overlay
  docker compose -f deploy/jenkins/docker-compose.yml \
    -f deploy/jenkins/docker-compose.gpu.yml up -d --build
  ok "Jenkins (prod) → http://127.0.0.1:8085"
}

start_stack_laptop() {
  log "Starting laptop stack dana-local…"
  if [[ "$SKIP_BUILD" == "1" ]]; then
    docker compose -p dana-local \
      -f deploy/compose/compose.base.yml \
      -f deploy/compose/compose.local.yml \
      --env-file deploy/compose/.env \
      up -d
  else
    docker compose -p dana-local \
      -f deploy/compose/compose.base.yml \
      -f deploy/compose/compose.local.yml \
      --env-file deploy/compose/.env \
      up -d --build
  fi
  ok "local stack up (WebUI :13000, orch :8100, KB :8000)"
}

start_stack_stage() {
  log "Starting stage stack dana-stage…"
  if [[ "$SKIP_BUILD" == "1" ]]; then
    docker compose -p dana-stage \
      -f deploy/compose/compose.base.yml \
      -f deploy/compose/compose.local.yml \
      -f deploy/compose/compose.stage.yml \
      --env-file deploy/compose/.env \
      up -d
  else
    docker compose -p dana-stage \
      -f deploy/compose/compose.base.yml \
      -f deploy/compose/compose.local.yml \
      -f deploy/compose/compose.stage.yml \
      --env-file deploy/compose/.env \
      up -d --build
  fi
  ok "stage stack up (WebUI :13100, orch :18100, KB :18000)"
}

start_stack_gpu() {
  log "Starting GPU app stack dana-prod…"
  if [[ "$SKIP_BUILD" == "1" ]]; then
    docker compose -p dana-prod \
      -f deploy/compose/compose.base.yml \
      -f deploy/compose/compose.gpu.yml \
      --env-file deploy/compose/.env.prod \
      up -d
  else
    docker compose -p dana-prod \
      -f deploy/compose/compose.base.yml \
      -f deploy/compose/compose.gpu.yml \
      --env-file deploy/compose/.env.prod \
      up -d --build
  fi
  ok "prod app stack up (expects Gemma/Manager already on host)"
}

health_check() {
  log "Health probes…"
  local ports=(8100 8200 8000 4000 13000 8085)
  if [[ "$WITH_STAGE" == "1" ]] || docker ps --format '{{.Names}}' | grep -q '^dana-stage-'; then
    ports+=(18100 18200 18000 13100)
  fi
  if [[ "$GPU" == "1" ]]; then
    ports=(8100 8200 8000 8085)
  fi
  local p code
  for p in "${ports[@]}"; do
    code="$(curl -sS -o /tmp/dana_health_$p.txt -w '%{http_code}' --max-time 5 "http://127.0.0.1:$p/health" 2>/dev/null || true)"
    if [[ "$code" != "200" ]]; then
      code="$(curl -sS -o /tmp/dana_health_$p.txt -w '%{http_code}' --max-time 5 "http://127.0.0.1:$p/health/liveliness" 2>/dev/null || true)"
    fi
    if [[ "$code" == "200" ]]; then
      ok "port $p → $code"
    elif [[ "$p" == "8085" ]]; then
      code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:8085/login" 2>/dev/null || true)"
      if [[ "$code" == "200" ]]; then ok "Jenkins :8085 login → $code"; else warn "Jenkins :8085 → $code"; fi
    elif [[ "$p" == "13000" || "$p" == "13100" ]]; then
      code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:$p/" 2>/dev/null || true)"
      if [[ "$code" == "200" ]]; then ok "WebUI :$p → $code"; else warn "WebUI :$p → $code (may still be starting)"; fi
    else
      warn "port $p → ${code:-down} (warmup OK for KB/models)"
    fi
  done
}

print_next() {
  cat <<EOF

=== Next ===
  WebUI (local):  http://127.0.0.1:13000
  Orch API:       http://127.0.0.1:8100/v1/chat/completions
  KB:             http://127.0.0.1:8000/health
  Jenkins:        http://127.0.0.1:8085
  Stage WebUI:    http://127.0.0.1:13100   (if --with-stage)

  Re-check:       bash scripts/setup_project.sh --check
  GPU keep-latest daemon docs: scripts/gpu_keep_latest.sh --help
EOF
}

# ── main ──────────────────────────────────────────────────────────
need_cmd docker
need_cmd git
need_cmd curl

if [[ "$CHECK_ONLY" == "1" ]]; then
  wait_docker
  health_check
  exit 0
fi

wait_docker

if [[ "$GPU" == "1" ]]; then
  ensure_env_gpu
else
  ensure_env_laptop
fi

if [[ "$STACK_ONLY" != "1" ]]; then
  sync_submodules
fi

if [[ "$STACK_ONLY" == "1" ]]; then
  :
elif [[ "$JENKINS_ONLY" == "1" ]]; then
  if [[ "$GPU" == "1" ]]; then start_jenkins_gpu; else start_jenkins_laptop; fi
  health_check
  print_next
  exit 0
else
  if [[ "$GPU" == "1" ]]; then start_jenkins_gpu; else start_jenkins_laptop; fi
fi

if [[ "$JENKINS_ONLY" == "1" ]]; then
  exit 0
fi

if [[ "$GPU" == "1" ]]; then
  start_stack_gpu
else
  start_stack_laptop
  if [[ "$WITH_STAGE" == "1" ]]; then
    start_stack_stage
  fi
fi

log "Waiting briefly for healthchecks…"
sleep 15
health_check
print_next
ok "setup finished"
