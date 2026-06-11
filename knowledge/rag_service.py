"""
Futurix Jarvis — RAG Knowledge Base Service.

Provides document ingestion (PDF, TXT, MD, source code files) with chunking
and semantic retrieval. Includes fallback to keyword search.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

from database.db_manager import DatabaseManager
from knowledge.vector_store_interface import VectorStoreInterface

logger = logging.getLogger(__name__)


class RAGService:
    """Retrieval-Augmented Generation service for document Q&A.

    Ingests documents (PDFs, text files, Markdown, source code) into chunked storage,
    then retrieves relevant chunks to augment LLM context using semantic search,
    with a fallback to SQLite keyword search if vector store is unavailable.
    """

    def __init__(
        self,
        db: DatabaseManager,
        vector_store: VectorStoreInterface,
        knowledge_dir: Path = Path("knowledge_base"),
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> None:
        self._db = db
        self._vector_store = vector_store
        self._knowledge_dir = knowledge_dir
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._knowledge_dir.mkdir(parents=True, exist_ok=True)

    # ── Document ingestion ───────────────────────────────────────────────

    def ingest_file(self, file_path: Path) -> int:
        """Ingest a single document into the knowledge base.

        Supported formats: .txt, .md, .pdf, and source code files.

        Args:
            file_path: Path to the document file.

        Returns:
            Number of chunks created.
        """
        file_path = Path(file_path).resolve()
        if not file_path.exists():
            logger.error("File not found: %s", file_path)
            return 0

        content = self._extract_text(file_path)
        if not content:
            return 0

        # Clear old chunks for this file
        self._db.clear_knowledge(str(file_path))
        self._vector_store.clear_store(str(file_path))

        # Chunk the content
        chunks = self._chunk_text(content)
        docs_to_add = []
        for idx, chunk in enumerate(chunks):
            self._db.store_knowledge_chunk(
                source_file=str(file_path),
                chunk_index=idx,
                content=chunk,
            )
            docs_to_add.append({
                "source_file": str(file_path),
                "chunk_index": idx,
                "content": chunk
            })

        if docs_to_add:
            try:
                self._vector_store.add_documents(docs_to_add)
            except Exception as exc:
                logger.error("Failed to add documents to vector store: %s", exc)

        logger.info("Ingested %s → %d chunks", file_path.name, len(chunks))
        return len(chunks)

    def ingest_directory(self, directory: Optional[Path] = None) -> dict[str, int]:
        """Ingest all supported files from a directory.

        Args:
            directory: Directory to scan. Defaults to ``knowledge_dir``.

        Returns:
            Dict mapping filename → chunk count.
        """
        target = directory or self._knowledge_dir
        target = Path(target).resolve()

        if not target.exists():
            logger.warning("Knowledge directory does not exist: %s", target)
            return {}

        results = {}
        # Basic supported extension list for standard documents
        supported = (".txt", ".md", ".pdf", ".py", ".json", ".csv")

        for file_path in sorted(target.rglob("*")):
            if file_path.is_file() and file_path.suffix.lower() in supported:
                count = self.ingest_file(file_path)
                results[file_path.name] = count

        logger.info("Ingested %d files from %s", len(results), target)
        return results

    def ingest_repository(self, repo_path: Path) -> dict[str, int]:
        """Index all supported code and doc files in a repository recursively.

        Skips build/dependency directories and binary/large files.

        Args:
            repo_path: Root path of the repository.

        Returns:
            Dict mapping filename to chunk count.
        """
        repo_path = Path(repo_path).resolve()
        if not repo_path.exists():
            logger.error("Repository directory not found: %s", repo_path)
            return {}

        results = {}
        skip_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            ".tox", "dist", "build", "target", ".idea", ".vscode", "eggs", "parts"
        }

        # Extended extensions for repository source code support
        supported = (
            ".txt", ".md", ".py", ".json", ".csv",
            ".js", ".ts", ".tsx", ".jsx", ".java", ".cpp", ".c", ".h",
            ".rs", ".go", ".sh", ".bat", ".yaml", ".yml", ".toml", ".sql", ".css", ".html",
            ".pdf"
        )

        logger.info("Starting repository indexing at: %s", repo_path)
        for file_path in repo_path.rglob("*"):
            # Skip if any directory path component is in skip_dirs
            if any(part in skip_dirs for part in file_path.parts):
                continue
            
            if file_path.is_file() and file_path.suffix.lower() in supported:
                # Skip files that are too large (> 1MB) to prevent token pollution / latency
                try:
                    if file_path.stat().st_size > 1024 * 1024:
                        logger.warning("Skipping too large file: %s", file_path)
                        continue
                except Exception:
                    pass

                count = self.ingest_file(file_path)
                if count > 0:
                    # Use relative path as key for better context
                    try:
                        rel_path = file_path.relative_to(repo_path)
                        results[str(rel_path)] = count
                    except ValueError:
                        results[file_path.name] = count

        logger.info("Repository indexing completed. Ingested %d files.", len(results))
        return results

    # ── Retrieval ────────────────────────────────────────────────────────

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """Retrieve relevant document chunks for a query using semantic search.

        Falls back to keyword search if vector store is unavailable or empty.

        Args:
            query: The user's question or search terms.
            top_k: Maximum number of chunks to return.

        Returns:
            List of chunk dicts with ``source_file``, ``content``, and ``score``.
        """
        try:
            if self._vector_store.is_available():
                results = self._vector_store.search(query, limit=top_k)
                if results:
                    return results

            # Fallback to database keyword search
            logger.info("Semantic store returned no results or is unavailable. Falling back to keyword search.")
            db_results = self._db.search_knowledge(query, limit=top_k)
            return [
                {
                    "source_file": r["source_file"],
                    "chunk_index": r["chunk_index"],
                    "content": r["content"],
                    "score": 0.0,
                }
                for r in db_results
            ]
        except Exception as exc:
            logger.error("Error during semantic search: %s. Falling back to keyword search.", exc)
            try:
                db_results = self._db.search_knowledge(query, limit=top_k)
                return [
                    {
                        "source_file": r["source_file"],
                        "chunk_index": r["chunk_index"],
                        "content": r["content"],
                        "score": 0.0,
                    }
                    for r in db_results
                ]
            except Exception as sql_exc:
                logger.error("Keyword search fallback also failed: %s", sql_exc)
                return []

    def retrieve_context_string(self, query: str, top_k: int = 5) -> str:
        """Retrieve relevant chunks as a formatted context string.

        Args:
            query: The search query.
            top_k: Maximum chunks.

        Returns:
            A string containing the relevant document excerpts.
        """
        chunks = self.retrieve(query, top_k)
        if not chunks:
            return ""

        parts = ["**Relevant knowledge base excerpts:**\n"]
        for i, chunk in enumerate(chunks, 1):
            source = Path(chunk.get("source_file", "unknown")).name
            content = chunk.get("content", "")
            score = chunk.get("score")
            score_str = f" (score: {score})" if score is not None and score > 0 else ""
            parts.append(f"**[{i}] {source}{score_str}:**\n{content}\n")

        return "\n".join(parts)

    # ── Text extraction ──────────────────────────────────────────────────

    def _extract_text(self, file_path: Path) -> str:
        """Extract text from a file based on its extension."""
        suffix = file_path.suffix.lower()

        # Extended extensions for repository source code support
        text_extensions = (
            ".txt", ".md", ".py", ".json", ".csv",
            ".js", ".ts", ".tsx", ".jsx", ".java", ".cpp", ".c", ".h",
            ".rs", ".go", ".sh", ".bat", ".yaml", ".yml", ".toml", ".sql", ".css", ".html"
        )

        if suffix in text_extensions:
            return self._read_text_file(file_path)
        elif suffix == ".pdf":
            return self._read_pdf_file(file_path)
        else:
            logger.warning("Unsupported file format: %s", suffix)
            return ""

    @staticmethod
    def _read_text_file(path: Path) -> str:
        """Read a plain text file."""
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            logger.error("Failed to read %s: %s", path, exc)
            return ""

    @staticmethod
    def _read_pdf_file(path: Path) -> str:
        """Extract text from a PDF file using pypdf if available."""
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return "\n\n".join(text_parts)

        except ImportError:
            logger.warning("pypdf not installed — skipping PDF: %s", path)
            return ""
        except Exception as exc:
            logger.error("Failed to read PDF %s: %s", path, exc)
            return ""

    # ── Chunking ─────────────────────────────────────────────────────────

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into overlapping chunks.

        Args:
            text: The full document text.

        Returns:
            List of text chunks.
        """
        if len(text) <= self._chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self._chunk_size
            # Try to break at a paragraph or sentence boundary
            if end < len(text):
                # Look for paragraph break
                para_break = text.rfind("\n\n", start, end)
                if para_break > start + self._chunk_size // 2:
                    end = para_break + 2
                else:
                    # Look for sentence break
                    for sep in (". ", ".\n", "! ", "? "):
                        sent_break = text.rfind(sep, start, end)
                        if sent_break > start + self._chunk_size // 2:
                            end = sent_break + len(sep)
                            break

            chunks.append(text[start:end].strip())
            start = end - self._chunk_overlap

        return [c for c in chunks if c]

    # ── Stats ────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return knowledge base statistics."""
        results = self._db.search_knowledge("", limit=100000)
        sources = set()
        total_chunks = len(results)
        for r in results:
            sources.add(r.get("source_file", ""))
        
        vector_stats = {}
        if self._vector_store.is_available():
            try:
                vector_stats = self._vector_store.collection_stats()
            except Exception:
                pass

        return {
            "total_documents": len(sources),
            "total_chunks": total_chunks,
            "knowledge_dir": str(self._knowledge_dir),
            "vector_store": vector_stats,
        }


