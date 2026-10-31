from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/dense.py")
content = path.read_text()

old_dense = """    def search(self, query: str, top_k: int = 30) -> list[tuple[str, float]]:
        \"\"\"Return ``[(chunk_id, cosine_sim)]`` sorted best-first.\"\"\"
        if not self.is_built:
            return []
        qv = self._encode([query])[0].astype(np.float32)
        qn = np.linalg.norm(qv)
        if qn == 0:
            return []
        qv = qv / qn
        sims = self._matrix @ qv  # rows already normalised -> cosine
        order = np.argsort(-sims)[:top_k]
        return [(self._ids[i], float(sims[i])) for i in order]"""

new_dense = """    def search(self, query: str, top_k: int = 30, allowed_ids: set[str] | None = None) -> list[tuple[str, float]]:
        \"\"\"Return ``[(chunk_id, cosine_sim)]`` sorted best-first.\"\"\"
        if not self.is_built:
            return []
        qv = self._encode([query])[0].astype(np.float32)
        qn = np.linalg.norm(qv)
        if qn == 0:
            return []
        qv = qv / qn
        sims = self._matrix @ qv  # rows already normalised -> cosine
        
        if allowed_ids is not None:
            # Mask out non-allowed ids by setting their similarity to -inf
            # use a simple list comprehension for boolean mask to avoid complex numpy string ops
            mask = np.array([cid not in allowed_ids for cid in self._ids])
            sims[mask] = -np.inf
            
        order = np.argsort(-sims)[:top_k]
        return [(self._ids[i], float(sims[i])) for i in order if sims[i] != -np.inf]"""

content = content.replace(old_dense, new_dense)
path.write_text(content)
