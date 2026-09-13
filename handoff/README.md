# Handoff — move to a bigger GPU machine and run wave 2

Exported 2026-09-13 from Vast instance 50713720 (RTX 3090 24 GB).
Git: parent `main` (this commit), KB `master`, orch/guard/setup `main`.

## Contents

- `CONTINUE.md` — **paste this into a fresh opencode session on the new machine.**
- `sessions/` — all 35 opencode sessions (1327 messages) as markdown:
  `sessions/INDEX.md` lists them. Main session is
  `ses_f6b058c02ffej8lpFUThWHsld0_*.md`. Secrets redacted.
- `bench/` — wave-1 result JSONs (`bench_minilm.json`, `bench_minilm-p30.json`,
  `bench_bgem3.json`, `bench_jina.json` partial), screens, `eval_remapped.json`
  (800 answer-grounded queries), `validation_2026-09-13.log` (17/17 PASS).
- `scripts/` — `bench_backbone.py`, `aggregate_bench.py`, `remap_gold.py`,
  `bench_wave2.sh`, helpers.

## Deliberately NOT included (too big / secret)

- `/tmp/hf_clean` (58 GB models) → re-download per `docs/WAVE2_GPU_RUNBOOK.md` §5,
  or `rsync` it across.
- `~/.local/share/opencode/opencode.db` (128 MB, over GitHub's 100 MB file
  limit) → the `sessions/` exports are its readable equivalent.
- `/tmp/opencode/langfuse.env`, `parent-git/` (116 MB stale mirror).

## New-machine order

1. Copy this repo (it has everything above) + optionally `/tmp/hf_clean`.
2. `bash scripts/bootstrap_gpu_machine.sh`
3. Restore the 2077-chunk PG (`kb_manager`) + run the embedding-column ALTER
   (both in `docs/WAVE2_GPU_RUNBOOK.md`).
4. `bash deploy/vast/start.sh`, then `bash deploy/vast/wave2_gpu.sh`.
5. Paste `handoff/CONTINUE.md` into opencode and continue.
