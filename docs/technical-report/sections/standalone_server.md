# Server Setup, Model Serving, and Scaling

## Section summary

Work Credit RAG runs on the self-hosted H200 lab server (`ai-gpu1`, 2× H200 NVL, about 281 GiB of VRAM) under `/splunk-data/v1/Work_RAG-Server-Setup`. The LLM Inference Manager on `:9000` fronts a multi-backend fleet—llama.cpp Gemma replicas on `8080–8084`, TensorRT-LLM champion traffic on `:8010`, embedding workers on `8001–8003`, and a standalone DeepSeek-V4-Flash wrapper on `:9001` that stays outside `MODEL_REGISTRY`. Redis, vector stores, and Open WebUI ride a Docker publish surface (`13000`, `15432`, `16379`, and the monitoring ports beside them). Corporate egress goes through Squid at `192.168.203.2:3128`, which makes `httpx` `trust_env=False` on localhost calls a hard correctness requirement. Containerization follows a five-phase cutover: phases 1–3 leave production listeners alone, phase 4 swaps each service onto its live port, and phase 5 retires host virtualenvs after a day of stability. Capacity planning follows `docs/plans/million-user-scale-plan.md`. Measured generation throughput on the H200 (history `013`) shows TensorRT-LLM BF16 continuous batching reaching ~3874 aggregate tok/s at concurrency 128 versus a flat ~58 tok/s llama.cpp Q4 single-slot path—about **67×** aggregate under the same Persian decode workload.

## H200 lab server

Docker serves the data plane, Jenkins can act as root, and the two GPUs run concurrent backends. Model control plane is the manager on `:9000`. Chat backends include five llama.cpp Gemma-4-31B instances (`gemma_supervisor.sh`: GPU0 on `8080`/`8082`/`8084`, GPU1 on `8081`/`8083`), optional Qwen2.5-7B on `:8090`, a dynamic llama.cpp band on `8085–8100` filled by `POST /admin/models/load`, and the TensorRT-LLM champion on GPU1 `:8010`. Embedding microservices stay off the decode CUDA contexts: multilingual-e5-small (384-d) on `:8001`, bge-m3 (1024-d) on `:8002`, and MiniLM (384-d, OpenAI `/v1/embeddings`) on `:8003`. DeepSeek-V4-Flash is a standalone wrapper on `:9001` and stays outside the manager registry, so promoting Gemma keeps chat on the Gemma fleet. Orchestrator and guardrails speak OpenAI JSON; production generation is Manager → champion, with automatic fallback into the llama.cpp pool when `:8010` is unavailable. Both `HF_HOME` and `HF_HUB_CACHE` point at the same cache directory. Figure 13 captures that high-level split—clients to manager to model backends, with Docker handling Redis/Qdrant/pgvector/WebUI—while Figure 14 expands the port map and the orchestrator/guardrails/KB adjacency.

![Figure 13. High-level server topology: clients reach the H200 Manager (:9000), which fans out to model backends; a parallel Docker data plane hosts Redis, Qdrant, pgvector, and Open WebUI.](../assets/diagrams/13_server_topology_hl.png)

*Figure 13 — High-level topology. The left/host plane is process-owned inference (manager + GPUs). The Docker plane is stateful infrastructure and the browser UI. Application services (orchestrator, guardrails, KB) sit beside that split. The diagram emphasizes the durable control-plane split.*

![Figure 14. Detailed H200 topology: Manager routes to TRT-LLM :8010, llama.cpp Gemma 8080–8084, Qwen :8090, and embeds 8001–8003; WebUI → Orchestrator → Guardrails/Manager; KB uses MiniLM embed :8003 and pgvector.](../assets/diagrams/14_server_topology_detail.png)

*Figure 14 — Detailed port topology. Champion traffic is TRT-LLM on GPU1 `:8010`; the Gemma pool remains the resilience path. Embedding ports stay separate so retrieval does not share CUDA contexts with decode. WebUI stays on `:13000` and never talks to Gemma ports directly.*

### Docker publish surface

Application ports on the host process plane (`8000`, `8100`, `8200`, `9000`, `8001–8003`, `8080–8084`) are not the same map as the containers Docker publishes. The data-plane and monitoring surface, from the server-setup pages, is:

