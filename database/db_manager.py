"""
Futurix Jarvis — SQLite Database Manager.

Thread-safe wrapper around ``sqlite3`` that manages conversation, message,
task memory, code symbol, and repository summary persistence.
All write operations are serialised through a single connection with WAL mode
for safe concurrent reads.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ── Data Transfer Objects ────────────────────────────────────────────────────

@dataclass
class ConversationRecord:
    """Represents a stored conversation."""
    id: int
    title: str
    created_at: str
    updated_at: str


@dataclass
class MessageRecord:
    """Represents a stored message within a conversation."""
    id: int
    conversation_id: int
    role: str           # "user", "assistant", or "system"
    content: str
    timestamp: str
    metadata: Optional[str] = None


@dataclass
class TaskRecord:
    """Represents a stored task."""
    id: int
    title: str
    description: Optional[str]
    status: str         # "pending", "in_progress", "completed"
    priority: str       # "low", "medium", "high"
    created_at: str
    updated_at: str
    due_date: Optional[str] = None


@dataclass
class TaskNoteRecord:
    """Represents a log note for a task."""
    id: int
    task_id: int
    note: str
    created_at: str


@dataclass
class CodeSymbolRecord:
    """Represents an AST-extracted code symbol."""
    id: int
    file_path: str
    symbol_name: str
    symbol_type: str    # "class", "function", "import"
    line_number: int
    end_line_number: Optional[int]
    parent_name: Optional[str]
    details: Optional[str]


@dataclass
class RepositorySummaryRecord:
    """Represents repository statistics and architectural summaries."""
    repo_path: str
    project_name: str
    languages_detected: str     # comma-separated list
    frameworks_detected: str    # comma-separated list
    dependency_files: str       # comma-separated list
    total_files: int
    total_lines: int
    summary: str
    updated_at: str


# ── Schema ───────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL DEFAULT 'New Conversation',
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id  INTEGER NOT NULL,
    role             TEXT    NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content          TEXT    NOT NULL,
    timestamp        TEXT    NOT NULL,
    metadata         TEXT,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conv
    ON messages(conversation_id, timestamp);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT    NOT NULL,
    chunk_index INTEGER NOT NULL,
    content     TEXT    NOT NULL,
    embedding   BLOB,
    created_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_knowledge_source
    ON knowledge_chunks(source_file);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    description TEXT,
    status      TEXT    NOT NULL CHECK (status IN ('pending', 'in_progress', 'completed')) DEFAULT 'pending',
    priority    TEXT    NOT NULL CHECK (priority IN ('low', 'medium', 'high')) DEFAULT 'medium',
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    due_date    TEXT
);

CREATE TABLE IF NOT EXISTS task_notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL,
    note        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS task_files (
    task_id     INTEGER NOT NULL,
    file_path   TEXT    NOT NULL,
    PRIMARY KEY (task_id, file_path),
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS code_symbols (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path       TEXT    NOT NULL,
    symbol_name     TEXT    NOT NULL,
    symbol_type     TEXT    NOT NULL CHECK (symbol_type IN ('class', 'function', 'import')),
    line_number     INTEGER NOT NULL,
    end_line_number INTEGER,
    parent_name     TEXT,
    details         TEXT
);

CREATE INDEX IF NOT EXISTS idx_code_symbols_name
    ON code_symbols(symbol_name);

CREATE TABLE IF NOT EXISTS repository_summaries (
    repo_path           TEXT    PRIMARY KEY,
    project_name        TEXT    NOT NULL,
    languages_detected  TEXT    NOT NULL,
    frameworks_detected TEXT    NOT NULL,
    dependency_files    TEXT    NOT NULL,
    total_files         INTEGER NOT NULL,
    total_lines         INTEGER NOT NULL,
    summary             TEXT    NOT NULL,
    updated_at          TEXT    NOT NULL
);
"""


