# Production pin — H200 (`v1.3.0`)

Operational snapshot of the **working production** stack on the H200 host.
Machine-readable twin: [`PRODUCTION_PIN.json`](PRODUCTION_PIN.json).

| Field | Value |
|-------|-------|
| Version | **`v1.3.0`** |
| Git tags | `v1.3.0`, `production`, `production-2026-11-12` |
| Image alias tags | `production`, `working`, `prod-2026-11-12` |
| Topology | Hybrid: host uvicorn for KB/orch/guard + Docker for WebUI/Jenkins/Postgres/Redis/embed |

Do **not** retag or rebuild these images for routine ops. Redeploy by digest / alias tag only.

## Exact image IDs (keep these)

| Role | Alias | Exact image ID |
|------|-------|----------------|
| WebUI (`dana-webui-prod` :13000) | `rag-webui:production` | `sha256:4e76b1243fabb207a25937387a43c0999cb9e00b99b0a4508092f5471c44b40e` |
| Jenkins (`dana-jenkins-prod`) | `dana-jenkins:production` | `sha256:46b04ab41fa71b05f2bb6a939a9b50f4c99b5ffe6799b42c798ea0178bdb674c` |
| Orchestrator image (CI build) | `rag-orchestrator:production` | `sha256:a865567e3a181ca2142528aaceca9dea994891a803e6299895985f4131b98237` |
| Guardrails image (CI build) | `rag-guardrails:production` | `sha256:0f3a49c6bfe2b72d6d4502622ba43728fe5be97981b386b9c43c8dd1b3d5af6a` |
| Embed (`rag-embed-prod-8001..8003`) | `rag-embed:production` | `sha256:6495b1aa7ab35e7cb019cdaff462881b1f432b01bc8d641296b919a5d6f4f4ff` |
| Postgres+pgvector | `pgvector/pgvector:production` | `sha256:a36250871de0833b8757561c72f2477ef1ddd1101afa4e617fb552e0de514c6b` |
| Redis | `redis:production` | `sha256:e7723ff73d963f5cc6d9c4643ea3d989527a402a319239054e9472a7fb9219a2` |

Same IDs are also tagged `:working` and `:prod-2026-11-12`.

### Embed note

Live containers still report `Image=sha256:b8a783f994857da754b5989742d3beea3b524bea146a3b645da4b84ccba9f001` with `Config.Image=local-h200:5000/rag-embed:b1d48b6`, but that layer digest is **missing from the local image store** (pruned). The pinned `rag-embed:production` tag is the surviving `b1d48b6` image (`6495b1aa…`). Do not `docker rm` the running embed containers until a verified re-pull/rebuild lands.

## Hybrid host processes (not containers)

| Service | Port | How it runs |
|---------|------|-------------|
| KB Manager | `:8000` | host venv uvicorn `kb_manager.web.app:app` |
| Orchestrator | `:8100` | host venv uvicorn `work_rag_orchestrator.api:create_app` |
| Guardrails | `:8200` | host venv uvicorn |
| LLM Manager / Gemma | `:9000` | host (`Work_RAG-Server-Setup`) |

WebUI nginx path: `chat.ics24.ir` → host `:13000` → `dana-webui-prod`.

## Recreate WebUI from the pin

```bash
docker run -d --name dana-webui-prod --restart unless-stopped \
  # …same flags as components/server-setup/deploy/recreate_dana_webui.sh…
  rag-webui:production
# or by digest:
#   rag-webui@sha256:4e76b1243fabb207a25937387a43c0999cb9e00b99b0a4508092f5471c44b40e
```

Prefer `bash components/server-setup/deploy/recreate_dana_webui.sh` after confirming it references `rag-webui:dana` / `:production`.

## Git component pins at cutover

Recorded in `PRODUCTION_PIN.json` under `git.submodules` (pre-pin HEAD was parent `de7fa3b`). After the `v1.3.0` commit, use:

```bash
git show v1.3.0:deploy/PRODUCTION_PIN.json
git submodule status
```
