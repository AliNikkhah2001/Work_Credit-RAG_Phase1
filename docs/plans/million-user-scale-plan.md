# Comprehensive Million-User Scaling Architecture Plan

This document serves as the master architectural blueprint for scaling the Knowledge Base Retrieval system to support **1,000,000+ concurrent users**. 

It contains the deep engineering rationale behind every technological shift ("The Why"), alongside two complete deployment models: **Scenario A (Cloud-Native Scale-Out)** and **Scenario B (Bare-Metal Scale-Up for 2x H200s)**.

---

## Part 1: The Bottlenecks & Design Rationale (The "Why")

At low scale, the current monolithic architecture is optimized for development speed. At a million-user scale, the engineering priorities shift to **high concurrency, memory footprint reduction, and lock avoidance**.

### 1. Vector Database: Why migrate from `pgvector` to Qdrant?
*   **The Current Bottleneck:** `pgvector` relies on PostgreSQL. Postgres is a relational database built on heavyweight, process-per-connection architecture and Multi-Version Concurrency Control (MVCC). At a million users, the high Queries-Per-Second (QPS) will exhaust connection pools (even with PgBouncer). Furthermore, Postgres' shared memory buffers aren't strictly designed for massive concurrent HNSW graph traversals, causing latency spikes when search competes with database writes.
*   **The Solution & Rationale:** Migrate to **Qdrant** (or Milvus). Qdrant is written in Rust from the ground up specifically for vector search, utilizing memory-mapped files and `io_uring` for extreme network concurrency. 
*   **The Killer Feature:** Qdrant natively supports **Sparse Vectors**. This allows us to execute a true Hybrid Search with a single network call, fusing Dense and Sparse scores at the database level.

### 2. Lexical Search: Why replace `RankBM25` with SPLADE?
*   **The Current Bottleneck:** `RankBM25` loads the entire text corpus into Python's RAM inside the FastAPI process. If you launch 100 FastAPI workers to handle web traffic, you duplicate that massive RAM footprint 100 times, instantly crashing your servers.
*   **Why not Elasticsearch?** The traditional fix is to deploy Elasticsearch for BM25. However, maintaining a massive Java-based Elasticsearch cluster *and* a Vector database creates a "Dual-Write" nightmare, making it very difficult to keep the two databases perfectly synced.
*   **The Solution & Rationale:** Use **SPLADE** (Sparse Lexical and Expansion Model). SPLADE generates highly efficient sparse vectors that capture exact keyword matches *and* semantic synonyms. Because Qdrant can store these sparse vectors alongside dense vectors, we completely eliminate the need for Elasticsearch while solving the catastrophic memory limits of `RankBM25`.

### 3. ML Inference: Why replace FastAPI with NVIDIA Triton?
*   **The Current Bottleneck:** Python suffers from the Global Interpreter Lock (GIL). When a user searches, the FastAPI thread locks up to run the Cross-Encoder Transformer math on the CPU/GPU. While it computes, it cannot answer other incoming network requests, causing cascading timeouts during traffic spikes.
*   **The Solution & Rationale:** Extract the models to **NVIDIA Triton Inference Server**, a dedicated C++ server built strictly for GPUs. 
*   **Dynamic Batching:** If 100 users search in the same millisecond, Triton automatically combines all 100 queries into a single Matrix Multiplication batch on the GPU, solving them simultaneously. FastAPI becomes a lightweight "router" that easily scales to thousands of concurrent users, while Triton efficiently saturates the expensive GPUs.

### 4. Compilation: Why replace PyTorch with TensorRT?
*   **The Current Bottleneck:** PyTorch executes graphs dynamically, which is computationally wasteful for production inference.
*   **The Solution & Rationale:** Compile the PyTorch models (`.pt`) into **TensorRT** engines (`.plan`). TensorRT physically compiles the mathematical graph for the specific architecture of your GPU (e.g., fusing layer-norms and attention blocks) and lowers precision to FP16 or FP8. This cuts the model's memory footprint in half and triples execution speed, dropping reranker latency from ~40ms to ~10ms.

### 5. Caching: Why use RedisVL over Standard Caching?
*   **The Current Bottleneck:** Standard caching requires exact string matches. If User A asks *"How to get a loan?"* and User B asks *"How do I get a loan?"*, a standard cache misses, forcing the GPU to do the expensive work twice.
*   **The Solution & Rationale:** **RedisVL** (Redis Vector Library) puts a vector index inside Redis. We embed the incoming query, and if it has a `>95%` vector similarity to a previously asked question, we instantly return the cached chunks. This bypasses the heavy Cross-Encoder for up to 50% of traffic.

---

## Part 2: Scenario A - Cloud-Native Distributed Architecture
This architecture is designed for AWS/GCP Kubernetes clusters, horizontally scaling across hundreds of smaller virtual machines.

### Scaling Strategy (Scale-Out)
*   **API Layer (CPU):** Stateless FastAPI pods. Scaled via K8s Horizontal Pod Autoscaler (HPA) based on CPU utilization. Scales from 10 to 1,000 pods in seconds.
*   **Inference Layer (GPU):** Triton pods. Scaled via KEDA (Kubernetes Event-driven Autoscaling) based on Queue Depth. Karpenter dynamically rents cloud GPUs when traffic spikes.
*   **Storage Layer:** Qdrant StatefulSets. Scaled by adding Read-Replicas to handle search spikes.

