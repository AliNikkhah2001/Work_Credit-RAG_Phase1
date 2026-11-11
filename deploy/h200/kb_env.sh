# Shared environment for the KB manager (port 8000) on the H200 host.
# Source this from any launcher so a manual/automated restart can NEVER
# silently degrade retrieval to CPU or lose the reranker.
#
# 2026-10-12 incident recap (why this file exists):
#   - a bare restart dropped KB_EMBED_DEVICE/KB_RERANKER_DEVICE -> config
#     defaulted to "cpu" -> dense leg 2.6 s instead of 24 ms;
#   - HF_HOME pointed at a nonexistent /tmp/hf_clean and HF_HUB_OFFLINE=1
#     made transformers' is_base_mistral() network probe hard-fail -> the
#     cross-encoder reranker was silently OFFLINE on every query
#     ("reranker offline fallback" in the service log, RRF-only results).
# Both are now additionally guarded in code (config.py GPU-first default,
# kb_manager/model_cache.py offline-safe model resolution), but keep this
# env explicit anyway — explicit beats implicit.

# --- data plane (pgvector HNSW, RAM-pinned: shared_buffers=16GB, pg_prewarm) ---
export KB_DB_MODE=pgvector
export KB_DB_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/kb_manager

# --- GPU residency (H200): dense ~6 ms, rerank ~20 ms (vs 2.6 s / 5.4 s CPU).
# Pinned to separate GPUs so co-tenant GPU work (LLM backends, TRT-LLM tests)
# on one device cannot queue behind the other stage.
export KB_EMBED_DEVICE=cuda:0
export KB_RERANKER_DEVICE=cuda:1

# --- RAM-first retrieval ---
export KB_USE_TANTIVY=true      # Rust tantivy BM25 (RAM, 50MB heap)
export KB_FAST_CACHE=true       # skip 2.7 s per-search fingerprint DB scan
export KB_SYNONYM_BEAM=5        # default beam width
export KB_DENSE_BACKEND=ram     # in-process cosine matrix (one batched encode); 'pgvector' = legacy SQL leg

# --- result cache (redis-test container, TTL 600 s, 150x cold->warm) ---
export KB_REDIS_URL=redis://127.0.0.1:16379/0
export KB_REDIS_TTL=600

# --- model resolution: repo ids are resolved offline-safe by
#     kb_manager/model_cache.py to offline-prep local dirs; HF env below is
#     only a fallback for anything not mirrored there. NOTE: HF_HUB_CACHE
#     must point at the *hub* subdirectory, NOT its parent (huggingface_hub
#     0.36 resolves models--* directly inside HF_HUB_CACHE). ---
export HF_HOME=/root/.cache/huggingface
export HF_HUB_CACHE=/root/.cache/huggingface/hub
export HF_HUB_OFFLINE=1

# --- localhost calls must never go through the squid proxy ---
export no_proxy=localhost,127.0.0.1
export NO_PROXY=localhost,127.0.0.1

KB_VENV=${KB_VENV:-/tmp/kb-venv}
KB_CODE=${KB_CODE:-/splunk-data/v1/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager}
export KB_VENV KB_CODE
