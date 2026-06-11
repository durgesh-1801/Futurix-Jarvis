"""
Futurix Jarvis — In-Memory Vector Store (Fallback).

A simple in-memory vector store that performs TF-IDF–style keyword matching.
Used as an automatic fallback when ChromaDB or Ollama embeddings are
unavailable, ensuring the application always has some retrieval capability.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Any, Optional

from knowledge.vector_store_interface import VectorStoreInterface

logger = logging.getLogger(__name__)


class InMemoryVectorStore(VectorStoreInterface):
    """Fallback vector store using TF-IDF keyword matching.

    Stores documents in memory and uses a simple term-frequency ×
    inverse-document-frequency scoring model for retrieval.  No external
    dependencies are required.
    """

    def __init__(self) -> None:
        self._documents: list[dict] = []   # Each: {source_file, chunk_index, content, metadata}
        self._idf_cache: dict[str, float] = {}
        self._dirty = True  # True when IDF needs recalculation
        logger.info("InMemoryVectorStore initialised (fallback mode)")

    # ── Interface implementation ─────────────────────────────────────────

    def add_documents(self, documents: list[dict]) -> None:
        if not documents:
            return
        for doc in documents:
            self._documents.append({
                "source_file": doc["source_file"],
                "chunk_index": doc["chunk_index"],
                "content": doc["content"],
                "metadata": doc.get("metadata", {}),
            })
        self._dirty = True
        logger.debug("InMemoryVectorStore: added %d documents (total: %d)",
                      len(documents), len(self._documents))

    def search(self, query: str, limit: int = 5) -> list[dict]:
        if not query.strip() or not self._documents:
            return []

        if self._dirty:
            self._rebuild_idf()

        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        scored: list[tuple[float, dict]] = []
        for doc in self._documents:
            score = self._score_document(query_terms, doc["content"])
            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, doc in scored[:limit]:
            results.append({
                "source_file": doc["source_file"],
                "chunk_index": doc["chunk_index"],
                "content": doc["content"],
                "score": round(score, 4),
            })
        return results

    def clear_store(self, source_file: Optional[str] = None) -> None:
        if source_file:
            before = len(self._documents)
            self._documents = [
                d for d in self._documents if d["source_file"] != source_file
            ]
            removed = before - len(self._documents)
            logger.info("InMemoryVectorStore: removed %d docs for %s", removed, source_file)
        else:
            self._documents.clear()
            logger.info("InMemoryVectorStore: cleared all documents")
        self._dirty = True

    def is_available(self) -> bool:
        return True  # Always available — it's in-memory

    def document_count(self) -> int:
        return len(self._documents)

    def collection_stats(self) -> dict[str, Any]:
        sources = {d["source_file"] for d in self._documents}
        return {
            "backend": "in_memory_tfidf",
            "document_count": len(self._documents),
            "unique_sources": len(sources),
            "persist_dir": None,
        }

    # ── TF-IDF internals ─────────────────────────────────────────────────

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Lowercase tokenization with basic punctuation stripping."""
        return re.findall(r"\b[a-z0-9_]+\b", text.lower())

    def _rebuild_idf(self) -> None:
        """Recalculate inverse-document-frequency for all terms."""
        n = len(self._documents)
        if n == 0:
            self._idf_cache = {}
            self._dirty = False
            return

        doc_freq: Counter[str] = Counter()
        for doc in self._documents:
            terms = set(self._tokenize(doc["content"]))
            for term in terms:
                doc_freq[term] += 1

        self._idf_cache = {
            term: math.log((n + 1) / (df + 1)) + 1
            for term, df in doc_freq.items()
        }
        self._dirty = False

    def _score_document(self, query_terms: list[str], content: str) -> float:
        """Calculate TF-IDF similarity score between query and document."""
        doc_terms = self._tokenize(content)
        if not doc_terms:
            return 0.0

        doc_tf: Counter[str] = Counter(doc_terms)
        max_tf = max(doc_tf.values()) if doc_tf else 1

        score = 0.0
        for term in query_terms:
            if term in doc_tf:
                tf = 0.5 + 0.5 * (doc_tf[term] / max_tf)  # augmented TF
                idf = self._idf_cache.get(term, 1.0)
                score += tf * idf

        return score
