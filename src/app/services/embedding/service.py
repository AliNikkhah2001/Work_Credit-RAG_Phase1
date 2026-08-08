# ============================================================
# RAG Agent Platform — Embedding Service (Fallback Only)
# ============================================================

import hashlib
import math
from typing import List

from app.core.config import settings


class FallbackEmbeddingService:
    """Local embedding using simple TF-IDF style hashing."""
    
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        print(f"✅ Using Fallback Embeddings (dimension: {dimension})")

    async def embed_text(self, text: str) -> List[float]:
        """Generate deterministic embedding using hashing."""
        if not text:
            return [0.0] * self.dimension
        
        # Count word frequencies
        words = text.lower().split()
        word_counts = {}
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        # Create embedding vector
        embedding = [0.0] * self.dimension
        
        for word, count in word_counts.items():
            # Use hash to get deterministic position
            hash_val = int(hashlib.sha256(word.encode()).hexdigest(), 16)
            idx = hash_val % self.dimension
            
            # Add weighted value
            tf = count / len(words) if words else 0
            value = tf * 0.1
            embedding[idx] += value
        
        # Normalize to unit vector
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]
        
        return embedding
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        return [await self.embed_text(text) for text in texts]


def get_embedding_service():
    """Get the embedding service (always fallback for now)."""
    return FallbackEmbeddingService()