| Published | Service | Host → container |
|---|---|---|
| 13000 | Open WebUI | 13000 → 8080 |
| 15432 | pgvector | 15432 → 5432 |
| 16333 / 16334 | Qdrant REST / gRPC | 16333 → 6333, 16334 → 6334 |
| 16379 | Redis | 16379 → 6379 |
| 19530 | Milvus | 19530 → 19530 |
| 13001 / 19090 | Grafana / Prometheus | 13001 → 3000, 19090 → 9090 |
| 14317 / 14318 / 19092 | OTel gRPC / HTTP / exporter prom | 14317 → 4317, 14318 → 4318, 19092 → 9091 |
| 9101 | GPU metrics exporter | host process |
| 8088 | nginx gateway | `/vllm/`, `/llama/`, `/embeddings/`, `/webui/` |

The pages technical map above is the inventory to operate against. Postgres inside the container is `5432`; callers on the H200 host use the published `15432` unless they are on the Docker network.

## Manager OpenAI gateway and Squid discipline

`components/server-setup/llm_inference_manager/app.py` exposes `/v1/chat/completions`, `/v1/completions`, `/v1/models`, `/health`, plus admin load/unload and Triton/TRT promote endpoints. Round-robin counters distribute load across replica URLs; SQLite (`manager.db`) records history and metrics. `MODEL_REGISTRY` carries `gemma-4-31b` and `gemma-4-31b-triton-trt`. Promotion is an admin action (`POST /admin/triton/promote?backend=trt&url=http://127.0.0.1:8010`) that flips the gateway mapping without changing orchestrator environment variables. When `:8010` is unavailable, the manager uses the llama.cpp pool.

Corporate egress is Squid at `http://192.168.203.2:3128`, persisted by `proxy_setup.sh` into the shell, apt, git, and the Docker daemon. The shell exports `http_proxy` / `https_proxy` and sets `no_proxy` / `NO_PROXY` to `localhost,127.0.0.1`. Localhost backends in the manager use their own client: every outbound call constructs `httpx.AsyncClient(timeout=120, trust_env=False)` (`llm_inference_manager/app.py` `proxy_chat`: line 301 for the promoted backend, line 333 for the llama.cpp pool). That flag keeps loopback requests to `:8010` and `:8080` on the host. Manual probes use `curl --noproxy '*'` (including the nginx gateway on `:8088`). The same `trust_env=False` rule belongs on guardrails and observability clients.

The champion itself is TensorRT-LLM **1.3.0rc29** (`trtllm-serve`, PyTorch backend, `tp_size=1`), BF16, `max_batch_size=128`, GPU1 `:8010`, launched from an isolated `offline-prep/venv-trtllm` so the shared live virtualenv’s torch, numpy, and transformers stay untouched. `scripts/serve_trtllm.sh` launches through `mpirun -n 1 trtllm-llmapi-launch` and sets `attn_backend: FLASHINFER` for Gemma-4 `global_head_dim=512`. The five GGUF replicas use bartowski `google_gemma-4-31B-it` Q4_K_M with `n_ctx` 4096 under an auto-reviving supervisor.

## Containerization and cutover

The H200 data plane runs from container images. Parent `deploy/docker/` holds compose variants (`docker-compose.yml`, GPU and Qdrant overlays, nginx) for the NVIDIA runtime. `components/server-setup/docs/migration/containerization-report.md` records a five-phase, side-by-side cutover:

| Phase | What changes for live traffic |
|---|---|
| **1** | Build images and validate each service on alternate ports only: KB `8100`, guardrails `8201`, orchestrator `8101`, tracing `3001`, manager `9001`, Gemma `8085–8089`, embeds `8004–8006`. Production listeners stay up. |
| **2** | End-to-end on those alternates: Open WebUI → orchestrator `:8101` → guardrails `:8201` → KB `:8100` → Gemma `:8085`. |
| **3** | Jenkins pipeline (checkout → lint → test → build → push → deploy-dev → e2e). Still no production port swap. |
| **4** | Per-service cutover onto the **same** production ports, in order: tracing → embeds → KB → guardrails → orchestrator → manager → Gemma ×5. Rollback is restarting the host virtualenv. |
| **5** | After 24 hours of stability, decommission the host virtualenvs. |

