import sys
import os
import unittest
import shutil
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager
from vision.vision_provider import OllamaVisionProvider
from vision.vision_service import VisionService
from coding.workspace_index import WorkspaceIndexer
from memory.task_service import TaskService


class TestVisionSystem(unittest.TestCase):
    """Test vision provider, Ollama formatting, and offline graceful degradation."""

    @patch("httpx.post")
    @patch("httpx.get")
    def test_ollama_vision_provider_success(self, mock_get, mock_post):
        """Test successful vision request to Ollama."""
        # Mock tags endpoint for model availability checking
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "llava:latest"}]}
        )
        # Mock generate endpoint
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"response": "This is a screenshot of a code editor."}
        )

        provider = OllamaVisionProvider(model_name="llava")
        self.assertTrue(provider.is_available())

        # Create a temp mock image file
        temp_img = Path("temp_screenshot.png")
        temp_img.write_bytes(b"PNG-fake-image-bytes")

        try:
            res = provider.analyse_image(temp_img, "Describe this image.")
            self.assertIn("code editor", res)
            
            # Assert payload has correct keys
            called_json = mock_post.call_args[1]["json"]
            self.assertEqual(called_json["model"], "llava")
            self.assertEqual(called_json["prompt"], "Describe this image.")
            self.assertEqual(len(called_json["images"]), 1)
        finally:
            if temp_img.exists():
                temp_img.unlink()

    @patch("httpx.get")
    def test_vision_fallback_when_offline(self, mock_get):
        """Vision provider should return warning without crashing when offline."""
        mock_get.side_effect = Exception("Ollama server not running")

        provider = OllamaVisionProvider(model_name="llava")
        self.assertFalse(provider.is_available())

        temp_img = Path("temp_offline_screenshot.png")
        temp_img.write_bytes(b"dummy")

        try:
            # Offline provider should return diagnostic message
            res = provider.analyse_image(temp_img, "Check alignments.")
            self.assertIn("Visual analysis is currently unavailable", res)
            self.assertIn("Check alignments", res)
        finally:
            if temp_img.exists():
                temp_img.unlink()


class TestWorkspaceIntelligence(unittest.TestCase):
    """Test AST-based code indexing and repo summary generation."""

    def setUp(self):
        self.test_dir = Path(__file__).resolve().parent / "temp_workspace_test"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.test_dir / "test_jarvis.db"
        self.db = DatabaseManager(self.db_path)
        
        self.indexer = WorkspaceIndexer(self.db)

    def tearDown(self):
        self.db.close()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_ast_symbol_extraction(self):
        """Verify Python AST parser indexes classes, functions, and imports with correct lines/metadata."""
        # Create a mock python script
        py_code = (
            "import os\n"
            "from math import pi\n\n"
            "class DatabaseModel:\n"
            "    \"\"\"Model docstring.\"\"\"\n"
            "    def __init__(self, name: str) -> None:\n"
            "        self.name = name\n\n"
            "    def save(self) -> bool:\n"
            "        return True\n\n"
            "def global_helper(x):\n"
            "    return x * 2\n"
        )
        
        file_path = self.test_dir / "models.py"
        file_path.write_text(py_code, encoding="utf-8")

        # Run indexer
        stats = self.indexer.index_directory(self.test_dir)
        self.assertEqual(stats["files_indexed"], 1)

        # Check cached symbols in DB
        classes = self.db.search_code_symbols("DatabaseModel", "class")
        self.assertEqual(len(classes), 1)
        self.assertEqual(classes[0].file_path, "models.py")
        self.assertEqual(classes[0].line_number, 4)

        # Check class details
        cls_details = json.loads(classes[0].details)
        self.assertIn("Model docstring", cls_details["docstring"])

        # Check methods
        methods = self.db.search_code_symbols("save", "function")
        self.assertEqual(len(methods), 1)
        self.assertEqual(methods[0].parent_name, "DatabaseModel")
        
        # Check imports
        imports = self.db.search_code_symbols("os", "import")
        self.assertEqual(len(imports), 1)

    def test_repository_summary_metrics(self):
        """Verify language/framework detection, LOC counts, and manifest files."""
        # Setup files representing different frameworks/languages
        (self.test_dir / "src").mkdir(exist_ok=True)
        (self.test_dir / "src" / "index.js").write_text("console.log('React');", encoding="utf-8")
        (self.test_dir / "requirements.txt").write_text("fastapi==0.100.0\npytest", encoding="utf-8")
        (self.test_dir / "main.py").write_text("print('hello')\n# comment\n", encoding="utf-8")

        # Run indexer
        self.indexer.index_directory(self.test_dir)

        # Retrieve summary record
        record = self.db.get_repository_summary(str(self.test_dir))
        self.assertIsNotNone(record)
        
        self.assertEqual(record.total_files, 2)  # index.js and main.py
        self.assertEqual(record.total_lines, 3)  # 1 (js) + 2 (py)
        
        # Check detected info
        self.assertIn("Python", record.languages_detected)
        self.assertIn("JavaScript", record.languages_detected)
        self.assertIn("FastAPI", record.frameworks_detected)
        self.assertIn("requirements.txt", record.dependency_files)


