#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/assets/mermaid"
OUT="$ROOT/assets/diagrams"
mkdir -p "$OUT"
CFG="$ROOT/assets/mermaid/mermaid-config.json"
PUP="$ROOT/assets/mermaid/puppeteer.json"
cat > "$CFG" <<'EOF'
{"theme":"neutral","flowchart":{"htmlLabels":false},"sequence":{"mirrorActors":false}}
EOF
cat > "$PUP" <<'EOF'
{"executablePath":"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome","args":["--no-sandbox","--disable-gpu"]}
EOF
for f in "$SRC"/*.mmd; do
  base="$(basename "$f" .mmd)"
  echo "Rendering $base"
  npx --yes @mermaid-js/mermaid-cli@11.4.0 -i "$f" -o "$OUT/${base}.png" -c "$CFG" -p "$PUP" -b white -s 2
  npx --yes @mermaid-js/mermaid-cli@11.4.0 -i "$f" -o "$OUT/${base}.svg" -c "$CFG" -p "$PUP" -b white || true
done
echo "Diagrams in $OUT"
ls -1 "$OUT" | wc -l
