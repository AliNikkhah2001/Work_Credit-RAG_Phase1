# Download rerankers set A (@general subagent)

Session: `ses_f6a575f42ffe8YMbPSYvlfdqbA`
Messages: 8


## [USER]

Download HuggingFace reranker models to the shared cache. No repo changes, no service restarts.

Run: `/tmp/kb-venv/bin/python -c "from huggingface_hub import snapshot_download; ..."` with `cache_dir='/tmp/hf_clean'` (default HF_HOME is fine too, but pass cache_dir explicitly). Models for YOUR track:
1. `BAAI/bge-reranker-v2-m3`
2. `Alibaba-NLP/gte-multilingual-reranker-base`
3. `BAAI/bge-reranker-v2-minicpm-layerwise` — if this exact id 404s, list candidates via `huggingface_hub.list_models(search='bge-reranker-v2-minicpm')` and download the closest layerwise MiniCPM reranker instead; report what you chose.

For each: run snapshot_download, then report local snapshot path + total size (`du -sh`). If a download fails, retry once, then report the error and move on. Keep concise: model → path → size → status.


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

Done, no repo changes / no restarts. `cache_dir='/tmp/hf_clean'`, `/tmp/kb-venv` (hub 1.31.0):

1. `BAAI/bge-reranker-v2-m3` → `/tmp/hf_clean/models--BAAI--bge-reranker-v2-m3/snapshots/953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` → 2.2G → OK (first try)
2. `Alibaba-NLP/gte-multilingual-reranker-base` → `/tmp/hf_clean/models--Alibaba-NLP--gte-multilingual-reranker-base/snapshots/8215cf04918ba6f7b6a62bb44238ce2953d8831c` → 601M → OK (first try)
3. `BAAI/bge-reranker-v2-minicpm-layerwise` → `/tmp/hf_clean/models--BAAI--bge-reranker-v2-minicpm-layerwise/snapshots/47b5332b296c4d8cb6ee2c60502cc62a0d708881` → 11G → OK (first try, exact id existed — no fallback needed)

Note: plain `du -sh <snapshot>` shows 4.0K (symlinks to blobs); sizes above are `du -shL` (followed) / full `models--*` dir — same values.