class TestTaskMemory(unittest.TestCase):
    """Test task entities, priority tracking, nullable due dates, and persistence across restarts."""

    def setUp(self):
        self.test_dir = Path(__file__).resolve().parent / "temp_task_test"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.test_dir / "test_jarvis.db"
        
        self.db = DatabaseManager(self.db_path)
        self.service = TaskService(self.db)

    def tearDown(self):
        self.db.close()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_task_operations_and_filters(self):
        """Test Task creation, notes, linked files, and search filters."""
        # Create tasks of different priorities
        task1_id = self.service.add_task(
            title="Refactor voice Cancellation",
            description="ImprovePyAudio stream performance.",
            priority="high",
            due_date="2026-06-30"
        )
        task2_id = self.service.add_task(
            title="Update CSS themes",
            description="Add neon glassmorphic elements.",
            priority="low"
        )

        self.assertEqual(task1_id, 1)
        self.assertEqual(task2_id, 2)

        # Verify task details
        task1 = self.db.get_task(task1_id)
        self.assertEqual(task1.priority, "high")
        self.assertEqual(task1.due_date, "2026-06-30")

        task2 = self.db.get_task(task2_id)
        self.assertIsNone(task2.due_date)

        # Transition status
        self.service.update_status(task1_id, "in_progress", "Started audio profiling.")
        task1_updated = self.db.get_task(task1_id)
        self.assertEqual(task1_updated.status, "in_progress")

        # Confirm progress note is recorded
        notes = self.db.get_task_notes(task1_id)
        self.assertEqual(len(notes), 1)
        self.assertIn("Started audio profiling", notes[0].note)

        # Link files
        self.db.add_task_file(task1_id, "voice/speech_to_text.py")
        files = self.db.get_task_files(task1_id)
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].endswith("speech_to_text.py"))

        # Search filter
        search_res = self.db.get_tasks(search_query="voice")
        self.assertEqual(len(search_res), 1)
        self.assertEqual(search_res[0].id, task1_id)

    def test_task_persistence_across_restarts(self):
        """Confirm tasks, notes, and file relations survive database shutdowns."""
        # Create and link task data
        task_id = self.service.add_task(
            title="Task to survive database close",
            description="Check database WAL write serialization.",
            priority="medium",
            due_date="2026-12-25"
        )
        self.db.add_task_note(task_id, "Initial log note.")
        self.db.add_task_file(task_id, "main.py")

        # Close database connection
        self.db.close()

        # Re-instantiate database manager pointing to the same file
        new_db = DatabaseManager(self.db_path)
        
        # Verify persistence
        survived_task = new_db.get_task(task_id)
        self.assertIsNotNone(survived_task)
        self.assertEqual(survived_task.title, "Task to survive database close")
        self.assertEqual(survived_task.priority, "medium")
        self.assertEqual(survived_task.due_date, "2026-12-25")

        survived_notes = new_db.get_task_notes(task_id)
        self.assertEqual(len(survived_notes), 1)
        self.assertEqual(survived_notes[0].note, "Initial log note.")

        survived_files = new_db.get_task_files(task_id)
        self.assertEqual(len(survived_files), 1)
        self.assertTrue(survived_files[0].endswith("main.py"))

        new_db.close()


if __name__ == "__main__":
    unittest.main()
