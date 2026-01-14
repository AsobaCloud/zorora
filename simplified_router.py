"""Simplified deterministic router for research-focused queries.

No LLM, no complex pattern matching - just clear decision tree.
"""

import re
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SimplifiedRouter:
    """
    Deterministic routing for research-focused workflows.

    Decision tree:
    1. File operations? → execute directly
    2. Research query? → multi-source workflow
    3. Code generation? → codestral
    4. Simple Q&A → reasoning model
    """

    def __init__(self):
        """Initialize router."""
        pass

    def route(self, user_input: str) -> Dict[str, Any]:
        """
        Route user input to appropriate workflow.

        Args:
            user_input: User's query

        Returns:
            Dict with:
                - workflow: "file_op" | "research" | "code" | "qa"
                - action: Specific action to take
                - confidence: Always 1.0 (deterministic)
        """
        user_lower = user_input.lower()

        # 1. File operations (highest priority - most specific)
        file_result = self._check_file_operation(user_lower, user_input)
        if file_result:
            return file_result

        # 2. Code generation (explicit keywords)
        if self._is_code_request(user_lower):
            logger.info("Routing to code generation (coding_agent)")
            return {
                "workflow": "code",
                "action": "generate_code",
                "tool": "use_coding_agent",
                "confidence": 1.0
            }

        # 3. Everything else: Research query (multi-source with web search)
        # Default to research instead of reasoning model to avoid outdated info
        logger.info("Routing to research workflow (newsroom + web + synthesis)")
        return {
            "workflow": "research",
            "action": "multi_source_research",
            "confidence": 1.0
        }

    def _check_file_operation(self, user_lower: str, original: str) -> Optional[Dict[str, Any]]:
        """
        Check if this is a file operation.

        Returns routing dict if file op, None otherwise.
        """
        # Read file patterns
        read_patterns = [
            r'\b(read|show|display|view|cat|open)\b.*\b(file|research|notes?)\b',
            r'\b(show|list)\b.*\b(my|saved|past)\b.*\b(research|findings|notes?)\b',
            r'\bwhat.*(?:research|notes?).*(?:have|saved)\b',
        ]

        for pattern in read_patterns:
            if re.search(pattern, user_lower):
                logger.info("Routing to file read operation")
                return {
                    "workflow": "file_op",
                    "action": "read_file",
                    "tool": "read_file",
                    "confidence": 1.0
                }

        # List files patterns
        list_patterns = [
            r'\b(list|show)\b.*\b(files|research|saved)\b',
            r'\bwhat.*(?:files|research).*(?:do i have|saved)\b',
        ]

        for pattern in list_patterns:
            if re.search(pattern, user_lower):
                logger.info("Routing to list files operation")
                return {
                    "workflow": "file_op",
                    "action": "list_files",
                    "tool": "list_files",
                    "confidence": 1.0
                }

        # Write/save file patterns
        write_patterns = [
            r'\b(save|write|store)\b.*\b(this|research|findings?|notes?)\b',
            r'\b(save|write|store)\b.*\b(to|as)\b',
            r'\bcreate.*\b(file|research note|notes?)\b',
        ]

        for pattern in write_patterns:
            if re.search(pattern, user_lower):
                logger.info("Routing to file write operation")
                return {
                    "workflow": "file_op",
                    "action": "write_file",
                    "tool": "write_file",
                    "confidence": 1.0
                }

        return None

    def _is_code_request(self, user_lower: str) -> bool:
        """
        Check if this is a code generation request.

        Looks for explicit code-related keywords.
        """
        code_patterns = [
            r'\b(write|generate|create|build)\b.*\b(code|script|function|program)\b',
            r'\b(write|create)\b.*\b(python|javascript|typescript|rust|go)\b',
            r'\bimplement\b.*\b(function|class|algorithm)\b',
            r'\bcode\s+(to|for|that)\b',
            r'\bpython\s+script\b',
        ]

        return any(re.search(pattern, user_lower) for pattern in code_patterns)

    def _is_research_query(self, user_lower: str) -> bool:
        """
        Check if this is a research query requiring multi-source synthesis.

        Research indicators:
        - Mentions multiple sources (newsroom, web, search)
        - Current events / trends / themes
        - "What are", "What is", "Tell me about" + current topics
        - Explicit research language
        """
        # Multi-source indicators (highest confidence)
        multi_source_patterns = [
            r'\b(based on|using|from)\b.*(newsroom|web|search|sources?)',
            r'\b(newsroom|headlines?).*(and|as well as|with|plus).*(web|search)',
            r'\b(search|web).*(and|as well as|with|plus).*(newsroom|headlines?)',
        ]

        for pattern in multi_source_patterns:
            if re.search(pattern, user_lower):
                logger.info(f"Multi-source research detected: {pattern}")
                return True

        # Research language indicators
        research_patterns = [
            r'\b(what are|what is).*(trend|theme|development|happening|latest|current)',
            r'\b(tell me about|explain|summarize).*(recent|current|latest|2024|2025)',
            r'\blatest\b.*(news|information|developments?|trends?)',
            r'\bcurrent\b.*(state|trends?|themes?|developments?)',
            r'\bmajor\s+(themes?|trends?|developments?|issues?)',
            r'\b(research|analyze|investigate)\b',
        ]

        for pattern in research_patterns:
            if re.search(pattern, user_lower):
                logger.info(f"Research query detected: {pattern}")
                return True

        # Newsroom/news indicators
        if re.search(r'\b(newsroom|headlines?|news|today\'s|todays)\b', user_lower):
            logger.info("Newsroom query detected")
            return True

        return False
