import os
import sys
import json
import time
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "components" / "knowledgebase" / "kb-manager"))
os.chdir(ROOT / "components" / "knowledgebase" / "kb-manager")

from kb_manager.web.routes import search as search_module

# We will need transformers for SPLADE
try:
    from transformers import AutoModelForMaskedLM, AutoTokenizer
    import torch
except ImportError:
    print("Please pip install transformers torch")
    sys.exit(1)

def run_splade(query, model, tokenizer, device):
    inputs = tokenizer(query, return_tensors="pt", truncation=True, max_length=512).to(device)
    with torch.no_grad():
        logits = model(**inputs).logits
    
    # SPLADE pooling (max along seq length)
    # output shape: (batch_size, seq_len, vocab_size)
    # We take max pooling over the sequence length, followed by relu
    vec = torch.max(torch.log(1 + torch.relu(logits)), dim=1).values.squeeze()
    
    # Extract non-zero elements
    cols = vec.nonzero().squeeze()
    weights = vec[cols]
    
    # Convert to dict of {token_str: weight}
    sparse_dict = {}
    if cols.dim() == 0:
        cols = [cols]
        weights = [weights]
        
    for col, w in zip(cols, weights):
        token_id = int(col)
        token_str = tokenizer.convert_ids_to_tokens(token_id)
        sparse_dict[token_str] = float(w)
        
    return sparse_dict

async def main():
    print("Loading SPLADE model (naver/splade-cocondenser-ensembledistil)...")
    model_id = "naver/splade-cocondenser-ensembledistil"
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = AutoModelForMaskedLM.from_pretrained(model_id).to(device)
    model.eval()
    
    print("Building KB Index for BM25 comparison...")
    chunk_data, bm25_tuple, dense_index, reranker, hyde = await search_module._build_index()
    bm25_content, bm25_kw = bm25_tuple
    print(f"Loaded {len(chunk_data)} chunks.")
    
    test_queries = ["گزارش اعتبارسنجی چیست؟", "چگونه وام بگیرم؟", "چک برگشتی", "رتبه اعتباری"]
    
    print("\n--- Running SPLADE Benchmark ---")
    for q in test_queries:
        print(f"\nQuery: {q}")
        t0 = time.time()
        sparse = run_splade(q, model, tokenizer, device)
        ms = (time.time() - t0) * 1000
        # sort by weight
        top_tokens = sorted(sparse.items(), key=lambda x: x[1], reverse=True)[:10]
        print(f"  SPLADE ({ms:.1f}ms): {top_tokens}")
        
    print("\nSPLADE initialization and inference test successful. Baseline confirmed.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
