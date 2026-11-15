#!/usr/bin/env bash
# Wire Iranian / regional package mirrors as FALLBACKS only.
# Primary registries stay official (pypi.org, registry.npmjs.org).
#
# Usage (Jenkins Build stage, or local compose builds):
#   source scripts/ci_apply_iran_mirrors.sh
#
# Defaults ON for laptop + GPU/prod. Set CI_USE_IRAN_MIRRORS=0 to skip.
# Escape hatch (Hub/PyPI fully blocked): CI_IRAN_MIRRORS_AS_PRIMARY=1
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIRROR_ENV="${CI_IRAN_MIRROR_ENV:-$ROOT/deploy/mirrors/iran.env}"

_use="${CI_USE_IRAN_MIRRORS:-1}"
if [ "$_use" != "1" ]; then
  echo "ci_apply_iran_mirrors: skipped (CI_USE_IRAN_MIRRORS=${_use})"
  return 0 2>/dev/null || exit 0
fi

UPSTREAM_PIP_INDEX_URL="https://pypi.org/simple"
UPSTREAM_NPM_REGISTRY="https://registry.npmjs.org/"
IRAN_PIP_EXTRA_INDEX_URL="https://mirror-pypi.pkg.shecan.ir/simple/ https://mirror-pypi.runflare.com/simple/ https://package-mirror.liara.ir/repository/pypi/simple/"
IRAN_NPM_REGISTRIES="https://mirror-npm.pkg.shecan.ir/ https://mirror-npm.runflare.com/ https://package-mirror.liara.ir/repository/npm/"

if [ -f "$MIRROR_ENV" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|\#*) continue ;;
    esac
    key="${line%%=*}"
    val="${line#*=}"
    val="${val%\"}"
    val="${val#\"}"
    case "$key" in
      IRAN_PIP_EXTRA_INDEX_URL|IRAN_PIP_INDEX_URL)
        # IRAN_PIP_INDEX_URL kept as alias for older iran.env copies → extras only
        IRAN_PIP_EXTRA_INDEX_URL="$val"
        ;;
      IRAN_NPM_REGISTRIES) IRAN_NPM_REGISTRIES="$val" ;;
      IRAN_NPM_REGISTRY|IRAN_NPM_REGISTRY_FALLBACK)
        case " $IRAN_NPM_REGISTRIES " in
          *" $val "*) ;;
          *) IRAN_NPM_REGISTRIES="${IRAN_NPM_REGISTRIES} $val" ;;
        esac
        ;;
    esac
  done < "$MIRROR_ENV"
fi

# Strip accidental upstream duplicates from the Iran extra list.
_clean_extras=""
for u in $IRAN_PIP_EXTRA_INDEX_URL; do
  case "$u" in
    https://pypi.org/simple|https://pypi.org/simple/|http://pypi.org/simple|http://pypi.org/simple/) continue ;;
  esac
  case " $_clean_extras " in *" $u "*) ;; *) _clean_extras="${_clean_extras} $u" ;; esac
done
IRAN_PIP_EXTRA_INDEX_URL="$(echo $_clean_extras)"

if [ "${CI_IRAN_MIRRORS_AS_PRIMARY:-0}" = "1" ]; then
  # Last-resort when upstream is unreachable (not the default).
  _first_iran="$(echo $IRAN_PIP_EXTRA_INDEX_URL | awk '{print $1}')"
  export PIP_INDEX_URL="${PIP_INDEX_URL:-${_first_iran:-$UPSTREAM_PIP_INDEX_URL}}"
  export PIP_EXTRA_INDEX_URL="${PIP_EXTRA_INDEX_URL:-$UPSTREAM_PIP_INDEX_URL}"
  echo "ci_apply_iran_mirrors: WARNING CI_IRAN_MIRRORS_AS_PRIMARY=1 (Iran as index-url)"
