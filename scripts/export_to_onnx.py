import os
import sys
from pathlib import Path

def main():
    print("This script will export HuggingFace models to ONNX format for Triton.")
    print("It requires the 'optimum' package and a machine with NVIDIA GPUs for TensorRT.")
    print("Usage example:")
    print("optimum-cli export onnx --model BAAI/bge-m3 --task feature-extraction models/bge-m3-onnx")
    print("optimum-cli export onnx --model BAAI/bge-reranker-v2-m3 --task text-classification models/bge-reranker-onnx")
    print("optimum-cli export onnx --model naver/splade-cocondenser-ensembledistil --task feature-extraction models/splade-onnx")
    print("\nAfter ONNX export, you compile to TensorRT using trtexec inside the Triton container:")
    print("trtexec --onnx=model.onnx --saveEngine=model.plan --minShapes=input_ids:1x1 --optShapes=input_ids:16x512 --maxShapes=input_ids:512x512")
    
if __name__ == "__main__":
    main()
