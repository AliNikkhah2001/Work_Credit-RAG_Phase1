# Continuation prompt — paste into a new opencode session on the bigger GPU machine

You are continuing the Persian Credit RAG Phase-1 project. Context files (read first):

1. `handoff/README.md` — what is where.
2. `docs/WAVE2_GPU_RUNBOOK.md` — VRAM math, machine sizing, wave-2 procedure.
3. `AGENTS.md` — repo map, service table, workflows, git rules, gotchas.
4. `handoff/sessions/ses_f6b058c02ffej8lpFUThWHsld0_find-chat-history-for-rag-agent-project.md`
   — full transcript of the session that did all of the below (1327 msgs total
   across 35 sessions, indexed in `handoff/sessions/INDEX.md`).

## State where we left off (2026-09-13, all pushed to GitHub)

- Parent `main` + KB `master` + orch/guard/setup `main` are merged and in sync.
  Never force-push. Never commit secrets / `*.npz` / logs / venvs.
- Services ran on old box: Gemma `:18000` (loopback), KB `:8000`, guard `:8200`,
  orch `:8100`, WebUI `:13000`, collector `:3000`, Langfuse v2 `:3001`,
  Studio `:2024`, PG `:5432` with 2077 chunks.
- Wave 1 (CPU, 800 remapped queries in `handoff/bench/eval_remapped.json`):
  MiniLM MRR 0.493, MiniLM-p30 0.495, BGE-m3 0.496 → **0.496 is the bar to beat**.
  Jina-v3 excluded (classification head fails to load under transformers 5).
- KB `master` HEAD contains: reranker registry (`KB_RERANKER_MODEL` /
  `KB_RERANK_POOL`), RRF fusion, device-aware loading, HyDE, keyword_boost,
  pad-token fallbacks (Jina/Qwen), `@dataclass` fix on `RerankerConfig`.
- Fresh/old PG databases need `ALTER TABLE chunks ADD COLUMN embedding vector(384)`
  (see runbook); fresh `create_all` DBs already have it.

## Your task now

1. Verify the stack on THIS machine (`bash deploy/vast/health.sh`, then the E2E
   smokes in `AGENTS.md` §3). Log to `handoff/bench/validation_<date>.log`.
2. Re-run the 5-query smoke:
   `bench_backbone.py qwen06-smoke Qwen/Qwen3-Reranker-0.6B 15 handoff/bench/smoke5.json …`
   (expect non-zero hit_rate; `RerankerConfig() takes no arguments` = stale checkout).
3. Run `bash deploy/vast/wave2_gpu.sh` (qwen06 → qwen4b → bge-gemma, full 800,
   pool 15, CUDA). On ≤24 GB cards stop `llama-server` first (bench is
   in-process and never touches `:18000`).
4. Aggregate (`handoff/scripts/aggregate_bench.py`), compare vs the 0.496 bar,
   write `handoff/bench/BENCH_WAVE2_REPORT.md`, update KB + parent READMEs,
   commit + push (submodules first, then parent pins).
5. Recommendation to converge on: keep MiniLM default unless a heavy beats 0.496
   with acceptable GPU latency; pool 30 showed no meaningful gain in wave 1.

Environment rules: unprivileged container = no docker; `HF_HOME` and
`HF_HUB_CACHE` both to the model cache; `KB_DB_URL` must be set explicitly.
KB models: Qwen3-0.6B/4B, bge-gemma-2B, MiniLM, BGE-m3, Jina-v3, GTE, MiniCPM —
see runbook for Persian-support notes and known blockers (GTE rope bug,
MiniCPM transformers-5, Jina head load).
