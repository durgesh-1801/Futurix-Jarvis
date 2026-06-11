"""
Futurix Jarvis — Speech-to-Text Service.

Captures audio from the microphone and converts it to text using
Google Speech Recognition.  Designed to run on a ``QThread`` so the
GUI stays responsive during recording.
"""

from __future__ import annotations

import logging
import math
import struct
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

logger = logging.getLogger(__name__)


def _calculate_rms(raw_data: bytes, sample_width: int) -> float:
    """Calculate Root Mean Square (RMS) of audio frame data.

    A future-proof replacement for audioop.rms() (removed in Python 3.13).
    """
    if not raw_data:
        return 0.0
    num_samples = len(raw_data) // sample_width
    if num_samples == 0:
        return 0.0

    if sample_width == 1:
        fmt = f"{num_samples}b"
        samples = struct.unpack(fmt, raw_data)
    elif sample_width == 2:
        fmt = f"<{num_samples}h"
        samples = struct.unpack(fmt, raw_data)
    elif sample_width == 4:
        fmt = f"<{num_samples}i"
        samples = struct.unpack(fmt, raw_data)
    else:
        return 0.0

    sum_squares = sum(s * s for s in samples)
    mean_square = sum_squares / num_samples
    return math.sqrt(mean_square)

# Lazy-imported to avoid startup crashes if PyAudio is missing
_sr = None
_Microphone = None
_Recognizer = None


def _import_speech_recognition():
    """Lazy-import speech_recognition to handle missing PyAudio gracefully."""
    global _sr, _Microphone, _Recognizer
    if _sr is None:
        try:
            import speech_recognition as sr
            _sr = sr
            _Microphone = sr.Microphone
            _Recognizer = sr.Recognizer
        except ImportError:
            logger.warning(
                "speech_recognition or PyAudio not installed — voice input disabled."
            )


