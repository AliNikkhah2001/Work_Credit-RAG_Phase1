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

3. `/workspace/Work_Credit-RAG_Phase1/deploy/vast/stop.sh` + `health.sh` — executable bash: stop.sh kills our uvicorn/llama/webui processes by port (8000/8100/8200/13000/3000/2024/18000) safely (fuser -k or pkill -f with exact patterns, never `pkill python`); health.sh curls all /health + /ready endpoints and pg count, exits non-zero on failure.

Constraints: create ONLY those files (AGENTS.md, deploy/vast/COMMANDS.md, deploy/vast/stop.sh, deploy/vast/health.sh). Do NOT modify anything else. chmod +x the scripts. Report file paths + line counts when done.


## [ASSISTANT]

(step-start: {"snapshot": "c025d758c3b9fdd5a3c596f65c07410b47393411", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "c025d758c3b9fdd5a3c596f65c07410b47393411", "type": "step-finish", "tokens": {"total": 7642, "input": 7191, "output": 327, "reasoning": 11, "cache": {"write": 0, "read": 113}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c025d758c3b9fdd5a3c596f65c07410b47393411", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "c025d758c3b9fdd5a3c596f65c07410b47393411", "type": "step-finish", "tokens": {"total": 27539, "input": 20089, "output": 114, "reasoning": 55, "cache": {"write": 0, "read": 7281}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c025d758c3b9fdd5a3c596f65c07410b47393411", "type": "step-start"})

(reasoning: )

(tool: read)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "c025d758c3b9fdd5a3c596f65c07410b47393411", "type": "step-finish", "tokens": {"total": 27965, "input": 512, "output": 131, "reasoning": 73, "cache": {"write": 0, "read": 27249}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c025d758c3b9fdd5a3c596f65c07410b47393411", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: write)

(step-finish: {"reason": "tool-calls", "snapshot": "8d4f2a2c37de899911af63b26ae9a834f5667f4b", "type": "step-finish", "tokens": {"total": 32512, "input": 1857, "output": 2779, "reasoning": 115, "cache": {"write": 0, "read": 27761}}, "cost": 0})

(patch: {"type": "patch", "hash": "c025d758c3b9fdd5a3c596f65c07410b47393411", "files": ["/workspace/Work_Credit-RAG_Phase1/AGENTS.md"]})


## [ASSISTANT]

(step-start: {"snapshot": "8d4f2a2c37de899911af63b26ae9a834f5667f4b", "type": "step-start"})

(tool: write)

(step-finish: {"reason": "tool-calls", "snapshot": "16286489030f0ef261b0a06843455ddaeb2646f6", "type": "step-finish", "tokens": {"total": 39016, "input": 29244, "output": 3771, "reasoning": 0, "cache": {"write": 0, "read": 6001}}, "cost": 0})

(patch: {"type": "patch", "hash": "8d4f2a2c37de899911af63b26ae9a834f5667f4b", "files": ["/workspace/Work_Credit-RAG_Phase1/deploy/vast/COMMANDS.md"]})


## [ASSISTANT]

(step-start: {"snapshot": "16286489030f0ef261b0a06843455ddaeb2646f6", "type": "step-start"})

(tool: write)

(tool: write)

(step-finish: {"reason": "tool-calls", "snapshot": "8652cfa64beb8205f758092887fc26716d977601", "type": "step-finish", "tokens": {"total": 40294, "input": 3856, "output": 1253, "reasoning": 0, "cache": {"write": 0, "read": 35185}}, "cost": 0})

(patch: {"type": "patch", "hash": "16286489030f0ef261b0a06843455ddaeb2646f6", "files": ["/workspace/Work_Credit-RAG_Phase1/deploy/vast/health.sh", "/workspace/Work_Credit-RAG_Phase1/deploy/vast/stop.sh"]})


## [ASSISTANT]

(step-start: {"snapshot": "8652cfa64beb8205f758092887fc26716d977601", "type": "step-start"})

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "4c0aa0bd678d7c1b33f9afca59c0a650f3cdef2e", "type": "step-finish", "tokens": {"total": 40481, "input": 1317, "output": 139, "reasoning": 0, "cache": {"write": 0, "read": 39025}}, "cost": 0})

(patch: {"type": "patch", "hash": "8652cfa64beb8205f758092887fc26716d977601", "files": ["/workspace/Work_Credit-RAG_Phase1/deploy/vast/health.sh", "/workspace/Work_Credit-RAG_Phase1/deploy/vast/stop.sh"]})


## [ASSISTANT]

(step-start: {"snapshot": "4c0aa0bd678d7c1b33f9afca59c0a650f3cdef2e", "type": "step-start"})

(reasoning: )

Done. Only the 4 allowed files created, nothing else modified (`git status` shows just the 4 new files). Scripts are executable, syntax-checked.

- `AGENTS.md` — 131 lines
- `deploy/vast/COMMANDS.md` — 224 lines
- `deploy/vast/stop.sh` — 24 lines (executable)
- `deploy/vast/health.sh` — 33 lines (executable)

Ground truth used: `README.md`, `docs/RUNBOOK_VAST.md` (incl. 50713720 appendix), `compose.mvp.yml`, `deploy/vast/start.sh`, `.gitmodules`, plus `studio.sh`/`langfuse-v2.sh` for exact panel commands. On branch `release/v1`, files left uncommitted for someone else to commit.

(step-finish: {"reason": "stop", "snapshot": "4c0aa0bd678d7c1b33f9afca59c0a650f3cdef2e", "type": "step-finish", "tokens": {"total": 40768, "input": 274, "output": 181, "reasoning": 8, "cache": {"write": 0, "read": 40305}}, "cost": 0})
