import os, traceback
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HOME"] = "/tmp/hf_clean"
os.environ["HF_HUB_CACHE"] = "/tmp/hf_clean"
# Attempt 1: shim is_torch_fx_available for remote module, load via AutoModelForCausalLM
import transformers.utils.import_utils as iu
print("has attr:", hasattr(iu, "is_torch_fx_available"))
if not hasattr(iu, "is_torch_fx_available"):
    iu.is_torch_fx_available = lambda: False
    print("shimmed")
from transformers import AutoModelForCausalLM
try:
    m = AutoModelForCausalLM.from_pretrained(
        "BAAI/bge-reranker-v2-minicpm-layerwise",
        trust_remote_code=True,
        torch_dtype="float32",
    )
    print("REMOTE OK", type(m))
except Exception:
    traceback.print_exc()
