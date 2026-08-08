#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

async def test():
    from src.app.services.embedding.service import get_embedding_service
    
    print("📝 Getting embedding service...")
    service = get_embedding_service()
    
    # Test with English first
    text = "Hello world, this is a test of the embedding system."
    print(f"\n📝 Testing: {text}")
    
    try:
        embedding = await service.embed_text(text)
        print(f"✅ Embedding generated: {len(embedding)} dimensions")
        print(f"   First 5 values: {embedding[:5]}")
        
        # Test batch
        texts = ["Hello world", "RAG چیست؟", "LangGraph is powerful"]
        print(f"\n📝 Testing batch: {len(texts)} texts")
        embeddings = await service.embed_batch(texts)
        print(f"✅ Generated {len(embeddings)} embeddings")
        print(f"   Each: {len(embeddings[0])} dimensions")
        
        print("\n✅ Embedding service is working!")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
