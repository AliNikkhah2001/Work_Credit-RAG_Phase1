# Finish wave-1 bench + aggregate (@general subagent)

Session: `ses_f662eaa64ffeVRZClGRfuksXF6`
Messages: 10


## [USER]

You are finishing a CPU reranker-benchmark wave on an unprivileged Vast.ai container (NO docker, NO pkill, NO service restarts — production services run on ports 18000/8000/8200/8100/13000/3001/2024; leave them alone).

CONTEXT: Persian Credit RAG, KB = 2077 chunks in Postgres. Four in-process benchmark workers score 800 remapped QA pairs (`/tmp/opencode/eval_remapped.json`, answer-grounded golds, ~7 gold/query) with top_k=5. Three workers are DONE (800/800): minilm, minilm-p30, bgem3. The jina worker (PID ~115332) is at ~575/800. Result files: `/tmp/opencode/bench_minilm.json`, `bench_minilm-p30.json`, `bench_bgem3.json`, `bench_jina.json` (partial until done). Worker script: `/tmp/opencode/bench_backbone.py`. Aggregator: `/tmp/opencode/aggregate_bench.py`. Venv: `/tmp/kb-venv/bin/python`. Env needed: `KB_DB_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/kb_manager" HF_HOME=/tmp/hf_clean HF_HUB_CACHE=/tmp/hf_clean HF_HUB_OFFLINE=1`.

TASKS:
1. Poll jina progress every ~5 min (`tail` its log `/tmp/opencode/bench_jina.log`, unbuffered `-u` so progress lines `[jina] N/800` appear). Wait until `[jina] 800/800` or the process exits. Be patient — it can take 1-2h. Use sleep-based polling, stay CPU-light.
2. When all 4 JSONs are complete (each has `"done": true` and 800 queries), run the aggregator: `/tmp/kb-venv/bin/python /tmp/opencode/aggregate_bench.py` (check its --help/usage first; it reads bench_*.json and writes a comparison). If the aggregator script has issues, compute the comparison manually: for each file print variant, hit_rate, top1_hit_rate, mrr, avg_rank, avg rerank latency.
3. Write a concise results report to `/tmp/opencode/BENCH_WAVE1_REPORT.md` with: method (dataset, golds, top_k, pools: minilm/minilm-p30 pool 15/30, bgem3/jina pool 30), per-variant metrics table, latency table, 3-5 bullet takeaways (which backbone wins on MRR/latency tradeoff, pool-size effect minilm vs minilm-p30), and caveats (CPU-only timing, answer-grounded golds).
4. OPTIONAL wave-2 only if time permits AND jina finished AND load average < 8: run qwen06 on the 200-query subset `/tmp/opencode/strat200.json` via bench_backbone.py with pool 15 and output `/tmp/opencode/bench_qwen06.json`. If load is high, SKIP wave-2 and say so in the report. NEVER launch qwen4b/gemma-4B full runs (too slow on CPU).

RULES: read-only w.r.t. services and repos — do NOT git commit, do NOT edit repo files, do NOT kill processes (except: if jina process is dead but JSON incomplete, report it, don't relaunch). Write only to /tmp/opencode/.

RETURN: the full metrics table, the report path, and whether wave-2 qwen06 was run or skipped (+why).


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)

(tool: read)


## [ASSISTANT]

(tool: read)

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
