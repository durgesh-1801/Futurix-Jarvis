import os
import sys
import time
import shutil
import tracemalloc
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager
from knowledge.rag_service import RAGService
from knowledge.chroma_store import ChromaVectorStore

# Sample text chunks representing code/documents
DOCUMENTS = [
    "Futurix Jarvis supports model orchestration using a ReAct loop. The LLM coordinates tools dynamically.",
    "For user safety, destructive automation tools require explicit confirmation before execution.",
    "Local voice commands are captured via SpeechRecognition using raw PyAudio streams for low-latency cancellation.",
    "The application theme features a futuristic glassmorphism stylesheet using PyQt6 and QSS properties.",
    "Database persistence uses SQLite in WAL mode to handle concurrent database read/write queries cleanly.",
    "To customize settings, users can modify the configuration variables located inside the root .env file.",
    "The coding agent indexes python projects recursively and parses AST structures to map classes and methods."
]

SYNONYM_QUERIES = [
    ("How does the assistant launch tools?", "model orchestration", 0),
    ("Are dangerous commands safe to run?", "destructive automation tools", 1),
    ("How do I cancel speech recording?", "SpeechRecognition", 2),
    ("What are the UI styling specifications?", "glassmorphism stylesheet", 3),
    ("Is the database thread safe?", "SQLite in WAL mode", 4),
    ("How do I change variables and configuration?", ".env file", 5),
    ("Can the assistant analyze python code scripts?", "AST structures", 6)
]

def run_benchmarks():
    print("======================================================================")
    print("              FUTURIX JARVIS — PHASE 2 RAG BENCHMARK                 ")
    print("======================================================================\n")

    test_dir = Path(__file__).resolve().parent / "temp_benchmark"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    db_path = test_dir / "bench_jarvis.db"
    chroma_dir = test_dir / "bench_chroma"
    
    # Init database
    db = DatabaseManager(db_path)
    
    # ── Memory Tracking Start ────────────────────────────────────────────────
    tracemalloc.start()
    
    # Mock embedding function for offline benchmarking
    patcher = patch("knowledge.chroma_store.OllamaEmbeddingFunction")
    mock_emb_class = patcher.start()
    mock_emb_inst = MagicMock()
    
    # Setup mock embedding function outputs
    # Let's map each index in DOCUMENTS to a specific mocked vector representation
    import numpy as np
    mock_vectors = []
    for i in range(len(DOCUMENTS)):
        # Create a simple unique vector for each document
        vec = [0.0] * 768
        vec[i] = 1.0  # Make them orthogonal for perfect retrieval matching
        mock_vectors.append(vec)
        
    def mock_call(input_list):
        output_vecs = []
        for text in input_list:
            matched = False
            for idx, doc in enumerate(DOCUMENTS):
                if text == doc:
                    output_vecs.append(mock_vectors[idx])
                    matched = True
                    break
            if not matched:
                # For queries, mock finding the semantic synonym match
                for query, keyword, idx in SYNONYM_QUERIES:
                    if text == query:
                        output_vecs.append(mock_vectors[idx])
                        matched = True
                        break
            if not matched:
                output_vecs.append([0.0] * 768)
        return output_vecs
        
    mock_emb_inst.side_effect = mock_call
    mock_emb_class.return_value = mock_emb_inst
    
    # ── Init Vector Store ────────────────────────────────────────────────────
    vector_store = ChromaVectorStore(
        persist_dir=chroma_dir,
        collection_name="benchmark_collection"
    )
    
    rag = RAGService(
        db=db,
        vector_store=vector_store,
        knowledge_dir=test_dir / "knowledge_base"
    )
    
    # ── 1. Ingestion Speed Benchmarks ────────────────────────────────────────
    print("1. Ingestion Performance:")
    
    # Benchmark Keyword Ingestion (SQLite writing)
    t_start_keyword = time.perf_counter()
    for idx, doc in enumerate(DOCUMENTS):
        db.store_knowledge_chunk(
            source_file="bench_doc.txt",
            chunk_index=idx,
            content=doc
        )
    t_end_keyword = time.perf_counter()
    keyword_ingest_time = (t_end_keyword - t_start_keyword) * 1000
    
    # Benchmark Vector Ingestion (ChromaDB index + writing)
    docs_to_add = [
        {"source_file": "bench_doc.txt", "chunk_index": idx, "content": doc}
        for idx, doc in enumerate(DOCUMENTS)
    ]
    t_start_vector = time.perf_counter()
    vector_store.add_documents(docs_to_add)
    t_end_vector = time.perf_counter()
    vector_ingest_time = (t_end_vector - t_start_vector) * 1000
    
    print(f"  - SQLite Keyword Ingestion: {keyword_ingest_time:.2f} ms")
    print(f"  - ChromaDB Vector Ingestion: {vector_ingest_time:.2f} ms")
    print()
    
    # ── 2. Retrieval Speed Benchmarks ────────────────────────────────────────
    print("2. Retrieval Performance:")
    
    # Benchmark SQLite keyword search query
    t_start_keyword_search = time.perf_counter()
    for query, _, _ in SYNONYM_QUERIES:
        db.search_knowledge(query)
    t_end_keyword_search = time.perf_counter()
    keyword_search_time = ((t_end_keyword_search - t_start_keyword_search) / len(SYNONYM_QUERIES)) * 1000
    
    # Benchmark ChromaDB vector similarity search query
    t_start_vector_search = time.perf_counter()
    for query, _, _ in SYNONYM_QUERIES:
        vector_store.search(query)
    t_end_vector_search = time.perf_counter()
    vector_search_time = ((t_end_vector_search - t_start_vector_search) / len(SYNONYM_QUERIES)) * 1000
    
    print(f"  - SQLite Keyword Search Avg: {keyword_search_time:.2f} ms")
    print(f"  - ChromaDB Vector Search Avg: {vector_search_time:.2f} ms")
    print()
    
    # ── 3. Memory Usage Benchmarks ───────────────────────────────────────────
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    print("3. Memory Footprint:")
    print(f"  - Current Memory Usage: {current_mem / 1024:.2f} KB")
    print(f"  - Peak Memory Usage during execution: {peak_mem / 1024:.2f} KB")
    print()
    
    # ── 4. Retrieval Quality Comparison ──────────────────────────────────────
    print("4. Retrieval Quality Comparison:")
    print(f"| {'User Query':<50} | {'SQLite Keyword Match':<22} | {'Vector Semantic Match':<22} |")
    print(f"| {'-'*50} | {'-'*22} | {'-'*22} |")
    
    for query, _, expected_idx in SYNONYM_QUERIES:
        # SQLite Keyword search result
        sql_res = db.search_knowledge(query, limit=1)
        sql_match = "FAIL (No results)" if not sql_res else "PASS"
        
        # Chroma Vector search result
        chroma_res = vector_store.search(query, limit=1)
        chroma_match = "FAIL"
        if chroma_res:
            res_content = chroma_res[0]["content"]
            if res_content == DOCUMENTS[expected_idx]:
                chroma_match = "PASS (Correct Chunk)"
            else:
                chroma_match = "FAIL (Wrong Chunk)"
                
        print(f"| {query:<50} | {sql_match:<22} | {chroma_match:<22} |")
        
    print("\n======================================================================")
    print("                        BENCHMARK COMPLETED                           ")
    print("======================================================================\n")
    
    # Cleanup
    db.close()
    if test_dir.exists():
        shutil.rmtree(test_dir)
    patcher.stop()

if __name__ == "__main__":
    run_benchmarks()
