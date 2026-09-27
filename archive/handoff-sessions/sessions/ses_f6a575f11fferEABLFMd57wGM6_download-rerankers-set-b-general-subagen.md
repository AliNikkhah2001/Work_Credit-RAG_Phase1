# Download rerankers set B (@general subagent)

Session: `ses_f6a575f11fferEABLFMd57wGM6`
Messages: 6


## [USER]

Download HuggingFace reranker models to the shared cache. No repo changes, no service restarts.

Run with /tmp/kb-venv/bin/python and `cache_dir='/tmp/hf_clean'` via `snapshot_download`:
1. `jinaai/jina-reranker-v3`
2. `Qwen/Qwen3-Reranker-0.6B`
3. `Qwen/Qwen3-Reranker-4B`
If any id 404s, use `huggingface_hub.list_models(search=...)` to find the closest correct id, download it, and report the substitution.

For each report: local snapshot path + size (`du -sh`) + status. Retry once on failure. Keep concise.


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

Done — 3/3 downloaded to `/tmp/hf_clean` via `/tmp/kb-venv/bin/python` + `snapshot_download(cache_dir='/tmp/hf_clean')`. No 404s, no substitutions, no retries needed. No repo changes, no restarts.

1. `jinaai/jina-reranker-v3` — OK (attempt 1)
   - snapshot: `/tmp/hf_clean/models--jinaai--jina-reranker-v3/snapshots/d7d7e73b6ea138ced340b83865931b5dfb6c97aa`
   - size: `1.2G` (`du -shL` snapshot; `du -sh` snapshot alone shows 4.0K due to symlink blobs)

2. `Qwen/Qwen3-Reranker-0.6B` — OK (attempt 1)
   - snapshot: `/tmp/hf_clean/models--Qwen--Qwen3-Reranker-0.6B/snapshots/e61197ed45024b0ed8a2d74b80b4d909f1255473`
   - size: `1.2G`

3. `Qwen/Qwen3-Reranker-4B` — OK (attempt 1)
   - snapshot: `/tmp/hf_clean/models--Qwen--Qwen3-Reranker-4B/snapshots/22e683669bc0f0bd69640a1354a6d0aebcfeede5`
   - size: `7.6G`

