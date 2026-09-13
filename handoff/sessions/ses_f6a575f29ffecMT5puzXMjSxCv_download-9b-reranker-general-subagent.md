# Download 9B reranker (@general subagent)

Session: `ses_f6a575f29ffecMT5puzXMjSxCv`
Messages: 10


## [USER]

Download ONE large HuggingFace reranker model to the shared cache. No repo changes, no service restarts.

Run with /tmp/kb-venv/bin/python and `cache_dir='/tmp/hf_clean'`:
`snapshot_download('BAAI/bge-reranker-v2-gemma', cache_dir='/tmp/hf_clean')`
This is ~18GB — it will take several minutes even on a fast link; wait for it (poll progress, do not abort early). If that exact id 404s, use `huggingface_hub.list_models(search='bge-reranker-v2-gemma')` to find the correct id and download it; report what you chose.

Report: local snapshot path + total size (`du -sh`) + status. Retry once on failure. Keep concise.


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

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

Done — exact id `BAAI/bge-reranker-v2-gemma` worked, no fallback needed, no retry needed. No repo changes, no restarts.

- Snapshot: `/tmp/hf_clean/models--BAAI--bge-reranker-v2-gemma/snapshots/1787044f8b6fb740a9de4557c3a12377f84d9e17` (17/17 files, verified resolvable via second `snapshot_download` call)
- Size: `9.4G` for `models--BAAI--bge-reranker-v2-gemma` (`du -sh`; blobs 4.6G+4.7G shards); full `/tmp/hf_clean` now `58G` total (other entries downloading concurrently by others)
- Status: complete, fresh download via `/tmp/kb-venv/bin/python` with `cache_dir='/tmp/hf_clean'`

