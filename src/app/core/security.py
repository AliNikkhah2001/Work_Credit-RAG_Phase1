# ============================================================
# RAG Agent Platform — Security Module
# ============================================================

import hashlib
import secrets
import sys
from datetime import datetime
from typing import Optional

from app.core.config import settings

# ─── ASCII ART BANNER ─────────────────────────────────────────
ASCII_BANNER = r"""
    ██████   █████  ██████   █████  ██████   █████  ███████ ███    ██ ████████
    ██       ██   ██ ██   ██ ██   ██ ██   ██ ██   ██ ██      ████   ██    ██
    ██   ███ ███████ ██████  ███████ ██████  ███████ █████   ██ ██  ██    ██
    ██    ██ ██   ██ ██   ██ ██   ██ ██   ██ ██   ██ ██      ██  ██ ██    ██
     ██████  ██   ██ ██   ██ ██   ██ ██   ██ ██   ██ ███████ ██   ████    ██
"""

BORDER = "=" * 80


def generate_access_code(seed: Optional[str] = None) -> tuple[str, str]:
    """Generate access code from ASCII art + seed + date + salt."""
    if seed is None:
        seed = settings.ACCESS_CODE_SEED or secrets.token_urlsafe(16)

    today = datetime.utcnow().strftime("%Y-%m-%d")
    salt = "RAG_PLATFORM_v1.0_SALT"

    raw = f"{ASCII_BANNER.strip()}:{seed}:{today}:{salt}"
    checksum = hashlib.sha256(raw.encode()).hexdigest()
    code = f"rag-{checksum[:8]}-{seed[:8]}"
    return code, seed


def print_startup_banner() -> str:
    """Print the ASCII banner with access code and return the code."""
    if settings.ACCESS_CODE:
        code = settings.ACCESS_CODE
        seed = settings.ACCESS_CODE_SEED or "manual"
    else:
        code, seed = generate_access_code()

    banner = f"""
{BORDER}
{ASCII_BANNER}
{BORDER}
🔐  ACCESS CODE:  {code}
🧂  SEED:         {seed}
📅  DATE:         {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}
🌐  FRONTEND:     http://localhost:8081
{BORDER}

💡  Use this access code to log into the chat interface.
"""
    sys.stdout.write(banner)
    sys.stdout.flush()
    return code


if __name__ == "__main__":
    print_startup_banner()
