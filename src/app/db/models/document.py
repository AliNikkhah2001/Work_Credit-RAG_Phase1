# ============================================================
# RAG Agent Platform — Document and Chunk Models
# ============================================================

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, JSON, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from pgvector.sqlalchemy import Vector

from app.db.session import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    source_path = Column(String(500), nullable=False)
    hash = Column(String(64), nullable=False)
    doc_metadata = Column(JSONB, default={})  # Renamed from 'metadata'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_documents_hash", "hash"),
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id = Column(PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536))  # OpenAI embedding dimension
    chunk_metadata = Column(JSONB, default={})  # Renamed from 'metadata'
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_chunks_document_id", "document_id"),
        Index("idx_chunks_embedding", "embedding", postgresql_using="ivfflat", postgresql_ops={"embedding": "vector_cosine_ops"}),
    )
