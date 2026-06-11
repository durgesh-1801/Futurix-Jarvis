"""
Futurix Jarvis — Assistant Controller.

The central bridge between the GUI and all backend services.  Receives
user input, dispatches it to the agent, and emits Qt signals that the
GUI connects to for display updates.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from assistant.agent import AgentOrchestrator
from config.settings import Settings
from database.db_manager import DatabaseManager
from knowledge.rag_service import RAGService, set_rag_instance
from knowledge.vector_store_factory import create_vector_store
from llm.llm_service import LLMService
from llm.model_manager import ModelManager
from mcp.mcp_client import MCPClient
from memory.memory_service import MemoryService
from voice.speech_to_text import SpeechToText
from voice.text_to_speech import TextToSpeech

# Import tool registries
from automation.app_launcher import get_app_launcher_tools
from automation.file_manager import get_file_manager_tools
from automation.web_search import get_web_search_tools
from automation.system_info import get_system_info_tools
from automation.system_commands import get_system_command_tools
from automation.screen_capture import get_screen_capture_tools
from knowledge.rag_service import get_knowledge_tools
from coding.coding_agent import get_coding_tools

# Phase 3 imports
from vision.vision_provider import OllamaVisionProvider
from vision.vision_service import VisionService
from coding.workspace_index import WorkspaceIndexer
from memory.task_service import TaskService

logger = logging.getLogger(__name__)


class _AgentWorker(QObject):
    """Background worker for running agent tasks off the GUI thread."""

    finished = pyqtSignal(str, list)   # (response_text, tool_executions)
    error = pyqtSignal(str)
    token = pyqtSignal(str)            # for streaming

    def __init__(self, agent: AgentOrchestrator, message: str, context: list) -> None:
        super().__init__()
        self._agent = agent
        self._message = message
        self._context = context

    def run(self) -> None:
        """Execute the agent (runs on QThread)."""
        try:
            response, tool_execs = self._agent.run_streaming(
                self._message, self._context
            )
            self.finished.emit(response, tool_execs)
        except Exception as exc:
            logger.exception("Agent worker error")
            self.error.emit(str(exc))


class AssistantController(QObject):
    """Central controller bridging the GUI to all backend services.

    Signals:
        response_ready(str): Final assistant response text.
        response_streaming(str): Individual streaming tokens.
        status_changed(str): Status indicator updates ('online', 'offline', 'thinking', 'listening').
        error_occurred(str): Error messages for the GUI.
        tool_executed(str, str): (tool_name, result) when a tool runs.
        conversations_updated(): Emitted when the conversation list changes.
        model_changed(str): Emitted when the active model changes.

    Usage::

        ctrl = AssistantController(settings)
        ctrl.response_ready.connect(gui.display_response)
        ctrl.handle_user_input("Open Chrome")
    """

    response_ready = pyqtSignal(str)
    response_streaming = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    tool_executed = pyqtSignal(str, str)
    conversations_updated = pyqtSignal()
    model_changed = pyqtSignal(str)

    def __init__(self, settings: Settings, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._worker_thread: Optional[QThread] = None
        self._worker: Optional[_AgentWorker] = None

        # ── Initialise services ──────────────────────────────────────────
        logger.info("Initialising assistant controller…")

        # Database
        self._db = DatabaseManager(settings.db_path)

        # Memory
        self._memory = MemoryService(self._db)

        # Model manager
        self._model_manager = ModelManager(
            base_url=settings.ollama_base_url,
            default_model=settings.ollama_model,
            configured_models=settings.ollama_available_models,
            timeout=10,
        )
        self._model_manager.list_models()

        # LLM
        self._llm = LLMService(
            self._model_manager,
            timeout=settings.ollama_timeout,
            tool_execution_mode=settings.tool_execution_mode
        )
        self._llm.status_changed.connect(self.status_changed.emit)
        self._llm.error_occurred.connect(self.error_occurred.emit)

        # RAG
        self._vector_store = create_vector_store(
            persist_dir=settings.vector_db_path,
            model_name=settings.embeddings_model,
            base_url=settings.ollama_base_url,
        )
        self._rag = RAGService(
            self._db,
            self._vector_store,
            knowledge_dir=settings.knowledge_dir,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        set_rag_instance(self._rag)

        # Vision
        self._vision_provider = OllamaVisionProvider(
            model_name="llava",
            base_url=settings.ollama_base_url,
        )
        self._vision_service = VisionService(self._vision_provider)
        from vision.vision_service import set_vision_service
        set_vision_service(self._vision_service)

        # Workspace Intelligence
        self._workspace_indexer = WorkspaceIndexer(
            db=self._db,
            llm=self._llm,
        )
        from coding.workspace_index import set_workspace_indexer
        set_workspace_indexer(self._workspace_indexer)

        # Task Memory
        self._task_service = TaskService(db=self._db)
        from memory.task_service import set_task_service
        set_task_service(self._task_service)

        # MCP
        self._mcp = MCPClient(
            config_path=settings.mcp_servers_config,
            enabled=settings.mcp_enabled,
        )

        # Voice
        self._stt = SpeechToText(wake_word=settings.wake_word)
        self._stt.text_recognised.connect(self._on_voice_input)
        self._stt.error_occurred.connect(self.error_occurred.emit)
        self._stt.listening_started.connect(lambda: self.status_changed.emit("listening"))
        self._stt.listening_stopped.connect(lambda: self.status_changed.emit("idle"))

        self._tts = TextToSpeech(
            rate=settings.voice_rate,
            volume=settings.voice_volume,
            voice_id=settings.voice_id,
        )

        # Agent — register all tools
        from coding.workspace_index import get_coding_tools as get_workspace_coding_tools
        from memory.task_service import get_task_tools
        from vision.vision_service import get_vision_tools

        all_tools = (
            get_app_launcher_tools()
            + get_file_manager_tools()
            + get_web_search_tools()
            + get_system_info_tools()
            + get_system_command_tools()
            + get_screen_capture_tools()
            + get_vision_tools()
            + get_knowledge_tools()
            + get_coding_tools()
            + get_workspace_coding_tools()
            + get_task_tools()
        )
        self._agent = AgentOrchestrator(self._llm, all_tools)

        # Start a default conversation
        self._memory.start_conversation("Welcome")

        logger.info(
            "Controller ready — LLM: %s, Tools: %d, MCP: %s",
            "online" if self._llm.is_available else "offline",
            len(all_tools),
            "enabled" if self._mcp.is_enabled else "disabled",
        )
        # Startup diagnostics
        logger.info("Model: %s", self._llm.model_name)
        logger.info("Tool Probe: %s", "Success" if self._llm.probe_success else "Failed")
        logger.info("Execution Mode: %s", self._llm.execution_mode)

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def is_llm_online(self) -> bool:
        return self._llm.is_available

    @property
    def active_model(self) -> str:
        return self._model_manager.active_model

    @property
    def memory(self) -> MemoryService:
        return self._memory

    @property
    def model_manager(self) -> ModelManager:
        return self._model_manager

    @property
    def stt(self) -> SpeechToText:
        return self._stt

    @property
    def tts(self) -> TextToSpeech:
        return self._tts

    # ── User input handling ──────────────────────────────────────────────

    @pyqtSlot(str)
    def handle_user_input(self, text: str) -> None:
        """Process a text input from the user.

        Runs the agent on a background thread to keep the GUI responsive.

        Args:
            text: The user's message.
        """
        if not text.strip():
            return

        # Check if a thread is already running to prevent concurrent collisions
        if self._worker_thread and self._worker_thread.isRunning():
            logger.warning("Agent worker is currently running. Ignoring new input.")
            self.error_occurred.emit("Assistant is busy processing your previous request. Please wait.")
            return

        logger.info("User: %s", text[:100])
        self.status_changed.emit("thinking")

        # Get conversation context
        context = self._memory.get_context(limit=20)

        # Augment with RAG context if relevant
        rag_context = self._rag.retrieve_context_string(text, top_k=3)
        if rag_context:
            context.append({"role": "system", "content": rag_context})

        # Run agent on background thread
        self._worker_thread = QThread()
        self._worker = _AgentWorker(self._agent, text, context)
        self._worker.moveToThread(self._worker_thread)

        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(
            lambda resp, tools: self._on_agent_complete(text, resp, tools)
        )
        self._worker.error.connect(self._on_agent_error)
        
        # Ensure thread stops running on both success and error
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.error.connect(self._worker_thread.quit)
        
        self._worker_thread.finished.connect(self._cleanup_worker)

        self._worker_thread.start()

    @pyqtSlot()
    def handle_voice_input(self) -> None:
        """Start listening for voice input."""
        if self._stt.is_listening:
            self._stt.stop_listening()
        else:
            self.status_changed.emit("listening")
            self._stt.start_listening()

    @pyqtSlot()
    def handle_new_conversation(self) -> None:
        """Create a new conversation."""
        self._memory.start_conversation()
        self.conversations_updated.emit()

    @pyqtSlot(int)
    def handle_load_conversation(self, conversation_id: int) -> None:
        """Load an existing conversation."""
        self._memory.load_conversation(conversation_id)

    @pyqtSlot(int)
    def handle_delete_conversation(self, conversation_id: int) -> None:
        """Delete a conversation."""
        self._memory.delete_conversation(conversation_id)
        self.conversations_updated.emit()

    @pyqtSlot(str)
    def handle_switch_model(self, model_name: str) -> None:
        """Switch the active LLM model."""
        success = self._llm.switch_model(model_name)
        if success:
            self.model_changed.emit(model_name)
            self.status_changed.emit("online")
        else:
            self.error_occurred.emit(f"Failed to switch to model: {model_name}")

    @pyqtSlot()
    def handle_reconnect(self) -> None:
        """Attempt to reconnect to Ollama."""
        success = self._llm.reconnect()
        if success:
            self.status_changed.emit("online")
        else:
            self.status_changed.emit("offline")

    # ── Private slots ────────────────────────────────────────────────────

    def _on_voice_input(self, text: str) -> None:
        """Handle recognised voice input."""
        clean_text = self._stt.strip_wake_word(text)
        if clean_text:
            self.handle_user_input(clean_text)

    def _on_agent_complete(self, user_msg: str, response: str, tool_execs: list) -> None:
        """Handle agent completion."""
        self.status_changed.emit("online" if self._llm.is_available else "offline")

        # Emit tool execution events
        for exec_info in tool_execs:
            self.tool_executed.emit(exec_info["name"], exec_info["result"])

        # Save to memory
        metadata = {"tools": tool_execs} if tool_execs else None
        self._memory.save_exchange(user_msg, response, metadata)
        self.conversations_updated.emit()

        # Emit the response
        self.response_ready.emit(response)

        # Speak the response (TTS)
        if self._tts.is_available:
            # Strip markdown for speech
            import re
            clean = re.sub(r"[*_`#\[\]|>!]", "", response)
            clean = re.sub(r"\n+", ". ", clean)
            if len(clean) < 500:  # Only speak short responses
                self._tts.speak(clean)

    def _on_agent_error(self, error: str) -> None:
        """Handle agent errors."""
        self.status_changed.emit("online" if self._llm.is_available else "offline")
        self.error_occurred.emit(error)
        self.response_ready.emit(f"❌ An error occurred: {error}")

    def _cleanup_worker(self) -> None:
        """Clean up worker thread resources."""
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._worker_thread is not None:
            self._worker_thread.deleteLater()
            self._worker_thread = None

    # ── Cleanup ──────────────────────────────────────────────────────────

    def shutdown(self) -> None:
        """Clean up all resources."""
        logger.info("Shutting down assistant controller…")
        self._tts.shutdown()
        self._stt.shutdown()
        if self._worker_thread and self._worker_thread.isRunning():
            self._worker_thread.quit()
            if not self._worker_thread.wait(3000):
                logger.warning("Agent worker thread did not stop. Terminating...")
                self._worker_thread.terminate()
                self._worker_thread.wait(1000)
        self._db.close()
        logger.info("Controller shut down.")
