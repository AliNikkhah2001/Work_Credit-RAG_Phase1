import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HOME"] = "/tmp/hf_clean"
os.environ["HF_HUB_CACHE"] = "/tmp/hf_clean"
from transformers import AutoConfig
c = AutoConfig.from_pretrained("BAAI/bge-reranker-v2-minicpm-layerwise", trust_remote_code=True)
print("rope_scaling:", repr(c.rope_scaling))
print("attn impl:", repr(getattr(c, "_attn_implementation", None)))
