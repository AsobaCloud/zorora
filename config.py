"""Configuration constants and settings."""

from pathlib import Path

# LM Studio API Configuration (OpenAI-compatible)
API_URL = "http://localhost:1234/v1/chat/completions"
MODEL = "qwen/qwen3-4b-2507"  # Regular model - fast and decisive
MAX_TOKENS = 2048  # Increased from 1000 for longer responses
TIMEOUT = 60  # Increased from 30s for complex tool operations
TEMPERATURE = 0.2

# Specialized Model Configuration
SPECIALIZED_MODELS = {
    "codestral": {
        "model": "qwen/qwen3-4b-thinking-2507",
        "max_tokens": 4096,
        "temperature": 0.3,
        "timeout": 90,
    },
    "reasoning": {
        "model": "qwen/qwen3-4b-thinking-2507",
        "max_tokens": 3072,
        "temperature": 0.4,
        "timeout": 90,
    },
    "search": {
        "model": "qwen/qwen3-4b-thinking-2507",
        "max_tokens": 2048,
        "temperature": 0.5,
        "timeout": 60,
    }
}

# External API Configuration
ENERGY_ANALYST = {
    "endpoint": "http://localhost:8000",  # Local or Production endpoint
    "timeout": 180,  # 3 minutes for slower LLM inference
    "enabled": True,  # Set to False to disable energy analyst tool
}
# Available endpoints:
# - Local: http://localhost:8000
# - Production: https://energyanalystragservice-production.up.railway.app

# Context Management
MAX_CONTEXT_MESSAGES = 50  # Changed from None (unlimited) to prevent context overflow

# Tool Configuration
TOOL_CHOICE = "required"  # Force tool usage - was "auto"
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


