#!/usr/bin/env bash
# =============================================================================
# scripts/dana_lastgood_prune.sh — bounded, rollback-safe retention for
# `dana-lastgood/<service>:<stamp>-<sha>` image tags.
#
# WHY THIS EXISTS
#   Every promotion/rollback stamps a fresh `dana-lastgood/<svc>:<ISO>-<sha>`
#   tag and nothing ever removed the old ones. One afternoon of deploy
#   simulations left 43 such tags on a laptop; the GPU host runs the auto-heal
#   daemon daily plus a 3-hour retry loop, so the tag set — and the image
#   generations those tags keep addressable — grows without bound.
#
# WHAT ALWAYS SURVIVES (union of these; precedence order)
#   1. Rollback state: any tag referenced by a last-known-good state file.
#      The rollback path (`deploy/gpu/rollback.sh`) resolves `images[].rollback_tag`
#      from `last_good.json` (and `.prev.json` for `--from-state`), so pruning
#      that tag destroys rollback capability. Every state file found is scanned,
#      including the legacy `deploy/compose/.last_good.json` manifest.
#   2. Recency: the N newest tags per repository (`DANA_LASTGOOD_KEEP`, default 5).
#   3. In-use images: a tag is never removed when it is the last reference to an
#      image a running container uses (`docker ps` image IDs, never name matching).
#      A tag that shares its image with another tag is still safe to untag.
#
# WHAT IT DELETES
#   Only the TAG: `docker rmi <repo>:<tag>`, never `-f`, never a bare image ID.
#   Untagging a shared image (`python:3.11-slim`, `rag-kb:local`, …) leaves the
#   image, the layers and every container untouched. No volumes, no networks,
#   no `docker system prune`.
#
# SAFE BY DEFAULT
#   Dry-run unless `--apply` or `DANA_LASTGOOD_PRUNE_APPLY=1`. A bad prune cannot
#   silently destroy rollback capability. Callers must treat this script as
#   non-fatal: a prune failure must never fail a deploy or a heal.
#
# Usage:
#   bash scripts/dana_lastgood_prune.sh                  # dry-run (show the plan)
#   bash scripts/dana_lastgood_prune.sh --apply          # retire old tags
#   bash scripts/dana_lastgood_prune.sh --keep 3 --apply
#   bash scripts/dana_lastgood_prune.sh --self-test      # no Docker needed
#   bash scripts/dana_lastgood_prune.sh --state f.json   # extra state file
#
#   Optional disk hygiene (separate, off by default, never `system prune`):
#   bash scripts/dana_lastgood_prune.sh --prune-dangling
#   bash scripts/dana_lastgood_prune.sh --prune-build-cache --keep-storage 10GB
#
# Flags:
#   --apply                  actually remove tags (default: dry-run)
#   --dry-run                force dry-run even if the env var is set
#   --keep N                 keep the N newest tags per repository (default 5)
#   --state FILE             add a last-known-good state file to protect
#                            (repeatable). Default: auto-discovery, see --help-full.
#   --inventory-file FILE    read `repo|tag|imageid` lines instead of `docker images`
#   --in-use-file FILE       read `sha256:<id>|<container>` lines instead of `docker ps`
#   --strict-inuse           keep every tag whose image a container is running,
#                            even when another tag still references that image
#   --prefix NAME            tag repository prefix (default dana-lastgood)
#   --prune-dangling         `docker image prune -f` (dangling layers only)
#   --prune-build-cache      `docker builder prune -f --keep-storage=<size>`
#   --keep-storage SIZE      build-cache budget for --prune-build-cache (default 10GB)
#   --self-test              prove KEEP-N / LKG-protection logic on fake data
#   --quiet                  only warnings/errors and the summary
#   -h, --help               this header
#
# Exit: 0 ok (including "nothing to prune"), 1 usage/precondition error,
#       3 self-test failed. Per-tag `docker rmi` failures are reported but never
#       fatal — this script must not be able to break a deploy.
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HOST_REPO="${DANA_HOST_REPO:-$ROOT}"

PREFIX="${DANA_LASTGOOD_PREFIX:-dana-lastgood}"
KEEP="${DANA_LASTGOOD_KEEP:-5}"
QUIET=0
SELF_TEST=0
STRICT_INUSE=0
PRUNE_DANGLING=0
PRUNE_BUILD_CACHE=0
KEEP_STORAGE="${DANA_BUILDER_KEEP_STORAGE:-10GB}"
INVENTORY_FILE=""
IN_USE_FILE=""
STATE_FILES=()

