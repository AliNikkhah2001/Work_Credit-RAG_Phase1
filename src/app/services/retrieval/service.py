# ============================================================
# RAG Agent Platform — Retrieval Service
# ============================================================

from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.models.document import Chunk
from app.services.embedding.service import get_embedding_service


class RetrievalService:
    """Service for retrieving relevant chunks from the vector database."""

    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = get_embedding_service()

    async def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant chunks using vector similarity.
        """
        # Generate embedding for the query
        query_embedding = await self.embedding_service.embed_text(query)
        
        # Convert to string for SQL
        embedding_str = str(query_embedding)
        
        # Vector similarity search
        stmt = text("""
            SELECT 
                c.id,
                c.content,
                c.chunk_metadata,
                d.name as document_name,
                1 - (c.embedding <=> :embedding) as similarity
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE 1 - (c.embedding <=> :embedding) >= :min_score
            ORDER BY similarity DESC
            LIMIT :top_k
        """)
        
        result = self.db.execute(
            stmt,
            {
                "embedding": embedding_str,
                "min_score": min_score,
                "top_k": top_k,
            }
        )
        
        rows = result.fetchall()
        
        return [
            {
                "id": str(row.id),
                "content": row.content,
                "metadata": row.chunk_metadata,
                "document_name": row.document_name,
                "similarity": float(row.similarity),
            }
            for row in rows
        ]

    async def format_context(self, results: List[Dict[str, Any]]) -> str:
        """
        Format search results into a context string for the LLM.
        """
        if not results:
            return "No relevant information found."
        
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(
                f"[Document {i}: {result['document_name']}]\n"
                f"{result['content']}\n"
                f"(Relevance: {result['similarity']:.2f})"
            )
        
        return "\n\n---\n\n".join(context_parts)


def get_retrieval_service(db: Session):
    return RetrievalService(db)
