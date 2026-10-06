import os
import sys
import json
import time
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "components" / "knowledgebase" / "kb-manager"))
os.chdir(ROOT / "components" / "knowledgebase" / "kb-manager")

from kb_manager.web.routes import search as search_module

try:
    from transformers import AutoModelForMaskedLM, AutoTokenizer
    import torch
except ImportError:
    print("Please pip install transformers torch")
    sys.exit(1)

def run_splade(texts, model, tokenizer, device, batch_size=16):
    sparse_dicts = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        inputs = tokenizer(batch, return_tensors="pt", padding=True, truncation=True, max_length=512).to(device)
        with torch.no_grad():
            logits = model(**inputs).logits
            
        # SPLADE pooling (max along seq length)
        vecs = torch.max(torch.log(1 + torch.relu(logits)), dim=1).values
        
        for vec in vecs:
            cols = vec.nonzero().squeeze(-1)
            weights = vec[cols]
            
            sparse_dict = {}
            if cols.dim() == 0:
                cols = [cols]
                weights = [weights]
                
            for col, w in zip(cols, weights):
                sparse_dict[int(col)] = float(w)
            sparse_dicts.append(sparse_dict)
            
    return sparse_dicts

def compute_mrr_and_hitrate(ranks, k=5):
    hits = sum(1 for r in ranks if 0 < r <= k)
    hit_rate = hits / len(ranks) if ranks else 0
    mrr = sum(1.0 / r for r in ranks if r > 0) / len(ranks) if ranks else 0
    return hit_rate, mrr

def dot_product(d1, d2):
    score = 0.0
    # iterate over the smaller dict
    if len(d1) > len(d2):
        d1, d2 = d2, d1
    for k, v in d1.items():
        if k in d2:
            score += v * d2[k]
    return score

async def main():
    print("Loading Knowledge Base...")
    chunk_data, bm25_tuple, dense_index, reranker, hyde = await search_module._build_index()
    bm25_content, bm25_kw = bm25_tuple
    
    chunks = []
    for cd in chunk_data:
        chunk_id = cd[0]
        text = cd[4]
        chunks.append({"id": chunk_id, "text": text})
    print(f"Loaded {len(chunks)} chunks.")
    
    print("\nLoading SPLADE model...")
    model_id = "naver/splade-cocondenser-ensembledistil"
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Using device: {device}")
    model = AutoModelForMaskedLM.from_pretrained(model_id).to(device)
    model.eval()
    
    print("\nEmbedding corpus with SPLADE...")
    t0 = time.time()
    corpus_texts = [c["text"] for c in chunks]
    corpus_sparse = run_splade(corpus_texts, model, tokenizer, device, batch_size=32)
    for c, s in zip(chunks, corpus_sparse):
        c["splade"] = s
    print(f"Corpus embedding took {time.time()-t0:.2f}s")
    
    with open("data/test_questions.json", "r", encoding="utf-8") as f:
        dataset = json.load(f)
        
    print(f"\nRunning benchmark on {len(dataset)} queries...")
    
    bm25_ranks = []
    splade_ranks = []
    
    # We will need the BM25 tokenize/expand methods
    from kb_manager.web.routes.search import _tokenize, _expand_query_for_bm25, _PERSIAN_TRANSLATE_TABLE, _KEYWORD_BOOST_DEFAULT
    
    for i, item in enumerate(dataset):
        query = item["query"]
        expected = item["expected_chunk_ids"]
        if not expected:
            continue
        
        target_id = expected[0]
        
        # --- BM25 ---
        query_norm = query.lower().translate(_PERSIAN_TRANSLATE_TABLE)
        query_tokens = _tokenize(query_norm)
        expanded_queries = _expand_query_for_bm25(query)
        bm25_scores = {}
        for q_tok in expanded_queries:
            toks = _tokenize(q_tok)
            for j in range(len(bm25_content.doc_ids)):
                s = bm25_content.score(toks, j)
                if s > 0:
                    cid = bm25_content.doc_ids[j]
                    bm25_scores[cid] = max(bm25_scores.get(cid, 0), float(s))
                    
        bm25_sorted = sorted(bm25_scores.items(), key=lambda x: x[1], reverse=True)
        bm25_rank = next((idx + 1 for idx, (cid, score) in enumerate(bm25_sorted) if cid == target_id), 0)
        if bm25_rank > 100: bm25_rank = 0
        bm25_ranks.append(bm25_rank)
        
        # --- SPLADE ---
        q_sparse = run_splade([query], model, tokenizer, device, batch_size=1)[0]
        splade_scores = []
        for c in chunks:
            score = dot_product(q_sparse, c["splade"])
            splade_scores.append((c["id"], score))
            
        splade_sorted = sorted(splade_scores, key=lambda x: x[1], reverse=True)
        splade_rank = next((idx + 1 for idx, (cid, score) in enumerate(splade_sorted) if cid == target_id), 0)
        if splade_rank > 100: splade_rank = 0
        splade_ranks.append(splade_rank)
        
        if (i+1) % 10 == 0:
            print(f"Processed {i+1}/{len(dataset)} queries")

    print("\n--- RESULTS ---")
    
    b_hit5, b_mrr = compute_mrr_and_hitrate(bm25_ranks, k=5)
    s_hit5, s_mrr = compute_mrr_and_hitrate(splade_ranks, k=5)
    
    b_hit1 = sum(1 for r in bm25_ranks if r == 1) / len(bm25_ranks)
    s_hit1 = sum(1 for r in splade_ranks if r == 1) / len(splade_ranks)
    
    print(f"BM25   | Hit@1: {b_hit1:.3f} | Hit@5: {b_hit5:.3f} | MRR: {b_mrr:.3f}")
    print(f"SPLADE | Hit@1: {s_hit1:.3f} | Hit@5: {s_hit5:.3f} | MRR: {s_mrr:.3f}")
    
    if s_mrr >= b_mrr:
        print("\n=> SPLADE meets or exceeds BM25. Safe to migrate!")
    else:
        print("\n=> WARNING: SPLADE underperforms BM25 on this dataset.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