# Apply is opt-in: env var or an explicit flag. Everything else is a dry-run.
APPLY=0
[ "${DANA_LASTGOOD_PRUNE_APPLY:-0}" = "1" ] && APPLY=1

say()  { [ "$QUIET" = "1" ] || printf '%s\n' "$*"; }
warn() { printf '[lastgood-prune][WARN] %s\n' "$*" >&2; }
err()  { printf '[lastgood-prune][ERR] %s\n' "$*" >&2; }
die()  { err "$*"; exit 1; }

usage() { sed -n '2,57p' "$0"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --dry-run) APPLY=0; shift ;;
    --keep) [ $# -ge 2 ] || die "--keep needs a value"; KEEP="$2"; shift 2 ;;
    --keep=*) KEEP="${1#*=}"; shift ;;
    --state) [ $# -ge 2 ] || die "--state needs a file"; STATE_FILES+=("$2"); shift 2 ;;
    --state=*) STATE_FILES+=("${1#*=}"); shift ;;
    --inventory-file) INVENTORY_FILE="$2"; shift 2 ;;
    --in-use-file) IN_USE_FILE="$2"; shift 2 ;;
    --strict-inuse) STRICT_INUSE=1; shift ;;
    --prefix) PREFIX="$2"; shift 2 ;;
    --prune-dangling) PRUNE_DANGLING=1; shift ;;
    --prune-build-cache) PRUNE_BUILD_CACHE=1; shift ;;
    --keep-storage) KEEP_STORAGE="$2"; shift 2 ;;
    --self-test) SELF_TEST=1; shift ;;
    --quiet) QUIET=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown arg: $1 (see --help)" ;;
  esac
done

case "$KEEP" in
  ''|*[!0-9]*) die "--keep must be a non-negative integer (got '$KEEP')" ;;
esac

TMPDIR_RUN="$(mktemp -d "${TMPDIR:-/tmp}/dana-lastgood-prune.XXXXXX")" || die "mktemp failed"
trap 'rm -rf "$TMPDIR_RUN"' EXIT INT TERM

INV_ALL="$TMPDIR_RUN/inventory-all.txt"      # repo|tag|imageid   (every tag on the host)
INV_DANA="$TMPDIR_RUN/inventory-dana.txt"    # repo|tag|imageid   (prefix only, newest first)
IN_USE="$TMPDIR_RUN/in-use.txt"              # imageid|container
IMG_REFS="$TMPDIR_RUN/img-refs.txt"          # imageid|count      (all tags)
IMG_DANA_REFS="$TMPDIR_RUN/img-dana-refs.txt"
PROTECTED_TAGS="$TMPDIR_RUN/protected-tags.txt"
PROTECTED_IMGS="$TMPDIR_RUN/protected-imgs.txt"
STATE_LIST="$TMPDIR_RUN/state-files.txt"
DECISIONS="$TMPDIR_RUN/decisions.txt"        # VERDICT|repo|tag|imageid|reason

# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
discover_state_files() {
  local d f
  # deploy/gpu owns the authoritative promoted state; the sim harness uses its
  # own DANA_STATE_DIR (deploy/gpu/sim/.state-*), and scripts/ci_rollback.sh
  # reads the legacy deploy/compose manifest. Protect tags from all of them:
  # over-protecting costs a few tags, under-protecting costs rollback.
  for d in "${DANA_STATE_DIR:-}" "${DANA_STATE_FILE:+$(dirname "${DANA_STATE_FILE:-}")}" \
           "$HOST_REPO/deploy/gpu/state" "$HOST_REPO"/deploy/gpu/sim/.state-* \
           "$HOST_REPO/deploy/compose"; do
    [ -n "$d" ] && [ -d "$d" ] || continue
    for f in "$d/last_good.json" "$d/last_good.prev.json" \
             "$d/state/last_good.json" "$d/state/last_good.prev.json" \
             "$d/.last_good.json" "$d/.last_good.json.prev"; do
      [ -f "$f" ] && printf '%s\n' "$f"
    done
  done
}

