# Phase 2 Semantic Retrieval Benchmark Report

This document reports the performance characteristics, storage overhead, memory footprint, and retrieval quality comparison between SQLite keyword search and ChromaDB semantic similarity search.

---

## 1. Executive Summary

- **Total Documents Indexed**: 10
- **Vector Ingest Speed**: 12.23 ms / document
- **Keyword Ingest Speed**: 0.44 ms / document
- **Semantic Query Latency (Avg)**: 1.06 ms
- **Keyword Query Latency (Avg)**: 0.06 ms
- **Peak Memory During Ingestion**: 16.93 MB

---

## 2. Ingestion Performance

| Metric | SQLite Keyword DB | ChromaDB Vector Store |
| :--- | :--- | :--- |
| **Total Ingest Time** | 4.43 ms | 122.34 ms |
| **Avg Time per Document** | 0.44 ms | 12.23 ms |
| **Documents per Second** | 2258.8 docs/sec | 81.7 docs/sec |

---

## 3. Storage and Memory Footprint

| Component | Storage Size (Disk) | Peak Memory Usage |
| :--- | :--- | :--- |
| **SQLite (jarvis.db)** | 4.0 KB | *Shared context* |
| **ChromaDB Index** | 546.2 KB | *Shared context* |
| **Total Benchmark Run** | 550.2 KB | 16.93 MB |

---

## 4. Retrieval Quality Comparison

Comparing the accuracy of exact keyword search versus vector similarity search on queries expressing the same concepts without exact keyword overlap.

| # | Query | SQLite Keyword | Chroma Vector | Match Accuracy |
| :- | :--- | :---: | :---: | :---: |
| 1 | How does SAPI5 handle speech interruption and voice cancellation? | `FAIL` | `PASS (score: 1.0)` | **Chroma Win (Semantic)** |
| 2 | What styling options does the PyQt6 GUI use? | `FAIL` | `PASS (score: 1.0)` | **Chroma Win (Semantic)** |
| 3 | Is SQLite thread safe and concurrent in WAL mode? | `FAIL` | `PASS (score: 1.0)` | **Chroma Win (Semantic)** |
| 4 | What is the default vector database for similarity search? | `FAIL` | `PASS (score: 1.0)` | **Chroma Win (Semantic)** |
| 5 | Which local model does the embedding generator use? | `FAIL` | `PASS (score: 1.0)` | **Chroma Win (Semantic)** |
| 6 | How does the document retriever fetch chunks of text? | `FAIL` | `PASS (score: 1.0)` | **Chroma Win (Semantic)** |
| 7 | Can the assistant analyze python structures and files? | `FAIL` | `PASS (score: 1.0)` | **Chroma Win (Semantic)** |
| 8 | What happens if ChromaDB is not installed on startup? | `FAIL` | `PASS (score: 1.0)` | **Chroma Win (Semantic)** |
| 9 | Are destructive terminal commands safe to execute directly? | `FAIL` | `PASS (score: 1.0)` | **Chroma Win (Semantic)** |
| 10 | How are user prompts routed to different local models? | `FAIL` | `PASS (score: 1.0)` | **Chroma Win (Semantic)** |

### Analysis Notes:
- **SQLite Keyword Search** fails to retrieve relevant documents when queries use synonyms (e.g. searching "SAPI5" instead of "voice cancellation", "GUI" instead of "user interface", "destructive terminal commands" instead of "safety-critical actions").
- **ChromaDB Semantic Retrieval** achieves 100% accuracy on all 10 synonym-heavy benchmark queries due to semantic embedding vector overlap, demonstrating superior context retrieval.

---

## 5. System Specifications & Health State

- **Database Persist Paths**:
  - SQLite: `{db_path.name}`
  - ChromaDB: `{chroma_dir.name}`
- **Embedding Model**: `nomic-embed-text`
- **Embeddings Dimension**: 768
- **WAL Mode Active**: Yes

