---
name: rag-kb
description: >-
  Implements or debugs Work_RAG-KB (kb-manager): hybrid search, EntityList
  supplements, ingest pipeline, dense embeddings. Use when editing
  components/knowledgebase, search.py, dense.py, entity lists, or retrieval bugs.
---

# RAG Knowledgebase skill

## Own only

`components/knowledgebase` → repo `Work_RAG-KB`, branch `master` (also `develop`).

## Entrypoints

| Concern | File |
|---|---|
| Search API | `kb-manager/kb_manager/web/routes/search.py` |
| Dense index | `kb-manager/kb_manager/dense.py` |
| Pipeline / EntityList write | `kb-manager/kb_manager/pipeline/orchestrator.py` |
| Models | `kb-manager/kb_manager/models/database.py` (`EntityList`) |
| Embedder | `kb-manager/kb_manager/embedder/sentence_transformer.py` |
| App | `kb-manager/kb_manager/web/app.py` |

## Correct dense encode pattern

```python
# BAD (current tip — always False; DenseSemanticIndex has no public .model)
if hasattr(dense, "model") and dense.model is not None:
    q_emb = dense.model.encode([query], normalize_embeddings=True)[0]

# GOOD
qv = dense._encode([query])[0]  # uses _ensure_model() internally
# or helper:
def _dense_encode(dense, texts: list[str]):
    return dense._encode(texts)
```

Sites to fix on tip: `search.py` ~768, ~789, ~1045 (step-8 entity inject).

## Supplement tool (desired)

Orchestrator expects `POST /search/supplement` with `{query, threshold}` (default 0.4), returning entity list rows ranked by embedding over **list_name + description**. Current tip only does step-8 inject inside `/search/api` at cosine > 0.6 and may no-op due to `.model` bug. Restore the route from commit `d040c63` and wire embeddings via `_encode` / `SentenceTransformerEmbedder`.

## Pipeline note

When constructing `PipelineOrchestrator`, pass embedder so `EntityList.description_embedding` is populated — empty embeddings disable inject/supplement.

## Verify

```bash
cd components/knowledgebase/kb-manager
pytest -q
curl -s http://127.0.0.1:8000/search/api -H 'Content-Type: application/json' \
  -d '{"query":"اعتبارسنجی چیست","top_k":3}' | jq '.injected_entities|length'
# after restore:
curl -s http://127.0.0.1:8000/search/supplement -H 'Content-Type: application/json' \
  -d '{"query":"MTX1","threshold":0.4}' | jq .
```
