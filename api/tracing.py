"""Tracing fallback collector entry point.

Thin wrapper over `components/tracing/app.py`.
Run with: `uvicorn api.tracing:app`
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "components" / "tracing"))

from app import app  # noqa: E402
