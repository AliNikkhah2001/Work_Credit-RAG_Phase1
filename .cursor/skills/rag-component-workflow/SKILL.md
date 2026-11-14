---
name: rag-component-workflow
description: >-
  Executes the correct submodule + PR workflow for Work Credit RAG component
  changes (KB, orchestrator, guardrails, server-setup). Use when editing
  production code, advancing gitlinks, or the user asks how to change a
  component safely.
---

# RAG component change workflow

## Rule

Never edit component source “as if” it belongs to the parent tree only. Always commit in the submodule repo first.

## Steps

1. Identify owner from path under `components/`
2. In that submodule:
   - Update from remote tip of tracking branch (`master` for KB, else `main`)
   - Branch `feature/...` or `fix/...` from `develop` when it exists, else from default branch
3. Implement + verify:
   - KB: `pytest` under `kb-manager/`; `py_compile` touched modules
   - Orchestrator/guardrails: package tests under `tests/`
   - Deploy: prefer `bash deploy/vast/health.sh` when stack is up
4. Conventional commit in submodule; open PR → develop/main
5. After merge, in parent: `git add components/<name>` + `chore: advance <name> submodule`
6. Do not force-push; do not commit secrets

## Localhost HTTP

Always `trust_env=False` on httpx to localhost behind Squid.

## Stop/start

- Stop: `bash deploy/vast/stop.sh` (port-scoped)
- Start: `bash deploy/vast/start.sh`
- Never `pkill python`
