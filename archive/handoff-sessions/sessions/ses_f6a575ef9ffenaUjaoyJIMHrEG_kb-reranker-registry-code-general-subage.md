# KB reranker registry code (@general subagent)

Session: `ses_f6a575ef9ffenaUjaoyJIMHrEG`
Messages: 40


## [USER]

Implement reranker configurability in the KB repo. Work ONLY in /workspace/Work_Credit-RAG_Phase1/components/knowledgebase (branch `feat/reranker-memory`, base b7c23c7). Do NOT touch other repos. Do NOT restart services. Commit on the branch when done (identity is configured globally); do NOT push.

First READ: kb-manager/kb_manager/reranker.py, kb-manager/kb_manager/config.py, kb-manager/web/routes/search.py (rerank section ~lines 380-430), kb-manager/kb_manager/dense.py (first 40 lines, for env-var conventions).

Implement:
1. `KB_RERANKER_MODEL` env var (read in config.py with default `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`; thread it to `get_reranker(model_name=...)` and the `_RERANKER_MODEL` usage in search.py). Default behavior must be byte-identical to today.
2. `KB_RERANK_POOL` env (int, default 0 = keep current `min(50, top_k*3)` logic; if >0 use it as the candidate pool cap instead).
3. Model registry in reranker.py: a dict mapping known ids {mmarco-MiniLM, `BAAI/bge-reranker-v2-m3`, `Alibaba-NLP/gte-multilingual-reranker-base`, `jinaai/jina-reranker-v3`, `Qwen/Qwen3-Reranker-0.6B`, `Qwen/Qwen3-Reranker-4B`, `BAAI/bge-reranker-v2-gemma`, `BAAI/bge-reranker-v2-minicpm-layerwise`} to loader specs: {needs_trust_remote_code: bool, loader: 'crossencoder'|'qwen'|'gemma'|'manual'}. Implement the standard `CrossEncoder` path for all (it handles BERT-like + Qwen? if unsure, implement crossencoder + trust_remote_code passthrough, and raise a CLEAR NotImplementedError with instructions for 'gemma'/'qwen' custom heads — do not fake support). Jina-v3 must pass trust_remote_code=True.
4. Rerank latency: time each rerank() call, log at info (`rerank model=... n=... ms=...`), and add `rerank_ms: float = 0.0` to the SearchSteps pydantic model + populate it.
5. Verify: `python -c "import kb_manager.web.app"` with cwd=kb-manager (set HF_HOME=/tmp/hf_clean, HF_HUB_CACHE=/tmp/hf_clean, HF_HUB_OFFLINE=1), plus a unit check that registry resolves every id without downloading (mock or inspect-only, no network model loads).

Commit message: `feat(kb): KB_RERANKER_MODEL registry + KB_RERANK_POOL + rerank latency logging`. Report: files changed, verification outputs, anything deferred (e.g. gemma custom head).


## [ASSISTANT]

(tool: read)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: read)

(tool: read)

(tool: read)


## [ASSISTANT]

(tool: grep)

(tool: read)


## [ASSISTANT]

(tool: glob)


## [ASSISTANT]

(tool: read)


## [ASSISTANT]

(tool: grep)


## [ASSISTANT]

(tool: read)

(tool: read)


## [ASSISTANT]

(tool: glob)

(tool: grep)


## [ASSISTANT]

(tool: grep)


## [ASSISTANT]

(tool: grep)

(tool: bash)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: edit)


## [ASSISTANT]

(tool: read)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: grep)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

(tool: bash)


## [ASSISTANT]

Done. Committed `60363d9` on `feat/reranker-memory` (parent `b7c23c7`), not pushed. Only the KB repo touched; no services restarted.

## Files changed
- **`kb-manager/kb_manager/reranker.py`** — `RERANKER_REGISTRY` (8 ids → `{loader, needs_trust_remote_code}`); `get_reranker_model_name()` / `get_rerank_pool()` env readers; `resolve_reranker_spec()` (unknown ids fall back to crossencoder + warning); `_ensure_model()` passes `trust_remote_code` through to both `AutoTokenizer` and `AutoModelForSequenceClassification`, and raises clear `NotImplementedError` (with implementation instructions + `KB_RERANKER_MODEL` workaround) for `qwen`/`gemma`/`manual` loaders *before* importing transformers; `rerank(..., pool=None)` (None→env, 0→legacy `min(top_k*3, len)`, >0→cap), times each call, logs `rerank model=... n=... ms=...` at info, records `self.last_rerank_ms`; `get_reranker(model_name=None)` defaults to env.
- **`kb-manager/kb_manager/config.py`** — new `RerankerConfig` (`model_name`, `pool`), added to `AppConfig`; `load_config()` reads `KB_RERANKER_MODEL` (default `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`) and `KB_RERANK_POOL` (default 0, invalid→0 via `_int_env`).
- **`kb-manager/kb_manager/web/routes/search.py`** — `_RERANKER_MODEL` env-aware (same default), `_RERANKER_TOP_K=50` kept as legacy cap; `_build_index()` uses live env model; `search_knowledge_base()` slices pre-pool by `KB_RERANK_POOL` when >0 else 50, passes `pool` through, populates new `SearchSteps.rerank_ms: float = 0.0`.

## Verification
- `python -c "import kb_manager.web.app"` (cwd=kb-manager, HF offline env, `/tmp/kb-venv`): **OK** (`KB Manager`).
- Offline unit check (no model downloads — stubbed `transformers`/`torch`, `HF_HUB_OFFLINE=1`): registry resolves all 8 ids with correct loader/trust (jina-v3 `trust_remote_code=True` verified in recorded `from_pretrained` kwargs); unknown id → crossencoder fallback; qwen×2/gemma/minicpm raise `NotImplementedError` mentioning `KB_RERANKER_MODEL`; pool caps 30 (legacy default and explicit 0) / 7 / 100-for-200; `KB_RERANK_POOL=5` honored, `"bogus"`→0; empty input → `[]`, `0.0 ms`; info log matches `rerank model=... n=... ms=...`; env threading verified through `get_reranker()`, search helpers, and `load_config()`; defaults byte-identical (`_RERANKER_MODEL`, `_RERANKER_TOP_K=50`, factory default, config defaults); `SearchSteps.rerank_ms` defaults `0.0`. **ALL UNIT CHECKS PASSED.**
- Note: two of my check-script assertions were initially wrong (expected last log line `n=7` when last call was `pool=200`; expected 10 results from a pool-7 call) — implementation behaved correctly in both cases; corrected and re-ran green.

## Deferred
- Custom scoring heads for `Qwen3-Reranker-0.6B/4B` (causal-LM yes/no head), `bge-reranker-v2-gemma` (Gemma head), `bge-reranker-v2-minicpm-layerwise` (layer selection) — intentionally raise `NotImplementedError` with pointers; not faked.
- No live end-to-end search run (would load the real cross-encoder and hit
…[truncated]…
