#!/usr/bin/env bash
# =============================================================================
# scripts/diagnose_edge_path.sh — locate the broken hop for chat.ics24.ir
#
# Read-only by default: it changes nothing and creates no files. Add --report to
# capture every probe on disk, and --push to publish that run to the separate
# Work_RAG_HealthCheck GitHub Pages repo so the result is readable from a laptop
# that has no shell access to the GPU host.
#
#   bash scripts/diagnose_edge_path.sh                       # read-only
#   bash scripts/diagnose_edge_path.sh --edge-ip 10.10.34.36 --port 13000
#   bash scripts/diagnose_edge_path.sh --report              # write a run dir
#   bash scripts/diagnose_edge_path.sh --push                # write + publish
#
# THE CHAIN we are testing (each hop is a separate, independent failure mode):
#
#   [1] public DNS      chat.ics24.ir -> ???          (what internet resolvers say)
#   [2] internal DNS    chat.ics24.ir -> ???          (what the internal resolver says)
#   [3] edge IP owner   is the edge address on THIS host?
#   [4] routes          who would carry traffic to the edge?
#   [5] host bind       is the host listening on the IP the edge targets?
#   [6] container bind  is the webui container publishing that port?
#   [7] app             does the app answer on loopback?
#   [8] edge -> host    can this host reach the edge address itself?
#   [9] TLS/SNI         does the edge terminate TLS for this hostname?
#  [10] host firewall   ufw/firewalld/iptables/pf view
#
# The verdict tells you WHICH hop to fix. Hop 5 is the common one: Docker
# publishes 192.168.x and 127.0.0.1, while DNS points at 10.10.34.36, so nothing
# listens on the address the edge actually dials.
#
# EXIT CODES (same convention as deploy/gpu/lib/common.sh):
#   0   every hop passed (WARN/SKIP do not fail a run)
#   1   at least one hop FAILED
#   64  refused / usage error — nothing was probed
#
# ROOT IS NOT REQUIRED. Without root these hops degrade, and say so:
#   * hop 5 cannot show the owning process (`ss -p` / `lsof` process column)
#   * hop 10 cannot read iptables/pf rules on most hosts
#   * hop 6 needs docker group membership or root to talk to the daemon
# Missing tools never abort the run: the hop is recorded as SKIP plus a
# `tool_missing=` line, so a reader can tell "not tested" from "test passed".
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- defaults (env-overridable, same names as before) ------------------------
EDGE_IP="${EDGE_IP:-10.10.34.36}"
EDGE_HOST="${EDGE_HOST:-chat.ics24.ir}"
APP_PORT="${APP_PORT:-13000}"
INTERNAL_DNS="${INTERNAL_DNS:-}"

# --- mode flags --------------------------------------------------------------
REPORT_MODE=0          # write a run directory on disk
PUSH_MODE=0            # publish that run directory
NO_PUSH_SEEN=0         # --no-push wins over --push
OUT_DIR_ARG=""         # --out-dir override
RUN_ID_ARG=""          # --run-id override (deterministic tests / re-publish)
REDACT_ONLY=""         # --redact-only DIR (sanitize a tree, then exit)

usage() {
  sed -n '2,42p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  cat <<'EOF'

FLAGS
  --edge-ip IP        edge address DNS points at        (default 10.10.34.36)
  --edge-host NAME    public hostname                   (default chat.ics24.ir)
  --port N            app port on the host              (default 13000)
  --dns IP            internal resolver to query        (default: system resolver)
  --report            capture every probe into a run directory on disk
  --push              implies --report, then publish the run to the health repo
  --out-dir DIR       run directory (default $DANA_STATE_DIR/dana-edge-diag/<RUN_ID>
                      or ${TMPDIR:-/tmp}/dana-edge-diag/<RUN_ID>)
  --run-id ID         reuse an explicit run id instead of <UTCSTAMP>-<host>
  --no-push           explicit override: collect on disk, publish nothing
  --redact-only DIR   sanitize DIR in place and exit (secret-removal self-test)
  -h, --help          this help

PUBLISHING
  Publishing reuses scripts/monitor/publish_report.py, the same publisher the
  nightly health report uses. It writes runs/<RUN_ID>.json, latest/, and
  logs/<RUN_ID>/ into Work_RAG_HealthCheck and pushes that repo's main branch.
  The source repo is never a legal target: if the resolved remote normalises to
  Work_Credit-RAG_Phase1 or Work_RAG-Server-Setup the script refuses with 64.

  Env: GPU_HEALTH_REPO / GPU_HEALTH_REPO_DIR / GPU_HEALTH_BRANCH
       (also DANA_EDGE_DIAG_REPO, _REPO_DIR, _BRANCH)
EOF
}

need_val() {
  if [[ $# -lt 2 || -z "${2:-}" ]]; then
    printf 'error: %s requires a value\n' "$1" >&2
    exit 64
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --edge-ip)     need_val "$@"; EDGE_IP="$2"; shift 2 ;;
    --edge-ip=*)   EDGE_IP="${1#*=}"; shift ;;
    --edge-host)   need_val "$@"; EDGE_HOST="$2"; shift 2 ;;
    --edge-host=*) EDGE_HOST="${1#*=}"; shift ;;
    --port)        need_val "$@"; APP_PORT="$2"; shift 2 ;;
    --port=*)      APP_PORT="${1#*=}"; shift ;;
    --dns)         need_val "$@"; INTERNAL_DNS="$2"; shift 2 ;;
    --dns=*)       INTERNAL_DNS="${1#*=}"; shift ;;
    --report)      REPORT_MODE=1; shift ;;
    --push)        PUSH_MODE=1; REPORT_MODE=1; shift ;;
    --out-dir)     need_val "$@"; OUT_DIR_ARG="$2"; shift 2 ;;
    --out-dir=*)   OUT_DIR_ARG="${1#*=}"; shift ;;
    --run-id)      need_val "$@"; RUN_ID_ARG="$2"; shift 2 ;;
    --run-id=*)    RUN_ID_ARG="${1#*=}"; shift ;;
    --no-push)     NO_PUSH_SEEN=1; PUSH_MODE=0; shift ;;
    --redact-only) need_val "$@"; REDACT_ONLY="$2"; shift 2 ;;
    --redact-only=*) REDACT_ONLY="${1#*=}"; shift ;;
    -h|--help)     usage; exit 0 ;;
    *) printf 'unknown argument: %s (try --help)\n' "$1" >&2; exit 64 ;;
  esac
done

if ! [[ "$APP_PORT" =~ ^[0-9]+$ ]]; then
  printf 'error: --port must be numeric, got %s\n' "$APP_PORT" >&2
  exit 64
fi

COLOR=0
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then COLOR=1; fi
if [[ "$COLOR" -eq 1 ]]; then
  C_OK=$'\033[32m'; C_BAD=$'\033[31m'; C_WARN=$'\033[33m'; C_DIM=$'\033[2m'
  C_BOLD=$'\033[1m'; C_OFF=$'\033[0m'
else
  C_OK=""; C_BAD=""; C_WARN=""; C_DIM=""; C_BOLD=""; C_OFF=""
fi