else
  # Default: official primary, Iranian mirrors as extra-index only.
  export PIP_INDEX_URL="${PIP_INDEX_URL:-$UPSTREAM_PIP_INDEX_URL}"
  if [ -n "${PIP_EXTRA_INDEX_URL:-}" ]; then
    :
  else
    export PIP_EXTRA_INDEX_URL="$IRAN_PIP_EXTRA_INDEX_URL"
  fi
fi

export PIP_DEFAULT_TIMEOUT="${PIP_DEFAULT_TIMEOUT:-180}"
export PIP_RETRIES="${PIP_RETRIES:-8}"
export UV_INDEX_URL="${UV_INDEX_URL:-$PIP_INDEX_URL}"
export UV_EXTRA_INDEX_URL="${UV_EXTRA_INDEX_URL:-${PIP_EXTRA_INDEX_URL:-}}"

# npm: always default to official registry; Iran list is for retry helpers.
export NPM_CONFIG_REGISTRY="${NPM_CONFIG_REGISTRY:-$UPSTREAM_NPM_REGISTRY}"
export npm_config_registry="${NPM_CONFIG_REGISTRY}"
export IRAN_NPM_REGISTRIES

_pip_hosts=""
for u in $PIP_INDEX_URL ${PIP_EXTRA_INDEX_URL:-}; do
  h="${u#*://}"
  h="${h%%/*}"
  [ -n "$h" ] || continue
  case " $_pip_hosts " in *" $h "*) ;; *) _pip_hosts="${_pip_hosts} $h" ;; esac
done
# shellcheck disable=SC2086
export PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST:-$(echo $_pip_hosts)}"

# Retry npm against Iranian registries only after upstream fails.
npm_with_iran_fallback() {
  if "$@"; then
    return 0
  fi
  echo "ci_apply_iran_mirrors: npm failed against ${NPM_CONFIG_REGISTRY:-upstream}; trying Iranian registries..."
  local reg
  for reg in $IRAN_NPM_REGISTRIES; do
    echo "ci_apply_iran_mirrors: npm retry registry=$reg"
    if NPM_CONFIG_REGISTRY="$reg" npm_config_registry="$reg" "$@"; then
      return 0
    fi
  done
  return 1
}
export -f npm_with_iran_fallback 2>/dev/null || true

# After upstream-pip builds fail: temporarily promote first Iran mirror to index-url.
promote_iran_pip_primary() {
  local first
  first="$(echo $IRAN_PIP_EXTRA_INDEX_URL | awk '{print $1}')"
  [ -n "$first" ] || return 1
  export PIP_INDEX_URL="$first"
  export PIP_EXTRA_INDEX_URL="$UPSTREAM_PIP_INDEX_URL"
  export UV_INDEX_URL="$PIP_INDEX_URL"
  export UV_EXTRA_INDEX_URL="$PIP_EXTRA_INDEX_URL"
  export PIP_TRUSTED_HOST="$(echo "$PIP_INDEX_URL $PIP_EXTRA_INDEX_URL $IRAN_PIP_EXTRA_INDEX_URL" | tr ' ' '\n' | sed 's|^.*://||;s|/.*||' | awk 'NF && !seen[$0]++' | tr '\n' ' ')"
  echo "ci_apply_iran_mirrors: promoted Iran pip primary → $PIP_INDEX_URL (upstream failed)"
}
export -f promote_iran_pip_primary 2>/dev/null || true

echo "ci_apply_iran_mirrors: mode=fallback-only (upstream primary)"
echo "ci_apply_iran_mirrors: PIP_INDEX_URL=$PIP_INDEX_URL"
echo "ci_apply_iran_mirrors: PIP_EXTRA_INDEX_URL=${PIP_EXTRA_INDEX_URL:-}"
echo "ci_apply_iran_mirrors: NPM_CONFIG_REGISTRY=$NPM_CONFIG_REGISTRY"
echo "ci_apply_iran_mirrors: IRAN_NPM_REGISTRIES=$IRAN_NPM_REGISTRIES"
echo "ci_apply_iran_mirrors: PIP_TRUSTED_HOST=$PIP_TRUSTED_HOST"
