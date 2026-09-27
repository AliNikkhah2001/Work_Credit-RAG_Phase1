# Fact-check KB submodule (@general subagent)

Session: `ses_f69bd00e1ffeZpMuACZP7ACDqh`
Messages: 6


## [USER]

You are Agent 2c (Technical Accuracy Auditor) in /workspace/Work_Credit-RAG_Phase1/components/knowledgebase. Validate claims in kb-manager/README.md, kb-source/README.md, kb-manager/versions/v1/README.md, versions/v2/README.md, versions/v4_retrieval/README.md against code in kb-manager/kb_manager/ (config.py defaults, web/routes/search.py endpoints, models/database.py tables, query_reform.py) and kb-source/ layout.

Check: API endpoints + ports (8000), env vars (KB_DB_URL, KB_WEB_HOST/PORT), embedding model IDs, reranker model IDs, chunking params (chunk_size/top_k defaults), DB tables (documents/chunks/versions/jobs/retrieval_logs), retrieval pipeline stages (dense/BM25/RRF/rerank — which are real vs aspirational), sqlite vs postgres claims, version-dir status (active vs archived).

Return ONLY: VERIFIED (file:line), INCORRECT (says vs is), MISSING. Compact. No file writes.


## [ASSISTANT]

(tool: read)


## [ASSISTANT]

(tool: glob)


## [ASSISTANT]

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)


## [ASSISTANT]

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: glob)


## [ASSISTANT]
