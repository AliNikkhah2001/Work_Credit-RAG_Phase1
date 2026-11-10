#!/usr/bin/env bash
# Laptop OpenRouter mode must not keep a stale local cross-encoder pin.
#
# Jenkins copies gitignored deploy/compose/.env from the host. That file
# previously set KB_RERANKER_BACKEND=local (BGE), which overrides
# LLM_UPSTREAM_MODE=openrouter and makes every stage deploy load the local
# reranker again. Embed backend is left unchanged (pgvector rows are 384-d).
set -euo pipefail

file="${1:-deploy/compose/.env}"
if [ ! -f "$file" ]; then
  echo "ci_laptop_rerank_env: no env file at $file — skip"
  exit 0
fi

mode="$(grep -E '^LLM_UPSTREAM_MODE=' "$file" | tail -1 | cut -d= -f2- | tr -d '"' | tr '[:upper:]' '[:lower:]' || true)"
if [ "$mode" != "openrouter" ]; then
  echo "ci_laptop_rerank_env: LLM_UPSTREAM_MODE=${mode:-unset} — leave reranker env unchanged"
  exit 0
fi

python3 - "$file" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
local_markers = (
    "baai/",
    "cross-encoder/",
    "sentence-transformers/",
    "jinaai/",
    "alibaba-nlp/",
)
lines = path.read_text().splitlines()
out = []
seen_backend = False
seen_model = False
for line in lines:
    if line.startswith("KB_RERANKER_BACKEND="):
        out.append("KB_RERANKER_BACKEND=openrouter")
        seen_backend = True
        continue
    if line.startswith("KB_RERANKER_MODEL="):
        val = line.split("=", 1)[1].strip().lower()
        if (not val) or any(m in val for m in local_markers):
            out.append("KB_RERANKER_MODEL=cohere/rerank-v3.5")
        else:
            out.append(line)
        seen_model = True
        continue
    out.append(line)
if not seen_backend:
    out.append("KB_RERANKER_BACKEND=openrouter")
if not seen_model:
    out.append("KB_RERANKER_MODEL=cohere/rerank-v3.5")
path.write_text("\n".join(out) + "\n")
print("ci_laptop_rerank_env: reranker forced to OpenRouter cohere/rerank-v3.5")
PY
