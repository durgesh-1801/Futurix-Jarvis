import sys
import os
import logging

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from assistant.agent import AgentOrchestrator
from llm.llm_service import LLMService
from automation.app_launcher import get_app_launcher_tools
from automation.file_manager import get_file_manager_tools
from automation.web_search import get_web_search_tools
from automation.system_info import get_system_info_tools
from automation.system_commands import get_system_command_tools
from automation.screen_capture import get_screen_capture_tools
from unittest.mock import MagicMock

# Setup basic logging to see matched intents
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

# Create mock LLM Service
mock_llm = MagicMock(spec=LLMService)
mock_llm.is_available = True
mock_llm.is_native_tool_calling_active = False

# Setup Agent Orchestrator with actual tools
all_tools = (
    get_app_launcher_tools()
    + get_file_manager_tools()
    + get_web_search_tools()
    + get_system_info_tools()
    + get_system_command_tools()
    + get_screen_capture_tools()
)
agent = AgentOrchestrator(mock_llm, all_tools)

# Define test queries
test_queries = [
    # Battery Intent
    "what's the battery percentage",
    "how much battery is left",
    "check battery",
    "show battery status",
    # CPU Intent
    "show cpu usage",
    "what is my cpu usage?",
    "system resources",
    # App Intent
    "open chrome",
    "start vscode",
    "launch calculator"
]

print("=== VERIFYING ROUTER INTENTS ===")
for query in test_queries:
    print(f"\nQuery: '{query}'")
    # Call _deterministic_route directly
    route_result = agent._deterministic_route(query)
    if route_result:
        res_text, executions = route_result
        print(f"Matched Tool: {executions[0]['name']}")
        print(f"Tool Argument: {executions[0]['args']}")
        print(f"Tool Output Preview: {str(res_text).splitlines()[0]}")
    else:
        print("No match (fallback to LLM)")

print("\n=== VERIFICATION COMPLETE ===")
