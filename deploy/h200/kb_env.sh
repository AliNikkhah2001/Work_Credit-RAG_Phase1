# Shared environment for the KB manager (port 8000) on the H200 host.
export KB_DB_MODE=pgvector
export KB_DB_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/kb_manager
# GPU1 hosts TRT-LLM champion (~133 GiB); keep both retrieval models on GPU0.
export KB_EMBED_DEVICE=cuda:0
export KB_RERANKER_DEVICE=cuda:0
export KB_USE_TANTIVY=true
export KB_FAST_CACHE=true
export KB_SYNONYM_BEAM=5
export KB_DENSE_BACKEND=ram
export KB_REDIS_URL=redis://127.0.0.1:16379/0
export KB_REDIS_TTL=600
export HF_HOME=/root/.cache/huggingface
export HF_HUB_CACHE=/root/.cache/huggingface/hub
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export no_proxy=localhost,127.0.0.1
export NO_PROXY=localhost,127.0.0.1
export DANA_ENV=prod
export LLM_UPSTREAM_MODE=self_hosted
KB_VENV=${KB_VENV:-/splunk-data/v1/Work_RAG-Server-Setup/offline-prep/venv}
KB_CODE=${KB_CODE:-/splunk-data/production/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager}
export KB_VENV KB_CODE
