# Agent State — GitHub Pages extract (short)

Sources: `agent-state/docs/{index,high-level,technical}.html`.

## Role

Separate submodule (`ICS_ChatBot_agent-state`) for agent working files — context, todos, archived sessions, skills, architecture, coding standards, insights — so production repos stay free of agent scratch noise. No runtime libraries; markdown only. Split dated **v1.0.0 / 2026-10-28**.

## Where to look

| Need | Path |
|---|---|
| Mission / context | `context/context.md` |
| Todos | `context/todo.md` |
| Session archives | `history/archive/` |
| Skills | `skills/` |
| Architecture | `architecture.md` |
| Coding standards | `coding-standards.md` |
| Insights / decisions | `insights.md` |
| Git / PR rules | `git-workflow.md` |
| File map | `FILE_MAP.md` |
| New-machine onboard | `onboarding.md` |

## Report-useful rules echoed from Pages

- Branch: `feature/*` → PR → `develop` → `main`/`master`; never direct push to protected branches; never force-push
- Never commit secrets / `*.npz` / logs / venvs; never `pkill python` (use `deploy/vast/stop.sh`)
- Set **both** `HF_HOME` and `HF_HUB_CACHE`; always include `request_id` in Studio runs
- httpx localhost: `trust_env=False` (Squid); do not mix `asyncio.to_thread` with asyncpg
- Notable insights called out on technical page: dense `_ensure_model` (not `.model`), entity `trim_supplemental` budget, Guardrails `finish_reason="length"` not `"error"`, clarify short-circuit on entity evidence