# =============================================================================
# redaction
# =============================================================================
# Every file we publish passes through this. It is deliberately conservative:
# over-redacting a diagnostic report costs nothing, a leaked token costs a lot.
# Naming matches the pass in gpu_full_recover_report.sh so both publishers
# remove the same shapes.
redact_file() {
  local f="$1" tmp="$1.redact.$$" out="$1.redacted.$$"
  [[ -f "$f" ]] || return 0
  # 1) PEM private-key bodies span lines: sed cannot express that portably.
  awk '
    /-----BEGIN [A-Z ]*PRIVATE KEY-----/ { print "-----BEGIN PRIVATE KEY----- [REDACTED]"; inkey=1; next }
    inkey == 1 && /-----END [A-Z ]*PRIVATE KEY-----/ { print "-----END PRIVATE KEY-----"; inkey=0; next }
    inkey == 1 { next }
    { print }
  ' "$f" >"$tmp" 2>/dev/null || { rm -f "$tmp"; return 1; }
  # 2) single-line secret shapes. Written to a separate file so a sed failure
  #    can never leave the ORIGINAL (unredacted) content in place.
  LC_ALL=C sed -E \
    -e 's~(Authorization|authorization|AUTHORIZATION):[[:space:]]*(Bearer|bearer|Basic|basic|Token|token)[[:space:]]+[^[:space:]]+~\1: \2 [REDACTED]~g' \
    -e 's~(Bearer|bearer)[[:space:]]+[A-Za-z0-9._~+/=-]{16,}~\1 [REDACTED]~g' \
    -e 's~sk-[A-Za-z0-9_-]{8,}~sk-REDACTED~g' \
    -e 's~gh[pousr]_[A-Za-z0-9]{16,}~gh-REDACTED~g' \
    -e 's~github_pat_[A-Za-z0-9_]{20,}~github_pat-REDACTED~g' \
    -e 's~(API_KEY|APIKEY|API-KEY|SECRET|PASSWORD|PASSWD|PASS|TOKEN|CREDENTIAL|PRIVATE_KEY|PRIVATE-KEY|ACCESS_KEY|CLIENT_SECRET|AUTH_TOKEN|api_key|apikey|secret|password|passwd|pass|token|credential|private_key|access_key|client_secret|auth_token)([[:space:]]*[=:][[:space:]]*)("[^"]*"|'"'"'[^'"'"']*'"'"'|[^[:space:]]+)~\1\2REDACTED~g' \
    -e 's~postgres(ql)?(\+asyncpg)?://[^[:space:]"'"'"']+~postgresql://REDACTED~g' \
    -e 's~mysql://[^[:space:]"'"'"']+~mysql://REDACTED~g' \
    -e 's~redis://[^[:space:]"'"'"']+~redis://REDACTED~g' \
    -e 's~https?://[^/:@[:space:]]+:[^/@[:space:]]+@~https://REDACTED@~g' \
    "$tmp" >"$out" 2>/dev/null
  local rc=$?
  rm -f "$tmp"
  if [[ "$rc" -ne 0 || ! -f "$out" ]]; then
    # Refuse to publish rather than keep a file we failed to sanitize.
    rm -f "$out"
    return 1
  fi
  mv -f "$out" "$f" 2>/dev/null || { rm -f "$out"; return 1; }
  return 0
}

# Names the health publisher refuses to copy (shell history, verbose host logs).
# They are quarantined out of the run directory so they cannot be published even
# if a future caller drops one there.
_sensitive_name() {
  local name="$1"
  case "$name" in
    command_shutdown_reboot_user.log|commands.txt|bash_history.txt|shell_history.txt|docker_inspect.txt)
      return 0 ;;
    host-*|env*|docker-env*) return 0 ;;
  esac
  return 1
}

# redact_tree DIR [REPORTFILE]
#   Redacts every text artifact under DIR and quarantines sensitive names into
#   DIR/redacted/ (which is not a published subdirectory). Writes a summary of
#   counts only — never the secret values — to REPORTFILE when given.
redact_tree() {
  local dir="$1" summary="${2:-}" scanned=0 changed=0 quarantined=0 failed=0
  local f before after
  [[ -d "$dir" ]] || return 0
  mkdir -p "$dir/redacted" 2>/dev/null || true

  while IFS= read -r -d '' f; do
    if _sensitive_name "$(basename "$f")"; then
      # Quarantine: move it out of any published subdirectory. If the move
      # fails the file is deleted instead — it must never be published.
      if mv "$f" "$dir/redacted/" 2>/dev/null; then
        quarantined=$((quarantined + 1))
      else
        rm -f "$f" 2>/dev/null && quarantined=$((quarantined + 1))
      fi
      continue
    fi
    scanned=$((scanned + 1))
    before="$(cksum <"$f" 2>/dev/null)"
    if ! redact_file "$f"; then
      failed=$((failed + 1))
      rm -f "$f" 2>/dev/null
      continue
    fi
    after="$(cksum <"$f" 2>/dev/null)"
    [[ "$before" != "$after" ]] && changed=$((changed + 1))
  done < <(find "$dir" -type f \
             \( -name '*.txt' -o -name '*.log' -o -name '*.json' -o -name '*.md' \
                -o -name '*.tsv' -o -name '*.html' -o -name '*.yml' \) \
             -not -path "$dir/redacted/*" -print0 2>/dev/null)

  if [[ -n "$summary" ]]; then
    {
      echo "# redaction summary"
      echo "scope=$(basename "$dir")"
      echo "files_scanned=$scanned"
      echo "files_changed=$changed"
      echo "files_quarantined=$quarantined"
      echo "files_deleted_unsanitizable=$failed"
      echo "rules=authorization-header bearer-token sk-key github-token key=value db-url url-userinfo private-key"
      echo "# Only counts are recorded here; redacted values never reach this file."
    } >"$summary" 2>/dev/null || true
  fi
  printf 'redaction: scanned=%s changed=%s quarantined=%s deleted=%s\n' \
    "$scanned" "$changed" "$quarantined" "$failed"
  [[ "$failed" -eq 0 ]]
}

if [[ -n "$REDACT_ONLY" ]]; then
  if [[ ! -d "$REDACT_ONLY" ]]; then
    printf 'error: --redact-only needs an existing directory: %s\n' "$REDACT_ONLY" >&2
    exit 64
  fi
  redact_tree "$REDACT_ONLY" "$REDACT_ONLY/redaction_report.txt"
  exit 0
fi

if [[ "$NO_PUSH_SEEN" -eq 1 && "$PUSH_MODE" -eq 1 ]]; then
  printf 'note: --no-push overrides --push; nothing will be published\n' >&2
  PUSH_MODE=0
fi

# =============================================================================
# publish-target guard (must run before any probe)
# =============================================================================
# The health repo is the ONLY legal push target. A stale GPU_HEALTH_REPO that
# still points at the umbrella repo or a component would push a diagnostic run
# into production, so this refuses instead of warning.
norm_repo_slug() {
  printf '%s' "$1" \
    | sed -E 's#^git@[^:]+:#https://x/#' \
    | sed -E 's#^https?://[^/]+/##' \
    | sed -E 's#\.git$##' \
    | tr 'A-Z' 'a-z'
}

