"""Source aggregator - collects sources from academic, web, and newsroom."""

import logging
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from engine.models import Source
from tools.research.academic_search import academic_search
from tools.research.web_search import web_search
from tools.research.newsroom import fetch_newsroom_api

logger = logging.getLogger(__name__)


def parse_academic_results(results_str: str, query: str) -> List[Source]:
    """Parse academic_search() formatted results into Source objects."""
    sources = []
    lines = results_str.split('\n')
    
    current_source = None
    for line in lines:
        line = line.strip()
        if not line or line.startswith('Academic search results') or line.startswith('Summary:'):
            continue
        
        # New source (numbered list)
        if line and line[0].isdigit() and '. ' in line:
            if current_source:
                sources.append(current_source)
            
            # Extract title (everything after number and period)
            title = line.split('. ', 1)[1] if '. ' in line else line
            source_id = Source.generate_id(title)
            current_source = Source(
                source_id=source_id,
                url="",
                title=title,
                source_type="academic",
                content_snippet=""
            )
        
        # URL
        elif line.startswith('   URL:'):
            if current_source:
                current_source.url = line.replace('   URL:', '').strip()
                # Regenerate ID with URL if available
                if current_source.url:
                    current_source.source_id = Source.generate_id(current_source.url)
        
        # DOI
        elif line.startswith('   DOI:'):
            if current_source:
                doi = line.replace('   DOI:', '').strip()
                if not current_source.url and doi:
                    current_source.url = f"https://doi.org/{doi}"
        
        # Description/content
        elif line.startswith('   ') and not line.startswith('   [') and not line.startswith('   Year:') and not line.startswith('   Citations:'):
            if current_source:
                content = line.replace('   ', '').strip()
                if content and content not in ['URL:', 'DOI:']:
                    if current_source.content_snippet:
                        current_source.content_snippet += " " + content
                    else:
                        current_source.content_snippet = content
    
    if current_source:
        sources.append(current_source)
    
    return sources


def parse_web_results(results_str: str, query: str) -> List[Source]:
    """Parse web_search() formatted results into Source objects."""
    sources = []
    lines = results_str.split('\n')
    
    current_source = None
    for line in lines:
        line = line.strip()
        if not line or line.startswith('Web search results') or line.startswith('Sources:'):
            continue
        
        # New source (numbered list)
        if line and line[0].isdigit() and '. ' in line:
            if current_source:
                sources.append(current_source)
            
            title = line.split('. ', 1)[1] if '. ' in line else line
            source_id = Source.generate_id(title)
            current_source = Source(
                source_id=source_id,
                url="",
                title=title,
                source_type="web",
                content_snippet=""
            )
        
        # URL
        elif line.startswith('   URL:'):
            if current_source:
                current_source.url = line.replace('   URL:', '').strip()
                if current_source.url:
                    current_source.source_id = Source.generate_id(current_source.url)
        
        # Description
        elif line.startswith('   ') and not line.startswith('   Domain:') and not line.startswith('   Age:') and not line.startswith('   Published:'):
            if current_source:
                content = line.replace('   ', '').strip()
                if content and content not in ['URL:', 'Domain:']:
                    if current_source.content_snippet:
                        current_source.content_snippet += " " + content
                    else:
                        current_source.content_snippet = content
    
    if current_source:
        sources.append(current_source)
    
    return sources


def parse_newsroom_results(articles: List[Dict[str, Any]], query: str) -> List[Source]:
    """Parse newsroom API articles into Source objects."""
    sources = []
    
    for article in articles:
        url = article.get("url", "")
        title = article.get("headline", "No title")
        source_id = Source.generate_id(url) if url else Source.generate_id(title)
        
        # Build content snippet
        snippet_parts = []
        if article.get("source"):
            snippet_parts.append(f"Source: {article['source']}")
        if article.get("topic_tags"):
            tags = article.get("topic_tags", [])[:3]
            snippet_parts.append(f"Topics: {', '.join(tags)}")
        
        source = Source(
            source_id=source_id,
            url=url,
            title=title,
            source_type="newsroom",
            content_snippet=" | ".join(snippet_parts),
            publication_date=article.get("date", "")
        )
        sources.append(source)
    
    return sources


def aggregate_sources(query: str, max_results_per_source: int = 10) -> List[Source]:
    """
    Aggregate sources from academic, web, and newsroom in parallel.
    
    Args:
        query: Research query
        max_results_per_source: Max results per source type
        
    Returns:
        List of Source objects
    """
    logger.info(f"Aggregating sources for: {query[:60]}...")
    all_sources = []
    
    def fetch_academic():
        try:
            results = academic_search(query, max_results=max_results_per_source)
            return parse_academic_results(results, query)
        except Exception as e:
            logger.warning(f"Academic search failed: {e}")
            return []
    
    def fetch_web():
        try:
            results = web_search(query, max_results=max_results_per_source)
            return parse_web_results(results, query)
        except Exception as e:
            logger.warning(f"Web search failed: {e}")
            return []
    
    def fetch_newsroom():
        try:
            articles = fetch_newsroom_api(query, days_back=90, max_results=max_results_per_source)
            return parse_newsroom_results(articles, query)
        except Exception as e:
            logger.warning(f"Newsroom fetch failed: {e}")
            return []
    
    # Fetch in parallel
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(fetch_academic): "academic",
            executor.submit(fetch_web): "web",
            executor.submit(fetch_newsroom): "newsroom"
        }
        
        for future in as_completed(futures):
            source_type = futures[future]
            try:
                sources = future.result()
                all_sources.extend(sources)
                logger.info(f"✓ {source_type}: {len(sources)} sources")
            except Exception as e:
                logger.warning(f"{source_type} aggregation failed: {e}")
    
    logger.info(f"Total sources aggregated: {len(all_sources)}")
    return all_sources
