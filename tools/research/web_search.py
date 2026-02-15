"""Web search tool - searches web using Brave Search API with DuckDuckGo fallback."""

import logging
import re
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests
import config

# Import shared functions from academic_search
from tools.research.academic_search import (
    _duckduckgo_search_raw,
    _scholar_search_raw,
    _pubmed_search_raw
)

logger = logging.getLogger(__name__)


def _brave_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search using Brave Search API and return raw results (not formatted).
    
    Args:
        query: Search query
        max_results: Number of results (max 20 for free tier)
        
    Returns:
        List of result dictionaries
    """
    logger.info(f"Brave Search API call: {query[:100]}...")

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": config.BRAVE_SEARCH["api_key"]
    }

    params = {
        "q": query,
        "count": min(max_results, 20),
        "text_decorations": False,
        "search_lang": "en"
    }

    try:
        response = requests.get(
            config.BRAVE_SEARCH["endpoint"],
            headers=headers,
            params=params,
            timeout=config.BRAVE_SEARCH["timeout"]
        )
        response.raise_for_status()

        data = response.json()
        web_results = data.get("web", {}).get("results", [])

        if not web_results:
            logger.warning(f"Brave Search returned no results for query: {query[:60]}...")
            return []

        # Convert to standard format
        standardized = []
        for result in web_results:
            standardized.append({
                "title": result.get("title", "No title"),
                "url": result.get("url", ""),
                "description": result.get("description", "No description"),
                "age": result.get("age"),  # Preserve age if available
                "published_date": result.get("published_date")  # Preserve date if available
            })
        
        logger.info(f"Brave Search returned {len(standardized)} results for: {query[:60]}...")
        return standardized

    except requests.exceptions.RequestException as e:
        logger.error(f"Brave Search API error: {e}")
        raise


def _parallel_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search multiple sources in parallel and return raw results.
    
    Args:
        query: Search query
        max_results: Number of results to return
        
    Returns:
        List of result dictionaries
    """
    logger.info(f"Parallel search (raw): {query[:100]}...")
    
    # Prepare search tasks
    tasks = []
    
    # Add Brave search task
    if config.BRAVE_SEARCH.get("enabled") and config.BRAVE_SEARCH.get("api_key"):
        tasks.append(("brave", _brave_search_raw, query, max_results))
    
    # Add DuckDuckGo search task
    tasks.append(("duckduckgo", _duckduckgo_search_raw, query, max_results))
    
    if not tasks:
        return []
    
    # Execute searches in parallel
    result_sets = []
    
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        # Submit all tasks
        future_to_source = {}
        for source, func, *args in tasks:
            future = executor.submit(func, *args)
            future_to_source[future] = source
        
        # Collect results as they complete
        for future in as_completed(future_to_source):
            source = future_to_source[future]
            try:
                results = future.result()
                if results:
                    result_sets.append(results)
                    logger.info(f"Parallel search: {source} returned {len(results)} results")
            except Exception as e:
                logger.warning(f"Parallel search: {source} failed: {e}")
    
    if not result_sets:
        logger.warning("Parallel search: No result sets collected")
        return []
    
    # Merge results
    try:
        from tools.utils._result_processor import ResultProcessor
        processor = ResultProcessor(
            max_domain_results=config.WEB_SEARCH.get("max_domain_results", 2)
        )
        merged_results = processor.merge_results(result_sets, query)
        logger.info(f"Parallel search: Merged {len(result_sets)} result sets into {len(merged_results)} results")
        return merged_results[:max_results]
    except ImportError as e:
        logger.warning(f"Result processor module not available: {e}, using raw results")
        # Fallback: return first successful result set
        if result_sets:
            logger.info(f"Parallel search fallback: Using first result set ({len(result_sets[0])} results)")
            return result_sets[0][:max_results]
        return []
    except Exception as e:
        logger.error(f"Failed to merge parallel search results: {e}")
        # Fallback: return first successful result set
        if result_sets:
            logger.info(f"Parallel search fallback: Using first result set ({len(result_sets[0])} results)")
            return result_sets[0][:max_results]
        return []


