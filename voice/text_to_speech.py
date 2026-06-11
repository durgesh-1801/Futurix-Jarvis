"""
Futurix Jarvis — Text-to-Speech Service.

Uses ``pyttsx3`` for offline, cross-platform speech synthesis.
Speech is dispatched to a background thread so the GUI remains responsive.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Optional

logger = logging.getLogger(__name__)


class TextToSpeech:
    """Offline text-to-speech engine using pyttsx3.

    Speech requests are queued and processed sequentially on a dedicated
    daemon thread.  This avoids blocking the main/GUI thread and prevents
    ``pyttsx3`` re-entrancy issues.

    Usage::

        tts = TextToSpeech(rate=175, volume=0.9)
        tts.speak("Hello, I am Jarvis.")
        tts.stop()          # interrupt current speech
        tts.shutdown()      # clean up
    """

    def __init__(
        self,
        rate: int = 175,
        volume: float = 0.9,
        voice_id: Optional[str] = None,
    ) -> None:
        self._rate = rate
        self._volume = volume
        self._voice_id = voice_id
        self._queue: queue.Queue[Optional[str]] = queue.Queue()
        self._stop_event = threading.Event()
        self._engine_ready = threading.Event()
        self._available = False

        # Start the speech worker thread
        self._thread = threading.Thread(target=self._worker, daemon=True, name="TTS-Worker")
        self._thread.start()
        # Wait briefly for engine init
        self._engine_ready.wait(timeout=5)

    # ── Public API ───────────────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        """Whether the TTS engine initialised successfully."""
        return self._available

    def speak(self, text: str) -> None:
        """Queue a text string for speech synthesis.

        Args:
            text: The text to speak.  Empty strings are silently ignored.
        """
        if not self._available:
            logger.warning("TTS unavailable — skipping speech.")
            return
        text = text.strip()
        if text:
            self._queue.put(text)

    def stop(self) -> None:
        """Stop any currently playing speech and clear the queue."""
        self._stop_event.set()
        # Clear the queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def shutdown(self) -> None:
        """Signal the worker thread to exit and wait for it."""
        self._queue.put(None)  # sentinel
        self._thread.join(timeout=5)

    def get_available_voices(self) -> list[dict[str, str]]:
        """Return a list of available voice descriptors.

        Returns:
            List of dicts with ``id``, ``name``, ``languages``.
        """
        if not self._available:
            return []
        # We can't access the engine from this thread, so we cached
        # voices during init.
        return self._voices_cache

    # ── Worker thread ────────────────────────────────────────────────────

    def _worker(self) -> None:
        """Background thread: initialise pyttsx3 and process the speech queue."""
        try:
            import pyttsx3
            engine = pyttsx3.init()
        except Exception as exc:
            logger.warning("Failed to initialise pyttsx3: %s", exc)
            self._available = False
            self._engine_ready.set()
            return

        # Configure engine
        engine.setProperty("rate", self._rate)
        engine.setProperty("volume", self._volume)

        # Cache voices
        voices = engine.getProperty("voices")
        self._voices_cache = [
            {
                "id": v.id,
                "name": v.name,
                "languages": str(getattr(v, "languages", [])),
            }
            for v in voices
        ]

        # Set specific voice if requested
        if self._voice_id:
            engine.setProperty("voice", self._voice_id)
        elif voices:
            # Default to first English voice if available
            for v in voices:
                if "english" in v.name.lower():
                    engine.setProperty("voice", v.id)
                    break

        self._available = True
        self._engine_ready.set()
        logger.info("TTS engine ready — rate=%d, volume=%.1f", self._rate, self._volume)

        def on_word(name, location, length):
            if self._stop_event.is_set():
                try:
                    engine.stop()
                    logger.debug("TTS interrupted via engine.stop() in word callback.")
                except Exception as exc:
                    logger.error("Error interrupting TTS engine: %s", exc)

        try:
            engine.connect("started-word", on_word)
        except Exception as exc:
            logger.warning("Failed to connect started-word callback: %s", exc)

        while True:
            text = self._queue.get()
            if text is None:
                # Shutdown sentinel
                break
            self._stop_event.clear()
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception as exc:
                logger.error("TTS error: %s", exc)
            finally:
                self._stop_event.clear()

        try:
            engine.stop()
        except Exception:
            pass
        logger.info("TTS worker shut down.")
