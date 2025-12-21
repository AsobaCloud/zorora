"""Hardcoded research workflow for multi-source synthesis.

No complex planning - just a fixed, reliable pipeline:
1. Fetch newsroom (if available)
2. Web search
3. Synthesize with citations
"""

import logging
import re
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class ResearchWorkflow:
    """
    Fixed pipeline for research queries.

    Philosophy:
    - Deterministic, not LLM-orchestrated
    - Always tries multiple sources
    - Automatic citation formatting
    - Simple error handling (skip failed sources)
    """

    def __init__(self, tool_executor, llm_client=None):
        """
        Initialize research workflow.

        Args:
            tool_executor: ToolExecutor for running tools
            llm_client: Optional LLMClient for synthesis
        """
        self.tool_executor = tool_executor
        self.llm_client = llm_client

    def execute(self, query: str, ui=None) -> str:
        """
        Execute research workflow.

        Pipeline:
        1. Fetch newsroom headlines (try, skip if unavailable)
        2. Web search (always)
        3. Synthesize both sources with citations

        Args:
            query: User's research question
            ui: Optional UI for progress feedback

        Returns:
            Synthesized answer with citations
        """
        logger.info(f"Starting research workflow for: {query[:80]}...")

        sources: List[Tuple[str, str]] = []

        # Step 1: Try newsroom (with query filtering)
        if ui:
            ui.console.print("\n[cyan]Step 1/3:[/cyan] Fetching relevant newsroom articles...")

        newsroom_result = self._fetch_newsroom(query)
        if newsroom_result:
            sources.append(("Newsroom", newsroom_result))
            if ui:
                ui.console.print(f"[green]  ✓ Found {self._count_articles(newsroom_result)} relevant articles[/green]")
        else:
            if ui:
                ui.console.print("[yellow]  ⚠ Newsroom unavailable, skipping[/yellow]")
            logger.warning("Newsroom fetch failed, continuing with web only")

        # Step 2: Web search (always)
        if ui:
            ui.console.print("\n[cyan]Step 2/3:[/cyan] Searching web...")

        search_query = self._extract_search_keywords(query)
        web_result = self._fetch_web(search_query)

        if web_result and not web_result.startswith("Error:"):
            sources.append(("Web", web_result))
            if ui:
                ui.console.print(f"[green]  ✓ Found web results[/green]")
        else:
            if ui:
                ui.console.print("[red]  ✗ Web search failed[/red]")
            logger.error(f"Web search failed: {web_result}")

        # Step 3: Synthesize
        if not sources:
            return "Error: Could not fetch any sources. Please check newsroom and web search availability."

        if ui:
            ui.console.print("\n[cyan]Step 3/3:[/cyan] Synthesizing findings...")

        result = self._synthesize(query, sources)

        if ui:
            ui.console.print("[green]  ✓ Research complete[/green]\n")

        return result

    def _fetch_newsroom(self, query: str) -> Optional[str]:
        """
        Fetch newsroom headlines filtered by query relevance.

        Args:
            query: Search query for relevance filtering

        Returns:
            Headlines string, or None if unavailable
        """
        try:
            result = self.tool_executor.execute("get_newsroom_headlines", {"query": query})
            if result and not result.startswith("Error:"):
                logger.info(f"Newsroom fetched: {len(result)} chars")
                return result
            else:
                logger.warning(f"Newsroom error: {result[:100]}")
                return None
        except Exception as e:
            logger.error(f"Newsroom fetch exception: {e}")
            return None

    def _fetch_web(self, search_query: str) -> Optional[str]:
        """
        Execute web search.

        Args:
            search_query: Extracted keywords for search

        Returns:
            Search results string
        """
        try:
            result = self.tool_executor.execute("web_search", {"query": search_query})
            logger.info(f"Web search completed: {len(result)} chars")
            return result
        except Exception as e:
            logger.error(f"Web search exception: {e}")
            return f"Error: {e}"

    def _extract_search_keywords(self, query: str) -> str:
        """
        Extract searchable keywords from query.

        Simple heuristic:
        - Remove question words (what, why, how, etc.)
        - Remove common filler words
        - Keep nouns and key terms

        Args:
            query: Original user query

        Returns:
            Cleaned search query
        """
        # Remove question words and common filler
        stopwords = [
            "what", "why", "how", "when", "where", "who",
            "are", "is", "the", "a", "an", "of", "in", "on", "at",
            "based on", "using", "from", "newsroom", "web search",
            "tell me about", "explain", "describe"
        ]

        cleaned = query.lower()
        for word in stopwords:
            cleaned = re.sub(rf'\b{re.escape(word)}\b', '', cleaned, flags=re.IGNORECASE)

        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # If too short, use original
        if len(cleaned) < 10:
            cleaned = query

        logger.info(f"Search keywords: {cleaned}")
        return cleaned

    def _count_articles(self, newsroom_text: str) -> int:
        """Count articles in newsroom result."""
        # Simple heuristic: count headlines or metadata blocks
        return len(re.findall(r'##|Title:', newsroom_text))

    def _synthesize(self, query: str, sources: List[Tuple[str, str]]) -> str:
        """
        Synthesize findings from multiple sources.

        Args:
            query: Original user query
            sources: List of (source_name, content) tuples

        Returns:
            Synthesized answer with citations and source URLs
        """
        import re

        # Extract URLs from sources for citations
        source_urls = []

        # Build synthesis prompt
        sources_text = ""
        for source_name, content in sources:
            # Extract URLs from content before truncation
            if source_name == "Web":
                # Extract all URLs from web search results
                url_pattern = r'URL: (https?://[^\s]+)'
                urls = re.findall(url_pattern, content)
                for url in urls[:5]:  # Keep top 5 URLs
                    source_urls.append(f"[Web] {url}")
            elif source_name == "Newsroom":
                # Extract URLs from newsroom results
                url_pattern = r'URL: (https?://[^\s]+)'
                urls = re.findall(url_pattern, content)
                for url in urls[:5]:  # Keep top 5 URLs
                    source_urls.append(f"[Newsroom] {url}")

            # Truncate long content but keep URLs accessible
            truncated = content[:5000] + "..." if len(content) > 5000 else content
            sources_text += f"\n\n[{source_name}]:\n{truncated}"

        from datetime import datetime
        current_date = datetime.now().strftime("%B %d, %Y")

        synthesis_prompt = f"""You are a research analyst synthesizing findings from multiple sources.

IMPORTANT: Today's date is {current_date}. When interpreting dates like "6 months ago", calculate from today's date.

SOURCES:
{sources_text}

RESEARCH QUESTION:
{query}

INSTRUCTIONS:
1. Synthesize key findings from ALL sources above
2. Cite sources inline using [Newsroom] or [Web] tags after each claim
3. When citing web results, mention the domain/site name when relevant
4. Be concise but comprehensive
5. Focus on answering the specific question
6. If sources conflict, note the discrepancy
7. Structure your answer with clear sections if covering multiple topics
8. Use the current date ({current_date}) when interpreting temporal references

ANSWER:"""

        if not self.llm_client:
            # No LLM available - just concatenate sources
            result = f"Research findings:\n{sources_text}"
            if source_urls:
                result += "\n\n## Sources:\n" + "\n".join(source_urls)
            return result

        try:
            response = self.llm_client.chat_complete(
                [{"role": "user", "content": synthesis_prompt}],
                tools=None
            )
            answer = self.llm_client.extract_content(response)

            # Always add source URLs at the end
            if source_urls:
                answer += "\n\n## Sources:\n" + "\n".join(source_urls)
            elif sources:
                # Fallback: at least list source names
                source_names = [name for name, _ in sources]
                answer += f"\n\nSources: {', '.join(source_names)}"

            return answer.strip()

        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            result = f"Error synthesizing results: {e}\n\nRaw sources:\n{sources_text}"
            if source_urls:
                result += "\n\n## Sources:\n" + "\n".join(source_urls)
            return result
