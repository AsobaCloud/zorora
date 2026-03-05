"""SEC EDGAR full-text search — searches SEC filing documents."""

import logging
from typing import List, Dict, Any

import requests
import config
from engine.models import Source

logger = logging.getLogger(__name__)


def _sec_edgar_search_raw(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Search SEC EDGAR full-text search index.

    Requires User-Agent header per SEC fair access policy.
    """
    sec_config = getattr(config, 'SEC_EDGAR', {})
    if not sec_config.get("enabled", True):
        return []

    endpoint = sec_config.get("endpoint", "https://efts.sec.gov/LATEST/search-index")
    timeout = sec_config.get("timeout", 15)
    user_agent = sec_config.get("user_agent", "Asoba admin@asoba.co")

    params = {
        "q": query,
        "dateRange": "custom",
        "startdt": "2020-01-01",
        "forms": "10-K,10-Q,8-K",
    }
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
    }

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        hits = data.get("hits", {}).get("hits", [])
        results = []

        for hit in hits[:max_results]:
            src = hit.get("_source", {})
            display_names = src.get("display_names", [])
            company = display_names[0] if display_names else "Unknown"
            ciks = src.get("ciks", [])
            adsh = src.get("adsh", "")
            root_forms = src.get("root_forms", [])
            form_type = root_forms[0] if root_forms else ""
            file_desc = src.get("file_description", "")
            period = src.get("period_of_report", "")
            file_date = src.get("file_date", "")

            # Build filing URL from accession number
            url = ""
            if adsh:
                adsh_clean = adsh.replace("-", "")
                url = f"https://www.sec.gov/Archives/edgar/data/{ciks[0] if ciks else ''}/{adsh_clean}/{adsh}-index.htm"

            title = f"{company} - {form_type}" if form_type else f"{company} - {file_desc}"

            desc_parts = [f"[SEC_EDGAR] {form_type}"]
            if file_desc:
                desc_parts.append(file_desc)
            if period:
                desc_parts.append(f"Period: {period}")
            description = " | ".join(desc_parts)

            results.append({
                "title": title,
                "url": url,
                "description": description,
                "date": file_date,
                "source": "SEC_EDGAR",
            })

        logger.info(f"SEC EDGAR returned {len(results)} results for: {query[:60]}...")
        return results

    except Exception as e:
        logger.warning(f"SEC EDGAR search failed: {e}")
        return []


def sec_search_sources(query: str, max_results: int = 10) -> List[Source]:
    """Search SEC EDGAR and return Source objects."""
    raw_results = _sec_edgar_search_raw(query, max_results)

    sources = []
    for result in raw_results:
        url = result.get("url", "")
        title = result.get("title", "No title")
        source_id = Source.generate_id(url) if url else Source.generate_id(title)

        description = result.get("description", "")
        if description.startswith("[SEC_EDGAR] "):
            description = description[len("[SEC_EDGAR] "):]

        source = Source(
            source_id=source_id,
            url=url,
            title=title,
            source_type="sec_filing",
            content_snippet=description,
            publication_date=result.get("date", ""),
        )
        sources.append(source)

    return sources
