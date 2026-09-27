import os, traceback
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HOME"] = "/tmp/hf_clean"
os.environ["HF_HUB_CACHE"] = "/tmp/hf_clean"
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch
try:
    tok = AutoTokenizer.from_pretrained("Alibaba-NLP/gte-multilingual-reranker-base", trust_remote_code=True)
    print("tok OK", type(tok).__name__, "pad:", tok.pad_token)
    m = AutoModelForSequenceClassification.from_pretrained("Alibaba-NLP/gte-multilingual-reranker-base", torch_dtype=torch.float32, trust_remote_code=True)
    print("model OK", type(m).__name__, m.num_labels if hasattr(m, "num_labels") else "?")
    m.eval()
    inp = tok(["اعتبارسنجی چیست"], ["اعتبارسنجی فرآیندی بانکی است."], padding=True, truncation=True, max_length=512, return_tensors="pt")
    with torch.no_grad():
        print("logits:", m(**inp).logits)
except Exception:
    traceback.print_exc()
