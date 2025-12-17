"""Turn processor for handling individual REPL turns with tool calling."""

from typing import Optional, List, Dict, Any
import re
import logging
import time
import json

from conversation import ConversationManager
from llm_client import LLMClient
from tool_executor import ToolExecutor
from tool_registry import ToolRegistry, SPECIALIST_TOOLS

logger = logging.getLogger(__name__)


class TurnProcessor:
    """Processes a single REPL turn, handling tool calls and responses."""

    def __init__(
        self,
        conversation: ConversationManager,
        llm_client: LLMClient,
        tool_executor: ToolExecutor,
        tool_registry: ToolRegistry,
        ui=None,
    ):
        self.conversation = conversation
        self.llm_client = llm_client
        self.tool_executor = tool_executor
        self.tool_registry = tool_registry
        self.ui = ui  # Optional UI for feedback

        # Track last specialist tool output for reference resolution
        self.last_specialist_output: Optional[str] = None

        # Track recent tool outputs for auto-context injection
        # Store tuples of (tool_name, result)
        self.recent_tool_outputs: List[tuple[str, str]] = []
        self.max_context_tools = 3  # Keep last 3 tool results for context

    def _extract_json_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON tool call from text output (for models that output JSON as text).

        Returns:
            Dict with 'tool' and 'arguments' if found, None otherwise
        """
        # Format 1: XML-style tool call: <tool_call> {"name": "...", "arguments": {...}} </tool_call>
        xml_pattern = r'<tool_call>\s*(\{.+?\})\s*</tool_call>'
        match = re.search(xml_pattern, text, re.DOTALL)
        if match:
            try:
                json_str = match.group(1)
                # Handle nested braces by finding the matching closing brace
                brace_count = 0
                end_pos = 0
                for i, char in enumerate(json_str):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_pos = i + 1
                            break

                if end_pos > 0:
                    json_str = json_str[:end_pos]

                data = json.loads(json_str)
                tool_name = data.get("name")
                arguments = data.get("arguments", {})
                if tool_name:
                    # Convert "prompt" to appropriate parameter name
                    if "prompt" in arguments and tool_name == "use_reasoning_model":
                        arguments["task"] = arguments.pop("prompt")
                    logger.info(f"Extracted XML tool call: {tool_name}")
                    return {"tool": tool_name, "arguments": arguments}
            except (json.JSONDecodeError, IndexError) as e:
                logger.warning(f"Failed to parse XML tool call: {e}")
                pass

        # Format 2: function_call: tool_name("arg") or function_call: tool_name()
        # First try with arguments
        func_call_pattern = r'function_call:\s*(\w+)\s*\("([^"]+)"\)'
        match = re.search(func_call_pattern, text)
        if match:
            tool_name = match.group(1)
            query = match.group(2)
            # Determine parameter name based on tool
            param_name = "query" if ("search" in tool_name or "energy" in tool_name or "analyst" in tool_name) else "code_context" if "code" in tool_name else "task"
            return {"tool": tool_name, "arguments": {param_name: query}}

        # Try without arguments (empty parentheses)
        func_call_no_args_pattern = r'function_call:\s*(\w+)\s*\(\s*\)'
        match = re.search(func_call_no_args_pattern, text)
        if match:
            tool_name = match.group(1)
            return {"tool": tool_name, "arguments": {}}

        # Format 3: JSON object with tool/action/name
        json_pattern = r'\{[^{}]*"(?:tool|action|name)"[^{}]*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)

        for match in matches:
            try:
                data = json.loads(match)
                # Check for different JSON formats models might use
                if "tool" in data or "action" in data or "name" in data:
                    tool_name = data.get("tool") or data.get("action") or data.get("name")
                    # Extract arguments (everything except the tool name key)
                    arguments = {k: v for k, v in data.items() if k not in ["tool", "action", "name"]}
                    return {"tool": tool_name, "arguments": arguments}
            except json.JSONDecodeError:
                continue

        return None

    def _resolve_references(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve reference pronouns in tool arguments to actual content.

        If write_file is called with content containing "this", "that", "the plan", etc.,
        replace with last_specialist_output.

        Args:
            tool_name: Name of the tool being called
            arguments: Tool arguments dict

        Returns:
            Updated arguments dict with references resolved
        """
        # Only handle write_file for now
        if tool_name != "write_file":
            return arguments

        # Check if content parameter exists and contains references
        content = arguments.get("content", "")

        # Skip if content is already long (likely not a reference)
        if len(content) > 100:
            return arguments

        # Reference patterns to detect
        reference_patterns = [
            r'\bthis\b',
            r'\bthat\b',
            r'\bthe plan\b',
            r'\bthe outline\b',
            r'\bthe analysis\b',
            r'\bthe report\b',
            r'\babove\b',
            r'\bprevious\b',
            r'\bjust generated\b',
            r'\bjust provided\b',
        ]

        # Check if content contains any reference pattern
        has_reference = any(re.search(pattern, content, re.IGNORECASE) for pattern in reference_patterns)

        if has_reference and self.last_specialist_output:
            logger.info(f"Resolving reference in write_file: '{content}' -> using last specialist output ({len(self.last_specialist_output)} chars)")
            # Replace content with last specialist output
            arguments = arguments.copy()
            arguments["content"] = self.last_specialist_output

        return arguments

    def _should_use_intent_detection(self, user_input: str) -> bool:
        """
        Determine if we should use intent detection for this input.

        Args:
            user_input: The user's request

        Returns:
            True if intent detection should be used
        """
        # Always use intent detection if we have previous specialist output (user might reference it)
        if self.last_specialist_output:
            return True

        # Check for file operation keywords
        file_keywords = [
            r'\bwrite\b.*\bfile\b',
            r'\bsave\b.*\bto\b',
            r'\bcreate\b.*\bfile\b',
            r'\b\.py\b',
            r'\b\.md\b',
            r'\b\.txt\b',
            r'\b\.json\b',
            r'\bwrite\b.*\bto\b',
            r'\bput\b.*\bin\b',
            r'\bstore\b.*\bin\b',
        ]

        for pattern in file_keywords:
            if re.search(pattern, user_input, re.IGNORECASE):
                logger.info(f"File operation keyword detected: {pattern}")
                return True

        return False

    def _execute_forced_tool_call(self, tool_name: str, user_input: str) -> Optional[str]:
        """
        Execute a forced tool call based on intent detection.

        Args:
            tool_name: The tool to execute
            user_input: The user's input

        Returns:
            Tool result, or None if unable to execute
        """
        logger.info(f"Forcing tool call: {tool_name}")

        if tool_name == "write_file":
            # Extract filename from user input
            # Patterns: "write to X", "save to X", "create X"
            filename_patterns = [
                r'(?:write|save|create|put|store).*?(?:to|as|in)\s+([^\s]+\.(?:py|md|txt|json|yaml|yml|sh|js|ts|html|css|ini|conf|cfg))',
                r'(?:file|the)?\s+([^\s]+\.(?:py|md|txt|json|yaml|yml|sh|js|ts|html|css|ini|conf|cfg))',
            ]

            filename = None
            for pattern in filename_patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    filename = match.group(1)
                    break

            if not filename:
                logger.warning("Could not extract filename from user input")
                return None

            # Use last specialist output as content
            if not self.last_specialist_output:
                logger.warning("No specialist output available for write_file")
                return None

            logger.info(f"Forcing write_file: {filename} ({len(self.last_specialist_output)} chars)")

            # Execute write_file directly
            arguments = {
                "path": filename,
                "content": self.last_specialist_output
            }

            result = self.tool_executor.execute(tool_name, arguments)
            return result

        elif tool_name == "read_file":
            # Extract filename from user input
            # Patterns: "read X", "show X", "view X", "content of X"
            filename_patterns = [
                r'(?:read|show|view|display|see|open|cat).*?(?:file|the)?\s+([^\s]+\.(?:py|md|txt|json|yaml|yml|sh|js|ts|html|css|ini|conf|cfg))',
                r'(?:content|contents)\s+(?:of|from)\s+(?:file|the)?\s*([^\s]+\.(?:py|md|txt|json|yaml|yml|sh|js|ts|html|css|ini|conf|cfg))',
                r'(?:file|the)\s+([^\s]+\.(?:py|md|txt|json|yaml|yml|sh|js|ts|html|css|ini|conf|cfg))',
            ]

            filename = None
            for pattern in filename_patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    filename = match.group(1)
                    break

            if not filename:
                logger.warning("Could not extract filename from user input for read_file")
                return None

            logger.info(f"Forcing read_file: {filename}")

            # Execute read_file directly
            arguments = {
                "path": filename
            }

            result = self.tool_executor.execute(tool_name, arguments)
            return result

        elif tool_name == "list_files":
            # Extract directory path from user input
            # Patterns: "list files in X", "show files in X", "ls X"
            dir_patterns = [
                r'(?:list|show|display|see)\s+(?:files|contents|directory)\s+(?:in|of|from)\s+([^\s]+)',
                r'(?:ls|dir)\s+([^\s]+)',
                r'(?:what.*?in|files.*?in)\s+([^\s]+)',
            ]

            directory = None
            for pattern in dir_patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    directory = match.group(1)
                    break

            # If no directory specified, use current directory
            if not directory:
                # Check if user just wants to list current directory
                if re.search(r'\b(?:list|show)\s+(?:files|directory|contents)\b', user_input, re.IGNORECASE):
                    directory = "."
                else:
                    logger.warning("Could not extract directory from user input for list_files")
                    return None

            logger.info(f"Forcing list_files: {directory}")

            # Execute list_files directly
            arguments = {
                "path": directory
            }

            result = self.tool_executor.execute(tool_name, arguments)
            return result

        return None

    def _inject_context(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Auto-inject previous tool results into specialist tool parameters.

        When a specialist tool is called, prepend recent tool outputs to provide context
        without relying on orchestrator intelligence.

        Args:
            tool_name: Name of the tool being called
            arguments: Tool arguments dict

        Returns:
            Updated arguments dict with context injected
        """
        # Only inject context for specialist tools
        if tool_name not in SPECIALIST_TOOLS:
            return arguments

        # Skip if no recent tool outputs to inject
        if not self.recent_tool_outputs:
            return arguments

        # Determine which parameter to inject into
        param_name = None
        if tool_name == "use_reasoning_model":
            param_name = "task"
        elif tool_name == "use_search_model":
            param_name = "query"
        elif tool_name == "use_codestral":
            param_name = "code_context"

        if not param_name or param_name not in arguments:
            return arguments

        # Build context from recent tool outputs
        context_parts = []
        for prev_tool_name, prev_result in self.recent_tool_outputs:
            # Truncate very long results
            truncated_result = prev_result[:2000] + "..." if len(prev_result) > 2000 else prev_result
            context_parts.append(f"[Previous {prev_tool_name} output]:\n{truncated_result}")

        context_str = "\n\n".join(context_parts)

        # Inject context into parameter
        original_value = arguments[param_name]
        arguments = arguments.copy()
        arguments[param_name] = f"{context_str}\n\n---\nTask: {original_value}"

        logger.info(f"Auto-injected context from {len(self.recent_tool_outputs)} previous tools into {tool_name}")
        return arguments

    def process(self, user_input: str, tools_available: bool = True) -> tuple[str, float]:
        """
        Process a single user turn to completion.

        Args:
            user_input: User's input for this turn
            tools_available: Whether tools should be available to the model

        Returns:
            Tuple of (final text response, execution time in seconds)

        Flow:
        1. Add user message to conversation
        2. Loop until final response:
           - Call LLM with conversation history and tools (if available)
           - If tool calls: execute all, add results, continue loop
           - If text response: add to conversation, return
        3. Return final response
        """
        # Add user message to conversation
        logger.info(f"User: {user_input[:100]}{'...' if len(user_input) > 100 else ''}")
        self.conversation.add_user_message(user_input)

        # Clear recent tool outputs for this turn
        self.recent_tool_outputs = []

        # Start timing
        total_start_time = time.time()

        # Intent detection: Check if we should use fast intent detector
        if self._should_use_intent_detection(user_input):
            logger.info("Using intent detection for this request")

            # Build recent context summary
            recent_context = ""
            if self.last_specialist_output:
                # Include summary of last specialist output
                summary = self.last_specialist_output[:200] + "..." if len(self.last_specialist_output) > 200 else self.last_specialist_output
                recent_context = f"Previous specialist output: {summary}"

            # Call intent detector
            try:
                intent_result = self.tool_executor.execute("use_intent_detector", {
                    "user_input": user_input,
                    "recent_context": recent_context
                })

                # Parse JSON response
                intent_data = json.loads(intent_result)
                detected_tool = intent_data.get("tool")
                confidence = intent_data.get("confidence")
                reasoning = intent_data.get("reasoning", "")

                logger.info(f"Intent detected: {detected_tool} (confidence: {confidence}) - {reasoning}")

                # If high confidence file operation, execute directly
                file_operations = ["write_file", "read_file", "list_files"]
                if detected_tool in file_operations and confidence == "high":
                    forced_result = self._execute_forced_tool_call(detected_tool, user_input)
                    logger.info(f"Forced execution result: {forced_result[:200] if forced_result else 'None'}...")
                    if forced_result:
                        # Add forced tool call to conversation for context
                        self.conversation.add_assistant_message(content=f"{forced_result}")
                        logger.info(f"Returning forced result early ({len(forced_result)} chars)")
                        return forced_result, time.time() - total_start_time
                    else:
                        logger.warning(f"Forced execution returned None, falling back to orchestrator")

            except Exception as e:
                logger.warning(f"Intent detection failed, falling back to normal flow: {e}")
                # Fall through to normal orchestrator flow

        max_iterations = 10  # Prevent infinite loops
        iteration = 0
        tools_provided = tools_available

        # Track recent tool calls for loop detection
        recent_tool_calls = []  # List of (function_name, arguments_json)

        while iteration < max_iterations:
            iteration += 1

            # Determine if tools should be provided
            # Keep tools available until model returns text (no tool calls)
            tools = self.tool_registry.get_definitions() if tools_provided else None

            # Get LLM response
            logger.debug(f"Calling LLM (iteration {iteration}, tools={'enabled' if tools else 'disabled'})")
            try:
                if self.ui:
                    with self.ui.loading_animation(iteration, max_iterations):
                        response = self.llm_client.chat_complete(
                            self.conversation.get_messages(),
                            tools=tools
                        )
                else:
                    response = self.llm_client.chat_complete(
                        self.conversation.get_messages(),
                        tools=tools
                    )

                # Check finish_reason for errors
                finish_reason = self.llm_client.extract_finish_reason(response)
                if finish_reason == "length":
                    return "Error: Response truncated due to max_tokens limit. Increase MAX_TOKENS in config.py", time.time() - total_start_time
                elif finish_reason == "content_filter":
                    return "Error: Response blocked by content filter", time.time() - total_start_time
                elif finish_reason not in ["stop", "tool_calls", None]:
                    return f"Warning: Unexpected finish_reason: {finish_reason}", time.time() - total_start_time

            except Exception as e:
                return f"Error: Failed to get LLM response: {e}", time.time() - total_start_time

            # Check for tool calls
            tool_calls = self.llm_client.extract_tool_calls(response)

            if tool_calls and len(tool_calls) > 0:
                logger.info(f"Received {len(tool_calls)} tool calls: {[tc.get('function', {}).get('name') for tc in tool_calls]}")
                # Add assistant message with tool calls FIRST (OpenAI format requirement)
                self.conversation.add_assistant_message(
                    content="",  # Empty string, not None - required by OpenAI spec
                    tool_calls=tool_calls
                )

                # THEN execute ALL tool calls and add results (parallel execution)
                specialist_result = None
                for tool_call in tool_calls:
                    # Validate tool_call_id exists
                    tool_call_id = tool_call.get("id")
                    if not tool_call_id:
                        # Log error and add error as tool result
                        error_msg = f"Error: Missing tool_call_id in tool_call: {tool_call}"
                        self.conversation.add_tool_result(
                            "error_missing_id",
                            "error",
                            error_msg
                        )
                        continue

                    function_name, arguments = self.tool_executor.parse_tool_call(tool_call)

                    # Resolve references (e.g., "this plan" -> actual content)
                    arguments = self._resolve_references(function_name, arguments)

                    # Auto-inject context from previous tools
                    arguments = self._inject_context(function_name, arguments)

                    # Loop detection: Check if we're calling the same tool repeatedly
                    arguments_json = json.dumps(arguments, sort_keys=True)
                    tool_signature = (function_name, arguments_json)
                    recent_tool_calls.append(tool_signature)

                    # If the same tool call appears 3+ times in recent history, we're stuck
                    if recent_tool_calls.count(tool_signature) >= 3:
                        logger.warning(f"Loop detected: {function_name} called 3+ times with same arguments")
                        execution_time = time.time() - total_start_time
                        return (
                            f"Error: Loop detected. I called '{function_name}' multiple times without progress.\n"
                            f"Recent tool calls: {[name for name, _ in recent_tool_calls[-5:]]}\n"
                            f"I may be stuck. Could you clarify what you need or try rephrasing your request?",
                            execution_time
                        )

                    # Show tool execution start
                    if self.ui:
                        self.ui.show_tool_execution(function_name, arguments)

                    tool_result = self.tool_executor.execute(function_name, arguments)

                    # Track tool output for context injection (only non-specialist tools)
                    if function_name not in SPECIALIST_TOOLS and not tool_result.startswith("Error:"):
                        self.recent_tool_outputs.append((function_name, tool_result))
                        # Keep only last N tool outputs
                        if len(self.recent_tool_outputs) > self.max_context_tools:
                            self.recent_tool_outputs.pop(0)

                    # Show tool execution result
                    if self.ui:
                        success = not tool_result.startswith("Error:")
                        self.ui.show_tool_result(function_name, success, len(tool_result))

                    # Add tool result to conversation
                    self.conversation.add_tool_result(
                        tool_call_id,  # Validated ID
                        function_name,
                        tool_result
                    )

                    # Check if this is a specialist tool - if so, return result directly
                    if function_name in SPECIALIST_TOOLS and not tool_result.startswith("Error:"):
                        specialist_result = tool_result
                        # Store for reference resolution
                        self.last_specialist_output = tool_result
                        logger.info(f"Specialist tool {function_name} returned result - ending iteration")

                # If a specialist tool was called, return its result immediately
                # instead of continuing the orchestrator loop
                if specialist_result:
                    execution_time = time.time() - total_start_time
                    return specialist_result.strip(), execution_time

                # Continue loop - model will see tool results and can call more tools or respond
                # Keep tools available for potential chaining
                # Note: Don't reset iteration counter to maintain loop protection
                continue

            # No tool calls - extract text content
            content = self.llm_client.extract_content(response)

            if content and content.strip():
                # Check if content contains JSON tool call (for models that output JSON as text)
                json_tool_call = self._extract_json_tool_call(content)

                if json_tool_call:
                    tool_name = json_tool_call["tool"]
                    arguments = json_tool_call["arguments"]

                    logger.info(f"Detected JSON tool call in text: {tool_name}({arguments})")

                    # Resolve references (e.g., "this plan" -> actual content)
                    arguments = self._resolve_references(tool_name, arguments)

                    # Auto-inject context from previous tools
                    arguments = self._inject_context(tool_name, arguments)

                    # Loop detection: Check if we're calling the same tool repeatedly
                    arguments_json = json.dumps(arguments, sort_keys=True)
                    tool_signature = (tool_name, arguments_json)
                    recent_tool_calls.append(tool_signature)

                    # If the same tool call appears 3+ times in recent history, we're stuck
                    if recent_tool_calls.count(tool_signature) >= 3:
                        logger.warning(f"Loop detected: {tool_name} called 3+ times with same arguments")
                        execution_time = time.time() - total_start_time
                        return (
                            f"Error: Loop detected. I called '{tool_name}' multiple times without progress.\n"
                            f"Recent tool calls: {[name for name, _ in recent_tool_calls[-5:]]}\n"
                            f"I may be stuck. Could you clarify what you need or try rephrasing your request?",
                            execution_time
                        )

                    # Show tool execution
                    if self.ui:
                        self.ui.show_tool_execution(tool_name, arguments)

                    # Execute the tool
                    tool_result = self.tool_executor.execute(tool_name, arguments)

                    # Track tool output for context injection (only non-specialist tools)
                    if tool_name not in SPECIALIST_TOOLS and not tool_result.startswith("Error:"):
                        self.recent_tool_outputs.append((tool_name, tool_result))
                        # Keep only last N tool outputs
                        if len(self.recent_tool_outputs) > self.max_context_tools:
                            self.recent_tool_outputs.pop(0)

                    # Show result
                    if self.ui:
                        success = not tool_result.startswith("Error:")
                        self.ui.show_tool_result(tool_name, success, len(tool_result))

                    # Add assistant message with the thinking/content
                    self.conversation.add_assistant_message(content=content)

                    # Add tool result
                    self.conversation.add_tool_result(
                        f"json_call_{iteration}",
                        tool_name,
                        tool_result
                    )

                    # Check if this is a specialist tool - if so, return result directly
                    if tool_name in SPECIALIST_TOOLS and not tool_result.startswith("Error:"):
                        # Store for reference resolution
                        self.last_specialist_output = tool_result
                        logger.info(f"Specialist tool {tool_name} (text-based) returned result - ending iteration")
                        execution_time = time.time() - total_start_time
                        return tool_result.strip(), execution_time

                    # Continue loop to get final response
                    continue

                # No JSON tool call - this is the final response
                logger.info(f"Final response: {len(content)} chars")
                self.conversation.add_assistant_message(content=content)
                execution_time = time.time() - total_start_time
                return content.strip(), execution_time
            else:
                # Empty response without tool_calls - this is an error
                finish_reason = self.llm_client.extract_finish_reason(response)
                error_msg = f"Error: LLM returned empty response (finish_reason: {finish_reason})"

                # Add error to conversation for context
                self.conversation.add_assistant_message(
                    content="[Internal error: empty response]"
                )
                return error_msg, time.time() - total_start_time

        return f"Error: Maximum iterations ({max_iterations}) reached without valid response.", time.time() - total_start_time

    def should_provide_tools(self, user_input: str) -> bool:
        """
        Determine if tools should be available based on user input.

        Args:
            user_input: User's input

        Returns:
            True if tools should be available
        """
        # Simple heuristic: check for filesystem-related keywords
        fs_patterns = [
            r"\b(list|show|ls|dir|files?|directory|directories)\b",
            r"\b(read|open|cat|view|show|display|get)\s+.*\b(file|files?|code|content)\b",
            r"\b(write|create|edit|modify|change|update|save)\s+.*\b(file|files?|code)\b",
            r"\b(refactor|rename|move|delete|remove)\b",
            r"\b(run|execute|exec|bash|shell|command)\b",
            r"\b(patch|diff|apply)\b",
            r"\b(codebase|project|repo|repository|directory|folder)\b",
            r"\.py\b|\.js\b|\.ts\b|\.md\b|\.txt\b",
            r"['\"][^'\"]*\.[a-z]{2,4}['\"]",
        ]
        pattern = re.compile("|".join(f"({p})" for p in fs_patterns), re.IGNORECASE)
        return bool(pattern.search(user_input))
