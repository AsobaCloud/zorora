"""Source aggregator - collects sources from academic, web, and newsroom."""

import logging
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests

import config
from engine.models import Source
from tools.research.academic_search import academic_search_sources
from tools.research.web_search import web_search_sources
from tools.research.newsroom import fetch_newsroom_api, _extract_keywords
from tools.research.worldbank_search import worldbank_search_sources
from tools.research.policy_search import policy_search_sources
from tools.research.sec_search import sec_search_sources
from tools.research.local_sme_corpus import load_local_sme_sources

logger = logging.getLogger(__name__)

POLICY_KEYWORDS = {
    'policy', 'regulation', 'regulatory', 'legislation', 'bill',
    'congress', 'federal', 'government', 'governance', 'law', 'mandate',
    'executive order', 'statute', 'compliance', 'rulemaking', 'subsidy',
    'tariff', 'sanction',
}

SEC_KEYWORDS = {
    'sec', 'filing', '10-k', '10-q', '8-k', 'annual report',
    'corporate', 'earnings', 'financial statement', 'balance sheet',
    'revenue', 'stock', 'equity', 'securities', 'ipo', 'merger',
    'acquisition', 'shareholder', 'company', 'investor',
}


def _query_matches_keywords(query: str, keywords: set) -> bool:
    """Check if query contains any of the given keywords (case-insensitive)."""
    query_lower = query.lower()
    return any(kw in query_lower for kw in keywords)


# Scouting pipeline stages that qualify as knowledge sources (SEP-059)
_QUALIFYING_STAGES = {"feasibility", "diligence", "decision"}


def scouting_knowledge_sources(query: str, imaging_store) -> List[Source]:
    """Return internal Source objects from completed scouting cases relevant to query.

    Only items at feasibility, diligence, or decision stage are included.
    Relevance and ranking are determined by FTS5 BM25 over feasibility findings
    (SEP-065).  Falls back gracefully if the FTS table is absent.
    """
    try:
        if not query or not query.strip():
            return []

        # --- FTS5 path (SEP-065) ---
        fts_search = getattr(imaging_store, "search_feasibility_fts", None)
        if callable(fts_search):
            try:
                fts_hits = fts_search(query, limit=50)
            except Exception as exc:
                logger.warning("FTS search failed, returning empty: %s", exc)
                return []

            if not fts_hits:
                return []

            # fts_hits[i]["item_id"] is the feasibility_results.id == "{asset_id}:{tab}"
            # Extract the asset id (everything before the last colon-separated tab)
            results: List[Source] = []
            seen_asset_ids: set = set()

            # Build a lookup of qualifying asset ids keyed by asset stage
            qualifying_asset_ids: set = set()
            for stage in _QUALIFYING_STAGES:
                try:
                    items = imaging_store.list_scouting_items("brownfield", stage=stage)
                except Exception:
                    items = []
                for item in items:
                    qualifying_asset_ids.add(item.get("id") or "")

            for hit in fts_hits:
                # FTS item_id == feasibility_results.item_id == asset id directly
                asset_id = hit.get("item_id") or ""
                if not asset_id:
                    continue

                if asset_id not in qualifying_asset_ids:
                    continue
                if asset_id in seen_asset_ids:
                    continue
                seen_asset_ids.add(asset_id)

                # Fetch asset details for title/snippet
                name = ""
                technology = ""
                country = ""
                findings_text = ""
                try:
                    # Try pipeline asset first
                    asset = imaging_store.get_pipeline_asset(asset_id)
                    if asset:
                        name = asset.get("asset_name") or asset.get("name") or ""
                        technology = asset.get("technology") or ""
                        country = asset.get("country") or ""
                except Exception:
                    pass
                try:
                    feasibility_results = imaging_store.get_feasibility_results(asset_id)
                    for fr in feasibility_results:
                        findings = fr.get("findings") or {}
                        findings_text += " " + (findings.get("key_finding") or "")
                        findings_text += " " + fr.get("conclusion", "")
                        findings_text += " " + fr.get("tab", "")
                except Exception:
                    pass

                url = f"scouting://brownfield/{asset_id}"
                title = f"[Internal] {name} — Scouting Feasibility"
                snippet = findings_text.strip()[:300] if findings_text.strip() else f"{technology} in {country}"
                source_id = Source.generate_id(url)

                results.append(
                    Source(
                        source_id=source_id,
                        url=url,
                        title=title,
                        source_type="internal",
                        content_snippet=snippet,
                    )
                )

            return results

        # --- Fallback: token-overlap (legacy / pre-SEP-065 stores) ---
        query_tokens = set(query.lower().split())
        fallback_results: List[Source] = []

        for stage in _QUALIFYING_STAGES:
            try:
                items = imaging_store.list_scouting_items("brownfield", stage=stage)
            except Exception:
                items = []
            for item in items:
                name = item.get("asset_name") or item.get("name") or ""
                technology = item.get("technology") or ""
                country = item.get("country") or ""
                item_id = item.get("id") or ""

                findings_text = ""
                try:
                    feasibility_results = imaging_store.get_feasibility_results(item_id)
                    for fr in feasibility_results:
                        findings = fr.get("findings") or {}
                        findings_text += " " + (findings.get("key_finding") or "")
                        findings_text += " " + fr.get("conclusion", "")
                        findings_text += " " + fr.get("tab", "")
                except Exception:
                    pass

                haystack = f"{name} {technology} {country} {findings_text}".lower()
                haystack_tokens = set(haystack.split())
                overlap = query_tokens & haystack_tokens
                meaningful_overlap = {t for t in overlap if len(t) > 3}
                if not meaningful_overlap:
                    continue

                url = f"scouting://brownfield/{item_id}"
                title = f"[Internal] {name} — Scouting Feasibility"
                snippet = findings_text.strip()[:300] if findings_text.strip() else f"{technology} in {country}"
                source_id = Source.generate_id(url)

                fallback_results.append(
                    Source(
                        source_id=source_id,
                        url=url,
                        title=title,
                        source_type="internal",
                        content_snippet=snippet,
                    )
                )

        return fallback_results

    except Exception as exc:
        logger.warning(f"scouting_knowledge_sources failed: {exc}")
        return []


