"""World Bank document search — searches World Bank Open Data API."""

import logging
from typing import List, Dict, Any

import requests
import config
from engine.models import Source

logger = logging.getLogger(__name__)


def _worldbank_document_search_raw(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Search World Bank document repository.

    Response is a dict keyed by document ID strings (not a list).
    The 'facet' key and other non-dict values must be skipped.
    """
    wb_config = getattr(config, 'WORLD_BANK', {})
    if not wb_config.get("enabled", True):
        return []

    endpoint = wb_config.get("search_endpoint", "https://search.worldbank.org/api/v2/wds")
    timeout = wb_config.get("timeout", 15)

    params = {
        "format": "json",
        "qterm": query,
        "rows": min(max_results, 30),
    }

    try:
        response = requests.get(endpoint, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        documents = data.get("documents", {})
        results = []

        for doc_id, doc in documents.items():
            # Skip non-document entries (e.g., "facet" key)
            if not isinstance(doc, dict):
                continue

            title = doc.get("display_title", "No title")
            abstract = doc.get("abstracts", "") or ""
            pdf_url = doc.get("pdfurl", "")
            date = doc.get("docdt", "")
            countries = doc.get("count", "")
            subtopic = doc.get("subtopic", "")

            desc_parts = ["[WorldBank]"]
            if countries:
                desc_parts.append(f"Countries: {countries}")
            if subtopic:
                desc_parts.append(f"Topic: {subtopic}")
            description = " ".join(desc_parts)
            if abstract:
                description += f" - {abstract[:200]}"

            results.append({
                "title": title,
                "url": pdf_url,
                "description": description,
                "date": date,
                "source": "WorldBank",
            })

        logger.info(f"World Bank returned {len(results)} results for: {query[:60]}...")
        return results

    except Exception as e:
        logger.warning(f"World Bank search failed: {e}")
        return []


def worldbank_search_sources(query: str, max_results: int = 10) -> List[Source]:
    """Search World Bank and return Source objects."""
    raw_results = _worldbank_document_search_raw(query, max_results)

    sources = []
    for result in raw_results:
        url = result.get("url", "")
        title = result.get("title", "No title")
        source_id = Source.generate_id(url) if url else Source.generate_id(title)

        # Strip tag from description
        description = result.get("description", "")
        if description.startswith("[WorldBank] "):
            description = description[len("[WorldBank] "):]

        source = Source(
            source_id=source_id,
            url=url,
            title=title,
            source_type="world_bank",
            content_snippet=description,
            publication_date=result.get("date", ""),
        )
        sources.append(source)

    return sources
