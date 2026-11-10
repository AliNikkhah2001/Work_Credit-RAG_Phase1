# Security and Networking

Work Credit RAG separates safety into three planes that stay distinct in design reviews. **Content safety** decides whether a Persian turn may be answered. **Application security** decides how services validate, store, and render request data. **Network exposure** decides which sockets a packet can reach. Guardrails on `:8200` is the content-safety boundary. Host bind addresses, Docker publish rules, and the corporate Squid proxy form the network plane. This chapter states each plane, the H200 black-box port map, the security control classes used in reviews, and the guardrails signal and policy architecture.

## Threat model

**Content safety** is the product promise to credit-domain users. Every user turn is checked before retrieval is allowed to drive an answer, and every completed assistant reply is checked again before it returns to WebUI. The detectors look for prompt injection and jailbreak phrasing, HurtLex hate, Persian profanity, out-of-domain text, Iranian PII, and secret markers. A secret marker is a hard stop. Other signals are evidence for a judge. Timeout, an empty verdict, a missing policy, or a transport error fails closed: the caller receives a premade Persian refusal rather than the upstream text. Iranian PII that survives an allow decision is masked.

**Application security** is the integrity of the processes behind those HTTP ports. Reviews cover upload filename handling, admin and ingest authentication, archive expansion quotas, template escaping for ingested office content, CORS origin and credential pairing, process-launch argument validation on the model manager, server-side request targets, Iranian PII and secret checks on the generation path, and stream-state isolation in the orchestrator.

**Network exposure** is which sockets exist outside the host. On the self-hosted **H200** lab server (`ai-gpu1`) inference and embeddings listen on the internal port range, Docker publishes a data plane, and corporate egress is forced through Squid. Localhost clients construct `httpx.AsyncClient(..., trust_env=False)` so proxy variables do not redirect loopback health checks. The three planes meet at one rule: a browser that can open WebUI must still be unable to open raw model backends, Postgres, or Redis as public services.

## Black-box service and network view

From outside the process boundary the platform is a set of listeners on the H200 lab server plus one proxy hop. The LLM Inference Manager is the OpenAI-shaped front door; llama.cpp and TensorRT-LLM are backends; Docker owns the data plane for WebUI, databases, and monitoring.

![Dual-host networking](../assets/diagrams/security_dual_host_net.png)

*H200 lab networking. Manager, DeepSeek, embeddings, the Gemma pool, and TRT-LLM run on the host network. Docker publishes WebUI, pgvector, and Redis on high ports. Squid at `http://192.168.203.2:3128` is egress for package and model downloads. `httpx` clients that talk to localhost set `trust_env=False` so that proxy variable cannot hairpin a loopback health check.*

### H200 listeners

The project runs on the self-hosted H200 lab server. The manager on `:9000` is the gateway (`/v1/chat/completions`, admin load, Triton promote). DeepSeek-V4-Flash on `:9001` is a standalone wrapper and is not in `MODEL_REGISTRY`. Embedding workers are multilingual-e5-small `:8001` (384-d), bge-m3 `:8002` (1024-d), and MiniLM `:8003` (384-d, OpenAI `/v1/embeddings`). Five llama.cpp Gemma replicas occupy `:8080`–`:8084`. TensorRT-LLM champion traffic is `:8010`. Dynamic extra llama.cpp ports `:8085`–`:8100` and Qwen on `:8090` exist on the host map and are treated as the same internal tier as the Gemma pool.

Application listeners on the same host include Open WebUI `:13000`, orchestrator `:8100`, knowledge base `:8000`, guardrails `:8200`, the fallback trace collector `:3000`, Langfuse `:3001`, and LangGraph Studio `:2024`. Studio run input carries `request_id`.

Docker on the same host publishes the data plane and the browser UI. The runbook inventory includes Open WebUI `13000→8080`, pgvector `15432→5432`, Redis `16379→6379`, Qdrant `16333` (gRPC `16334`), Milvus `19530`, Grafana `13001`, Prometheus `19090`, and the OpenTelemetry collector `14317`. Those published container ports are reachable on the host network. Postgres and Redis remain internal services for the data plane rather than public internet endpoints.

### Squid and `trust_env`

Corporate egress on `ai-gpu1` is Squid at `http://192.168.203.2:3128`, exported as `HTTP_PROXY` and `HTTPS_PROXY` for apt, pip, git, and Hugging Face. Manager, guardrails, and the orchestrator’s localhost clients construct `httpx.AsyncClient(..., trust_env=False)`. With the flag off, a health check to `:8010`, `:8080`, or `:9000` stays on the loopback interface. Manual probes use `curl --noproxy '*'`.

### Compose MVP surface

`compose.mvp.yml` is the privileged-host packaging of the MVP on hosts that run Docker. The file is explicit about the public surface: Open WebUI is published as `0.0.0.0:13000:8080`, and the Langfuse container is published as `0.0.0.0:3000:3000`. Knowledge base `:8000`, guardrails `:8200`, orchestrator `:8100`, Postgres `:5432`, and Redis `:6379` are `expose`d onto the Docker network so containers resolve each other by name. Guardrails reaches the model plane through the manager on the host network.

![Compose MVP surface](../assets/diagrams/security_compose_mvp.png)

