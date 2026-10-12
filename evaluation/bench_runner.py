"""Shim: re-export orchestrator evaluation bench_runner for `python -m evaluation.bench_runner`.

This allows `python3 -m evaluation.bench_runner --dry-run` from repo root
to work even though the canonical file lives at
`components/orchestrator/evaluation/bench_runner.py`.
"""

from components.orchestrator.evaluation.bench_runner import *  # noqa: F403,F401
from components.orchestrator.evaluation.bench_runner import main  # noqa: F401

if __name__ == "__main__":
    main()
