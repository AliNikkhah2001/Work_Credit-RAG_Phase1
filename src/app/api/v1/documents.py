# ============================================================
# RAG Agent Platform — Document Management Endpoints
# ============================================================

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.services.ingestion.service import get_ingestion_service
from app.services.retrieval.service import get_retrieval_service

router = APIRouter()


@router.get("/documents/search")
async def search_documents(
    query: str = Query(..., description="Search query"),
    top_k: int = Query(5, description="Number of results to return"),
    db: Session = Depends(get_db),
):
    """
    Search for relevant documents using vector similarity.
    """
    try:
        retrieval_service = get_retrieval_service(db)
        results = await retrieval_service.search(query, top_k)
        
        return {
            "query": query,
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/ingest")
async def ingest_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload and ingest a document into the vector database.
    """
    try:
        content = await file.read()
        text = content.decode('utf-8')
        
        ingestion_service = get_ingestion_service(db)
        doc = await ingestion_service.ingest_document(
            content=text,
            name=file.filename,
            source_path=f"upload://{file.filename}",
            doc_metadata={"uploaded": True},
        )
        
        return {
            "status": "success",
            "document_id": str(doc.id),
            "name": doc.name,
            "hash": doc.hash,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/ingest-text")
async def ingest_text(
    name: str,
    content: str,
    db: Session = Depends(get_db),
):
    """
    Ingest text content directly into the vector database.
    """
    try:
        ingestion_service = get_ingestion_service(db)
        doc = await ingestion_service.ingest_document(
            content=content,
            name=name,
            source_path=f"text://{name}",
            doc_metadata={"type": "direct_text"},
        )
        
        return {
            "status": "success",
            "document_id": str(doc.id),
            "name": doc.name,
            "hash": doc.hash,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
