# ============================================================
# RAG Agent Platform — API Router
# ============================================================

from fastapi import APIRouter

from app.api.v1 import chat
from app.api.v1 import documents

api_router = APIRouter()

# Version 1 endpoints
api_router.include_router(chat.router, prefix="/v1", tags=["Chat"])
api_router.include_router(documents.router, prefix="/v1", tags=["Documents"])
