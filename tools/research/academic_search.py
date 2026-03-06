"""Academic search tool - searches 7 academic sources in parallel."""

import logging
import re
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
import time
import ssl
import warnings
import threading

import requests
import config
from engine.models import Source

logger = logging.getLogger(__name__)

# Suppress BeautifulSoup encoding warnings
logging.getLogger("bs4.dammit").setLevel(logging.ERROR)

_QUERY_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "from",
    "with", "by", "as", "is", "are", "was", "were", "be", "been", "being",
    "what", "how", "why", "when", "where", "which",
})
_REFINEMENT_ARTIFACTS_RE = re.compile(
    r"\b(?:time period|geography|geographic focus|analysis type|scope)\s*:\s*",
    re.IGNORECASE,
)
_PROVIDER_QUERY_LIMITS = {
    "core": (18, 180),
    "openalex": (16, 140),
    "openalex_fallback": (10, 90),
    "semantic_scholar": (14, 140),
    "semantic_scholar_fallback": (10, 90),
    "world_bank": (10, 90),
    "policy": (12, 100),
    "sec": (10, 90),
    "default": (20, 220),
}
_PROVIDER_DEFAULT_BACKOFF = {
    "openalex": 1.0,
    "semantic_scholar": 30.0,
    "core": 1.0,
}
_PROVIDER_STATE_LOCK = threading.Lock()
_PROVIDER_COOLDOWN_UNTIL: Dict[str, float] = {}


