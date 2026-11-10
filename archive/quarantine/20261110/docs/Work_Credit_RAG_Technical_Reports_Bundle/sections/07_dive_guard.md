# Deep Dive: Guardrails & Security

## Section summary

Guardrails (`Work_RAG-Guardrails`, port `:8200`) is the mandatory safety boundary between the LangGraph orchestrator and the Gemma inference plane. Every user turn is checked on the *input* stage before retrieval context is answered; every completed assistant reply is checked again on the *output* stage before it returns to WebUI. The path is deterministic evidence signals, then an adjudicating judge (`gemma`, `mizan`, or `hybrid`), then a direct-LLM yes/no self-check. Policy text ships as versioned YAML; the credit pin is `policies/ics-credit-v1.0.0.yaml`. HurtLex hate checks consult an exact-word allowlist of **28** lemmas. Iranian PII on allowed answers is masked after mod-11 (national ID) and mod-97 (Sheba / IR-IBAN) checks; secret markers hard-block. Ghadeer mmBERT operating points published with the stack are toxicity **0.80**, hate **0.80**, PII **0.90**, and injection **0.85**. Judge timeout, empty verdict, or transport error fails *closed*.

## Position in the request path

Figure 11 places Guardrails between Orchestrator `:8100` and Gemma on the H200 LLM Inference Manager (`:9000`). The orchestrator never calls the LLM directly: it posts `rails/check` for input and output stages, then `chat/completions` for guarded generation. The reply that reaches the user is either a masked safe completion or a category-scoped refusal.

![Figure 11. Guardrails between orchestrator and Gemma.](../assets/diagrams/11_guard_position_hl.png)

*Figure 11 — High-level placement. The orchestrator never dials Gemma directly: it posts `rails/check` for input and output stages, then `chat/completions` for guarded generation. Guardrails alone proxies to the H200 Manager on `:9000` and returns either a PII-masked safe completion or a category-scoped Persian refusal. The diagram is the safety contract for the rest of this section.*

The component docs keep a three-file SVG inventory, also copied into this report’s diagram folder: `../assets/diagrams/architecture-platform.svg` (orchestrator → guardrails → Gemma), `../assets/diagrams/internal-pipeline.svg` (signals → judge → self-check → output rails), and `../assets/diagrams/code-hierarchy.svg` (the `src/`, `config/`, `kb/`, `policies/`, `tests/`, and `images/` tree). The live dashboard at `GET /dashboard` draws its own SVG plots—per-category and per-detector bars, a 24-hour block timeline, and a stage donut—from masked JSONL rather than from those static files.

## Signals, judge, and fail-closed

The runtime lives in `components/guardrails/src/work_rag_guardrails/`:

| Module | Role |
|--------|------|
| `service.py` | FastAPI app, `/v1/rails/check`, `/v1/chat/completions`, premade refusals, upstream proxy, history trim |
| `signals.py` | Deterministic detectors → evidence list (injection, jailbreak, HurtLex hate, profanity, scope, PII-IR) |
| `judge.py` | `adjudicate()` — secret hard-block, policy judge backends, direct-LLM self-check, fail-closed |
| `events.py` | JSONL decision log with PII/secret masking (`/tmp/guard_events.jsonl`) |
| `dashboard.py` | Zero-dependency RTL dashboard on the same `:8200` process |

`collect_signals` normalizes Persian text and runs pattern/list detectors. Those hits are *helpers for the judge*, and `secret` (`sk-`, `api_key`, `database_url`, `Bearer`) is the detector `adjudicate` short-circuits to refuse. Domain keywords from the active policy feed a fast out-of-domain pre-check. An absent policy file or an empty keyword list routes to review.

The HurtLex detector reads `kb/hurtlex_allowlist.json`: **28** lemmas matched as exact words on both input and output, chosen so credit and social vocabulary (حذف، تأمین مالی، اشتغال، مردم، and the rest of that list) stays in domain. Profanity, PII, and secret checks stay outside that allowlist.

Output-stage **PII-IR** is checksum-aware, not a bare digit hunt. A national ID must satisfy the Iranian mod-11 check; a Sheba / IR-IBAN must satisfy mod-97; mobile and landline patterns are matched alongside those validators. A valid PII hit on an otherwise allowed answer is **mask-and-continue** (`[masked-pii]`). A secret marker is a hard block. The events log stores only the masked form.

Judge backend is selected with `GUARD_JUDGE_BACKEND`:

- **`gemma`** (default) — pinned-policy categories judged by Gemma; parse `VERDICT` / `CATEGORY`; empty or unparseable → refuse.
- **`mizan`** — Mizan System-1 via Manager (`/systemone`) with calibrated safety / scope / severity questions.
- **`hybrid`** — Mizan first; escalate to Gemma when confidence is low, severity is high, or hard signals fire (injection, jailbreak, secret, PII, hate, offense).

