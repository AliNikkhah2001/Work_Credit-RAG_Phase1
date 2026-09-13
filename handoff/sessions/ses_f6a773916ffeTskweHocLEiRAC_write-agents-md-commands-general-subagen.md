# Write AGENTS.md + commands (@general subagent)

Session: `ses_f6a773916ffeTskweHocLEiRAC`
Messages: 9


## [USER]

Write agent operating docs for the RAG umbrella repo at /workspace/Work_Credit-RAG_Phase1 (you are on branch `release/v1`; your files WILL be committed by someone else — just write them).

First READ these for ground truth (do not guess): /workspace/Work_Credit-RAG_Phase1/README.md (full), /workspace/Work_Credit-RAG_Phase1/docs/RUNBOOK_VAST.md (full, incl. the 50713720 appendix), /workspace/Work_Credit-RAG_Phase1/compose.mvp.yml, /workspace/Work_Credit-RAG_Phase1/deploy/vast/start.sh, /workspace/Work_Credit-RAG_Phase1/.gitmodules.

Live deployment facts (verified 2026-09-12, instance 50713720, 1x RTX 3090):
- venvs: /tmp/kb-venv, /tmp/guard-venv, /tmp/orch-venv, /tmp/webui-venv (python3.11)
- Ports (0.0.0.0; gemma loopback-only): KB :8000 (pgvector KB_DB_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/kb_manager), guardrails :8200 (UPSTREAM_LLM_BASE_URL=http://127.0.0.1:18000/v1, MODEL=unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL), orchestrator :8100 (KB_BASE_URL :8000, GUARDRAILS_BASE_URL :8200, LANGFUSE_HOST :3001 + seeded keys in /tmp/opencode/langfuse.env), WebUI :13000 (backend :8100/v1), fallback collector :3000, real Langfuse v2 UI :3001, Studio API :2024, llama-server :18000 (binary /workspace/llama.cpp-src/build-cuda/bin/llama-server, --ctx-size 8192 --temp 0.2 --no-mmproj --jinja -ngl 999), postgres :5432
- Models cache /tmp/hf_clean (HF_HUB_CACHE + HF_HOME must BOTH point there; hub 1.x reads $HF_HOME/hub)
- Git: parent pins submodules to exact commits (gitlinks). Component fixes go on each repo's `vast-gemma4-migration`, pushed; parent records pins. Deployment-only material goes on parent `vast-deploy`/`release` branches. Never force-push. Never commit secrets (*.env, tokens, passwords) or generated artifacts (*.npz, __pycache__, *.log, venvs).
- Vast.ai constraints: unprivileged container (no docker); NAT ports fixed at creation → public access via SSH tunnels (`ssh -p <ssh_port> root@<ssh_host> -L 13000:localhost:13000 ...`).

Write these THREE files (plain markdown, concise, command-first, no fluff):

1. `/workspace/Work_Credit-RAG_Phase1/AGENTS.md` — root agent operating manual: repo map + ownership rule, service table (dir, venv, module, port, key env), standard workflows (health check, restart one service, full restart via deploy/vast/start.sh, e2e smoke test curls, view traces, Studio run), git rules above, Vast gotchas (phantom overlay dentries, HF cache layout, asyncpg loop bug fixed, langfuse v2 envelope), "never do" list.

2. `/workspace/Work_Credit-RAG_Phase1/deploy/vast/COMMANDS.md` — complete command reference, copy-pasteable: prerequisites (apt, venvs, postgres+pgvector, models), env exports, per-service start commands, health/ready checks, e2e curls (greeting, credit question, rails check, KB search), WebUI signup+chat, Langfuse inspect (jsonl + API + UI), Studio run, SSH tunnels, stop commands, troubleshooting (VRAM OOM → ctx 4096, HF offline miss → HF_HUB_CACHE, KB empty search → check loop fix).

3. `/workspace/
…[truncated]…


## [ASSISTANT]

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: read)

(tool: read)


## [ASSISTANT]

(tool: write)


## [ASSISTANT]

(tool: write)


## [ASSISTANT]

(tool: write)

(tool: write)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

Done. Only the 4 allowed files created, nothing else modified (`git status` shows just the 4 new files). Scripts are executable, syntax-checked.

- `AGENTS.md` — 131 lines
- `deploy/vast/COMMANDS.md` — 224 lines
- `deploy/vast/stop.sh` — 24 lines (executable)
- `deploy/vast/health.sh` — 33 lines (executable)

Ground truth used: `README.md`, `docs/RUNBOOK_VAST.md` (incl. 50713720 appendix), `compose.mvp.yml`, `deploy/vast/start.sh`, `.gitmodules`, plus `studio.sh`/`langfuse-v2.sh` for exact panel commands. On branch `release/v1`, files left uncommitted for someone else to commit.
