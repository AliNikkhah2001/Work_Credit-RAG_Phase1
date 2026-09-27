# Fact-check guardrails+setup (@general subagent)

Session: `ses_f69bd0067ffeYkQj7BGbueJNdi`
Messages: 5


## [USER]

You are Agent 2d (Technical Accuracy Auditor) for components/guardrails/README.md, components/guardrails/kb/README.md, components/server-setup/README.md, components/server-setup/docs/README.md in /workspace/Work_Credit-RAG_Phase1. Validate against: guardrails src/work_rag_guardrails/ (api.py ports, service.py stages, observability.py, pyproject.toml), guardrails/kb/ contents, server-setup key files (do NOT read whole tree — check only files the READMEs reference: llm_inference_manager/, deploy/, docs/ structure).

Check: ports (8200), UPSTREAM_LLM_* env, rule/policy names, check stages (input/output), model IDs, which server-setup parts are active on the Vast host vs legacy/docker-only (AGENTS.md: gemma-manager never launched, no docker on unprivileged host), outdated references.

Return ONLY: VERIFIED (file:line), INCORRECT (says vs is), MISSING. Compact. No file writes.


## [ASSISTANT]

(tool: read)

(tool: read)

(tool: read)

(tool: read)


## [ASSISTANT]

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)


## [ASSISTANT]

(tool: read)

(tool: read)

(tool: read)

(tool: read)


## [ASSISTANT]
