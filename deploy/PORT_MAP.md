# Reserved port map (H200 hybrid)

Fixed allocations for production and stage. Do **not** bind services outside these ranges without updating this file and the health-report probe list.

## Forbidden

| Port | Reason |
|------|--------|
| **8089** | Retired `rag-public` Cloudflare-tunnel nginx listener — must stay unused |

## Production (hybrid host)

| Port | Service | Bind |
|------|---------|------|
| 8000 | KB Manager | `0.0.0.0` (host uvicorn) |
| 8001–8003 | Embed workers | docker |
| 8080–8084 | Gemma backends | host supervisor |
| 8085 | Jenkins UI | `127.0.0.1` |
| 8088 | nginx gateway (`chat.ics24.ir`) | `0.0.0.0` |
| 8100 | Orchestrator | host uvicorn |
| 8200 | Guardrails | host uvicorn |
| 9000 | LLM Manager | host |
| 13000 | WebUI | `127.0.0.1` + LAN IPs |
| 13002 | Tracing | `127.0.0.1` |
| 15432 | Compose Postgres (optional) | `127.0.0.1` |
| 16379 | Redis | `127.0.0.1` |
| 50000 | Jenkins agent | `127.0.0.1` |
| 13300–13307 | **Prod spare / ops** | reserved unused |

System Postgres+pgvector for live KB may also use host `:5432` (`pgvector-kb-prod`).

## Stage (`compose.stage.yml` / project `dana-stage`)

| Port | Service |
|------|---------|
| 14000 | LiteLLM |
| 18000 | KB |
| 18100 | Orchestrator |
| 18200 | Guardrails |
| 13100 | WebUI |
| 13001 | Tracing |
| 25432 | Postgres |
| 26379 | Redis |
| 18300–18307 | **Stage spare** |

## Jenkins exclusive

`8085` and `50000` are Jenkins-only. Dynamic llama backends must **not** scan `8085–8100` in a way that steals Jenkins' port; Gemma stays on `8080–8084`, orch on `8100`.

## Docker bridge CIDRs

See [`gateway/WAF_CIDR_CLASH.md`](gateway/WAF_CIDR_CLASH.md).

| Network | Subnet |
|---------|--------|
| `jenkins_default` | `172.30.100.0/24` |
| `dana-stage_rag` | `172.30.101.0/24` |
| compose `rag` (base) | `172.30.110.0/24` |
