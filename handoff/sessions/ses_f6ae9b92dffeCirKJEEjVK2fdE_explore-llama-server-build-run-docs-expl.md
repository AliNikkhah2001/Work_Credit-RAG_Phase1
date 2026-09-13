# Explore llama-server build/run docs (@explore subagent)

Session: `ses_f6ae9b92dffeCirKJEEjVK2fdE`
Messages: 3


## [USER]

Explore /workspace/Work_Credit-RAG_Phase1/components/server-setup and /workspace/Work_Credit-RAG_Phase1/docs, plus the llama.cpp source tree at /workspace/llama.cpp-src and llama.cpp wrapper dir at /workspace/llama.cpp.

Context: This host has an NVIDIA RTX 3090 24GB, CUDA 13.0 driver 580.173.02, no docker, 64 CPUs, ~109GB RAM. The Gemma 4 model is at /workspace/.hf_home/hub/models--unsloth--gemma-4-31B-it-GGUF/snapshots/c1ac76e99d5513b141e8adde7288b85c3f9c32ec/gemma-4-31B-it-UD-Q4_K_XL.gguf (18.8GiB).

Report precisely (read-only, no modifications):

1. From /workspace/Work_Credit-RAG_Phase1/docs/VAST_GEMMA4_MIGRATION.md and RUNBOOK_VAST.md: the exact llama.cpp build/run recipe used previously — CMake flags (CUDA), the llama-server invocation args (`--no-mmproj --jinja --ctx-size 8192 --temp 0.2 --port 18000`, model path, LD_LIBRARY_PATH), and how `chat_template_kwargs:{"enable_thinking":false}` is passed. Also how the server was monitored (pid, supervisor).
2. Check /workspace/llama.cpp-src for: a build dir already present (build/bin/llama-server), its git status/version (git -C /workspace/llama.cpp-src log --oneline -1), and required deps for CUDA build (cmake, nvcc/compiler availability: run `which cmake nvcc gcc g++` and `nvcc --version`).
3. What is /workspace/llama.cpp (empty?) and /workspace/gemma_simple.jinja (its content and purpose).
4. Confirm the exact GGUF file paths and sizes for the model + mmproj, and any other GGUF variants. Report whether the 31B UD-Q4_K_XL fits 24GB VRAM with --ctx-size 8192 (rough estimate from docs; README said it runs on 2x RTX 6000 in earlier env — note this host has 1x 3090 24GB).
5. From docs: the exact end-to-end chat curl for testing Gemma raw (POST /v1/chat/completions with model name unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL and chat_template_kwargs enable_thinking:false).
6. Check /workspace/onstart.sh and /workspace/ports.log for what ports were expected to run.

Return a concise structured report: build recipe, run command with full args, model files present, GPU fit assessment, and the raw-gemma test curl.


## [ASSISTANT]

(tool: bash)

(tool: bash)

(tool: bash)

(tool: bash)

(tool: bash)


## [ASSISTANT]

(tool: read)

(tool: read)

(tool: read)

(tool: read)

(tool: read)
