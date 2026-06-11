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
from knowledge.vector_store_interface import VectorStoreInterface
from knowledge.memory_store import InMemoryVectorStore
from knowledge.chroma_store import ChromaVectorStore, OllamaEmbeddingFunction
from knowledge.vector_store_factory import create_vector_store


class TestVectorStoreAbstractions(unittest.TestCase):
    """Test the vector store interfaces and fallback implementation."""

    def test_in_memory_store_lifecycle(self):
        """Test InMemoryVectorStore basic CRUD, TF-IDF matching and clear."""
        store = InMemoryVectorStore()
        self.assertTrue(store.is_available())
        self.assertEqual(store.document_count(), 0)

        docs = [
            {"source_file": "doc1.txt", "chunk_index": 0, "content": "The quick brown fox jumps over the lazy dog"},
            {"source_file": "doc2.txt", "chunk_index": 0, "content": "Artificial intelligence and machine learning are transformative"}
        ]
        store.add_documents(docs)
        self.assertEqual(store.document_count(), 2)

        # Search matching fox
        res = store.search("fox")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["source_file"], "doc1.txt")
        self.assertIn("fox", res[0]["content"])

        # Search matching machine
        res = store.search("machine")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["source_file"], "doc2.txt")

        # Stats
        stats = store.collection_stats()
        self.assertEqual(stats["backend"], "in_memory_tfidf")
        self.assertEqual(stats["document_count"], 2)

        # Clear one file
        store.clear_store("doc1.txt")
        self.assertEqual(store.document_count(), 1)
        self.assertEqual(len(store.search("fox")), 0)

        # Clear all
        store.clear_store()
        self.assertEqual(store.document_count(), 0)

    @patch("chromadb.PersistentClient")
    def test_chroma_store_mocked(self, mock_client_class):
        """Test ChromaVectorStore with mocked chromadb client."""
        # Custom mock class to satisfy Chroma's inspect signature requirement
        class MockEmbeddingFunction:
            @staticmethod
            def name() -> str:
                return "MockEmbeddingFunction"

            def get_config(self) -> dict:
                return {}

            def embed_query(self, input: list[str]) -> list[list[float]]:
                return self(input)

            def embed_documents(self, input: list[str]) -> list[list[float]]:
                return self(input)

            def __call__(self, input: list[str]) -> list[list[float]]:
                return [[0.1] * 768] * len(input)

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_client_class.return_value = mock_client

        mock_collection.count.return_value = 5
        mock_collection.query.return_value = {
            "documents": [["mock content 1", "mock content 2"]],
            "metadatas": [[{"source_file": "file1.py", "chunk_index": 0}, {"source_file": "file2.py", "chunk_index": 1}]],
            "distances": [[0.1, 0.4]]
        }

        # Patch class construction to return our MockEmbeddingFunction instance
        with patch("knowledge.chroma_store.OllamaEmbeddingFunction", return_value=MockEmbeddingFunction()):
            store = ChromaVectorStore(persist_dir=Path("fake_dir"))

        self.assertTrue(store.is_available())
        self.assertEqual(store.document_count(), 5)

        # Search
        res = store.search("query")
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["source_file"], "file1.py")
        self.assertEqual(res[0]["content"], "mock content 1")
        self.assertEqual(res[0]["score"], 0.9)  # 1.0 - 0.1

        # Clear one file
        store.clear_store("file1.py")
        mock_collection.delete.assert_called_with(where={"source_file": "file1.py"})

        # Clear all
        store.clear_store()
        mock_client.delete_collection.assert_called_with(mock_collection.name)


