import sys
import os
import unittest
import json
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.llm_service import LLMService, check_model_tool_support
from llm.model_manager import ModelManager
from assistant.agent import AgentOrchestrator


class TestLLMCompatibilityAndProbe(unittest.TestCase):
    """Validate model tool calling checks and execution mode configurations."""

    def test_native_tool_model(self):
        """Verify tool support whitelist cache hits."""
        # Whitelisted models should return True immediately without hitting network
        self.assertTrue(check_model_tool_support("http://localhost:11434", "llama3.1"))
        self.assertTrue(check_model_tool_support("http://localhost:11434", "qwen2.5:7b"))

    def test_known_non_tool_models(self):
        """Verify non-tool blacklist cache hits."""
        # llama3 (3.0) and llava are blacklisted and should return False
        self.assertFalse(check_model_tool_support("http://localhost:11434", "llama3"))
        self.assertFalse(check_model_tool_support("http://localhost:11434", "llava"))

    @patch("httpx.post")
    def test_tool_probe_failures(self, mock_post):
        """Verify dynamic tool probe checks fail on 400 Bad Request."""
        # Mocking 400 error (unsupported tools)
        mock_post.return_value = MagicMock(status_code=400)
        self.assertFalse(check_model_tool_support("http://localhost:11434", "custom-unsupported-model"))

    @patch("httpx.post")
    def test_tool_probe_success(self, mock_post):
        """Verify dynamic tool probe checks succeed on 200 OK."""
        # Mocking 200 success (supports tools)
        mock_post.return_value = MagicMock(status_code=200)
        self.assertTrue(check_model_tool_support("http://localhost:11434", "custom-supported-model"))

    @patch("httpx.post")
    def test_tool_probe_network_error(self, mock_post):
        """Verify probe gracefully defaults to False on connection failures."""
        mock_post.side_effect = Exception("Connection refused")
        self.assertFalse(check_model_tool_support("http://localhost:11434", "custom-unknown-model"))

    @patch("llm.llm_service.check_model_tool_support")
    def test_auto_mode_selection(self, mock_check):
        """Verify NATIVE vs REACT execution mode configurations under AUTO/NATIVE/REACT."""
        mock_mgr = MagicMock(spec=ModelManager)
        mock_mgr.active_model = "llama3"
        mock_mgr._base_url = "http://localhost:11434"
        mock_mgr.check_health.return_value = True

        with patch("langchain_ollama.ChatOllama"):
            # 1. AUTO mode with probe failure -> REACT execution mode
            mock_check.return_value = False
            llm_auto_fail = LLMService(mock_mgr, tool_execution_mode="AUTO")
            self.assertFalse(llm_auto_fail.is_native_tool_calling_active)
            self.assertEqual(llm_auto_fail.execution_mode, "REACT")

            # 2. AUTO mode with probe success -> NATIVE execution mode
            mock_check.return_value = True
            llm_auto_success = LLMService(mock_mgr, tool_execution_mode="AUTO")
            self.assertTrue(llm_auto_success.is_native_tool_calling_active)
            self.assertEqual(llm_auto_success.execution_mode, "NATIVE")

            # 3. FORCE NATIVE mode -> NATIVE execution mode regardless of probe
            mock_check.return_value = False
            llm_native = LLMService(mock_mgr, tool_execution_mode="NATIVE")
            self.assertTrue(llm_native.is_native_tool_calling_active)
            self.assertEqual(llm_native.execution_mode, "NATIVE")

            # 4. FORCE REACT mode -> REACT execution mode regardless of probe
            mock_check.return_value = True
            llm_react = LLMService(mock_mgr, tool_execution_mode="REACT")
            self.assertFalse(llm_react.is_native_tool_calling_active)
            self.assertEqual(llm_react.execution_mode, "REACT")


