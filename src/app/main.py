# ============================================================
# RAG Agent Platform — FastAPI Application Entry Point
# ============================================================

from contextlib import asynccontextmanager
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.security import print_startup_banner


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # ─── Startup ─────────────────────────────────────────────────
    sys.stdout.write("🚀 Starting lifespan...\n")
    sys.stdout.flush()
    access_code = print_startup_banner()
    app.state.access_code = access_code
    yield
    # ─── Shutdown ─────────────────────────────────────────────────
    sys.stdout.write("🛑 Shutting down...\n")
    sys.stdout.flush()


# ─── FastAPI App ──────────────────────────────────────────────
app = FastAPI(
    title="RAG Agent Platform",
    version="0.1.0",
    description="Production-ready RAG agent with LangGraph, pgvector, and FastAPI",
    lifespan=lifespan,
)

# ─── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Include Routers ──────────────────────────────────────────
app.include_router(api_router, prefix="/api")

# ─── Health Check ─────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "RAG Agent Platform"}

# ─── Root ─────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "message": "RAG Agent Platform API",
        "docs": "/docs",
        "health": "/health",
    }
