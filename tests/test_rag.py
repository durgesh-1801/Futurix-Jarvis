import sys
import os
import unittest
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager
from knowledge.rag_service import RAGService
from knowledge.chroma_store import ChromaVectorStore

class TestRAGSemanticSearch(unittest.TestCase):
    """Unit tests for ChromaVectorStore and RAGService semantic retrieval."""

    def setUp(self):
        # Create temp directories for test DB and Chroma
        self.test_dir = Path(__file__).resolve().parent / "temp_rag_test"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.test_dir / "test_jarvis.db"
        self.chroma_dir = self.test_dir / "chroma_db"
        
        # Init SQLite database
        self.db = DatabaseManager(self.db_path)
        
        # Mock the embedding function to return static mock embeddings
        # so we don't need a running Ollama service for running these tests
        self.patcher = patch("knowledge.chroma_store.OllamaEmbeddingFunction")
        self.mock_emb_class = self.patcher.start()
        
        # Mock embedding function returns lists of lists of floats
        self.mock_emb_inst = MagicMock()
        self.mock_emb_inst.return_value = [[0.1] * 768, [0.2] * 768]
        self.mock_emb_class.return_value = self.mock_emb_inst
        
        # Init ChromaVectorStore with mocked embeddings
        self.vector_store = ChromaVectorStore(
            persist_dir=self.chroma_dir,
            collection_name="test_collection"
        )
        
        # Init RAGService
        self.rag = RAGService(
            db=self.db,
            vector_store=self.vector_store,
            knowledge_dir=self.test_dir / "knowledge_base"
        )

    def tearDown(self):
        # Close database connection
        self.db.close()
        # Clean up temp directories
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.patcher.stop()

    def test_ingestion_and_retrieval(self):
        # Create a temp txt file
        doc_path = self.rag._knowledge_dir / "billing_info.txt"
        doc_path.write_text("Futurix Jarvis supports semantic retrieval. The secret key is ALPHA-100.", encoding="utf-8")
        
        # Ingest file
        chunks_added = self.rag.ingest_file(doc_path)
        self.assertEqual(chunks_added, 1)
        
        # Verify chunks exist in SQLite database
        db_chunks = self.db.search_knowledge("ALPHA-100")
        self.assertEqual(len(db_chunks), 1)
        self.assertEqual(db_chunks[0]["source_file"], str(doc_path))
        
        # Query semantic retrieval
        results = self.rag.retrieve("secret key")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source_file"], str(doc_path))
        self.assertIn("ALPHA-100", results[0]["content"])
        
        # Clear vector store for the file
        self.rag._vector_store.clear_store(str(doc_path))
        
        # Verify it is gone from vector store
        results_after_clear = self.rag.retrieve("secret key")
        self.assertEqual(len(results_after_clear), 0)


if __name__ == "__main__":
    unittest.main()
