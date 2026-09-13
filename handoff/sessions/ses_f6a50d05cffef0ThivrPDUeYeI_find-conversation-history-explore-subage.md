# Find conversation history (@explore subagent)

Session: `ses_f6a50d05cffef0ThivrPDUeYeI`
Messages: 14


## [USER]

Search the workspace /workspace/Work_Credit-RAG_Phase1 for conversation history storage with the RAG agent. Look for: chat history, message stores, memory, checkpointers, LangGraph checkpointer, postgres tables, sqlite files, JSONL logs, tracing files. Check components/orchestrator, components/tracing, components/knowledgebase, components/guardrails, deploy/, data/, contracts/. Return file paths, DB tables, and code references (file:line) for where conversation history is stored and retrieved.


## [ASSISTANT]

(tool: read)


## [ASSISTANT]

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)


## [ASSISTANT]

(tool: glob)

(tool: glob)

(tool: glob)

(tool: glob)

(tool: glob)


## [ASSISTANT]

(tool: glob)

(tool: glob)

(tool: glob)

(tool: glob)

(tool: read)


## [ASSISTANT]

(tool: grep)

(tool: grep)

(tool: grep)

(tool: grep)


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

(tool: read)


## [ASSISTANT]

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)


## [ASSISTANT]

(tool: grep)

(tool: read)

(tool: read)

(tool: grep)


## [ASSISTANT]

(tool: read)

(tool: read)

(tool: read)

(tool: read)


## [ASSISTANT]

(tool: read)

(tool: read)

(tool: glob)

(tool: grep)

(tool: read)


## [ASSISTANT]

(tool: grep)

(tool: read)

(tool: grep)


## [ASSISTANT]

**Conversation-history storage — `/workspace/Work_Credit-RAG_Phase1` — finding: NO persistent RAG history DB. Stateless by design.**

## 1. Core verdict: stateless RAG agent

Client (`Open WebUI :13000`) sends full `messages[]` every `POST :8100/v1/chat/completions`. Orchestrator uses it transiently for rewrite + prompt, never persists.

> `components/orchestrator/src/work_rag_orchestrator/rewrite.py:1-4`:
> `No DB, no checkpointer: WebUI already sends the full messages history`
> `components/orchestrator/src/work_rag_orchestrator/rewrite.py:26-28`: `HISTORY_EXCHANGES=2`, `HISTORY_MAX_CHARS=1500`
> `README.md:204`: `agent is stateless: does not remember previous turns`
> `docs/RERANKER_MEMORY_TASK.md:9`: `Agent is stateless today`
> `eval/build_report_site.py:156`: `stateless ... only latest user message`

`session_id` declared but unused:

* `/workspace/Work_Credit-RAG_Phase1/components/orchestrator/src/work_rag_orchestrator/schemas.py:19` — `session_id: Optional[str]=None` in `ChatCompletionRequest` — never read in `api.py`.

## 2. LangGraph checkpointer — in-memory only, no retrieval across turns

* `/workspace/Work_Credit-RAG_Phase1/components/orchestrator/src/work_rag_orchestrator/graph.py:6` — `from langgraph.checkpoint.memory import MemorySaver`
* `/workspace/Work_Credit-RAG_Phase1/components/orchestrator/src/work_rag_orchestrator/graph.py:61-65` — `compile_graph(): graph.compile(checkpointer=MemorySaver()) # no PostgreSQL checkpointing in MVP`
* `/workspace/Work_Credit-RAG_Phase1/components/orchestrator/src/work_rag_orchestrator/api.py:156` — `config={"configurable":{"thread_id": request_id}}` where `api.py:118` `request_id=x_request_id or uuid4()` — unique per request, never reused → no cross-request replay.
* `/workspace/Work_Credit-RAG_Phase1/components/orchestrator/studio_graph.py:1,8-9` — `no custom checkpointer / LangGraph API handles persistence; graph=create_graph().compile()`
* `/workspace/Work_Credit-RAG_Phase1/components/orchestrator/STUDIO.md:24` — `Thread history (MemorySaver) - replay same thread_id (=request_id)` — dev/Studio only.
* `/workspace/Work_Credit-RAG_Phase1/components/orchestrator/pyproject.toml:19` — `langgraph-checkpoint>=2.0.0` dep, no `postgres` saver used.
* No `PostgresSaver/AsyncPostgresSaver/SqliteSaver` anywhere — grep confirms absent. `README.md:50` explicitly excludes `PostgreSQL LangGraph checkpoints`.

Dev-only LangGraph Studio persistence (not prod):

* `/workspace/Work_Credit-RAG_Phase1/components/orchestrator/.langgraph_api/.langgraph_checkpoint.1.pckl`
* `/workspace/Work_Credit-RAG_Phase1/components/orchestrator/.langgraph_api/.langgraph_checkpoint.2.pckl`
* `/workspace/Work_Credit-RAG_Phase1/components/orchestrator/.langgraph_api/.langgraph_checkpoint.3.pckl`
* `/workspace/Work_Credit-RAG_Phase1/components/orchestrator/.langgraph_api/.langgraph_ops.pckl`
* `/workspace/Work_Credit-RAG_Phase1/components/orchestrator/.langgraph_api/store.pckl`
* `/workspace/Work_Credit-RAG_Phase1/components/orchest
…[truncated]…
