"""Hardcoded research workflow for multi-source synthesis.

No complex planning - just a fixed, reliable pipeline:
1. Fetch newsroom (if available)
2. Web search
3. Synthesize with citations
"""

import logging
import re
import uuid
import time
import threading
from typing import List, Tuple, Optional

from ui.progress_events import ProgressEvent, EventType

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

        # Generate workflow node ID
        workflow_id = f"workflow_{uuid.uuid4().hex[:8]}"

        # Start progress display
        if ui:
            with ui.progress(f"Research: {query[:60]}...") as progress:
                # Emit workflow start
                progress.emit(ProgressEvent(
                    event_type=EventType.WORKFLOW_START,
                    message=f"Research: {query[:60]}...",
                    parent_id=None,
                    metadata={"workflow_id": workflow_id, "query": query}
                ))

                sources: List[Tuple[str, str]] = []

                # Step 1: Try newsroom
                step1_id = f"step1_{uuid.uuid4().hex[:8]}"
                progress.emit(ProgressEvent(
                    event_type=EventType.STEP_START,
                    message="Step 1/3: Fetching newsroom articles...",
                    parent_id=workflow_id,
                    metadata={"node_id": step1_id, "step": 1}
                ))

                newsroom_result = self._fetch_newsroom(query)
                if newsroom_result:
                    sources.append(("Newsroom", newsroom_result))
                    article_count = self._count_articles(newsroom_result)
                    progress.emit(ProgressEvent(
                        event_type=EventType.STEP_COMPLETE,
                        message=f"Found {article_count} relevant articles",
                        parent_id=workflow_id,
                        metadata={"node_id": step1_id, "article_count": article_count}
                    ))
                else:
                    progress.emit(ProgressEvent(
                        event_type=EventType.STEP_ERROR,
                        message="Newsroom unavailable (API 401) - skipping",
                        parent_id=workflow_id,
                        metadata={"node_id": step1_id}
                    ))
                    logger.warning("Newsroom fetch failed, continuing with web only")

                # Step 2: Web search
                step2_id = f"step2_{uuid.uuid4().hex[:8]}"
                progress.emit(ProgressEvent(
                    event_type=EventType.STEP_START,
                    message="Step 2/3: Searching web...",
                    parent_id=workflow_id,
                    metadata={"node_id": step2_id, "step": 2}
                ))

                search_query = self._extract_search_keywords(query)
                web_result = self._fetch_web(search_query)

                if web_result and not web_result.startswith("Error:"):
                    sources.append(("Web", web_result))
                    progress.emit(ProgressEvent(
                        event_type=EventType.STEP_COMPLETE,
                        message="Found web results",
                        parent_id=workflow_id,
                        metadata={"node_id": step2_id}
                    ))
                else:
                    progress.emit(ProgressEvent(
                        event_type=EventType.STEP_ERROR,
                        message="Web search failed",
                        parent_id=workflow_id,
                        metadata={"node_id": step2_id}
                    ))
                    logger.error(f"Web search failed: {web_result}")

                # Step 3: Synthesize
                if not sources:
                    progress.emit(ProgressEvent(
                        event_type=EventType.WORKFLOW_COMPLETE,
                        message="Error: No sources available",
                        parent_id=None,
                        metadata={"workflow_id": workflow_id, "error": True}
                    ))
                    return "Error: Could not fetch any sources. Please check newsroom and web search availability."

                step3_id = f"step3_{uuid.uuid4().hex[:8]}"
                progress.emit(ProgressEvent(
                    event_type=EventType.STEP_START,
                    message="Step 3/3: Synthesizing findings... This may take 15-25 seconds.",
                    parent_id=workflow_id,
                    metadata={"node_id": step3_id, "step": 3}
                ))

                # Emit periodic updates during synthesis
                synthesis_done = threading.Event()
                synthesis_start_time = time.time()
                
                def emit_heartbeat():
                    """Emit periodic heartbeat messages during synthesis."""
                    heartbeat_count = 0
                    messages = [
                        "Analyzing sources and generating synthesis...",
                        "Processing findings and cross-referencing...",
                        "Generating comprehensive answer with citations...",
                        "Finalizing synthesis..."
                    ]
                    while not synthesis_done.wait(5):  # Update every 5 seconds
                        heartbeat_count += 1
                        if heartbeat_count <= len(messages):
                            progress.emit(ProgressEvent(
                                event_type=EventType.MESSAGE,
                                message=messages[heartbeat_count - 1],
                                parent_id=workflow_id,
                                metadata={"node_id": step3_id, "heartbeat": heartbeat_count}
                            ))
                        else:
                            # After all messages, just show elapsed time
                            elapsed = int(time.time() - synthesis_start_time)
                            progress.emit(ProgressEvent(
                                event_type=EventType.MESSAGE,
                                message=f"Still synthesizing... ({elapsed}s elapsed)",
                                parent_id=workflow_id,
                                metadata={"node_id": step3_id, "heartbeat": heartbeat_count}
                            ))
                
                heartbeat_thread = threading.Thread(target=emit_heartbeat, daemon=True)
                heartbeat_thread.start()
                
                try:
                    result = self._synthesize(query, sources)
                finally:
                    synthesis_done.set()
                    heartbeat_thread.join(timeout=1)

                progress.emit(ProgressEvent(
                    event_type=EventType.STEP_COMPLETE,
                    message="Synthesis complete",
                    parent_id=workflow_id,
                    metadata={"node_id": step3_id}
                ))

                progress.emit(ProgressEvent(
                    event_type=EventType.WORKFLOW_COMPLETE,
                    message="Research complete",
                    parent_id=None,
                    metadata={"workflow_id": workflow_id}
                ))

                return result
        else:
            # No UI - fallback to old behavior
            sources: List[Tuple[str, str]] = []
            newsroom_result = self._fetch_newsroom(query)
            if newsroom_result:
                sources.append(("Newsroom", newsroom_result))
            search_query = self._extract_search_keywords(query)
            web_result = self._fetch_web(search_query)
            if web_result and not web_result.startswith("Error:"):
                sources.append(("Web", web_result))
            if not sources:
                return "Error: Could not fetch any sources."
            result = self._synthesize(query, sources)
            return result

    def _fetch_newsroom(self, query: str) -> Optional[str]:
        """
        Fetch newsroom articles from cache for semantic filtering at synthesis.

        Returns all cached articles as summaries - the LLM will filter
        for relevance during synthesis.

        Args:
            query: Search query (used for logging only)

        Returns:
            Article summaries string, or None if unavailable
        """
        try:
            from tools.research.newsroom import fetch_newsroom_cached

            articles = fetch_newsroom_cached(max_results=100)

            if not articles:
                logger.warning("No articles in newsroom cache")
                return None

            # Format articles as summaries for LLM to filter
            summaries = []
            for art in articles:
                headline = art.get('headline', 'No headline')
                topics = ', '.join(art.get('topic_tags', [])[:3]) or 'No topics'
                date = art.get('date', '')[:10]
                url = art.get('url', '')
                source = art.get('source', 'Unknown')
                summaries.append(f"- [{date}] {headline}\n  Topics: {topics}\n  Source: {source}\n  URL: {url}")

            result = "\n\n".join(summaries)
            logger.info(f"Newsroom: {len(articles)} articles fetched from cache")
            return result

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
1. First, identify which Newsroom articles are semantically relevant to the research question
   - The Newsroom contains many articles; only use those actually related to the query
   - Consider topic relevance, not just keyword matches
   - Ignore irrelevant articles completely
2. Synthesize findings from the RELEVANT newsroom articles and web results
3. Cite sources inline using [Newsroom] or [Web] tags after each claim
4. When citing web results, mention the domain/site name when relevant
5. Be concise but comprehensive - focus on answering the specific question
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
