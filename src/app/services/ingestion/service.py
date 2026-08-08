# ============================================================
# RAG Agent Platform — Document Ingestion Service
# ============================================================

import hashlib
import os
from typing import List, Dict, Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models.document import Document, Chunk
from app.services.embedding.service import get_embedding_service


class DocumentIngestionService:
    """Service for ingesting documents into the vector database."""

    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = get_embedding_service()

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Split text into overlapping chunks.
        """
        if not text:
            return []
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + chunk_size, len(text))
            # Try to break at a sentence/paragraph boundary
            if end < len(text):
                # Look for space or newline near the end
                for i in range(end, max(start, end - 50), -1):
                    if text[i] in " .,!?;:\n":
                        end = i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap if end < len(text) else end
        
        return chunks

    async def ingest_document(self, content: str, name: str, source_path: str, doc_metadata: Dict[str, Any] = None) -> Document:
        """
        Ingest a document: chunk, embed, and store.
        """
        # Compute hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # Check if document already exists
        existing = self.db.query(Document).filter(Document.hash == content_hash).first()
        if existing:
            return existing
        
        # Create document record
        doc = Document(
            name=name,
            source_path=source_path,
            hash=content_hash,
            doc_metadata=doc_metadata or {},
        )
        self.db.add(doc)
        self.db.flush()
        
        # Chunk the content
        chunks = self.chunk_text(content)
        
        # Generate embeddings for all chunks
        embeddings = await self.embedding_service.embed_batch(chunks)
        
        # Create chunk records
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            chunk = Chunk(
                document_id=doc.id,
                chunk_index=idx,
                content=chunk_text,
                embedding=embedding,
                chunk_metadata={"source": source_path, "index": idx},
            )
            self.db.add(chunk)
        
        self.db.commit()
        self.db.refresh(doc)
        
        return doc

    async def ingest_from_file(self, file_path: str) -> Document:
        """
        Ingest a document from a file.
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        name = os.path.basename(file_path)
        return await self.ingest_document(
            content=content,
            name=name,
            source_path=file_path,
            doc_metadata={"file_type": "text"}
        )


def get_ingestion_service(db: Session):
    return DocumentIngestionService(db)
