"""Guardrails API entry point.

Thin wrapper over `components/guardrails/src/work_rag_guardrails/api.py`.
Run with: `uvicorn api.guardrails:app`
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "components" / "guardrails" / "src"))

from work_rag_guardrails.api import create_app  # noqa: E402

app = create_app()
