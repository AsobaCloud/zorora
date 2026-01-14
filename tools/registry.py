"""
Central tool registry - imports all tools and provides unified interface.
Replaces monolithic tool_registry.py with modular structure.

Migration complete:
- Phase 1: Research tools → tools/research/
- Phase 2: File operations → tools/file_ops/
- Phase 3: Shell operations → tools/shell/
- Phase 4: Specialist tools → tools/specialist/
- Phase 5: Image tools → tools/image/

The legacy tool_registry_legacy.py is kept for backward compatibility
with any code that still imports from it directly.
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
    use_energy_analyst,
)

# Import image tools (from modules)
from tools.image import analyze_image, generate_image, web_image_search

# Import remaining tools from legacy (only registry structures now)
from tool_registry_legacy import (
    # Tool registry structures
    TOOL_FUNCTIONS as LEGACY_TOOL_FUNCTIONS,
    TOOL_ALIASES as LEGACY_TOOL_ALIASES,
    TOOLS_DEFINITION as LEGACY_TOOLS_DEFINITION,
    SPECIALIST_TOOLS as LEGACY_SPECIALIST_TOOLS,
    ToolRegistry as LegacyToolRegistry,
)

# Build new TOOL_FUNCTIONS dict
# Research tools (from modules)
TOOL_FUNCTIONS: Dict[str, Callable[..., str]] = {
    "academic_search": academic_search,
    "web_search": web_search,
    "get_newsroom_headlines": get_newsroom_headlines,
    # File operations (from modules)
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "make_directory": make_directory,
    "list_files": list_files,
    "get_working_directory": get_working_directory,
    # Shell operations (from modules)
    "run_shell": run_shell,
    "apply_patch": apply_patch,
    # Specialist tools (from modules)
    "use_coding_agent": use_coding_agent,
    "use_reasoning_model": use_reasoning_model,
    "use_search_model": use_search_model,
    "use_intent_detector": use_intent_detector,
    "use_energy_analyst": use_energy_analyst,
    # Image tools (from modules)
    "analyze_image": analyze_image,
    "generate_image": generate_image,
    "web_image_search": web_image_search,
}

# Tools migrated to modules (skip when copying from legacy)
MIGRATED_TOOLS = [
    "academic_search", "web_search", "get_newsroom_headlines",  # research
    "read_file", "write_file", "edit_file", "make_directory", "list_files", "get_working_directory",  # file_ops
    "run_shell", "apply_patch",  # shell
    "use_coding_agent", "use_reasoning_model", "use_search_model", "use_intent_detector", "use_energy_analyst",  # specialist
    "analyze_image", "generate_image", "web_image_search",  # image
]

# Add remaining tools from legacy registry
for tool_name, tool_func in LEGACY_TOOL_FUNCTIONS.items():
    if tool_name not in MIGRATED_TOOLS:
        TOOL_FUNCTIONS[tool_name] = tool_func

# Build new TOOL_ALIASES dict (copy from legacy)
TOOL_ALIASES: Dict[str, str] = LEGACY_TOOL_ALIASES.copy()

# Build new TOOLS_DEFINITION list
# Start with research tool definitions (NEW)
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
    # File operations (from modules)
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
    # Shell operations (from modules)
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
    # Specialist tools (from modules)
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
            "name": "use_energy_analyst",
            "description": "Analyze energy policy and regulatory compliance using EnergyAnalyst RAG.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Energy policy or regulatory compliance question"}
                },
                "required": ["query"]
            }
        }
    },
    # Image tools (from modules)
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
]

# Add remaining tool definitions from legacy registry
for tool_def in LEGACY_TOOLS_DEFINITION:
    tool_name = tool_def.get("function", {}).get("name", "")
    # Skip migrated tools (already added above)
    if tool_name not in MIGRATED_TOOLS:
        TOOLS_DEFINITION.append(tool_def)

# Build new SPECIALIST_TOOLS list
SPECIALIST_TOOLS = [
    "deep_research",  # Will be added in Phase 3
    "use_coding_agent",
    "use_reasoning_model",
    "use_search_model",
    "use_intent_detector",  # Internal routing tool (not shown to user)
    "analyze_image",
    "generate_image",
    "academic_search",  # Returns formatted academic results directly
]

# ToolRegistry class (same interface as legacy)
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