*Compose MVP surface. WebUI on `:13000` and Langfuse on `:3000` attach to host interfaces. Orchestrator, KB, guardrails, Postgres, and Redis stay on the Docker DNS network for service discovery.*

## Security control classes

The table below summarizes the production security controls used when reviewing the stack. Each row names the control and what it covers in this architecture.

![Audit hotspots](../assets/diagrams/security_audit_hotspots.png)

*Security control classes across knowledge base, manager and tracing, guardrails, and the orchestrator stream path. Reviews walk each control against the owning component on the H200 deployment.*

| Control | What it covers |
|---|---|
| Content adjudication | Judge and policy document assembly; Persian instruction-override phrasing handled as the `prompt_injection` and jailbreak content-safety categories; ingestion logs on collector endpoints. |
| Upload and export paths | Upload filenames are sanitized into the upload directory. `from-path` and export-path reads stay under restricted roots. |
| Admin authentication | KB admin and ingest routers check `X-Admin-Token` / `KB_ADMIN_TOKEN`. Manager and tracing dashboard and ingestion endpoints require authentication. |
| Archive limits | Ingest applies archive expansion quotas, compression-ratio checks, byte caps, and stage-directory retention. |
| CORS | The manager and related dashboards use explicit CORS origin lists paired with credential flags. |
| Process launch | Process launches omit `shell=True`. Admin load validates `port` and `n_ctx` ranges and uses model-registry allowlists. |
| Callback targets | Studio and related collector callbacks use allowlisted server-side request targets. |
| Rendered content | Ingested chunk text is escaped in KB templates. Observability pages use safe DOM assignment. |
| PII and secrets | PII-IR is Persian-digit and spaced-Sheba aware. Secret markers are hard blocks. Output rails run on streamed completions. |
| Stream isolation | The orchestrator isolates per-request stream state so concurrent turns do not share mutable initial state. |

## Guardrails signal and policy architecture

Guardrails is a sealed HTTP box on `:8200`. Orchestrator `:8100` posts `POST /v1/rails/check` with `{stage, text, request_id}` for input and again for output, then `POST /v1/chat/completions` for guarded generation. Guardrails is the component that dials the H200 LLM manager on `:9000`. WebUI never receives upstream model URLs.

![Guardrails black-box](../assets/diagrams/security_guard_blackbox.png)

*Guardrails black box. Callers see two routes and one outcome: a PII-masked completion with `finish_reason=stop`, a length-mapped upstream condition with `finish_reason=length`, or a category refusal with `finish_reason=content_filter`. Inside the box, input rails run before the upstream call and output rails run on the completed text. The upstream arrow terminates at the H200 manager. A judge error, an empty verdict, or a timeout refuses the turn.*

Inside the box the order is deterministic signals, then a policy judge, then a direct-LLM yes/no self-check. `collect_signals` normalizes Persian text and emits evidence: injection, jailbreak, HurtLex hate, profanity, scope, and PII. Those hits do not themselves block, except `secret` (`sk-` prefixes, `api_key`, `database_url`, `Bearer`), which `adjudicate` refuses immediately. `GUARD_JUDGE_BACKEND` selects `gemma` (pinned policy, parse `VERDICT` / `CATEGORY`), `mizan` (Manager `/systemone`), or `hybrid` (Mizan first, Gemma when confidence is low or a hard signal fired). `GUARD_JUDGE_MODE=on-signal` skips the LLM judge when the text is clean; `always` forces it. The self-check is selected by `GUARD_NEMO_SELFCHECK` (`on`, `shadow`, or `off`). An error in that check fails closed.

Datasets and policy files that feed the box:

| Asset | Role |
|-------|------|
| `kb/hurtlex_fa.json` (HurtLex FA 1.2) | Hate and insult lemmas, on the order of 2464 entries across 17 categories, used by `check_hurtlex`. |
| `kb/hurtlex_allowlist.json` | Exact-word credit and social exceptions: **28 lemmas**. Profanity, PII, and secrets are not allowlisted. |
| `kb/prompt_injection_fa.json` | About 26 Persian injection and jailbreak patterns for `check_prompt_injection_fa`. |
| `kb/persian_swear.json` | About 322 profanity entries for `check_profanity_fa`. Strict. |
| `policies/ics-credit-v1.0.0.yaml` | Versioned ICS policy, pinned by `policies/active.yaml`. Categories include `out-of-domain` (company and people questions stay in domain) and `ungrounded-advice`. `domain_keywords` drive the fast pre-check. New policy ships as a new file plus a pin move. Released versions stay immutable. |
| `eval/samples/` | Offline expectations: `prompt_injection.json`, `pii.json`, `hate_toxicity.json`, `financial_false_positive.json`, `benign_credit.json`. |

**PII-IR** is the output-stage Iranian identifier check: national ID with a mod-11 test, Sheba / IR-IBAN with mod-97, and mobile or landline shapes. A validator hit on an otherwise allowed answer is mask-and-continue (`[masked-pii]`). A secret marker is a hard block, not a mask. Event logs store the masked form.

Production refusals are premade Persian strings keyed by category (`prompt_injection`, `jailbreak`, `hate`, offense, `out_of_scope`, `pii`, `secret`, `policy`, `engine_error`). The `reason` field in production mode does not echo the regex or the judge trace. Output-stage hate and profanity refusals attribute the problem to the answer. Upstream context overflow is mapped to `finish_reason=length` with a short Persian retry hint.
