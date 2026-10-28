"""KB retrieval API entry point.

Thin wrapper over `components/knowledgebase/kb-manager/kb_manager/web/app.py`.
Run with: `uvicorn api.kb:app`
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "components" / "knowledgebase" / "kb-manager"))

from kb_manager.web.app import app  # noqa: E402