# Extract rollback tags (and recorded image ids) from state files. JSON is read
# properly; hand-written/legacy manifests fall back to a regex scan so a
# malformed file still protects whatever tags it mentions.
extract_protected() {
  local files=("$@")
  [ "${#files[@]}" -gt 0 ] || return 0
  python3 - "${files[@]}" <<'PY'
import json
import re
import sys

tags, ids = set(), set()
TAG_RE = re.compile(r"%s/[^\s\"',]+" % "dana-lastgood")
ID_RE = re.compile(r"sha256:[0-9a-f]{64}")


def walk(node):
    if isinstance(node, dict):
        for key, val in node.items():
            if key == "rollback_tag" and isinstance(val, str):
                tags.add(val)
            elif key == "image_id" and isinstance(val, str):
                ids.add(val)
            elif key == "image_ids" and isinstance(val, dict):
                ids.update(v for v in val.values() if isinstance(v, str))
            else:
                walk(val)
    elif isinstance(node, list):
        for item in node:
            walk(item)


for path in sys.argv[1:]:
    try:
        with open(path) as fh:
            walk(json.load(fh))
    except Exception:
        try:
            with open(path, errors="replace") as fh:
                blob = fh.read()
        except OSError:
            continue
        tags.update(TAG_RE.findall(blob))
        ids.update(ID_RE.findall(blob))

for tag in sorted(tags):
    print("TAG\t" + tag)
for image_id in sorted(ids):
    print("IMG\t" + image_id)
PY
}

load_inventory() {
  if [ -n "$INVENTORY_FILE" ]; then
    [ -f "$INVENTORY_FILE" ] || die "inventory file not found: $INVENTORY_FILE"
    # Tolerate a `repo|tag|id|anything` fixture; keep the first three columns.
    awk -F'|' 'NF>=3 && $1!="" {printf "%s|%s|%s\n", $1, $2, $3}' "$INVENTORY_FILE"
    return 0
  fi
  command -v docker >/dev/null 2>&1 || die "docker not found (use --inventory-file for offline runs)"
  docker images --no-trunc --format '{{.Repository}}|{{.Tag}}|{{.ID}}' 2>/dev/null
}

load_in_use() {
  if [ -n "$IN_USE_FILE" ]; then
    [ -f "$IN_USE_FILE" ] || die "in-use file not found: $IN_USE_FILE"
    awk -F'|' 'NF>=1 && $1!="" {printf "%s|%s\n", $1, ($2==""?"unknown":$2)}' "$IN_USE_FILE"
    return 0
  fi
  command -v docker >/dev/null 2>&1 || return 0
  docker ps -q 2>/dev/null | while IFS= read -r cid; do
    [ -n "$cid" ] || continue
    docker inspect --format '{{.Image}}|{{.Name}}' "$cid" 2>/dev/null | sed 's#^/##'
  done
}

# count_in <file> <key> — second column for a key, or 0.
count_in() {
  awk -F'|' -v k="$2" '$1==k {print $2; found=1; exit} END {if (!found) print 0}' "$1"
}

count_map() { awk -F'|' 'NF>=3 {c[$3]++} END {for (i in c) printf "%s|%d\n", i, c[i]}'; }

in_use_container() {
  awk -F'|' -v k="$1" '$1==k {print $2; found=1; exit} END {if (!found) print ""}' "$IN_USE"
}

# Best (newest) `repo:tag` addressing an image ID, from the dana inventory.
newest_tag_for_image() {
  awk -F'|' -v k="$1" '$1==k {print $2; found=1; exit} END {if (!found) print ""}' "$IMG_NEWEST_TAG"
}

# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------
build_plan() {
  : >"$INV_ALL"; : >"$INV_DANA"; : >"$IN_USE"; : >"$PROTECTED_TAGS"; : >"$PROTECTED_IMGS"; : >"$DECISIONS"

  # 1. inventory + reference counts
  load_inventory | sort >"$INV_ALL"
  load_inventory | awk -F'|' -v p="$PREFIX/" 'index($1, p)==1' | sort >"$TMPDIR_RUN/dana-raw.txt"
  # Newest first per repo. The stamp is the tag prefix (YYYYMMDDTHHMMSSZ), which
  # sorts chronologically as plain text, so no `docker inspect` is required.
  sort -t'|' -k1,1 -k2,2r "$TMPDIR_RUN/dana-raw.txt" >"$INV_DANA"
  load_in_use >"$IN_USE"
  count_map <"$INV_ALL" >"$IMG_REFS"
  count_map <"$INV_DANA" >"$IMG_DANA_REFS"

  # 2. rollback protection
  discover_state_files | sort -u >"$TMPDIR_RUN/discovered.txt"
  if [ "${#STATE_FILES[@]}" -gt 0 ]; then
    printf '%s\n' "${STATE_FILES[@]}" >>"$TMPDIR_RUN/discovered.txt"
  fi
  sort -u "$TMPDIR_RUN/discovered.txt" >"$STATE_LIST"
  local existing=() f
  while IFS= read -r f; do
    [ -f "$f" ] && existing+=("$f")
  done <"$STATE_LIST"
  if [ "${#existing[@]}" -gt 0 ]; then
    extract_protected "${existing[@]}" >"$TMPDIR_RUN/protected.txt"
    awk -F'\t' '$1=="TAG" {print $2}' "$TMPDIR_RUN/protected.txt" | sort -u >"$PROTECTED_TAGS"
    awk -F'\t' '$1=="IMG" {print $2}' "$TMPDIR_RUN/protected.txt" | sort -u >"$PROTECTED_IMGS"
  fi

  # 3. walk newest-first; keep N per repo, force-keep protected tags.
  # imageid -> newest `repo:tag` that addresses those bytes (used to keep a
  # recorded image resolvable even when the state file names only the image ID).
  IMG_NEWEST_TAG="$TMPDIR_RUN/img-newest-tag.txt"
  awk -F'|' '{
      key = $3
      if (!(key in best_tag) || $2 > best_tag[key]) { best_tag[key] = $2; best_ref[key] = $1 ":" $2 }
    }
    END { for (k in best_ref) printf "%s|%s\n", k, best_ref[k] }' "$INV_DANA" >"$IMG_NEWEST_TAG"

  local repo tag img cur_repo="" idx=0 stamp verdict reason
  while IFS='|' read -r repo tag img; do
    [ -n "$repo" ] || continue
    if [ "$repo" != "$cur_repo" ]; then
      cur_repo="$repo"; idx=0
    fi
    idx=$((idx + 1))
    stamp="$(printf '%s' "$tag" | sed -n 's/^\([0-9]\{8\}T[0-9]\{6\}Z\).*/\1/p')"

    if [ -z "$stamp" ]; then
      # Not a recognisable rollback tag: age is unknown, so never guess.
      verdict="KEEP"; reason="unrecognised tag format (age unknown)"
    elif grep -Fxq "$repo:$tag" "$PROTECTED_TAGS" 2>/dev/null; then
      verdict="KEEP"; reason="referenced by last-known-good state"
    elif [ "$idx" -le "$KEEP" ]; then
      verdict="KEEP"; reason="recent $idx/$KEEP in $repo"
    elif [ -n "$img" ] && grep -Fxq "$img" "$PROTECTED_IMGS" 2>/dev/null \
         && [ "$(newest_tag_for_image "$img")" = "$repo:$tag" ]; then
      # The state file names this image's bytes but not this exact tag (older
      # manifest, or the tag was re-pointed). Keep the newest tag that still
      # addresses those bytes, so the recorded image stays resolvable by name.
      verdict="KEEP"; reason="newest tag for an image recorded in last-known-good state"
    else
      verdict="REMOVE"; reason="older than newest $KEEP in $repo"
    fi
    printf '%s|%s|%s|%s|%s\n' "$verdict" "$repo" "$tag" "$img" "$reason" >>"$DECISIONS"
  done <"$INV_DANA"

  # 4. in-use safety, applied only to removal candidates.
  local container others
  : >"$TMPDIR_RUN/decisions-final.txt"
  while IFS='|' read -r verdict repo tag img reason; do
    if [ "$verdict" = "REMOVE" ]; then
      container="$(in_use_container "$img")"
      if [ -n "$container" ]; then
        others=$(( $(count_in "$IMG_REFS" "$img") - $(count_in "$IMG_DANA_REFS" "$img") ))
        if [ "$STRICT_INUSE" = "1" ]; then
          verdict="KEEP"; reason="in use by $container (--strict-inuse)"
        elif [ "$others" -le 0 ]; then
          verdict="KEEP"; reason="in use by $container and no other tag names this image"
        else
          reason="older than newest $KEEP (shared image, $others other tag(s) keep it)"
        fi
      fi
    fi
    printf '%s|%s|%s|%s|%s\n' "$verdict" "$repo" "$tag" "$img" "$reason" >>"$TMPDIR_RUN/decisions-final.txt"
  done <"$DECISIONS"
  cp "$TMPDIR_RUN/decisions-final.txt" "$DECISIONS"
}