# ── LangChain Tools ──────────────────────────────────────────────────────────

# We need a module-level RAG instance — set by the controller at startup
_rag_instance: Optional[RAGService] = None


def set_rag_instance(rag: RAGService) -> None:
    """Register the RAG service instance for tool access."""
    global _rag_instance
    _rag_instance = rag


@tool
def search_knowledge_base(query: str) -> str:
    """Search the knowledge base for information relevant to a query.

    The knowledge base contains ingested documents (PDFs, text files, source code).

    Args:
        query: The question or search terms to look up.
    """
    if _rag_instance is None:
        return "❌ Knowledge base is not initialised."
    context = _rag_instance.retrieve_context_string(query)
    if not context:
        return f"📚 No relevant documents found for: **{query}**"
    return context


@tool
def ingest_document(path: str) -> str:
    """Add a document or file to the knowledge base for future retrieval.

    Supported formats: PDF, TXT, MD, source code files.

    Args:
        path: Path to the document file to ingest.
    """
    if _rag_instance is None:
        return "❌ Knowledge base is not initialised."
    count = _rag_instance.ingest_file(Path(path))
    if count > 0:
        return f"✅ Ingested `{Path(path).name}` → {count} chunks added to knowledge base."
    return f"❌ Failed to ingest `{path}`. Check if the file exists and is a supported format."


