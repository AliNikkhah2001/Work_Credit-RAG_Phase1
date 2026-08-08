# ============================================================
# RAG Agent Platform — Secure API Key Management
# ============================================================
# Never expose keys in code, logs, or error messages.
# Keys are loaded from environment variables only.
# ============================================================

import os
import re
from typing import Optional
from functools import lru_cache

from app.core.config import settings


class SecretManager:
    """Secure API key management with validation and redaction."""

    @staticmethod
    def get_openai_key() -> str:
        """
        Get OpenAI API key from environment.
        Raises ValueError if key is missing or invalid format.
        """
        key = settings.OPENAI_API_KEY

        if not key or key == "your-secret-key-here":
            raise ValueError(
                "OPENAI_API_KEY not set. Please add it to your .env file."
            )

        # Validate format (sk-proj- or sk-)
        if not re.match(r"^sk-(?:proj-)?[A-Za-z0-9_-]{20,}$", key):
            raise ValueError(
                "OPENAI_API_KEY appears to be invalid format. "
                "It should start with 'sk-' or 'sk-proj-'."
            )

        return key

    @staticmethod
    def get_redacted_key() -> str:
        """Get a redacted version of the API key for logging."""
        try:
            key = SecretManager.get_openai_key()
            if len(key) > 16:
                return f"{key[:8]}...{key[-8:]}"
            return "***"
        except ValueError:
            return "[NOT SET]"

    @staticmethod
    def validate_all_keys() -> dict:
        """Validate all required API keys and return status."""
        status = {}

        # OpenAI
        try:
            SecretManager.get_openai_key()
            status["openai"] = {"status": "valid", "redacted": SecretManager.get_redacted_key()}
        except ValueError as e:
            status["openai"] = {"status": "error", "error": str(e)}

        return status


@lru_cache(maxsize=1)
def get_openai_api_key() -> str:
    """Cached version of the API key getter."""
    return SecretManager.get_openai_key()


def redact_sensitive_data(text: str) -> str:
    """Redact any sensitive data from logs or error messages."""
    # Redact OpenAI keys
    text = re.sub(
        r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}",
        "[REDACTED_API_KEY]",
        text
    )
    # Redact Bearer tokens
    text = re.sub(
        r"Bearer\s+sk-(?:proj-)?[A-Za-z0-9_-]{20,}",
        "Bearer [REDACTED_API_KEY]",
        text
    )
    return text


# Convenience exports
openai_key = get_openai_api_key
redacted_key = SecretManager.get_redacted_key
