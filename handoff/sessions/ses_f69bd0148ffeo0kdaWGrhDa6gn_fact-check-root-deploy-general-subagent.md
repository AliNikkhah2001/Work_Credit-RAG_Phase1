# Fact-check root+deploy (@general subagent)

Session: `ses_f69bd0148ffeo0kdaWGrhDa6gn`
Messages: 5


## [USER]

You are Agent 2a (Technical Accuracy Auditor) in /workspace/Work_Credit-RAG_Phase1. Validate technical claims in README.md (root), deploy/docker/README.md, contracts/README.md, eval/README.md against reality.

Ground truth to check against: AGENTS.md (service table: ports 18000/8000/8200/8100/13000/3000/3001/2024, env vars, startup order `bash deploy/vast/start.sh`), deploy/vast/*.sh + *.md, contracts/*.json filenames, eval/*.py filenames, .gitmodules, compose.mvp.yml, components/tracing/app.py + observe.py endpoints (/observe, /studio, /api/observe/*, /api/studio/*).

For each README list: VERIFIED claims (with file:line evidence), INCORRECT claims (what it says vs what code/env shows), MISSING info. Pay attention to: ports, URLs, env var names, model IDs/paths, service names, startup commands, tunnel instructions, submodule branches.

Return ONLY compact structured lists. No file writes.


## [ASSISTANT]

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)


## [ASSISTANT]

(tool: glob)

(tool: glob)

(tool: glob)

(tool: read)

(tool: read)


## [ASSISTANT]

(tool: read)

(tool: read)

(tool: glob)

(tool: glob)


## [ASSISTANT]
