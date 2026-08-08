# ============================================================
# RAG Agent Platform — Configuration
# ============================================================

import secrets
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "RAG Agent Platform"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "info"

    # LLM
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/rag"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Security
    ACCESS_CODE: Optional[str] = None
    ACCESS_CODE_SEED: Optional[str] = None
    SUPER_SECRET_KEY: str = secrets.token_urlsafe(32)

    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60

    # Monitoring
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # Vector
    VECTOR_DIMENSION: int = 1536
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # Embedding toggle (NEW)
    USE_OPENAI_EMBEDDING: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Allow extra fields in .env


settings = Settings()
