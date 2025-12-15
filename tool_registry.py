"""Tool registry for tool definitions and function mapping."""

from typing import Dict, Callable, List, Dict as DictType, Any, Optional
from pathlib import Path
import subprocess


# Tool function implementations
def _validate_path(path: str) -> tuple[bool, str]:
    """
    Validate file path for security.

    Returns:
        (is_valid, error_message)
    """
    try:
        file_path = Path(path).resolve()
        cwd = Path.cwd().resolve()

        # Prevent path traversal outside current directory
        if not str(file_path).startswith(str(cwd)):
            return False, f"Error: Path '{path}' is outside current directory"

        return True, ""
    except Exception as e:
        return False, f"Error: Invalid path '{path}': {e}"


def read_file(path: str) -> str:
    """Read contents of a file."""
    # Validate path security
    is_valid, error = _validate_path(path)
    if not is_valid:
        return error

    file_path = Path(path)
    if not file_path.exists():
        return f"Error: File '{path}' does not exist."
    if not file_path.is_file():
        return f"Error: '{path}' is not a file."

    # Check file size limit (10MB)
    if file_path.stat().st_size > 10_000_000:
        return f"Error: File '{path}' too large (>10MB)"

    try:
        return file_path.read_text()
    except UnicodeDecodeError:
        return f"Error: File '{path}' is not a text file"
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str) -> str:
    """Write content to a file (creates or overwrites)."""
    # Validate path security
    is_valid, error = _validate_path(path)
    if not is_valid:
        return error

    try:
        Path(path).write_text(content)
        return f"OK: Written {len(content)} characters to '{path}'"
    except Exception as e:
        return f"Error writing file: {e}"


def list_files(path: str = ".") -> str:
    """List files and directories in a path."""
    # Validate path security
    is_valid, error = _validate_path(path)
    if not is_valid:
        return error

    try:
        dir_path = Path(path)
        if not dir_path.exists():
            return f"Error: Path '{path}' does not exist."
        if not dir_path.is_dir():
            return f"Error: '{path}' is not a directory."
        items = [p.name for p in dir_path.iterdir()]
        return "\n".join(sorted(items)) if items else "(empty directory)"
    except Exception as e:
        return f"Error listing files: {e}"


def run_shell(command: str) -> str:
    """Execute a shell command with enhanced security."""
    # Expanded banned patterns
    banned = [
        "rm ", "sudo", "su ", "shutdown", "reboot", "poweroff", "halt",
        "chmod 777", "chown", "kill -9",
        ">", ">>", "|", ";", "&&", "||",  # Prevent command chaining
        "`", "$(",  # Prevent command substitution
        "mkfs", "dd if=", "dd of=", "format", "deltree",
    ]
    command_lower = command.lower()
    matched_patterns = [p for p in banned if p in command_lower]
    if matched_patterns:
        return f"Error: Command blocked for safety (contains: {matched_patterns})"

    # Whitelist approach - only allow safe commands
    safe = ["ls", "pwd", "echo", "cat", "grep", "find", "wc", "head", "tail",
            "python", "python3", "node", "npm", "git", "pytest", "black", "flake8"]
    first_word = command.split()[0] if command.split() else ""
    if first_word not in safe:
        return f"Error: Command '{first_word}' not in whitelist. Allowed: {', '.join(safe)}"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
            timeout=30,
        )
        output = result.stdout if result.stdout else ""
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[exit: {result.returncode}]"
        return output if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds."
    except Exception as e:
        return f"Error executing command: {e}"


def apply_patch(path: str, unified_diff: str) -> str:
    """Apply a unified diff patch to a file."""
    file_path = Path(path)
    if not file_path.exists():
        return f"Error: File '{path}' does not exist."
    if not file_path.is_file():
        return f"Error: '{path}' is not a file."

    try:
        original_lines = file_path.read_text().splitlines(keepends=True)
        diff_lines = unified_diff.splitlines(keepends=True)
        patched_lines = list(original_lines)

        i = 0
        while i < len(diff_lines):
            line = diff_lines[i]
            if line.startswith("@@"):
                i += 1
                hunk_lines = []
                while i < len(diff_lines) and not diff_lines[i].startswith("@@"):
                    hunk_lines.append(diff_lines[i])
                    i += 1
                i -= 1

                for hunk_line in hunk_lines:
                    if hunk_line.startswith("+"):
                        patched_lines.append(hunk_line[1:])
                    elif hunk_line.startswith("-"):
                        target = hunk_line[1:]
                        if target in patched_lines:
                            patched_lines.remove(target)
            i += 1

        file_path.write_text("".join(patched_lines))
        return f"OK: Applied patch to '{path}'"
    except Exception as e:
        return f"Error applying patch: {e}"


# Tool function mapping
TOOL_FUNCTIONS: Dict[str, Callable[..., str]] = {
    "read_file": read_file,
    "write_file": write_file,
    "list_files": list_files,
    "run_shell": run_shell,
    "apply_patch": apply_patch,
}

# Tool aliases
TOOL_ALIASES: Dict[str, str] = {
    "run_bash": "run_shell",
    "bash": "run_shell",
    "shell": "run_shell",
    "exec": "run_shell",
    "ls": "list_files",
    "cat": "read_file",
    "open": "read_file",
}

# Tool definitions in OpenAI function calling format
TOOLS_DEFINITION: List[DictType[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories in a given path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path (default: current directory '.')"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file (creates or overwrites)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to write"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Execute a shell command",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": "Apply a unified diff patch to a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to patch"
                    },
                    "unified_diff": {
                        "type": "string",
                        "description": "Unified diff format patch to apply"
                    }
                },
                "required": ["path", "unified_diff"]
            }
        }
    }
]


class ToolRegistry:
    """Registry for tool definitions and function lookup."""

    def __init__(self):
        self.tools = TOOL_FUNCTIONS.copy()
        self.aliases = TOOL_ALIASES.copy()
        self.definitions = TOOLS_DEFINITION.copy()

    def get_function(self, tool_name: str) -> Optional[Callable[..., str]]:
        """Get tool function by name, resolving aliases."""
        resolved = self.aliases.get(tool_name, tool_name)
        return self.tools.get(resolved)

    def get_definitions(self) -> List[DictType[str, Any]]:
        """Get tool definitions in OpenAI format."""
        return self.definitions
