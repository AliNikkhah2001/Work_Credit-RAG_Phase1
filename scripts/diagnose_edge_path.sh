#!/usr/bin/env bash
# =============================================================================
# scripts/diagnose_edge_path.sh — locate the broken hop for chat.ics24.ir
#
# Run ON THE GPU SERVER as root. Read-only: it changes nothing.
#
#   sudo bash scripts/diagnose_edge_path.sh
#   sudo bash scripts/diagnose_edge_path.sh --edge-ip 10.10.34.36 --port 13000
#
# THE CHAIN we are testing (each hop is a separate, independent failure mode):
#
#   [1] public DNS      chat.ics24.ir -> ???          (what internet resolvers say)
#   [2] internal DNS    chat.ics24.ir -> ???          (what the internal resolver says)
#   [3] firewall/NAT    does anything answer on that IP:port?
#   [4] edge -> host    does the edge IP reach THIS host?
#   [5] host bind       is the host listening on the IP the edge targets?
#   [6] container bind  is the webui container publishing that port?
#   [7] app             does the app answer on loopback?
#   [8] TLS/SNI         does the edge terminate TLS for this hostname?
#
# The report verdict tells you WHICH hop to fix. Hop 5 is the common one:
# Docker publishes 192.168.x and 127.0.0.1, while DNS points at 10.10.34.36,
# so nothing listens on the address the edge actually dials.
# =============================================================================
set -uo pipefail

EDGE_IP="${EDGE_IP:-10.10.34.36}"
EDGE_HOST="${EDGE_HOST:-chat.ics24.ir}"
APP_PORT="${APP_PORT:-13000}"
INTERNAL_DNS="${INTERNAL_DNS:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --edge-ip)   EDGE_IP="$2"; shift 2 ;;
    --edge-host) EDGE_HOST="$2"; shift 2 ;;
    --port)      APP_PORT="$2"; shift 2 ;;
    --dns)       INTERNAL_DNS="$2"; shift 2 ;;
    -h|--help)   sed -n '2,26p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

C_OK=$'\033[32m'; C_BAD=$'\033[31m'; C_WARN=$'\033[33m'; C_DIM=$'\033[2m'
C_BOLD=$'\033[1m'; C_OFF=$'\033[0m'

hdr() { printf '\n%s=== %s ===%s\n' "$C_BOLD" "$1" "$C_OFF"; }
ok()  { printf '  %sOK%s    %s\n' "$C_OK" "$C_OFF" "$*"; }
bad() { printf '  %sFAIL%s  %s\n' "$C_BAD" "$C_OFF" "$*"; }
wrn() { printf '  %sWARN%s  %s\n' "$C_WARN" "$C_OFF" "$*"; }
note(){ printf '        %s%s%s\n' "$C_DIM" "$*" "$C_OFF"; }

printf '%s=== edge path diagnosis: %s -> :%s ===%s\n' \
  "$C_BOLD" "$EDGE_HOST" "$APP_PORT" "$C_OFF"
printf '  assumed edge IP : %s   (override with --edge-ip)\n' "$EDGE_IP"
printf '  app port        : %s\n' "$APP_PORT"