def _brave_news_search(query: str, max_results: int = 5, query_metadata: dict = None) -> str:
    """
    Search news using Brave News API.
    
    Args:
        query: Search query
        max_results: Number of results (max 20 for free tier)
        query_metadata: Optional metadata from query optimization
        
    Returns:
        Formatted news search results
    """
    logger.info(f"Brave News Search: {query[:100]}...")
    
    # Brave News API endpoint
    news_endpoint = config.BRAVE_SEARCH.get("news_endpoint", "https://api.search.brave.com/res/v1/news/search")
    
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": config.BRAVE_SEARCH["api_key"]
    }
    
    params = {
        "q": query,
        "count": min(max_results, 20),  # Max 20 for free tier
        "search_lang": "en",
        "freshness": "pd"  # Past day - prioritize recent news
    }
    
    try:
        response = requests.get(
            news_endpoint,
            headers=headers,
            params=params,
            timeout=config.BRAVE_SEARCH["timeout"]
        )
        response.raise_for_status()
        
        data = response.json()
        news_results = data.get("results", [])
        
        if not news_results:
            return f"No news found for: {query}"
        
        # Format news results with dates prominently displayed
        formatted = [f"News search results for: {query}"]
        if query_metadata and query_metadata.get("intent") == "news":
            formatted[0] += " (intent: news)"
        formatted[0] += " [Brave News]\n"
        
        for i, result in enumerate(news_results, 1):
            title = result.get("title", "No title")
            url = result.get("url", "")
            description = result.get("description", "No description")
            
            # Extract date information
            date_info = ""
            if "age" in result:
                age = result.get("age")
                if age:
                    date_info = f" | Published: {age} ago"
            elif "published_date" in result:
                pub_date = result.get("published_date")
                if pub_date:
                    date_info = f" | Published: {pub_date}"
            
            # Extract source
            source = result.get("meta_url", {}).get("hostname", "") if isinstance(result.get("meta_url"), dict) else ""
            if not source and url:
                try:
                    parsed = urlparse(url)
                    source = parsed.netloc.replace("www.", "")
                except Exception:
                    pass
            
            formatted.append(f"\n{i}. {title}")
            formatted.append(f"   URL: {url}")
            
            # Add metadata with date prominently displayed
            meta_parts = []
            if source:
                meta_parts.append(f"Source: {source}")
            if date_info:
                meta_parts.append(date_info.strip(" |"))
            if meta_parts:
                formatted.append(f"   {' | '.join(meta_parts)}")
            
            formatted.append(f"   {description}")
        
        return "\n".join(formatted)
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Brave News Search API error: {e}")
        raise


def _format_search_results(query: str, results: List[Dict[str, Any]], source: str = "Unknown", query_metadata: dict = None, include_extracted: bool = False) -> str:
    """
    Format search results with enhanced metadata.
    
    Args:
        query: Original search query
        results: List of result dictionaries with 'title', 'url', 'description'
        source: Search engine source name
        query_metadata: Optional metadata from query optimization
        
    Returns:
        Formatted string with enhanced metadata
    """
    if not results:
        return f"No results found for: {query}"
    
    formatted = [f"Web search results for: {query}"]
    
    # Add source and intent info if available
    if query_metadata and query_metadata.get("intent") != "general":
        formatted[0] += f" (intent: {query_metadata['intent']})"
    formatted[0] += f" [{source}]\n"
    
    for i, result in enumerate(results, 1):
        title = result.get("title", "No title")
        url = result.get("url", "")
        description = result.get("description", "No description")
        
        # Extract domain from URL
        domain = ""
        if url:
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.replace("www.", "")
            except Exception:
                pass
        
        # Extract date if available (Brave API sometimes includes age)
        date_info = ""
        if "age" in result:
            age = result.get("age")
            if age:
                date_info = f" | Age: {age}"
        elif "published_date" in result:
            pub_date = result.get("published_date")
            if pub_date:
                date_info = f" | Published: {pub_date}"
        
        # Format result entry
        formatted.append(f"\n{i}. {title}")
        formatted.append(f"   URL: {url}")
        
        # Add metadata line if available
        if domain or date_info:
            meta_parts = []
            if domain:
                meta_parts.append(f"Domain: {domain}")
            if date_info:
                meta_parts.append(date_info.strip(" |"))
            if meta_parts:
                formatted.append(f"   {' | '.join(meta_parts)}")
        
        formatted.append(f"   {description}")
        
        # Add extracted content if available and enabled
        if include_extracted:
            extracted = result.get("extracted_content", "")
            if extracted:
                formatted.append(f"\n   [Extracted Content]: {extracted[:500]}...")  # Truncate for display
    
    return "\n".join(formatted)


