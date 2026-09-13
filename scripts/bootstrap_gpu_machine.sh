#!/usr/bin/env bash
# Bootstrap a fresh Vast GPU machine for the RAG stack + wave-2 GPU bench.
# Assumes: workspace dir copied to $WORKDIR (default /workspace/Work_Credit-RAG_Phase1),
#   /tmp/opencode helpers + /tmp/hf_clean optionally copied (else re-downloaded).
# Run as root. Idempotent-ish: safe to re-run.
set -euo pipefail

WORKDIR="${WORKDIR:-/workspace/Work_Credit-RAG_Phase1}"
HFDIR="${HFDIR:-/tmp/hf_clean}"
PGPASS="${PGPASS:-postgres}"

echo "### 1. system deps"
apt-get update -qq && apt-get install -y -qq python3.11-venv python3-pip postgresql-14 \
  postgresql-14-pgvector fuser curl jq git sqlite3 > /dev/null
service postgresql start || pg_ctlcluster 14 main start

echo "### 2. postgres roles/dbs"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='postgres'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE ROLE postgres LOGIN SUPERUSER PASSWORD '$PGPASS';"
for db in kb_manager langfuse; do
  sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$db'" | grep -q 1 \
    || sudo -u postgres createdb -O postgres "$db";
done
sudo -u postgres psql -d kb_manager -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo "### 3. HF cache layout"
mkdir -p "$HFDIR"
export HF_HOME="$HFDIR" HF_HUB_CACHE="$HFDIR"

echo "### 4. venvs (kb-venv gets CUDA torch for wave-2 GPU)"
for v in kb-venv guard-venv orch-venv webui-venv; do
  [ -x "/tmp/$v/bin/python" ] || python3.11 -m venv "/tmp/$v";
done
/tmp/kb-venv/bin/pip install -q --upgrade pip
/tmp/kb-venv/bin/pip install -q torch --index-url https://download.pytorch.org/whl/cu121
/tmp/kb-venv/bin/pip install -q -e "$WORKDIR/components/knowledgebase/kb-manager"
/tmp/guard-venv/bin/pip install -q -e "$WORKDIR/components/guardrails"
/tmp/orch-venv/bin/pip install -q -e "$WORKDIR/components/orchestrator"
/tmp/kb-venv/bin/python -c "import torch; assert torch.cuda.is_available(); print('CUDA OK:', torch.cuda.get_device_name(0))"

echo "### 5. models (skip if HFDIR was copied)"
if [ -d "$HFDIR/models--Qwen--Qwen3-Reranker-4B" ]; then
  echo "rerankers already cached"
else
  /tmp/kb-venv/bin/pip install -q huggingface_hub
  /tmp/kb-venv/bin/huggingface-cli download Qwen/Qwen3-Reranker-0.6B \
    Qwen/Qwen3-Reranker-4B BAAI/bge-reranker-v2-gemma \
    cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 \
    sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
fi

echo "### 6. KB data (needs kb_1405.db or a pg_dump from the old machine)"
echo "If you have a dump: pg_restore into kb_manager, else run the xlsx ingest per kb-manager README."
echo "Then verify: PGPASSWORD=$PGPASS psql -h 127.0.0.1 -U postgres -d kb_manager -tAc 'SELECT count(*) FROM chunks;'  # want 2077"

echo "### 7. next steps"
echo "  bash $WORKDIR/deploy/vast/start.sh   # full stack (Gemma needs its GGUF!)"
echo "  bash $WORKDIR/deploy/vast/wave2_gpu.sh  # stop llama-server first on 24GB cards"
