"""
Futurix Jarvis — Main Window.

The primary application window combining the sidebar, chat area, input
bar, voice button, model selector, and status indicators into a cohesive
dark futuristic interface.
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import QSize, Qt, pyqtSlot
from PyQt6.QtGui import QAction, QFont, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from assistant.controller import AssistantController
from config.settings import Settings
from gui.chat_widget import ChatWidget
from gui.history_panel import HistoryPanel
from gui.styles import (
    CHAT_STYLESHEET,
    MAIN_STYLESHEET,
    MODEL_SELECTOR_STYLESHEET,
    STATUS_STYLES,
)
from gui.voice_button import VoiceButton

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """The primary Futurix Jarvis desktop window.

    Layout::

        ┌─────────────┬──────────────────────────────────────┐
        │             │                                      │
        │  History    │         Chat Display Area             │
        │  Panel      │                                      │
        │  (sidebar)  │                                      │
        │             ├──────────────────────────────────────┤
        │             │ [🎤] [  Chat input...  ] [  Send  ]  │
        │             │ [Model ▼]          [Status: Online]  │
        └─────────────┴──────────────────────────────────────┘
    """

    def __init__(self, settings: Settings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._settings = settings

        # Initialise the controller (connects all services)
        self._controller = AssistantController(settings)

        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        self._refresh_conversations()

        logger.info("Main window initialised.")

    # ── Window setup ─────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        """Configure the main window properties."""
        self.setWindowTitle("⚡ Futurix Jarvis — AI Assistant")
        self.setMinimumSize(1000, 700)
        self.resize(1280, 800)
        self.setStyleSheet(MAIN_STYLESHEET)

        # Center on screen
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2
            y = (geo.height() - self.height()) // 2
            self.move(x, y)

    # ── UI construction ──────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        """Build the complete UI layout."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────────
        self._history_panel = HistoryPanel()
        self._history_panel.set_model_info(self._controller.active_model)
        self._history_panel.set_status(
            "online" if self._controller.is_llm_online else "offline"
        )
        main_layout.addWidget(self._history_panel)

        # ── Chat area ────────────────────────────────────────────────────
        chat_container = QWidget()
        chat_layout = QVBoxLayout(chat_container)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        # Header bar
        header = self._build_header()
        chat_layout.addWidget(header)

        # Chat display
        self._chat_widget = ChatWidget()
        chat_layout.addWidget(self._chat_widget, 1)

        # Input bar
        input_bar = self._build_input_bar()
        chat_layout.addWidget(input_bar)

        main_layout.addWidget(chat_container, 1)

        # ── Status bar ───────────────────────────────────────────────────
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self._status_bar.addWidget(self._status_label)

        # ── Keyboard shortcuts ───────────────────────────────────────────
        shortcut_voice = QShortcut(QKeySequence("Ctrl+Space"), self)
        shortcut_voice.activated.connect(self._on_voice_clicked)

        shortcut_send = QShortcut(QKeySequence("Return"), self._input)
        shortcut_send.activated.connect(self._on_send_clicked)

    def _build_header(self) -> QWidget:
        """Build the header bar with model selector and reconnect button."""
        header = QWidget()
        header.setStyleSheet(
            "background: #111827; border-bottom: 1px solid #334155; padding: 4px;"
        )
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 8, 16, 8)

        # Title
        title = QLabel("⚡ Futurix Jarvis")
        title.setStyleSheet(
            "color: #00d4ff; font-size: 18px; font-weight: bold;"
        )
        layout.addWidget(title)

        layout.addStretch()

        # Model selector
        self._model_combo = QComboBox()
        self._model_combo.setObjectName("model_selector")
        self._model_combo.setStyleSheet(MODEL_SELECTOR_STYLESHEET)
        for model in self._settings.ollama_available_models:
            self._model_combo.addItem(model)
        # Set current model
        idx = self._model_combo.findText(self._controller.active_model)
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)
        self._model_combo.currentTextChanged.connect(self._on_model_changed)
        layout.addWidget(self._model_combo)

        # Reconnect button
        reconnect_btn = QPushButton("🔄")
        reconnect_btn.setToolTip("Reconnect to Ollama")
        reconnect_btn.setFixedSize(32, 32)
        reconnect_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid #334155; "
            "border-radius: 6px; font-size: 16px; color: #94a3b8; }"
            "QPushButton:hover { border-color: #00d4ff; color: #00d4ff; }"
        )
        reconnect_btn.clicked.connect(self._controller.handle_reconnect)
        layout.addWidget(reconnect_btn)

        # Status dot
        self._header_status = QLabel("● Online")
        self._header_status.setStyleSheet(
            STATUS_STYLES.get("online", "color: #94a3b8;") + " font-size: 12px;"
        )
        layout.addWidget(self._header_status)

        return header

    def _build_input_bar(self) -> QWidget:
        """Build the chat input bar with voice button and send button."""
        bar = QWidget()
        bar.setStyleSheet(
            "background: #111827; border-top: 1px solid #334155;"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Voice button
        self._voice_btn = VoiceButton()
        self._voice_btn.clicked.connect(self._on_voice_clicked)
        layout.addWidget(self._voice_btn)

        # Text input
        self._input = QLineEdit()
        self._input.setObjectName("chat_input")
        self._input.setPlaceholderText("Ask Jarvis anything… (Enter to send, Ctrl+Space for voice)")
        self._input.setStyleSheet(CHAT_STYLESHEET)
        self._input.returnPressed.connect(self._on_send_clicked)
        layout.addWidget(self._input, 1)

        # Send button
        self._send_btn = QPushButton("Send  ➤")
        self._send_btn.setObjectName("send_btn")
        self._send_btn.setStyleSheet(CHAT_STYLESHEET)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.clicked.connect(self._on_send_clicked)
        layout.addWidget(self._send_btn)

        return bar

    # ── Signal connections ───────────────────────────────────────────────

    def _connect_signals(self) -> None:
        """Wire up controller signals to GUI updates."""
        ctrl = self._controller

        # Response handling
        ctrl.response_ready.connect(self._on_response)
        ctrl.error_occurred.connect(self._on_error)
        ctrl.status_changed.connect(self._on_status_changed)
        ctrl.tool_executed.connect(self._on_tool_executed)
        ctrl.conversations_updated.connect(self._refresh_conversations)
        ctrl.model_changed.connect(self._on_model_switched)

        # History panel
        self._history_panel.conversation_selected.connect(self._on_conversation_selected)
        self._history_panel.conversation_deleted.connect(ctrl.handle_delete_conversation)
        self._history_panel.new_conversation_requested.connect(self._on_new_conversation)

        # Voice
        ctrl.stt.listening_started.connect(lambda: self._voice_btn.set_listening(True))
        ctrl.stt.listening_stopped.connect(lambda: self._voice_btn.set_listening(False))

    # ── Slot handlers ────────────────────────────────────────────────────

    @pyqtSlot()
    def _on_send_clicked(self) -> None:
        """Handle send button click or Enter key."""
        text = self._input.text().strip()
        if not text:
            return

        # Display user message
        self._chat_widget.add_user_message(text)
        self._input.clear()
        self._input.setFocus()

        # Disable send while processing
        self._send_btn.setEnabled(False)

        # Dispatch to controller
        self._controller.handle_user_input(text)

    @pyqtSlot()
    def _on_voice_clicked(self) -> None:
        """Handle voice button click or Ctrl+Space."""
        self._controller.handle_voice_input()

    @pyqtSlot(str)
    def _on_response(self, response: str) -> None:
        """Display the assistant's response."""
        self._chat_widget.add_assistant_message(response)
        self._send_btn.setEnabled(True)

    @pyqtSlot(str)
    def _on_error(self, error: str) -> None:
        """Display an error message."""
        self._chat_widget.add_system_message(f"⚠️ {error}")
        self._send_btn.setEnabled(True)

    @pyqtSlot(str)
    def _on_status_changed(self, status: str) -> None:
        """Update all status indicators."""
        style = STATUS_STYLES.get(status, STATUS_STYLES["idle"])

        status_map = {
            "online": "● Online",
            "offline": "● Offline",
            "thinking": "◉ Thinking…",
            "listening": "◉ Listening…",
            "idle": "● Idle",
        }
        display = status_map.get(status, "● Unknown")

        self._header_status.setText(display)
        self._header_status.setStyleSheet(style + " font-size: 12px;")
        self._status_label.setText(display)
        self._history_panel.set_status(status)

        if status == "thinking":
            self._voice_btn.set_processing(True)
        elif status in ("online", "offline", "idle"):
            self._voice_btn.set_processing(False)

    @pyqtSlot(str, str)
    def _on_tool_executed(self, tool_name: str, result: str) -> None:
        """Display a tool execution indicator in the chat."""
        self._chat_widget.add_tool_execution(tool_name, result)

    @pyqtSlot(int)
    def _on_conversation_selected(self, conv_id: int) -> None:
        """Load and display a selected conversation."""
        self._controller.handle_load_conversation(conv_id)
        messages = self._controller.memory.get_context(limit=100)
        self._chat_widget.load_history(messages)

    @pyqtSlot()
    def _on_new_conversation(self) -> None:
        """Create a new conversation and clear the chat."""
        self._controller.handle_new_conversation()
        self._chat_widget.clear_chat()

    @pyqtSlot(str)
    def _on_model_changed(self, model_name: str) -> None:
        """Handle model selector change."""
        self._controller.handle_switch_model(model_name)

    @pyqtSlot(str)
    def _on_model_switched(self, model_name: str) -> None:
        """Update UI after model switch."""
        self._history_panel.set_model_info(model_name)
        self._chat_widget.add_system_message(f"Model switched to: {model_name}")

    def _refresh_conversations(self) -> None:
        """Reload the conversation list in the sidebar."""
        conversations = self._controller.memory.get_conversations()
        self._history_panel.update_conversations(conversations)

    # ── Window events ────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Clean up resources on window close."""
        logger.info("Window closing — shutting down controller…")
        self._controller.shutdown()
        event.accept()
