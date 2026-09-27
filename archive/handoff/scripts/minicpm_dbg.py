import os, traceback
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HOME"] = "/tmp/hf_clean"
os.environ["HF_HUB_CACHE"] = "/tmp/hf_clean"
from FlagEmbedding.inference.reranker.decoder_only.models.modeling_minicpm_reranker import LayerWiseMiniCPMForCausalLM
try:
    m = LayerWiseMiniCPMForCausalLM.from_pretrained(
        "BAAI/bge-reranker-v2-minicpm-layerwise",
        trust_remote_code=True,
        torch_dtype="float32",
    )
    print("BUNDLED OK", type(m))
except Exception:
    traceback.print_exc()
