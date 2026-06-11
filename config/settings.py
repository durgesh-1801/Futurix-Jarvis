"""
Futurix Jarvis — Application Settings.

Centralized configuration loaded from environment variables and .env file.
Uses a singleton pattern to ensure consistent settings across the application.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# ── Load .env from project root ──────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _bool_env(key: str, default: bool = False) -> bool:
    """Parse a boolean environment variable."""
    val = os.getenv(key, str(default)).strip().lower()
    return val in ("true", "1", "yes", "on")


@dataclass(frozen=True)
class Settings:
    """Immutable application-wide settings.

    All values are sourced from environment variables with sensible defaults.
    The ``frozen=True`` flag prevents accidental mutation after initialisation.
    """

    # ── Project paths ────────────────────────────────────────────────────────
    project_root: Path = field(default_factory=lambda: _PROJECT_ROOT)

    # ── Ollama / LLM ────────────────────────────────────────────────────────
    ollama_base_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    ollama_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3")
    )
    ollama_timeout: int = field(
        default_factory=lambda: int(os.getenv("OLLAMA_TIMEOUT", "120"))
    )
    ollama_available_models: list[str] = field(
        default_factory=lambda: [
            m.strip()
            for m in os.getenv(
                "OLLAMA_AVAILABLE_MODELS", "llama3,qwen2,deepseek-coder-v2"
            ).split(",")
        ]
    )
    tool_execution_mode: str = field(
        default_factory=lambda: os.getenv("TOOL_EXECUTION_MODE", "AUTO").strip().upper()
    )

    # ── Voice ────────────────────────────────────────────────────────────────
    wake_word: str = field(
        default_factory=lambda: os.getenv("WAKE_WORD", "hey jarvis")
    )
    voice_rate: int = field(
        default_factory=lambda: int(os.getenv("VOICE_RATE", "175"))
    )
    voice_volume: float = field(
        default_factory=lambda: float(os.getenv("VOICE_VOLUME", "0.9"))
    )
    voice_id: Optional[str] = field(
        default_factory=lambda: os.getenv("VOICE_ID") or None
    )

    # ── Database ─────────────────────────────────────────────────────────────
    db_path: Path = field(
        default_factory=lambda: _PROJECT_ROOT / os.getenv("DB_PATH", "data/jarvis.db")
    )

    # ── RAG / Knowledge ──────────────────────────────────────────────────────
    knowledge_dir: Path = field(
        default_factory=lambda: _PROJECT_ROOT
        / os.getenv("KNOWLEDGE_DIR", "knowledge_base")
    )
    chunk_size: int = field(
        default_factory=lambda: int(os.getenv("CHUNK_SIZE", "1000"))
    )
    chunk_overlap: int = field(
        default_factory=lambda: int(os.getenv("CHUNK_OVERLAP", "200"))
    )
    vector_db_path: Path = field(
        default_factory=lambda: _PROJECT_ROOT / os.getenv("VECTOR_DB_PATH", "data/chroma_db")
    )
    embeddings_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDINGS_MODEL", "nomic-embed-text")
    )

    # ── Logging ──────────────────────────────────────────────────────────────
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper()
    )
    log_dir: Path = field(
        default_factory=lambda: _PROJECT_ROOT / os.getenv("LOG_DIR", "logs")
    )

    # ── MCP ──────────────────────────────────────────────────────────────────
    mcp_enabled: bool = field(
        default_factory=lambda: _bool_env("MCP_ENABLED", False)
    )
    mcp_servers_config: Path = field(
        default_factory=lambda: _PROJECT_ROOT
        / os.getenv("MCP_SERVERS_CONFIG", "config/mcp_servers.json")
    )

    # ── Safety ───────────────────────────────────────────────────────────────
    confirm_delete: bool = field(
        default_factory=lambda: _bool_env("REQUIRE_CONFIRMATION_FOR_DELETE", True)
    )
    confirm_shutdown: bool = field(
        default_factory=lambda: _bool_env("REQUIRE_CONFIRMATION_FOR_SHUTDOWN", True)
    )
    confirm_commands: bool = field(
        default_factory=lambda: _bool_env("REQUIRE_CONFIRMATION_FOR_COMMANDS", True)
    )


# ── Singleton accessor ───────────────────────────────────────────────────────
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Return the global ``Settings`` singleton, creating it on first call."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


def reset_settings() -> None:
    """Reset the singleton (useful for testing)."""
    global _settings_instance
    _settings_instance = None