def parse_newsroom_results(articles: List[Dict[str, Any]], query: str) -> List[Source]:
    """Parse newsroom API articles into Source objects, filtering by query relevance."""
    keywords = _extract_keywords(query) if query else []
    sources = []

    for article in articles:
        # Relevance gate: at least one keyword must appear in title or tags
        if keywords:
            haystack = f"{article.get('headline', '')} {' '.join(str(t) for t in article.get('topic_tags', []))}".lower()
            matched = sum(1 for kw in keywords if kw in haystack)
            min_required = 2 if len(keywords) >= 3 else 1
            if matched < min_required:
                continue
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

    logger.info(f"Newsroom: {len(sources)}/{len(articles)} passed relevance filter")
    return sources


def aggregate_sources(
    query: str,
    max_results_per_source: int = 10,
    include_brave_news: bool = False,
    force_policy: bool = False,
    suppress_policy: bool = False,
    include_local_sme: bool = False,
    sme_intent_domain: str = "",
    asset_metadata: dict = None,
    imaging_store=None,
) -> List[Source]:
    """
    Aggregate sources from academic, web, newsroom, and optionally Brave News in parallel.

    Args:
        query: Research query
        max_results_per_source: Max results per source type
        include_brave_news: Whether to include Brave News API results (depth 3)
        force_policy: Force-include policy channel even when query has no policy keywords
        suppress_policy: Force-exclude policy channel regardless of query keywords

    Returns:
        List of Source objects
    """
    logger.info(f"Aggregating sources for: {query[:60]}... (brave_news={include_brave_news})")
    all_sources = []

    def fetch_academic():
        try:
            return academic_search_sources(query, max_results=max_results_per_source)
        except Exception as e:
            logger.warning(f"Academic search failed: {e}")
            return []

    def fetch_web():
        try:
            return web_search_sources(query, max_results=max_results_per_source)
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

    def fetch_brave_news():
        """Fetch news results from Brave News API."""
        try:
            if not config.BRAVE_SEARCH.get("enabled") or not config.BRAVE_SEARCH.get("api_key"):
                logger.warning("Brave News skipped: API not configured")
                return []

            news_endpoint = config.BRAVE_SEARCH.get(
                "news_endpoint", "https://api.search.brave.com/res/v1/news/search"
            )
            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": config.BRAVE_SEARCH["api_key"],
            }
            params = {
                "q": query,
                "count": min(max_results_per_source, 20),
                "search_lang": "en",
                "freshness": "pw",  # Past week
            }

            response = requests.get(
                news_endpoint,
                headers=headers,
                params=params,
                timeout=config.BRAVE_SEARCH.get("timeout", 10),
            )
            response.raise_for_status()

            news_results = response.json().get("results", [])
            sources = []
            for item in news_results:
                url = item.get("url", "")
                title = item.get("title", "No title")
                description = item.get("description", "")
                source_id = Source.generate_id(url) if url else Source.generate_id(title)

                # Extract source domain
                source_name = ""
                if url:
                    try:
                        source_name = urlparse(url).netloc.replace("www.", "")
                    except Exception:
                        pass

                snippet_parts = []
                if source_name:
                    snippet_parts.append(f"Source: {source_name}")
                if description:
                    snippet_parts.append(description[:300])

                source = Source(
                    source_id=source_id,
                    url=url,
                    title=title,
                    source_type="news",
                    content_snippet=" | ".join(snippet_parts),
                    publication_date=item.get("age", ""),
                )
                sources.append(source)

            logger.info(f"Brave News returned {len(sources)} results")
            return sources

        except Exception as e:
            logger.warning(f"Brave News fetch failed: {e}")
            return []

    def fetch_worldbank():
        try:
            return worldbank_search_sources(query, max_results=max_results_per_source)
        except Exception as e:
            logger.warning(f"World Bank search failed: {e}")
            return []

    def fetch_policy():
        try:
            return policy_search_sources(query, max_results=max_results_per_source)
        except Exception as e:
            logger.warning(f"Policy search failed: {e}")
            return []

    def fetch_sec():
        try:
            return sec_search_sources(query, max_results=max_results_per_source)
        except Exception as e:
            logger.warning(f"SEC EDGAR search failed: {e}")
            return []

    def fetch_local_sme():
        try:
            return load_local_sme_sources(
                query=query,
                intent_domain=sme_intent_domain,
                asset_metadata=asset_metadata,
                max_results=max_results_per_source,
            )
        except Exception as e:
            logger.warning(f"Local SME corpus fetch failed: {e}")
            return []

    # Determine which conditional channels to include
    if suppress_policy:
        include_policy = False
    elif force_policy:
        include_policy = True
    else:
        include_policy = _query_matches_keywords(query, POLICY_KEYWORDS)
    include_sec = _query_matches_keywords(query, SEC_KEYWORDS)

    # Fetch in parallel
    max_workers = 4 + (1 if include_brave_news else 0) + 1 + (1 if include_policy else 0) + (1 if include_sec else 0) + (1 if include_local_sme else 0)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_academic): "academic",
            executor.submit(fetch_web): "web",
            executor.submit(fetch_newsroom): "newsroom",
            executor.submit(fetch_worldbank): "world_bank",
        }
        if include_brave_news:
            futures[executor.submit(fetch_brave_news)] = "brave_news"
        if include_policy:
            futures[executor.submit(fetch_policy)] = "policy"
        if include_sec:
            futures[executor.submit(fetch_sec)] = "sec_edgar"
        if include_local_sme:
            futures[executor.submit(fetch_local_sme)] = "local_sme"

        for future in as_completed(futures):
            source_type = futures[future]
            try:
                sources = future.result()
                all_sources.extend(sources)
                logger.info(f"✓ {source_type}: {len(sources)} sources")
            except Exception as e:
                logger.warning(f"{source_type} aggregation failed: {e}")

    # SEP-059: inject scouting internal sources when an imaging store is provided
    if imaging_store is not None:
        internal = scouting_knowledge_sources(query=query, imaging_store=imaging_store)
        if internal:
            all_sources.extend(internal)
            logger.info(f"Scouting internal sources added: {len(internal)}")

    logger.info(f"Total sources aggregated: {len(all_sources)}")
    return all_sources
