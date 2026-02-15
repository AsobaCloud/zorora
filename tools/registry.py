"""
Central tool registry - imports all tools and provides unified interface.

All tool implementations live in submodules:
- tools/research/   — academic_search, web_search, newsroom
- tools/file_ops/   — read_file, write_file, edit_file, directory ops
- tools/shell/      — run_shell, apply_patch
- tools/specialist/ — coding, reasoning, search, intent, energy
- tools/image/      — analyze, generate, web image search
"""

from typing import Dict, Callable, List, Dict as DictType, Any, Optional

# Import research tools (from modules)
from tools.research.academic_search import academic_search
from tools.research.web_search import web_search
from tools.research.newsroom import get_newsroom_headlines

# Import file operations (from modules)
from tools.file_ops import (
    read_file,
    write_file,
    edit_file,
    make_directory,
    list_files,
    get_working_directory,
)

# Import shell operations (from modules)
from tools.shell import run_shell, apply_patch

# Import specialist tools (from modules)
from tools.specialist import (
    use_coding_agent,
    use_reasoning_model,
    use_search_model,
    use_intent_detector,
    use_nehanda,
    use_energy_analyst,  # backwards compat alias
)

# Import image tools (from modules)
from tools.image import analyze_image, generate_image, web_image_search

# Import data analysis tools (from modules)
from tools.data_analysis.execute import execute_analysis
from tools.data_analysis.nehanda_local import nehanda_query

# Tool function mapping
TOOL_FUNCTIONS: Dict[str, Callable[..., str]] = {
    # Research tools
    "academic_search": academic_search,
    "web_search": web_search,
    "get_newsroom_headlines": get_newsroom_headlines,
    # File operations
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "make_directory": make_directory,
    "list_files": list_files,
    "get_working_directory": get_working_directory,
    # Shell operations
    "run_shell": run_shell,
    "apply_patch": apply_patch,
    # Specialist tools
    "use_coding_agent": use_coding_agent,
    "use_reasoning_model": use_reasoning_model,
    "use_search_model": use_search_model,
    "use_intent_detector": use_intent_detector,
    "use_nehanda": use_nehanda,
    "use_energy_analyst": use_energy_analyst,
    # Image tools
    "analyze_image": analyze_image,
    "generate_image": generate_image,
    "web_image_search": web_image_search,
    # Data analysis tools
    "execute_analysis": execute_analysis,
    "nehanda_query": nehanda_query,
    # Convenience aliases
    "use_codestral": use_coding_agent,
    "search": use_search_model,
    "generate_code": use_coding_agent,
    "plan": use_reasoning_model,
    "pwd": get_working_directory,
}

# Tool aliases (name → canonical tool name)
TOOL_ALIASES: Dict[str, str] = {
    "run_bash": "run_shell",
    "bash": "run_shell",
    "shell": "run_shell",
    "exec": "run_shell",
    "ls": "list_files",
    "cat": "read_file",
    "open": "read_file",
    "code": "use_coding_agent",
    "use_codestral": "use_coding_agent",
    "plan": "use_reasoning_model",
    "research": "use_search_model",
}

