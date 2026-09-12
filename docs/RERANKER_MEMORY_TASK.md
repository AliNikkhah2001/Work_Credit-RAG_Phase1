# Task: reranker benchmark + conversation memory (branch `feat/reranker-memory`)

## Goal
1. Compare cross-encoder rerankers (incl. biggest SOTA) on our Persian credit KB and pick the winner.
2. Add stateless conversation memory: history-aware query rewrite + last-2-turns prompt grounding.

## Motivation
- Pipeline is retrieval-bound (120-q benchmark: failures = distractor chunks retrieved; Q8-vs-Q4 proved LLM size irrelevant). Reranker upgrade is the highest-leverage model change.
- Agent is stateless today: follow-ups like «دکتری کجا بوده حالا» (after asking about رضا قاسم‌پور) fail — only the last message reaches KB search and the prompt (`validate_input` picks `messages[-1]`; `build_context` builds system + 1 question).

## Reranker candidates (all → /tmp/hf_clean)
| Model | Params | License |
|---|---|---|
| cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 (baseline, cached) | 118M | Apache 2.0 |
| BAAI/bge-reranker-v2-m3 | 568M | MIT |
| BAAI/bge-reranker-v2-gemma (biggest SOTA) | 9B | Apache 2.0 |
| BAAI/bge-reranker-v2-minicpm-layerwise | 2.7B | Apache 2.0 |
| jinaai/jina-reranker-v3 | 0.6B | Apache 2.0 (v2 skipped: CC-BY-NC) |
| Alibaba-NLP/gte-multilingual-reranker-base | ~300M | Apache 2.0 |
| Qwen/Qwen3-Reranker-0.6B + Qwen/Qwen3-Reranker-4B | 0.6B/4B | Apache 2.0 |

## KB code changes (`Work_RAG-KB`, branch `feat/reranker-memory`)
- `KB_RERANKER_MODEL` env (default: current mmarco model — behavior unchanged).
- `KB_RERANK_POOL` depth flag (default preserves `min(50, top_k*3)`).
- Model registry: standard `CrossEncoder` path (MiniLM, BGE-m3, GTE) + special-case loaders (Jina-v3 `trust_remote_code`, Qwen3, Gemma-9B) with graceful fallback + docs.
- Rerank latency logging per call (+ `rerank_ms` in search steps).

## Memory code changes (`Work_RAG-Orchestrator`, branch `feat/reranker-memory`)
- History-aware query rewrite via Gemma (direct `:18000`, `enable_thinking:false`) when history exists; single-turn bypass (120-q behavior unchanged).
- Last 2 exchanges into prompt (cap ~1500 chars of the 6000 budget).
- `rewritten_query` in state + audit; `query-rewrite` Langfuse span; history echoed in retrieve span.
- Guardrails keeps checking the raw current message. No checkpointer, no schema migration.
- Regression test: 3-turn coreference (مدیر → رضا قاسم‌پور → «دکتری کجا بوده حالا» must resolve).

## Benchmark protocol
1. Screen all variants on ~25 known-hard questions (false abstentions + sim<0.5 from v4), pool 30.
2. Full 120-q + LLM-judge on top-2 + latency table → winner becomes default.
3. 120-q no-regression run for memory changes.

## Branches
- Parent: `feat/reranker-memory` (this doc + pins at the end).
- `Work_RAG-KB`: `feat/reranker-memory` (from `b7c23c7`).
- `Work_RAG-Orchestrator`: `feat/reranker-memory` (from `cee7a54`).