Phases 1–3 leave production traffic on its current listeners; phase 4 is the step that changes them. Production ports in the map are `8000`, `8001–8003`, `8080–8084`, `8100`, `8200`, `9000`, `13000`, `16379`, postgres `5432`, and tracing `3000`. Two alternate numbers in the phase-1 map already name live services: KB’s alternate `8100` is the orchestrator port, and the alternate manager `9001` is the DeepSeek wrapper. Confirm the host is free before binding those alternates.

## Scaling: million-user plan and measured decode throughput

`docs/plans/million-user-scale-plan.md` separates **scale-out** from **scale-up**. Scale-out places stateless FastAPI/orchestrator pods behind Kubernetes Ingress with HPA on CPU, GPU inference behind Triton/TensorRT replicas scaled by queue depth (KEDA), and a dedicated vector cluster (Qdrant) with read replicas—trading operational complexity for elastic concurrency (Figure 17). Scale-up keeps a single 2×H200 machine saturated: large in-RAM indexes, many Triton instance groups per GPU, and Gunicorn worker counts near core count, minimizing cross-node latency at the cost of vertical coupling (Figure 18). For Work Credit RAG’s Persian chat path, generation—not retrieval—dominates wall time, so inference batching efficiency dominates capacity math.

![Figure 17. Scale-out: million users → K8s Ingress → HPA’d orchestrator pods → guardrails/KB pods → Qdrant cluster and Triton/TRT-LLM GPU replicas.](../assets/diagrams/17_scale_out.png)

*Figure 17 — Cloud-native scale-out. CPU tiers (orchestrator, guardrails, KB) scale independently of GPU inference tiers behind Ingress and HPA/KEDA. Semantic cache and hybrid vector search sit beside autoscaled Triton/TRT replicas so decode GPUs are not wasted on duplicate retrieval work. This is the elasticity path when concurrent Persian chat outgrows a single chassis.*

![Figure 18. Scale-up: users → Nginx → Gunicorn workers → FastAPI apps → Triton on 2×H200 saturating VRAM with model replicas.](../assets/diagrams/18_scale_up.png)

*Figure 18 — Bare-metal scale-up. One chassis, two H200s, shared-memory friendly batching. Prefer this when the model footprint fits and operational ownership stays on `ai-gpu1`.*

History `013` (`components/server-setup/docs/history/013_2026-10-13_trtllm_champion_concurrency.md`) recorded a like-for-like Persian prompt (`max_tokens=256`) across concurrency. llama.cpp Q4 on the single-slot placeholder stayed ~58–59 aggregate tok/s at every concurrency (no continuous batching). TensorRT-LLM BF16 on `:8010` scaled roughly linearly with in-flight requests: ~50 tok/s at conc 1, ~386 at 8, ~1385 at 32, and **3874.2** aggregate tok/s at conc 128 (~**67.3×** versus the flat Q4 baseline). Single-stream favors Q4 slightly (memory traffic); multi-user traffic favors TRT. An FP8 KV-cache experiment (`TRTLLM_KV_DTYPE=fp8`) landed near 0.95× at low concurrency and about +15% at concurrency 128. Operators should size on sustained ~2.9k tok/s under power capping, not the first-burst 3.8k peak, and keep CUDA-graph batch sizes dense up to 128 so intermediate concurrencies do not fall off the graph cliff into eager decode.

## Tooling

| Tool | Role in this stack |
|---|---|
| llama.cpp | GGUF Gemma/Qwen servers; H200 pool `8080–8084` |
| TensorRT-LLM | Champion BF16 continuous batching on `:8010` |
| LiteLLM | Optional embed/chat adapter path from the manager |
| Docker | H200 data plane and image cutover |
| vLLM | Alternate OpenAI-compatible serving on H200 offline prep |
| PyTorch | TRT export/serve stack, embeds, offline CUDA wheels |

Together these pieces keep a single OpenAI-shaped contract from WebUI through orchestrator and guardrails, with generation served by the H200 champion and the llama.cpp pool behind the manager on `:9000`.
