from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/web/routes/search.py")
content = path.read_text()

old_bm25 = """    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        q_tokens = _tokenize(query)
        if not q_tokens or self.doc_count == 0:
            return []
        scored = [(self.doc_ids[i], self.score(q_tokens, i)) for i in range(self.doc_count)]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]"""

new_bm25 = """    def search(self, query: str, top_k: int = 20, allowed_ids: set[str] | None = None) -> list[tuple[str, float]]:
        q_tokens = _tokenize(query)
        if not q_tokens or self.doc_count == 0:
            return []
        if allowed_ids is not None:
            scored = [(self.doc_ids[i], self.score(q_tokens, i)) for i in range(self.doc_count) if self.doc_ids[i] in allowed_ids]
        else:
            scored = [(self.doc_ids[i], self.score(q_tokens, i)) for i in range(self.doc_count)]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]"""

content = content.replace(old_bm25, new_bm25)
path.write_text(content)
