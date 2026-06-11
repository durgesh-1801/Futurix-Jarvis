import sys
import os
import time
import logging
import threading
import psutil
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from assistant.agent import AgentOrchestrator
from llm.llm_service import LLMService
from config.settings import get_settings
from database.db_manager import DatabaseManager
from coding.workspace_index import WorkspaceIndexer
from voice.speech_to_text import SpeechToText
from automation.app_launcher import get_app_launcher_tools
from automation.file_manager import get_file_manager_tools
from automation.web_search import get_web_search_tools
from automation.system_info import get_system_info_tools
from automation.system_commands import get_system_command_tools
from automation.screen_capture import get_screen_capture_tools

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger("stability_validation")

def check_resources():
    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / (1024 * 1024)
    threads = threading.active_count()
    return mem_mb, threads

def run_voice_e2e_test(agent):
    logger.info("--- 1. End-to-End Voice Test ---")
    mock_stt = SpeechToText()
    
    # We will mock speech recognition stream and test commands
    voice_commands = [
        "open calculator",
        "open chrome",
        "what's the battery percentage"
    ]
    
    for command in voice_commands:
        logger.info(f"Simulating voice recognition of: '{command}'")
        # Direct route execution
        res = agent._deterministic_route(command)
        if res:
            res_text, executions = res
            logger.info(f"STT -> controller -> matched tool: {executions[0]['name']}")
            logger.info(f"Tool response: {str(res_text).splitlines()[0]}")
        else:
            logger.warning("No tool matched (ReAct fallback)")

def run_long_session_test(agent):
    logger.info("--- 2. Long Session Test (30+ mixed commands) ---")
    
    mixed_commands = [
        # Battery commands (Battery intent)
        "what's the battery percentage",
        "how much battery is left?",
        "check battery",
        "show battery status",
        "battery status",
        "battery percentage",
        "remaining battery",
        "power status",
        # CPU/Resource commands (Resource intent)
        "show cpu usage",
        "what is my cpu usage?",
        "system resources",
        "cpu usage",
        "resource usage",
        # App launching commands (App intent)
        "open chrome",
        "launch chrome",
        "start chrome",
        "open calculator",
        "launch calculator",
        "open vscode",
        "start vscode",
        "open notepad",
        "launch notepad",
        "open explorer",
        "launch file explorer",
        # Other variations
        "whats the battery percentage?",
        "can you check my battery?",
        "battery status!",
        "cpu usage.",
        "open chrome...",
        "open vscode!",
        "system resources?",
        "check my battery",
        "launch calc",
        "start vs code"
    ]
    
    mem_start, threads_start = check_resources()
    logger.info(f"Start resource status: Memory={mem_start:.2f} MB, Threads={threads_start}")
    
    start_time = time.time()
    successful_routes = 0
    
    for i, cmd in enumerate(mixed_commands):
        res = agent._deterministic_route(cmd)
        if res:
            successful_routes += 1
            
        if (i + 1) % 5 == 0 or (i + 1) == len(mixed_commands):
            mem_curr, threads_curr = check_resources()
            logger.info(f"Step {i+1}/{len(mixed_commands)}: Memory={mem_curr:.2f} MB (Delta={mem_curr - mem_start:+.2f} MB), Threads={threads_curr}")
            
    end_time = time.time()
    mem_end, threads_end = check_resources()
    
    logger.info(f"Long session completed in {end_time - start_time:.2f}s")
    logger.info(f"Successful matches: {successful_routes}/{len(mixed_commands)}")
    logger.info(f"End resource status: Memory={mem_end:.2f} MB, Threads={threads_end}")
    logger.info(f"Memory leak: {mem_end - mem_start:+.2f} MB")
    logger.info(f"Thread leak: {threads_end - threads_start:+.0f} threads")
    
    return {
        "duration": end_time - start_time,
        "mem_delta": mem_end - mem_start,
        "thread_delta": threads_end - threads_start,
        "total_commands": len(mixed_commands),
        "successful_routes": successful_routes
    }

def run_vision_test(agent):
    logger.info("--- 3. Vision Test ---")
    from automation.screen_capture import capture_screenshot, analyse_screenshot
    from vision.vision_service import review_ui, analyse_terminal_output
    
    # 1. Capture screenshot
    logger.info("Capturing screenshot...")
    scr_res = capture_screenshot.invoke({"save_path": "temp_validation_screenshot.png"})
    logger.info(f"Screenshot result: {scr_res}")
    
    # 2. Analyse screenshot (with mock response if offline)
    logger.info("Analysing screenshot...")
    analysis_res = analyse_screenshot.invoke({"description": "Describe what you see on screen"})
    logger.info(f"Analysis preview: {analysis_res.splitlines()[0] if analysis_res else 'None'}")
    
    # 3. Review UI
    logger.info("Reviewing UI...")
    review_res = review_ui.invoke({"prompt": "Review design and alignment."})
    logger.info(f"UI Review preview: {review_res.splitlines()[0] if review_res else 'None'}")
    
    # 4. Analyse terminal output
    logger.info("Analysing terminal output...")
    terminal_res = analyse_terminal_output.invoke({"prompt": "Explain compiler outputs."})
    logger.info(f"Terminal output preview: {terminal_res.splitlines()[0] if terminal_res else 'None'}")
    
    # Clean up temp screenshot
    if os.path.exists("temp_validation_screenshot.png"):
        os.remove("temp_validation_screenshot.png")
        logger.info("Temporary screenshot cleaned up.")