def _synthesize_results(results: List[Dict[str, Any]], original_query: str, optimized_query: str, query_metadata: dict = None) -> str:
    """
    Synthesize search results using LLM models.
    
    Args:
        results: List of search result dictionaries
        original_query: Original user query
        optimized_query: Optimized query used for search
        query_metadata: Optional metadata from query optimization
        
    Returns:
        Synthesized answer string
    """
    # Build context from results
    context_parts = []
    for i, result in enumerate(results[:5], 1):  # Use top 5 for synthesis
        title = result.get("title", "No title")
        url = result.get("url", "")
        description = result.get("description", "No description")
        extracted = result.get("extracted_content", "")
        
        context_parts.append(f"{i}. {title} ({url})")
        context_parts.append(f"   {description}")
        if extracted:
            context_parts.append(f"   [Content]: {extracted[:500]}...")  # Truncate extracted content
    
    context = "\n".join(context_parts)
    
    # Use search model for synthesis
    try:
        # Import use_search_model from modular registry
        from tools.registry import use_search_model
        
        synthesis_prompt = f"""Based on the following web search results for "{original_query}", provide a comprehensive answer:

{context}

Please synthesize the information from these sources to answer: {original_query}

Provide a clear, well-structured answer that combines information from multiple sources. Cite sources when making specific claims."""
        
        # Use existing use_search_model function
        synthesized = use_search_model(synthesis_prompt)
        
        if synthesized and not synthesized.startswith("Error:"):
            # Add source attribution
            sources_list = "\n".join([f"- {r.get('title', 'Unknown')} ({r.get('url', '')})" for r in results[:5]])
            return f"{synthesized}\n\nSources:\n{sources_list}"
        
        return synthesized
        
    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        return f"Error: Failed to synthesize results: {e}"


