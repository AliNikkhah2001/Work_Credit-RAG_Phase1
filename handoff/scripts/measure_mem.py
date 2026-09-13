import os, subprocess, sys
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HOME"] = "/tmp/hf_clean"
os.environ["HF_HUB_CACHE"] = "/tmp/hf_clean"
cases = [
    ("Qwen/Qwen3-Reranker-0.6B", "FlagLLMReranker"),
    ("Qwen/Qwen3-Reranker-4B", "FlagLLMReranker"),
    ("BAAI/bge-reranker-v2-m3", "FlagReranker"),
    ("BAAI/bge-reranker-v2-gemma", "FlagLLMReranker"),
]
for model, cls in cases:
    pid = os.fork()
    if pid == 0:
        os.execv("/tmp/kb-venv/bin/python", ["/tmp/kb-venv/bin/python", "/tmp/opencode/toy_rerank.py", model, cls])
    _, status, rusage = os.wait4(pid, 0)
    peak_gb = rusage.ru_maxrss / 1024 / 1024  # ru_maxrss in KB on Linux
    print(f"RESULT {model} exit={os.waitstatus_to_exitcode(status)} peakRSS={peak_gb:.2f}GB", flush=True)
