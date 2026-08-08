# ============================================================
# RAG Agent Platform — Embedding Model Endpoints
# ============================================================

from typing import List, Optional
from fastapi import APIRouter, HTTPException

from app.services.embedding.registry import EmbeddingRegistry
from app.services.embedding.comparison import EmbeddingComparison

router = APIRouter()


@router.get("/embeddings/models")
async def list_embedding_models():
    """List all available embedding models."""
    return {
        "models": EmbeddingRegistry.list_models(),
        "default": EmbeddingRegistry.get_default_model(),
    }


@router.post("/embeddings/compare")
async def compare_embedding_models(
    model_names: Optional[List[str]] = None,
):
    """
    Compare embedding models on Persian text.
    
    Results include:
    - Encoding time (latency)
    - Memory usage
    - Semantic consistency (cosine similarity scores)
    """
    try:
        results = EmbeddingComparison.compare_models(model_names)
        
        return {
            "status": "success",
            "results": [
                {
                    "model": r.model_name,
                    "info": r.model_info,
                    "encode_time_ms": round(r.encode_time_ms, 2),
                    "memory_mb": round(r.memory_mb, 2),
                    "avg_similarity": round(r.avg_similarity, 4),
                    "embedding_shape": r.embedding_shape,
                    "sample_embedding": r.sample_output,
                }
                for r in results
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/embeddings/cross-lingual")
async def test_cross_lingual():
    """
    Test cross-lingual performance (Persian ↔ English).
    """
    try:
        results = EmbeddingComparison.test_cross_lingual()
        return {
            "status": "success",
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