class _ListenWorker(QObject):
    """Worker that captures mic audio on a background thread."""

    finished = pyqtSignal(str)      # recognised text (empty on failure)
    error = pyqtSignal(str)         # error message
    listening_started = pyqtSignal()
    listening_stopped = pyqtSignal()

    def __init__(
        self,
        timeout: int = 5,
        phrase_time_limit: int = 15,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.timeout = timeout
        self.phrase_time_limit = phrase_time_limit
        self._cancelled = False

    def cancel(self) -> None:
        """Signal the worker to stop as soon as possible."""
        self._cancelled = True

    def run(self) -> None:
        """Capture audio and recognise speech (runs on QThread)."""
        _import_speech_recognition()
        if _sr is None:
            self.error.emit("Speech recognition is not available (missing PyAudio).")
            self.finished.emit("")
            return

        recognizer = _Recognizer()
        try:
            with _Microphone() as source:
                if self._cancelled:
                    self.finished.emit("")
                    return

                recognizer.adjust_for_ambient_noise(source, duration=0.5)

                if self._cancelled:
                    self.finished.emit("")
                    return

                self.listening_started.emit()
                logger.debug("Listening for speech (interruptible)…")

                sample_rate = source.SAMPLE_RATE
                sample_width = source.SAMPLE_WIDTH
                chunk_size = source.CHUNK

                threshold = recognizer.energy_threshold
                pause_seconds = recognizer.pause_threshold
                non_speaking_chunks = int(pause_seconds * sample_rate / chunk_size)

                max_timeout_chunks = int(self.timeout * sample_rate / chunk_size) if self.timeout else None
                max_phrase_chunks = int(self.phrase_time_limit * sample_rate / chunk_size) if self.phrase_time_limit else None

                frames = []
                speech_started = False
                silent_chunks = 0
                total_chunks = 0

                while not self._cancelled:
                    try:
                        raw_data = source.stream.read(chunk_size)
                    except Exception as e:
                        logger.error("Error reading audio chunk: %s", e)
                        break

                    frames.append(raw_data)
                    total_chunks += 1

                    # Calculate energy of the chunk
                    energy = _calculate_rms(raw_data, sample_width)

                    if not speech_started:
                        if energy > threshold:
                            speech_started = True
                            logger.debug("Speech detected, recording…")
                        elif max_timeout_chunks and total_chunks > max_timeout_chunks:
                            logger.debug("STT Timeout: no speech detected before timeout.")
                            break
                    else:
                        if energy < threshold:
                            silent_chunks += 1
                        else:
                            silent_chunks = 0

                        # If silent for pause_threshold, stop recording
                        if silent_chunks > non_speaking_chunks:
                            logger.debug("Silence detected, stopping recording.")
                            break

                        if max_phrase_chunks and len(frames) > max_phrase_chunks:
                            logger.debug("Phrase time limit reached, stopping recording.")
                            break

                self.listening_stopped.emit()

                if self._cancelled:
                    logger.debug("Speech recognition cancelled.")
                    self.finished.emit("")
                    return

                if not frames or not speech_started:
                    logger.debug("No audio recorded or worker timed out.")
                    self.finished.emit("")
                    return

                audio = _sr.AudioData(b"".join(frames), sample_rate, sample_width)
                text = recognizer.recognize_google(audio)
                logger.info("Recognised: %s", text)
                self.finished.emit(text)

        except _sr.WaitTimeoutError:
            self.listening_stopped.emit()
            logger.debug("Listening timed out — no speech detected.")
            self.finished.emit("")

        except _sr.UnknownValueError:
            self.listening_stopped.emit()
            logger.debug("Could not understand audio.")
            self.error.emit("Sorry, I couldn't understand that. Please try again.")
            self.finished.emit("")

        except _sr.RequestError as exc:
            self.listening_stopped.emit()
            msg = f"Speech recognition service error: {exc}"
            logger.error(msg)
            self.error.emit(msg)
            self.finished.emit("")

        except Exception as exc:
            self.listening_stopped.emit()
            msg = f"Unexpected voice error: {exc}"
            logger.exception(msg)
            self.error.emit(msg)
            self.finished.emit("")


class SpeechToText(QObject):
    """High-level speech-to-text interface for the GUI.

    Signals:
        text_recognised(str): Emitted with the recognised text.
        error_occurred(str): Emitted when recognition fails.
        listening_started(): Microphone is active.
        listening_stopped(): Microphone has stopped.

    Usage::

        stt = SpeechToText()
        stt.text_recognised.connect(on_text)
        stt.start_listening()
    """

    text_recognised = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    listening_started = pyqtSignal()
    listening_stopped = pyqtSignal()

    def __init__(self, wake_word: str = "hey jarvis", parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._wake_word = wake_word.lower().strip()
        self._thread: Optional[QThread] = None
        self._worker: Optional[_ListenWorker] = None
        self._is_listening = False

    @property
    def is_listening(self) -> bool:
        """Whether the microphone is currently active."""
        return self._is_listening

    def start_listening(
        self,
        timeout: int = 8,
        phrase_time_limit: int = 20,
    ) -> None:
        """Begin capturing audio on a background thread.

        Args:
            timeout: Seconds to wait for speech to begin.
            phrase_time_limit: Maximum seconds of speech to capture.
        """
        if self._is_listening:
            logger.warning("Already listening — ignoring duplicate call.")
            return

        self._is_listening = True
        self._thread = QThread()
        self._worker = _ListenWorker(timeout, phrase_time_limit)
        self._worker.moveToThread(self._thread)

        # Wire signals
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self.error_occurred.emit)
        self._worker.listening_started.connect(self._on_listening_started)
        self._worker.listening_stopped.connect(self._on_listening_stopped)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup)

        self._thread.start()

    def stop_listening(self) -> None:
        """Cancel the current recording."""
        if self._worker is not None:
            self._worker.cancel()

    def shutdown(self) -> None:
        """Ensure the listening thread is stopped and cleaned up."""
        logger.info("Shutting down SpeechToText...")
        self.stop_listening()
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            if not self._thread.wait(2000):
                logger.warning("SpeechToText thread did not stop gracefully. Terminating...")
                self._thread.terminate()
                self._thread.wait(1000)

    def detect_wake_word(self, text: str) -> bool:
        """Check if the text starts with the configured wake word.

        Args:
            text: The recognised speech text.

        Returns:
            ``True`` if the wake word was detected.
        """
        return text.lower().strip().startswith(self._wake_word)

    def strip_wake_word(self, text: str) -> str:
        """Remove the wake word prefix from the text.

        Args:
            text: Speech text potentially starting with the wake word.

        Returns:
            Text with the wake word removed.
        """
        lower = text.lower().strip()
        if lower.startswith(self._wake_word):
            return text[len(self._wake_word):].strip(" ,.")
        return text

    # ── Private slots ────────────────────────────────────────────────────

    def _on_finished(self, text: str) -> None:
        self._is_listening = False
        if text:
            self.text_recognised.emit(text)

    def _on_listening_started(self) -> None:
        self.listening_started.emit()

    def _on_listening_stopped(self) -> None:
        self.listening_stopped.emit()

    def _cleanup(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None
