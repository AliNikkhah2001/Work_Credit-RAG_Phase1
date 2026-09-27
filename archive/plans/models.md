# Model Cards — Work Credit RAG Phase 1

> All models are self-hosted. No external API dependencies in production path.

---

## 1. Generation Model (LLM)

### Gemma 4 31B Instruct (Champion)

| Attribute | Value |
|-----------|-------|
| **Model ID** | `unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL` |
| **HF Repo** | `bartowski/google_gemma-4-31B-it-GGUF` |
| **File** | `google_gemma-4-31B-it-UD-Q4_K_XL.gguf` |
| **Size** | ~18.8 GiB |
| **Quantization** | UD-Q4_K_XL (unsloth dynamic 4-bit) |
| **Context** | 8192 tokens |
| **Architecture** | Gemma 2-based, 31B params |
| **License** | Gemma Terms of Use (Google) |
| **Server** | llama.cpp 0.3.0-dev (build 0f3a71b) |
| **Flags** | `--ctx-size 8192 --temp 0.2 --no-mmproj --jinja -ngl 999` |
| **Critical Param** | `chat_template_kwargs:{"enable_thinking":false}` |
| **Port** | :18000 (127.0.0.1 only) |
| **VRAM** | ~22.7/24 GB at ctx 8192 |

**Verification (live):**
```bash
curl -s http://127.0.0.1:18000/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL","messages":[{"role":"user","content":"سلام"}],"temperature":0,"max_tokens":50,"chat_template_kwargs":{"enable_thinking":false}}' \
  | python3 -c "import json,sys; j=json.load(sys.stdin); c=j['choices'][0]['message']['content']; print('has_unused:', '<unused' in c, 'len:', len(c))"
# → has_unused: False, len: 35
```

**Benchmark (Persian 7-task, 50 ex/task, temp 0.0):**
| Task | Accuracy |
|------|----------|
| fa_arc | 0.960 |
| fa_mc | 0.700 |
| fa_math | 0.640 |
| fa_sentiment | 0.820 |
| fa_entail | 0.160 |
| fa_ner | **1.000** |
| fa_rc | 0.360 |
| **Mean** | **0.663** |

**Speed:** 55.7 tok/s (256-token Persian, n_gpu_layers=-1)

---

## 2. Embedding Model

### paraphrase-multilingual-MiniLM-L12-v2

| Attribute | Value |
|-----------|-------|
| **Model ID** | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| **Dimensions** | 384 |
| **Max Seq Len** | 128 (truncated) |
| **License** | Apache 2.0 |
| **Usage** | Dense retrieval in KB Manager |
| **Device** | CPU (default), CUDA configurable via `KB_EMBED_DEVICE` |
| **Batch Size** | 64 |

**Alternative Embeddings (server-setup, not in MVP path):**
| Model | Dim | Port | Status |
|-------|-----|------|--------|
| multilingual-e5-small | 384 | 8001 | live |
| bge-m3 | 1024 | 8002 | live |
| paraphrase-multilingual-MiniLM-L12-v2 | 384 | 8003 | live |

---

## 3. Reranker Models

### Current Default: cross-encoder/mmarco-mMiniLMv2-L12-H384-v1

