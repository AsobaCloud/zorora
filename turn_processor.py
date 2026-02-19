"""Turn processor for handling individual REPL turns with tool calling."""

from typing import Optional, List, Dict, Any
import re
import logging
import time
import json
from pathlib import Path

from conversation import ConversationManager
from llm_client import LLMClient
from tool_executor import ToolExecutor
from tools.registry import ToolRegistry, SPECIALIST_TOOLS, edit_file
from tools.specialist.client import create_specialist_client
from simplified_router import SimplifiedRouter
from research_workflow import ResearchWorkflow
from research_persistence import ResearchPersistence
import config
from tools.data_analysis import session as data_session
from tools.data_analysis.context import build_data_system_context

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

        # Initialize simplified router (deterministic decision tree)
        self.router = SimplifiedRouter()

        # Initialize research workflow (hardcoded pipeline)
        self.research_workflow = ResearchWorkflow(tool_executor, llm_client)

        # Initialize research persistence (save/load findings)
        self.research_persistence = ResearchPersistence()

        # Track last specialist tool output for reference resolution
        self.last_specialist_output: Optional[str] = None

        # Track recent tool outputs for auto-context injection
        # Store tuples of (tool_name, result)
        self.recent_tool_outputs: List[tuple[str, str]] = []
        self.max_context_tools = 3  # Keep last 3 tool results for context

    def _resolve_references(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve reference pronouns in tool arguments to actual content.

        If a tool is called with content containing "this", "that", "this topic", etc.,
        replace with last_specialist_output or extract from conversation history.

        Args:
            tool_name: Name of the tool being called
            arguments: Tool arguments dict

        Returns:
            Updated arguments dict with references resolved
        """
        # Find the parameter that likely contains the content/query
        param_name = None
        if tool_name == "write_file":
            param_name = "content"
        elif tool_name == "use_coding_agent":
            param_name = "code_context"
        elif tool_name == "use_reasoning_model":
            param_name = "task"
        elif tool_name == "web_search":
            param_name = "query"
        elif tool_name == "use_search_model":
            param_name = "query"
        elif tool_name in ["use_nehanda", "use_energy_analyst"]:
            param_name = "query"

        if not param_name or param_name not in arguments:
            return arguments

        original_value = arguments[param_name]
        if not isinstance(original_value, str):
            return arguments

        # Patterns that indicate a reference to previous output or topic
        reference_patterns = [
            r'\bthis\s+topic\b',
            r'\bthat\s+topic\b',
            r'\bthe\s+topic\b',
            r'\bthis\s+subject\b',
            r'\bthis\s+issue\b',
            r'\bthis\s+question\b',
            r'^(this|that|the)\s+(topic|subject|issue|question|thing)$',  # Entire query is just "this topic"
            r'\bthe\s+plan\b',
            r'\bthe\s+outline\b',
            r'\bthe\s+analysis\b',
            r'\bthe\s+report\b',
            r'\babove\b',
            r'\bprevious\b',
            r'\bjust\s+generated\b',
            r'\bjust\s+provided\b',
        ]

        # Check if the value contains reference patterns or is too vague
        has_reference = any(re.search(pattern, original_value, re.IGNORECASE) for pattern in reference_patterns)
        is_too_vague = re.match(r'^(this|that|the)\s+(topic|subject|issue|question|thing)$', original_value.strip(), re.IGNORECASE)

        if has_reference or is_too_vague:
            # Try to resolve from conversation history first (for web_search, get the original user query)
            resolved_value = None
            
            # For web_search, try to get the original user query from conversation
            if tool_name == "web_search":
                messages = self.conversation.get_messages()
                # Look for the most recent user message that's substantial
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        user_query = msg.get("content", "")
                        # If it's a substantial query (not just "let's do a web search"), use it
                        if len(user_query) > 20 and not re.match(r'^(let\'?s\s+)?(do\s+a\s+)?(web\s+)?search', user_query, re.IGNORECASE):
                            resolved_value = user_query
                            logger.info(f"Resolved 'this topic' from conversation history: {user_query[:60]}...")
                            break
            
            # Fallback to last_specialist_output if available
            if not resolved_value and self.last_specialist_output:
                # For web_search, try to extract keywords from last output
                if tool_name == "web_search":
                    # Extract first line or key phrase from last output
                    first_line = self.last_specialist_output.split('\n')[0]
                    # Try to extract a meaningful query - look for the original query in the output
                    query_match = re.search(r'for:\s*(.+?)(?:\s+\[|$)', first_line)
                    if query_match:
                        resolved_value = query_match.group(1).strip()
                    elif len(first_line) > 10:
                        resolved_value = first_line[:100]  # Use first 100 chars as query
                else:
                    resolved_value = self.last_specialist_output
            
            if resolved_value:
                arguments = arguments.copy()
                arguments[param_name] = resolved_value
                logger.info(f"Resolved reference '{original_value}' in {tool_name}.{param_name} to: {resolved_value[:60]}...")
                return arguments
            else:
                logger.warning(f"Could not resolve reference '{original_value}' in {tool_name}.{param_name} - no context available")

        return arguments

    def _execute_specialist_tool(self, tool_name: str, user_input: str) -> Optional[str]:
        """
        Execute a specialist tool with proper context injection and reference resolution.
        
        Args:
            tool_name: Name of the specialist tool to execute
            user_input: User's input to pass to the tool
            
        Returns:
            Tool result string, or None if unable to execute
        """
        logger.info(f"Executing specialist tool: {tool_name}")

        # Determine the parameter name for each specialist tool
        param_mapping = {
            "use_coding_agent": "code_context",
            "use_reasoning_model": "task",
            "use_search_model": "query",
            "use_nehanda": "query",
            "use_energy_analyst": "query",  # backwards compat alias
            "web_search": "query",
            "generate_image": "prompt",
            "execute_analysis": "code",
            "nehanda_query": "query",
        }

        param_name = param_mapping.get(tool_name)
        if not param_name:
            logger.warning(f"No parameter mapping for specialist tool: {tool_name}")
            return None

        # For codestral, if we have recent context about files, include it
        if tool_name == "use_coding_agent":
            context_parts = [user_input]
            if self.last_specialist_output and len(self.last_specialist_output) > 0:
                # Add reference to last output for context
                context_parts.append(f"\n\nContext from previous operation:\n{self.last_specialist_output[:500]}")
            user_input_with_context = "\n".join(context_parts)
            arguments = {param_name: user_input_with_context}
        else:
            arguments = {param_name: user_input}
        
        # Resolve references (e.g., "this topic" -> actual previous query)
        arguments = self._resolve_references(tool_name, arguments)
        
        # Auto-inject context from previous tools (for specialist tools)
        arguments = self._inject_context(tool_name, arguments)

        result = self.tool_executor.execute(tool_name, arguments)
        
        # Track tool output for context injection (non-specialist tools only)
        # This ensures results from forced tool calls are available for next tool
        if tool_name not in SPECIALIST_TOOLS and result and not result.startswith("Error:"):
            self.recent_tool_outputs.append((tool_name, result))
            # Keep only last N tool outputs
            if len(self.recent_tool_outputs) > self.max_context_tools:
                self.recent_tool_outputs.pop(0)
            logger.info(f"Added {tool_name} result to recent_tool_outputs for context injection")

        return result

    def _detect_file_in_input(self, user_input: str) -> Optional[str]:
        """
        Detect if user mentions a file path that exists.

        Returns:
            Path to existing file, or None if no file detected/exists
        """
        # Common file path patterns
        patterns = [
            r'(?:update|edit|modify|change|fix)\s+([^\s"\']+\.[a-zA-Z0-9]+)',  # "update file.py"
            r'([^\s"\']+\.[a-zA-Z0-9]+)\s+(?:from|to)',  # "file.py from X to Y"
            r'(?:in|on)\s+([^\s"\']+\.[a-zA-Z0-9]+)',  # "in file.py"
            r'"([^"]+\.[a-zA-Z0-9]+)"',  # "file.py" (quoted)
            r"'([^']+\.[a-zA-Z0-9]+)'",  # 'file.py' (quoted)
            r'([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z0-9]+)',  # Simple filename like script.py
        ]

        working_dir = self.tool_executor.working_directory

        for pattern in patterns:
            matches = re.findall(pattern, user_input, re.IGNORECASE)
            for match in matches:
                # Try as-is first
                full_path = Path(working_dir) / match
                if full_path.exists() and full_path.is_file():
                    return str(match)

                # Try with common extensions if no extension
                if '.' not in match:
                    for ext in ['.py', '.js', '.ts', '.json', '.yaml', '.yml', '.md']:
                        full_path = Path(working_dir) / (match + ext)
                        if full_path.exists():
                            return str(match + ext)

        return None

    def _execute_code_edit(self, user_input: str, file_path: str, max_retries: int = 3) -> str:
        """
        Execute a file edit using the coding model and edit_file tool.

        This provides the proper edit workflow:
        1. Read the file with line numbers
        2. Build an edit prompt for the coding model
        3. Parse OLD_CODE/NEW_CODE from response
        4. Apply edit_file with retry on failure

        Args:
            user_input: User's edit request
            file_path: Path to the file to edit
            max_retries: Maximum retry attempts

        Returns:
            Result message
        """
        working_dir = self.tool_executor.working_directory
        full_path = Path(working_dir) / file_path

        if not full_path.exists():
            return f"Error: File {file_path} does not exist"

        last_error = None

        for attempt in range(max_retries):
            try:
                # Read file with line numbers
                current_content = full_path.read_text(encoding='utf-8')
                numbered_content = self._add_line_numbers(current_content)

                # Truncate if very large
                if len(numbered_content) > 15000:
                    lines = numbered_content.split('\n')
                    numbered_content = '\n'.join(lines[:200]) + '\n... (truncated) ...\n' + '\n'.join(lines[-100:])

                # Build prompt (include error context on retry)
                if attempt == 0:
                    prompt = self._build_edit_prompt(user_input, file_path, numbered_content)
                else:
                    prompt = self._build_retry_edit_prompt(user_input, file_path, numbered_content, last_error, attempt)

                # Call coding model directly (bypass planning phase for simple edits)
                model_config = config.SPECIALIZED_MODELS["codestral"]
                client = create_specialist_client("codestral", model_config)

                messages = [
                    {
                        "role": "system",
                        "content": "You are a code editor. Your ONLY job is to output OLD_CODE and NEW_CODE blocks. Do not explain or discuss - just output the exact format requested."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]

                response = client.chat_complete(messages, tools=None)
                result = client.extract_content(response)

                if not result or result.startswith("Error"):
                    last_error = result or "No response from coding model"
                    logger.warning(f"Edit attempt {attempt+1}: {last_error}")
                    continue

                # Parse OLD_CODE/NEW_CODE from response
                edit_instructions = self._extract_edit_instructions(result, current_content)

                if not edit_instructions:
                    last_error = "Could not parse OLD_CODE/NEW_CODE from model response"
                    logger.warning(f"Edit attempt {attempt+1}: {last_error}")
                    continue

                old_code = edit_instructions["old"]
                new_code = edit_instructions["new"]

                # Apply edit
                edit_result = edit_file(file_path, old_code, new_code, working_dir)

                if not edit_result.startswith("Error"):
                    # Success!
                    if attempt > 0:
                        logger.info(f"Edit succeeded on attempt {attempt+1}")
                    return f"Successfully edited {file_path}:\n{edit_result}"

                # Failed - capture error for next attempt
                last_error = edit_result
                logger.warning(f"Edit attempt {attempt+1} failed: {edit_result}")

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Edit attempt {attempt+1} exception: {e}")

        return f"Error: Failed to edit {file_path} after {max_retries} attempts. Last error: {last_error}"

    def _add_line_numbers(self, content: str) -> str:
        """Add line numbers to content for reference."""
        lines = content.splitlines()
        numbered = [f"{i:4d} | {line}" for i, line in enumerate(lines, 1)]
        return "\n".join(numbered)

    def _build_edit_prompt(self, user_input: str, file_path: str, numbered_content: str) -> str:
        """Build prompt for editing a file."""
        return f"""You need to edit a file based on the user's request.

FILE: {file_path}

CURRENT CONTENT (with line numbers for reference):
{numbered_content}

USER REQUEST: {user_input}

IMPORTANT:
1. The OLD_CODE must match EXACTLY what's in the file (including whitespace/indentation)
2. Copy the text precisely from the content above (do NOT include line numbers)
3. If string appears multiple times, include enough context to make it unique
4. Make minimal changes - only change what's necessary

Output your response in this EXACT format:
OLD_CODE:
```
[exact code to replace - copy from above, without line numbers]
```

NEW_CODE:
```
[replacement code]
```"""

    def _build_retry_edit_prompt(self, user_input: str, file_path: str, numbered_content: str,
                                  previous_error: str, attempt: int) -> str:
        """Build prompt for retry attempt with error context."""
        return f"""RETRY ATTEMPT {attempt + 1}: Your previous edit failed.

ERROR: {previous_error}

FILE: {file_path}

CURRENT CONTENT (with line numbers - use these for reference):
{numbered_content}

USER REQUEST: {user_input}

IMPORTANT:
1. The OLD_CODE must match EXACTLY what's in the file (including whitespace)
2. Copy the exact text from the file above, preserving indentation
3. If the string appears multiple times, include more context to make it unique
4. Do NOT include line numbers in your OLD_CODE - just the actual code

Output in this EXACT format:
OLD_CODE:
```
[exact code to replace - copy from file above, without line numbers]
```

NEW_CODE:
```
[replacement code]
```"""

    def _extract_edit_instructions(self, response: str, current_content: str) -> Optional[Dict[str, str]]:
        """Extract OLD_CODE and NEW_CODE from model response."""
        try:
            if "OLD_CODE:" not in response or "NEW_CODE:" not in response:
                return None

            old_start = response.find("OLD_CODE:") + 9
            old_end = response.find("NEW_CODE:")
            new_start = response.find("NEW_CODE:") + 9

            old_section = response[old_start:old_end].strip()
            new_section = response[new_start:].strip()

            # Remove code block markers
            old_code = self._extract_code_block(old_section)
            new_code = self._extract_code_block(new_section)

            # Verify old_code exists in current content
            if old_code and old_code in current_content:
                return {"old": old_code, "new": new_code}
            else:
                logger.warning("OLD_CODE not found in current file content")
                return None

        except Exception as e:
            logger.error(f"Error extracting edit instructions: {e}")
            return None

    def _extract_code_block(self, text: str) -> str:
        """Extract code from markdown code block."""
        if "```" in text:
            start = text.find("```")
            # Skip language identifier
            newline = text.find("\n", start)
            if newline >= 0:
                start = newline + 1
                end = text.find("```", start)
                if end >= 0:
                    return text[start:end].strip()
        return text.strip()

    def _inject_context(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Auto-inject previous tool results into specialist tool parameters.

        When a specialist tool is called, prepend recent tool outputs to provide context
        without relying on orchestrator intelligence. Also checks conversation history
        for tool outputs when recent_tool_outputs is empty (e.g., after session resume).

        Args:
            tool_name: Name of the tool being called
            arguments: Tool arguments dict

        Returns:
            Updated arguments dict with context injected
        """
        # Only inject context for specialist tools
        if tool_name not in SPECIALIST_TOOLS:
            return arguments

        # Determine which parameter to inject into
        param_name = None
        if tool_name == "use_reasoning_model":
            param_name = "task"
        elif tool_name == "use_search_model":
            param_name = "query"
        elif tool_name == "use_coding_agent":
            param_name = "code_context"
        elif tool_name == "analyze_image":
            param_name = "task"

        if not param_name or param_name not in arguments:
            return arguments

        # Collect context from recent_tool_outputs
        context_parts = []
        if self.recent_tool_outputs:
            for prev_tool_name, prev_result in self.recent_tool_outputs:
                # Use larger limit for search/academic tools that need full context for summarization
                if prev_tool_name in ["academic_search", "web_search"]:
                    max_length = 10000  # Larger limit for search results
                else:
                    max_length = 2000  # Standard limit for other tools
                
                # Truncate very long results
                truncated_result = prev_result[:max_length] + "..." if len(prev_result) > max_length else prev_result
                context_parts.append(f"[Previous {prev_tool_name} output]:\n{truncated_result}")
        
        # If no recent tool outputs, check conversation history for tool outputs
        # This helps when resuming sessions where recent_tool_outputs wasn't persisted
        if not context_parts:
            messages = self.conversation.get_messages()
            # Look at recent assistant messages (last 5) for tool output patterns
            for msg in reversed(messages[-5:]):
                if msg.get("role") == "assistant":
                    content = msg.get("content", "")
                    # Check for tool output patterns
                    if any(marker in content for marker in [
                        "Academic search results for:",
                        "Search results for:",
                        "Found",
                        "Summary: Found"
                    ]):
                        # Use larger limit for search/academic results
                        # Determine if this is a search result by checking markers
                        is_search_result = "Academic search results for:" in content or "Search results for:" in content
                        max_length = 10000 if is_search_result else 2000
                        
                        # Truncate very long results
                        truncated_result = content[:max_length] + "..." if len(content) > max_length else content
                        context_parts.append(f"[Previous tool output from conversation]:\n{truncated_result}")
                        logger.info("Found tool output in conversation history for context injection")
                        break  # Only use the most recent tool output

        if not context_parts:
            return arguments

        context_str = "\n\n".join(context_parts)

        # Inject context into parameter
        original_value = arguments[param_name]
        arguments = arguments.copy()
        arguments[param_name] = f"{context_str}\n\n---\nTask: {original_value}"

        logger.info(f"Auto-injected context from {len(context_parts)} source(s) into {tool_name}")
        return arguments

    def process(self, user_input: str, forced_workflow: str = None) -> tuple[str, float]:
        """
        Process a single user turn to completion.

        Args:
            user_input: User's input for this turn
            forced_workflow: Optional workflow to force (bypasses router)
                           Values: "research", "code", "qa"

        Returns:
            Tuple of (final text response, execution time in seconds)

        Simplified Research-Focused Flow:

        1. Route query (deterministic decision tree):
           - File operation? → Execute directly
           - Research query? → Multi-source workflow (newsroom + web + synthesis)
           - Code generation? → Codestral
           - Default → Research (web search)

        2. Execute workflow (no complex orchestration)

        3. Return result
        """
        # Add user message to conversation
        logger.info(f"User: {user_input[:100]}{'...' if len(user_input) > 100 else ''}")
        self._sync_data_session_context()
        self.conversation.add_user_message(user_input)

        # Start timing
        total_start_time = time.time()

        # Check for forced workflow (from slash commands)
        if forced_workflow:
            logger.info(f"Forced workflow: {forced_workflow}")
            workflow = forced_workflow
        else:
            # Route query using simplified decision tree
            routing = self.router.route(user_input)
            workflow = routing["workflow"]
            logger.info(f"Routed to workflow: {workflow}")

        # Execute based on workflow type
        if workflow == "research":
            # Multi-source research workflow (newsroom + web + synthesis)
            result = self.research_workflow.execute(user_input, ui=self.ui)
            self.conversation.add_assistant_message(content=result)
            return result, time.time() - total_start_time

        elif workflow == "code":
            # Code generation or file editing with coding model
            # First, check if user wants to edit an existing file
            detected_file = self._detect_file_in_input(user_input)

            if detected_file:
                # User mentioned an existing file - use edit workflow
                logger.info(f"Detected file edit request for: {detected_file}")
                if self.ui:
                    self.ui.console.print(f"[cyan]Detected file: {detected_file} - using edit workflow...[/cyan]")
                result = self._execute_code_edit(user_input, detected_file)
            else:
                # No file detected - use standard code generation
                tool = "use_coding_agent" if forced_workflow else routing.get("tool", "use_coding_agent")
                result = self._execute_specialist_tool(tool, user_input)

            if result:
                self.conversation.add_assistant_message(content=result)
            return (result or "Error executing code operation"), time.time() - total_start_time

        elif workflow == "file_op":
            # File operations (read, write, list)
            result = self._execute_file_operation(routing, user_input)
            self.conversation.add_assistant_message(content=result)
            return result, time.time() - total_start_time

        elif workflow == "qa":
            # Direct Q&A with reasoning model (no search)
            # Only accessible via /ask slash command - not used as routing fallback
            logger.info("Using reasoning model for conversational response (no web search)")
            result = self._execute_specialist_tool("use_reasoning_model", user_input)
            if result:
                self.conversation.add_assistant_message(content=result)
            return (result or "Error executing reasoning model"), time.time() - total_start_time

        elif workflow == "data_analysis":
            # Data analysis with loaded dataset
            logger.info("Executing data analysis")
            result = self._execute_specialist_tool("execute_analysis", user_input)
            if result:
                self.conversation.add_assistant_message(content=result)
            return (result or "Error: No dataset loaded. Use /load <path> first."), time.time() - total_start_time

        elif workflow == "cross_domain":
            # Data + policy + market synthesis flow
            logger.info("Executing cross-domain synthesis workflow")
            result = self._execute_cross_domain_query(user_input)
            if result:
                self.conversation.add_assistant_message(content=result)
            return (result or "Error executing cross-domain workflow"), time.time() - total_start_time

        elif workflow == "energy":
            # Nehanda RAG query for policy documents
            # Only accessible via /analyst slash command
            logger.info("Querying Nehanda RAG for policy documents")
            result = self._execute_specialist_tool("use_nehanda", user_input)
            if result:
                self.conversation.add_assistant_message(content=result)
            return (result or "Error executing Nehanda query"), time.time() - total_start_time

        elif workflow == "image":
            # Image generation with FLUX
            # Only accessible via /image slash command
            logger.info("Generating image with FLUX")
            result = self._execute_specialist_tool("generate_image", user_input)
            if result:
                self.conversation.add_assistant_message(content=result)
            return (result or "Error generating image"), time.time() - total_start_time

        elif workflow == "vision":
            # Image analysis with vision model
            # Only accessible via /analyze slash command
            logger.info("Analyzing image with vision model")
            # Parse path and optional task from user_input
            parts = user_input.split(maxsplit=1)
            path = parts[0]
            task = parts[1] if len(parts) > 1 else "Analyze this image and describe what you see"
            # Inject context into task parameter
            arguments = {"path": path, "task": task}
            arguments = self._inject_context("analyze_image", arguments)
            result = self.tool_executor.execute("analyze_image", arguments)
            if result:
                self.conversation.add_assistant_message(content=result)
            return (result or "Error analyzing image"), time.time() - total_start_time

        else:
            # Unknown workflow - default to research (web search)
            logger.warning(f"Unknown workflow: {workflow}, defaulting to research")
            result = self.research_workflow.execute(user_input, ui=self.ui)
            self.conversation.add_assistant_message(content=result)
            return result, time.time() - total_start_time

    def _sync_data_session_context(self) -> None:
        """Inject active data-session context into system prompt when available."""
        try:
            active = data_session.get_session("")
            if not active:
                self.conversation.clear_runtime_context("data_session")
                return
            context_block = build_data_system_context(active)
            if context_block:
                self.conversation.set_runtime_context("data_session", context_block)
            else:
                self.conversation.clear_runtime_context("data_session")
        except Exception as e:
            logger.warning(f"Failed to sync data session context: {e}")

    def _execute_file_operation(self, routing: Dict[str, Any], user_input: str) -> str:
        """
        Execute file operations (read, write, list).

        Args:
            routing: Routing dict from simplified router
            user_input: User's input

        Returns:
            Result string
        """
        action = routing["action"]
        tool = routing.get("tool")

        if action == "list_files":
            # Check if this is a filesystem list or research list
            # If user mentions "current directory", "pwd", "here", "this directory" -> filesystem
            # Otherwise, assume research files
            user_lower = user_input.lower()
            is_filesystem = any(keyword in user_lower for keyword in [
                "current directory", "this directory", "pwd", "here", "cwd",
                "working directory", "local", "folder"
            ])

            if is_filesystem or tool == "list_files":
                # List actual filesystem files using the list_files tool
                logger.info("Listing filesystem files")
                result = self.tool_executor.execute("list_files", {"path": "."})
                return result
            else:
                # List research files
                research_files = self.research_persistence.list_all()
                if not research_files:
                    return "No saved research found."

                result = "Saved Research:\n\n"
                for i, file_info in enumerate(research_files, 1):
                    topic = file_info["topic"]
                    timestamp = file_info.get("timestamp", "Unknown")
                    query = file_info.get("query", "")

                    result += f"{i}. **{topic}**\n"
                    result += f"   Saved: {timestamp[:10]}\n"
                    if query:
                        result += f"   Query: {query[:80]}...\n" if len(query) > 80 else f"   Query: {query}\n"
                    result += "\n"

                return result

        elif action == "read_file":
            # Extract topic/filename from user input
            topic = self._extract_topic_from_query(user_input)

            if not topic:
                return "Please specify which research to read (e.g., 'show my research on AI energy')"

            research_data = self.research_persistence.load(topic)

            if not research_data:
                return f"Research not found: {topic}\n\nUse 'list files' to see saved research."

            metadata = research_data["metadata"]
            content = research_data["content"]

            result = f"# {metadata.get('topic', 'Research')}\n\n"
            result += f"**Saved:** {metadata.get('timestamp', 'Unknown')[:19]}\n"

            if metadata.get('query'):
                result += f"**Query:** {metadata['query']}\n"

            if metadata.get('sources'):
                result += f"**Sources:** {', '.join(metadata['sources'])}\n"

            result += f"\n---\n\n{content}"

            return result

        elif action == "write_file":
            # Save last result or specified content
            topic = self._extract_topic_from_query(user_input)

            if not topic:
                return "Please specify a topic name (e.g., 'save this as AI energy trends')"

            # Use last specialist output if available
            content = self.last_specialist_output
            if not content:
                return "No content to save. Run a research query first, then save the results."

            # Save research
            filepath = self.research_persistence.save(
                topic=topic,
                content=content,
                query=user_input,
                sources=["Research"]
            )

            return f"Saved research to: {filepath.name}\n\nUse 'list files' to see all saved research."

        else:
            return f"Unknown file operation: {action}"

    def _extract_python_snippet(self, text: str) -> str:
        """Extract first Python code block from model output."""
        if not text:
            return ""
        block = re.search(r"```(?:python)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if block:
            return block.group(1).strip()
        return text.strip()

    def _execute_cross_domain_query(self, user_input: str) -> str:
        """Execute deterministic multi-tool flow for data+policy questions."""
        code_prompt = (
            "Generate ONLY executable Python code for execute_analysis.\n"
            "Use the loaded DataFrame df and set variable result.\n"
            "No markdown, no explanation.\n"
            f"Question: {user_input}"
        )
        generated = self._execute_specialist_tool("use_coding_agent", code_prompt) or ""
        code = self._extract_python_snippet(generated)
        if not code:
            code = "result = df.describe()"

        analysis_result = self.tool_executor.execute("execute_analysis", {"code": code})
        policy_result = self.tool_executor.execute("nehanda_query", {"query": user_input})
        web_result = self.tool_executor.execute("web_search", {"query": user_input})

        synthesis_prompt = (
            "Synthesize the following results into one grounded answer.\n"
            "Always separate what comes from dataset analysis, policy retrieval, and web context.\n\n"
            f"[Data Analysis]\n{analysis_result}\n\n"
            f"[Policy Retrieval]\n{policy_result}\n\n"
            f"[Market Context]\n{web_result}\n\n"
            f"Original question: {user_input}"
        )

        final = self._execute_specialist_tool("use_reasoning_model", synthesis_prompt)
        if final and not final.startswith("Error"):
            return final

        # Deterministic fallback when synthesis model fails
        compact = {
            "analysis": analysis_result[:1200],
            "policy": policy_result[:1200],
            "market": web_result[:1200],
        }
        return json.dumps(compact, indent=2)

    def _extract_topic_from_query(self, query: str) -> Optional[str]:
        """
        Extract topic/filename from user query.

        Args:
            query: User input

        Returns:
            Extracted topic or None
        """
        import re

        # Patterns for extracting topic
        patterns = [
            r'(?:save|write|store).*(?:as|to)\s+["\']?([^"\']+?)["\']?(?:\s|$)',
            r'(?:read|show|load|open)\s+["\']?([^"\']+?)["\']?(?:\s|$)',
            r'(?:research on|about|regarding)\s+([^"\']+?)(?:\s|$)',
            r'["\']([^"\']+)["\']',  # Quoted text
        ]

        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                topic = match.group(1).strip()
                # Clean up common words
                topic = re.sub(r'\b(my|the|this|that|file|research|notes?)\b', '', topic, flags=re.IGNORECASE)
                topic = topic.strip()
                if topic:
                    return topic

        return None
