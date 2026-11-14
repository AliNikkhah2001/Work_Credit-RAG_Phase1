---
name: rag-guardrails
description: >-
  Implements or debugs Work_RAG-Guardrails Persian safety rails and guarded
  Gemma gateway. Use when editing components/guardrails, judge, signals, PII,
  or finish_reason / upstream overflow behavior.
---

# RAG Guardrails skill

## Own only

`components/guardrails` → `Work_RAG-Guardrails` `main`.

## Runtime (NeMo removed)

`service.py` + `judge.py` + `signals.py`:

1. Collect deterministic signals (injection, jailbreak, hate, offense, scope, PII, secret)  
2. Adjudicate: Gemma policy judge and/or Mizan System-1 (`GUARD_JUDGE_BACKEND=gemma|mizan|hybrid`)  
3. Fail closed on timeout/error  
4. `secret` hard-blocks; others usually evidence for the judge  
5. Guarded generate proxies upstream with history trim + token cleanup  

## Endpoints

- `POST /v1/rails/check` — input/output stage  
- `POST /v1/chat/completions` — guarded Gemma gateway  
- `/health`, `/ready`, dashboard  

## Gotchas

- Upstream context overflow → return `finish_reason="length"` (valid Literal), never `"error"`  
- Persian PII: normalize digits (`۰۹۱۲…`) before regex  
- Empty judge response must **block**, not allow  
- `trust_env=False` on httpx to `:18000` / `:9000`  
- Production refusals use premade Persian category messages (no internal leak)  

## Verify

```bash
curl -s http://127.0.0.1:8200/v1/rails/check -H 'Content-Type: application/json' \
  -d '{"stage":"input","text":"سلام","request_id":"t"}' | jq .
```
