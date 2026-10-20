---
layout: default
title: "Subspace & Domain Partitioning Papers"
description: "PC-RAG, SPLIT-RAG, DSRAG, EvoRAG - Domain-partitioned retrieval, question-driven graph partitioning, hierarchical KGs"
---

<div class="page-header">
  <h1>Subspace & Domain Partitioning Papers</h1>
  <p class="lead">PC-RAG, SPLIT-RAG, DSRAG, EvoRAG - Domain-partitioned retrieval, question-driven graph partitioning, hierarchical KGs</p>
</div>

## Paper Summaries

### PC-RAG: Domain-Partitioned Retrieval as Hallucination Mitigation

| Field | Detail |
|-------|--------|
| **Title** | Domain-Partitioned Retrieval as a Hallucination Mitigation Strategy in Conversational RAG: The PC-RAG Architecture |
| **Authors** | Ruben Alejandro Jaime |
| **Venue** | ResearchSquare (2026-04-16) |
| **DOI** | 10.21203/rs.3.rs-9334334/v1 |
| **Code** | Not specified |

**Key Claims**:
- **Primary cause of hallucination**: Context window contamination from cross-domain chunk aggregation
- **Solution**: Domain-partitioned retrieval — decompose query into domain-isolated sub-tasks, independent retrieval per partition
- **Results**: 51% reduction in false-positive chunk inclusion; human-rated quality 3.1→4.1/5 (κ=0.79, p<0.001)
- **Full system**: 4.2/5, beats HyDE (3.6), multi-query (3.7), RAPTOR (3.9)

**Relevance to Our Fix**: 
- Our `subspace_map` fix = domain-partitioned retrieval
- PC-RAG validates: **partitioning alone reduces cross-domain noise by 51%**
- Our cheque map fix ("چک" → "گزارش اعتباراتنجی چک") = exactly domain partitioning

---

### SPLIT-RAG: Question-Driven Graph Partitioning

| Field | Detail |
|-------|--------|
| **Title** | Divide by Question, Conquer by Agent: SPLIT-RAG with Question-Driven Graph Partitioning |
| **Authors** | Multiple authors |
| **Venue** | arXiv:2505.13994 (2025), ICML 2025 |
| **Code** | Not specified |

**Key Claims**:
- **Problem**: Full-graph retrieval searches all n triples → cost C(n)
- **Solution**: Partition KG by reasoning paths from training questions → assign specialized agents to partitions
- **Inference**: Query-specific planner activates relevant partition-agents → parallel subgraph retrieval
- **Result**: Strong performance on WebQSP, CWQ, MetaQA with reduced latency

**Architecture**:
1. **Question-Type Clustering** → KG Partitioning (from training Q reasoning paths)
2. **Agent-Subgraph Assignment** → Specialized retrieval agents per partition
3. **Retrieval Plan Selection** → Entity-type similarity + relation-path sketch
4. **Multi-Agent RAG** → Parallel subgraph retrieval
5. **Conflict Resolution** → Compatibility-based evidence filtering

**Relevance to Our Fix**:
- Our static `subspace_map` = manual partitioning
- SPLIT-RAG shows: **learn routing from training queries** instead of static map
- Future: Learn `subspace_map` from training Qs instead of hardcoding

---

### DSRAG: Domain-Specific RAG with Hierarchical KG

| Field | Detail |
|-------|--------|
| **Title** | DSRAG: A Domain-Specific Retrieval Framework Based on Document-derived Multimodal Knowledge Graph |
| **Venue** | arXiv:2509.10467 (2025) |
| **Key Innovation** | Hierarchical KG: Concept KG (domain concepts/workflows) + Instance KG (facts) |

**Key Claims**:
- **Multimodal KG**: Text + images + tables → Concept KG + Instance KG
- **Concept KG**: Core domain concepts/workflows from document structure
- **Instance KG**: Fine-grained facts from document content
- **Retrieval**: Semantic subgraph retrieval + vector matching

**Relevance**: Our KB has implicit hierarchy (پایگاه دانش → اشخاص حقیقی → گزارش اعتباراتنجی چک) — DSRAG formalizes this.

---

### EvoRAG: Evolving Graph-Based Context Modeling

| Field | Detail |
|-------|--------|
| **Title** | Evolving Graph-Based Context Modeling for Multi-Turn Conversational RAG |
| **Venue** | ACM DL 2024 (or similar) |
| **Key Innovation** | Dynamic knowledge graph evolving with conversation |

**Key Claims**:
- Maintains evolving KG of logical relations among queries, responses, passages across turns
- Captures contextual dependencies → improves retrieval + generation
- Tested on 4 conversational RAG datasets

**Relevance**: Our sticky context = simple version of evolving context graph. EvoRAG shows full graph approach.

---

## Comparison Table

| Paper | Approach | Partitioning | Routing | Validation |
|-------|----------|--------------|---------|------------|
| **PC-RAG** | Domain-partitioned retrieval | Manual domains (HR, legal, compliance) | Query decomposition → domain-isolated retrieval | 51% false-positive reduction; 3.1→4.1 quality |
| **SPLIT-RAG** | Question-driven KG partitioning | Learned from training Q reasoning paths | Query-specific planner → partition-agents | WebQSP, CWQ, MetaQA SOTA |
| **DSRAG** | Hierarchical multimodal KG | Document-derived (Concept + Instance KG) | Semantic subgraph + vector matching | Domain-specific QA excellence |
| **EvoRAG** | Evolving conversation KG | Dynamic (evolves with conversation) | Graph-based context tracking | 4 conversational RAG datasets |

---

## Our Implementation vs Papers

| Aspect | PC-RAG | SPLIT-RAG | Our Implementation |
|--------|--------|-----------|-------------------|
| **Partitioning** | Manual domains | Learned from training Qs | Manual `subspace_map` (fixed) |
| **Routing** | Query decomposition | Query-specific planner | Static `subspace_map` + fuzzy match |
| **Retrieval** | Domain-isolated independent | Parallel partition-agents | Single KB with `filter_path` |
| **Fusion** | Independent per domain | RRF across agents | RRF fusion (filtered + whole-KB) |
| **Validation** | Human eval (3.1→4.1) | WebQSP/CWQ/MetaQA | 41-turn bench (hit 0.78) |

---

## Future Work: From Static Map to Learned Routing

Based on SPLIT-RAG, our next evolution:

```python
# Future: Learned subspace router
class SubspaceRouter:
    def __init__(self):
        self.encoder = SentenceTransformer("bge-m3")
        self.classifier = LogisticRegression()
    
    def train(self, queries, subspace_labels):
        embeddings = self.encoder.encode(queries)
        self.classifier.fit(embeddings, subspace_labels)
    
    def route(self, query):
        emb = self.encoder.encode([query])
        return self.classifier.predict(emb)[0]
```

Training data: Our 41-turn benchmark + historical queries → learn `subspace_map` instead of hardcoding.

---

## Related Pages

- [Problem: Subspace Filtering](../problems/subspace-filtering.html)
- [Paper: Retrieval Fusion & RRF](./retrieval-fusion.html)
- [Paper: Memory Architectures](./memory-architectures.html)
- [Architecture: SPLIT-RAG](../architectures.html#split-rag)