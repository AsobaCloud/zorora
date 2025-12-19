"""Heuristic routing layer for fast, keyword-based tool selection."""

from typing import Optional, Dict, Any
import re
import logging

logger = logging.getLogger(__name__)


class HeuristicRouter:
    """Fast keyword-based routing before LLM."""

    # Keyword patterns mapped to tools
    # Patterns are tried in order - first match wins
    PATTERNS = {
        "get_working_directory": [
            r'\b(what is|what\'s|show me|tell me)\b.*\b(current|working)\s+(directory|folder|path|dir)\b',
            r'\b(current|working)\s+(directory|folder|path|dir)\b',
            r'\bpwd\b',
        ],
        "web_search": [
            r'\b(search|google|find|lookup|latest|current|news|today|now)\b.*\b(news|information|article|update|today)\b',
            r'\b(what\'s|what is|whats)\b.*\b(latest|current|new|happening|today)\b.*\b(news|information|article|update)\b',
            r'\b(search for|look up|find out)\b',
        ],
        "use_codestral": [
            r'\b(write|create|generate|implement|code|build)\b.*\b(function|class|script|program|code|module|component)\b',
            r'\b(fix|debug|refactor|optimize|improve)\b.*\b(code|bug|error|function|script)\b',
            r'\b(add|update|modify|change)\b.*\b(function|class|method|code|feature)\b',
            r'\b(implement|create)\b.*\b(api|endpoint|route|handler)\b',
        ],
        "use_reasoning_model": [
            r'\b(plan|design|architect|analyze|think|strategy|approach)\b',
            r'\b(how should|what approach|best way|how to)\b.*\b(implement|design|build|structure)\b',
            r'\b(pros and cons|tradeoffs|compare|evaluate)\b',
            r'\b(explain|analyze)\b.*\b(architecture|system|design)\b',
        ],
        "read_file": [
            r'\b(read|show|display|view|cat|open|see)\b.*\.(py|js|md|txt|json|yaml|yml|sh|ts|html|css|rs|go|java|c|cpp|h|hpp)',
            r'\b(what\'s in|contents of|show me)\b.*\.(py|js|md|txt|json|yaml|yml|sh|ts|html|css|rs|go|java)',
            r'\b(show|display)\b.*\b(config|readme|file)\b',
        ],
        "write_file": [
            r'\b(write|save|store|create|put)\b.*\b(to|in|as)\b.*\.(py|js|md|txt|json|yaml|yml|sh|ts|html|css|rs|go|java)',
            r'\b(save this|write this|create file)\b',
        ],
        "edit_file": [
            r'\b(edit|modify|change|update|replace|fix)\b.*\b(in|the)\b.*\.(py|js|md|txt|json|yaml|yml|sh|ts|html|css|rs|go|java)',
            r'\b(change|replace|update)\b.*\b(to|with|from)\b',
            r'\b(fix|correct)\b.*\b(typo|error|mistake)\b',
        ],
        "make_directory": [
            r'\b(make|create|mkdir)\b.*\b(directory|folder|dir)\b',
            r'\b(create|make)\b.*\b(folder|directory)\b',
        ],
        "list_files": [
            r'\b(list|ls|dir|show)\b.*\b(files|directory|folder|contents)\b',
            r'\b(what files|show files|see files)\b',
        ],
        "run_shell": [
            r'\b(run|execute|exec)\b.*\b(command|shell|bash|test|tests)\b',
            r'\b(git|npm|pip|docker|kubectl|cargo|go|make)\b\s+\w+',
            r'\b(install|build|test|deploy)\b.*\b(package|dependencies|project)\b',
        ],
        "use_energy_analyst": [
            r'\b(FERC|ISO|NEM|tariff|tariffs)\b',
            r'\b(energy policy|grid|utility|power)\b.*\b(regulatory|compliance|interconnection)\b',
            r'\bOrder \d{4}\b',  # FERC orders like "Order 2222"
        ],
        "generate_image": [
            r'\b(generate|create|make|draw|produce)\b.*\b(image|picture|photo|illustration|graphic|visual)\b',
            r'\b(image of|picture of|illustration of)\b',
        ],
        "use_search_model": [
            r'\b(explain|what is|what are|tell me about|describe)\b',
            r'\b(how does|how do|why does|why do)\b.*\b(work|function|operate)\b',
        ],
    }

    def route(self, user_input: str) -> Optional[Dict[str, Any]]:
        """
        Attempt heuristic routing based on keywords.

        Args:
            user_input: User's request

        Returns:
            Dict with 'tool', 'input', 'confidence' if matched, None otherwise
        """
        user_lower = user_input.lower()

        # Track all matches with priority
        # First match wins (patterns are ordered by specificity)
        for tool, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, user_lower):
                    logger.info(f"Heuristic match: {tool} (pattern: {pattern[:50]}...)")
                    return {
                        "tool": tool,
                        "input": user_input,
                        "confidence": 0.95  # High confidence for pattern match
                    }

        # No matches → defer to LLM
        logger.info("No heuristic match found, deferring to LLM")
        return None

    def add_pattern(self, tool: str, pattern: str):
        """
        Add a custom pattern for a tool.

        Args:
            tool: Tool name
            pattern: Regex pattern to match
        """
        if tool not in self.PATTERNS:
            self.PATTERNS[tool] = []
        self.PATTERNS[tool].append(pattern)
        logger.info(f"Added pattern for {tool}: {pattern}")

    def remove_pattern(self, tool: str, pattern: str):
        """
        Remove a pattern from a tool.

        Args:
            tool: Tool name
            pattern: Regex pattern to remove
        """
        if tool in self.PATTERNS and pattern in self.PATTERNS[tool]:
            self.PATTERNS[tool].remove(pattern)
            logger.info(f"Removed pattern for {tool}: {pattern}")

    def get_patterns(self, tool: str) -> list:
        """
        Get all patterns for a tool.

        Args:
            tool: Tool name

        Returns:
            List of regex patterns
        """
        return self.PATTERNS.get(tool, [])