is_local_path() {
  case "$1" in
    /*|./*|../*|~*) return 0 ;;
  esac
  return 1
}

# Prints "safe" or "unsafe:<reason>". Never echoes credentials: only the slug.
push_target_verdict() {
  local raw="$1" slug
  if [[ -z "$raw" ]]; then
    printf 'unsafe:empty-remote'
    return 0
  fi
  slug="$(norm_repo_slug "$raw")"
  # 1) production source repos: hard refusal, no override.
  case "$slug" in
    *work_credit-rag_phase1*|*work_rag-server-setup*|*work_rag-kb*|*work_rag-orchestrator*|*work_rag-guardrails*|*work_rag-webui*)
      printf 'unsafe:production-repo:%s' "$slug"
      return 0 ;;
  esac
  # 2) a filesystem remote cannot be a production host. Used by the local
  #    end-to-end test (temporary bare repo) and by air-gapped mirrors.
  if is_local_path "$raw"; then
    printf 'safe:local-path'
    return 0
  fi
  # 3) the one remote we do accept.
  case "$slug" in
    *healthcheck*) printf 'safe:health-repo:%s' "$slug"; return 0 ;;
  esac
  printf 'unsafe:not-the-health-repo:%s' "$slug"
}

HEALTH_REMOTE="${DANA_EDGE_DIAG_REPO:-${GPU_HEALTH_REPO:-https://github.com/AliNikkhah2001/Work_RAG_HealthCheck.git}}"
HEALTH_REPO_DIR="${DANA_EDGE_DIAG_REPO_DIR:-${GPU_HEALTH_REPO_DIR:-$HOME/Work_RAG_HealthCheck}}"
HEALTH_BRANCH="${DANA_EDGE_DIAG_BRANCH:-${GPU_HEALTH_BRANCH:-main}}"

if [[ "$PUSH_MODE" -eq 1 ]]; then
  TARGET_VERDICT="$(push_target_verdict "$HEALTH_REMOTE")"
  case "$TARGET_VERDICT" in
    safe:*) : ;;
    *)
      printf 'refusing to publish: %s\n' "${TARGET_VERDICT#unsafe:}" >&2
      printf '  resolved remote: %s\n' "$(norm_repo_slug "$HEALTH_REMOTE")" >&2
      printf '  only the standalone health-check repo may be pushed to;\n' >&2
      printf '  set GPU_HEALTH_REPO (or DANA_EDGE_DIAG_REPO) to it.\n' >&2
      printf '  nothing was probed.\n' >&2
      exit 64 ;;
  esac
fi

# =============================================================================
# run directory + logging
# =============================================================================
MACHINE_NAME="$(hostname -s 2>/dev/null || hostname 2>/dev/null || echo host)"
MACHINE_NAME="$(printf '%s' "$MACHINE_NAME" | tr -cd 'A-Za-z0-9._-')"
[[ -n "$MACHINE_NAME" ]] || MACHINE_NAME="host"

case "$(uname -s 2>/dev/null || echo unknown)" in
  Darwin) MACHINE_TYPE="dev_laptop" ;;
  *)
    if [[ -f /etc/os-release ]] && grep -qiE 'ubuntu|centos|rhel|amzn|rocky|almalinux' /etc/os-release 2>/dev/null; then
      MACHINE_TYPE="production_gpu"
    else
      MACHINE_TYPE="generic_linux"
    fi ;;
esac

RUN_ID="${RUN_ID_ARG:-$(date -u +%Y%m%dT%H%M%SZ)-${MACHINE_NAME}}"
UTC_NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ "$REPORT_MODE" -eq 1 ]]; then
  if [[ -n "$OUT_DIR_ARG" ]]; then
    OUT="$OUT_DIR_ARG"
  else
    BASE="${DANA_STATE_DIR:-${TMPDIR:-/tmp}/dana-edge-diag}"
    BASE="${BASE%/}"
    OUT="$BASE/$RUN_ID"
  fi
  mkdir -p "$OUT"/{meta,redacted,curl} || {
    printf 'error: cannot create run directory %s\n' "$OUT" >&2
    exit 64
  }
  RUN_LOG="$OUT/run.log"
  : >"$RUN_LOG"
else
  OUT=""
  RUN_LOG=""
fi

IS_ROOT=0
[[ "$(id -u 2>/dev/null || echo 1)" -eq 0 ]] && IS_ROOT=1

_log() { [[ "$REPORT_MODE" -eq 1 ]] && printf '%s\n' "$*" >>"$RUN_LOG" 2>/dev/null; return 0; }
say()  { printf '%s\n' "$*"; _log "$*"; }
hdr()  { printf '\n%s=== %s ===%s\n' "$C_BOLD" "$1" "$C_OFF"; _log ""; _log "=== $1 ==="; }
ok()   { printf '  %sOK%s    %s\n' "$C_OK" "$C_OFF" "$*"; _log "  OK    $*"; }
bad()  { printf '  %sFAIL%s  %s\n' "$C_BAD" "$C_OFF" "$*"; _log "  FAIL  $*"; }
wrn()  { printf '  %sWARN%s  %s\n' "$C_WARN" "$C_OFF" "$*"; _log "  WARN  $*"; }
skip() { printf '  %sSKIP%s  %s\n' "$C_DIM" "$C_OFF" "$*"; _log "  SKIP  $*"; }
note() { printf '        %s%s%s\n' "$C_DIM" "$*" "$C_OFF"; _log "        $*"; }

have() { command -v "$1" >/dev/null 2>&1; }

# run_timeout SECONDS CMD...
# GNU coreutils' `timeout` is missing on stock macOS (only `gtimeout` if
# coreutils is installed), and a filtered port makes openssl block for minutes.
# The background+watchdog fallback is portable and keeps hop 9 honest on a Mac.
run_timeout() {
  local secs="$1"; shift
  if have timeout; then timeout "$secs" "$@"; return $?; fi
  if have gtimeout; then gtimeout "$secs" "$@"; return $?; fi
  "$@" &
  local pid=$! watcher rc
  ( sleep "$secs"; kill -9 "$pid" 2>/dev/null ) >/dev/null 2>&1 &
  watcher=$!
  wait "$pid" 2>/dev/null; rc=$?
  kill "$watcher" 2>/dev/null
  wait "$watcher" 2>/dev/null
  return $rc
}

# capture NAME CMD...   run CMD, save stdout+stderr to meta/NAME, echo it back.
# Returns CMD's exit status. An empty result is recorded explicitly so a reader
# can tell "ran, produced nothing" from "never ran".
capture() {
  local name="$1"; shift
  local rc=0 out
  out="$("$@" 2>&1)" || rc=$?
  if [[ "$REPORT_MODE" -eq 1 ]]; then
    {
      if [[ -n "$out" ]]; then printf '%s\n' "$out"; else printf '(no output; exit=%s)\n' "$rc"; fi
      printf -- '--- exit=%s cmd=%s\n' "$rc" "$*"
    } >"$OUT/meta/$name" 2>/dev/null || true
  fi
  [[ -n "$out" ]] && printf '%s\n' "$out"
  return $rc
}

# capture_pipe NAME   same, but reads stdin so pipelines stay pipelines.
capture_pipe() {
  local name="$1" data=""
  data="$(cat 2>/dev/null)"
  if [[ "$REPORT_MODE" -eq 1 ]]; then
    {
      if [[ -n "$data" ]]; then printf '%s\n' "$data"; else printf '(no output; stdin)\n'; fi
    } >"$OUT/meta/$name" 2>/dev/null || true
  fi
  [[ -n "$data" ]] && printf '%s\n' "$data"
  return 0
}

# ev_note NAME TEXT...   append a plain fact to meta/NAME (evidence only).
ev_note() {
  local name="$1"; shift
  [[ "$REPORT_MODE" -eq 1 && -n "${OUT:-}" ]] || return 0
  printf '%s\n' "$*" >>"$OUT/meta/$name" 2>/dev/null || true
}

# --- hop bookkeeping (bash 3.2: parallel indexed arrays) --------------------
HOP_NUM=(); HOP_NAME=(); HOP_RESULT=(); HOP_DETAIL=()
hop_result() {
  HOP_NUM+=("$1"); HOP_NAME+=("$2"); HOP_RESULT+=("$3"); HOP_DETAIL+=("$4")
  case "$3" in
    PASS) ok "$4" ;;
    FAIL) bad "$4" ;;
    WARN) wrn "$4" ;;
    *)    skip "$4" ;;
  esac
}

printf '%s=== edge path diagnosis: %s -> :%s ===%s\n' \
  "$C_BOLD" "$EDGE_HOST" "$APP_PORT" "$C_OFF"
_log "=== edge path diagnosis: $EDGE_HOST -> :$APP_PORT ==="
say "  assumed edge IP : $EDGE_IP   (override with --edge-ip)"
say "  app port        : $APP_PORT"
say "  run id          : $RUN_ID"
if [[ "$REPORT_MODE" -eq 1 ]]; then
  say "  report dir      : $OUT"
fi
if [[ "$IS_ROOT" -eq 1 ]]; then
  say "  privilege       : root (process names and firewall rules readable)"
else
  say "  privilege       : unprivileged (hops 5, 6, 10 degrade — they say so)"
fi

# --- host metadata the publisher reads --------------------------------------
if [[ "$REPORT_MODE" -eq 1 ]]; then
  {
    echo "hostname=$MACHINE_NAME"
    echo "machine_type=$MACHINE_TYPE"
    echo "machine_fqdn=$(hostname -f 2>/dev/null || hostname 2>/dev/null || echo unknown)"
    echo "utc=$UTC_NOW"
    echo "run_id=$RUN_ID"
    echo "edge_host=$EDGE_HOST"
    echo "edge_ip=$EDGE_IP"
    echo "app_port=$APP_PORT"
    echo "internal_dns=${INTERNAL_DNS:-system-resolver}"
    echo "root=$IS_ROOT"
    echo "user=$(whoami 2>/dev/null || echo unknown)"
    echo "uid=$(id -u 2>/dev/null || echo unknown)"
    echo "kernel=$(uname -srm 2>/dev/null || echo unknown)"
  } >"$OUT/meta/host_metadata.txt" 2>/dev/null || true

  {
    echo "# tool availability — 'missing' means the hop that needs it is SKIP, not PASS"
    for t in dig host nslookup getent ip ifconfig route netstat ss lsof docker curl \
             openssl timeout gtimeout iptables ufw firewall-cmd pfctl python3 git; do
      if have "$t"; then echo "$t=present"; else echo "$t=missing"; fi
    done
    echo "# system"
    uname -a 2>&1 || true
    echo "--- disk inodes on / ---"
    df -i / 2>/dev/null | head -3 || true
  } >"$OUT/meta/tools.txt" 2>/dev/null || true

  {
    echo "--- uptime ---"; uptime 2>&1 || true
    echo "--- uname ---"; uname -a 2>&1 || true
    echo "--- whoami/id ---"; whoami 2>&1; id 2>&1 || true
  } >"$OUT/meta/run_env.txt" 2>/dev/null || true
fi

# =============================================================================
# hop 1 — public DNS
# =============================================================================
hdr "1. what DNS actually publishes"
if have dig; then
  # Every resolver call is bounded: an unreachable resolver otherwise stalls the
  # whole diagnostic for ~20s per query, which is how this script used to take a
  # minute on a host whose DNS was the very thing being investigated.
  # +short can emit an error sentence on stdout under dig; only a real address
  # counts as a nameserver, otherwise the next query would be aimed at prose.
  AUTH_NS="$(run_timeout 6 dig +short +time=3 +tries=1 ns1.ics24.ir A 2>/dev/null \
      | grep -E '^[0-9]{1,3}(\.[0-9]{1,3}){3}$' | head -1)"
  ev_note hop01_dns.txt "authoritative_ns=${AUTH_NS:-<unresolved>}"
  note "authoritative ns1.ics24.ir -> ${AUTH_NS:-<unresolved>}"
  if [[ -n "$AUTH_NS" ]]; then
    AUTH_ANSWER="$(run_timeout 6 dig +short +time=3 +tries=1 @"$AUTH_NS" "$EDGE_HOST" A 2>/dev/null | head -3 | tr '\n' ' ' | sed 's/ *$//')"
    printf '  authoritative answer  : %s\n' "${AUTH_ANSWER:-<none>}"
    _log "  authoritative answer  : ${AUTH_ANSWER:-<none>}"
    ev_note hop01_dns.txt "authoritative_answer=${AUTH_ANSWER:-<none>}"
  fi
  # One resolver transcript serves both the answer and the status line, so a
  # blocked resolver is queried once, not twice.
  PUB_RAW="$(run_timeout 6 dig +time=3 +tries=1 @1.1.1.1 "$EDGE_HOST" A 2>&1 || true)"
  if [[ "$REPORT_MODE" -eq 1 ]]; then
    {
      if [[ -n "$PUB_RAW" ]]; then printf '%s\n' "$PUB_RAW"; else printf '(no output)\n'; fi
      printf -- '--- cmd=dig @1.1.1.1 %s A\n' "$EDGE_HOST"
    } >"$OUT/meta/hop01_public_dig.txt" 2>/dev/null || true
  fi
  PUB_ANSWER="$(printf '%s\n' "$PUB_RAW" | awk '/^;; ANSWER SECTION:/{f=1;next} /^;;/{f=0} f && $4=="A"{print $5}' | head -3 | tr '\n' ' ' | sed 's/ *$//')"
  printf '  public (1.1.1.1)      : %s\n' "${PUB_ANSWER:-<none / NXDOMAIN>}"
  _log "  public (1.1.1.1)      : ${PUB_ANSWER:-<none / NXDOMAIN>}"
  PUB_STATUS="$(printf '%s\n' "$PUB_RAW" | grep -oE 'status: [A-Z]+' | head -1)"
  printf '  public status         : %s\n' "${PUB_STATUS:-unknown}"
  _log "  public status         : ${PUB_STATUS:-unknown}"
  ev_note hop01_dns.txt "public_answer=${PUB_ANSWER:-<none>}"
  ev_note hop01_dns.txt "public_status=${PUB_STATUS:-unknown}"
  case "$PUB_ANSWER" in
    *10.*|*192.168.*|*172.1[6-9].*|*172.2[0-9].*|*172.3[01].*)
      hop_result 1 "public DNS" FAIL "public DNS returns a PRIVATE address ($PUB_ANSWER)"
      note "public resolvers strip/refuse RFC1918 answers -> the name is"
      note "unresolvable from the internet even though your edge works." ;;
    "")
      hop_result 1 "public DNS" WARN "no public A record — the name only exists on internal DNS" ;;
    *)
      hop_result 1 "public DNS" PASS "public DNS resolves to $PUB_ANSWER" ;;
  esac
else
  ev_note hop01_dns.txt "tool_missing=dig"
  hop_result 1 "public DNS" SKIP "dig not installed (tool_missing=dig; apt-get install -y dnsutils)"
fi

# =============================================================================
# hop 2 — resolution from this host
# =============================================================================
hdr "2. what THIS host resolves"
if [[ -n "$INTERNAL_DNS" ]] && have dig; then
  INT_ANSWER="$(run_timeout 6 dig +short +time=3 +tries=1 @"$INTERNAL_DNS" "$EDGE_HOST" A 2>/dev/null | head -3 | tr '\n' ' ' | sed 's/ *$//')"
  INT_RAW="$(run_timeout 6 dig +time=3 +tries=1 @"$INTERNAL_DNS" "$EDGE_HOST" A 2>&1 || true)"
  if [[ "$REPORT_MODE" -eq 1 ]]; then
    {
      if [[ -n "$INT_RAW" ]]; then printf '%s\n' "$INT_RAW"; else printf '(no output)\n'; fi
      printf -- '--- cmd=dig @%s %s A\n' "$INTERNAL_DNS" "$EDGE_HOST"
    } >"$OUT/meta/hop02_internal_dig.txt" 2>/dev/null || true
  fi
  printf '  internal (%s) : %s\n' "$INTERNAL_DNS" "${INT_ANSWER:-<none>}"
  _log "  internal ($INTERNAL_DNS) : ${INT_ANSWER:-<none>}"
fi
if have getent; then
  # Bounded: the libc resolver waits ~25s for an unreachable internal resolver,
  # and an unresolved internal name is the NORMAL case on the GPU host itself.
  LOCAL_RAW="$(run_timeout 6 getent hosts "$EDGE_HOST" 2>&1 || true)"
  if [[ "$REPORT_MODE" -eq 1 ]]; then
    {
      if [[ -n "$LOCAL_RAW" ]]; then printf '%s\n' "$LOCAL_RAW"; else printf '(no output)\n'; fi
      printf -- '--- cmd=getent hosts %s\n' "$EDGE_HOST"
    } >"$OUT/meta/hop02_hosts.txt" 2>/dev/null || true
  fi
  RESOLVED="$(printf '%s\n' "$LOCAL_RAW" | head -2 | tr '\n' ' ' | sed 's/ *$//')"
  if [[ -n "$RESOLVED" ]] && printf '%s' "$RESOLVED" | grep -qE '^[0-9a-fA-F:.]+ '; then
    hop_result 2 "local DNS" PASS "$RESOLVED"
  else
    ev_note hop02_hosts.txt "result=unresolved"
    hop_result 2 "local DNS" WARN "$EDGE_HOST does not resolve here (expected on the server itself)"
  fi
elif have host; then
  RESOLVED="$(run_timeout 6 host "$EDGE_HOST" 2>&1 | head -3 | tr '\n' ' ' | sed 's/ *$//')"
  if [[ "$REPORT_MODE" -eq 1 ]]; then
    {
      if [[ -n "$RESOLVED" ]]; then printf '%s\n' "$RESOLVED"; else printf '(no output)\n'; fi
      printf -- '--- cmd=host %s\n' "$EDGE_HOST"
    } >"$OUT/meta/hop02_hosts.txt" 2>/dev/null || true
  fi
  if printf '%s' "$RESOLVED" | grep -qE 'has address|has IPv6'; then
    hop_result 2 "local DNS" PASS "$RESOLVED"
  else
    hop_result 2 "local DNS" WARN "$EDGE_HOST does not resolve here (expected on the server itself)"
  fi
else
  ev_note hop02_hosts.txt "tool_missing=getent,host"
  hop_result 2 "local DNS" SKIP "neither getent nor host available (tool_missing=getent,host)"
fi

# =============================================================================
# hop 3 — does the edge IP belong to this machine?
# =============================================================================
hdr "3. does the edge IP belong to this machine?"
printf '  local addresses:\n'
if have ip; then
  LOCAL_ADDRS="$(ip -4 -o addr show 2>/dev/null | awk '{printf "%-10s %s\n", $2, $4}')"
  capture hop03_addresses.txt ip -4 -o addr show >/dev/null 2>&1 || true
elif have ifconfig; then
  LOCAL_ADDRS="$(ifconfig 2>/dev/null | awk '/^[a-z]/{iface=$1} /inet /{printf "%-10s %s\n", iface, $2}')"
  capture hop03_addresses.txt ifconfig >/dev/null 2>&1 || true
else
  LOCAL_ADDRS=""
  ev_note hop03_addresses.txt "tool_missing=ip,ifconfig"
fi
if [[ -n "$LOCAL_ADDRS" ]]; then
  printf '%s\n' "$LOCAL_ADDRS" | sed 's/^/    /'
  _log "$LOCAL_ADDRS"
else
  note "no address tool available — cannot list local addresses"
fi
# Only the addresses themselves are evidence; matching is done on the raw list.
IP_IS_OURS=0
if printf '%s\n' "$LOCAL_ADDRS" | grep -qw -- "$EDGE_IP"; then IP_IS_OURS=1; fi
ev_note hop03_addresses.txt "edge_ip_assigned_to_this_host=$IP_IS_OURS"
if [[ -z "$LOCAL_ADDRS" ]]; then
  hop_result 3 "edge IP owner" SKIP "no ip/ifconfig — ownership not tested (tool_missing=ip,ifconfig)"
elif [[ "$IP_IS_OURS" -eq 1 ]]; then
  hop_result 3 "edge IP owner" PASS "$EDGE_IP IS assigned to this host — the edge may DNAT or connect directly"
else
  hop_result 3 "edge IP owner" FAIL "$EDGE_IP is NOT assigned to this host"
  note "either the edge NATs to us (fine, check hop 4) or DNS points"
  note "somewhere unrelated (broken record)."
fi

# =============================================================================
# hop 4 — routes
# =============================================================================
hdr "4. routes / who would carry traffic to the edge"
if have ip; then
  printf '  default route:\n'
  DEF_ROUTE="$(ip route show default 2>/dev/null)"
  [[ -n "$DEF_ROUTE" ]] && printf '%s\n' "$DEF_ROUTE" | sed 's/^/    /'
  printf '  route match for %s:\n' "$EDGE_IP"
  ROUTE_GET="$(ip route get "$EDGE_IP" 2>/dev/null)"
  capture hop04_routes.txt ip route get "$EDGE_IP" >/dev/null 2>&1 || true
  if [[ -n "$ROUTE_GET" ]]; then
    printf '%s\n' "$ROUTE_GET" | sed 's/^/    /'
    hop_result 4 "routes" PASS "$ROUTE_GET"
  else
    note "no route"
    hop_result 4 "routes" FAIL "no route to $EDGE_IP"
  fi
elif have route; then
  DEF_ROUTE="$(route -n get default 2>/dev/null | tr -s ' ' | tr '\n' ' ')"
  ROUTE_GET="$(route -n get "$EDGE_IP" 2>/dev/null | tr -s ' ' | tr '\n' ' ')"
  capture hop04_routes.txt route -n get "$EDGE_IP" >/dev/null 2>&1 || true
  if [[ -n "$ROUTE_GET" ]]; then
    hop_result 4 "routes" PASS "$(printf '%s' "$ROUTE_GET" | cut -c1-160)"
  else
    hop_result 4 "routes" FAIL "no route to $EDGE_IP"
  fi
else
  ev_note hop04_routes.txt "tool_missing=ip,route"
  hop_result 4 "routes" SKIP "no ip/route tool (tool_missing=ip,route)"
fi

# =============================================================================
# hop 5 — which address is the app listening on?
# =============================================================================
hdr "5. which address is the app ACTUALLY listening on?"
LISTEN_ADDRS=""
LISTEN_SOURCE=""
if have ss; then
  LISTEN_SOURCE="ss -tlnp"
  LISTEN_RAW="$(ss -tlnp 2>/dev/null | awk -v p=":$APP_PORT\$" '$4 ~ p {print}')"
  capture hop05_listen.txt ss -tlnp >/dev/null 2>&1 || true
  [[ "$IS_ROOT" -eq 0 ]] && note "unprivileged: 'ss -p' hides process names (run as root for the owner column)"
  LISTEN_ADDRS="$(printf '%s\n' "$LISTEN_RAW" | awk '{print $4}' | grep -- ":$APP_PORT\$")"
elif have netstat; then
  LISTEN_SOURCE="netstat"
  capture hop05_listen.txt netstat -an >/dev/null 2>&1 || true
  # Linux prints "127.0.0.1:13000"; BSD/macOS prints "127.0.0.1.13000" and puts
  # LISTEN in a separate column. Only the LAST separator is a port delimiter —
  # replacing every dot would turn 127.0.0.1 into 127:0:0:1 — so split it off
  # explicitly and rejoin with ':'.
  LISTEN_ADDRS="$(netstat -an 2>/dev/null | awk -v p="$APP_PORT" '
      {
        addr = $4
        if (addr ~ /^.*[.:][0-9]+$/) {
          i = 0
          for (j = length(addr); j > 0; j--) {
            c = substr(addr, j, 1)
            if (c == ":" || c == ".") { i = j; break }
          }
          if (i > 0 && substr(addr, i + 1) == p) {
            print substr(addr, 1, i - 1) ":" p
          }
        }
      }
    ' | sort -u)"
elif have lsof; then
  LISTEN_SOURCE="lsof"
  capture hop05_listen.txt lsof -nP -iTCP:"$APP_PORT" -sTCP:LISTEN >/dev/null 2>&1 || true
  LISTEN_ADDRS="$(lsof -nP -iTCP:"$APP_PORT" -sTCP:LISTEN 2>/dev/null \
      | awk -v p=":$APP_PORT" 'NR>1 {for(i=1;i<=NF;i++) if (index($i,p)>0) print $i}')"
else
  ev_note hop05_listen.txt "tool_missing=ss,netstat,lsof"
fi
# Normalise "*:13000" to 0.0.0.0:13000 so the all-interfaces check works either way.
LISTEN_ADDRS="$(printf '%s\n' "$LISTEN_ADDRS" | sed 's/^\*:/0.0.0.0:/' | sort -u | sed '/^$/d')"
ev_note hop05_listen.txt "listen_source=${LISTEN_SOURCE:-none}"
ev_note hop05_listen.txt "listen_addresses=${LISTEN_ADDRS:-<none>}"

if [[ -z "$LISTEN_SOURCE" ]]; then
  hop_result 5 "host bind" SKIP "no ss/netstat/lsof — bind not tested (tool_missing=ss,netstat,lsof)"
elif [[ -z "$LISTEN_ADDRS" ]]; then
  hop_result 5 "host bind" FAIL "nothing listening on :$APP_PORT on the host"
else
  printf '%s\n' "$LISTEN_ADDRS" | sed 's/^/    /'
  _log "$LISTEN_ADDRS"
  if printf '%s\n' "$LISTEN_ADDRS" | grep -qE "0\.0\.0\.0:$APP_PORT|\[::\]:$APP_PORT"; then
    hop_result 5 "host bind" PASS "listening on ALL interfaces (:$APP_PORT) — any edge IP can reach it"
  elif printf '%s\n' "$LISTEN_ADDRS" | grep -qE "127\.0\.0\.1:$APP_PORT"; then
    hop_result 5 "host bind" FAIL "listening on LOOPBACK ONLY (127.0.0.1:$APP_PORT)"
    note "the edge must be on this same host and proxy to loopback;"
    note "a remote edge CANNOT reach a loopback-only bind."
  else
    hop_result 5 "host bind" WARN "listening on a specific address only: $(printf '%s' "$LISTEN_ADDRS" | tr '\n' ' ')"
    note "the edge must target one of those addresses, not $EDGE_IP"
  fi
fi

# =============================================================================
# hop 6 — how Docker published the webui port
# =============================================================================
hdr "6. how Docker published the webui port"
BOUND_IPS=""
DOCKER_USABLE=0
if have docker; then
  if docker info >/dev/null 2>&1; then
    DOCKER_USABLE=1
  else
    capture hop06_docker_info.txt docker info >/dev/null 2>&1 || true
    note "docker CLI present but the daemon is not reachable as $(whoami 2>/dev/null || echo this user)"
  fi
else
  ev_note hop06_docker.txt "tool_missing=docker"
fi

if [[ "$DOCKER_USABLE" -eq 1 ]]; then
  WEBUI_CONTAINERS="$(docker ps --format '{{.Names}}' 2>/dev/null | grep -iE 'webui' || true)"
  capture hop06_docker_ps.txt docker ps --format '{{.Names}}\t{{.Ports}}' >/dev/null 2>&1 || true
  for c in $WEBUI_CONTAINERS; do
    printf '  container: %s\n' "$c"
    _log "  container: $c"
    PORTS="$(docker inspect "$c" --format \
      '{{range $p, $b := .NetworkSettings.Ports}}{{$p}} -> {{range $b}}{{.HostIp}}:{{.HostPort}} {{end}}{{"\n"}}{{end}}' \
      2>/dev/null || true)"
    if [[ -n "$PORTS" ]]; then
      printf '%s\n' "$PORTS" | sed 's/^/    /'
      _log "$PORTS"
    fi
    ev_note hop06_docker.txt "container=$c"
    [[ -n "$PORTS" ]] && ev_note hop06_docker.txt "$PORTS"
  done
  BOUND_IPS="$(docker inspect $(docker ps -q --filter 'name=webui') --format \
      '{{range $p, $b := .NetworkSettings.Ports}}{{range $b}}{{.HostIp}} {{end}}{{end}}' 2>/dev/null || true)"
  ev_note hop06_docker.txt "published_host_ips=$(printf '%s' "$BOUND_IPS" | xargs 2>/dev/null || true)"
  if printf '%s' "$BOUND_IPS" | grep -qw -- "$EDGE_IP"; then
    hop_result 6 "container bind" PASS "a webui binding includes $EDGE_IP"
  elif [[ -n "${BOUND_IPS// /}" ]]; then
    hop_result 6 "container bind" FAIL "no webui binding on $EDGE_IP (bound: $(printf '%s' "$BOUND_IPS" | xargs))"
    note "compose.gpu.yml pins 127.0.0.1:${APP_PORT} plus any host IPs;"
    note "add the edge IP or use 0.0.0.0 if the edge connects directly."
  elif [[ -z "$WEBUI_CONTAINERS" ]]; then
    hop_result 6 "container bind" WARN "no running container matching 'webui' — nothing published"
  else
    hop_result 6 "container bind" WARN "webui runs but publishes no ports at all (see meta/hop06_docker.txt)"
  fi
elif have docker; then
  hop_result 6 "container bind" SKIP "docker daemon unreachable — publish mapping not tested (see meta/hop06_docker_info.txt)"
else
  hop_result 6 "container bind" SKIP "docker not available (tool_missing=docker)"
fi

# =============================================================================
# hop 7 — does the app answer locally?
# =============================================================================
hdr "7. does the app answer locally?"
if have curl; then
  code="$(curl -s -m 8 -o /dev/null -w '%{http_code}' "http://127.0.0.1:${APP_PORT}/health" 2>/dev/null)"
  ev_note hop07_loopback.txt "url=http://127.0.0.1:${APP_PORT}/health"
  ev_note hop07_loopback.txt "http_code=${code:-000}"
  capture hop07_loopback_body.txt curl -s -m 8 "http://127.0.0.1:${APP_PORT}/health" >/dev/null 2>&1 || true
  if [[ "$code" == "200" ]]; then
    hop_result 7 "app (loopback)" PASS "app healthy on 127.0.0.1:${APP_PORT} (-> 200)"
  else
    hop_result 7 "app (loopback)" FAIL "app on 127.0.0.1:${APP_PORT}/health -> ${code:-no-response}"
  fi
else
  ev_note hop07_loopback.txt "tool_missing=curl"
  hop_result 7 "app (loopback)" SKIP "curl not available (tool_missing=curl)"
fi

# =============================================================================
# hop 8 — can this host reach the edge IP itself?
# =============================================================================
hdr "8. can this host reach the edge IP itself?"
if have curl; then
  code="$(curl -s -m 8 -o /dev/null -w '%{http_code}' "http://${EDGE_IP}:${APP_PORT}/health" 2>/dev/null)"
  ev_note hop08_edge_reach.txt "url=http://${EDGE_IP}:${APP_PORT}/health"
  ev_note hop08_edge_reach.txt "http_code=${code:-000}"
  capture hop08_edge_reach_body.txt curl -s -m 8 "http://${EDGE_IP}:${APP_PORT}/health" >/dev/null 2>&1 || true
  if [[ "$code" == "200" ]]; then
    hop_result 8 "edge reach" PASS "http://${EDGE_IP}:${APP_PORT}/health -> 200"
  elif [[ "$code" == "000" ]]; then
    hop_result 8 "edge reach" FAIL "http://${EDGE_IP}:${APP_PORT} -> no response"
    note "if hop 3 showed the IP is not ours, this is the edge's job;"
    note "if it IS ours, nothing is bound there (see hop 5/6)."
  else
    hop_result 8 "edge reach" WARN "http://${EDGE_IP}:${APP_PORT}/health -> $code"
  fi
else
  ev_note hop08_edge_reach.txt "tool_missing=curl"
  hop_result 8 "edge reach" SKIP "curl not available (tool_missing=curl)"
fi

# =============================================================================
# hop 9 — TLS/SNI as the edge presents it
# =============================================================================
hdr "9. TLS/SNI as the edge presents it"
if ! have openssl; then
  ev_note hop09_tls.txt "tool_missing=openssl"
  hop_result 9 "TLS/SNI" SKIP "openssl not available (tool_missing=openssl)"
else
  RAW_TLS="$(run_timeout 8 openssl s_client -connect "${EDGE_IP}:443" \
      -servername "$EDGE_HOST" </dev/null 2>&1 || true)"
  {
    printf '%s\n' "$RAW_TLS"
    printf -- '--- exit=recorded cmd=openssl s_client -connect %s:443 -servername %s\n' "$EDGE_IP" "$EDGE_HOST"
  } >"$OUT/meta/hop09_tls.txt" 2>/dev/null || true
  CERT="$(printf '%s\n' "$RAW_TLS" | openssl x509 -noout -subject -issuer -dates 2>/dev/null || true)"
  if [[ -n "$CERT" ]]; then
    printf '%s\n' "$CERT" | sed 's/^/    /'
    _log "$CERT"
    SUBJ="$(printf '%s\n' "$CERT" | tr '\n' ' ')"
    hop_result 9 "TLS/SNI" PASS "$SUBJ"
  else
    hop_result 9 "TLS/SNI" WARN "no TLS handshake on ${EDGE_IP}:443 (edge may serve plain HTTP on another port)"
  fi
fi

# =============================================================================
# hop 10 — host firewall
# =============================================================================
hdr "10. edge-side firewall view (host firewall only)"
FW_FOUND=0
if have ufw; then
  FW_FOUND=1
  capture hop10_firewall.txt ufw status >/dev/null 2>&1 || true
  ufw status 2>/dev/null | head -8 | sed 's/^/    /' || note "ufw present but not readable (needs root)"
elif have firewall-cmd; then
  FW_FOUND=1
  capture hop10_firewall.txt firewall-cmd --list-all >/dev/null 2>&1 || true
  firewall-cmd --list-all 2>/dev/null | head -10 | sed 's/^/    /' || note "firewalld present but not readable (needs root)"
fi
if have iptables; then
  FW_FOUND=1
  printf '  iptables INPUT policy:\n'
  IPT="$(iptables -S INPUT 2>/dev/null | head -8 || true)"
  capture hop10_iptables.txt iptables -S INPUT >/dev/null 2>&1 || true
  if [[ -n "$IPT" ]]; then
    printf '%s\n' "$IPT" | sed 's/^/    /'
  else
    note "iptables not readable without root"
    ev_note hop10_iptables.txt "readable=no (root required)"
  fi
fi
if have pfctl; then
  FW_FOUND=1
  capture hop10_pf.txt pfctl -s rules >/dev/null 2>&1 || true
  note "macOS pf: rule list captured in meta/hop10_pf.txt (needs root)"
fi
if [[ "$FW_FOUND" -eq 0 ]]; then
  ev_note hop10_firewall.txt "tool_missing=ufw,firewall-cmd,iptables,pfctl"
  hop_result 10 "host firewall" SKIP "no ufw/firewalld/iptables/pfctl on this host — filtering is upstream"
else
  hop_result 10 "host firewall" PASS "host firewall state captured (see meta/hop10_*.txt; unreadable rules need root)"
fi

# =============================================================================
# verdict
# =============================================================================
N_FAIL=0; N_WARN=0; N_PASS=0; N_SKIP=0
i=0
while [[ $i -lt ${#HOP_NUM[@]} ]]; do
  case "${HOP_RESULT[$i]}" in
    FAIL) N_FAIL=$((N_FAIL + 1)) ;;
    WARN) N_WARN=$((N_WARN + 1)) ;;
    PASS) N_PASS=$((N_PASS + 1)) ;;
    *)    N_SKIP=$((N_SKIP + 1)) ;;
  esac
  i=$((i + 1))
done

if [[ "$N_FAIL" -gt 0 ]]; then OVERALL="FAIL"
elif [[ "$N_WARN" -gt 0 ]]; then OVERALL="WARN"
else OVERALL="PASS"; fi

FIRST_FAIL=""
i=0
while [[ $i -lt ${#HOP_NUM[@]} ]]; do
  if [[ -z "$FIRST_FAIL" && "${HOP_RESULT[$i]}" == "FAIL" ]]; then
    FIRST_FAIL="${HOP_NUM[$i]} (${HOP_NAME[$i]})"
  fi
  i=$((i + 1))
done

# Publisher status vocabulary: the dashboard colours runs by these three words.
case "$OVERALL" in
  PASS) RUN_STATUS="HEALTHY" ;;
  WARN) RUN_STATUS="DEGRADED" ;;
  *)    RUN_STATUS="DOWN" ;;
esac

hdr "VERDICT"
if [[ "$OVERALL" == "FAIL" ]]; then
  printf '  %s%s%s  — first broken hop: %s\n' "$C_BAD" "$OVERALL" "$C_OFF" "$FIRST_FAIL"
  _log "  $OVERALL — first broken hop: $FIRST_FAIL"
else
  printf '  %s%s%s  — %s pass, %s warn, %s skip\n' \
    "$C_OK" "$OVERALL" "$C_OFF" "$N_PASS" "$N_WARN" "$N_SKIP"
  _log "  $OVERALL — $N_PASS pass, $N_WARN warn, $N_SKIP skip"
fi

cat <<'GUIDE'

  1 or 2 FAIL  -> DNS. The record points at an address the internet cannot route.
  3 FAIL       -> the edge IP is not ours and not reachable: record is wrong,
                  or the edge is down.
  5 loopback   -> the app is only on 127.0.0.1. A remote edge cannot reach it;
                  bind 0.0.0.0 or the interface the edge dials.
  6 FAIL       -> Docker is not publishing on the IP the edge targets. Fix the
                  compose port mapping (this is the 2026-11-12 outage class).
  7 FAIL       -> the app itself is down; nothing upstream matters yet.
  8 FAIL + 5/6 -> edge-to-host hop is broken (firewall rule, wrong VLAN).
  8 OK + 1 FAIL-> ONLY DNS is broken; the service chain is healthy.
  SKIP         -> that hop was not tested (missing tool or privilege); it is
                  never counted as a pass.
GUIDE
_log "verdict guide printed"

# =============================================================================
# report artifacts
# =============================================================================
if [[ "$REPORT_MODE" -eq 1 ]]; then
  # Per-hop rows for the dashboard heatmap. The codes are chosen for what
  # publish_report.classify_http() makes of them, so the colours match the
  # verdict: 200 -> up (green), 000 -> down (red), 408 -> degraded (amber),
  # SKIP -> no-data (grey). Using 500 for a FAIL would render amber, because
  # classify_http() treats 4xx/5xx as "degraded".
  {
    printf 'port\tservice\thttp_code\tbody_preview\n'
    i=0
    while [[ $i -lt ${#HOP_NUM[@]} ]]; do
      case "${HOP_RESULT[$i]}" in
        PASS) hcode=200 ;;
        FAIL) hcode=000 ;;
        WARN) hcode=408 ;;
        *)    hcode=SKIP ;;
      esac
      preview="$(printf '%s' "${HOP_DETAIL[$i]}" | tr '\t\n' '  ' | sed 's/^ *//' | cut -c1-180)"
      # The publisher reads this as (port, service, http_code, preview) and uses
      # the middle column as the dashboard's service label. Its name must be a
      # plain slug (the real service names are: kb, guardrails, webui, …).
      # BSD sed has no \+ / \{n\} in BRE, so the collapse is spelled out and the
      # character class repeats instead of using a quantifier.
      hop_slug="$(printf 'hop%02d-%s' "${HOP_NUM[$i]}" "${HOP_NAME[$i]}" \
                    | tr 'A-Z' 'a-z' \
                    | sed -e 's/[^a-z0-9][^a-z0-9]*/-/g' -e 's/--*/-/g' -e 's/-*$//')"
      printf '%s\t%s\t%s\t%s\n' "${HOP_NUM[$i]}" "$hop_slug" "$hcode" "$preview"
      i=$((i + 1))
    done
  } >"$OUT/curl/matrix.tsv" 2>/dev/null || true

  md_cell() { printf '%s' "$1" | tr '\n' ' ' | sed 's/|/\\|/g'; }

  {
    printf '# Edge path diagnosis — %s -> :%s\n\n' "$EDGE_HOST" "$APP_PORT"
    printf '| Field | Value |\n|---|---|\n'
    printf '| Run ID | `%s` |\n' "$RUN_ID"
    printf '| Machine | `%s` |\n' "$MACHINE_NAME"
    printf '| Machine type | `%s` |\n' "$MACHINE_TYPE"
    printf '| UTC timestamp | `%s` |\n' "$UTC_NOW"
    printf '| Edge host | `%s` |\n' "$EDGE_HOST"
    printf '| Edge IP (assumed) | `%s` |\n' "$EDGE_IP"
    printf '| App port | `%s` |\n' "$APP_PORT"
    printf '| Internal resolver | `%s` |\n' "${INTERNAL_DNS:-system}"
    printf '| Privilege | %s |\n' "$([[ "$IS_ROOT" -eq 1 ]] && echo root || echo unprivileged)"
    printf '| Hops | %s pass · %s warn · %s fail · %s skip |\n' "$N_PASS" "$N_WARN" "$N_FAIL" "$N_SKIP"
    if [[ "$OVERALL" == "FAIL" ]]; then
      printf '| Verdict | **FAIL** — first broken hop: %s |\n\n' "$FIRST_FAIL"
    else
      printf '| Verdict | **%s** |\n\n' "$OVERALL"
    fi

    printf '## Results per hop\n\n'
    printf '| # | Hop | Result | Detail |\n|---|---|---|---|\n'
    i=0
    while [[ $i -lt ${#HOP_NUM[@]} ]]; do
      printf '| %s | %s | **%s** | %s |\n' \
        "${HOP_NUM[$i]}" "${HOP_NAME[$i]}" "${HOP_RESULT[$i]}" "$(md_cell "${HOP_DETAIL[$i]}")"
      i=$((i + 1))
    done
    printf '\nPASS = tested and healthy · FAIL = tested and broken · WARN = tested, '
    printf 'inconclusive or degraded · SKIP = **not tested** (missing tool or privilege).\n'
    printf 'A SKIP is never evidence that a hop works.\n\n'

    printf '## How to read this\n\n'
    printf -- '- `FAIL` on hop 1 or 2 means DNS: the published record points somewhere'
    printf ' the internet cannot route.\n'
    printf -- '- `FAIL` on hop 5 with `127.0.0.1:PORT` means the app is loopback-only;'
    printf ' a remote edge cannot reach it.\n'
    printf -- '- `FAIL` on hop 6 is the 2026-11-12 outage class: Docker recreated the'
    printf ' container with no published port.\n'
    printf -- '- `FAIL` on hop 7 means the application itself is down, so nothing'
    printf ' upstream matters yet.\n'
    printf -- '- hop 8 OK + hop 1 FAIL means ONLY DNS is broken and the service chain'
    printf ' is healthy.\n\n'

    printf '## Raw evidence\n\n'
    printf '| File | Captured |\n|---|---|\n'
    for f in "$OUT"/meta/*; do
      [[ -f "$f" ]] || continue
      printf '| `meta/%s` | %s bytes |\n' "$(basename "$f")" "$(wc -c <"$f" 2>/dev/null | tr -d ' ')"
    done
    for f in "$OUT"/curl/*; do
      [[ -f "$f" ]] || continue
      printf '| `curl/%s` | %s bytes |\n' "$(basename "$f")" "$(wc -c <"$f" 2>/dev/null | tr -d ' ')"
    done
    printf '\n`run.log` holds the full terminal transcript for this run.\n\n'

    printf '## Environment\n\n'
    printf '```\n'
    sed -n '1,40p' "$OUT/meta/host_metadata.txt" 2>/dev/null || true
    printf '```\n\n'
    printf 'Generated by `scripts/diagnose_edge_path.sh` (read-only probes; nothing on '
    printf 'the host was modified). Secrets are redacted before publication.\n'
  } >"$OUT/REPORT.md" 2>/dev/null || true

  say ""
  say "  report written: $OUT/REPORT.md"
fi

# =============================================================================
# publish
# =============================================================================
PUSH_STATUS="SKIPPED"
if [[ "$REPORT_MODE" -eq 1 && "$PUSH_MODE" -eq 1 ]]; then
  hdr "PUBLISH to the health-check repo"
  PUBLISHER="$SCRIPT_DIR/monitor/publish_report.py"
  # Evidence of the target is collected before the publisher runs, because the
  # publisher copies meta/ into the pushed tree before it talks to git.
  {
    echo "target_verdict=$TARGET_VERDICT"
    echo "branch=$HEALTH_BRANCH"
    echo "repo_dir=$HEALTH_REPO_DIR"
    echo "run_status=$RUN_STATUS"
    echo "run_overall=$OVERALL"
  } >"$OUT/meta/publish_target.txt" 2>/dev/null || true

  if ! have python3; then
    bad "python3 not available — cannot publish (run dir kept at $OUT)"
    PUSH_STATUS="FAILED"
  elif [[ ! -f "$PUBLISHER" ]]; then
    bad "publisher not found at $PUBLISHER (run dir kept at $OUT)"
    PUSH_STATUS="FAILED"
  else
    say "  target  : $(norm_repo_slug "$HEALTH_REMOTE") ($HEALTH_BRANCH)"
    say "  run id  : $RUN_ID"
    say "  status  : $RUN_STATUS (from verdict $OVERALL)"
    # Sanitize before anything leaves the host. Publication copies files, so the
    # redaction has to happen here, not after the push.
    redact_tree "$OUT" "$OUT/meta/redaction.txt" | tee -a "$RUN_LOG"
    PUSH_LOG_TMP="$(mktemp 2>/dev/null || echo "/tmp/edge-diag-push.$$")"
    if python3 "$PUBLISHER" \
        --run-dir "$OUT" \
        --run-id "$RUN_ID" \
        --machine-name "$MACHINE_NAME" \
        --machine-type "$MACHINE_TYPE" \
        --mode "edge-diag" \
        --status "$RUN_STATUS" \
        --origin manual \
        --repo "$HEALTH_REPO_DIR" \
        --remote "$HEALTH_REMOTE" \
        --branch "$HEALTH_BRANCH" \
        --keep-logs "${GPU_HEALTH_KEEP_LOGS:-30}" 2>&1 | tee "$PUSH_LOG_TMP"; then
      PUSH_STATUS="PASSED"
    else
      PUSH_STATUS="FAILED"
    fi
    # The publisher writes the tree before it pushes, so this log is evidence
    # only — but it can contain a credential-bearing URL from a git error, so it
    # is redacted before it is kept.
    cp "$PUSH_LOG_TMP" "$OUT/meta/git-push.log" 2>/dev/null || true
    redact_file "$OUT/meta/git-push.log" 2>/dev/null || true
    rm -f "$PUSH_LOG_TMP" 2>/dev/null || true

    if [[ "$PUSH_STATUS" == "PASSED" ]]; then
      ok "published $RUN_ID to $(norm_repo_slug "$HEALTH_REMOTE")#$HEALTH_BRANCH"
      say "  dashboard : https://alinikkhah2001.github.io/Work_RAG_HealthCheck/"
      say "  run record: runs/$RUN_ID.json"
      say "  this run  : logs/$RUN_ID/REPORT.md"
      say "  newest    : latest/REPORT.md"
    else
      bad "publish FAILED — the run directory is still on disk at $OUT"
      note "see $OUT/meta/git-push.log (redacted)"
    fi
  fi
elif [[ "$REPORT_MODE" -eq 1 ]]; then
  note "publishing disabled — re-run with --push to send this run to GitHub"
fi

if [[ "$REPORT_MODE" -eq 1 ]]; then
  { echo "PUSH_STATUS=$PUSH_STATUS"; echo "OVERALL=$OVERALL"; } >"$OUT/meta/push_status" 2>/dev/null || true
  # Re-redact: the report and push_status were written after the publish-time pass.
  if [[ "$PUSH_MODE" -eq 0 ]]; then
    redact_tree "$OUT" "$OUT/meta/redaction.txt" >/dev/null 2>&1 || true
  fi
fi

# =============================================================================
# exit
# =============================================================================
if [[ "$N_FAIL" -gt 0 ]]; then exit 1; fi
exit 0
