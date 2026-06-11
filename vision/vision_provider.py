"""
Futurix Jarvis — Vision Provider Subsystem.

Defines the abstract interface for visual analysis and the concrete Ollama
multimodal (LLaVA/BakLLaVA) implementation.
"""

from __future__ import annotations

import base64
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class VisionProviderInterface(ABC):
    """Abstract interface for image/screenshot visual analysis.

    Enables swapping visual models (Ollama, Claude, OpenAI, etc.) in the future
    without altering screen analysis tools.
    """

    @abstractmethod
    def analyse_image(self, image_path: Path, prompt: str) -> str:
        """Analyze an image or screenshot with a text prompt.

        Args:
            image_path: Absolute or relative path to the image file.
            prompt: Question or instruction for the vision model.

        Returns:
            Description or answer text from the model.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether the vision provider model/service is online.

        Returns:
            True if operational, False otherwise.
        """

    @abstractmethod
    def model_name(self) -> str:
        """Return the name of the active vision model.

        Returns:
            Model name string.
        """


class OllamaVisionProvider(VisionProviderInterface):
    """Concrete implementation of VisionProviderInterface using local Ollama.

    Requires a multimodal model such as 'llava' or 'bakllava' to be downloaded.
    """

    def __init__(
        self,
        model_name: str = "llava",
        base_url: str = "http://localhost:11434",
    ) -> None:
        self._model_name = model_name
        self.base_url = base_url.rstrip("/")
        self._available: Optional[bool] = None  # Lazy cached probe

    def model_name(self) -> str:
        return self._model_name

    def is_available(self) -> bool:
        """Probe the local Ollama tags endpoint to check if model is downloaded."""
        if self._available is None:
            self._available = self._probe_ollama()
        return self._available

    def reset_availability(self) -> None:
        """Force a re-probe on next invocation."""
        self._available = None

    def analyse_image(self, image_path: Path, prompt: str) -> str:
        """Load image file, convert to base64, and POST to Ollama /api/generate."""
        path = Path(image_path)
        if not path.exists():
            logger.error("Vision image path not found: %s", path)
            return f"❌ Vision error: Image path not found: `{path}`"

        if not self.is_available():
            logger.warning("Vision analysis requested but model '%s' is offline. Falling back.", self._model_name)
            return (
                f"⚠️ Visual analysis is currently unavailable (model '{self._model_name}' offline).\n"
                f"**Request details:** {prompt}"
            )

        try:
            # Read image and convert to base64
            img_bytes = path.read_bytes()
            b64_img = base64.b64encode(img_bytes).decode("utf-8")

            import httpx
            
            logger.info("Sending screenshot analysis request to local Ollama (%s)", self._model_name)
            response = httpx.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self._model_name,
                    "prompt": prompt,
                    "images": [b64_img],
                    "stream": False,
                },
                timeout=45.0,  # Vision models can take longer to compute
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("response", "").strip()
            else:
                logger.error("Ollama vision API error (HTTP %d): %s", response.status_code, response.text)
                return f"❌ Vision API Error (HTTP {response.status_code}): {response.text}"
        except Exception as exc:
            logger.exception("Error executing vision analysis via Ollama")
            # Mark as unavailable temporarily
            self._available = False
            return f"❌ Vision analysis failed: {exc}"

    def _probe_ollama(self) -> bool:
        """Check if Ollama is running and has the configured model available."""
        try:
            import httpx
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            if resp.status_code != 200:
                return False
            
            models = resp.json().get("models", [])
            # Check if any model tag matches or contains our model_name
            for m in models:
                name = m.get("name", "")
                if self._model_name in name or name.startswith(self._model_name):
                    return True
            logger.warning("Ollama vision model '%s' not found locally.", self._model_name)
            return False
        except Exception:
            logger.warning("Failed to connect to Ollama at %s for vision probe.", self.base_url)
            return False
