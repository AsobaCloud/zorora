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
    import re
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
                # Only add if we have a URL or DOI
                if current_source.url:
                    sources.append(current_source)
                else:
                    logger.warning(f"Skipping academic source without URL: {current_source.title[:50]}")
            
            # Extract title (everything after number and period)
            title = line.split('. ', 1)[1] if '. ' in line else line
            title = title.strip()
            if not title:
                continue  # Skip if no title
            source_id = Source.generate_id(title)
            current_source = Source(
                source_id=source_id,
                url="",
                title=title,
                source_type="academic",
                content_snippet=""
            )
        
        # URL - be more flexible with whitespace
        elif re.match(r'^\s*URL:', line):
            if current_source:
                url = re.sub(r'^\s*URL:\s*', '', line).strip()
                if url:
                    current_source.url = url
                    # Regenerate ID with URL if available
                    current_source.source_id = Source.generate_id(current_source.url)
        
        # DOI
        elif re.match(r'^\s*DOI:', line):
            if current_source:
                doi = re.sub(r'^\s*DOI:\s*', '', line).strip()
                if doi and not current_source.url:
                    current_source.url = f"https://doi.org/{doi}"
                    current_source.source_id = Source.generate_id(current_source.url)
        
        # Description/content
        elif line.startswith('   ') and not line.startswith('   [') and not re.match(r'^\s*(Year:|Citations:)', line):
            if current_source:
                content = line.replace('   ', '').strip()
                if content and content not in ['URL:', 'DOI:']:
                    if current_source.content_snippet:
                        current_source.content_snippet += " " + content
                    else:
                        current_source.content_snippet = content
    
    if current_source:
        # Only add if we have a URL or DOI
        if current_source.url:
            sources.append(current_source)
        else:
            logger.warning(f"Skipping academic source without URL: {current_source.title[:50]}")
    
    return sources


def parse_web_results(results_str: str, query: str) -> List[Source]:
    """Parse web_search() formatted results into Source objects."""
    import re
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
                # Web sources MUST have URLs
                if current_source.url:
                    sources.append(current_source)
                else:
                    logger.warning(f"Skipping web source without URL: {current_source.title[:50]}")
            
            title = line.split('. ', 1)[1] if '. ' in line else line
            title = title.strip()
            if not title:
                continue  # Skip if no title
            source_id = Source.generate_id(title)
            current_source = Source(
                source_id=source_id,
                url="",
                title=title,
                source_type="web",
                content_snippet=""
            )
        
        # URL - be more flexible with whitespace and also look for http/https patterns
        elif re.match(r'^\s*URL:', line):
            if current_source:
                url = re.sub(r'^\s*URL:\s*', '', line).strip()
                if url:
                    current_source.url = url
                    current_source.source_id = Source.generate_id(current_source.url)
        # Also catch URLs that might be on their own line (http/https)
        elif current_source and not current_source.url and re.match(r'^https?://', line):
            current_source.url = line.strip()
            current_source.source_id = Source.generate_id(current_source.url)
        
        # Description
        elif line.startswith('   ') and not re.match(r'^\s*(Domain:|Age:|Published:)', line):
            if current_source:
                content = line.replace('   ', '').strip()
                if content and content not in ['URL:', 'Domain:'] and not re.match(r'^https?://', content):
                    if current_source.content_snippet:
                        current_source.content_snippet += " " + content
                    else:
                        current_source.content_snippet = content
    
    if current_source:
        # Web sources MUST have URLs
        if current_source.url:
            sources.append(current_source)
        else:
            logger.warning(f"Skipping web source without URL: {current_source.title[:50]}")
    
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
