"""Orchestrator API entry point.

Thin wrapper over `components/orchestrator/src/work_rag_orchestrator/api.py`.
Run with: `uvicorn api.orchestrator:app`
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "components" / "orchestrator" / "src"))

from work_rag_orchestrator.api import create_app  # noqa: E402

app = create_app()
