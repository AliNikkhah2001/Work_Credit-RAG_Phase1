#!/usr/bin/env bash
# Download company logo and common open-source project logos (simple SVG/PNG).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOGO_DIR="$ROOT/assets/logo"
LIBS="$ROOT/assets/logos"
mkdir -p "$LOGO_DIR" "$LIBS"

# ICS company logo
curl -fsSL -A "Mozilla/5.0" -o "$LOGO_DIR/ics-logo.png" \
  "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTkZwJB3ai0rD49Aq56LXU8wfq0WBj7bWa2FUCGjVqRfjigHJWkCEwXlhBW&s=10" || true

# Simple text-mark logos as SVG (offline-friendly, classic monochrome)
write_mark() {
  local name="$1" label="$2"
  cat > "$LIBS/${name}.svg" <<EOF
<svg xmlns="http://www.w3.org/2000/svg" width="160" height="48" viewBox="0 0 160 48">
  <rect width="160" height="48" fill="#f7f7f7" stroke="#333" stroke-width="1"/>
  <text x="80" y="30" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="14" fill="#222">${label}</text>
</svg>
EOF
}

write_mark fastapi "FastAPI"
write_mark langgraph "LangGraph"
write_mark pgvector "pgvector"
write_mark tantivy "tantivy"
write_mark redis "Redis"
write_mark sentence_transformers "SentenceTransformers"
write_mark bge "BGE / BAAI"
write_mark httpx "httpx"
write_mark langfuse "Langfuse"
write_mark llamacpp "llama.cpp"
write_mark trtllm "TensorRT-LLM"
write_mark litellm "LiteLLM"
write_mark docker "Docker"
write_mark sqlalchemy "SQLAlchemy"
write_mark pytorch "PyTorch"
write_mark prometheus "Prometheus"

echo "Assets ready under $ROOT/assets"
