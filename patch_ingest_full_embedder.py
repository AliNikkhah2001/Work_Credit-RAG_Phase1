from pathlib import Path

path = Path("components/knowledgebase/kb-manager/ingest_full.py")
content = path.read_text()

old = """    chunker = SemanticChunker(max_tokens=512, min_tokens=100)
    orchestrator = PipelineOrchestrator(
        database=db,
        preprocessor=None,
        chunker=chunker,
        embedder=None,
    )"""

new = """    chunker = SemanticChunker(max_tokens=512, min_tokens=100)
    from kb_manager.embedder.registry import get_embedder
    embedder = get_embedder("sentence-transformer", model_name_or_path=config.embedding.model_name)
    orchestrator = PipelineOrchestrator(
        database=db,
        preprocessor=None,
        chunker=chunker,
        embedder=embedder,
    )"""

if old in content:
    content = content.replace(old, new)
    path.write_text(content)
    print("ingest_full.py updated with embedder")
else:
    print("Could not find block in ingest_full.py")
