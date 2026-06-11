"""
Futurix Jarvis — LLM Service.

Provides the interface to Ollama via ``langchain-ollama``.  Supports both
streaming and non-streaming chat, tool binding, and graceful offline fallback.
"""

from __future__ import annotations

import logging
from typing import Any, Generator, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from llm.model_manager import ModelManager

logger = logging.getLogger(__name__)


def check_model_tool_support(base_url: str, model_name: str) -> bool:
    """Probes the local Ollama instance dynamically to determine if model_name supports tools.

    A whitelist/blacklist is checked first as an optimization cache. The dynamic probe is the source of truth.
    """
    model_lower = model_name.lower()

    # 1. Fast Cache Whitelist Optimization (returns True immediately)
    known_tool_models = [
        "llama3.1", "llama3.2", "qwen2.5", "mistral", "mixtral", "command-r", "llama3-groq"
    ]
    if any(pattern in model_lower for pattern in known_tool_models):
        logger.info("Model %s is in the known tool-supporting whitelist.", model_name)
        return True

    # 2. Fast Cache Blacklist Optimization (returns False immediately for known non-tool models)
    known_no_tool_models = [
        "llama3", "llama2", "gemma", "phi3", "llava", "nomic-embed"
    ]
    # Note: if it has llama3 but not llama3.1/3.2, it is llama3.0, which doesn't support tools.
    if "llama3" in model_lower and not ("llama3.1" in model_lower or "llama3.2" in model_lower):
        logger.info("Model %s is llama3.0 (which does not support tools).", model_name)
        return False

    if any(pattern in model_lower for pattern in known_no_tool_models):
        logger.info("Model %s is in the known non-tool blacklist.", model_name)
        return False

    # 3. Dynamic Tool-Calling Probe (Source of Truth for unknown models)
    logger.info("Performing dynamic tool-calling probe for model: %s", model_name)
    try:
        import httpx
        url = f"{base_url.rstrip('/')}/api/chat"
        # Dummy message and a dummy tool to see if the server accepts it
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": "Ping"}],
            "tools": [{
                "type": "function",
                "function": {
                    "name": "dummy_probe_tool",
                    "description": "Probe if tool calling works",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    }
                }
            }],
            "stream": False
        }
        resp = httpx.post(url, json=payload, timeout=3.0)
        # If it returns 400 (Bad Request), it means the model does not support tools
        if resp.status_code == 400:
            logger.info("Dynamic probe: Model %s does not support tools (status: %d)", model_name, resp.status_code)
            return False
        if resp.status_code == 200:
            logger.info("Dynamic probe: Model %s supports tools (status: 200)", model_name)
            return True

        # Any other code (e.g. model not found, server error, etc.) - default to False
        logger.warning("Dynamic probe returned status code %d for model %s. Defaulting to tool calling unsupported.", resp.status_code, model_name)
        return False
    except Exception as exc:
        logger.warning("Dynamic tool-calling probe failed with exception: %s. Defaulting to tool calling unsupported.", exc)
        return False


# ── System prompt ────────────────────────────────────────────────────────────

JARVIS_SYSTEM_PROMPT = """You are Jarvis, an advanced AI assistant created by Futurix.
You are helpful, intelligent, and speak in a natural, professional tone.

Your capabilities include:
- Opening and closing desktop applications
- Searching the web (Google, YouTube)
- Managing files and folders
- Reading system information (CPU, RAM, battery)
- Executing system commands (with user confirmation for dangerous operations)
- Capturing and analysing screenshots
- Searching through a knowledge base of documents
- Assisting with coding tasks (code generation, Git operations, repo analysis)

When a user request requires an action, use the appropriate tool.
When a request is conversational, respond naturally without tools.
Always be concise but thorough.  Use markdown formatting in your responses.
If you're unsure about something, say so honestly.

SAFETY RULES:
- NEVER delete files without explicit user confirmation.
- NEVER shut down or restart the system without explicit user confirmation.
- NEVER execute potentially destructive commands without confirmation.
- Always explain what a command will do before executing it.
"""