# ---------------------------------------------------------------------------
hdr "1. what DNS actually publishes"
if command -v dig >/dev/null 2>&1; then
  AUTH_NS="$(dig +short ns1.ics24.ir A 2>/dev/null | head -1)"
  note "authoritative ns1.ics24.ir -> ${AUTH_NS:-<unresolved>}"
  if [[ -n "$AUTH_NS" ]]; then
    AUTH_ANSWER="$(dig +short @"$AUTH_NS" "$EDGE_HOST" A 2>/dev/null | head -3 | tr '\n' ' ')"
    printf '  authoritative answer  : %s\n' "${AUTH_ANSWER:-<none>}"
  fi
  PUB_ANSWER="$(dig +short @1.1.1.1 "$EDGE_HOST" A 2>/dev/null | head -3 | tr '\n' ' ')"
  printf '  public (1.1.1.1)      : %s\n' "${PUB_ANSWER:-<none / NXDOMAIN>}"
  PUB_STATUS="$(dig +noall +comments @1.1.1.1 "$EDGE_HOST" A 2>/dev/null | grep -oE 'status: [A-Z]+' | head -1)"
  printf '  public status         : %s\n' "${PUB_STATUS:-unknown}"
  case "$PUB_ANSWER" in
    *10.*|*192.168.*|*172.1[6-9].*|*172.2[0-9].*|*172.3[01].*)
      bad "public DNS returns a PRIVATE address ($PUB_ANSWER)"
      note "public resolvers strip/refuse RFC1918 answers -> the name is"
      note "unresolvable from the internet even though your edge works." ;;
    "")
      wrn "no public A record — the name only exists on internal DNS" ;;
    *)
      ok "public DNS resolves to $PUB_ANSWER" ;;
  esac
else
  wrn "dig not installed (apt-get install -y dnsutils)"
fi

# ---------------------------------------------------------------------------
hdr "2. what THIS host resolves"
if getent hosts "$EDGE_HOST" >/dev/null 2>&1; then
  ok "$(getent hosts "$EDGE_HOST" | head -2 | tr '\n' ' ')"
else
  wrn "$EDGE_HOST does not resolve here (expected on the server itself)"
fi

# ---------------------------------------------------------------------------
hdr "3. does the edge IP belong to this machine?"
printf '  local addresses:\n'
if command -v ip >/dev/null 2>&1; then
  ip -4 -o addr show 2>/dev/null | awk '{printf "    %-10s %s\n", $2, $4}'
else
  ifconfig 2>/dev/null | grep 'inet ' | awk '{printf "    %s\n", $2}'
fi
if command -v ip >/dev/null 2>&1 && ip -4 -o addr show 2>/dev/null | grep -qw "$EDGE_IP"; then
  ok "$EDGE_IP IS assigned to this host — the edge may DNAT or connect directly"
else
  bad "$EDGE_IP is NOT assigned to this host"
  note "either the edge NATs to us (fine, check hop 4) or DNS points"
  note "somewhere unrelated (broken record)."
fi

# ---------------------------------------------------------------------------
hdr "4. routes / who would carry traffic to the edge"
if command -v ip >/dev/null 2>&1; then
  printf '  default route:\n'
  ip route show default 2>/dev/null | sed 's/^/    /'
  printf '  route match for %s:\n' "$EDGE_IP"
  ip route get "$EDGE_IP" 2>/dev/null | sed 's/^/    /' || note "no route"
fi

# ---------------------------------------------------------------------------
hdr "5. which address is the app ACTUALLY listening on?"
if command -v ss >/dev/null 2>&1; then
  LISTEN="$(ss -tlnp 2>/dev/null | awk -v p=":$APP_PORT" '$4 ~ p {print}')"
  if [[ -n "$LISTEN" ]]; then
    printf '%s\n' "$LISTEN" | sed 's/^/    /'
    if printf '%s' "$LISTEN" | grep -qE "0\.0\.0\.0:$APP_PORT|\[::\]:$APP_PORT|\*:$APP_PORT"; then
      ok "listening on ALL interfaces (:${APP_PORT}) — any edge IP can reach it"
    elif printf '%s' "$LISTEN" | grep -qE "127\.0\.0\.1:$APP_PORT"; then
      bad "listening on LOOPBACK ONLY (127.0.0.1:${APP_PORT})"
      note "the edge must be on this same host and proxy to loopback;"
      note "a remote edge CANNOT reach a loopback-only bind."
    else
      wrn "listening on a specific address only:"
      note "the edge must target one of those addresses, not $EDGE_IP"
    fi
  else
    bad "nothing listening on :$APP_PORT on the host"
  fi
else
  wrn "ss not available (netstat -tlnp)"
fi

