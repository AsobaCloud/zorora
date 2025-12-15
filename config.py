"""Configuration constants and settings."""

from pathlib import Path

# LM Studio API Configuration (OpenAI-compatible)
API_URL = "http://localhost:1234/v1/chat/completions"
MODEL = "essentialai/rnj-1"
MAX_TOKENS = 2048  # Increased from 1000 for longer responses
TIMEOUT = 60  # Increased from 30s for complex tool operations
TEMPERATURE = 0.2

# Context Management
MAX_CONTEXT_MESSAGES = 50  # Changed from None (unlimited) to prevent context overflow

# Tool Configuration
TOOL_CHOICE = "auto"  # "auto", "required", "none", or {"type": "function", "function": {"name": "..."}}
PARALLEL_TOOL_CALLS = True  # Enable parallel tool execution

# Logging Configuration
import logging
LOGGING_LEVEL = logging.INFO
LOGGING_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = Path(__file__).parent / "repl.log"

# UI Configuration
UI_ENABLED = True  # Master switch for rich UI
UI_NO_COLOR = False  # Accessibility mode (respects NO_COLOR env var)
UI_MARKDOWN_RENDERING = True  # Render markdown in responses
UI_SYNTAX_HIGHLIGHTING = True  # Syntax highlight code blocks
UI_SPINNER_STYLE = "dots"  # Spinner animation: dots, line, arc, etc.
UI_SHOW_TOKEN_COUNT = True  # Display token usage in loading animation
UI_THEME = "monokai"  # Pygments theme for syntax highlighting

# System Prompt
SYSTEM_PROMPT_FILE = Path(__file__).parent / "system_prompt.txt"


def load_system_prompt() -> str:
    """Load system prompt from file."""
    if SYSTEM_PROMPT_FILE.exists():
        return SYSTEM_PROMPT_FILE.read_text().strip()
    return """You are a local coding assistant with tool access.

Rules:
- Use tools when you need filesystem information (files, directories, file contents).
- After a tool result is provided, respond naturally to the user's question.
- Be concise and direct in your responses.
"""