@tool
def index_repository(path: str = ".") -> str:
    """Index an entire repository recursively for semantic search.

    This parses source files, markdown, PDFs, and text documents
    and adds them to the vector store.

    Args:
        path: Path to the repository directory. Defaults to "." (current directory).
    """
    if _rag_instance is None:
        return "❌ Knowledge base is not initialised."
    
    target_path = Path(path)
    results = _rag_instance.ingest_repository(target_path)
    if not results:
        return f"❌ Failed to index repository at `{path}`. Check if the directory exists and contains supported files."
    
    total_chunks = sum(results.values())
    return f"✅ Successfully indexed repository at `{path}`. Ingested {len(results)} files, creating {total_chunks} chunks."


@tool
def knowledge_base_stats() -> str:
    """Get statistics about the knowledge base."""
    if _rag_instance is None:
        return "❌ Knowledge base is not initialised."
    stats = _rag_instance.get_stats()
    v_stats = stats.get("vector_store", {})
    backend_info = "None"
    if v_stats:
        backend_info = f"{v_stats.get('backend', 'unknown')} (status: {v_stats.get('status', 'unknown')})"
        if v_stats.get("embeddings_model"):
            backend_info += f", model: {v_stats.get('embeddings_model')}"

    return (
        f"📚 **Knowledge Base Stats**\n\n"
        f"| Property | Value |\n"
        f"|----------|-------|\n"
        f"| Documents | {stats['total_documents']} |\n"
        f"| Total Chunks | {stats['total_chunks']} |\n"
        f"| Vector Store Backend | {backend_info} |\n"
        f"| Directory | `{stats['knowledge_dir']}` |"
    )


def get_knowledge_tools() -> list:
    """Return all knowledge-base tools for agent registration."""
    return [search_knowledge_base, ingest_document, index_repository, knowledge_base_stats]
