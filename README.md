# Work Credit RAG — Phase 1

Umbrella repository for a self-hosted, Persian-capable conversational RAG platform. The implementation is split into independently maintained Git submodules so model/server operations, knowledge-base lifecycle, safety policy, and LangGraph orchestration can evolve without returning to a monolith.

> **Branch:** `vast-gemma4-migration` is live on Vast.ai (2026-09-02). `main` is the last stable monolith checkpoint (`3ee1780`). Do not merge to `main` until §16 is persistent.

## Repository composition

| Path | Repository | Current responsibility | Default branch | Vast pin |
|---|---|---|---|---|
| `components/server-setup` | [Work_RAG-Server-Setup](https://github.com/AliNikkhah2001/Work_RAG-Server-Setup) | H200/Vast provisioning, local model and embedding services, Gemma manager, Open WebUI, infra | `main` | `5d5a7e4` |
| `components/knowledgebase` | [Work_RAG-KB](https://github.com/AliNikkhah2001/Work_RAG-KB) | KB ingestion, maintenance, versioning, hybrid retrieval (BM25+dense+RRF+cross-encoder), KB web UI | `master` | `8b8f6e5` |
| `components/guardrails` | [Work_RAG-Guardrails](https://github.com/AliNikkhah2001/Work_RAG-Guardrails) | Deterministic Persian rails + risk scoring + semantic interface (v2) | `main` | `6ce319f` |
| `components/orchestrator` | [Work_RAG-Orchestrator](https://github.com/AliNikkhah2001/Work_RAG-Orchestrator) | LangGraph workflow and public OpenAI-compatible chat API | `main` | `cdb6e7d` |

Each gitlink is pinned to an exact commit. Updating a component requires a component-repository commit followed by a parent-repository commit that advances the corresponding gitlink.

```bash
git submodule status --recursive
# 6ce319f... components/guardrails (heads/vast-gemma4-migration)
# 8b8f6e5...       components/knowledgebase (heads/vast-gemma4-migration)
# cdb6e7d...       components/orchestrator (heads/vast-gemma4-migration)
# 5d5a7e4...       components/server-setup (heads/vast-gemma4-migration)
```

## MVP target

The first goal is one small, deterministic, observable request path — not the full production architecture:

```mermaid
flowchart LR
    UI["Open WebUI :13000"] --> ORCH["LangGraph API :8100"]
    ORCH --> KB["KB retrieval :8000"]
    ORCH --> GR["NeMo Guardrails :8200"]
    GR --> GEMMA["Gemma :18000 external llama-server"]
```

Request order:

```text
browser :13000 → Open WebUI → Orchestrator :8100
  → KB :8000 hybrid retrieval (BM25 + MiniLM 384 + RRF + mmarco cross-encoder)
  → context construction (MAX_CHUNKS 3, MAX_CHARS 4000)
  → Guardrails :8200 → Gemma :18000 (unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL)
  → citation-shaped response (rag.citations) → frontend
```

**Vast deployment:** Gemma is external at `http://127.0.0.1:18000/v1` (host) / `http://host.docker.internal:18000/v1` (Docker). `compose.mvp.yml` removes the legacy `gemma-manager` service; `LLM_BASE_URL`/`LLM_MODEL` are env-configurable. Public browser URL is `http://91.108.80.253:13000` (`0.0.0.0:13000:8080`, fallback `8080→22341` via `ssh -p 24044 -L 13000:localhost:13000 root@ssh9.vast.ai`). See `docs/RUNBOOK_VAST.md` and `docs/VAST_GEMMA4_MIGRATION.md`.

The MVP deliberately excludes long-term memory, PostgreSQL LangGraph checkpoints, query rewriting, agent loops, retrieval retries, streaming, GraphRAG, multi-agent routing, and Kubernetes. Those come after the basic path is reliable.

Detailed plan and acceptance tests: [docs/MVP_INTEGRATION_PLAN.md](docs/MVP_INTEGRATION_PLAN.md)

## Clone

```bash
git clone --recurse-submodules https://github.com/AliNikkhah2001/Work_Credit-RAG_Phase1.git
cd Work_Credit-RAG_Phase1
git switch vast-gemma4-migration
git submodule sync --recursive && git submodule update --init --recursive
```

## Quick start (Vast, host venvs — Docker is unprivileged on this host)

```bash
# 1. KB (caddy occupies *:8000, so host uses 8004)
KB_DB_URL="sqlite+aiosqlite://$PWD/components/knowledgebase/kb-manager/data/kb_test.db" \
  KB_WEB_HOST=127.0.0.1 KB_WEB_PORT=8004 \
  /tmp/kb-venv/bin/python -m uvicorn kb_manager.web.app:app --host 127.0.0.1 --port 8004 &

# 2. Guardrails (5c28940, with HurtLex allowlist 12 lemmas + enable_thinking:false)
PYTHONPATH=components/guardrails/src \
  GUARDRAILS_HOST=127.0.0.1 GUARDRAILS_PORT=8200 \
  UPSTREAM_LLM_BASE_URL=http://127.0.0.1:18000/v1 \
  UPSTREAM_LLM_MODEL=unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL \
  /tmp/guard-venv/bin/python -m uvicorn work_rag_guardrails.api:create_app --factory --host 127.0.0.1 --port 8200 &

# 3. Orchestrator
PYTHONPATH=components/orchestrator/src \
  KB_BASE_URL=http://127.0.0.1:8004 GUARDRAILS_BASE_URL=http://127.0.0.1:8200 \
  UPSTREAM_LLM_MODEL=unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL \
  /tmp/orch-venv/bin/python -m uvicorn work_rag_orchestrator.api:create_app --factory --host 127.0.0.1 --port 8100 &

# 4. Open WebUI
OPENAI_API_BASE_URL=http://127.0.0.1:8100/v1 OPENAI_API_KEY=sk-local-dev WEBUI_AUTH=false \
  /tmp/webui-venv/bin/open-webui serve --host 0.0.0.0 --port 13000 &

# Health
for p in 8004 8200 8100; do curl -s http://127.0.0.1:$p/health | grep ok && echo "$p ok"; done
curl -s http://127.0.0.1:8100/ready | jq .dependencies
curl -s http://127.0.0.1:8200/ready | jq .
curl -s http://127.0.0.1:18000/v1/models | jq .data[0].id
```

Docker (privileged host): `LLM_BASE_URL=http://host.docker.internal:18000/v1 docker compose -f compose.mvp.yml up --build -d` — only `13000` is public.

## Status — Vast `vast-gemma4-migration` (pushed 2026-09-02, parent `422365d` → next, pins: guardrails `6ce319f`, orchestrator `cdb6e7d`, KB `8b8f6e5`, server-setup `5d5a7e4`)

Live on Vast VM `49624249` (`ssh9.vast.ai:24044`, `91.108.80.253`), `2× RTX 6000 Ada 49 Gi (595.58.03, CUDA 13.2)`, `96× EPYC 7443`, `503 Gi RAM`, `100 Gi disk`. `env | grep proxy` empty. Gemma at `http://127.0.0.1:18000/v1` (`/opt/llama-new`, not supervisor-managed yet). `ss -tlnp` shows `0.0.0.0:18000 (llama-new)`, `127.0.0.1:8004/8200/8100`, `0.0.0.0:13000`. Guardrails `6ce319f` (allowlist 15 lemmas, profanity len>2, risk+observability+semantic) + Orchestrator `cdb6e7d` (Persian prompt) live via host venvs (`8200` pid `85170`, `8100` pid `85178`); Docker `compose.mvp.yml` ready for privileged hosts but this Vast host is unprivileged (`unshare` denied).

- **Gemma — FIXED at source (was `<unused*>` leak):** `unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL` (30.6 B, 18.8 GiB) now on `llama.cpp 0.3.0-dev (build 1, 0f3a71b, 2026-09-02, /opt/llama-new/bin/llama-server)` with `--no-mmproj --jinja --ctx-size 8192 --temp 0.2` (`LD_LIBRARY_PATH=/opt/llama-new/lib`). `POST /v1/chat/completions` with `chat_template_kwargs:{"enable_thinking":false}` → clean Persian, `has_unused False`, `reasoning_content` empty. Verified 5 prompts sequential: `سلام`→`سلام! چطور می‌توانم…` (35 chars), `Hello` (32), `اعتبارسنجی چیست` (311), `چگونه گزارش اعتباری...` (323), `یک پاسخ کوتاه...` (19). Old `b1-ff5ef82` + `mmproj-BF16.gguf` always injected `<unused*>`/`<|tool_call|>` even for `Hello`.

- **Guardrails — FIXED false positives (was HurtLex 15 lemmas `حذف`/`بخشی`/`تامین مالی`/`اشتغال`/`پست`/`پستی`/`مصرف`/`هدف`/`نادرست`/`مهم`/`ضعیف`/`خسته`/`شرح`/`دسته`/`جزئی` + profanity `ان` len 2):** `6ce319f` sends `chat_template_kwargs:{"enable_thinking":false}` and uses `kb/hurtlex_allowlist.json` (15 lemmas) plus `check_profanity_fa` `len>2` and `risk/scorer.py` (PII 0.90, injection 0.85, toxicity/hate 0.80) + `observability.py` + `semantic/{toxicity,hate,intent}.py` (Ghadeer mmBERT F1 0.94 Persian, lazy). Before fix, RAG prompt with KB context `درخواست حذف` was `hate:حذف`, `جدول نوع تماس` as `hate:مهم`, `تفاوت شرکت...` as `profanity:ان`, 6 expected answers as `hate:ضعیف`, `سلام خسته نباشید` as `hate:خسته`, `دلایل کاهش امتیاز...` as `hate:شرح`/`جزئی`, `رتبه چه فرقی...` as `hate:دسته`. After fix, `20/20` KB eval `ok` (was `18/20`), `0/120` input blocked (was `2`), `0/120` output blocked (was `6`), and `6/6` credit + `6/6` user samples all `stop` 5 citations, Persian only, genuine hate/profanity/PII/secret still blocked (26 tests: 15 benign incl. `پستی`/`مهم`/`ضعیف`/`خسته`/`شرح`/`دسته`/`جزئی`, 11 malicious). Baseline `eval/results/baseline.json` `76/82` correct `92.7%` `0 FP` `6 FN` `25ms`.

- **KB Manager:**:** `POST /search/api` → `final_results` after BM25+MiniLM384+RRF+mmarco; `GET /health`/`ready`; `0.0.0.0:8000` (Docker) / `127.0.0.1:8004` (host). DB `977 MiB`, `69 docs`, `2399 chunks` (5 XLSX fail `No valid sheets` vs prod 8291, expected).

- **Orchestrator — FIXED prompt language (was English fallback):** `cdb6e7d` Persian-only system prompt: `شما دستیار هوشمند اعتبارسنجی ایران (ICS) هستید... فقط بر اساس متن‌های [Context]... همیشه به فارسی پاسخ دهید... برای سلام با لحنی دوستانه... منابع را با [1],[2] ارجاع دهید`. Before, out-of-context like `چرا یکی از وام...` and `رتبه چه فرقی...` returned English `The provided context does not contain...`; now all return Persian `بر اساس اطلاعات موجود در پایگاه دانش، پاسخی یافت نشد.` with 5 citations. Handles `سلام` as greeting. Graph `validate_input → retrieve → build_context → guarded_generate → format_response`; `_clean_answer` defensive only; when genuinely blocked, `content_filter` with `citations:[]`, for allowlisted benign citations preserved.

- **Open WebUI:** `0.0.0.0:13000:8080`, `OPENAI_API_BASE_URL=http://orchestrator:8100/v1`, needs `GET /v1/models` (implemented).

## Samples

### 1. Raw Gemma (clean, via `enable_thinking:false`)

```bash
curl -s http://127.0.0.1:18000/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL","messages":[{"role":"user","content":"سلام"}],"temperature":0,"max_tokens":50,"chat_template_kwargs":{"enable_thinking":false}}' | jq .choices[0].message.content
# → "سلام! چطور می‌توانم به شما کمک کنم؟"  has_unused False
```

### 2. KB retrieval

```bash
curl -s http://127.0.0.1:8004/search/api -H 'Content-Type: application/json' \
  -d '{"query":"اعتبارسنجی چیست","top_k":3}' | jq .final_results[0].content_preview
```

### 3. Guardrails checks

```bash
# Input allowed (was blocked before allowlist for KB context)
curl -s http://127.0.0.1:8200/v1/rails/check -H 'Content-Type: application/json' \
  -d '{"stage":"input","text":"درخواست حذف سابقه منفی قدیمی از گزارش اعتباری","request_id":"t"}' | jq .
# → {"allowed":true}

# Output blocked for true hate (not allowlisted)
curl -s http://127.0.0.1:8200/v1/rails/check -H 'Content-Type: application/json' \
  -d '{"stage":"output","text":"این فرد حرامزاده است","request_id":"t"}' | jq .
# → {"allowed":false,"categories":["hate"],"reason":"پاسخ حاوی محتوای نامناسب است. (hate:حرامزاده)"}
```

### 4. RAG — previously failing, now fixed (6/6)

```bash
# Failing query (was hate:حذف → 0 citations, now 5)
curl -s http://127.0.0.1:8100/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"چگونه می‌توانم گزارش اعتباری خود را دریافت کنم؟"}],"temperature":0,"max_tokens":500}' | jq .
# → {"choices":[{"message":{"content":"با توجه به متن ارائه شده، اطلاعات کافی... امکان اخذ گزارش اعتبارسنجی وجود ندارد [1],[2],[3]."},"finish_reason":"stop"}],"rag":{"citations":[5]}}

# 5 more that now pass (all stop, 5 citations, no <unused>):
for q in "اعتبارسنجی چیست" "امتیاز اعتباری چگونه محاسبه می‌شود؟" "چگونه می‌توانم درخواست حذف سابقه منفی قدیمی از گزارش اعتباری شرکت را ثبت کنم؟" "بخشی از اطلاعات اعتباری من ناقص است، چگونه اصلاح کنم؟" "تامین مالی از طریق تسهیلات بانکی چگونه انجام می‌شود؟"; do
  curl -s http://127.0.0.1:8100/v1/chat/completions -H 'Content-Type: application/json' \
    -d "{\"model\":\"gemma-4-31b\",\"messages\":[{\"role\":\"user\",\"content\":\"$q\"}]}" | jq -c '{q:$q, finish:.choices[0].finish_reason, citations:(.rag.citations|length)}'
done
# All → finish stop, citations 5
```

### 5. Open WebUI

Open `http://91.108.80.253:13000` (or `http://localhost:13000` via `ssh -p 24044 -L 13000:localhost:13000 root@ssh9.vast.ai`) → chat with any above Persian question → answer with citations `[1][2]` (max 2 since 2026-09-09).

## Agent Behaviour & Benchmark Report (2026-09-09)

Full interactive version with plots: [`docs/benchmark-report/`](docs/benchmark-report/) (GitHub Pages — enable Pages from `/docs` in repo settings).

**Method.** All 120 questions from `components/knowledgebase/kb-manager/data/test_questions.json` (20 underlying topics × 6 wording formats: `verbatim, paraphrase, reworded, typo, conversational, keyword_only` — same information, different wording) were asked to the live agent (`POST :8100/v1/chat/completions`, temp 0). For each answer we measured cosine similarity to the ground-truth `expected_answer` with the KB embedding model (`paraphrase-multilingual-MiniLM-L12-v2`), citation counts, and finish reasons. A second pass used Gemma itself as LLM-judge (question + ground truth + agent answer → 1–5 scores for faithfulness/correctness/tone/citation + pass/fail). Three parallel analysis agents audited faithfulness, citations/tone, and wording robustness. Scripts: `eval/run_llm_answer_benchmark.py`, `eval/run_llm_judge.py`, `eval/make_plots.py`, `eval/build_report_site.py`.

**Results (120 questions, 0 errors).**

| metric | v2 Q4 pre-tweak | v3 Q4 tweaked prompt | v4 Q8 tweaked prompt |
|---|---|---|---|
| mean similarity | 0.602 | 0.621 | 0.620 |
| median similarity | 0.685 | 0.691 | 0.675 |
| sim > 0.5 | 76% | 79% | 78% |
| sim > 0.7 | 43% | 44% | 43% |
| mean / max citations | 1.44 / 2 | 1.62 / 2 | 1.62 / 2 |
| answers citing ≤ 2 | 100% | 100% | 100% |
| finish `stop` | 120/120 | 120/120 | 120/120 |
| judge pass rate | 49% | 47% | 45% |
| judge faithfulness / correctness / tone / citation | 4.08 / 3.21 / 4.86 / 4.98 | 3.77 / 3.24 / 4.83 / 4.94 | 3.65 / 3.14 / 4.90 / 4.95 |

![similarity distribution](eval/results/plots/similarity_hist_v4.png)
![wording robustness](eval/results/plots/format_means_v4.png)
![citation counts](eval/results/plots/citations_v4.png)
![Q8 vs Q4 per-question similarity](eval/results/plots/v3-vs-v4.png)

**QA samples (live, Persian).**

- Q: `سلام` → A: `سلام، در خدمت شما هستم. چگونه می‌توانم به شما کمک کنم؟` (1 citation, stop)
- Q: `اعتبارسنجی چیست؟` → A: `اعتبارسنجی فرآیندی است که در آن از داده‌های اعتباری برای تحلیل ریسک، تعیین امتیاز اعتباری و ارائه خدمات مشاوره‌ای استفاده می‌شود [2]…` (2 citations, stop)
- Q: `امتیاز اعتباری چگونه محاسبه می‌شود؟` → A: `محاسبه امتیاز اعتباری بر اساس ترکیبی از عوامل مختلف صورت می‌گیرد… در محاسبه امتیاز چک، سوابق مربوط به چک‌ها نقش تعیین‌کننده‌ای دارند [3]…` (1 citation, stop)
- Q: `چگونه می‌توانم درخواست حذف سابقه منفی قدیمی از گزارش اعتباری شرکت را ثبت کنم؟` → A: `سوابق منفی تا مدت پنج سال در سیستم باقی می‌مانند و پس از گذشت این بازه زمانی، به‌طور خودکار حذف می‌شوند [1]…` (1 citation, stop)
- Q: `ببخشید، مسئولیت بانک‌ها در قبال گزارش اعتباری چیست؟` → A (no سلام-misuse): `مسئولیت بانک‌ها در فرآیند اعتبارسنجی شامل موارد زیر است… [1]…` (2 citations, stop)
- Q: `تفاوت رتبه اعتباری با امتیاز اعتباری چیست؟` → A: `رتبه اعتباری: معیارهای پذیرش… در اختیار هر بانک می‌باشد [2]…` (2 citations, stop)

**Findings.**

- *Faithfulness/correctness.* Dominant failure is **false abstention** (~18% pre-tweak: `پاسخی یافت نشد` despite 5 retrieved chunks); no بله↔خیر polarity flips — failures are omission, not inversion. Mid-range answers sometimes pad with retrieved-but-unasked bullets. One verified drift: for `محکومیت غیرمالی…` the agent generalized a check-score chunk into `محکومیت‌های مالی تأثیری بر امتیاز چک ندارند`, contradicting the ground truth (`فقط محکومیت‌های مالی… درج می‌شود`).
- *Citations.* 100% of answers cite ≤ 2; `format_response` now returns **only chunks actually referenced `[n]`** in the text (fallback: top-1). No invalid markers (`[0]`/`[6+]`); one pre-tweak answer wrote 3 markers in text while metadata correctly truncated to 2 — fixed by a hard max-2 prompt rule.
- *Tone/identity.* Persian-only, professional, intro + 1–3 points + closing. The agent answers as the Iranian credit scoring company AI agent (`شما دستیار هوشمند رسمی شرکت اعتبارسنجی ایران…`). Greeting rule tightened (`ببخشید` ≠ سلام).
- *Wording robustness.* `reworded` weakest (mean ~0.55–0.57, 30% < 0.5), `keyword_only` strongest (~0.65). Retrieval always returns 5 chunks — failures come from 5 distractors, not empty retrieval. Fix applied: light Persian normalization + politeness-filler strip in `retrieve.py` before KB search.
- *Guardrails.* Benchmark found 2 false positives, fixed per repo pattern: `profanity:کردن` (bare verb removed from `persian_swear.json`; vulgar phrases `کس کردن`/`شق کردن` still blocked) and `hate:پلیس` (allowlisted — police records are a legit credit data source). Blocked answers 5/120 → 0/120; genuine vulgar still blocked.
- *Q8 vs Q4.* The bigger model (`UD-Q8_K_XL`, 35 GB, 39.7 GB VRAM) changes **nothing measurable** (mean 0.621 → 0.620): the pipeline is retrieval-bound, not model-bound. Q4 remains the efficient choice.
- *Memory.* The agent is **stateless**: it does not remember previous turns, neither across requests nor within multi-turn `messages` (only the latest user message becomes the query). Verified in Persian (`اسم من علی است…` → `اسم من چیست؟` → `پاسخی یافت نشد`). Short-term history is not implemented in the MVP graph.

Reproduce: `python eval/run_llm_answer_benchmark.py --out eval/results/llm_answer_benchmark_v4.json` → `python eval/run_llm_judge.py eval/results/llm_answer_benchmark_v4.json --out eval/results/llm_judge_v4.json` → `python eval/make_plots.py …` → `python eval/build_report_site.py`.

## Reranker backbones & shootout (2026-09-12, running)

The pipeline is retrieval-bound (failures = distractor chunks, not empty retrieval), so the reranker is the highest-leverage model change. Candidates, all local CPU (see KB README for the full table + loader notes):

| Model | Params | License | Note |
|---|---|---|---|
| `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (current default) | 118M | Apache 2.0 | baseline |
| `BAAI/bge-reranker-v2-m3` | 568M | MIT | m3 tops FaMTEB Persian rerank |
| `jinaai/jina-reranker-v3` | 0.6B | Apache 2.0 | (v2 skipped: CC-BY-NC) |
| `Qwen/Qwen3-Reranker-0.6B` / `4B` | 0.6B / 4B | Apache 2.0 | FlagEmbedding LLM head |
| `BAAI/bge-reranker-v2-gemma` | 2.5B | Apache 2.0 | biggest SOTA in scope |
| MiniCPM-layerwise / GTE-multilingual | 2.7B / 300M | Apache 2.0 | blocked (transformers-5 / rope bugs, documented in KB README) |

Method: massive retrieval benchmark — all 800 QA pairs from `kb-manager/kb_manager/evaluation/datasets/eval_clean.json` (gold `expected_chunk_ids`) × every backbone (pool 30, top_k 5), parallel in-process CPU workers (`/tmp/opencode/bench_backbone.py`), hit/MRR/latency + ranx metrics → `eval/results/reranker_benchmark_*` + plots. Winner becomes the new default. Select manually anytime via `KB_RERANKER_MODEL`.

## Done vs Pending

### Done ✓

- [x] **Branches** `vast-gemma4-migration` on parent + 4 submodules, pinned and pushed
- [x] **Environment** validated (503 Gi RAM, 2× RTX 6000 Ada, CUDA 13.2, no proxy, Docker 29.7.2 unprivileged → host venv fallback)
- [x] **KB** ingest `977 MiB` `2399 chunks` `69 docs`, `search/api` hybrid retrieval verified, `POST /search/api` on `8004` returns Persian `final_results`
- [x] **Guardrails** deterministic Persian rails (injection, jailbreak `دان` word-boundary, HurtLex, profanity, out-of-scope), `0.0.0.0:8200` + `host-gateway` to `18000`, `LLM_BASE_URL` alias, `GET /health`/`ready`
- [x] **Orchestrator** LangGraph 5 nodes, `MAX_CHUNKS 3` `MAX_CHARS 4000`, `upstream_llm_model` env, `max_tokens 512`, `GET /v1/models` for Open WebUI, `0.0.0.0:8100`
- [x] **Gemma source fix** — built `llama.cpp 0f3a71b` at `/opt/llama-new` (`--no-mmproj --jinja`), `supervisorctl stop llama` + manual `LD_LIBRARY_PATH=... /opt/llama-new/bin/llama-server --port 18000 ...` (pid `64871` → now `80957`), verified 5 prompts `has_unused False`
- [x] **Control-token filter** — `_clean_gemma_output` / `_clean_answer` as defensive (now not masking, source is clean)
- [x] **HurtLex allowlist** — `kb/hurtlex_allowlist.json` **15 lemmas** (`حذف,بخشی,تامین مالی,اشتغال,پست,پستی,مصرف,هدف,نادرست,مهم,ضعیف,خسته,شرح,دسته,جزئی`) with evidence from 30+120 audit (v7 `2077` chunks); `actions.py` `load_hurtlex_allowlist()` + `check_hurtlex_fa` skips allowlisted, logs `HurtLex match`, `check_hurtlex_fa_strict` kept, `check_profanity_fa` now `len>2` (fixes `ان` on KB chunk `اثر ان را`); **26 tests** `test_hurtlex_allowlist.py` (15 benign incl. `پستی`/`مهم`/`ضعیف`/`خسته`/`شرح`/`دسته`/`جزئی` + 11 malicious `حرامزاده`/`احمق`/`آشغال`/`خائن`/`PII`/`secret`) all pass; RAG **20/20 `ok`** (was `18/20`), `0/120` input blocked (was `2`), `0/120` output blocked (was `6`), `eval/results/baseline.json` `76/82` `0 FP` `25ms`
- [x] **Prompt & orchestrator** — `cdb6e7d` Persian-only `شما دستیار هوشمند...` (`MAX_CHUNKS 5` `6000 chars` for v7 `2077` chunks); fixes English fallback `The provided...` → Persian `بر اساس اطلاعات موجود...` for `چرا یکی از وام...`/`رتبه چه فرقی...`; `6/6` user samples + `7` v7 samples all `stop` 5 citations Persian, no `hate:دسته`
- [x] **Compose** `compose.mvp.yml` (no `gemma-manager`, only `13000` public, `host-gateway`), `deploy/docker-compose.vast.yml` overlay, host venvs verified (`8200` `107731`, `8100` `106583`, `8004` `100146` v7)
- [x] **KB v7** — `b1bb648` → `8b8f6e5` (`kb-source 1ef3b4b`, `1405-05-31` 34 docs, `data/kb_1405.db` `986M` `2077` chunks: `585 QA`/`982 body`/`499 reason_detail`/`11 parent`, `TestQuestions_IVA` `15`); `eval/kb_rag_evaluation_20samples.json` + `eval/FINDINGS.md` + `eval/README.md` saved, `0/120` input/output blocked after fix
- [x] **Docs** `docs/VAST_GEMMA4_MIGRATION.md` §15-17 (HurtLex 11→15, Persian prompt v2, 20-sample eval, 6 user samples), `docs/RUNBOOK_VAST.md` Known Issues (allowlist 15), `docs/GUARDRAILS_V2_PLAN.md` (risk scoring, observability, semantic interface, thresholds, rollback), `README` Status/Samples/Verification, `eval/` framework (`5` datasets `82` samples, `baseline.json`)
- [x] **Public URL** `http://91.108.80.253:13000` → `0.0.0.0:13000` verified `curl 127.0.0.1:13000` 200, `ss -tlnp` shows `0.0.0.0:13000`
- [x] **Commits** parent `5e06a50` → `9ecdbb4` (guardrails `5c28940`→`6ce319f` 15 lemmas + `cdb6e7d` orchestrator + `470dd9f` KB `8b8f6e5` + `eval` framework), guardrails `6ce319f` (15 lemmas, risk/semantic), orchestrator `cdb6e7d`, KB `8b8f6e5`/`1ef3b4b`, server-setup `5d5a7e4` — all pushed to `main` `9ecdbb4` and `vast` `fdfff91`→`f780167`, no force-push

### Pending ⏳

- [ ] **Make `llama-new` persistent** — currently `nohup` manual (`64871` → `80957`), `supervisorctl status llama` is `STOPPED`. Need `supervisor` to exec `/opt/llama-new/bin/llama-server` with `LD_LIBRARY_PATH=/opt/llama-new/lib:/usr/local/cuda/lib64` and `LLAMA_ARGS="--temp 0.2 --no-mmproj --jinja --port 18000 --ctx-size 8192"`, then `supervisorctl start llama` and verify `0.0.0.0:18000` is `0f3a71b`.
- [ ] **Docker privileged** — this Vast host is unprivileged (`unshare: operation not permitted`, `iptables: Permission denied`); `docker run` fails even with `vfs --iptables=false`. Need privileged host or `host` network fallback documented in `RUNBOOK`.
- [ ] **KB completeness** — 5 XLSX fail `No valid sheets` → `2399` vs prod `8291`; `dense_embeddings.npz` is git-ignored artifact, `pgvector` vs `sqlite` parity.
- [ ] **Vast port mapping** — `13000` not in `vastai show instance --raw` `ports` (only `22→24044,8000→32221,8080→22341,1111→17547`); currently reachable via host `0.0.0.0:13000` but should be added to instance `ports` or documented as `8080→22341` fallback.
- [ ] **HurtLex coverage** — allowlist is minimal (8); future false positives (e.g., other `hurtlex_fa_conservative.json` entries like `نادرست` was added in Phase 5) should be audited via same 30-text script; consider `hurtlex_allowlist_output.json` vs `input`.
- [ ] **Orchestrator fallback cleanup** — `guarded_generate` generic fallback `متأسفم، مدل پاسخ...` is now defensive only; decide if duplicate fallback in `format_response` should be removed if guardrails owns concern, and add regression test for `<unused`.
- [ ] **Merge to `main`** — do not merge until `llama-new` is supervisor-persistent and `13000` mapping is explicit; then `git switch main && git merge vast-gemma4-migration` and retag pins.

## Verification

```bash
# Gemma raw clean
curl -s http://127.0.0.1:18000/v1/models | jq .data[0].id
for p in "سلام" "Hello" "اعتبارسنجی چیست" "چگونه گزارش اعتباری خود را دریافت کنم؟" "یک پاسخ کوتاه فارسی بده"; do
  curl -s http://127.0.0.1:18000/v1/chat/completions -H 'Content-Type: application/json' \
    -d "{\"model\":\"unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL\",\"messages\":[{\"role\":\"user\",\"content\":\"$p\"}],\"temperature\":0,\"max_tokens\":50,\"chat_template_kwargs\":{\"enable_thinking\":false}}" | python3 -c "import json,sys; j=json.load(sys.stdin); c=j['choices'][0]['message']['content']; print('$p', 'has_unused', '<unused' in c, 'len', len(c))"
done

# Guardrails allowlist (15 lemmas, 26 tests) + baseline
PYTHONPATH=components/guardrails/src /tmp/guard-venv/bin/python -m pytest components/guardrails/tests/test_hurtlex_allowlist.py -v  # 26 passed
PYTHONPATH=components/guardrails/src /tmp/guard-venv/bin/python /workspace/Work_Credit-RAG_Phase1/eval/run_guardrails_eval.py  # → 76/82 0 FP 25ms, baseline.json
curl -s http://127.0.0.1:8200/v1/rails/check -H 'Content-Type: application/json' -d '{"stage":"input","text":"حذف","request_id":"t"}' | jq .allowed # false strict, true with allowlist via guarded_completion
curl -s http://127.0.0.1:8200/v1/rails/check -H 'Content-Type: application/json' -d '{"stage":"output","text":"حرامزاده","request_id":"t"}' | jq .allowed # false

# RAG E2E
curl -s http://127.0.0.1:8100/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"gemma-4-31b","messages":[{"role":"user","content":"چگونه می‌توانم گزارش اعتباری خود را دریافت کنم؟"}]}' | jq '{finish:.choices[0].finish_reason, citations:(.rag.citations|length), content:.choices[0].message.content}'
# → finish stop, citations 5
```

## UI panels

Two observability UIs run alongside the pipeline (both on the `vast-deploy` branch; no Docker needed):

- **Open WebUI** (`0.0.0.0:13000`, the chat frontend) — backend `OPENAI_API_BASE_URL=http://127.0.0.1:8100/v1`. Start: `DATA_DIR=/tmp/webui-data /tmp/webui-venv/bin/open-webui serve --host 0.0.0.0 --port 13000`.
- **Langfuse v2** (`0.0.0.0:3001`, real trace UI built from source, Postgres-backed) — every orchestrator request lands as a trace (`input` → `output`, keyed by `X-Request-ID`). Setup/run: `bash deploy/vast/langfuse-v2.sh` (seeds admin + project keys into `/tmp/opencode/langfuse.env`, never committed). Point the orchestrator at it via `LANGFUSE_HOST=http://127.0.0.1:3001` + the seeded keys. A lightweight fallback collector (`components/tracing/app.py`, `:3000`, JSONL at `/tmp/langfuse_traces.jsonl`) remains for offline use.
- **LangGraph Studio** (visual graph debugger for the `rag` graph) — serve: `bash deploy/vast/studio.sh` (API on `0.0.0.0:2024`), then open `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`. Studio run inputs must include `request_id`, e.g. `{"request_id":"studio-001","messages":[{"role":"user","content":"سلام"}]}`.

On Vast.ai, ports are NAT-fixed at instance creation, so reach all panels via SSH tunnels, e.g. `ssh -p <ssh_port> root@<ssh_host> -L 13000:localhost:13000 -L 3001:localhost:3001 -L 2024:localhost:2024`. Full startup order (postgres → Gemma → KB → guardrails → collector → orchestrator → WebUI): `bash deploy/vast/start.sh`.

## Ownership rule

- hardware, model lifecycle, infra → Server Setup
- ingestion, retrieval, reranking → Knowledgebase
- policy, guarded Gemma → Guardrails
- graph state, adapters, public API → Orchestrator
- pins, integrated startup, E2E → this parent

Do not duplicate component implementation in the parent.

## Updating a submodule

```bash
cd components/orchestrator
git switch main && git pull --ff-only
cd ../..
git add components/orchestrator
git commit -m "chore: advance orchestrator submodule"
```

Always run contract and end-to-end tests before advancing a production pin.

## License

See [LICENSE](LICENSE). Each submodule may also declare its own license and dependency obligations.

## Links

- Runbook (public, startup, env, ports, troubleshooting): [docs/RUNBOOK_VAST.md](docs/RUNBOOK_VAST.md)
- Migration log (discovery, 14 inspection items, fixes, verification, HurtLex audit): [docs/VAST_GEMMA4_MIGRATION.md](docs/VAST_GEMMA4_MIGRATION.md)
- MVP plan and acceptance tests: [docs/MVP_INTEGRATION_PLAN.md](docs/MVP_INTEGRATION_PLAN.md)
- Compose (Vast): [compose.mvp.yml](compose.mvp.yml) + [components/server-setup/deploy/docker-compose.vast.yml](components/server-setup/deploy/docker-compose.vast.yml)
- Guardrails allowlist: [components/guardrails/kb/hurtlex_allowlist.json](components/guardrails/kb/hurtlex_allowlist.json) + [components/guardrails/src/work_rag_guardrails/actions.py](components/guardrails/src/work_rag_guardrails/actions.py)
- Tests: [components/guardrails/tests/test_hurtlex_allowlist.py](components/guardrails/tests/test_hurtlex_allowlist.py) (18 tests), [components/orchestrator/tests](components/orchestrator/tests) (9 tests), [components/knowledgebase/kb-manager/tests](components/knowledgebase/kb-manager/tests) (32 passed)