def _sanitize_provider_query(raw_query: str, provider: str) -> str:
    """Normalize refined/decomposed queries for provider API compatibility."""
    if not raw_query:
        return ""

    max_terms, max_chars = _PROVIDER_QUERY_LIMITS.get(
        provider, _PROVIDER_QUERY_LIMITS["default"]
    )
    cleaned = raw_query.replace("|", " ")
    cleaned = _REFINEMENT_ARTIFACTS_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\bfocus on\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[^A-Za-z0-9%$€£/\-+.\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    tokens = re.findall(r"[A-Za-z0-9%$€£][A-Za-z0-9%$€£/\-+.]*", cleaned)
    deduped = []
    seen = set()
    for token in tokens:
        lower = token.lower()
        if lower in _QUERY_STOPWORDS:
            continue
        if lower in seen:
            continue
        seen.add(lower)
        deduped.append(token)
        if len(deduped) >= max_terms:
            break

    normalized = " ".join(deduped).strip()
    if not normalized:
        normalized = cleaned[:max_chars].strip()
    if len(normalized) > max_chars:
        normalized = normalized[:max_chars].strip()

    return normalized


def _respect_provider_cooldown(provider: str) -> None:
    """Sleep only if provider is currently in cooldown due to prior 429."""
    with _PROVIDER_STATE_LOCK:
        now = time.monotonic()
        until = _PROVIDER_COOLDOWN_UNTIL.get(provider, 0.0)
        wait = max(0.0, until - now)
    if wait > 0:
        time.sleep(wait)


def _provider_cooldown_remaining(provider: str) -> float:
    with _PROVIDER_STATE_LOCK:
        now = time.monotonic()
        until = _PROVIDER_COOLDOWN_UNTIL.get(provider, 0.0)
        return max(0.0, until - now)


def _set_provider_cooldown(provider: str, seconds: float) -> None:
    if seconds <= 0:
        return
    with _PROVIDER_STATE_LOCK:
        now = time.monotonic()
        current_until = _PROVIDER_COOLDOWN_UNTIL.get(provider, 0.0)
        next_until = now + seconds
        _PROVIDER_COOLDOWN_UNTIL[provider] = max(current_until, next_until)


def _parse_retry_after_seconds(response: requests.Response, default: float) -> float:
    """Parse Retry-After header; fallback to provider default delay."""
    retry_after = ""
    try:
        retry_after = (response.headers or {}).get("Retry-After", "")
    except Exception:
        retry_after = ""
    if retry_after:
        try:
            parsed = float(retry_after)
            if parsed > 0:
                return parsed
        except Exception:
            pass
    return default


def _duckduckgo_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search using DuckDuckGo and return raw results (not formatted).
    
    Args:
        query: Search query
        max_results: Number of results
        
    Returns:
        List of result dictionaries
    """
    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            from ddgs import DDGS

            logger.info(f"DuckDuckGo search: {query[:100]}... (attempt {attempt + 1}/{max_retries})")

            if attempt > 0:
                time.sleep(retry_delay * attempt)

            # Create SSL context that avoids TLS 1.3 issues
            try:
                ssl_context = ssl.create_default_context()
                if hasattr(ssl_context, 'maximum_version'):
                    ssl_context.maximum_version = ssl.TLSVersion.TLSv1_2
            except (AttributeError, ValueError):
                ssl_context = ssl.create_default_context()

            # Suppress SSL/TLS warnings from ddgs library
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*protocol version.*")
                warnings.filterwarnings("ignore", message=".*Unsupported protocol.*")
                try:
                    with DDGS(verify=ssl_context) as ddgs:
                        results = list(ddgs.text(query, max_results=max_results))
                except ValueError as e:
                    # Handle "Unsupported protocol version 0x304" error
                    if "protocol version" in str(e) or "0x304" in str(e):
                        logger.debug(f"TLS 1.3 issue detected, retrying with different SSL config: {e}")
                        with DDGS() as ddgs:
                            results = list(ddgs.text(query, max_results=max_results))
                    else:
                        raise

            if not results:
                logger.warning(f"DuckDuckGo returned no results for query: {query[:60]}... (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    continue
                return []

            # Convert to standard format
            standardized = []
            for result in results:
                standardized.append({
                    "title": result.get("title", "No title"),
                    "url": result.get("href", ""),
                    "description": result.get("body", "No description")
                })
            
            logger.info(f"DuckDuckGo returned {len(standardized)} results for: {query[:60]}...")
            return standardized

        except Exception as e:
            logger.warning(f"DuckDuckGo search attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                continue
            raise


def _scholar_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search Google Scholar using DuckDuckGo with site: filter.
    
    Args:
        query: Search query
        max_results: Number of results
        
    Returns:
        List of result dictionaries with [Scholar] tag in description
    """
    provider_query = _sanitize_provider_query(query, "default")
    scholar_query = f"site:scholar.google.com {provider_query}"
    results = _duckduckgo_search_raw(scholar_query, max_results)
    
    # Tag results as Scholar
    for result in results:
        if "description" in result:
            result["description"] = f"[Scholar] {result['description']}"
        else:
            result["description"] = "[Scholar] Academic paper"
    
    logger.info(f"Scholar search returned {len(results)} results for: {query[:60]}...")
    return results


def _pubmed_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search PubMed using DuckDuckGo with site: filter.
    
    Args:
        query: Search query
        max_results: Number of results
        
    Returns:
        List of result dictionaries with [PubMed] tag in description
    """
    provider_query = _sanitize_provider_query(query, "default")
    pubmed_query = f"site:pubmed.ncbi.nlm.nih.gov {provider_query}"
    results = _duckduckgo_search_raw(pubmed_query, max_results)
    
    # Tag results as PubMed
    for result in results:
        if "description" in result:
            result["description"] = f"[PubMed] {result['description']}"
        else:
            result["description"] = "[PubMed] Research article"
    
    logger.info(f"PubMed search returned {len(results)} results for: {query[:60]}...")
    return results


def _core_api_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search CORE API for open access academic papers.
    
    Args:
        query: Search query
        max_results: Number of results
        
    Returns:
        List of result dictionaries with [CORE] tag
    """
    academic_config = getattr(config, 'ACADEMIC_SEARCH', {})
    api_key = academic_config.get("core_api_key")
    if not api_key:
        logger.warning("CORE API key not configured, skipping CORE search")
        return []
    
    provider_query = _sanitize_provider_query(query, "core")
    if not provider_query:
        return []

    endpoint = "https://api.core.ac.uk/v3/search/works/"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    params = {
        "q": provider_query,
        "limit": min(max_results, 10),  # CORE API limit
        "page": 1
    }

    try:
        _respect_provider_cooldown("core")
        response = requests.get(endpoint, headers=headers, params=params, timeout=10)
        if response.status_code == 429:
            delay = _parse_retry_after_seconds(
                response, _PROVIDER_DEFAULT_BACKOFF["core"]
            )
            _set_provider_cooldown("core", delay)
            logger.warning("CORE rate limited; backing off %.1fs", delay)
            return []
        response.raise_for_status()
        
        data = response.json()
        works = data.get("results", [])
        
        results = []
        for work in works:
            # Extract authors
            authors = [author.get("name", "") for author in work.get("authors", [])]
            authors_str = ", ".join(authors[:3])  # First 3 authors
            if len(authors) > 3:
                authors_str += " et al."
            
            # Build description
            desc_parts = ["[CORE]"]
            if authors_str:
                desc_parts.append(authors_str)
            if work.get("yearPublished"):
                desc_parts.append(f"({work['yearPublished']})")
            if work.get("citationCount") is not None:
                desc_parts.append(f"Citations: {work['citationCount']}")
            
            description = " ".join(desc_parts)
            if work.get("abstract"):
                description += f" - {work['abstract'][:200]}"
            
            # Use downloadUrl if available, otherwise use display link
            url = work.get("downloadUrl") or work.get("links", [{}])[0].get("url", "")
            if not url and work.get("links"):
                for link in work.get("links", []):
                    if link.get("type") == "display":
                        url = link.get("url", "")
                        break
            
            results.append({
                "title": work.get("title", "No title"),
                "url": url,
                "description": description,
                "doi": work.get("doi"),
                "year": work.get("yearPublished"),
                "citation_count": work.get("citationCount", 0),
                "source": "CORE"
            })
        
        logger.info(f"CORE API returned {len(results)} results for: {query[:60]}...")
        return results
        
    except Exception as e:
        logger.warning(f"CORE API search failed: {e}")
        return []


def _crossref_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search CrossRef for academic works with DOIs, abstracts, and citation counts."""
    crossref_config = getattr(config, 'CROSSREF', {})
    if not crossref_config.get("enabled", True):
        return []

    endpoint = crossref_config.get("endpoint", "https://api.crossref.org/works")
    timeout = crossref_config.get("timeout", 15)
    email = crossref_config.get("polite_email", "")

    provider_query = _sanitize_provider_query(query, "default")
    if not provider_query:
        return []

    params = {
        "query": provider_query,
        "rows": min(max_results, 20),
    }
    if email:
        params["mailto"] = email

    try:
        response = requests.get(endpoint, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.warning("CrossRef API search failed: %s", e)
        return []

    results = []
    for item in data.get("message", {}).get("items", []):
        title_list = item.get("title", [])
        title = title_list[0] if title_list else "No title"

        authors = []
        for author in item.get("author", []):
            given = author.get("given", "")
            family = author.get("family", "")
            name = f"{given} {family}".strip()
            if name:
                authors.append(name)
        authors_str = ", ".join(authors[:3])
        if len(authors) > 3:
            authors_str += " et al."

        doi = item.get("DOI", "")
        cite_count = item.get("is-referenced-by-count", 0) or 0

        # Extract year from published-print or published-online
        year = None
        for date_field in ("published-print", "published-online"):
            date_parts = item.get(date_field, {}).get("date-parts", [[]])
            if date_parts and date_parts[0]:
                year = date_parts[0][0]
                break

        # Strip HTML tags from abstract
        abstract = item.get("abstract", "") or ""
        abstract = re.sub(r"<[^>]+>", "", abstract).strip()

        desc_parts = ["[CrossRef]"]
        if authors_str:
            desc_parts.append(authors_str)
        if year:
            desc_parts.append(f"({year})")
        if cite_count:
            desc_parts.append(f"Citations: {cite_count}")
        description = " ".join(desc_parts)
        if abstract:
            description += f" - {abstract[:200]}"

        url = f"https://doi.org/{doi}" if doi else ""

        results.append({
            "title": title,
            "url": url,
            "description": description,
            "doi": doi,
            "year": year,
            "citation_count": cite_count,
            "source": "CrossRef",
        })

    logger.info("CrossRef returned %d results for: %s...", len(results), query[:60])
    return results


def _arxiv_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search arXiv using the native Atom XML API."""
    import xml.etree.ElementTree as ET

    arxiv_config = getattr(config, 'ARXIV', {})
    if not arxiv_config.get("enabled", True):
        return []

    endpoint = arxiv_config.get("endpoint", "http://export.arxiv.org/api/query")
    timeout = arxiv_config.get("timeout", 15)

    provider_query = _sanitize_provider_query(query, "default")
    if not provider_query:
        return []

    params = {
        "search_query": f"all:{provider_query}",
        "max_results": min(max_results, 20),
        "sortBy": "relevance",
    }

    try:
        response = requests.get(endpoint, params=params, timeout=timeout)
        response.raise_for_status()
        root = ET.fromstring(response.text)
    except Exception as e:
        logger.warning("arXiv API search failed: %s", e)
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    results = []
    for entry in root.findall("atom:entry", ns):
        title_el = entry.find("atom:title", ns)
        summary_el = entry.find("atom:summary", ns)
        published_el = entry.find("atom:published", ns)
        id_el = entry.find("atom:id", ns)

        title = title_el.text.strip() if title_el is not None and title_el.text else "No title"
        abstract = summary_el.text.strip() if summary_el is not None and summary_el.text else ""
        url = id_el.text.strip() if id_el is not None and id_el.text else ""
        published = published_el.text.strip()[:4] if published_el is not None and published_el.text else ""

        authors = []
        for author_el in entry.findall("atom:author", ns):
            name_el = author_el.find("atom:name", ns)
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())

        authors_str = ", ".join(authors[:3])
        if len(authors) > 3:
            authors_str += " et al."

        desc_parts = ["[arXiv]"]
        if authors_str:
            desc_parts.append(authors_str)
        if published:
            desc_parts.append(f"({published})")
        description = " ".join(desc_parts)
        if abstract:
            description += f" - {abstract[:200]}"

        results.append({
            "title": title,
            "url": url,
            "description": description,
            "year": int(published) if published else None,
            "source": "arXiv",
        })

    logger.info("arXiv API returned %d results for: %s...", len(results), query[:60])
    return results