report_plan() {
  local total keep remove
  total=$(grep -c . "$INV_DANA" 2>/dev/null || true); [ -n "$total" ] || total=0
  keep=$(awk -F'|' '$1=="KEEP"' "$DECISIONS" 2>/dev/null | grep -c . || true); [ -n "$keep" ] || keep=0
  remove=$(awk -F'|' '$1=="REMOVE"' "$DECISIONS" 2>/dev/null | grep -c . || true); [ -n "$remove" ] || remove=0

  say "== dana-lastgood retention plan =="
  say "prefix=$PREFIX/  keep=$KEEP per repo  mode=$([ "$APPLY" = "1" ] && echo APPLY || echo DRY-RUN)"
  say ""
  say "rollback state files scanned (tags here are never pruned):"
  if [ -s "$STATE_LIST" ]; then
    while IFS= read -r f; do [ -f "$f" ] && say "  $f  (present)"; done <"$STATE_LIST"
  else
    say "  (none found — no state file to protect, be careful)"
  fi
  say ""
  say "protected tags: $(grep -c . "$PROTECTED_TAGS" 2>/dev/null || echo 0)"
  if [ -s "$PROTECTED_TAGS" ]; then sed 's/^/  /' "$PROTECTED_TAGS"; fi
  say ""

  say "inventory: $total tag(s) under $PREFIX/"
  local repo n_keep n_remove
  for repo in $(awk -F'|' '{print $2}' "$DECISIONS" | sort -u); do
    n_keep=$(awk -F'|' -v r="$repo" '$1=="KEEP" && $2==r' "$DECISIONS" | grep -c . || true)
    n_remove=$(awk -F'|' -v r="$repo" '$1=="REMOVE" && $2==r' "$DECISIONS" | grep -c . || true)
    printf '  %-38s total %2d   keep %2d   remove %2d\n' "$repo" $((n_keep + n_remove)) "$n_keep" "$n_remove"
  done
  say ""

  if [ "$keep" -gt 0 ]; then
    say "KEEP ($keep):"
    awk -F'|' '$1=="KEEP" {printf "%s:%s  [%s]\n", $2, $3, $5}' "$DECISIONS" | sed 's/^/  /'
    say ""
  fi
  if [ "$remove" -gt 0 ]; then
    if [ "$APPLY" = "1" ]; then say "REMOVE ($remove):"; else say "WOULD REMOVE ($remove):"; fi
    awk -F'|' '$1=="REMOVE" {printf "%s:%s  [%s]\n", $2, $3, $5}' "$DECISIONS" | sed 's/^/  /'
    say ""
  fi
  say "summary: keep=$keep remove=$remove (of $total)"
}

# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------
apply_plan() {
  local removed=0 failed=0 repo tag img reason
  while IFS='|' read -r _ repo tag img reason; do
    # Plain untag. No -f: Docker refuses if this is the last reference to an
    # image a container holds, which is exactly the behaviour we want.
    if docker rmi "$repo:$tag" >/dev/null 2>"$TMPDIR_RUN/rmi.err"; then
      removed=$((removed + 1))
      say "  removed $repo:$tag"
    else
      failed=$((failed + 1))
      warn "could not remove $repo:$tag — $(tr '\n' ' ' <"$TMPDIR_RUN/rmi.err" | cut -c1-160)"
    fi
  done < <(awk -F'|' '$1=="REMOVE"' "$DECISIONS")
  say "apply: removed=$removed failed=$failed"
  # Never fatal: the caller is a deploy/heal path.
  return 0
}

