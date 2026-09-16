# Handoff — opencode history + wave results (branch `opencode-history`)

Exported 2026-09-16 from Vast instance 50713720 (RTX 3090 24 GB).
Git: parent `main` (this commit), KB `master`, orch/guard/setup `main`.

## Contents

- `CONTINUE.md` — **paste this into a fresh opencode session on the new machine.**
- `sessions/` — all 40 opencode sessions (1857 messages) as markdown:
  `sessions/INDEX.md` lists them. Main session is
  `ses_f6b058c02ffej8lpFUThWHsld0_*.md`. Secrets redacted (verified: no
  `ghp_` / `sk-lf` / `pk-lf` / `Langfuse-Admin-*` literals remain).
- `db/opencode-2026-09-16.db` — full raw opencode SQLite backup (VACUUMed,
  314 MB, **Git LFS**) for exact restore:
  `cp db/opencode-2026-09-16.db ~/.local/share/opencode/opencode.db`.
- `bench/` — wave-1 + wave-2 result JSONs (`bench_minilm*.json`,
  `bench_bgem3.json`, `bench_jina.json`, `bench_qwen*.json`,
  `bench_bgemma25.json`, `e2e_*.json`), screens, `eval_remapped.json`
  (800 answer-grounded queries), `validation_2026-09-13.log` (17/17 PASS).
- `scripts/` — `bench_backbone.py`, `aggregate_bench.py`, `remap_gold.py`,
  `bench_wave2.sh`, helpers.

## Deliberately NOT included (too big / secret)

- `/tmp/hf_clean` (58 GB models) → re-download per `docs/WAVE2_GPU_RUNBOOK.md` §5,
  or `rsync` it across.
- `/tmp/opencode/langfuse.env`, `parent-git/` (116 MB stale mirror).

## New-machine order

1. Copy this repo (it has everything above) + optionally `/tmp/hf_clean`.
2. `bash scripts/bootstrap_gpu_machine.sh`
3. Restore the 2077-chunk PG (`kb_manager`) + run the embedding-column ALTER
   (both in `docs/WAVE2_GPU_RUNBOOK.md`).
4. `bash deploy/vast/start.sh`, then `bash deploy/vast/wave2_gpu.sh`.
5. Paste `handoff/CONTINUE.md` into opencode and continue.