def _biorxiv_search_raw(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """Search bioRxiv via DuckDuckGo."""
    provider_query = _sanitize_provider_query(query, "default")
    biorxiv_query = f"site:biorxiv.org {provider_query}"
    results = _duckduckgo_search_raw(biorxiv_query, max_results)
    for result in results:
        result["description"] = f"[bioRxiv] {result.get('description', 'Biology preprint')}"
    logger.info(f"bioRxiv search returned {len(results)} results")
    return results


def _medrxiv_search_raw(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """Search medRxiv via DuckDuckGo."""
    provider_query = _sanitize_provider_query(query, "default")
    medrxiv_query = f"site:medrxiv.org {provider_query}"
    results = _duckduckgo_search_raw(medrxiv_query, max_results)
    for result in results:
        result["description"] = f"[medRxiv] {result.get('description', 'Medical preprint')}"
    logger.info(f"medRxiv search returned {len(results)} results")
    return results


def _pmc_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search PubMed Central via DuckDuckGo."""
    # DuckDuckGo site: filters are unreliable for PMC, so use keyword search + URL filtering
    pmc_keywords = ["PMC", "open access", "PubMed Central"]
    
    provider_query = _sanitize_provider_query(query, "default")
    if not provider_query:
        return []

    # Try queries with PMC keywords (avoid site: filter which causes errors)
    search_queries = [
        f"{provider_query} {' '.join(pmc_keywords)}",
        f"{provider_query} PMC",
        f"{provider_query} PubMed Central open access",
    ]
    
    for search_query in search_queries:
        try:
            # Get more results than needed to account for filtering
            results = _duckduckgo_search_raw(search_query, max_results * 3)
            
            # Filter to only PMC URLs
            pmc_results = []
            for result in results:
                url = result.get("url", "").lower()
                # Check for PMC URL patterns
                if any(pattern in url for pattern in [
                    "pubmed.ncbi.nlm.nih.gov/pmc",
                    "pmc.ncbi.nlm.nih.gov",
                    "/pmc/articles/",
                    "/pmc/",
                ]):
                    result["description"] = f"[PMC] {result.get('description', 'Open access article')}"
                    pmc_results.append(result)
                    if len(pmc_results) >= max_results:
                        break
            
            if pmc_results:
                logger.info(f"PMC search returned {len(pmc_results)} results")
                return pmc_results
                
        except Exception as e:
            logger.debug(f"PMC search with query '{search_query}' failed: {e}, trying next format")
            continue
    
    logger.warning("PMC search failed with all query formats")
    return []


def _reconstruct_abstract(inverted_index: dict) -> str:
    """Reconstruct abstract from OpenAlex abstract_inverted_index format.

    The inverted index maps each word to a list of positions where it appears.
    We invert this to get (position, word) pairs and join them in order.
    """
    if not inverted_index:
        return ""
    pairs = []
    for word, positions in inverted_index.items():
        for pos in positions:
            pairs.append((pos, word))
    pairs.sort(key=lambda x: x[0])
    return " ".join(word for _, word in pairs)


def _openalex_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search OpenAlex for academic works.

    Uses the polite pool (mailto parameter) for higher rate limits.
    """
    openalex_config = getattr(config, 'OPENALEX', {})
    if not openalex_config.get("enabled", True):
        return []

    endpoint = openalex_config.get("endpoint", "https://api.openalex.org/works")
    timeout = openalex_config.get("timeout", 15)
    email = openalex_config.get("polite_email", "")

    active_query = _sanitize_provider_query(query, "openalex")
    if not active_query:
        return []

    if _provider_cooldown_remaining("openalex") > 0:
        logger.info("OpenAlex in cooldown window; skipping request")
        return []

    max_retries = 3
    for attempt in range(max_retries):
        params = {
            "search": active_query,
            "per_page": min(max_results, 25),
        }
        if email:
            params["mailto"] = email

        try:
            _respect_provider_cooldown("openalex")
            response = requests.get(endpoint, params=params, timeout=timeout)
            if response.status_code == 400 and attempt == 0:
                fallback_query = _sanitize_provider_query(active_query, "openalex_fallback")
                if fallback_query and fallback_query != active_query:
                    logger.warning(
                        "OpenAlex rejected query shape; retrying with provider-safe fallback query"
                    )
                    active_query = fallback_query
                    continue
                return []
            if response.status_code == 429 and attempt < max_retries - 1:
                delay = _parse_retry_after_seconds(
                    response,
                    _PROVIDER_DEFAULT_BACKOFF["openalex"] * (attempt + 1),
                )
                _set_provider_cooldown("openalex", delay)
                logger.warning("OpenAlex rate limited; backing off %.1fs", delay)
                return []
            response.raise_for_status()
            data = response.json()

            results = []
            for work in data.get("results", []):
                # Reconstruct abstract from inverted index
                abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))

                # Extract authors
                authors = []
                for authorship in work.get("authorships", []):
                    author = authorship.get("author", {})
                    name = author.get("display_name", "")
                    if name:
                        authors.append(name)

                authors_str = ", ".join(authors[:3])
                if len(authors) > 3:
                    authors_str += " et al."

                # Build description
                desc_parts = ["[OpenAlex]"]
                if authors_str:
                    desc_parts.append(authors_str)
                year = work.get("publication_date", "")[:4] if work.get("publication_date") else ""
                if year:
                    desc_parts.append(f"({year})")
                cite_count = work.get("cited_by_count", 0)
                if cite_count:
                    desc_parts.append(f"Citations: {cite_count}")
                description = " ".join(desc_parts)
                if abstract:
                    description += f" - {abstract[:200]}"

                # DOI handling
                doi_raw = work.get("doi", "")
                doi = doi_raw.replace("https://doi.org/", "") if doi_raw else ""
                url = doi_raw or ""

                results.append({
                    "title": work.get("title", "No title"),
                    "url": url,
                    "description": description,
                    "doi": doi,
                    "year": int(year) if year else None,
                    "citation_count": cite_count,
                    "source": "OpenAlex",
                })

            logger.info(f"OpenAlex returned {len(results)} results for: {active_query[:60]}...")
            return results

        except Exception as e:
            logger.warning(f"OpenAlex search failed: {e}")
            return []

    return []


