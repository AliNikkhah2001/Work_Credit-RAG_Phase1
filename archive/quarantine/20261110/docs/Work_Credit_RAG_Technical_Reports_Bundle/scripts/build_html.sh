#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# HTML is maintained under html/; sync a copy into out/
cp -f "$ROOT/html/index.html" "$ROOT/out/index.html"
cp -f "$ROOT/html/style.css" "$ROOT/out/style.css"
mkdir -p "$ROOT/out/assets"
rsync -a --delete "$ROOT/assets/" "$ROOT/out/assets/" 2>/dev/null || cp -R "$ROOT/assets/." "$ROOT/out/assets/"
echo "HTML -> $ROOT/out/index.html"
