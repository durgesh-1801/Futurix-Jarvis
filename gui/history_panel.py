"""
Futurix Jarvis — Conversation History Panel.

A sidebar widget showing past conversations with click-to-load and
right-click-to-delete functionality.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.styles import SIDEBAR_STYLESHEET


class HistoryPanel(QWidget):
    """Sidebar panel listing past conversations.

    Signals:
        conversation_selected(int): Emitted when a conversation is clicked (ID).
        conversation_deleted(int): Emitted when delete is confirmed (ID).
        new_conversation_requested(): Emitted when "New Chat" is clicked.

    Usage::

        panel = HistoryPanel()
        panel.conversation_selected.connect(on_select)
        panel.update_conversations([{"id": 1, "title": "Hello", ...}])
    """

    conversation_selected = pyqtSignal(int)
    conversation_deleted = pyqtSignal(int)
    new_conversation_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(280)
        self.setStyleSheet(SIDEBAR_STYLESHEET)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the sidebar layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ───────────────────────────────────────────────────────
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 8, 0, 0)

        title = QLabel("⚡ Jarvis")
        title.setObjectName("sidebar_title")
        header_layout.addWidget(title)

        # New chat button
        self._new_btn = QPushButton("✨  New Chat")
        self._new_btn.setObjectName("new_chat_btn")
        self._new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_btn.clicked.connect(self.new_conversation_requested.emit)
        header_layout.addWidget(self._new_btn)

        layout.addWidget(header)

        # ── Conversation list ────────────────────────────────────────────
        self._list = QListWidget()
        self._list.setObjectName("conversation_list")
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)

        # ── Footer with model info ───────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet("background: #111827; border-top: 1px solid #334155;")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(12, 8, 12, 8)

        self._model_label = QLabel("Model: —")
        self._model_label.setStyleSheet("color: #64748b; font-size: 11px;")
        footer_layout.addWidget(self._model_label)

        self._status_label = QLabel("● Offline")
        self._status_label.setStyleSheet("color: #ef4444; font-size: 11px;")
        footer_layout.addWidget(self._status_label)

        layout.addWidget(footer)

    # ── Public API ───────────────────────────────────────────────────────

    def update_conversations(self, conversations: list[dict]) -> None:
        """Refresh the conversation list.

        Args:
            conversations: List of dicts with ``id``, ``title``, ``updated_at``.
        """
        self._list.clear()
        for conv in conversations:
            title = conv.get("title", "Untitled")
            if len(title) > 35:
                title = title[:32] + "…"

            item = QListWidgetItem(f"💬  {title}")
            item.setData(Qt.ItemDataRole.UserRole, conv.get("id"))
            item.setToolTip(
                f"Created: {conv.get('created_at', '?')}\n"
                f"Updated: {conv.get('updated_at', '?')}"
            )
            self._list.addItem(item)

    def set_model_info(self, model_name: str) -> None:
        """Update the model name display.

        Args:
            model_name: Name of the active model.
        """
        self._model_label.setText(f"Model: {model_name}")

    def set_status(self, status: str) -> None:
        """Update the connection status display.

        Args:
            status: One of 'online', 'offline', 'thinking', 'listening'.
        """
        status_map = {
            "online": ("● Online", "#22c55e"),
            "offline": ("● Offline", "#ef4444"),
            "thinking": ("◉ Thinking…", "#f59e0b"),
            "listening": ("◉ Listening…", "#00d4ff"),
            "idle": ("● Idle", "#94a3b8"),
        }
        text, colour = status_map.get(status, ("● Unknown", "#94a3b8"))
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {colour}; font-size: 11px;")

    # ── Private slots ────────────────────────────────────────────────────

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """Handle conversation item click."""
        conv_id = item.data(Qt.ItemDataRole.UserRole)
        if conv_id is not None:
            self.conversation_selected.emit(conv_id)

    def _show_context_menu(self, position) -> None:
        """Show right-click context menu for conversation items."""
        item = self._list.itemAt(position)
        if item is None:
            return

        conv_id = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #1e293b; color: #f1f5f9; border: 1px solid #334155; "
            "border-radius: 8px; padding: 4px; }"
            "QMenu::item:selected { background: rgba(239, 68, 68, 0.15); }"
        )
        delete_action = menu.addAction("🗑️  Delete Conversation")
        action = menu.exec(self._list.mapToGlobal(position))

        if action == delete_action and conv_id is not None:
            self.conversation_deleted.emit(conv_id)
