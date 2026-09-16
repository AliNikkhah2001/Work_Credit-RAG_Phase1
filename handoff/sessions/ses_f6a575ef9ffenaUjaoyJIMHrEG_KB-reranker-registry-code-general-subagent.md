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

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 9707, "input": 9447, "output": 89, "reasoning": 58, "cache": {"write": 0, "read": 113}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 9918, "input": 337, "output": 116, "reasoning": 8, "cache": {"write": 0, "read": 9457}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(tool: read)

(tool: read)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 10287, "input": 355, "output": 219, "reasoning": 0, "cache": {"write": 0, "read": 9713}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(tool: grep)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 14399, "input": 4259, "output": 171, "reasoning": 0, "cache": {"write": 0, "read": 9969}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(tool: glob)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 15358, "input": 1087, "output": 78, "reasoning": 0, "cache": {"write": 0, "read": 14193}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 15472, "input": 187, "output": 68, "reasoning": 0, "cache": {"write": 0, "read": 15217}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(tool: grep)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 21267, "input": 5800, "output": 101, "reasoning": 21, "cache": {"write": 0, "read": 15345}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(tool: read)

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 22677, "input": 1408, "output": 164, "reasoning": 0, "cache": {"write": 0, "read": 21105}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(reasoning: )

(reasoning: )

(reasoning: )

(reasoning: )

(tool: glob)

(tool: grep)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 28635, "input": 2507, "output": 300, "reasoning": 3315, "cache": {"write": 0, "read": 22513}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(tool: grep)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 31603, "input": 6535, "output": 103, "reasoning": 20, "cache": {"write": 0, "read": 24945}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(reasoning: )

(reasoning: )

(reasoning: )

(reasoning: )

(reasoning: )

(tool: grep)

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 38214, "input": 156, "output": 382, "reasoning": 6203, "cache": {"write": 0, "read": 31473}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 39489, "input": 6667, "output": 1197, "reasoning": 24, "cache": {"write": 0, "read": 31601}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 39728, "input": 1256, "output": 215, "reasoning": 0, "cache": {"write": 0, "read": 38257}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-finish", "tokens": {"total": 40891, "input": 343, "output": 1139, "reasoning": 0, "cache": {"write": 0, "read": 39409}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "type": "step-start"})

(reasoning: )

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 41696, "input": 1250, "output": 771, "reasoning": 10, "cache": {"write": 0, "read": 39665}}, "cost": 0})

(patch: {"type": "patch", "hash": "ea212945d45abe1ea5c6beee6ad6fb1e456d1c12", "files": ["/workspace/Work_Credit-RAG_Phase1/components/orchestrator"]})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 42012, "input": 903, "output": 292, "reasoning": 0, "cache": {"write": 0, "read": 40817}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 42336, "input": 323, "output": 300, "reasoning": 0, "cache": {"write": 0, "read": 41713}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 42639, "input": 391, "output": 259, "reasoning": 20, "cache": {"write": 0, "read": 41969}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 42860, "input": 310, "output": 197, "reasoning": 0, "cache": {"write": 0, "read": 42353}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 43053, "input": 275, "output": 169, "reasoning": 0, "cache": {"write": 0, "read": 42609}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 43281, "input": 212, "output": 204, "reasoning": 0, "cache": {"write": 0, "read": 42865}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(reasoning: )

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 43674, "input": 312, "output": 298, "reasoning": 71, "cache": {"write": 0, "read": 42993}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 44066, "input": 449, "output": 368, "reasoning": 0, "cache": {"write": 0, "read": 43249}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 44364, "input": 457, "output": 274, "reasoning": 0, "cache": {"write": 0, "read": 43633}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 44542, "input": 371, "output": 154, "reasoning": 0, "cache": {"write": 0, "read": 44017}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 44902, "input": 293, "output": 336, "reasoning": 0, "cache": {"write": 0, "read": 44273}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(tool: edit)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 45213, "input": 397, "output": 287, "reasoning": 0, "cache": {"write": 0, "read": 44529}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: read)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 45410, "input": 324, "output": 106, "reasoning": 67, "cache": {"write": 0, "read": 44913}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 49612, "input": 4295, "output": 135, "reasoning": 13, "cache": {"write": 0, "read": 45169}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(reasoning: )

(reasoning: )

(reasoning: )

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 54492, "input": 274, "output": 2214, "reasoning": 2611, "cache": {"write": 0, "read": 49393}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(reasoning: )

(reasoning: )

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 56957, "input": 52244, "output": 1431, "reasoning": 993, "cache": {"write": 0, "read": 2289}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(reasoning: )

(reasoning: )

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 58525, "input": 2448, "output": 390, "reasoning": 1174, "cache": {"write": 0, "read": 54513}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(reasoning: )

(reasoning: )

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 59696, "input": 1588, "output": 488, "reasoning": 675, "cache": {"write": 0, "read": 56945}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 61271, "input": 1297, "output": 1354, "reasoning": 139, "cache": {"write": 0, "read": 58481}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: grep)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 61751, "input": 1660, "output": 123, "reasoning": 207, "cache": {"write": 0, "read": 59761}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 62441, "input": 974, "output": 112, "reasoning": 58, "cache": {"write": 0, "read": 61297}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-finish", "tokens": {"total": 62656, "input": 371, "output": 92, "reasoning": 0, "cache": {"write": 0, "read": 62193}}, "cost": 0})


## [ASSISTANT]

(step-start: {"snapshot": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "type": "step-start"})

(reasoning: )

(reasoning: )

(tool: bash)

(step-finish: {"reason": "tool-calls", "snapshot": "ff796a2fc1c6b730112e136df5d429e7a8857c31", "type": "step-finish", "tokens": {"total": 64640, "input": 1918, "output": 166, "reasoning": 107, "cache": {"write": 0, "read": 62449}}, "cost": 0})

(patch: {"type": "patch", "hash": "c1acbc14574f519e39cc81d63cfcf25441bcf403", "files": ["/workspace/Work_Credit-RAG_Phase1/components/knowledgebase"]})


## [ASSISTANT]

(step-start: {"snapshot": "ff796a2fc1c6b730112e136df5d429e7a8857c31", "type": "step-start"})

(reasoning: )

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
- No live end-to-end search run (would load the real cross-encoder and hit the DB); no service restarts per instructions.

(step-finish: {"reason": "stop", "snapshot": "ff796a2fc1c6b730112e136df5d429e7a8857c31", "type": "step-finish", "tokens": {"total": 65717, "input": 536, "output": 893, "reasoning": 47, "cache": {"write": 0, "read": 64241}}, "cost": 0})
