# Server Setup — GitHub Pages extract

Sources: `components/server-setup/docs/{index,technical,high-level}.html`, `guides/03-services-and-endpoints.md`, `gemma_endpoints.md`, `migration/containerization-report.md` (intro/phases).

## Role

H200 offline RAG environment (2× H200 NVL, 281 GiB VRAM). Owns host bootstrap, model lifecycle, embeddings, LLM Inference Manager (`:9000`), Docker data plane, monitoring. Working dir: `/splunk-data/v1/Work_RAG-Server-Setup`.

## Squid / trust_env

- Corporate Squid proxy: `http://192.168.203.2:3128`
- Persist via `proxy_setup.sh` (env + apt + git + docker daemon)
- Shell: `http_proxy` / `https_proxy` set; `no_proxy` / `NO_PROXY` = `localhost,127.0.0.1`
- **Critical:** Manager uses `httpx.AsyncClient(timeout=120, trust_env=False)` (`app.py:301`, `app.py:331`) so localhost backends bypass Squid
- Local curls: `curl --noproxy '*'` (also for nginx gateway `:8088`)

## Ports

### Host / LLM / embeds

| Port(s) | Service |
|---|---|
| 8001 | multilingual-e5-small embeddings (384-d) |
| 8002 | bge-m3 embeddings (1024-d) |
| 8003 | MiniLM embeddings (384-d) — OpenAI `/v1/embeddings` |
| 8010 | **TRT-LLM** Gemma-4-31B champion (GPU1, `serve_trtllm.sh`) |
| 8080–8084 | 5× Gemma-4-31B llama.cpp (`gemma_supervisor.sh`; GPU0: 8080/8082/8084, GPU1: 8081/8083) |
| 8085–8100 | Dynamic llama.cpp backends (`POST /admin/models/load`) |
| 8090 | Qwen2.5-7B |
| 9000 | LLM Inference Manager gateway (OpenAI-compatible, `manager.db`) |
| 9001 | DeepSeek-V4-Flash wrapper (standalone; **not** in `MODEL_REGISTRY`) |

### Docker data-plane / monitoring

| Port(s) | Service | Host→container |
|---|---|---|
| 13000 | Open WebUI | 13000→8080 |
| 15432 | pgvector | 15432→5432 |
| 16333 / 16334 | Qdrant REST/gRPC | 16333→6333, 16334→6334 |
| 16379 | Redis | 16379→6379 |
| 19530 | Milvus | 19530→19530 |
| 13001 / 19090 | Grafana / Prometheus | 13001→3000, 19090→9090 |
| 14317 / 14318 / 19092 | OTel gRPC / HTTP / prom | 14317→4317, 14318→4318, 19092→9091 |
| 9101 | GPU metrics exporter (host) | — |
| 8088 | nginx gateway (guide 03) | `/vllm/`, `/llama/`, `/embeddings/`, `/webui/`, … |

Guide 03 also notes historical/alternate binds (vLLM `:8000`, early embed `:8001` as bge-small) — prefer Pages technical port map for current H200 inventory.

### Gemma 5-instance map (`gemma_endpoints.md`)

| Model ID | Port | GPU |
|---|---|---|
| gemma-4-31b-1 … -5 | 8080–8084 | alternating 0/1 |
| GGUF | bartowski `google_gemma-4-31B-it` Q4_K_M, `n_ctx` 4096 | auto-reviving supervisor |

## TRT notes

- Champion `gemma-4-31b` via **TensorRT-LLM 1.3.0rc29** (`trtllm-serve`, PyTorch backend, `tp_size=1`), BF16, `max_batch_size=128`, GPU1 `:8010`
- Launcher fixes in `scripts/serve_trtllm.sh`: `mpirun -n 1 trtllm-llmapi-launch` (avoid OpenMPI `MPI_Comm_spawn` deadlock); isolated `offline-prep/venv-trtllm` first on PATH; `attn_backend: FLASHINFER` (default TRTLLM MMHA asserts on Gemma-4 `global_head_dim=512`)
- Throughput: single-stream GGUF ~58 tok/s vs TRT BF16 ~50 tok/s; TRT continuous batching ~3874 tok/s @ concurrency 128; FP8-KV (`TRTLLM_KV_DTYPE=fp8`) ~0.95× low conc, +15% @ conc-128
- Manager `MODEL_REGISTRY`: `gemma-4-31b` + `gemma-4-31b-triton-trt`; promote via `POST /admin/triton/promote?backend=trt&url=http://127.0.0.1:8010`; fallback to llama.cpp pool
- Gotcha: never upgrade shared live venv’s torch/numpy/transformers — keep TRT in isolated venv

## Containerization phases (`migration/containerization-report.md`)

Status (2026-10-31): approved for Phase 1. Side-by-side validation — **Phases 1–3 leave production traffic untouched**.

| Phase | Goal |
|---|---|
| **1** | Build images; validate each on **alt ports** (KB 8100, Guard 8201, Orch 8101, Trace 3001, Manager 9001, Gemma 8085–8089, Embed 8004–8006) |
| **2** | E2E on alt ports via Open WebUI → orch:8101 → guard:8201 → kb:8100 → gemma:8085 |
| **3** | Jenkins pipeline (checkout → lint → test → build → push → deploy-dev → e2e) |
| **4** | Per-service production cutover on **same** ports (order: tracing → embeds → KB → guardrails → orchestrator → manager → Gemma ×5); rollback = restart host venv |
| **5** | After 24h stability, decommission host venvs |

Final ports unchanged: 8000, 8001–8003, 8080–8084, 8100, 8200, 9000, 13000, 16379, 5432, 3000.
