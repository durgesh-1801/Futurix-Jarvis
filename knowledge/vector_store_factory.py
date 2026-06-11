"""
Futurix Jarvis — Vector Store Factory.

Constructs the best available ``VectorStoreInterface`` implementation at
startup and transparently falls back to ``InMemoryVectorStore`` when
ChromaDB or Ollama embeddings are unavailable.

This ensures that ``RAGService`` never needs to know which backend is
active, and new providers can be added here without modifying RAGService.
"""

from __future__ import annotations

import logging
from pathlib import Path

from knowledge.vector_store_interface import VectorStoreInterface

logger = logging.getLogger(__name__)


def create_vector_store(
    persist_dir: Path,
    collection_name: str = "jarvis_knowledge",
    model_name: str = "nomic-embed-text",
    base_url: str = "http://localhost:11434",
) -> VectorStoreInterface:
    """Create the best available vector store.

    Attempts to initialise ChromaDB first.  If that fails (missing library,
    init error, etc.), falls back to an in-memory TF-IDF store.

    Args:
        persist_dir: Directory for persistent ChromaDB storage.
        collection_name: ChromaDB collection name.
        model_name: Ollama embedding model name.
        base_url: Ollama server URL.

    Returns:
        A ready-to-use ``VectorStoreInterface`` implementation.
    """
    # ── Try ChromaDB first ───────────────────────────────────────────────
    try:
        from knowledge.chroma_store import ChromaVectorStore

        store = ChromaVectorStore(
            persist_dir=persist_dir,
            collection_name=collection_name,
            model_name=model_name,
            base_url=base_url,
        )
        if store.is_available():
            stats = store.collection_stats()
            logger.info(
                "Vector store: ChromaDB (collection='%s', docs=%d, embeddings=%s)",
                collection_name,
                stats.get("document_count", 0),
                "✓" if stats.get("embeddings_available") else "✗ (zero-vector fallback)",
            )
            return store
        else:
            logger.warning(
                "ChromaDB initialised but is_available() returned False. "
                "Falling back to in-memory store."
            )
    except ImportError:
        logger.warning(
            "chromadb package not installed. Falling back to in-memory vector store. "
            "Install with: pip install chromadb"
        )
    except Exception as exc:
        logger.warning(
            "ChromaDB init failed: %s. Falling back to in-memory vector store.", exc
        )

    # ── Fallback: in-memory TF-IDF ───────────────────────────────────────
    from knowledge.memory_store import InMemoryVectorStore

    store = InMemoryVectorStore()
    logger.info("Vector store: InMemoryVectorStore (TF-IDF fallback)")
    return store
