#!/usr/bin/env bash
# Apply Iranian / regional package mirrors for CI builds (pip, uv, npm).
# Intended as fallback when pypi.org / registry.npmjs.org stall via Squid.
#
# Usage (Jenkins Build stage):
#   source scripts/ci_apply_iran_mirrors.sh
#
# Defaults ON for GPU/prod. Set CI_USE_IRAN_MIRRORS=0 to skip.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIRROR_ENV="${CI_IRAN_MIRROR_ENV:-$ROOT/deploy/mirrors/iran.env}"

_role="${DANA_ROLE:-}"
_host="${DANA_HOST:-}"
_use="${CI_USE_IRAN_MIRRORS:-}"
if [ -z "$_use" ]; then
  if [ "$_host" = "gpu" ] || [ "$_role" = "prod" ]; then
    _use=1
  else
    _use=0
  fi
fi

if [ "$_use" != "1" ]; then
  echo "ci_apply_iran_mirrors: skipped (CI_USE_IRAN_MIRRORS=${_use})"
  return 0 2>/dev/null || exit 0
fi

IRAN_PIP_INDEX_URL="https://mirror-pypi.pkg.shecan.ir/simple/"
IRAN_PIP_EXTRA_INDEX_URL="https://mirror-pypi.runflare.com/simple/ https://package-mirror.liara.ir/repository/pypi/simple/ https://pypi.org/simple"
IRAN_NPM_REGISTRY="https://mirror-npm.pkg.shecan.ir/"

if [ -f "$MIRROR_ENV" ]; then
  # Load overrides from deploy/mirrors/iran.env (KEY=VALUE lines only).
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|\#*) continue ;;
    esac
    key="${line%%=*}"
    val="${line#*=}"
    val="${val%\"}"
    val="${val#\"}"
    case "$key" in
      IRAN_PIP_INDEX_URL) IRAN_PIP_INDEX_URL="$val" ;;
      IRAN_PIP_EXTRA_INDEX_URL) IRAN_PIP_EXTRA_INDEX_URL="$val" ;;
      IRAN_NPM_REGISTRY) IRAN_NPM_REGISTRY="$val" ;;
    esac
  done < "$MIRROR_ENV"
fi

# Primary = Iranian; extras keep upstream as last resort (fallback chain).
export PIP_INDEX_URL="${PIP_INDEX_URL:-$IRAN_PIP_INDEX_URL}"
export PIP_EXTRA_INDEX_URL="${PIP_EXTRA_INDEX_URL:-$IRAN_PIP_EXTRA_INDEX_URL}"
export PIP_DEFAULT_TIMEOUT="${PIP_DEFAULT_TIMEOUT:-180}"
export PIP_RETRIES="${PIP_RETRIES:-8}"
export UV_INDEX_URL="${UV_INDEX_URL:-$PIP_INDEX_URL}"
export UV_EXTRA_INDEX_URL="${UV_EXTRA_INDEX_URL:-$PIP_EXTRA_INDEX_URL}"
export NPM_CONFIG_REGISTRY="${NPM_CONFIG_REGISTRY:-$IRAN_NPM_REGISTRY}"
export npm_config_registry="${NPM_CONFIG_REGISTRY}"

_pip_hosts=""
for u in $PIP_INDEX_URL $PIP_EXTRA_INDEX_URL; do
  h="${u#*://}"
  h="${h%%/*}"
  [ -n "$h" ] || continue
  case " $_pip_hosts " in *" $h "*) ;; *) _pip_hosts="${_pip_hosts} $h" ;; esac
done
# shellcheck disable=SC2086
export PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST:-$(echo $_pip_hosts)}"

echo "ci_apply_iran_mirrors: PIP_INDEX_URL=$PIP_INDEX_URL"
echo "ci_apply_iran_mirrors: PIP_EXTRA_INDEX_URL=$PIP_EXTRA_INDEX_URL"
echo "ci_apply_iran_mirrors: NPM_CONFIG_REGISTRY=$NPM_CONFIG_REGISTRY"
echo "ci_apply_iran_mirrors: PIP_TRUSTED_HOST=$PIP_TRUSTED_HOST"