| Attribute | Value |
|-----------|-------|
| **Model ID** | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` |
| **Params** | 118M |
| **License** | Apache 2.0 |
| **Loader** | `CrossEncoder` (sentence-transformers) |
| **Pool Size** | 50 (configurable `KB_RERANK_POOL`) |
| **Top-K** | 5 (configurable `RETRIEVAL_TOP_K`) |
| **Status** | Production baseline |

### Candidate Backbones (shootout running)

| Model | Params | License | Loader | Status |
|-------|--------|---------|--------|--------|
| `BAAI/bge-reranker-v2-m3` | 568M | MIT | CrossEncoder | Candidate — m3 tops FaMTEB Persian rerank |
| `jinaai/jina-reranker-v3` | 0.6B | Apache 2.0 | CrossEncoder (trust_remote_code, EOS pad) | Candidate (v2 skipped: CC-BY-NC) |
| `Qwen/Qwen3-Reranker-0.6B` | 0.6B | Apache 2.0 | FlagEmbedding LLM head | Candidate |
| `Qwen/Qwen3-Reranker-4B` | 4B | Apache 2.0 | FlagEmbedding LLM head | Candidate (~23GB RAM) |
| `BAAI/bge-reranker-v2-gemma` | 2.5B | Apache 2.0 | FlagEmbedding LLM head | Candidate, biggest SOTA in scope |
| `BAAI/bge-reranker-v2-minicpm-layerwise` | 2.7B | Apache 2.0 | — | **Blocked**: transformers-5 port needed |
| `Alibaba-NLP/gte-multilingual-reranker-base` | ~300M | Apache 2.0 | — | **Blocked**: rope index bug under transformers 5 |

**Notes:**
- Causal-LM-derived rerankers (Jina-v3, Qwen3) ship `pad_token_id=None`; loader falls back to EOS
- `bge-reranker-v2-gemma` is Gemma-2B-based (~2.5B, 9.4GB), not 9B
- No Persian-specific cross-encoder exists; all rely on multilingual models
- Hosted APIs (Cohere, Voyage) excluded — self-hosted only

---

## 4. Guardrails Models

### Risk Scoring (Heuristic + ML)

| Component | Model/Method | Threshold | Notes |
|-----------|--------------|-----------|-------|
| PII Detection | Regex + NER | 0.90 | Persian patterns |
| Prompt Injection | Keywords + heuristics | 0.85 | "دان" word-boundary |
| Toxicity | Ghadeer mmBERT | 0.80 | F1 0.94 Persian |
| Hate Speech | Ghadeer mmBERT | 0.80 | F1 0.94 Persian |
| Intent Classification | Ghadeer mmBERT | — | Semantic interface |
| Secret Leak | Regex (API keys, tokens) | 0.90 | Deterministic |

### HurtLex Persian Allowlist (19 lemmas)

| Lemma | Evidence | Type |
|-------|----------|------|
| حذف | KB: 'درخواست حذف سابقه منفی' | Credit operation |
| بخشی | 'بخشی از اطلاعات' | Credit phrase |
| تأمین مالی | Core term 'تسهیلات بانکی' | Credit domain |
| اشتغال | 'اشتغال و سابقه بیمه' | Credit domain |
| پست | 'پست سازمانی' | Credit form |
| مصرف | Bench question 'گزارش‌های مصرف' | Credit phrase |
| هدف | KB 'هدف از دریافت تسهیلات' | Credit domain |
| نادرست | 'اطلاعات نادرست را اصلاح' | Credit correction |
| پستی | KB chunk, polite greeting context | Credit form |
| مهم | KB 'مهم است' flagged on 'جدول نوع تماس' | Credit phrase |
| ضعیف | 6 expected answers 'رتبه ضعیف' | Credit rating |
| خسته | 'خسته نباشید' polite greeting | Social |
| شرح | 'شرح' = description in reports | Credit domain |
| دسته | 'دسته‌بندی' = category | Credit domain |
| جزئی | 'جزئی' = partial/minor | Credit domain |
| ناشی | 'ناشی از' = resulting from | Credit phrase |
| خوشحال | Positive sentiment | Social |
| سخت | 'سخت' = difficult | General |
| پلیس | 'سوابق پلیس' = police records (credit source) | Credit domain |

---

## 5. Server-Setup Models (H200, not in MVP path)

| Model | Quant | Size | Bench Mean | Status |
|-------|-------|------|------------|--------|
| Gemma-4-31B Q4_K_M | Q4_K_M | 19.6G | **0.663** | Loaded 5× (8080-8084) |
| Gemma-3-27B Q4_K_M | Q4_K_M | 16.5G | 0.600 | Available |
| Qwen3.8-27B Q4_K_M | Q4_K_M | 17.8G | 0.477 | Available |
| Qwen3-30B-A3B MoE | Q4_K_M | 18.6G | 0.283 | Available |
| Nemotron-49B Q4_K_M | Q4_K_M | 30.2G | 0.494 | Available |
| Qwen2.5-7B Q4_K_M | Q4_K_M | 4.4G | 0.443 | **Loaded :8090** |
| Llama-3.2-3B Q4_K_M | Q4_K_M | 1.9G | 0.326 | Available |
| Mistral-7B v0.3 | Multi | 127G total | 0.186 (Q4_K_M) | Available |
| Phi-3-mini 4K | q4 | 2.4G | 0.143 | Available |
| DeepSeek-V4-Flash | FP8 MoE | 148.7G | — | Needs vLLM |
| Qwen2.5-72B | Multi | 73G | — | Partial/on-disk |

---

## 6. Model Selection Rationale

| Role | Selected | Why |
|------|----------|-----|
| Generation | Gemma-4-31B UD-Q4_K_XL | Best Persian 7-task mean (0.663), fits 24GB VRAM, clean output with `enable_thinking:false` |
| Embedding | paraphrase-multilingual-MiniLM-L12-v2 | 384-dim, fast, multilingual, proven in v5-v8 benchmarks |
| Reranker | mmarco-mMiniLMv2-L12-H384-v1 | 118M params, Apache 2.0, baseline; shootout will promote winner |
| Guardrails | Deterministic + Ghadeer mmBERT | Zero false positives after allowlist; F1 0.94 Persian |

---

## 7. Quantization & Hardware Notes

- **GGUF quantization**: UD-Q4_K_XL (unsloth dynamic) chosen over Q4_K_M for better quality/size tradeoff
- **VRAM budget**: 24 GB (RTX 3090 on Vast) → 22.7 GB used at ctx 8192; OOM fallback = `--ctx-size 4096`
- **n_gpu_layers=-1**: All layers on GPU (llama.cpp)
- **Flash Attention**: Not used with GGUF; llama.cpp handles attention natively
- **Batch inference**: Not implemented (single-request MVP)