def _semantic_scholar_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search Semantic Scholar for academic papers.

    Includes exponential backoff on 429 rate limit responses.
    """
    ss_config = getattr(config, 'SEMANTIC_SCHOLAR', {})
    if not ss_config.get("enabled", True):
        return []

    endpoint = ss_config.get("endpoint", "https://api.semanticscholar.org/graph/v1/paper/search")
    timeout = ss_config.get("timeout", 15)
    api_key = ss_config.get("api_key", "")
    active_query = _sanitize_provider_query(query, "semantic_scholar")
    if not active_query:
        return []
    if _provider_cooldown_remaining("semantic_scholar") > 0:
        logger.info("Semantic Scholar in cooldown window; skipping request")
        return []

    params = {
        "query": active_query,
        "limit": min(max_results, 20),
        "fields": "title,url,year,citationCount,abstract,authors,externalIds",
    }
    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    # Provider-specific backoff for rate limiting.
    for attempt in range(3):
        try:
            _respect_provider_cooldown("semantic_scholar")
            response = requests.get(endpoint, params=params, headers=headers, timeout=timeout)
            if response.status_code == 400 and attempt == 0:
                fallback_query = _sanitize_provider_query(active_query, "semantic_scholar_fallback")
                if fallback_query and fallback_query != active_query:
                    active_query = fallback_query
                    params["query"] = active_query
                    logger.warning(
                        "Semantic Scholar rejected query shape; retrying with provider-safe fallback query"
                    )
                    continue
                return []
            if response.status_code == 429 and attempt < 2:
                delay = _parse_retry_after_seconds(
                    response,
                    _PROVIDER_DEFAULT_BACKOFF["semantic_scholar"] * (attempt + 1),
                )
                _set_provider_cooldown("semantic_scholar", delay)
                logger.warning(
                    "Semantic Scholar rate limited (attempt %d), backing off %.1fs...",
                    attempt + 1,
                    delay,
                )
                return []
            response.raise_for_status()
            data = response.json()

            results = []
            for paper in data.get("data", []):
                authors = [a.get("name", "") for a in paper.get("authors", [])]
                authors_str = ", ".join(authors[:3])
                if len(authors) > 3:
                    authors_str += " et al."

                desc_parts = ["[SemanticScholar]"]
                if authors_str:
                    desc_parts.append(authors_str)
                year = paper.get("year")
                if year:
                    desc_parts.append(f"({year})")
                cite_count = paper.get("citationCount", 0) or 0
                if cite_count:
                    desc_parts.append(f"Citations: {cite_count}")
                description = " ".join(desc_parts)
                abstract = paper.get("abstract", "") or ""
                if abstract:
                    description += f" - {abstract[:200]}"

                external_ids = paper.get("externalIds", {}) or {}
                doi = external_ids.get("DOI", "")
                url = paper.get("url", "")
                if doi and not url:
                    url = f"https://doi.org/{doi}"

                results.append({
                    "title": paper.get("title", "No title"),
                    "url": url,
                    "description": description,
                    "doi": doi,
                    "year": year,
                    "citation_count": cite_count,
                    "source": "SemanticScholar",
                })

            logger.info(f"Semantic Scholar returned {len(results)} results for: {active_query[:60]}...")
            return results

        except Exception as e:
            logger.warning(f"Semantic Scholar search failed: {e}")
            return []

    return []


def _check_scihub_availability(doi: Optional[str] = None, title: Optional[str] = None) -> Optional[str]:
    """
    Check if a paper is available on Sci-Hub and return PDF URL.
    
    Args:
        doi: DOI of the paper
        title: Title of the paper
        
    Returns:
        PDF URL if found, None otherwise
    """
    if not doi and not title:
        return None
    
    academic_config = getattr(config, 'ACADEMIC_SEARCH', {})
    scihub_mirrors = academic_config.get("scihub_mirrors", [
        "https://sci-hub.se",
        "https://sci-hub.st",
        "https://sci-hub.ru"
    ])
    
    search_term = doi if doi else title
    
    for mirror in scihub_mirrors:
        try:
            url = f"{mirror}/{quote(search_term)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            
            if response.status_code == 200:
                try:
                    from bs4 import BeautifulSoup
                    
                    # Suppress BeautifulSoup encoding warnings
                    warnings.filterwarnings("ignore", category=UserWarning, module="bs4.dammit")
                    warnings.filterwarnings("ignore", message=".*could not be decoded.*")
                    
                    bs4_logger = logging.getLogger("bs4.dammit")
                    original_level = bs4_logger.level
                    bs4_logger.setLevel(logging.ERROR)
                    
                    try:
                        soup = BeautifulSoup(response.content, 'html.parser', from_encoding='utf-8')
                    finally:
                        bs4_logger.setLevel(original_level)
                    
                    # Look for PDF embed or download link
                    pdf_embed = soup.find('embed', {'type': 'application/pdf'})
                    if pdf_embed:
                        pdf_url = pdf_embed.get('src', '')
                        if not pdf_url.startswith('http'):
                            pdf_url = mirror + pdf_url if pdf_url.startswith('/') else f"{mirror}/{pdf_url}"
                        return pdf_url
                    
                    # Look for PDF download button/link
                    pdf_link = soup.find('a', href=re.compile(r'\.pdf|download'))
                    if pdf_link:
                        pdf_url = pdf_link.get('href', '')
                        if not pdf_url.startswith('http'):
                            pdf_url = mirror + pdf_url if pdf_url.startswith('/') else f"{mirror}/{pdf_url}"
                        return pdf_url
                        
                except ImportError:
                    logger.warning("BeautifulSoup4 not available for Sci-Hub parsing")
                    return None
                except Exception as e:
                    logger.debug(f"Sci-Hub parsing failed for {mirror}: {e}")
                    continue
                    
        except requests.exceptions.RequestException:
            continue
        except Exception as e:
            logger.debug(f"Sci-Hub check failed for {mirror}: {e}")
            continue
    
    return None


def academic_search_sources(query: str, max_results: int = 10) -> List[Source]:
    """
    Search multiple academic sources and return structured Source objects.

    Runs the same parallel search + Sci-Hub check + dedup pipeline as
    academic_search(), but returns List[Source] instead of a formatted string.

    Args:
        query: Search query
        max_results: Maximum number of results to return

    Returns:
        List of Source objects with structured data preserved
    """
    logger.info(f"Academic search (structured): {query[:100]}...")

    # Get config with defaults
    academic_config = getattr(config, 'ACADEMIC_SEARCH', {})
    academic_max = academic_config.get("default_max_results", 10)
    max_results = min(max_results, academic_max)

    # Search all sources in parallel
    all_results = []

    try:
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(_scholar_search_raw, query, max_results // 2): "Scholar",
                executor.submit(_pubmed_search_raw, query, max_results // 2): "PubMed",
                executor.submit(_core_api_search, query, max_results // 2): "CORE",
                executor.submit(_arxiv_search_raw, query, max_results // 4): "arXiv",
                executor.submit(_biorxiv_search_raw, query, max_results // 6): "bioRxiv",
                executor.submit(_medrxiv_search_raw, query, max_results // 6): "medRxiv",
                executor.submit(_pmc_search_raw, query, max_results // 4): "PMC",
                executor.submit(_openalex_search_raw, query, max_results // 2): "OpenAlex",
                executor.submit(_semantic_scholar_search_raw, query, max_results // 2): "SemanticScholar",
                executor.submit(_crossref_search_raw, query, max_results // 2): "CrossRef",
            }

            for future in as_completed(futures):
                source = futures[future]
                try:
                    results = future.result(timeout=None)
                    if results:
                        all_results.extend(results)
                        logger.info(f"Academic search: {source} returned {len(results)} results")
                except KeyboardInterrupt:
                    logger.info("Academic search interrupted, cancelling remaining searches...")
                    for f in futures:
                        f.cancel()
                    raise
                except Exception as e:
                    logger.warning(f"Academic search: {source} failed: {e}")
    except KeyboardInterrupt:
        logger.info("Academic search interrupted by user")
        raise

    if not all_results:
        return []

    # Check Sci-Hub for full-text access in parallel
    logger.info(f"Checking Sci-Hub availability for {len(all_results)} papers...")

    def check_scihub_for_result(result):
        """Helper function to check Sci-Hub for a single result."""
        doi = result.get("doi")
        title = result.get("title")

        if doi or title:
            scihub_url = _check_scihub_availability(doi=doi, title=title)
            if scihub_url:
                result["scihub_url"] = scihub_url
                result["full_text_available"] = True
                desc = result.get("description", "")
                if "[Full Text Available]" not in desc:
                    result["description"] = f"{desc} [Full Text Available]"
        return result

    if all_results:
        try:
            with ThreadPoolExecutor(max_workers=min(10, len(all_results))) as executor:
                futures = [executor.submit(check_scihub_for_result, result) for result in all_results]
                for future in as_completed(futures):
                    try:
                        future.result(timeout=None)
                    except KeyboardInterrupt:
                        logger.info("Sci-Hub checking interrupted, cancelling remaining checks...")
                        for f in futures:
                            f.cancel()
                        raise
        except KeyboardInterrupt:
            logger.info("Sci-Hub checking interrupted by user")
            raise

    # Deduplicate by title/DOI
    seen = set()
    unique_results = []
    for result in all_results:
        key = result.get("doi") or result.get("title", "").lower()
        if key and key not in seen:
            seen.add(key)
            unique_results.append(result)

    # Limit results
    unique_results = unique_results[:max_results]

    # Convert to Source objects
    sources = []
    tag_pattern = re.compile(r'^\[(Scholar|CORE|PubMed|arXiv|bioRxiv|medRxiv|PMC|OpenAlex|SemanticScholar|CrossRef)\]\s*')

    for result in unique_results:
        url = result.get("url", "")
        doi = result.get("doi")
        title = result.get("title", "No title")

        # Construct URL from DOI if no direct URL
        if not url and doi:
            url = f"https://doi.org/{doi}"

        # Generate source_id from best available identifier
        id_key = url or (f"https://doi.org/{doi}" if doi else title)
        source_id = Source.generate_id(id_key)

        # Strip source tags from description (formatting artifacts)
        description = result.get("description", "")
        description = tag_pattern.sub('', description).strip()
        description = description.replace("[Full Text Available]", "").strip()

        source = Source(
            source_id=source_id,
            url=url,
            title=title,
            source_type="academic",
            content_snippet=description,
            cited_by_count=result.get("citation_count", 0) or 0,
            publication_date=str(result.get("year", "")) if result.get("year") else ""
        )
        sources.append(source)

    return sources


def academic_search(query: str, max_results: int = 10) -> str:
    """
    Search multiple academic sources and check Sci-Hub for full-text access.

    Args:
        query: Search query
        max_results: Maximum number of results to return

    Returns:
        Formatted academic search results with citations and full-text indicators
    """
    sources = academic_search_sources(query, max_results)

    if not sources:
        return f"No academic results found for: {query}\n\nTry:\n- Using more specific keywords\n- Checking spelling\n- Using academic terminology"

    # Format results from Source objects
    formatted = [f"Academic search results for: {query}\n"]

    for i, source in enumerate(sources, 1):
        formatted.append(f"\n{i}. {source.title}")
        if source.url:
            formatted.append(f"   URL: {source.url}")

        # Add year and citations if available
        meta_parts = []
        if source.publication_date:
            meta_parts.append(f"Year: {source.publication_date}")
        if source.cited_by_count:
            meta_parts.append(f"Citations: {source.cited_by_count}")
        if meta_parts:
            formatted.append(f"   {' | '.join(meta_parts)}")

        if source.content_snippet:
            formatted.append(f"   {source.content_snippet}")

    formatted.append(f"\n\nSummary: Found {len(sources)} papers")

    return "\n".join(formatted)
