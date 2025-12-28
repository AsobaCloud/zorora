"""
Central tool registry - imports all tools and provides unified interface.
Replaces monolithic tool_registry.py with modular structure.

Phase 1: Research tools migrated to tools/research/
Phase 2+: Other tools will be migrated incrementally
"""

from typing import Dict, Callable, List, Dict as DictType, Any, Optional

# Import research tools (NEW - from modules)
from tools.research.academic_search import academic_search
from tools.research.web_search import web_search
from tools.research.newsroom import get_newsroom_headlines

# Import all other tools from legacy tool_registry (will migrate later)
# Use tool_registry_legacy to avoid circular import with shim
from tool_registry_legacy import (
    # File operations
    read_file,
    write_file,
    edit_file,
    make_directory,
    list_files,
    get_working_directory,
    
    # Image tools
    analyze_image,
    generate_image,
    
    # Shell operations
    run_shell,
    apply_patch,
    
    # Specialist models
    use_codestral,
    use_reasoning_model,
    use_search_model,
    use_intent_detector,
    use_energy_analyst,
    
    # Other search tools
    web_image_search,
    
    # Tool registry structures
    TOOL_FUNCTIONS as LEGACY_TOOL_FUNCTIONS,
    TOOL_ALIASES as LEGACY_TOOL_ALIASES,
    TOOLS_DEFINITION as LEGACY_TOOLS_DEFINITION,
    SPECIALIST_TOOLS as LEGACY_SPECIALIST_TOOLS,
    ToolRegistry as LegacyToolRegistry,
)

# Build new TOOL_FUNCTIONS dict
# Research tools (NEW - from modules)
TOOL_FUNCTIONS: Dict[str, Callable[..., str]] = {
    "academic_search": academic_search,
    "web_search": web_search,
    "get_newsroom_headlines": get_newsroom_headlines,
}

# Add all other tools from legacy registry
for tool_name, tool_func in LEGACY_TOOL_FUNCTIONS.items():
    # Skip research tools (already added above)
    if tool_name not in ["academic_search", "web_search", "get_newsroom_headlines"]:
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
]

# Add all other tool definitions from legacy registry
for tool_def in LEGACY_TOOLS_DEFINITION:
    tool_name = tool_def.get("function", {}).get("name", "")
    # Skip research tools (already added above)
    if tool_name not in ["academic_search", "web_search", "get_newsroom_headlines"]:
        TOOLS_DEFINITION.append(tool_def)

# Build new SPECIALIST_TOOLS list
SPECIALIST_TOOLS = [
    "deep_research",  # Will be added in Phase 3
    "use_codestral",
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