# Tool definitions in OpenAI function calling format
TOOLS_DEFINITION: List[DictType[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "academic_search",
            "description": "Search multiple academic sources (Google Scholar, PubMed, CORE, arXiv, bioRxiv, medRxiv, PMC) and check Sci-Hub for full-text availability. Returns formatted results with citations and full-text indicators.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for academic papers"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web using Brave Search API (with DuckDuckGo fallback) for current information, news, or real-time data. Automatically routes to news search when news intent is detected.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for the web"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_newsroom_headlines",
            "description": "Fetch recent compiled news articles from Asoba newsroom via API. Returns headlines from energy, AI, blockchain, and legislation articles. Use when user asks about news, current articles, newsroom content, or wants to analyze news themes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to filter articles by relevance (optional)"
                    },
                    "days_back": {
                        "type": "integer",
                        "description": "Number of days to search back (default: 90)",
                        "default": 90
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max relevant articles to return (default: 25)",
                        "default": 25
                    }
                },
                "required": []
            }
        }
    },
    # File operations
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file with line numbers for precise editing. Returns file content with numbered lines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to read"},
                    "show_line_numbers": {"type": "boolean", "description": "If True, prefix each line with line number (default: True)", "default": True}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file (creates or overwrites).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to write"},
                    "content": {"type": "string", "description": "Content to write to the file"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit a file by replacing exact string match. You MUST read the file first with read_file before editing. The old_string must match exactly including whitespace and indentation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to edit"},
                    "old_string": {"type": "string", "description": "Exact string to find and replace (must be unique or use replace_all)"},
                    "new_string": {"type": "string", "description": "String to replace with"},
                    "replace_all": {"type": "boolean", "description": "If True, replace all occurrences (default: False)", "default": False}
                },
                "required": ["path", "old_string", "new_string"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "make_directory",
            "description": "Create a new directory (including parent directories if needed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path for the new directory"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories in a path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to list (default: current directory)", "default": "."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_working_directory",
            "description": "Get the current working directory.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    # Shell operations
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Execute a shell command with enhanced security. Uses whitelist approach - only allows safe commands.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": "Apply a unified diff patch to a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to patch"},
                    "unified_diff": {"type": "string", "description": "Unified diff content to apply"}
                },
                "required": ["path", "unified_diff"]
            }
        }
    },
    # Specialist tools
    {
        "type": "function",
        "function": {
            "name": "use_coding_agent",
            "description": "Generate or refactor code using the configured coding model with planning approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code_context": {"type": "string", "description": "Description of code to generate, existing code to refactor, or programming task to solve"}
                },
                "required": ["code_context"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "use_reasoning_model",
            "description": "Plan or reason about complex tasks. Breaks down complex problems into clear, actionable steps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Planning task, architectural decision, or complex reasoning problem"}
                },
                "required": ["task"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "use_search_model",
            "description": "Research information using search model for general knowledge questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Research query or information retrieval task"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "use_intent_detector",
            "description": "Fast intent detection to determine which tool should handle a request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_input": {"type": "string", "description": "The user's request to analyze"},
                    "recent_context": {"type": "string", "description": "Recent conversation context (optional)", "default": ""}
                },
                "required": ["user_input"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "use_nehanda",
            "description": "Analyze energy policy and regulatory compliance using Nehanda RAG.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Energy policy or regulatory compliance question"}
                },
                "required": ["query"]
            }
        }
    },
    # Image tools
    {
        "type": "function",
        "function": {
            "name": "analyze_image",
            "description": "Analyze an image using a vision-language model for OCR and content extraction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the image file"},
                    "task": {"type": "string", "description": "Description of what to do with the image (default: OCR and convert to markdown)", "default": "Convert this image to markdown format, preserving all text, tables, charts, and structure. Use OCR to extract any text."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Generate an image from a text prompt using Flux Schnell model.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Text description of the image to generate"},
                    "filename": {"type": "string", "description": "Optional filename to save image (default: auto-generated with timestamp)", "default": ""}
                },
                "required": ["prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_image_search",
            "description": "Search images using Brave Image Search API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Number of results (max 20 for free tier)", "default": 5}
                },
                "required": ["query"]
            }
        }
    },
    # Data analysis tools
    {
        "type": "function",
        "function": {
            "name": "execute_analysis",
            "description": "Execute Python code for data analysis in a sandboxed environment with access to the loaded DataFrame (df), pandas, numpy, scipy, and matplotlib.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute. Set 'result' variable for output. Has access to df, pd, np, scipy, plt."
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Session ID (default: empty string for default session)",
                        "default": ""
                    }
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "nehanda_query",
            "description": "Search local policy corpus using vector similarity for energy policy and regulatory documents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for policy documents"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of top results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
]

SPECIALIST_TOOLS = [
    "deep_research",
    "use_coding_agent",
    "use_reasoning_model",
    "use_search_model",
    "use_intent_detector",
    "analyze_image",
    "generate_image",
    "academic_search",
    "execute_analysis",
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