# ---------------------------------------------------------------------------
hdr "6. how Docker published the webui port"
if command -v docker >/dev/null 2>&1; then
  for c in $(docker ps --format '{{.Names}}' 2>/dev/null | grep -iE 'webui' ); do
    printf '  container: %s\n' "$c"
    docker inspect "$c" --format \
      '{{range $p, $b := .NetworkSettings.Ports}}{{$p}} -> {{range $b}}{{.HostIp}}:{{.HostPort}} {{end}}{{"\n"}}{{end}}' \
      2>/dev/null | sed 's/^/    /'
  done
  BOUND_IPS="$(docker inspect $(docker ps -q --filter 'name=webui') --format \
      '{{range $p, $b := .NetworkSettings.Ports}}{{range $b}}{{.HostIp}} {{end}}{{end}}' 2>/dev/null || true)"
  if printf '%s' "$BOUND_IPS" | grep -qw "$EDGE_IP"; then
    ok "a webui binding includes $EDGE_IP"
  elif [[ -n "${BOUND_IPS// /}" ]]; then
    bad "no webui binding on $EDGE_IP (bound: $(printf '%s' "$BOUND_IPS" | xargs))"
    note "compose.gpu.yml pins 127.0.0.1:${APP_PORT} plus any host IPs;"
    note "add the edge IP or use 0.0.0.0 if the edge connects directly."
  fi
else
  wrn "docker not available"
fi

# ---------------------------------------------------------------------------
hdr "7. does the app answer locally?"
code="$(curl -s -m 8 -o /dev/null -w '%{http_code}' "http://127.0.0.1:${APP_PORT}/health" 2>/dev/null)"
if [[ "$code" == "200" ]]; then
  ok "app healthy on 127.0.0.1:${APP_PORT} (-> 200)"
else
  bad "app on 127.0.0.1:${APP_PORT}/health -> ${code:-no-response}"
fi

# ---------------------------------------------------------------------------
hdr "8. can this host reach the edge IP itself?"
code="$(curl -s -m 8 -o /dev/null -w '%{http_code}' "http://${EDGE_IP}:${APP_PORT}/health" 2>/dev/null)"
if [[ "$code" == "200" ]]; then
  ok "http://${EDGE_IP}:${APP_PORT}/health -> 200"
elif [[ "$code" == "000" ]]; then
  bad "http://${EDGE_IP}:${APP_PORT} -> no response"
  note "if hop 3 showed the IP is not ours, this is the edge's job;"
  note "if it IS ours, nothing is bound there (see hop 5/6)."
else
  wrn "http://${EDGE_IP}:${APP_PORT}/health -> $code"
fi

# ---------------------------------------------------------------------------
hdr "9. TLS/SNI as the edge presents it"
if command -v openssl >/dev/null 2>&1; then
  CERT="$(echo | timeout 8 openssl s_client -connect "${EDGE_IP}:443" \
      -servername "$EDGE_HOST" 2>/dev/null | openssl x509 -noout -subject -issuer -dates 2>/dev/null)"
  if [[ -n "$CERT" ]]; then
    printf '%s\n' "$CERT" | sed 's/^/    /'
  else
    wrn "no TLS handshake on ${EDGE_IP}:443 (edge may serve plain HTTP on another port)"
  fi
fi

# ---------------------------------------------------------------------------
hdr "10. edge-side firewall view (host firewall only)"
if command -v ufw >/dev/null 2>&1; then ufw status 2>/dev/null | head -8 | sed 's/^/    /'
elif command -v firewall-cmd >/dev/null 2>&1; then firewall-cmd --list-all 2>/dev/null | head -10 | sed 's/^/    /'
else note "no ufw/firewalld on this host — filtering is upstream"; fi
printf '  iptables INPUT policy:\n'
iptables -S INPUT 2>/dev/null | head -8 | sed 's/^/    /' || note "iptables not readable"

# ---------------------------------------------------------------------------
hdr "VERDICT GUIDE"
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
GUIDE