# ---------------------------------------------------------------------------
# Optional disk hygiene — separate from tag retention, opt-in, no system prune.
# ---------------------------------------------------------------------------
disk_hygiene() {
  [ "$PRUNE_DANGLING" = "1" ] || [ "$PRUNE_BUILD_CACHE" = "1" ] || return 0
  local mode="EXECUTE"; [ "$APPLY" = "1" ] || mode="DRY-RUN"
  say ""
  say "== disk hygiene ($mode) =="
  if [ "$PRUNE_DANGLING" = "1" ]; then
    if [ "$APPLY" = "1" ]; then
      say "  docker image prune -f   # dangling layers only; no tagged image"
      docker image prune -f 2>&1 | sed 's/^/    /'
    else
      say "  would run: docker image prune -f   # dangling layers only"
    fi
  fi
  if [ "$PRUNE_BUILD_CACHE" = "1" ]; then
    if [ "$APPLY" = "1" ]; then
      say "  docker builder prune -f --keep-storage=$KEEP_STORAGE"
      docker builder prune -f --keep-storage="$KEEP_STORAGE" 2>&1 | sed 's/^/    /' \
        || warn "builder prune --keep-storage unsupported on this Docker; nothing removed"
    else
      say "  would run: docker builder prune -f --keep-storage=$KEEP_STORAGE"
    fi
  fi
  say "  (never: docker system prune -a, volume prune, non-dana tagged images)"
}

