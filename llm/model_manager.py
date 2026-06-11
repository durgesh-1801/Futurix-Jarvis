"""
Futurix Jarvis — Model Manager.

Manages multiple Ollama models — listing available models, checking server
health, pulling new models, and switching the active model at runtime.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Metadata for an Ollama model."""
    name: str
    size: str = ""
    parameter_size: str = ""
    quantization: str = ""
    modified_at: str = ""
    digest: str = ""
    is_available: bool = False


class ModelManager:
    """Manage Ollama models — health checks, listing, and switching.

    Usage::

        mgr = ModelManager("http://localhost:11434")
        if mgr.check_health():
            models = mgr.list_models()
            mgr.set_active_model("llama3")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3",
        configured_models: Optional[list[str]] = None,
        timeout: int = 10,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._active_model = default_model
        self._configured_models = configured_models or ["llama3", "qwen2", "deepseek-coder-v2"]
        self._timeout = timeout
        self._available_models: list[ModelInfo] = []
        self._is_online = False

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def active_model(self) -> str:
        """The name of the currently selected model."""
        return self._active_model

    @property
    def is_online(self) -> bool:
        """Whether the Ollama server was reachable at last check."""
        return self._is_online

    @property
    def available_models(self) -> list[ModelInfo]:
        """Models that are actually downloaded and available locally."""
        return self._available_models

    @property
    def configured_models(self) -> list[str]:
        """Model names from the user configuration."""
        return list(self._configured_models)

    # ── Server health ────────────────────────────────────────────────────

    def check_health(self) -> bool:
        """Ping the Ollama server to check if it's running.

        Returns:
            ``True`` if the server responds successfully.
        """
        try:
            resp = httpx.get(f"{self._base_url}/", timeout=self._timeout)
            self._is_online = resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, Exception) as exc:
            logger.warning("Ollama server unreachable: %s", exc)
            self._is_online = False
        return self._is_online

    # ── Model listing ────────────────────────────────────────────────────

    def list_models(self) -> list[ModelInfo]:
        """Fetch the list of locally available models from Ollama.

        Returns:
            List of ``ModelInfo`` objects.  Empty if the server is unreachable.
        """
        if not self.check_health():
            return []

        try:
            resp = httpx.get(
                f"{self._base_url}/api/tags",
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            models = []
            for m in data.get("models", []):
                details = m.get("details", {})
                info = ModelInfo(
                    name=m.get("name", "unknown"),
                    size=self._format_size(m.get("size", 0)),
                    parameter_size=details.get("parameter_size", ""),
                    quantization=details.get("quantization_level", ""),
                    modified_at=m.get("modified_at", ""),
                    digest=m.get("digest", "")[:12],
                    is_available=True,
                )
                models.append(info)

            self._available_models = models
            logger.info("Found %d local models", len(models))
            return models

        except Exception as exc:
            logger.error("Failed to list models: %s", exc)
            return []

    def get_model_status(self) -> list[dict]:
        """Return status for each configured model (available or not).

        Returns:
            List of dicts with ``name``, ``is_available``, ``size``.
        """
        available_names = {m.name.split(":")[0] for m in self._available_models}
        result = []
        for name in self._configured_models:
            is_avail = name in available_names or any(
                m.name.startswith(name) for m in self._available_models
            )
            size = ""
            for m in self._available_models:
                if m.name.startswith(name):
                    size = m.size
                    break
            result.append({
                "name": name,
                "is_available": is_avail,
                "size": size,
            })
        return result

    # ── Model switching ──────────────────────────────────────────────────

    def set_active_model(self, model_name: str) -> bool:
        """Switch the active model.

        Args:
            model_name: The model to activate.

        Returns:
            ``True`` if the model is available and was activated.
        """
        # Check if the model exists locally
        available_names = {m.name for m in self._available_models}
        full_match = model_name in available_names
        prefix_match = any(m.name.startswith(model_name) for m in self._available_models)

        if full_match or prefix_match:
            self._active_model = model_name
            logger.info("Active model changed to: %s", model_name)
            return True
        else:
            logger.warning("Model '%s' not available locally.", model_name)
            # Set anyway — user may pull it later
            self._active_model = model_name
            return False

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format byte count to human-readable string."""
        for unit in ("B", "KB", "MB", "GB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