`GUARD_JUDGE_MODE=on-signal` (default) skips the LLM judge when the text is clean; `always` forces adjudication. A second-opinion direct-LLM yes/no self-check is fail-closed on error. `GUARD_NEMO_SELFCHECK` (`on` / `shadow` / `off`) selects that self-check.

Published Ghadeer mmBERT score floors, from the parent models table, sit next to those detectors: toxicity **0.80**, hate **0.80**, PII **0.90**, injection **0.85**. They are operating points for the classifier signals, not a second policy language. The category taxonomy the judge actually returns is `prompt_injection`, `jailbreak`, `hate`, `offense` (profanity), `pii`, `out_of_scope`, `secret`, `policy`, and `engine_error`.

![Figure 12. Adjudication pipeline.](../assets/diagrams/12_guard_adjudicate_detail.png)

*Figure 12 — Normalize → collect signals → domain scope → policy judge (Gemma / Mizan / hybrid) → direct-LLM self-check → allow or premade Persian refuse. Errors route to fail-closed refusal.*

## Policy pin

Versioned prompts live under `policies/` as `policies/<domain>-v<semver>.yaml`. `policies/active.yaml` is the pin. The current credit file is `policies/ics-credit-v1.0.0.yaml`: company and people mentions count as in-domain, and ungrounded advice is its own refusal category. Each file carries `id`, `version`, `stage`, and `categories` whose `prompt` interpolates `{{text}}` and `{{signals}}`, plus `refusal`, `examples`, and `domain_keywords` for the no-LLM scope pre-check. Released versions are immutable; a change is a new file and a moved pin. The reported default `POLICY_VERSION` when nothing is pinned is `mvp-1`.

## Endpoints and user-facing policy

**`POST /v1/rails/check`** accepts `{stage, text, request_id}` for `input` or `output`. The response carries `allowed`, `action`, category ids, and a `reason` string. In production mode (`GUARD_RESPONSE_MODE`), `reason` is a premade Persian message keyed by category—prompt injection, jailbreak, hate, offense, out-of-scope, PII, secret, policy—without exposing regex matches or judge traces. Output-stage hate/profanity refusals blame the *answer* (“پاسخ حاوی محتوای نامناسب است…”) rather than the user.

**`POST /v1/chat/completions`** is the OpenAI-compatible guarded gateway used by the orchestrator’s `guarded_generate` node. Flow:

1. Extract the question slice from an augmented user message (`Question:` / `سوال:`), cap to the rails text limit.
2. Input rails → refuse with `finish_reason="content_filter"` if blocked.
3. Trim chat history to a Persian-aware char budget so upstream context (8192 tokens) is not overflowed.
4. Call Gemma with `chat_template_kwargs: {"enable_thinking": false}` and strip leaked control tokens.
5. Output rails → refuse or continue.
6. If PII-IR validators (national-id mod-11, Sheba mod-97, phone patterns) still match an *allowed* answer, `events.mask_text` replaces those digit runs—and API-key-like spans—before return.

Health and readiness expose upstream reachability and policy version; the interactive dashboard aggregates masked JSONL events (block rate, categories, 24h timeline, sample viewer).

## Upstream contract details

All outbound `httpx.AsyncClient` calls to the manager on `:9000` set **`trust_env=False`**. That flag keeps loopback traffic off the host Squid proxy at `192.168.203.2:3128`. See the server-setup section for the same rule on the manager.

The gateway maps timeout and context-window paths to **`finish_reason="length"`** with a short Persian retry hint. Successful rails refusals use `content_filter`; clean answers use `stop`. The allowed set is `stop`, `length`, and `content_filter`.

Buffered completions run input rails, call the manager, run output rails, and write a masked JSONL event. The dashboard reads that log.

## Tooling

| Tool | Role in Guardrails |
|---|---|
| FastAPI | HTTP API factory (`create_app`), rails + chat routes, dashboard |
| httpx | Async upstream / Mizan / health clients (`trust_env=False`) |
| HurtLex | Persian hate lexicon evidence for the judge; **28**-lemma credit allowlist in `kb/hurtlex_allowlist.json` |
| Pydantic | Request/response models including `finish_reason` literals |
| uvicorn | ASGI server for the `:8200` factory app |

Together these pieces keep Guardrails a thin, fail-closed Persian safety shell: deterministic evidence in, adjudicated allow/refuse out, secrets never returned, and Gemma reachable only through a controlled proxy that refuses when unsure.