class DatabaseManager:
    """Thread-safe SQLite database manager.

    Manages conversation memory, RAG chunks, AST symbols, and Task lists.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_database()
        logger.info("Database initialised at %s", self._db_path)

    # ── Connection management ────────────────────────────────────────────

    def _ensure_database(self) -> None:
        """Create the database file and schema if they don't exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_connection()
        conn.executescript(_SCHEMA_SQL)
        conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """Return the singleton connection, creating it on first call."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
                timeout=10,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    @contextmanager
    def _cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Yield a cursor inside the thread lock and auto-commit."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                yield cursor
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            logger.info("Database connection closed.")

    # ── Conversation CRUD ────────────────────────────────────────────────

    def create_conversation(self, title: str = "New Conversation") -> int:
        """Create a new conversation and return its ID."""
        now = datetime.now(timezone.utc).isoformat()
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (title, created_at, updated_at) VALUES (?, ?, ?)",
                (title, now, now),
            )
            conv_id = cur.lastrowid
        logger.debug("Created conversation %d: %s", conv_id, title)
        return conv_id  # type: ignore[return-value]

    def get_conversations(self, limit: int = 50) -> list[ConversationRecord]:
        """Return the most recent conversations, newest first."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT id, title, created_at, updated_at "
                "FROM conversations ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        return [ConversationRecord(**dict(r)) for r in rows]

    def update_conversation_title(self, conv_id: int, title: str) -> None:
        """Update the title of an existing conversation."""
        now = datetime.now(timezone.utc).isoformat()
        with self._cursor() as cur:
            cur.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, now, conv_id),
            )

    def delete_conversation(self, conv_id: int) -> None:
        """Delete a conversation and all its messages (cascade)."""
        with self._cursor() as cur:
            cur.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        logger.info("Deleted conversation %d", conv_id)

    # ── Message CRUD ─────────────────────────────────────────────────────

    def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        metadata: Optional[str] = None,
    ) -> int:
        """Append a message to a conversation."""
        now = datetime.now(timezone.utc).isoformat()
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO messages (conversation_id, role, content, timestamp, metadata) "
                "VALUES (?, ?, ?, ?, ?)",
                (conversation_id, role, content, now, metadata),
            )
            msg_id = cur.lastrowid
            # Touch the parent conversation's updated_at
            cur.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
        return msg_id  # type: ignore[return-value]

    def get_messages(
        self,
        conversation_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MessageRecord]:
        """Retrieve messages for a conversation in chronological order."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT id, conversation_id, role, content, timestamp, metadata "
                "FROM messages WHERE conversation_id = ? "
                "ORDER BY timestamp ASC LIMIT ? OFFSET ?",
                (conversation_id, limit, offset),
            )
            rows = cur.fetchall()
        return [MessageRecord(**dict(r)) for r in rows]

    def get_message_count(self, conversation_id: int) -> int:
        """Return the number of messages in a conversation."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
                (conversation_id,),
            )
            return cur.fetchone()[0]

    # ── Knowledge chunks (RAG) ───────────────────────────────────────────

    def store_knowledge_chunk(
        self,
        source_file: str,
        chunk_index: int,
        content: str,
        embedding: Optional[bytes] = None,
    ) -> int:
        """Store a document chunk for RAG retrieval."""
        now = datetime.now(timezone.utc).isoformat()
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO knowledge_chunks (source_file, chunk_index, content, embedding, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (source_file, chunk_index, content, embedding, now),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def search_knowledge(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Simple keyword search over knowledge chunks."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT id, source_file, chunk_index, content FROM knowledge_chunks "
                "WHERE content LIKE ? LIMIT ?",
                (f"%{query}%", limit),
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def clear_knowledge(self, source_file: Optional[str] = None) -> None:
        """Remove knowledge chunks — optionally filtered by source file."""
        with self._cursor() as cur:
            if source_file:
                cur.execute(
                    "DELETE FROM knowledge_chunks WHERE source_file = ?",
                    (source_file,),
                )
            else:
                cur.execute("DELETE FROM knowledge_chunks")

    # ── Tasks CRUD (Phase 3) ──────────────────────────────────────────────

    def create_task(
        self,
        title: str,
        description: Optional[str] = None,
        priority: str = "medium",
        due_date: Optional[str] = None,
    ) -> int:
        """Create a new task in memory."""
        now = datetime.now(timezone.utc).isoformat()
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO tasks (title, description, status, priority, created_at, updated_at, due_date) "
                "VALUES (?, ?, 'pending', ?, ?, ?, ?)",
                (title, description, priority, now, now, due_date),
            )
            task_id = cur.lastrowid
        logger.info("Created task %d: %s (%s, due: %s)", task_id, title, priority, due_date)
        return task_id  # type: ignore[return-value]

    def update_task_status(self, task_id: int, status: str) -> None:
        """Update task completion status."""
        now = datetime.now(timezone.utc).isoformat()
        with self._cursor() as cur:
            cur.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, task_id),
            )

    def add_task_note(self, task_id: int, note: str) -> int:
        """Add a progress note to a task."""
        now = datetime.now(timezone.utc).isoformat()
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO task_notes (task_id, note, created_at) VALUES (?, ?, ?)",
                (task_id, note, now),
            )
            note_id = cur.lastrowid
        return note_id  # type: ignore[return-value]

    def add_task_file(self, task_id: int, file_path: str) -> None:
        """Link a file path to a task."""
        file_path_str = str(Path(file_path).resolve())
        with self._cursor() as cur:
            cur.execute(
                "INSERT OR IGNORE INTO task_files (task_id, file_path) VALUES (?, ?)",
                (task_id, file_path_str),
            )

    def get_tasks(
        self,
        status: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> list[TaskRecord]:
        """Fetch tasks, optionally filtered by status or search terms."""
        query = "SELECT id, title, description, status, priority, created_at, updated_at, due_date FROM tasks"
        params: list[Any] = []
        conditions = []

        if status:
            conditions.append("status = ?")
            params.append(status)

        if search_query:
            conditions.append("(title LIKE ? OR description LIKE ?)")
            term = f"%{search_query}%"
            params.extend([term, term])

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY updated_at DESC"

        with self._cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
        return [TaskRecord(**dict(r)) for r in rows]

    def get_task(self, task_id: int) -> Optional[TaskRecord]:
        """Fetch details of a single task."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT id, title, description, status, priority, created_at, updated_at, due_date "
                "FROM tasks WHERE id = ?",
                (task_id,),
            )
            row = cur.fetchone()
        return TaskRecord(**dict(row)) if row else None

    def get_task_notes(self, task_id: int) -> list[TaskNoteRecord]:
        """Fetch notes associated with a task, newest first."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT id, task_id, note, created_at FROM task_notes WHERE task_id = ? ORDER BY created_at DESC",
                (task_id,),
            )
            rows = cur.fetchall()
        return [TaskNoteRecord(**dict(r)) for r in rows]

    def get_task_files(self, task_id: int) -> list[str]:
        """Fetch files associated with a task."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT file_path FROM task_files WHERE task_id = ?",
                (task_id,),
            )
            rows = cur.fetchall()
        return [r["file_path"] for r in rows]

    def delete_task(self, task_id: int) -> None:
        """Remove a task and its relations (cascades notes and files)."""
        with self._cursor() as cur:
            cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    # ── Code symbols & Repository summaries (Phase 3) ──────────────────────

    def store_code_symbol(
        self,
        file_path: str,
        symbol_name: str,
        symbol_type: str,
        line_number: int,
        end_line_number: Optional[int],
        parent_name: Optional[str],
        details: Optional[str],
    ) -> int:
        """Store an AST-extracted code symbol."""
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO code_symbols (file_path, symbol_name, symbol_type, line_number, end_line_number, parent_name, details) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (file_path, symbol_name, symbol_type, line_number, end_line_number, parent_name, details),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def clear_code_symbols(self, file_path: Optional[str] = None) -> None:
        """Delete code symbols cache, optionally filtered by file."""
        with self._cursor() as cur:
            if file_path:
                cur.execute("DELETE FROM code_symbols WHERE file_path = ?", (file_path,))
            else:
                cur.execute("DELETE FROM code_symbols")

    def search_code_symbols(
        self,
        query: str,
        symbol_type: Optional[str] = None,
    ) -> list[CodeSymbolRecord]:
        """Search code symbols table."""
        sql = "SELECT id, file_path, symbol_name, symbol_type, line_number, end_line_number, parent_name, details FROM code_symbols WHERE symbol_name LIKE ?"
        params: list[Any] = [f"%{query}%"]

        if symbol_type:
            sql += " AND symbol_type = ?"
            params.append(symbol_type)

        with self._cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        return [CodeSymbolRecord(**dict(r)) for r in rows]

    def store_repository_summary(
        self,
        repo_path: str,
        project_name: str,
        languages: list[str],
        frameworks: list[str],
        dependencies: list[str],
        total_files: int,
        total_lines: int,
        summary: str,
    ) -> None:
        """Store/cache overall repository metadata and summary."""
        now = datetime.now(timezone.utc).isoformat()
        langs_str = ",".join(languages)
        frams_str = ",".join(frameworks)
        deps_str = ",".join(dependencies)
        
        with self._cursor() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO repository_summaries (repo_path, project_name, languages_detected, frameworks_detected, dependency_files, total_files, total_lines, summary, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (repo_path, project_name, langs_str, frams_str, deps_str, total_files, total_lines, summary, now),
            )

    def get_repository_summary(self, repo_path: str) -> Optional[RepositorySummaryRecord]:
        """Fetch the cached repository summary."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT repo_path, project_name, languages_detected, frameworks_detected, dependency_files, total_files, total_lines, summary, updated_at "
                "FROM repository_summaries WHERE repo_path = ?",
                (repo_path,),
            )
            row = cur.fetchone()
        return RepositorySummaryRecord(**dict(row)) if row else None
