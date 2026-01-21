"""Digest workflow - generates news trend analysis from newsroom by continent."""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


class DigestWorkflow:
    """Generates news trend digest organized by continent with no article repetition."""

    CONTINENT_TAGS = ["Africa", "Americas", "Asia", "Europe", "Middle East", "Oceania", "Global"]
    ARTICLES_PER_CONTINENT = 6

    # Mapping of geography tags to continents
    GEOGRAPHY_TO_CONTINENT = {
        # Africa
        "Africa": "Africa",
        "North Africa": "Africa",
        "Sub-Saharan Africa": "Africa",
        "East Africa": "Africa",
        "West Africa": "Africa",
        "Southern Africa": "Africa",
        "Central Africa": "Africa",
        # Americas
        "Americas": "Americas",
        "North America": "Americas",
        "South America": "Americas",
        "Latin America": "Americas",
        "Central America": "Americas",
        "Caribbean": "Americas",
        # Asia
        "Asia": "Asia",
        "East Asia": "Asia",
        "Southeast Asia": "Asia",
        "South Asia": "Asia",
        "Central Asia": "Asia",
        # Europe
        "Europe": "Europe",
        "Western Europe": "Europe",
        "Eastern Europe": "Europe",
        "Northern Europe": "Europe",
        "Southern Europe": "Europe",
        # Middle East
        "Middle East": "Middle East",
        "MENA": "Middle East",
        # Oceania
        "Oceania": "Oceania",
        "Australia": "Oceania",
        "Pacific": "Oceania",
        # Global
        "Global": "Global",
        "World": "Global",
        "International": "Global",
    }

    def __init__(self, llm_client=None):
        """
        Initialize digest workflow.

        Args:
            llm_client: Optional LLM client (uses reasoning model if not provided)
        """
        self.llm_client = llm_client

    def execute(self, days_back: int, topic: str = None, output_path: str = None) -> str:
        """
        Execute the digest workflow.

        Args:
            days_back: Number of days to look back (max 90)
            topic: Optional topic focus (e.g., "crude oil", "AI infrastructure")
            output_path: Optional path to save markdown output

        Returns:
            Formatted markdown digest
        """
        logger.info(f"Starting digest workflow: {days_back} days, topic={topic}")

        # Cap at 90 days
        days_back = min(days_back, 90)

        # Phase 1: Fetch articles
        articles = self._fetch_articles(days_back)
        if not articles:
            return "Error: No articles found. Check NEWSROOM_JWT_TOKEN configuration."

        logger.info(f"Fetched {len(articles)} articles")

        # Phase 2: Filter by topic if provided
        if topic:
            articles = self._filter_by_topic(articles, topic)
            if not articles:
                return f"Error: No articles found matching topic '{topic}' in the past {days_back} days."
            logger.info(f"Filtered to {len(articles)} articles matching topic: {topic}")

        # Phase 3: Identify meta trends
        trends = self._identify_trends(articles, topic)
        logger.info(f"Identified {len(trends)} meta trends")

        # Phase 4: Assign articles to continents (no repetition)
        continental_articles = self._assign_articles_to_continents(articles)
        logger.info(f"Assigned articles to {len(continental_articles)} continents")

        # Phase 5: Summarize articles
        for continent, continent_articles in continental_articles.items():
            if continent_articles:
                continental_articles[continent] = self._summarize_articles(continent_articles, topic)

        # Phase 6: Format digest
        digest = self._format_digest(trends, continental_articles, days_back, topic, len(articles))

        # Save to file if output_path provided
        if output_path:
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(digest)
                logger.info(f"Digest saved to {output_path}")
            except Exception as e:
                logger.error(f"Failed to save digest: {e}")

        return digest

    def _fetch_articles(self, days_back: int) -> List[Dict]:
        """
        Fetch articles from newsroom API.

        Args:
            days_back: Number of days to fetch

        Returns:
            List of article dictionaries
        """
        from tools.research.newsroom import _fetch_newsroom_api_raw

        # Fetch more articles for better coverage across continents
        max_results = min(days_back * 50, 1000)  # ~50 articles per day, max 1000
        articles = _fetch_newsroom_api_raw(days_back=days_back, max_results=max_results)

        return articles

    def _filter_by_topic(self, articles: List[Dict], topic: str) -> List[Dict]:
        """
        Filter articles by topic relevance using keyword matching.

        For simplicity, uses keyword matching rather than LLM scoring.
        Articles are scored based on topic presence in headline and topic_tags.

        Args:
            articles: List of articles
            topic: Topic to filter by

        Returns:
            Filtered list of relevant articles
        """
        topic_words = [w.lower() for w in topic.split() if len(w) >= 2]

        scored_articles = []
        for article in articles:
            score = 0
            headline = article.get("headline", "").lower()
            topic_tags = [t.lower() for t in article.get("topic_tags", [])]
            tags_str = " ".join(topic_tags)

            # Score based on keyword matches
            for word in topic_words:
                if word in headline:
                    score += 3  # Higher weight for headline match
                if word in tags_str:
                    score += 2  # Medium weight for topic tag match

            # Check for full phrase match
            if topic.lower() in headline:
                score += 5
            if topic.lower() in tags_str:
                score += 3

            if score >= 2:  # Minimum threshold
                scored_articles.append((score, article))

        # Sort by score and return articles
        scored_articles.sort(key=lambda x: x[0], reverse=True)
        return [article for _, article in scored_articles]

    def _identify_trends(self, articles: List[Dict], topic: str = None) -> List[Dict]:
        """
        Identify 3 meta trends from articles using LLM.

        Args:
            articles: List of articles
            topic: Optional topic focus

        Returns:
            List of trend dictionaries with 'title' and 'description'
        """
        # Prepare headlines and topic tags for analysis
        article_summaries = []
        for article in articles[:100]:  # Limit to 100 for LLM context
            headline = article.get("headline", "No headline")
            tags = article.get("topic_tags", [])
            date = article.get("date", "")
            article_summaries.append(f"- {headline} [{date}] Tags: {', '.join(tags)}")

        articles_text = "\n".join(article_summaries)

        topic_instruction = ""
        if topic:
            topic_instruction = f"Focus your analysis specifically on trends related to '{topic}'."

        prompt = f"""Analyze these news headlines and identify exactly 3 high-level meta trends.
{topic_instruction}

Headlines and tags:
{articles_text}

Return your analysis as JSON with exactly this format:
{{
  "trends": [
    {{"title": "Trend 1 Title", "description": "2-3 sentence description of this trend"}},
    {{"title": "Trend 2 Title", "description": "2-3 sentence description of this trend"}},
    {{"title": "Trend 3 Title", "description": "2-3 sentence description of this trend"}}
  ]
}}

Important:
- Identify overarching themes, not individual stories
- Be specific and insightful about market/industry implications
- Keep descriptions concise (2-3 sentences each)
- Return ONLY valid JSON, no other text"""

        try:
            from tools.registry import TOOL_FUNCTIONS
            use_reasoning_model = TOOL_FUNCTIONS.get("use_reasoning_model")

            if use_reasoning_model:
                result = use_reasoning_model(prompt)
                # Extract JSON from response
                trends = self._parse_trends_json(result)
                if trends:
                    return trends
        except Exception as e:
            logger.warning(f"LLM trend analysis failed: {e}")

        # Fallback: frequency-based trend analysis
        return self._fallback_trend_analysis(articles, topic)

    def _parse_trends_json(self, text: str) -> List[Dict]:
        """Parse trends JSON from LLM response."""
        try:
            # Try to find JSON in the response
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = text[start:end]
                data = json.loads(json_str)
                if "trends" in data and isinstance(data["trends"], list):
                    return data["trends"][:3]
        except json.JSONDecodeError:
            pass
        return []

    def _fallback_trend_analysis(self, articles: List[Dict], topic: str = None) -> List[Dict]:
        """Fallback trend analysis using topic tag frequency."""
        from collections import Counter

        # Count topic tags
        tag_counts = Counter()
        for article in articles:
            for tag in article.get("topic_tags", []):
                tag_counts[tag] += 1

        # Get top 3 topics
        top_tags = tag_counts.most_common(3)

        trends = []
        for tag, count in top_tags:
            trends.append({
                "title": f"Rising Focus on {tag}",
                "description": f"Multiple sources ({count} articles) are reporting on {tag}-related developments, indicating significant market attention in this area."
            })

        return trends

    def _assign_articles_to_continents(self, articles: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Assign each article to exactly one continent (no repetition).

        Articles are assigned based on geography_tags, with priority order matching CONTINENT_TAGS.

        Args:
            articles: List of articles

        Returns:
            Dict mapping continent names to lists of articles
        """
        continental_articles = {continent: [] for continent in self.CONTINENT_TAGS}
        used_urls: Set[str] = set()

        # Process continents in priority order
        for continent in self.CONTINENT_TAGS:
            if len(continental_articles[continent]) >= self.ARTICLES_PER_CONTINENT:
                continue

            for article in articles:
                url = article.get("url", "")
                if url in used_urls:
                    continue

                # Check if article matches this continent
                geography_tags = article.get("geography_tags", [])
                assigned_continent = self._get_continent_for_article(geography_tags)

                if assigned_continent == continent:
                    continental_articles[continent].append(article)
                    used_urls.add(url)

                    if len(continental_articles[continent]) >= self.ARTICLES_PER_CONTINENT:
                        break

        # Second pass: assign untagged articles to "Global" if they have no geography
        for article in articles:
            url = article.get("url", "")
            if url in used_urls:
                continue

            geography_tags = article.get("geography_tags", [])
            if not geography_tags and len(continental_articles["Global"]) < self.ARTICLES_PER_CONTINENT:
                continental_articles["Global"].append(article)
                used_urls.add(url)

        return continental_articles

    def _get_continent_for_article(self, geography_tags: List[str]) -> Optional[str]:
        """
        Determine the primary continent for an article based on its geography tags.

        Args:
            geography_tags: List of geography tags from the article

        Returns:
            Continent name or None if no match
        """
        for tag in geography_tags:
            # Check exact match
            if tag in self.GEOGRAPHY_TO_CONTINENT:
                return self.GEOGRAPHY_TO_CONTINENT[tag]

            # Check case-insensitive match
            tag_lower = tag.lower()
            for geo_tag, continent in self.GEOGRAPHY_TO_CONTINENT.items():
                if geo_tag.lower() == tag_lower:
                    return continent

        return None

    def _summarize_articles(self, articles: List[Dict], topic: str = None) -> List[Dict]:
        """
        Summarize articles, adding a 'summary' field to each.

        For efficiency, batch summarizes using LLM.

        Args:
            articles: List of articles to summarize
            topic: Optional topic focus

        Returns:
            Articles with 'summary' field added
        """
        if not articles:
            return articles

        # Prepare batch prompt
        headlines = []
        for i, article in enumerate(articles):
            headline = article.get("headline", "No headline")
            headlines.append(f"{i+1}. {headline}")

        headlines_text = "\n".join(headlines)

        topic_instruction = ""
        if topic:
            topic_instruction = f"Focus on aspects relevant to '{topic}'."

        prompt = f"""Summarize each of these news headlines in 1-2 sentences each. {topic_instruction}

Headlines:
{headlines_text}

Return your summaries as JSON:
{{
  "summaries": [
    "Summary for headline 1",
    "Summary for headline 2",
    ...
  ]
}}

Important:
- Each summary should be 1-2 sentences
- Be concise and factual
- Return ONLY valid JSON"""

        try:
            from tools.registry import TOOL_FUNCTIONS
            use_reasoning_model = TOOL_FUNCTIONS.get("use_reasoning_model")

            if use_reasoning_model:
                result = use_reasoning_model(prompt)
                summaries = self._parse_summaries_json(result)

                if summaries and len(summaries) >= len(articles):
                    for i, article in enumerate(articles):
                        article["summary"] = summaries[i]
                    return articles
        except Exception as e:
            logger.warning(f"LLM summarization failed: {e}")

        # Fallback: use headline as summary
        for article in articles:
            article["summary"] = article.get("headline", "No summary available.")

        return articles

    def _parse_summaries_json(self, text: str) -> List[str]:
        """Parse summaries JSON from LLM response."""
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = text[start:end]
                data = json.loads(json_str)
                if "summaries" in data and isinstance(data["summaries"], list):
                    return data["summaries"]
        except json.JSONDecodeError:
            pass
        return []

    def _format_digest(
        self,
        trends: List[Dict],
        continental_articles: Dict[str, List[Dict]],
        days_back: int,
        topic: str,
        total_articles: int
    ) -> str:
        """
        Format the final digest as markdown.

        Args:
            trends: List of trend dictionaries
            continental_articles: Dict mapping continents to articles
            days_back: Number of days covered
            topic: Optional topic focus
            total_articles: Total articles analyzed

        Returns:
            Formatted markdown string
        """
        lines = []

        # Header
        lines.append(f"# Newsroom Digest: Past {days_back} Days")
        if topic:
            lines.append(f"## Focus: {topic}")
        lines.append("")
        lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Articles analyzed: {total_articles}*")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Meta Trends
        lines.append("## Meta Trends")
        lines.append("")
        for i, trend in enumerate(trends, 1):
            title = trend.get("title", f"Trend {i}")
            description = trend.get("description", "No description available.")
            lines.append(f"### {i}. {title}")
            lines.append(description)
            lines.append("")

        lines.append("---")
        lines.append("")

        # Continental sections
        for continent in self.CONTINENT_TAGS:
            articles = continental_articles.get(continent, [])

            lines.append(f"## {continent}")
            lines.append("")

            if not articles:
                lines.append("*No articles for this period*")
                lines.append("")
            else:
                for article in articles:
                    headline = article.get("headline", "No headline")
                    summary = article.get("summary", headline)
                    url = article.get("url", "")
                    source = article.get("source", "Unknown source")
                    date = article.get("date", "")

                    lines.append(f"**{headline}**")
                    lines.append(f"*{source}* | {date}")
                    lines.append("")
                    lines.append(summary)
                    if url:
                        lines.append(f"[Read more]({url})")
                    lines.append("")

            lines.append("")

        # Footer
        lines.append("---")
        lines.append(f"*End of digest. {total_articles} articles processed.*")

        return "\n".join(lines)
