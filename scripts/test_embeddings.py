#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app.services.embedding.service import get_embedding_service

async def test_embedding():
    service = get_embedding_service()
    
    # Test Persian text
    text = "RAG چیست و چگونه کار می‌کند؟"
    print(f"📝 Text: {text}")
    
    embedding = await service.embed_text(text)
    print(f"📊 Embedding length: {len(embedding)}")
    print(f"📊 First 10 values: {embedding[:10]}")
    
    # Test batch
    texts = ["سلام", "RAG چیست؟", "لنگ‌گراف"]
    print(f"\n📝 Batch: {texts}")
    embeddings = await service.embed_batch(texts)
    print(f"📊 Batch size: {len(embeddings)}")
    print(f"📊 Each length: {len(embeddings[0])}")

if __name__ == "__main__":
    asyncio.run(test_embedding())
