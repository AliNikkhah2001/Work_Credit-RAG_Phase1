# Work Credit RAG — deep reference

## Decision log (intended behavior)

From `agent-state/insights.md` + code review 2026-11-09:

| # | Decision | Code reality on tips |
|---|---|---|
| 1 | Use `_ensure_model` / `_encode`, never `dense.model` | **KB tip still uses `hasattr(dense,'model')` — FIX NEEDED** |
| 2 | Embed entity lists with title+description | Pipeline must pass embedder |
| 3 | `trim_supplemental` + ~4KB budgets | Present in orchestrator `retrieve.py` / `build_context.py` |
| 4 | Guardrails `finish_reason="length"` | Keep when touching generate path |
| 5 | Clarify short-circuits on entity evidence | Present in `graph.should_clarify` |
| 6 | Code-token weighting in trim | Present in `trim_supplemental` |
| 7 | `/search/supplement` thr 0.4 | **Route missing on KB tip — restore** |

## Ports

| Service | Port | Notes |
|---|---|---|
| Gemma | 18000 | loopback only |
| KB | 8000 | |
| Orchestrator | 8100 | |
| Guardrails | 8200 | |
| Manager (H200) | 9000 | |
| Embeds | 8001–8003 | e5 / bge-m3 / MiniLM |
| Collector / Langfuse | 3000 / 3001 | |
| Studio | 2024 | need `request_id` |
| WebUI | 13000 | |

## Hosts

- **Vast RTX 3090**: `deploy/vast/start.sh`, no Docker, HF `/tmp/hf_clean`  
- **H200 ai-gpu1**: `/splunk-data/v1/Work_RAG-Server-Setup`, proxy `192.168.203.2:3128`, manager `:9000`

## OpenCode sessions recovered

1. Aug 2026 — H200 runbook + manager + OpenCode provider (`server-setup/.opencode`) — done  
2. Aug 2026 — DeepSeek-V4 TileLang on H200 — paused  
3. Sep 2026 — 142-issue audit plan — backlog  
4. Oct 2026 — entity supplement / context window work (insights) — partially missing on remote tips  
5. Nov 2026 — Cursor laptop onboard  

## Deploy smoke

```bash
bash deploy/vast/health.sh
# E2E Persian smoke from AGENTS.md
```
