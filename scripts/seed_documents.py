#!/usr/bin/env python3
# ============================================================
# Seed script for testing RAG
# ============================================================

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.db.session import SessionLocal
from app.services.ingestion.service import get_ingestion_service


async def main():
    print("📚 Seeding documents for RAG testing...")
    
    db = SessionLocal()
    try:
        ingestion_service = get_ingestion_service(db)
        
        # Sample documents
        documents = [
            {
                "name": "sample_rag.txt",
                "content": """
Retrieval-Augmented Generation (RAG) is a technique that combines information retrieval with 
large language models to generate more accurate and contextually relevant responses. 

RAG works by first retrieving relevant documents or passages from a knowledge base, 
then using those retrieved passages as context for the language model to generate a response.

Key benefits of RAG include:
1. Improved accuracy: By grounding the model in factual data
2. Up-to-date information: The knowledge base can be refreshed without retraining
3. Transparency: Citations can be provided for the sources used

The RAG pipeline typically consists of:
1. Document ingestion (chunking and embedding)
2. Query processing
3. Retrieval (vector search)
4. Response generation
                """
            },
            {
                "name": "langgraph_intro.txt",
                "content": """
LangGraph is a library for building stateful, multi-actor applications with LLMs. 
It extends LangChain with the ability to create cyclical graphs, which are essential for 
agentic workflows.

Key features of LangGraph:
1. State management: Persistent state across graph execution
2. Cycles: Support for loops and iterative refinement
3. Checkpointing: Save and resume graph execution
4. Human-in-the-loop: Interrupt and resume at any point

LangGraph uses the concept of a StateGraph, where nodes represent operations and 
edges define the flow. The graph is compiled into an executable that can be run 
with different inputs.
                """
            }
        ]
        
        for doc_data in documents:
            doc = await ingestion_service.ingest_document(
                content=doc_data["content"],
                name=doc_data["name"],
                source_path=f"seed://{doc_data['name']}",
            )
            print(f"✅ Ingested: {doc.name} (ID: {doc.id})")
        
        print("\n✅ Seeding complete!")
        
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
