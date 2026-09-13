import os, traceback
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HOME"] = "/tmp/hf_clean"
os.environ["HF_HUB_CACHE"] = "/tmp/hf_clean"
from FlagEmbedding.inference.reranker.decoder_only.models.modeling_minicpm_reranker import LayerWiseMiniCPMForCausalLM
from FlagEmbedding.inference.reranker.decoder_only.models.configuration_minicpm_reranker import LayerWiseMiniCPMConfig
cfg = LayerWiseMiniCPMConfig.from_pretrained("BAAI/bge-reranker-v2-minicpm-layerwise", trust_remote_code=True)
print("before:", repr(cfg.rope_scaling))
cfg.rope_scaling = None
try:
    m = LayerWiseMiniCPMForCausalLM.from_pretrained(
        "BAAI/bge-reranker-v2-minicpm-layerwise",
        config=cfg,
        trust_remote_code=False,
        torch_dtype="float32",
    )
    print("PATCHED-CONFIG OK", type(m))
except Exception:
    traceback.print_exc()
