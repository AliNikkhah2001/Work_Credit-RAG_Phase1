# Dana compose stack (laptop → H200)

## Profiles

| File | Role |
|---|---|
| `compose.base.yml` | Shared: postgres, redis, kb, guardrails, orchestrator, tracing, webui |
| `compose.local.yml` | LiteLLM→OpenRouter, CPU embed/rerank, loopback ports |
| `compose.stage.yml` | Alt ports for Jenkins `develop` |
| `compose.prod-sim.yml` | Standard ports for Jenkins `main` (laptop prod-sim) |

## Quick start (laptop)

```bash
cp deploy/compose/.env.example deploy/compose/.env
# set OPENROUTER_API_KEY=

docker compose -f deploy/compose/compose.base.yml \
  -f deploy/compose/compose.local.yml \
  --env-file deploy/compose/.env \
  up -d --build
```

Health: `curl -s localhost:8000/health`; chat: `localhost:8100/v1/chat/completions`; UI: `localhost:13000`.

## Prod cutover (H200)

Same images. Change only:

- `UPSTREAM_LLM_BASE_URL=http://llm-manager:9000/v1` (or Gemma)
- `KB_EMBED_DEVICE=cuda` / `KB_RERANKER_DEVICE=cuda`
- Drop LiteLLM service (or keep as optional gateway)