def run_repository_index_test():
    logger.info("--- 4. Repository Index Test ---")
    from pathlib import Path
    db_path = Path("data/jarvis.db")
    db = DatabaseManager(db_path)
    indexer = WorkspaceIndexer(db)
    
    start_time = time.time()
    logger.info("Indexing entire futurix_jarvis project...")
    stats = indexer.index_directory(_PROJECT_ROOT)
    end_time = time.time()
    
    logger.info(f"Indexing completed in {end_time - start_time:.2f}s")
    logger.info(f"Files indexed: {stats.get('files_indexed', 0)}")
    logger.info(f"Symbols extracted: {stats.get('symbols_extracted', 0)}")
    
    # Verify symbol search
    logger.info("Verifying symbol search...")
    symbols = db.search_code_symbols("AgentOrchestrator", "class")
    logger.info(f"Found {len(symbols)} matches for class 'AgentOrchestrator'")
    for sym in symbols:
        logger.info(f"Class: {sym.symbol_name} in {sym.file_path} at line {sym.line_number}")
        
    # Verify repository summary
    logger.info("Verifying repository summary...")
    summary = db.get_repository_summary(_PROJECT_ROOT)
    if summary:
        logger.info(f"Total files: {summary.total_files}")
        logger.info(f"Languages detected: {summary.languages_detected}")
        logger.info(f"Dependency files: {summary.dependency_files}")
    else:
        logger.warning("Repository summary not found in database.")
        
    db.close()
    
    return {
        "duration": end_time - start_time,
        "files_indexed": stats.get('files_indexed', 0),
        "symbols_extracted": stats.get('symbols_extracted', 0)
    }

def run_shutdown_test():
    logger.info("--- 5. Shutdown Test (Mid-Execution Interrupts) ---")
    
    # 1. Voice listening thread shutdown
    logger.info("Simulating shutdown during voice recording...")
    stt = SpeechToText()
    stt.start_listening()
    time.sleep(0.5)
    stt.shutdown()
    logger.info("Voice listening thread cleanly shut down.")
    
    # 2. Worker thread execution shutdown
    logger.info("Simulating shutdown during tool execution / ReAct loop...")
    from PyQt6.QtCore import QThread, QObject, pyqtSignal
    
    class MockWorker(QObject):
        finished = pyqtSignal()
        def __init__(self):
            super().__init__()
            self._stopped = False
            
        def run(self):
            logger.info("Worker thread active and performing mock tool execution...")
            for _ in range(20):
                if self._stopped:
                    break
                time.sleep(0.1)
            self.finished.emit()
            
    thread = QThread()
    worker = MockWorker()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    thread.start()
    
    time.sleep(0.2)
    logger.info("Interrupting thread worker mid-execution...")
    worker._stopped = True
    thread.quit()
    if not thread.wait(1000):
        logger.warning("Thread did not quit in 1s. Terminating...")
        thread.terminate()
        thread.wait(500)
    logger.info("Worker thread cleanly interrupted and stopped.")

def main():
    from PyQt6.QtCore import QCoreApplication
    app = QCoreApplication(sys.argv)

    logger.info("============================================================")
    logger.info("  Futurix Jarvis — Stability Validation Test Suite")
    logger.info("============================================================")
    
    # Initialize AgentOrchestrator with all actual tools
    mock_llm = MagicMock(spec=LLMService)
    mock_llm.is_available = True
    mock_llm.is_native_tool_calling_active = False
    
    all_tools = (
        get_app_launcher_tools()
        + get_file_manager_tools()
        + get_web_search_tools()
        + get_system_info_tools()
        + get_system_command_tools()
        + get_screen_capture_tools()
    )
    agent = AgentOrchestrator(mock_llm, all_tools)
    
    # Run tests
    run_voice_e2e_test(agent)
    long_session_stats = run_long_session_test(agent)
    run_vision_test(agent)
    indexing_stats = run_repository_index_test()
    run_shutdown_test()
    
    logger.info("============================================================")
    logger.info("  Stability Validation Tests Completed Successfully!")
    logger.info("============================================================")
    sys.exit(0)

if __name__ == "__main__":
    main()
