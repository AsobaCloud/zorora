"""Tool executor for executing tools and formatting results."""

from typing import Dict, Any, Optional
import json

from tool_registry import ToolRegistry, SPECIALIST_TOOLS


# Maximum size for tool results (to prevent context bloat)
MAX_TOOL_RESULT_SIZE = 10000  # characters


class ToolExecutor:
    """Executes tools and formats results."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

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

        try:
            result = tool_func(**arguments)
            return self._truncate_result(result, tool_name)
        except TypeError as e:
            return f"Error: Invalid arguments for tool '{tool_name}': {e}"
        except Exception as e:
            return f"Error executing tool '{tool_name}': {e}"

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
