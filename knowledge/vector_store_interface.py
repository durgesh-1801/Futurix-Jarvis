"""
Futurix Jarvis — Vector Store Interface.

Abstract base class that decouples RAGService from any specific vector
database implementation.  Concrete implementations include ChromaDB,
FAISS, pgvector, Milvus, or a simple in-memory fallback.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class VectorStoreInterface(ABC):
    """Abstract base class for vector store implementations.

    This ensures that RAGService is decoupled from ChromaDB and can
    be swapped with other databases (e.g. FAISS, pgvector, or Milvus)
    in the future.
    """

    @abstractmethod
    def add_documents(self, documents: list[dict]) -> None:
        """Add document chunks to the vector store.

        Args:
            documents: A list of dicts, each containing:
                       - "source_file": Path to the source document.
                       - "content": Text content of the chunk.
                       - "chunk_index": Index of the chunk.
                       - "metadata": (optional) Additional metadata dict.
        """

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Perform a vector-based similarity search.

        Args:
            query: The search query string.
            limit: The maximum number of matches to return.

        Returns:
            A list of matching dicts, each containing:
            - "source_file": Path of the source document.
            - "content": The matching text chunk.
            - "chunk_index": Index of the chunk.
            - "score": (optional) Similarity score (higher = better match).
        """

    @abstractmethod
    def clear_store(self, source_file: Optional[str] = None) -> None:
        """Clear all or specific documents from the vector store.

        Args:
            source_file: If provided, only delete chunks associated with this file.
                         If None, clear the entire vector store.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether the vector store backend is operational.

        Returns:
            True if the store is ready to accept queries and documents.
        """

    @abstractmethod
    def document_count(self) -> int:
        """Return the total number of document chunks stored.

        Returns:
            Integer count of stored chunks.
        """

    @abstractmethod
    def collection_stats(self) -> dict[str, Any]:
        """Return metadata/statistics about the vector store.

        Returns:
            Dict with keys like 'backend', 'document_count', 'persist_dir', etc.
        """

    def health_check(self) -> dict[str, Any]:
        """Run a comprehensive health check.

        Returns:
            Dict with 'healthy' (bool) and 'details' (str).
        """
        try:
            available = self.is_available()
            count = self.document_count() if available else 0
            return {
                "healthy": available,
                "document_count": count,
                "details": "operational" if available else "unavailable",
            }
        except Exception as exc:
            return {
                "healthy": False,
                "document_count": 0,
                "details": f"health check failed: {exc}",
            }
