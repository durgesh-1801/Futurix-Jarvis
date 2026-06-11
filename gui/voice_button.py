"""
Futurix Jarvis — Animated Voice Button.

A circular push-to-talk button with pulsing glow animation that changes
colour based on state: idle (dim cyan), listening (pulsing red), and
processing (amber).
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSize,
    Qt,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QRadialGradient
from PyQt6.QtWidgets import QPushButton, QWidget

from gui.styles import VOICE_BUTTON_STYLESHEET


class VoiceButton(QPushButton):
    """Circular microphone button with animated glow.

    States:
    - **idle**: Dim cyan glow, mic icon.
    - **listening**: Pulsing red glow, recording indicator.
    - **processing**: Amber glow, spinner.

    Signals:
        clicked(): Inherited from QPushButton.

    Usage::

        btn = VoiceButton()
        btn.set_listening(True)
        btn.set_processing(True)
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("🎤", parent)
        self.setObjectName("voice_btn")
        self.setStyleSheet(VOICE_BUTTON_STYLESHEET)
        self.setFixedSize(48, 48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Push to talk (or press Ctrl+Space)")

        self._glow_intensity = 0.0
        self._is_listening = False
        self._is_processing = False

        # Pulse animation
        self._pulse_anim = QPropertyAnimation(self, b"glowIntensity")
        self._pulse_anim.setDuration(800)
        self._pulse_anim.setStartValue(0.3)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse_anim.setLoopCount(-1)  # Infinite loop

    # ── Custom property for animation ────────────────────────────────────

    @pyqtProperty(float)
    def glowIntensity(self) -> float:
        return self._glow_intensity

    @glowIntensity.setter
    def glowIntensity(self, value: float) -> None:
        self._glow_intensity = value
        self.update()  # Trigger repaint

    # ── State management ─────────────────────────────────────────────────

    def set_listening(self, listening: bool) -> None:
        """Switch to listening (recording) state.

        Args:
            listening: Whether the mic is actively recording.
        """
        self._is_listening = listening
        self._is_processing = False
        self.setProperty("listening", listening)
        self.style().unpolish(self)
        self.style().polish(self)

        if listening:
            self.setText("⏹")
            self.setToolTip("Click to stop recording")
            self._pulse_anim.start()
        else:
            self.setText("🎤")
            self.setToolTip("Push to talk (or press Ctrl+Space)")
            self._pulse_anim.stop()
            self._glow_intensity = 0.0

        self.update()

    def set_processing(self, processing: bool) -> None:
        """Switch to processing state.

        Args:
            processing: Whether the assistant is thinking.
        """
        self._is_processing = processing
        self._is_listening = False
        self._pulse_anim.stop()

        if processing:
            self.setText("⏳")
            self.setToolTip("Processing…")
            self.setEnabled(False)
        else:
            self.setText("🎤")
            self.setToolTip("Push to talk (or press Ctrl+Space)")
            self.setEnabled(True)

        self.update()

    # ── Custom painting (glow effect) ────────────────────────────────────

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the button with an animated glow effect."""
        super().paintEvent(event)

        if self._is_listening and self._glow_intensity > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            center = self.rect().center()
            radius = self.width() / 2

            # Radial glow
            gradient = QRadialGradient(center.x(), center.y(), radius)
            alpha = int(80 * self._glow_intensity)
            gradient.setColorAt(0.0, QColor(239, 68, 68, alpha))
            gradient.setColorAt(0.5, QColor(239, 68, 68, alpha // 2))
            gradient.setColorAt(1.0, QColor(239, 68, 68, 0))

            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(self.rect())
            painter.end()