```mermaid
flowchart TD
    User([Million Users]) --> LB[Kubernetes Ingress / Load Balancer]
    
    subgraph Stateless Web Layer (CPU Auto-Scaled via HPA)
        LB --> API1[FastAPI Pod 1]
        LB --> API2[FastAPI Pod N]
    end
    
    subgraph Semantic Cache Layer
        API1 <--> Redis[(Redis Cluster)]
    end
    
    subgraph GPU Inference Layer (GPU Auto-Scaled via KEDA)
        API1 -- gRPC --> Triton[NVIDIA Triton Pods]
        Triton --> Embed[TensorRT Embedder]
        Triton --> Rerank[TensorRT Cross-Encoder]
    end
    
    subgraph Distributed Database Layer
        API1 --> Qdrant[(Qdrant Cluster)]
        Qdrant --> Hybrid[Native Hybrid Search: SPLADE + Dense]
    end
```

---

## Part 3: Scenario B - Bare-Metal Architecture (1TB RAM, 2x H200)
This architecture abandons cloud autoscaling and focuses entirely on **Hardware Saturation (Scale-Up)** for a massive single machine.

### Scaling Strategy (Scale-Up)
*   **Saturating 1000GB RAM:** Instead of disk reads, the vector database (`pgvector` or Qdrant) is allocated massive RAM limits (`shared_buffers=256GB`) to keep the entire index in memory. Redis is allocated 100GB for massive query caching.
*   **Saturating 2x H200s (141GB VRAM each):** The models are tiny (~2GB). Triton is configured with `instance_groups` to load **16 to 32 parallel replicas** of the model onto GPU 0, and another 16-32 replicas onto GPU 1. 
*   **Bypassing Python GIL:** FastAPI is run via Gunicorn with workers matching the physical CPU cores (e.g., 64 workers).

```mermaid
flowchart TD
    User([1,000,000+ Users]) --> Nginx[Local Nginx / HAProxy]
    
    subgraph Container 1: API Gateway (CPU Bound)
        Nginx --> G1[Gunicorn Worker 1]
        Nginx --> G2[Gunicorn Worker 64]
    end
    
    subgraph Container 4: Semantic Cache (100GB RAM Allocated)
        G1 <--> Redis[(Redis Stack Vector Cache)]
    end
    
    subgraph Container 2: Inference (2x H200 GPUs)
        G1 -- gRPC (Shared Memory) --> Triton[NVIDIA Triton Server]
        Triton --> R1[Model Replica 1...16 on GPU 0]
        Triton --> R2[Model Replica 17...32 on GPU 1]
    end
    
    subgraph Container 3: Storage (256GB RAM Allocated)
        G1 --> PG[(Postgres / Qdrant)]
        PG --> RAM[In-Memory HNSW Graph]
    end
```

---

## Part 4: Theoretical Implementation Specifications

### 1. Triton Configuration Theory (`config.pbtxt`)
To achieve the GPU saturation described in Scenario B, Triton relies on strict configuration parameters per model:
*   **Max Batch Size:** Set to `512`. Processing 512 queries simultaneously takes almost the exact same amount of time as processing 1 query due to the H200's 4.8 TB/s memory bandwidth.
*   **Dynamic Batching:** `max_queue_delay_microseconds: 5000`. Triton pauses for exactly 5 milliseconds to collect incoming web queries from the Gunicorn workers, bundles them, and fires them into the GPU as a single matrix multiplication block.
*   **Instance Groups:** The mapping configuration `count: 16` and `gpus: [0, 1]` forces Triton to copy the FP16 model 16 times into GPU 0 and 16 times into GPU 1, consuming ~32GB of VRAM and leaving over 100GB free for extreme dynamic batch computations.

### 2. Docker Compose Theory (Local Orchestration)
To stitch the Bare-Metal components together without Kubernetes, Docker Compose relies on extreme parameter tuning:
*   **Triton Container:** Uses the `nvidia` runtime with `count: all` to pass both H200s into the container. Crucially, it configures `shm_size: 32gb` (Shared Memory), allowing the FastAPI container to pass massive text tensors directly to Triton via shared RAM rather than slow TCP network overhead.
*   **API Container:** Unrestricted CPU access. Runs the command `gunicorn -w 64 -k uvicorn.workers.UvicornWorker`.

### 3. The End-to-End Request Trace
1.  **Edge:** 1,000 queries hit the Load Balancer simultaneously.
2.  **Routing:** Traffic is distributed instantly across the 64 Python workers.
3.  **Cache Check:** Workers embed the queries and ping the 100GB Redis cluster. 400 queries are semantic exact-matches and are returned instantly.
4.  **Inference:** The remaining 600 queries are sent via gRPC to Triton.
5.  **Batching:** Triton holds the 600 queries for 5ms, splits them into batches, and routes them to the TensorRT engines on GPU 0 and GPU 1.
6.  **Retrieval:** The embeddings are returned to the workers, which query the 256GB in-memory database.
7.  **Reranking:** Top results are sent back to Triton for Cross-Encoder scoring using dynamic batching.
8.  **Response:** Finalized top-K results are returned to the 1,000 users in under 100 milliseconds.
