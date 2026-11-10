# Jenkins on laptop (same pipeline later on H200)

## Start

```bash
docker compose -f deploy/jenkins/docker-compose.yml up -d
open http://127.0.0.1:8085
```

## Multibranch job

1. Install suggested plugins + Docker Pipeline.
2. New Item → Multibranch Pipeline → point at GitHub `Work_Credit-RAG_Phase1`.
3. Credentials: GitHub PAT + `OPENROUTER_API_KEY` / `LITELLM_MASTER_KEY` as secret text.
4. Branch discover: `develop`, `main`, `feature/*`.

## Branch mapping (Jenkinsfile)

| Branch | Action |
|---|---|
| `develop` | Build images → deploy `compose.stage.yml` (alt ports) |
| `main` | Build images → manual approval → `compose.prod-sim.yml` |
| `feature/*` | Build + lint only |

## H200 lift-and-shift

Copy this compose + root `Jenkinsfile`. Change only registry host and set `UPSTREAM_LLM_BASE_URL` to Manager/Gemma (drop LiteLLM or keep as optional).
