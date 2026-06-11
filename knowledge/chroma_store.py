"""
Futurix Jarvis — ChromaDB Vector Store.

Concrete implementation of ``VectorStoreInterface`` backed by ChromaDB with
Ollama embeddings (nomic-embed-text).  Includes graceful degradation: if
ChromaDB or Ollama are unavailable at init time, the store reports itself
as unavailable and all operations become safe no-ops.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from knowledge.vector_store_interface import VectorStoreInterface

logger = logging.getLogger(__name__)


class OllamaEmbeddingFunction:
    """Custom embedding function for ChromaDB that calls Ollama directly via HTTP.

    If the Ollama server is unreachable, the function returns zero-vectors
    so that ChromaDB can still store documents (though retrieval quality
    will be degraded until Ollama comes back).
    """

    VECTOR_DIM = 768  # nomic-embed-text default dimension

    @staticmethod
    def name() -> str:
        return "OllamaEmbeddingFunction"

    def get_config(self) -> dict:
        return {"model_name": self.model_name, "base_url": self.base_url}

    def embed_query(self, input: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of queries (calls __call__)."""
        return self(input)

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of documents (calls __call__)."""
        return self(input)

    def __init__(
        self,
        model_name: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self._available: Optional[bool] = None  # lazy probe

    @property
    def available(self) -> bool:
        """Check (and cache) whether Ollama is reachable."""
        if self._available is None:
            self._available = self._probe_ollama()
        return self._available

    def reset_availability(self) -> None:
        """Force a re-probe on next call."""
        self._available = None

    def __call__(self, input: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        import httpx

        embeddings: list[list[float]] = []
        for text in input:
            try:
                response = httpx.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model_name, "prompt": text},
                    timeout=15.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    embeddings.append(data["embedding"])
                    # Mark as available on first success
                    if self._available is not True:
                        self._available = True
                else:
                    logger.warning(
                        "Ollama embedding request failed (HTTP %d). Using zero-vector fallback.",
                        response.status_code,
                    )
                    embeddings.append([0.0] * self.VECTOR_DIM)
            except Exception as exc:
                logger.error("Ollama embedding error: %s. Using zero-vector fallback.", exc)
                self._available = False
                embeddings.append([0.0] * self.VECTOR_DIM)
        return embeddings

    def _probe_ollama(self) -> bool:
        """Quick health-check against the Ollama API."""
        try:
            import httpx
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False


class ChromaVectorStore(VectorStoreInterface):
    """ChromaDB implementation of the VectorStoreInterface.

    Graceful init: if ``chromadb`` is not installed or the persistent
    directory can't be created, the store marks itself as unavailable
    rather than crashing the application.
    """

    def __init__(
        self,
        persist_dir: Path,
        collection_name: str = "jarvis_knowledge",
        model_name: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
    ) -> None:
        self._persist_dir = Path(persist_dir)
        self._collection_name = collection_name
        self._client = None
        self._collection = None
        self._embedding_func: Optional[OllamaEmbeddingFunction] = None
        self._init_error: Optional[str] = None

        try:
            self._init_store(model_name, base_url)
        except Exception as exc:
            self._init_error = str(exc)
            logger.warning(
                "ChromaVectorStore init failed — running in unavailable mode: %s", exc
            )

    def _init_store(self, model_name: str, base_url: str) -> None:
        """Attempt to initialise the ChromaDB backend."""
        import chromadb  # noqa: delayed import

        self._persist_dir.parent.mkdir(parents=True, exist_ok=True)
        self._persist_dir.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=str(self._persist_dir))
        self._embedding_func = OllamaEmbeddingFunction(
            model_name=model_name, base_url=base_url
        )
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            embedding_function=self._embedding_func,
        )
        logger.info(
            "ChromaVectorStore initialised at %s (collection='%s', embeddings=%s)",
            self._persist_dir,
            self._collection_name,
            model_name,
        )

    # ── Interface: add / search / clear ──────────────────────────────────

    def add_documents(self, documents: list[dict]) -> None:
        if not documents or not self.is_available():
            return

        ids: list[str] = []
        metadatas: list[dict] = []
        contents: list[str] = []

        for doc in documents:
            source = doc["source_file"]
            idx = doc["chunk_index"]
            content = doc["content"]

            ids.append(f"{source}#chunk_{idx}")
            metadatas.append({
                "source_file": source,
                "chunk_index": idx,
                **(doc.get("metadata", {})),
            })
            contents.append(content)

        # ChromaDB's `add` auto-upserts when IDs match.
        self._collection.upsert(
            ids=ids,
            metadatas=metadatas,
            documents=contents,
        )
        logger.debug("ChromaVectorStore: upserted %d documents", len(documents))

    def search(self, query: str, limit: int = 5) -> list[dict]:
        if not query.strip() or not self.is_available():
            return []

        results = self._collection.query(query_texts=[query], n_results=limit)

        output: list[dict] = []
        if results and results.get("documents") and results["documents"]:
            docs = results["documents"][0]
            metas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            for i, doc_text in enumerate(docs):
                meta = metas[i] if i < len(metas) else {}
                # ChromaDB distances — lower is better.  Convert to a 0-1 similarity score.
                dist = distances[i] if i < len(distances) else 0.0
                similarity = max(0.0, 1.0 - dist)

                output.append({
                    "source_file": meta.get("source_file", "unknown"),
                    "chunk_index": meta.get("chunk_index", 0),
                    "content": doc_text,
                    "score": round(similarity, 4),
                })
        return output

    def clear_store(self, source_file: Optional[str] = None) -> None:
        if not self.is_available():
            return

        if source_file:
            self._collection.delete(where={"source_file": source_file})
            logger.info("ChromaVectorStore: cleared documents for source: %s", source_file)
        else:
            name = self._collection.name
            self._client.delete_collection(name)
            self._collection = self._client.get_or_create_collection(
                name=name,
                embedding_function=self._embedding_func,
            )
            logger.info("ChromaVectorStore: cleared all documents in collection '%s'", name)

    # ── Interface: health & stats ────────────────────────────────────────

    def is_available(self) -> bool:
        return self._collection is not None and self._client is not None

    def document_count(self) -> int:
        if not self.is_available():
            return 0
        return self._collection.count()

    def collection_stats(self) -> dict[str, Any]:
        if not self.is_available():
            return {
                "backend": "chromadb",
                "status": "unavailable",
                "error": self._init_error,
                "document_count": 0,
                "persist_dir": str(self._persist_dir),
            }

        embeddings_available = (
            self._embedding_func.available if self._embedding_func else False
        )

        return {
            "backend": "chromadb",
            "status": "operational",
            "document_count": self._collection.count(),
            "collection_name": self._collection_name,
            "persist_dir": str(self._persist_dir),
            "embeddings_model": self._embedding_func.model_name if self._embedding_func else None,
            "embeddings_available": embeddings_available,
        }

    @property
    def embedding_function(self) -> Optional[OllamaEmbeddingFunction]:
        """Access the embedding function (useful for diagnostics)."""
        return self._embedding_func
