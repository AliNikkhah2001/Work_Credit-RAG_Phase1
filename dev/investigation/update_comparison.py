import json
import os
from pathlib import Path

data_dir = Path("components/knowledgebase/kb-manager/data")
comp_file = data_dir / "benchmark_comparison.json"
metrics_file = data_dir / "benchmark_results.json"

if not comp_file.exists() or not metrics_file.exists():
    print("Files missing")
    exit(1)

with open(comp_file, "r") as f:
    comp = json.load(f)

with open(metrics_file, "r") as f:
    metrics = json.load(f)

overall = metrics["overall"]

v5 = {
    "pipeline": "1405-07-06 BGE-M3 RRF + Dynamic Thresholding",
    "corpus": {
        "docs": 90,
        "chunks": 774,
        "qa": 774,
        "distinct_q": 774,
        "dup": 0
    },
    "overall": {
        "hit_at_5": overall["hit_rate"],
        "top1": overall["top1_hit_rate"],
        "mrr": overall["mrr"],
        "latency_s": overall["avg_latency_ms"] / 1000.0
    },
    "per_format": {}
}

for fmt, stats in metrics["by_format"].items():
    v5["per_format"][fmt] = {
        "hit": stats["hit_rate"],
        "top1": stats["top1_hit_rate"],
        "mrr": stats["mrr"],
        "lat_ms": stats["avg_latency_ms"]
    }

comp["versions"]["v5_1405_07_06"] = v5
comp["deltas"]["v4_to_v5"] = {
    "hit": overall["hit_rate"] - comp["versions"]["v4"]["overall"]["hit_at_5"],
    "top1": overall["top1_hit_rate"] - comp["versions"]["v4"]["overall"]["top1"],
    "mrr": overall["mrr"] - comp["versions"]["v4"]["overall"]["mrr"],
    "latency": (overall["avg_latency_ms"] / 1000.0) - comp["versions"]["v4"]["overall"]["latency_s"],
    "note": "Dynamic Thresholding applied, full 1405-07-06 dataset."
}

with open(comp_file, "w") as f:
    json.dump(comp, f, indent=2)

print("Added v5 to comparison")