class LLMService(QObject):
    """High-level LLM service wrapping Ollama via LangChain.

    Provides both synchronous and streaming chat methods, tool binding,
    and graceful degradation when Ollama is offline.

    Signals:
        token_received(str): Emitted for each token during streaming.
        response_complete(str): Emitted when a full response is ready.
        error_occurred(str): Emitted on LLM errors.
        status_changed(str): Emitted when connection status changes.

    Usage::

        llm = LLMService(model_manager)
        if llm.is_available:
            response = llm.chat([{"role": "user", "content": "Hello!"}])
    """

    token_received = pyqtSignal(str)
    response_complete = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    status_changed = pyqtSignal(str)

    def __init__(
        self,
        model_manager: ModelManager,
        timeout: int = 120,
        tool_execution_mode: str = "AUTO",
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._model_manager = model_manager
        self._timeout = timeout
        self._tool_execution_mode = tool_execution_mode
        self._probe_success = False
        self._supports_tools = False
        self._execution_mode = "REACT"
        self._chat_model = None
        self._is_available = False
        self._tools: list[Any] = []
        self._initialise()

    # ── Initialisation ───────────────────────────────────────────────────

    def _initialise(self) -> None:
        """Attempt to connect to Ollama and create the chat model."""
        try:
            from langchain_ollama import ChatOllama

            if not self._model_manager.check_health():
                logger.warning("Ollama server is offline — LLM features disabled.")
                self._is_available = False
                self.status_changed.emit("offline")
                return

            self._chat_model = ChatOllama(
                model=self._model_manager.active_model,
                base_url=self._model_manager._base_url,
                timeout=self._timeout,
            )
            self._is_available = True
            self.status_changed.emit("online")
            logger.info(
                "LLM connected — model=%s", self._model_manager.active_model
            )

            # Probe for tool support
            self._probe_success = check_model_tool_support(
                self._model_manager._base_url, self._model_manager.active_model
            )

            # Determine execution mode based on TOOL_EXECUTION_MODE setting
            mode_upper = self._tool_execution_mode.upper()
            if mode_upper == "NATIVE":
                self._supports_tools = True
                self._execution_mode = "NATIVE"
            elif mode_upper == "REACT":
                self._supports_tools = False
                self._execution_mode = "REACT"
            else:  # AUTO
                self._supports_tools = self._probe_success
                self._execution_mode = "NATIVE" if self._probe_success else "REACT"

            logger.info(
                "Model: %s | Tool Probe: %s | Execution Mode: %s",
                self._model_manager.active_model,
                "Success" if self._probe_success else "Failed",
                self._execution_mode
            )

        except ImportError:
            logger.error("langchain-ollama not installed — LLM disabled.")
            self._is_available = False
            self.status_changed.emit("offline")

        except Exception as exc:
            logger.error("Failed to initialise LLM: %s", exc)
            self._is_available = False
            self.status_changed.emit("offline")

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        """Whether the LLM is connected and ready."""
        return self._is_available

    @property
    def model_name(self) -> str:
        """The active model name."""
        return self._model_manager.active_model

    @property
    def is_native_tool_calling_active(self) -> bool:
        """Whether native tool calling is active."""
        return self._is_available and self._supports_tools

    @property
    def execution_mode(self) -> str:
        """The active tool execution mode ('NATIVE' or 'REACT')."""
        return self._execution_mode

    @property
    def probe_success(self) -> bool:
        """Whether the dynamic tool probe succeeded."""
        return self._probe_success

    # ── Model switching ──────────────────────────────────────────────────

    def switch_model(self, model_name: str) -> bool:
        """Switch to a different Ollama model.

        Args:
            model_name: Name of the model to switch to.

        Returns:
            ``True`` if the switch was successful.
        """
        self._model_manager.set_active_model(model_name)
        self._initialise()
        return self._is_available

    # ── Tool binding ─────────────────────────────────────────────────────

    def bind_tools(self, tools: list[Any]) -> None:
        """Bind LangChain tools to the chat model.

        Args:
            tools: List of LangChain ``@tool``-decorated functions.
        """
        self._tools = tools
        if self._chat_model is not None and tools:
            if self.is_native_tool_calling_active:
                try:
                    self._chat_model = self._chat_model.bind_tools(tools)
                    logger.info("Bound %d tools natively to LLM", len(tools))
                except Exception as exc:
                    logger.warning(
                        "Model does not support native tool calling.\nFalling back to ReAct tool execution. Details: %s",
                        exc
                    )
                    self._supports_tools = False
                    self._execution_mode = "REACT"
            else:
                logger.info(
                    "Native tool calling inactive (mode=%s). %d tools registered for ReAct execution.",
                    self._execution_mode,
                    len(tools)
                )

    # ── Chat methods ─────────────────────────────────────────────────────

    def chat(
        self,
        messages: list[dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> str:
        """Send a chat request and return the full response.

        Args:
            messages: List of ``{role, content}`` message dicts.
            system_prompt: Override the default system prompt.

        Returns:
            The assistant's response text, or a fallback message if offline.
        """
        if not self._is_available or self._chat_model is None:
            return self._offline_response()

        prompt = system_prompt or JARVIS_SYSTEM_PROMPT
        full_messages = [{"role": "system", "content": prompt}] + messages

        try:
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

            lc_messages = []
            for m in full_messages:
                if m["role"] == "system":
                    lc_messages.append(SystemMessage(content=m["content"]))
                elif m["role"] == "user":
                    lc_messages.append(HumanMessage(content=m["content"]))
                elif m["role"] == "assistant":
                    lc_messages.append(AIMessage(content=m["content"]))

            response = self._chat_model.invoke(lc_messages)
            return response.content

        except Exception as exc:
            logger.error("LLM chat error: %s", exc)
            self.error_occurred.emit(str(exc))
            return f"I encountered an error: {exc}"

    def stream_chat(
        self,
        messages: list[dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """Stream a chat response token by token.

        Args:
            messages: List of ``{role, content}`` message dicts.
            system_prompt: Override the default system prompt.

        Yields:
            Individual tokens/chunks of the response.
        """
        if not self._is_available or self._chat_model is None:
            yield self._offline_response()
            return

        prompt = system_prompt or JARVIS_SYSTEM_PROMPT
        full_messages = [{"role": "system", "content": prompt}] + messages

        try:
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

            lc_messages = []
            for m in full_messages:
                if m["role"] == "system":
                    lc_messages.append(SystemMessage(content=m["content"]))
                elif m["role"] == "user":
                    lc_messages.append(HumanMessage(content=m["content"]))
                elif m["role"] == "assistant":
                    lc_messages.append(AIMessage(content=m["content"]))

            for chunk in self._chat_model.stream(lc_messages):
                token = chunk.content
                if token:
                    yield token

        except Exception as exc:
            logger.error("LLM stream error: %s", exc)
            yield f"I encountered an error: {exc}"

    def invoke_with_tools(
        self,
        messages: list[dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> Any:
        """Invoke the LLM and return the raw response (including tool_calls).

        This is used by the AgentOrchestrator for the ReAct loop.

        Args:
            messages: List of ``{role, content}`` message dicts.
            system_prompt: Override the default system prompt.

        Returns:
            The raw LangChain ``AIMessage`` response object.
        """
        if not self._is_available or self._chat_model is None:
            return None

        prompt = system_prompt or JARVIS_SYSTEM_PROMPT
        full_messages = [{"role": "system", "content": prompt}] + messages

        try:
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

            lc_messages = []
            for m in full_messages:
                if m["role"] == "system":
                    lc_messages.append(SystemMessage(content=m["content"]))
                elif m["role"] == "user":
                    lc_messages.append(HumanMessage(content=m["content"]))
                elif m["role"] == "assistant":
                    lc_messages.append(AIMessage(content=m["content"]))

            return self._chat_model.invoke(lc_messages)

        except Exception as exc:
            logger.error("LLM invoke error: %s", exc)
            return None

    # ── Reconnection ─────────────────────────────────────────────────────

    def reconnect(self) -> bool:
        """Attempt to reconnect to Ollama.

        Returns:
            ``True`` if reconnection was successful.
        """
        logger.info("Attempting LLM reconnection…")
        self._initialise()
        return self._is_available

    # ── Fallback ─────────────────────────────────────────────────────────

    @staticmethod
    def _offline_response() -> str:
        """Return a friendly fallback message when the LLM is offline."""
        return (
            "🔌 I'm currently offline — the Ollama server isn't reachable.\n\n"
            "I can still help with:\n"
            "• Opening applications\n"
            "• Searching the web\n"
            "• Managing files\n"
            "• System information\n\n"
            "To restore AI features, start Ollama with: `ollama serve`"
        )