class TestReActExecutionAndParsing(unittest.TestCase):
    """Validate the custom ReAct cycle, parsing tolerations, and runaway safety boundaries."""

    def setUp(self):
        self.mock_llm = MagicMock(spec=LLMService)
        self.mock_llm.is_available = True
        self.mock_llm.is_native_tool_calling_active = False

        # Register a mock tool
        self.mock_tool = MagicMock()
        self.mock_tool.name = "open_chrome"
        self.mock_tool.description = "Launch Google Chrome web browser."
        self.mock_tool.args = {}
        self.mock_tool.invoke.return_value = "Chrome launched successfully."

        self.agent = AgentOrchestrator(self.mock_llm)
        self.agent.register_tools([self.mock_tool])

    def test_malformed_action_blocks(self):
        """Assert parsing tolerance on different LLM formats and single quotes."""
        # Standard casing, empty JSON
        act, args = self.agent._parse_react_action("Thought: I need Chrome.\nAction: open_chrome\nAction Input: {}")
        self.assertEqual(act, "open_chrome")
        self.assertEqual(args, {})

        # Lowercase casing, spaces and bold stars
        act, args = self.agent._parse_react_action("**Action** : open_chrome\n**Action Input**: {'url': 'google.com'}")
        self.assertEqual(act, "open_chrome")
        self.assertEqual(args, {"url": "google.com"})

        # Markdown json code block
        act, args = self.agent._parse_react_action("ACTION: open_chrome\nACTION INPUT:\n```json\n{\"url\": \"http://example.com\"}\n```")
        self.assertEqual(act, "open_chrome")
        self.assertEqual(args, {"url": "http://example.com"})

        # Python dictionary representation (single quotes)
        act, args = self.agent._parse_react_action("Action: open_chrome\nAction Input: {'query': 'python tutorials'}")
        self.assertEqual(act, "open_chrome")
        self.assertEqual(args, {"query": "python tutorials"})

        # Tolerating plain text instead of JSON if tool expects query
        self.mock_tool.name = "search_google"
        self.mock_tool.args = {"query": {"type": "string", "description": "query"}}
        self.agent.register_tools([self.mock_tool])
        act, args = self.agent._parse_react_action("Action: search_google\nAction Input: space exploration breakthroughs")
        self.assertEqual(act, "search_google")
        self.assertEqual(args, {"query": "space exploration breakthroughs"})

    def test_parser_fallbacks(self):
        """Assert parsing fallbacks work when model doesn't emit Action/Action Input/Final Answer, or emits None."""
        # Action: None rejection
        act, args = self.agent._parse_react_action("Thought: No further tools.\nAction: None")
        self.assertIsNone(act)
        self.assertIsNone(args)
        
        # Tool name mentioned in plain text
        act, args = self.agent._parse_react_action("I think I should open the chrome using open_chrome.")
        self.assertEqual(act, "open_chrome")
        self.assertEqual(args, {})
        
        # Tool name mentioned with key-value argument extraction
        self.mock_tool.name = "open_file_explorer"
        self.mock_tool.args = {"path": {"type": "string"}}
        self.agent.register_tools([self.mock_tool])
        act, args = self.agent._parse_react_action("Let's call open_file_explorer with path='C:\\Users'")
        self.assertEqual(act, "open_file_explorer")
        self.assertEqual(args, {"path": "C:\\Users"})

    def test_deterministic_command_router(self):
        """Assert direct commands execute directly without LLM reasoning."""
        self.mock_tool.name = "open_chrome"
        self.mock_tool.invoke.return_value = "Chrome launched successfully."
        self.agent.register_tools([self.mock_tool])
        
        response = self.agent.run("open chrome")
        self.assertEqual(response, "Chrome launched successfully.")
        self.assertEqual(self.mock_tool.invoke.call_count, 1)
        self.mock_llm.chat.assert_not_called()

    def test_open_chrome_react(self):
        """Verify complete execution flow under ReAct fallback loop."""
        # 1st loop: Model asks to run open_chrome
        # 2nd loop: Model returns Final Answer
        self.mock_llm.chat.side_effect = [
            "Thought: User wants to open Chrome. I'll launch it.\nAction: open_chrome\nAction Input: {}",
            "Thought: The tool executed and Chrome is active. I will inform the user.\nFinal Answer: Chrome has been opened successfully."
        ]

        response = self.agent.run("please open the web browser")
        self.assertEqual(response, "Chrome has been opened successfully.")
        self.assertEqual(self.mock_tool.invoke.call_count, 1)

    def test_maximum_step_termination(self):
        """Verify agent gracefully aborts when exceeding max step thresholds."""
        # Always output a tool action, preventing natural resolution
        self.mock_llm.chat.return_value = "Thought: Run Chrome.\nAction: open_chrome\nAction Input: {}"
        
        # Override step count limit to speed up test execution
        self.agent.MAX_REACT_STEPS = 3

        response, tool_execs = self.agent._execute_react_loop("Loop prompt")
        self.assertIn("limit of 3 steps exceeded", response.lower())
        self.assertEqual(len(tool_execs), 3)

    def test_tool_error_recovery(self):
        """Verify exceptions thrown by tools are caught and fed back to LLM context."""
        self.mock_tool.invoke.side_effect = Exception("Process not found")

        self.mock_llm.chat.side_effect = [
            "Thought: Launch Chrome.\nAction: open_chrome\nAction Input: {}",
            "Thought: Chrome execution failed. I will tell the user.\nFinal Answer: I was unable to open Chrome: Process not found."
        ]

        response = self.agent.run("please open the web browser")
        self.assertIn("unable to open Chrome", response)
        
        # Verify call arguments to llm chat contains the tool error output
        history_msgs = self.mock_llm.chat.call_args_list[1][0][0]
        error_msg = history_msgs[-1]["content"]
        self.assertIn("Observation: ❌ Tool 'open_chrome' failed: Process not found", error_msg)

    def test_intent_pattern_router(self):
        """Assert direct commands execute directly without LLM reasoning using intent patterns."""
        self.mock_tool.name = "get_battery_status"
        self.mock_tool.invoke.return_value = "Battery status returned."
        self.agent.register_tools([self.mock_tool])

        test_queries = [
            "what's the battery percentage?",
            "how much battery is left?",
            "check battery",
            "show battery status"
        ]

        for query in test_queries:
            response = self.agent.run(query)
            self.assertEqual(response, "Battery status returned.")

        # Should NOT hit LLM chat
        self.mock_llm.chat.assert_not_called()
