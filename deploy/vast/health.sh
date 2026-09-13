#!/bin/bash
# health.sh — check all RAG endpoints + pg chunk count. Exit non-zero on any failure.
set -u
FAIL=0
check() { # $1=name $2=url $3=expect(optional grep)
  out="$(curl -s --max-time 8 "$2" 2>/dev/null)"
  if [ -z "$out" ]; then echo "FAIL $1 ($2): no response"; FAIL=1; return; fi
  if [ -n "${3:-}" ] && ! printf "%s" "$out" | grep -qi "$3"; then
    echo "FAIL $1: missing '$3' in: $(printf "%s" "$out" | head -c 200)"; FAIL=1; return
  fi
  echo "OK   $1: $(printf "%s" "$out" | head -c 120)"
}
check "gemma:18000"      http://127.0.0.1:18000/health
check "gemma-models"     http://127.0.0.1:18000/v1/models gemma
check "kb:8000"          http://127.0.0.1:8000/health ok
check "guardrails:8200"  http://127.0.0.1:8200/health ok
check "orch:8100"        http://127.0.0.1:8100/health ok
check "orch-ready"       http://127.0.0.1:8100/ready
check "guard-ready"      http://127.0.0.1:8200/ready
check "collector:3000"   http://127.0.0.1:3000/api/public/health
# optional panels (warn only)
curl -s --max-time 10 http://127.0.0.1:2024/ok >/dev/null 2>&1 \
  && echo "OK   studio:2024" || echo "WARN studio:2024 not running (optional)"
curl -s --max-time 10 http://127.0.0.1:3001/api/public/health >/dev/null 2>&1 \
  && echo "OK   langfuse:3001" || echo "WARN langfuse:3001 not running (optional)"
# pg chunk count
if PGPASSWORD=postgres psql -h 127.0.0.1 -U postgres -d kb_manager -tAc "SELECT count(*) FROM chunks;" 2>/dev/null | grep -qE "^[1-9]"; then
  echo "OK   pg chunks: $(PGPASSWORD=postgres psql -h 127.0.0.1 -U postgres -d kb_manager -tAc "SELECT count(*) FROM chunks;")"
else
  echo "FAIL pg kb_manager.chunks empty/unreachable"; FAIL=1
fi
[ "$FAIL" -eq 0 ] && echo "ALL HEALTHY" || echo "UNHEALTHY"
exit "$FAIL"
