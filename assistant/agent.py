"""
Futurix Jarvis — Agent Orchestrator.

Implements the ReAct (Reason + Act) loop: the LLM decides whether a
request needs a tool, executes the tool, feeds the result back, and
generates a final natural-language answer.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from llm.llm_service import LLMService

logger = logging.getLogger(__name__)


REACT_AGENT_PROMPT_TEMPLATE = """You are Jarvis, an advanced AI assistant created by Futurix.
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

You operate in a ReAct loop (Reason + Act).
For any request, you must decide if you need to use a tool to fulfill it.

You have access to the following tools:
{tool_descriptions}

To use a tool, you MUST use the exact following format:
Thought: <your reasoning about why you need this tool and what to do next>
Action: <the tool name, must be one of [{tool_names}]>
Action Input: <the JSON formatted input arguments for the tool, e.g., {{"query": "search term"}} or {{}} if no arguments>

After you output the Action and Action Input, the system will execute the tool and return the output in the format:
Observation: <the tool output>

If you do not need to use a tool, or you have collected all observations and are ready to provide a final response to the user, use this format:
Thought: <your reasoning why the task is finished>
Final Answer: <your final response to the user in markdown format>

SAFETY RULES:
- NEVER delete files without explicit user confirmation.
- NEVER shut down or restart the system without explicit user confirmation.
- NEVER execute potentially destructive commands without confirmation.
- Always explain what a command will do before executing it.

