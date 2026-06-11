import sys
import os
import logging

# Ensure project root is in sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.settings import get_settings
from utils.logger import setup_logging

# Initialise logging to stdout
setup_logging(level="INFO")
logger = logging.getLogger("test_cli")

from assistant.controller import AssistantController

def run_test():
    settings = get_settings()
    
    # We will override settings to force REACT mode to test the ReAct cycle
    os.environ["TOOL_EXECUTION_MODE"] = "REACT"
    # Ensure settings reload
    from config import settings as settings_mod
    settings_mod.reset_settings()
    settings = settings_mod.get_settings()
    
    logger.info("Initializing AssistantController in REACT mode...")
    controller = AssistantController(settings)
    
    # Check if LLM is online
    if not controller.is_llm_online:
        logger.warning("Ollama server is offline. The agent will run in rule-based offline mode.")
    else:
        logger.info("Ollama is ONLINE. Execution mode is: %s", controller._llm.execution_mode)

    commands = [
        "open chrome",
        "open calculator",
        "show cpu usage"
    ]
    
    # We will run the agent directly on these commands
    agent = controller._agent
    
    for cmd in commands:
        logger.info("\n" + "="*80)
        logger.info("TESTING COMMAND: '%s'", cmd)
        logger.info("="*80)
        
        # We run the agent synchronously
        response = agent.run(cmd)
        
        logger.info("RESPONSE RECEIVED:")
        logger.info(response)
        logger.info("="*80)

if __name__ == "__main__":
    run_test()
