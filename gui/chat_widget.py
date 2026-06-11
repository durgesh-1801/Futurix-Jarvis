"""
Futurix Jarvis — Chat Display Widget.

A rich text browser that renders conversation messages with styled HTML
bubbles.  Supports streaming text append and auto-scrolling.
"""

from __future__ import annotations

import html
import re
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

from gui.styles import (
    ASSISTANT_MESSAGE_HTML,
    CHAT_STYLESHEET,
    SYSTEM_MESSAGE_HTML,
    TOOL_EXECUTION_HTML,
    USER_MESSAGE_HTML,
    WELCOME_HTML,
)


class ChatWidget(QWidget):
    """Chat display area with styled message bubbles.

    Renders user and assistant messages as HTML inside a ``QTextBrowser``.
    Supports streaming token appends and auto-scrolling.

    Usage::

        chat = ChatWidget()
        chat.add_user_message("Hello!")
        chat.add_assistant_message("Hi there! How can I help?")
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._show_welcome()

    def _setup_ui(self) -> None:
        """Build the widget layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._browser = QTextBrowser()
        self._browser.setObjectName("chat_display")
        self._browser.setOpenExternalLinks(True)
        self._browser.setReadOnly(True)
        self._browser.setStyleSheet(CHAT_STYLESHEET)
        layout.addWidget(self._browser)

        self._message_count = 0
        self._streaming_buffer = ""

    # ── Public API ───────────────────────────────────────────────────────

    def add_user_message(self, text: str) -> None:
        """Display a user message bubble.

        Args:
            text: The user's message text.
        """
        if self._message_count == 0:
            self._browser.clear()

        escaped = self._format_text(text)
        html_block = USER_MESSAGE_HTML.format(message=escaped)
        self._append_html(html_block)
        self._message_count += 1

    def add_assistant_message(self, text: str) -> None:
        """Display an assistant message bubble.

        Args:
            text: The assistant's response text.
        """
        formatted = self._format_text(text)
        html_block = ASSISTANT_MESSAGE_HTML.format(message=formatted)
        self._append_html(html_block)
        self._message_count += 1

    def add_tool_execution(self, tool_name: str, result: str) -> None:
        """Display a tool execution indicator.

        Args:
            tool_name: Name of the tool that was executed.
            result: Preview of the tool's result.
        """
        preview = result[:150].replace("\n", " ")
        html_block = TOOL_EXECUTION_HTML.format(
            tool_name=html.escape(tool_name),
            result_preview=html.escape(preview),
        )
        self._append_html(html_block)

    def add_system_message(self, text: str) -> None:
        """Display a centered system/info message.

        Args:
            text: The system message text.
        """
        html_block = SYSTEM_MESSAGE_HTML.format(message=html.escape(text))
        self._append_html(html_block)

    def start_streaming(self) -> None:
        """Begin a streaming assistant response."""
        self._streaming_buffer = ""
        if self._message_count == 0:
            self._browser.clear()

    def append_streaming_token(self, token: str) -> None:
        """Append a token to the current streaming response.

        Args:
            token: A single token/chunk from the LLM.
        """
        self._streaming_buffer += token

    def finish_streaming(self) -> None:
        """Finalise the streaming response and render it."""
        if self._streaming_buffer:
            self.add_assistant_message(self._streaming_buffer)
            self._streaming_buffer = ""

    def clear_chat(self) -> None:
        """Clear all messages and show the welcome screen."""
        self._browser.clear()
        self._message_count = 0
        self._show_welcome()

    def load_history(self, messages: list[dict[str, str]]) -> None:
        """Load a list of historical messages.

        Args:
            messages: List of ``{role, content}`` dicts.
        """
        self._browser.clear()
        self._message_count = 0

        if not messages:
            self._show_welcome()
            return

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                self.add_user_message(content)
            elif role == "assistant":
                self.add_assistant_message(content)
            elif role == "system":
                self.add_system_message(content)

    # ── Private helpers ──────────────────────────────────────────────────

    def _show_welcome(self) -> None:
        """Display the welcome screen."""
        self._browser.setHtml(WELCOME_HTML)

    def _append_html(self, html_content: str) -> None:
        """Append HTML to the browser and scroll to bottom."""
        cursor = self._browser.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._browser.setTextCursor(cursor)
        self._browser.insertHtml(html_content)
        self._browser.insertHtml("<br>")
        # Auto-scroll to bottom
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        """Scroll the browser to the bottom."""
        scrollbar = self._browser.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @staticmethod
    def _format_text(text: str) -> str:
        """Convert plain text / basic Markdown to HTML for display.

        Args:
            text: Input text with optional Markdown formatting.

        Returns:
            HTML-safe formatted string.
        """
        # Escape HTML entities
        text = html.escape(text)

        # Code blocks: ```lang\ncode\n```
        text = re.sub(
            r"```(\w*)\n(.*?)```",
            lambda m: (
                f'<pre style="background: #0f172a; border: 1px solid #334155; '
                f'border-radius: 8px; padding: 12px; margin: 8px 0; '
                f'font-family: Consolas, monospace; font-size: 13px; '
                f'color: #e2e8f0; overflow-x: auto;">{m.group(2)}</pre>'
            ),
            text,
            flags=re.DOTALL,
        )

        # Inline code: `code`
        text = re.sub(
            r"`([^`]+)`",
            r'<code style="background: #1e293b; padding: 2px 6px; '
            r'border-radius: 4px; font-family: Consolas, monospace; '
            r'font-size: 13px; color: #00d4ff;">\1</code>',
            text,
        )

        # Bold: **text**
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

        # Italic: *text*
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)

        # Headers: ## text
        text = re.sub(
            r"^### (.+)$",
            r'<div style="font-size: 14px; font-weight: bold; color: #00d4ff; margin: 8px 0 4px;">\1</div>',
            text,
            flags=re.MULTILINE,
        )
        text = re.sub(
            r"^## (.+)$",
            r'<div style="font-size: 16px; font-weight: bold; color: #00d4ff; margin: 8px 0 4px;">\1</div>',
            text,
            flags=re.MULTILINE,
        )

        # Line breaks
        text = text.replace("\n", "<br>")

        return text