Remember:
1. Every Action MUST be followed by Action Input.
2. Do NOT output anything after Action Input. Wait for the Observation.
3. If you have the tool result, continue with a new Thought and then either another Action or a Final Answer.
"""


class AgentOrchestrator:
    """Orchestrates tool-calling in a ReAct loop.

    The agent:
    1. Receives user input + conversation context.
    2. Asks the LLM whether a tool is needed.
    3. If yes, executes the tool and feeds the result back.
    4. Repeats until the LLM produces a final text answer.

    Usage::

        agent = AgentOrchestrator(llm_service, tools)
        response = agent.run("Open Chrome and search for Python tutorials")
    """

    MAX_ITERATIONS = 5  # Safety limit to prevent infinite tool loops
    MAX_REACT_STEPS = 10  # ReAct safety steps limit

    def __init__(
        self,
        llm_service: LLMService,
        tools: Optional[list[Any]] = None,
    ) -> None:
        self._llm = llm_service
        self._tools: dict[str, Any] = {}
        self._tool_list: list[Any] = []

        if tools:
            self.register_tools(tools)

    # ── Tool registration ────────────────────────────────────────────────

    def register_tools(self, tools: list[Any]) -> None:
        """Register tools for the agent to use.

        Args:
            tools: List of LangChain ``@tool``-decorated functions.
        """
        self._tool_list = tools
        self._tools = {t.name: t for t in tools}
        self._llm.bind_tools(tools)
        logger.info(
            "Agent registered %d tools: %s",
            len(tools),
            ", ".join(self._tools.keys()),
        )

    # ── Main execution loop ──────────────────────────────────────────────

    def run(
        self,
        user_message: str,
        context: Optional[list[dict[str, str]]] = None,
    ) -> str:
        """Execute the full agent loop for a user request.

        Args:
            user_message: The user's input text.
            context: Optional conversation history (list of {role, content} dicts).

        Returns:
            The agent's final text response.
        """
        if not self._llm.is_available:
            # Try offline tool execution via keyword matching
            return self._offline_dispatch(user_message)

        if not self._llm.is_native_tool_calling_active:
            final_ans, _ = self._execute_react_loop(user_message, context)
            return final_ans

        messages = list(context or [])
        messages.append({"role": "user", "content": user_message})

        for iteration in range(self.MAX_ITERATIONS):
            logger.debug("Agent iteration %d/%d", iteration + 1, self.MAX_ITERATIONS)

            response = self._llm.invoke_with_tools(messages)
            if response is None:
                return self._llm._offline_response()

            # Check if the LLM wants to call a tool
            tool_calls = getattr(response, "tool_calls", None)

            if not tool_calls:
                # No tool call — return the text response
                content = getattr(response, "content", "")
                return content or "I processed your request."

            # Execute each tool call
            tool_results = []
            for tool_call in tool_calls:
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("args", {})
                tool_id = tool_call.get("id", "")

                logger.info("Executing tool: %s(%s)", tool_name, tool_args)
                result = self._execute_tool(tool_name, tool_args)
                tool_results.append({
                    "tool_call_id": tool_id,
                    "name": tool_name,
                    "result": result,
                })

            # Append the assistant's tool-call message and tool results
            messages.append({
                "role": "assistant",
                "content": getattr(response, "content", "") or "",
            })

            # Add tool results as a system/tool message
            results_text = "\n\n".join(
                f"**Tool `{r['name']}`:**\n{r['result']}" for r in tool_results
            )
            messages.append({
                "role": "user",
                "content": f"[Tool Results]\n{results_text}\n\nPlease provide a natural response based on these results.",
            })

        # Exhausted iterations
        logger.warning("Agent reached max iterations (%d)", self.MAX_ITERATIONS)
        return "I've completed the available actions. Let me know if you need anything else."

    # ── Streaming execution ──────────────────────────────────────────────

    def run_streaming(
        self,
        user_message: str,
        context: Optional[list[dict[str, str]]] = None,
    ) -> tuple[str, list[dict]]:
        """Execute the agent loop and return both the response and tool calls made.

        This version is used by the controller for richer GUI feedback.

        Args:
            user_message: The user's input text.
            context: Optional conversation history.

        Returns:
            Tuple of (final_response, list_of_tool_executions).
        """
        tool_executions = []

        if not self._llm.is_available:
            response = self._offline_dispatch(user_message)
            return response, tool_executions

        if not self._llm.is_native_tool_calling_active:
            return self._execute_react_loop(user_message, context)

        messages = list(context or [])
        messages.append({"role": "user", "content": user_message})

        for iteration in range(self.MAX_ITERATIONS):
            response = self._llm.invoke_with_tools(messages)
            if response is None:
                return self._llm._offline_response(), tool_executions

            tool_calls = getattr(response, "tool_calls", None)

            if not tool_calls:
                content = getattr(response, "content", "")
                return content or "Done.", tool_executions

            for tool_call in tool_calls:
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("args", {})
                result = self._execute_tool(tool_name, tool_args)

                tool_executions.append({
                    "name": tool_name,
                    "args": tool_args,
                    "result": result,
                })

            # Build follow-up messages
            messages.append({
                "role": "assistant",
                "content": getattr(response, "content", "") or "",
            })
            results_text = "\n\n".join(
                f"**Tool `{r['name']}`:**\n{r['result']}" for r in tool_executions
            )
            messages.append({
                "role": "user",
                "content": f"[Tool Results]\n{results_text}\n\nProvide a natural response.",
            })

        return "Actions completed.", tool_executions

    # ── Tool execution ───────────────────────────────────────────────────

    def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """Execute a single tool by name.

        Args:
            tool_name: The registered tool name.
            tool_args: Keyword arguments for the tool.

        Returns:
            The tool's output string.
        """
        tool_func = self._tools.get(tool_name)
        if tool_func is None:
            msg = f"Unknown tool: {tool_name}"
            logger.error(msg)
            return f"❌ {msg}"

        try:
            result = tool_func.invoke(tool_args)
            logger.info("Tool %s returned: %s", tool_name, str(result)[:200])
            return str(result)
        except Exception as exc:
            msg = f"Tool '{tool_name}' failed: {exc}"
            logger.exception(msg)
            return f"❌ {msg}"

    # ── Offline fallback ─────────────────────────────────────────────────

    def _offline_dispatch(self, message: str) -> str:
        """Try to match a user request to a tool without the LLM.

        Uses simple keyword matching as a fallback when Ollama is offline.

        Args:
            message: The user's input text.

        Returns:
            Tool output or an offline message.
        """
        msg_lower = message.lower()

        # Keyword → tool name mapping
        keyword_map = {
            ("open chrome", "launch chrome"): "open_chrome",
            ("open vscode", "open vs code", "launch vscode"): "open_vscode",
            ("open calculator", "launch calculator", "open calc"): "open_calculator",
            ("open explorer", "file explorer"): "open_file_explorer",
            ("open notepad", "launch notepad"): "open_notepad",
            ("battery",): "get_battery_status",
            ("cpu", "ram", "memory", "resource"): "get_resource_usage",
            ("system info", "system information"): "get_system_info",
            ("search google",): "search_google",
            ("search youtube",): "search_youtube",
            ("screenshot", "capture screen"): "capture_screenshot",
            ("lock screen", "lock computer"): "lock_screen",
        }

        for keywords, tool_name in keyword_map.items():
            if any(kw in msg_lower for kw in keywords):
                tool_func = self._tools.get(tool_name)
                if tool_func:
                    try:
                        # Extract query for search tools
                        if tool_name in ("search_google", "search_youtube"):
                            for prefix in ("search google for ", "search youtube for ",
                                           "search google ", "search youtube "):
                                if msg_lower.startswith(prefix):
                                    query = message[len(prefix):].strip()
                                    return str(tool_func.invoke({"query": query}))
                            return str(tool_func.invoke({"query": message}))
                        return str(tool_func.invoke({}))
                    except Exception as exc:
                        return f"❌ Tool error: {exc}"

        return self._llm._offline_response()

    # ── ReAct prompting fallback execution ───────────────────────────────

    def _deterministic_route(self, message: str) -> Optional[tuple[str, list[dict]]]:
        """Check if the user message matches a direct command and execute it directly.

        Returns a tuple of (final_response, tool_executions) if matched, else None.
        """
        import re

        # Clean message: lowercase, remove punctuation, compress spaces
        cleaned = re.sub(r"[?!.,;:\-\`\'\"]", "", message.lower()).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)

        # Intent patterns configuration
        intent_patterns = [
            # Battery Intent
            {
                "intent": "battery",
                "tool": ("get_battery_status", {}),
                "patterns": [
                    r"\bbattery\b",
                    r"\bpower\s+status\b",
                    r"\bpower\s+remaining\b"
                ]
            },
            # CPU / Resource Intent
            {
                "intent": "resource",
                "tool": ("get_resource_usage", {}),
                "patterns": [
                    r"\bcpu\b",
                    r"\bresource\s+usage\b",
                    r"\bsystem\s+resources\b",
                    r"\bram\s+usage\b",
                    r"\bmemory\s+usage\b",
                    r"\bdisk\s+usage\b"
                ]
            },
            # Chrome Intent
            {
                "intent": "chrome",
                "tool": ("open_chrome", {}),
                "patterns": [
                    r"\b(?:open|launch|start)\s+chrome\b",
                    r"\b(?:open|launch|start)\s+google\s+chrome\b"
                ]
            },
            # Calculator Intent
            {
                "intent": "calculator",
                "tool": ("open_calculator", {}),
                "patterns": [
                    r"\b(?:open|launch|start)\s+calc(?:ulator)?\b"
                ]
            },
            # VS Code Intent
            {
                "intent": "vscode",
                "tool": ("open_vscode", {}),
                "patterns": [
                    r"\b(?:open|launch|start)\s+vs\s*code\b",
                    r"\b(?:open|launch|start)\s+visual\s+studio\s+code\b"
                ]
            },
            # Notepad Intent
            {
                "intent": "notepad",
                "tool": ("open_notepad", {}),
                "patterns": [
                    r"\b(?:open|launch|start)\s+notepad\b"
                ]
            },
            # File Explorer Intent
            {
                "intent": "explorer",
                "tool": ("open_file_explorer", {}),
                "patterns": [
                    r"\b(?:open|launch|start)\s+explorer\b",
                    r"\b(?:open|launch|start)\s+file\s+explorer\b"
                ]
            }
        ]

        for ip in intent_patterns:
            tool_name, tool_args = ip["tool"]
            for pattern in ip["patterns"]:
                if re.search(pattern, cleaned):
                    tool_func = self._tools.get(tool_name)
                    if tool_func:
                        logger.info(
                            "Deterministic Command Router matched intent '%s' (pattern '%s'): '%s' -> tool '%s'",
                            ip["intent"], pattern, message, tool_name
                        )
                        result = self._execute_tool(tool_name, tool_args)
                        return result, [{
                            "name": tool_name,
                            "args": tool_args,
                            "result": result
                        }]

        return None

    def _execute_react_loop(
        self,
        user_message: str,
        context: Optional[list[dict[str, str]]] = None,
    ) -> tuple[str, list[dict]]:
        """Run a text-based ReAct loop for models that don't support native tool calling."""
        import json
        
        # Deterministic route check before entering ReAct loop
        routed = self._deterministic_route(user_message)
        if routed:
            return routed

        messages = list(context or [])
        messages.append({"role": "user", "content": user_message})

        tool_executions = []

        tool_descs = []
        for t in self._tool_list:
            args_info = []
            for arg_name, arg_data in t.args.items():
                arg_type = arg_data.get("type", "any")
                arg_desc = arg_data.get("description", "")
                args_info.append(f"{arg_name} ({arg_type}): {arg_desc}")
            args_str = ", ".join(args_info) if args_info else "None"
            tool_descs.append(f"- **{t.name}**: {t.description}\n  Arguments: {args_str}")

        tool_descriptions_str = "\n".join(tool_descs)
        tool_names_str = ", ".join(self._tools.keys())

        # Formulate ReAct system prompt
        react_sys_prompt = REACT_AGENT_PROMPT_TEMPLATE.format(
            tool_descriptions=tool_descriptions_str,
            tool_names=tool_names_str
        )

        for step in range(self.MAX_REACT_STEPS):
            logger.info("=" * 60)
            logger.info("ReAct Step %d/%d", step + 1, self.MAX_REACT_STEPS)
            logger.info("Prompt Sent to LLM:\n%s", json.dumps(messages, indent=2))
            logger.info("=" * 60)

            response_text = self._llm.chat(list(messages), system_prompt=react_sys_prompt)
            
            logger.info("=" * 60)
            logger.info("RAW LLM RESPONSE: %s", response_text)
            logger.info("=" * 60)

            if not response_text or response_text.startswith("I encountered an error"):
                logger.error("LLM invoke error or empty response: %s", response_text)
                return response_text or "Failed to query the LLM.", tool_executions

            # Append the model's generation (thought + action if any)
            messages.append({"role": "assistant", "content": response_text})

            action, action_input = self._parse_react_action(response_text)
            logger.info("Parsed action: %s", action)
            logger.info("Parsed action input: %s", action_input)

            if action:
                logger.info("Executing ReAct action: %s with input: %s", action, action_input)
                result = self._execute_tool(action, action_input or {})
                logger.info("Tool execution result: %s", result)
                
                tool_executions.append({
                    "name": action,
                    "args": action_input or {},
                    "result": result,
                })

                # Append the observation
                messages.append({
                    "role": "user",
                    "content": f"Observation: {result}"
                })
            else:
                # Fallback: No action matches, check if we should treat it as conversational final answer
                final_answer = self._extract_final_answer(response_text)
                logger.info("Final answer: %s", final_answer)
                return final_answer, tool_executions
        else:
            logger.warning("ReAct agent exceeded max steps (%d)", self.MAX_REACT_STEPS)
            return (
                f"❌ Max execution limit of {self.MAX_REACT_STEPS} steps exceeded. Loop aborted to prevent runaway automation.",
                tool_executions
            )

    def _extract_json(self, text: str) -> Optional[dict]:
        """Extract a JSON object from text if present."""
        import json
        import re
        # Try to find balanced braces content
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            candidate = text[first_brace:last_brace+1]
            try:
                val = json.loads(candidate)
                if isinstance(val, dict):
                    return val
            except Exception:
                pass

        # Try to find any match of { ... }
        matches = re.findall(r"\{.*?\}", text, re.DOTALL)
        for m in matches:
            try:
                val = json.loads(m)
                if isinstance(val, dict):
                    return val
            except Exception:
                # Try single to double quote replacement
                try:
                    val = json.loads(m.replace("'", '"'))
                    if isinstance(val, dict):
                        return val
                except Exception:
                    pass
        return None

    def _parse_react_action(self, text: str) -> tuple[Optional[str], Optional[dict]]:
        """Parse the Action and Action Input from the LLM text response.

        Tolerates formatting variations produced by local models.
        """
        import re
        import json
        
        # 1. Search for Action tag (tolerating bold, spacing, brackets, quotes)
        # E.g., Action: open_chrome, **Action**: "open_chrome", Action: [open_chrome]
        action_match = re.search(r"Action[\s_-]*\s*\*?\*?\s*:\s*\*?\*?[\"'\[`]?([a-zA-Z0-9_-]+)[\"'\]`]?", text, re.IGNORECASE)
        
        if not action_match:
            # Fallback: check if model mentioned any tool name in text without formal Action prefix
            for tool_name in self._tools.keys():
                pattern = r"\b" + re.escape(tool_name) + r"\b"
                if re.search(pattern, text, re.IGNORECASE):
                    logger.warning("Model mentioned tool '%s' without Action prefix. Falling back to it.", tool_name)
                    parsed_json = self._extract_json(text)
                    if parsed_json is not None:
                        return tool_name, parsed_json
                    
                    tool_func = self._tools.get(tool_name)
                    if tool_func:
                        args_keys = list(tool_func.args.keys()) if hasattr(tool_func, "args") else []
                        if not args_keys:
                            return tool_name, {}
                        extracted_args = {}
                        for key in args_keys:
                            kv_pattern = r"\b" + re.escape(key) + r"\b\s*[:=]\s*[\"']?([^\"'\n]+)[\"']?"
                            kv_match = re.search(kv_pattern, text, re.IGNORECASE)
                            if kv_match:
                                extracted_args[key] = kv_match.group(1).strip()
                        if extracted_args:
                            return tool_name, extracted_args
                        if len(args_keys) == 1:
                            quoted_match = re.search(r"\"([^\"]+)\"|'([^']+)'", text)
                            if quoted_match:
                                val = quoted_match.group(1) or quoted_match.group(2)
                                return tool_name, {args_keys[0]: val}
                            return tool_name, {args_keys[0]: text.strip()}
                    return tool_name, {}
            return None, None

        action = action_match.group(1).strip()
        if action.lower() == "none":
            logger.info("Parsed action is 'None'. Rejecting as no-action.")
            return None, None

        # 2. Search for Action Input tag (tolerating spaces, underscores, dashes, bold, etc.)
        action_input_match = re.search(r"Action[\s_-]*Input\s*\*?\*?\s*:\s*(.*)", text, re.IGNORECASE | re.DOTALL)
        if not action_input_match:
            parsed_json = self._extract_json(text)
            if parsed_json is not None:
                return action, parsed_json
            
            tool_func = self._tools.get(action)
            if tool_func:
                args_keys = list(tool_func.args.keys()) if hasattr(tool_func, "args") else []
                if not args_keys:
                    return action, {}
                extracted_args = {}
                for key in args_keys:
                    kv_pattern = r"\b" + re.escape(key) + r"\b\s*[:=]\s*[\"']?([^\"'\n]+)[\"']?"
                    kv_match = re.search(kv_pattern, text, re.IGNORECASE)
                    if kv_match:
                        extracted_args[key] = kv_match.group(1).strip()
                if extracted_args:
                    return action, extracted_args
                if len(args_keys) == 1:
                    quoted_match = re.search(r"\"([^\"]+)\"|'([^']+)'", text)
                    if quoted_match:
                        val = quoted_match.group(1) or quoted_match.group(2)
                        return action, {args_keys[0]: val}
                    return action, {args_keys[0]: text.strip()}
            return action, {}

        input_str = action_input_match.group(1).strip()

        # Strip off any hallucinated "Observation:" or subsequent blocks
        for delimiter in ["Observation:", "Thought:", "Final Answer:"]:
            if delimiter in input_str:
                input_str = input_str.split(delimiter)[0].strip()

        # Strip markdown code blocks wrapping JSON
        if "```" in input_str:
            block_match = re.search(r"```(?:json)?\s*(.*?)\s*```", input_str, re.DOTALL)
            if block_match:
                input_str = block_match.group(1).strip()

        if not input_str or input_str == "{}" or input_str == "None":
            return action, {}

        # Safe single-quote replacement for JSON loading
        cleaned_input = input_str
        if "'" in cleaned_input and '"' not in cleaned_input:
            cleaned_input = cleaned_input.replace("'", '"')

        try:
            return action, json.loads(cleaned_input)
        except Exception:
            parsed_json = self._extract_json(cleaned_input)
            if parsed_json is not None:
                return action, parsed_json

            tool_func = self._tools.get(action)
            if tool_func:
                args_keys = list(tool_func.args.keys()) if hasattr(tool_func, "args") else []
                if len(args_keys) == 0:
                    return action, {}
                if len(args_keys) == 1:
                    arg_name = args_keys[0]
                    return action, {arg_name: input_str}

                kv_match = re.match(r"([a-zA-Z0-9_-]+)\s*=\s*(.*)", input_str)
                if kv_match:
                    k, v = kv_match.group(1).strip(), kv_match.group(2).strip()
                    v = v.strip("\"'")
                    return action, {k: v}

            return action, {"query": input_str}

    def _extract_final_answer(self, text: str) -> str:
        """Extract the final answer text block, tolerating formatting variations."""
        import re
        match = re.search(r"Final\s+Answer\s*:\s*(.*)", text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()

        # Fallback: remove Thought/Action tags and return clean text
        cleaned = text
        cleaned = re.sub(r"Thought:\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"Action\s*:\s*.*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"Action Input\s*:\s*.*", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        return cleaned.strip()
