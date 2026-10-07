from pathlib import Path

path = Path("README.md")
content = path.read_text()
if "## Latest Metrics" not in content:
    metrics = """## Latest Metrics (1405-07-06)

*   **Overall Hit Rate (Top-5):** `91.67%`
*   **Top-1 Hit Rate:** `79.17%`
*   **Mean Reciprocal Rank (MRR):** `0.844`
*   **Latency:** Dynamic Thresholding with Cross-Encoder RRF.
"""
    content = content.replace("##", metrics + "\n##", 1)
    path.write_text(content)

path_eval = Path("docs/evaluation.md")
if path_eval.exists():
    content_eval = path_eval.read_text()
    if "1405-07-06" not in content_eval:
        metrics_eval = """
### Version: 1405-07-06 (BGE-M3 RRF + Dynamic Thresholding)
- **Hit@5**: 91.67%
- **Top-1**: 79.17%
- **MRR**: 0.844
"""
        content_eval = content_eval.replace("### Version", metrics_eval + "\n### Version", 1)
        path_eval.write_text(content_eval)

print("Docs updated")