class TestRAGServiceIngestion(unittest.TestCase):
    """Test RAGService ingestion of various document formats."""

    def setUp(self):
        self.test_dir = Path(__file__).resolve().parent / "temp_rag_test"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.test_dir / "test_jarvis.db"
        self.db = DatabaseManager(self.db_path)
        self.vector_store = InMemoryVectorStore()
        
        self.rag = RAGService(
            db=self.db,
            vector_store=self.vector_store,
            knowledge_dir=self.test_dir / "knowledge_base"
        )

    def tearDown(self):
        self.db.close()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_plain_text_ingestion(self):
        """Test plain text file ingestion."""
        doc_path = self.rag._knowledge_dir / "test.txt"
        doc_path.write_text("This is plain text content for testing RAG service ingestion.", encoding="utf-8")
        
        chunks = self.rag.ingest_file(doc_path)
        self.assertEqual(chunks, 1)
        self.assertEqual(self.vector_store.document_count(), 1)
        
        # Verify SQLite DB also stored it
        db_rows = self.db.search_knowledge("RAG service")
        self.assertEqual(len(db_rows), 1)

    def test_markdown_ingestion(self):
        """Test Markdown file ingestion."""
        doc_path = self.rag._knowledge_dir / "readme.md"
        markdown_content = (
            "# Project Title\n\n"
            "## Description\n"
            "Jarvis is an AI coding assistant.\n\n"
            "## Features\n"
            "- Voice interruption\n"
            "- Semantic RAG search\n"
        )
        doc_path.write_text(markdown_content, encoding="utf-8")
        
        chunks = self.rag.ingest_file(doc_path)
        self.assertEqual(chunks, 1)
        
        results = self.rag.retrieve("Voice interruption")
        self.assertEqual(len(results), 1)
        self.assertIn("Semantic RAG search", results[0]["content"])

    @patch("pypdf.PdfReader")
    def test_pdf_ingestion(self, mock_pdf_reader_class):
        """Test PDF ingestion with pypdf mocked."""
        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Extracting text from a mock PDF file page 1. Semantic indexing is fun."
        mock_reader.pages = [mock_page]
        mock_pdf_reader_class.return_value = mock_reader

        doc_path = self.rag._knowledge_dir / "manual.pdf"
        doc_path.write_text("", encoding="utf-8")  # create empty mock file

        chunks = self.rag.ingest_file(doc_path)
        self.assertEqual(chunks, 1)
        
        results = self.rag.retrieve("Semantic indexing")
        self.assertEqual(len(results), 1)
        self.assertIn("Semantic indexing is fun", results[0]["content"])

    def test_source_code_ingestion(self):
        """Test source code (.py) ingestion."""
        doc_path = self.rag._knowledge_dir / "utils.py"
        code_content = (
            "def calculate_metrics(values):\n"
            "    \"\"\"Compute sum and mean of values.\"\"\"\n"
            "    s = sum(values)\n"
            "    m = s / len(values) if values else 0\n"
            "    return s, m\n"
        )
        doc_path.write_text(code_content, encoding="utf-8")

        chunks = self.rag.ingest_file(doc_path)
        self.assertEqual(chunks, 1)

        results = self.rag.retrieve("calculate_metrics")
        self.assertEqual(len(results), 1)
        self.assertIn("Compute sum and mean", results[0]["content"])


class TestSemanticRetrievalFallback(unittest.TestCase):
    """Test semantic search quality and fallback mechanics."""

    def setUp(self):
        self.test_dir = Path(__file__).resolve().parent / "temp_fallback_test"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.test_dir / "test_jarvis.db"
        self.db = DatabaseManager(self.db_path)
        
        # We'll mock a failing/unavailable vector store
        self.mock_vector_store = MagicMock(spec=VectorStoreInterface)
        self.mock_vector_store.is_available.return_value = False
        
        self.rag = RAGService(
            db=self.db,
            vector_store=self.mock_vector_store,
            knowledge_dir=self.test_dir / "knowledge_base"
        )

    def tearDown(self):
        self.db.close()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_keyword_fallback_on_unavailable_vector_store(self):
        """RAGService should fall back to SQLite when vector store is unavailable."""
        # Insert raw keyword row directly in DB
        self.db.store_knowledge_chunk(
            source_file="manual.txt",
            chunk_index=0,
            content="Fallback keyword test: secret token is XYZ-777."
        )

        results = self.rag.retrieve("XYZ-777")
        # Assert fallback worked
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source_file"], "manual.txt")
        self.assertIn("XYZ-777", results[0]["content"])
        self.mock_vector_store.search.assert_not_called()

    def test_keyword_fallback_on_empty_semantic_results(self):
        """RAGService should fall back to SQLite when vector store returns 0 results."""
        self.mock_vector_store.is_available.return_value = True
        self.mock_vector_store.search.return_value = []  # Empty results

        self.db.store_knowledge_chunk(
            source_file="manual.txt",
            chunk_index=0,
            content="Fallback keyword test: another secret token is ABC-123."
        )

        results = self.rag.retrieve("ABC-123")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source_file"], "manual.txt")
        self.assertIn("ABC-123", results[0]["content"])
        self.mock_vector_store.search.assert_called_once()


class TestGracefulStartup(unittest.TestCase):
    """Test startup behaviors when components are offline."""

    @patch("chromadb.PersistentClient")
    def test_startup_chromadb_unavailable_fallback(self, mock_client):
        """If chromadb client initialization throws error, factory should return InMemory store."""
        mock_client.side_effect = Exception("ChromaDB library error, e.g., sqlite3 version match fail.")
        
        store = create_vector_store(persist_dir=Path("nonexistent"))
        self.assertIsInstance(store, InMemoryVectorStore)
        self.assertTrue(store.is_available())

    @patch("httpx.post")
    @patch("httpx.get")
    def test_startup_ollama_unavailable_embedding_fallback(self, mock_get, mock_post):
        """If Ollama is down/errors out, embedding function should yield zeros instead of raising error."""
        mock_get.side_effect = Exception("Connection refused")
        mock_post.side_effect = Exception("Timeout error")

        emb_func = OllamaEmbeddingFunction()
        self.assertFalse(emb_func.available)  # Probe should fail

        embeddings = emb_func(["Hello World", "Machine Learning"])
        self.assertEqual(len(embeddings), 2)
        self.assertEqual(embeddings[0], [0.0] * 768)
        self.assertEqual(embeddings[1], [0.0] * 768)


if __name__ == "__main__":
    unittest.main()