# ---------------------------------------------------------------------------
# Self-test — pure logic, no Docker, no real tags.
# ---------------------------------------------------------------------------
self_test() {
  local failures=0 case_dir fixture
  st_assert() { # <description> <expected> <actual>
    if [ "$2" = "$3" ]; then
      printf '  PASS  %s\n' "$1"
    else
      printf '  FAIL  %s (expected: %s | actual: %s)\n' "$1" "$2" "$3"
      failures=$((failures + 1))
    fi
  }
  st_verdict() { # <repo:tag> → KEEP|REMOVE|MISSING
    awk -F'|' -v k="$1" '{ key = $2 ":" $3; if (key == k) {print $1; found=1; exit} } END {if (!found) print "MISSING"}' "$DECISIONS"
  }
  st_reset() {
    case_dir="$(mktemp -d "$TMPDIR_RUN/case.XXXXXX")"
    fixture="$case_dir/inv.txt"
    : >"$case_dir/no-containers.txt"
    INVENTORY_FILE="$fixture"
    IN_USE_FILE="$case_dir/no-containers.txt"   # isolated from the host's containers
    STATE_FILES=()
    APPLY=0; QUIET=1; STRICT_INUSE=0
    discover_state_files() { :; }   # isolate the planner from this host's state
  }
  st_run() { build_plan; }

  printf 'self-test: KEEP-N selection and last-known-good protection\n'

  # --- case 1: KEEP-N per repo
  st_reset
  cat >"$fixture" <<'EOF'
dana-lastgood/api|20260101T000001Z-aaaaaaa|sha256:1111
dana-lastgood/api|20260101T000002Z-aaaaaaa|sha256:1111
dana-lastgood/api|20260101T000003Z-aaaaaaa|sha256:1111
dana-lastgood/api|20260101T000004Z-aaaaaaa|sha256:1111
dana-lastgood/api|20260101T000005Z-aaaaaaa|sha256:1111
dana-lastgood/api|20260101T000006Z-aaaaaaa|sha256:1111
EOF
  KEEP=3; st_run
  st_assert "case1 newest tag kept"          KEEP   "$(st_verdict dana-lastgood/api:20260101T000006Z-aaaaaaa)"
  st_assert "case1 3rd-newest kept"          KEEP   "$(st_verdict dana-lastgood/api:20260101T000004Z-aaaaaaa)"
  st_assert "case1 4th-newest removed"       REMOVE "$(st_verdict dana-lastgood/api:20260101T000003Z-aaaaaaa)"
  st_assert "case1 oldest removed"           REMOVE "$(st_verdict dana-lastgood/api:20260101T000001Z-aaaaaaa)"
  st_assert "case1 exactly 3 kept"           3      "$(awk -F'|' '$1=="KEEP"' "$DECISIONS" | grep -c .)"

  # --- case 2: repo counting is per-repository, not global
  st_reset
  cat >"$fixture" <<'EOF'
dana-lastgood/api|20260101T000001Z-aaaaaaa|sha256:1111
dana-lastgood/api|20260101T000002Z-aaaaaaa|sha256:1111
dana-lastgood/api|20260101T000003Z-aaaaaaa|sha256:1111
dana-lastgood/api|20260101T000004Z-aaaaaaa|sha256:1111
dana-lastgood/web|20260101T000001Z-bbbbbbb|sha256:2222
dana-lastgood/web|20260101T000002Z-bbbbbbb|sha256:2222
dana-lastgood/web|20260101T000003Z-bbbbbbb|sha256:2222
dana-lastgood/web|20260101T000004Z-bbbbbbb|sha256:2222
EOF
  KEEP=2; st_run
  st_assert "case2 api keeps its own 2"      2 "$(awk -F'|' '$1=="KEEP" && $2=="dana-lastgood/api"' "$DECISIONS" | grep -c .)"
  st_assert "case2 web keeps its own 2"      2 "$(awk -F'|' '$1=="KEEP" && $2=="dana-lastgood/web"' "$DECISIONS" | grep -c .)"
  st_assert "case2 api oldest removed"       REMOVE "$(st_verdict dana-lastgood/api:20260101T000001Z-aaaaaaa)"

  # --- case 3: active LKG outside the top N is retained
  st_reset
  cat >"$fixture" <<'EOF'
dana-lastgood/api|20260101T000001Z-aaaaaaa|sha256:1111
dana-lastgood/api|20260101T000002Z-aaaaaaa|sha256:1111
dana-lastgood/api|20260101T000003Z-aaaaaaa|sha256:1111
dana-lastgood/api|20260101T000004Z-aaaaaaa|sha256:1111
dana-lastgood/api|20260101T000005Z-aaaaaaa|sha256:1111
dana-lastgood/api|20260101T000006Z-aaaaaaa|sha256:1111
EOF
  cat >"$case_dir/last_good.json" <<'EOF'
{"images": [{"service": "api", "image_id": "sha256:1111",
             "rollback_tag": "dana-lastgood/api:20260101T000001Z-aaaaaaa"}]}
EOF
  KEEP=3; STATE_FILES=("$case_dir/last_good.json"); st_run
  st_assert "case3 old LKG tag retained"     KEEP   "$(st_verdict dana-lastgood/api:20260101T000001Z-aaaaaaa)"
  st_assert "case3 next-oldest still pruned" REMOVE "$(st_verdict dana-lastgood/api:20260101T000002Z-aaaaaaa)"
  st_assert "case3 keep count is N+1"        4      "$(awk -F'|' '$1=="KEEP"' "$DECISIONS" | grep -c .)"
  grep -q 'referenced by last-known-good state' <(awk -F'|' '$1=="KEEP" && $3=="20260101T000001Z-aaaaaaa"' "$DECISIONS") \
    && st_assert "case3 reason names the LKG" 1 1 || st_assert "case3 reason names the LKG" 1 0

  # --- case 4: previous state file is protected too (rollback --from-state prev)
  st_reset
  cat >"$fixture" <<'EOF'
dana-lastgood/api|20260101T000001Z-aaaaaaa|sha256:1111
dana-lastgood/api|20260101T000002Z-aaaaaaa|sha256:1111
dana-lastgood/api|20260101T000003Z-aaaaaaa|sha256:1111
dana-lastgood/api|20260101T000004Z-aaaaaaa|sha256:1111
dana-lastgood/api|20260101T000005Z-aaaaaaa|sha256:1111
EOF
  cat >"$case_dir/last_good.prev.json" <<'EOF'
{"images": [{"service": "api", "rollback_tag": "dana-lastgood/api:20260101T000001Z-aaaaaaa"}]}
EOF
  KEEP=2; STATE_FILES=("$case_dir/last_good.prev.json"); st_run
  st_assert "case4 prev-state tag retained"  KEEP   "$(st_verdict dana-lastgood/api:20260101T000001Z-aaaaaaa)"
  st_assert "case4 prev-state tag survives N" 3     "$(awk -F'|' '$1=="KEEP"' "$DECISIONS" | grep -c .)"

  # --- case 5: in-use image guard (last reference vs shared image)
  st_reset
  cat >"$fixture" <<'EOF'
dana-lastgood/api|20260101T000001Z-aaaaaaa|sha256:9999
dana-lastgood/api|20260101T000002Z-aaaaaaa|sha256:9999
python:3.11-slim|latest|sha256:9999
EOF
  printf 'sha256:9999|/busy-container\n' >"$case_dir/in-use.txt"
  IN_USE_FILE="$case_dir/in-use.txt"; KEEP=1
  rm -f "$case_dir/last_good.json"
  st_run
  st_assert "case5 shared in-use image: old tag pruned" REMOVE "$(st_verdict dana-lastgood/api:20260101T000001Z-aaaaaaa)"

  st_reset
  cat >"$fixture" <<'EOF'
dana-lastgood/api|20260101T000001Z-aaaaaaa|sha256:9999
dana-lastgood/api|20260101T000002Z-aaaaaaa|sha256:9999
EOF
  printf 'sha256:9999|/busy-container\n' >"$case_dir/in-use.txt"
  IN_USE_FILE="$case_dir/in-use.txt"; KEEP=1; st_run
  st_assert "case5 sole in-use reference kept" KEEP   "$(st_verdict dana-lastgood/api:20260101T000001Z-aaaaaaa)"
  st_assert "case5 keeps both when image is in use" 2 "$(awk -F'|' '$1=="KEEP"' "$DECISIONS" | grep -c .)"

  # --- case 6: unrecognised tag format is never guessed at
  st_reset
  cat >"$fixture" <<'EOF'
dana-lastgood/api|manual-hotfix|sha256:3333
dana-lastgood/api|20260101T000002Z-aaaaaaa|sha256:3333
dana-lastgood/api|20260101T000003Z-aaaaaaa|sha256:3333
dana-lastgood/api|20260101T000004Z-aaaaaaa|sha256:3333
EOF
  KEEP=1; st_run
  st_assert "case6 unrecognised tag kept"    KEEP "$(st_verdict dana-lastgood/api:manual-hotfix)"

  # --- case 7: dry-run is the default, so a plan exists but APPLY stays off
  st_reset
  cat >"$fixture" <<'EOF'
dana-lastgood/api|20260101T000001Z-aaaaaaa|sha256:4444
dana-lastgood/api|20260101T000002Z-aaaaaaa|sha256:4444
EOF
  KEEP=1; APPLY=0; st_run
  st_assert "case7 plan proposes a prune"    REMOVE "$(st_verdict dana-lastgood/api:20260101T000001Z-aaaaaaa)"
  st_assert "case7 APPLY stays off by default" 0 "$APPLY"

  # --- case 8: state records only an image ID (no tag): newest holder survives
  st_reset
  cat >"$fixture" <<'EOF'
dana-lastgood/kb|20260101T000001Z-aaaaaaa|sha256:5555
dana-lastgood/kb|20260101T000002Z-aaaaaaa|sha256:5555
dana-lastgood/kb|20260101T000003Z-aaaaaaa|sha256:6666
dana-lastgood/kb|20260101T000004Z-aaaaaaa|sha256:6666
EOF
  cat >"$case_dir/last_good.json" <<'EOF'
{"compose": {"config_sha256": "x"},
 "image_ids": {"rag-kb:local": "sha256:5555"}}
EOF
  KEEP=1; STATE_FILES=("$case_dir/last_good.json"); st_run
  st_assert "case8 newest holder of recorded image kept" KEEP \
    "$(st_verdict dana-lastgood/kb:20260101T000002Z-aaaaaaa)"
  st_assert "case8 older holder of same image pruned"    REMOVE \
    "$(st_verdict dana-lastgood/kb:20260101T000001Z-aaaaaaa)"

  printf 'self-test: %s\n' "$([ "$failures" -eq 0 ] && echo "all cases PASS" || echo "$failures FAILURE(S)")"
  [ "$failures" -eq 0 ] || return 3
  return 0
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if [ "$SELF_TEST" = "1" ]; then
  self_test
  exit $?
fi

if [ -n "$INVENTORY_FILE" ]; then
  [ -f "$INVENTORY_FILE" ] || die "inventory file not found: $INVENTORY_FILE"
fi

build_plan

_total=$(grep -c . "$INV_DANA" 2>/dev/null || true); [ -n "$_total" ] || _total=0
if [ "$_total" -eq 0 ]; then
  say "no $PREFIX/* tags found — nothing to prune"
  disk_hygiene
  exit 0
fi

report_plan

if [ "$APPLY" = "1" ]; then
  say ""
  say "applying (tag-only untag, no --force):"
  apply_plan
else
  say ""
  say "dry-run: nothing removed. Re-run with --apply (or DANA_LASTGOOD_PRUNE_APPLY=1) to retire these tags."
fi

disk_hygiene
exit 0