def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using Brave Search API (with DuckDuckGo fallback).
    Enhanced with caching, query optimization, and improved formatting.

    Args:
        query: Search query (may include meta-language like "search for" - will be cleaned)
        max_results: Maximum number of results to return (default: 5)

    Returns:
        Formatted search results with titles, URLs, and snippets
    """
    if not query or not isinstance(query, str):
        return "Error: query must be a non-empty string"

    if len(query) > 500:
        return "Error: query too long (max 500 characters)"
    
    # Pre-process query to remove meta-language before optimization
    original_query = query
    query = query.strip()
    
    # Remove common meta-language prefixes
    meta_prefixes = [
        r'^(let\'?s\s+)?(do\s+a\s+)?(web\s+)?search\s+(for|to|about|on)\s+',
        r'^(can\s+you\s+)?(please\s+)?(search\s+for|look\s+up|find\s+information\s+about)\s+',
        r'^(i\s+want\s+to\s+)?(search|find|look\s+up)\s+(for|about|on)\s+',
        r'^(help\s+me\s+)?(understand|learn|find\s+out)\s+(about|more\s+about)\s+',
    ]
    
    for pattern in meta_prefixes:
        query = re.sub(pattern, '', query, flags=re.IGNORECASE)
        query = query.strip()
    
    # Remove meta-language in the middle/end
    query = re.sub(r'\s+and\s+what\s+it\s+means\s+', ' ', query, flags=re.IGNORECASE)
    query = query.strip()
    
    # Remove other meta-language suffixes
    meta_suffixes = [
        r'\s+what\s+does\s+this\s+mean.*$',
        r'\s+what\s+is\s+the\s+context.*$',
        r'\s+to\s+better\s+understand.*$',
        r'\s+to\s+understand.*$',
    ]
    
    for pattern in meta_suffixes:
        query = re.sub(pattern, '', query, flags=re.IGNORECASE)
        query = query.strip()
    
    # Remove "better understand the context around" type phrases
    query = re.sub(r'\b(better\s+)?understand\s+(the\s+)?context\s+around\s+', '', query, flags=re.IGNORECASE)
    query = query.strip()
    
    # Remove "the context behind/around/for" type phrases
    query = re.sub(r'\bthe\s+context\s+(behind|around|for|of)\s+', '', query, flags=re.IGNORECASE)
    query = query.strip()
    
    # Remove "behind" when used as meta-language
    query = re.sub(r'^(behind|about|regarding)\s+', '', query, flags=re.IGNORECASE)
    query = query.strip()
    
    if not query:
        return "Error: Query became empty after removing meta-language. Please provide a search query."
    
    # Log if query was cleaned
    if query != original_query:
        logger.info(f"Query cleaned: '{original_query[:60]}...' -> '{query[:60]}...'")
    
    # Initialize cache if enabled
    cache = None
    if config.WEB_SEARCH.get("cache_enabled", True):
        try:
            from tools.utils._search_cache import SearchCache
            cache = SearchCache(
                max_entries=config.WEB_SEARCH.get("cache_max_entries", 100),
                default_ttl_hours=config.WEB_SEARCH.get("cache_ttl_hours", 1),
                stable_ttl_hours=config.WEB_SEARCH.get("cache_ttl_stable_hours", 24)
            )
            # Check cache first
            cached_result = cache.get(query, max_results)
            if cached_result:
                logger.info(f"Returning cached result for: {query[:50]}...")
                return cached_result
        except ImportError as e:
            logger.warning(f"Cache module not available: {e}, continuing without cache")
        except Exception as e:
            logger.warning(f"Cache initialization failed: {e}, continuing without cache")
    
    # Optimize query if enabled
    optimized_query = query
    query_metadata = {}
    if config.WEB_SEARCH.get("query_optimization", True):
        try:
            from tools.utils._query_optimizer import QueryOptimizer
            optimizer = QueryOptimizer(enabled=config.WEB_SEARCH.get("intent_detection", True))
            optimized_query, query_metadata = optimizer.optimize(query)
        except ImportError as e:
            logger.warning(f"Query optimizer module not available: {e}, using original query")
        except Exception as e:
            logger.warning(f"Query optimization failed: {e}, using original query")
    
    # Route to specialized search types based on intent
    intent = query_metadata.get("intent", "general")
    
    # News search - only route if query explicitly mentions news-related terms
    if intent == "news" and config.WEB_SEARCH.get("news_enabled", True):
        news_keywords = ['news', 'headline', 'article', 'breaking', 'update', 'announcement', 'happening', 'happened']
        query_lower = optimized_query.lower()
        has_news_keyword = any(keyword in query_lower for keyword in news_keywords)
        
        if has_news_keyword and config.BRAVE_SEARCH.get("enabled") and config.BRAVE_SEARCH.get("api_key"):
            try:
                result = _brave_news_search(optimized_query, max_results, query_metadata)
                # Cache result
                if cache and result and not result.startswith("Error:"):
                    try:
                        cache.set(query, max_results, result)
                    except Exception:
                        pass
                return result
            except Exception as e:
                logger.warning(f"News search failed: {e}, falling back to regular search")
    
    # Check if parallel search is enabled
    parallel_enabled = config.WEB_SEARCH.get("parallel_enabled", False)
    brave_available = config.BRAVE_SEARCH.get("enabled") and config.BRAVE_SEARCH.get("api_key")
    
    # Get raw results for processing
    raw_results = None
    academic_max_results = config.WEB_SEARCH.get("academic_max_results", 3)
    
    if parallel_enabled and brave_available:
        # Parallel search: search both Brave and DuckDuckGo simultaneously
        logger.info(f"Using parallel search (Brave + DuckDuckGo) for: {optimized_query[:60]}...")
        raw_results = _parallel_search_raw(optimized_query, max_results)
    else:
        # Sequential search: try Brave first, fallback to DuckDuckGo
        if brave_available:
            logger.info(f"Attempting Brave Search for: {optimized_query[:60]}...")
            try:
                raw_results = _brave_search_raw(optimized_query, max_results)
                if raw_results:
                    logger.info(f"Brave Search succeeded: {len(raw_results)} results")
                else:
                    logger.warning("Brave Search returned no results, falling back to DuckDuckGo")
            except Exception as e:
                logger.warning(f"Brave Search failed: {e}, falling back to DuckDuckGo")
        
        # Fallback to DuckDuckGo if Brave failed or not configured
        if raw_results is None:
            logger.info(f"Using DuckDuckGo fallback for: {optimized_query[:60]}...")
            try:
                raw_results = _duckduckgo_search_raw(optimized_query, max_results)
                if raw_results:
                    logger.info(f"DuckDuckGo search succeeded: {len(raw_results)} results")
                else:
                    logger.warning("DuckDuckGo returned no results")
            except Exception as e:
                logger.error(f"DuckDuckGo search failed: {e}")
                return f"Error: Web search failed: {e}. Try again or rephrase query."
    
    # Always include academic sources (Scholar + PubMed)
    academic_results = []
    academic_sources_used = []
    try:
        logger.info(f"Searching academic sources (Scholar + PubMed) for: {optimized_query[:60]}...")
        scholar_results = _scholar_search_raw(optimized_query, academic_max_results)
        if scholar_results:
            academic_results.extend(scholar_results)
            academic_sources_used.append("Scholar")
    except Exception as e:
        logger.warning(f"Scholar search failed: {e}, continuing without Scholar results")
    
    try:
        pubmed_results = _pubmed_search_raw(optimized_query, academic_max_results)
        if pubmed_results:
            academic_results.extend(pubmed_results)
            academic_sources_used.append("PubMed")
    except Exception as e:
        logger.warning(f"PubMed search failed: {e}, continuing without PubMed results")
    
    # Merge web and academic results
    if academic_results:
        if raw_results:
            # Combine results for processing
            raw_results = raw_results + academic_results
            logger.info(f"Merged {len(academic_results)} academic results with {len(raw_results) - len(academic_results)} web results")
        else:
            # Only academic results available
            raw_results = academic_results
            logger.info(f"Using {len(academic_results)} academic results only")
    
    if not raw_results:
        # Log which search sources were attempted
        sources_tried = []
        if parallel_enabled and brave_available:
            sources_tried.append("Brave (parallel)")
            sources_tried.append("DuckDuckGo (parallel)")
        elif brave_available:
            sources_tried.append("Brave")
            sources_tried.append("DuckDuckGo (fallback)")
        else:
            sources_tried.append("DuckDuckGo")
        
        logger.warning(f"No results found from {', '.join(sources_tried)} for query: {query[:60]}...")
        return f"No results found for: {query}\n\nTry:\n- Rephrasing the query\n- Using more specific keywords\n- Checking if the search terms are spelled correctly"
    
    # Process results (deduplication, ranking, domain diversity)
    try:
        from tools.utils._result_processor import ResultProcessor
        processor = ResultProcessor(
            max_domain_results=config.WEB_SEARCH.get("max_domain_results", 2)
        )
        processed_results = processor.process_results(raw_results, optimized_query)
        processed_results = processed_results[:max_results]
    except ImportError as e:
        logger.warning(f"Result processor module not available: {e}, using raw results")
        processed_results = raw_results[:max_results]
    except Exception as e:
        logger.warning(f"Result processing failed: {e}, using raw results")
        processed_results = raw_results[:max_results]
    
    # Extract content from top results if enabled
    extract_content = config.WEB_SEARCH.get("extract_content", False)
    if extract_content:
        try:
            from tools.utils._content_extractor import ContentExtractor
            extractor = ContentExtractor(
                enabled=True,
                extract_top_n=config.WEB_SEARCH.get("extract_top_n", 2),
                max_content_length=2000
            )
            processed_results = extractor.extract_from_results(processed_results, optimized_query)
        except ImportError as e:
            logger.warning(f"Content extractor module not available: {e}, continuing without extraction")
        except Exception as e:
            logger.warning(f"Content extraction failed: {e}, continuing without extraction")
    
    # Synthesize results if enabled
    synthesize = config.WEB_SEARCH.get("synthesize_results", False)
    if synthesize and len(processed_results) >= config.WEB_SEARCH.get("synthesize_threshold", 5):
        try:
            synthesized = _synthesize_results(processed_results, query, optimized_query, query_metadata)
            if synthesized and not synthesized.startswith("Error:"):
                # Cache synthesized result
                if cache:
                    try:
                        cache.set(query, max_results, synthesized)
                    except Exception:
                        pass
                return synthesized
        except Exception as e:
            logger.warning(f"Result synthesis failed: {e}, using regular formatting")
    
    # Format results with academic sources included
    sources_parts = []
    if parallel_enabled and brave_available:
        sources_parts.append("Brave + DuckDuckGo")
    elif brave_available:
        sources_parts.append("Brave")
    else:
        sources_parts.append("DuckDuckGo")
    
    # Add academic sources if we have academic results
    if academic_sources_used:
        sources_parts.append(" + ".join(academic_sources_used))
    
    sources_str = " + ".join(sources_parts)
    result = _format_search_results(query, processed_results, sources_str, query_metadata, extract_content)
    
    # Cache result if cache is available
    if cache and result and not result.startswith("Error:"):
        try:
            cache.set(query, max_results, result)
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")
    
    return result
