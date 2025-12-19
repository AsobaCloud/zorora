"""Tool executor for executing tools and formatting results."""

from typing import Dict, Any, Optional
import json
import re
import logging

from tool_registry import ToolRegistry, SPECIALIST_TOOLS

logger = logging.getLogger(__name__)


# Maximum size for tool results (to prevent context bloat)
MAX_TOOL_RESULT_SIZE = 10000  # characters


class ToolExecutor:
    """Executes tools and formats results."""

    def __init__(self, registry: ToolRegistry, ui=None):
        self.registry = registry
        self.ui = ui
        # Track current working directory for stateful navigation
        from pathlib import Path
        self.working_directory = Path.cwd()

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a tool with given arguments.

        Args:
            tool_name: Tool name (may be alias)
            arguments: Tool arguments dict

        Returns:
            Tool result string (truncated if too large)
        """
        tool_func = self.registry.get_function(tool_name)
        if tool_func is None:
            return f"Error: Unknown tool '{tool_name}'"

        # Fix common parameter name mistakes from orchestrator
        arguments = self._fix_parameter_names(tool_name, arguments)

        try:
            # Special handling for use_codestral - pass UI for interactive planning
            if tool_name == "use_codestral" and self.ui is not None:
                arguments['ui'] = self.ui

            # Pass working directory to file operations and navigation tools
            file_ops = ["read_file", "write_file", "edit_file", "list_files", "make_directory", "get_working_directory", "pwd"]
            if tool_name in file_ops:
                arguments['working_directory'] = self.working_directory

            result = tool_func(**arguments)

            # Detect cd command and update working directory
            if tool_name == "run_shell":
                self._handle_cd_command(arguments.get("command", ""), result)

            return self._truncate_result(result, tool_name)
        except TypeError as e:
            return f"Error: Invalid arguments for tool '{tool_name}': {e}"
        except Exception as e:
            return f"Error executing tool '{tool_name}': {e}"

    def _handle_cd_command(self, command: str, result: str):
        """
        Detect cd commands and update working directory state.

        Args:
            command: The shell command that was executed
            result: The result from running the command
        """
        import re
        from pathlib import Path

        # Check if this is a cd command
        cd_match = re.match(r'^cd\s+(.+?)(?:\s*&&|\s*;|\s*$)', command.strip())
        if not cd_match:
            return

        # Check if command succeeded (no "No such file or directory" in stderr)
        if "No such file or directory" in result or "[exit:" in result:
            # Command failed, don't update directory
            return

        # Extract target directory
        target = cd_match.group(1).strip().strip('"').strip("'")

        try:
            # Expand ~ and resolve path
            target_path = Path(target).expanduser()

            # If relative path, resolve against current working directory
            if not target_path.is_absolute():
                target_path = (self.working_directory / target_path).resolve()
            else:
                target_path = target_path.resolve()

            # Verify directory exists before updating
            if target_path.exists() and target_path.is_dir():
                self.working_directory = target_path
                logger.info(f"Updated working directory to: {self.working_directory}")
            else:
                logger.warning(f"cd target does not exist or is not a directory: {target_path}")

        except Exception as e:
            logger.warning(f"Failed to update working directory: {e}")

    def _fix_parameter_names(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fix common parameter name mistakes made by orchestrator models.

        Args:
            tool_name: Name of the tool being called
            arguments: Original arguments dict

        Returns:
            Fixed arguments dict with correct parameter names
        """
        # Common parameter name mappings
        fixes = {
            "read_file": {"task": "path", "file": "path", "filename": "path"},
            "write_file": {"task": "path", "file": "path", "filename": "path"},
            "list_files": {"task": "path", "dir": "path", "directory": "path"},
            "use_codestral": {"task": "code_context", "prompt": "code_context"},
            "use_reasoning_model": {"prompt": "task", "question": "task"},
            "use_search_model": {"task": "query", "question": "query", "search": "query"},
        }

        if tool_name not in fixes:
            return arguments

        fixed = arguments.copy()
        mappings = fixes[tool_name]

        for wrong_name, correct_name in mappings.items():
            if wrong_name in fixed and correct_name not in fixed:
                fixed[correct_name] = fixed.pop(wrong_name)
                import logging
                logging.getLogger(__name__).info(f"Fixed parameter name: {wrong_name} → {correct_name} for {tool_name}")

        return fixed

    def _truncate_result(self, result: str, tool_name: str) -> str:
        """
        Truncate large tool results to prevent context bloat.
        Specialist tools are exempt from truncation as they return final responses.

        Args:
            result: Tool result string
            tool_name: Name of the tool that produced the result

        Returns:
            Truncated result with indicator if truncated (or full result for specialist tools)
        """
        # Don't truncate specialist tools - they return final responses to be shown in full
        if tool_name in SPECIALIST_TOOLS:
            return result

        if len(result) <= MAX_TOOL_RESULT_SIZE:
            return result

        truncated = result[:MAX_TOOL_RESULT_SIZE]
        return f"{truncated}\n\n[Result truncated: showing first {MAX_TOOL_RESULT_SIZE} of {len(result)} characters]"

    def parse_tool_call(self, tool_call: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """
        Parse a tool call dict into (function_name, arguments).

        Args:
            tool_call: Tool call dict with 'function' key

        Returns:
            Tuple of (function_name, arguments_dict)
        """
        function = tool_call.get("function", {})
        function_name = function.get("name", "")
        arguments_str = function.get("arguments", "{}")

        try:
            arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
        except json.JSONDecodeError:
            arguments = {}

        return function_name, arguments

    def parse_json_tool_call(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse JSON tool call from orchestrator response.

        Expected format:
        {
          "tool": "tool_name",
          "input": "user input",
          "confidence": 0.85
        }

        Args:
            response_text: Text response from orchestrator

        Returns:
            Dict with 'tool', 'arguments', 'confidence' or None if invalid
        """
        try:
            # Extract JSON from response (handle markdown code blocks)
            # First try to extract from code blocks
            code_block_match = re.search(r'```(?:json)?\s*(\{[^`]+\})\s*```', response_text, re.DOTALL)
            if code_block_match:
                json_str = code_block_match.group(1)
            else:
                # Try to find JSON object directly
                json_match = re.search(r'\{[^{}]*"tool"[^{}]*\}', response_text, re.DOTALL)
                if not json_match:
                    return None
                json_str = json_match.group(0)

            data = json.loads(json_str)

            # Validate required fields
            if "tool" not in data or "input" not in data:
                logger.warning(f"Invalid JSON tool call: missing 'tool' or 'input' fields")
                return None

            tool_name = data["tool"]
            user_input = data["input"]
            confidence = data.get("confidence", 0.5)

            # Map input to correct parameter name for each tool
            param_mapping = {
                "web_search": "query",
                "use_codestral": "code_context",
                "use_reasoning_model": "task",
                "use_search_model": "query",
                "use_energy_analyst": "query",
                "get_newsroom_headlines": None,  # No parameters
                "read_file": "path",
                "write_file": "content",  # Special case: needs path extraction
                "list_files": "path",
                "run_shell": "command",
                "apply_patch": "patch",
                "generate_image": "prompt",
                "analyze_image": "path",
            }

            param_name = param_mapping.get(tool_name)

            # Handle tools with no parameters
            if param_name is None:
                arguments = {}
            else:
                arguments = {param_name: user_input}

            return {
                "tool": tool_name,
                "arguments": arguments,
                "confidence": confidence
            }

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON tool call: {e}")
            return None
        except Exception as e:
            logger.warning(f"Error parsing JSON tool call: {e}")
            return None
