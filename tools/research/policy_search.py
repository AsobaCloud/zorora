"""Policy search — Congress.gov, GovTrack, and Federal Register APIs."""

import logging
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import config
from engine.models import Source
from tools.research.academic_search import _sanitize_provider_query

logger = logging.getLogger(__name__)


def _congress_gov_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search Congress.gov bill API."""
    cg_config = getattr(config, 'CONGRESS_GOV', {})
    if not cg_config.get("enabled", True):
        return []

    api_key = cg_config.get("api_key", "")
    if not api_key:
        logger.warning("Congress.gov API key not configured, skipping")
        return []

    endpoint = cg_config.get("endpoint", "https://api.congress.gov/v3/bill")
    timeout = cg_config.get("timeout", 15)

    provider_query = _sanitize_provider_query(query, "policy")
    if not provider_query:
        return []

    params = {
        "api_key": api_key,
        "format": "json",
        "limit": min(max_results, 20),
        "query": provider_query,
    }

    try:
        response = requests.get(endpoint, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        results = []
        for bill in data.get("bills", []):
            title = bill.get("title", "No title")
            bill_type = bill.get("type", "")
            number = bill.get("number", "")
            url = bill.get("url", "")

            latest_action = bill.get("latestAction", {})
            action_text = latest_action.get("text", "")
            action_date = latest_action.get("actionDate", "")

            desc_parts = [f"[Congress.gov] {bill_type} {number}"]
            if action_text:
                desc_parts.append(f"Action: {action_text}")
            description = " | ".join(desc_parts)

            results.append({
                "title": title,
                "url": url,
                "description": description,
                "date": action_date,
                "source": "Congress.gov",
            })

        logger.info(f"Congress.gov returned {len(results)} results")
        return results

    except Exception as e:
        logger.warning(f"Congress.gov search failed: {e}")
        return []


def _govtrack_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search GovTrack bill API."""
    gt_config = getattr(config, 'GOVTRACK', {})
    if not gt_config.get("enabled", True):
        return []

    endpoint = gt_config.get("endpoint", "https://www.govtrack.us/api/v2/bill")
    timeout = gt_config.get("timeout", 15)

    provider_query = _sanitize_provider_query(query, "policy")
    if not provider_query:
        return []

    params = {
        "q": provider_query,
        "limit": min(max_results, 20),
        "format": "json",
    }

    try:
        response = requests.get(endpoint, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        results = []
        for bill in data.get("objects", []):
            title = bill.get("title", "No title")
            url = bill.get("link", "")
            bill_type = bill.get("bill_type", "")
            status = bill.get("current_status", "")
            date = bill.get("introduced_date", "")

            desc_parts = [f"[GovTrack] {bill_type}"]
            if status:
                desc_parts.append(f"Status: {status}")
            description = " | ".join(desc_parts)

            results.append({
                "title": title,
                "url": url,
                "description": description,
                "date": date,
                "source": "GovTrack",
            })

        logger.info(f"GovTrack returned {len(results)} results")
        return results

    except Exception as e:
        logger.warning(f"GovTrack search failed: {e}")
        return []


def _federal_register_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search Federal Register documents API."""
    fr_config = getattr(config, 'FEDERAL_REGISTER', {})
    if not fr_config.get("enabled", True):
        return []

    endpoint = fr_config.get("endpoint", "https://www.federalregister.gov/api/v1/documents.json")
    timeout = fr_config.get("timeout", 15)

    provider_query = _sanitize_provider_query(query, "policy")
    if not provider_query:
        return []

    params = {
        "conditions[term]": provider_query,
        "per_page": min(max_results, 20),
        "order": "relevance",
    }

    try:
        response = requests.get(endpoint, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        results = []
        for doc in data.get("results", []):
            title = doc.get("title", "No title")
            url = doc.get("html_url", "")
            abstract = doc.get("abstract", "") or ""
            date = doc.get("publication_date", "")
            doc_type = doc.get("type", "")
            agencies = doc.get("agencies", [])
            agency_names = ", ".join(a.get("name", "") for a in agencies if a.get("name"))

            desc_parts = [f"[FederalRegister] {doc_type}"]
            if agency_names:
                desc_parts.append(f"Agency: {agency_names}")
            description = " | ".join(desc_parts)
            if abstract:
                description += f" - {abstract[:200]}"

            results.append({
                "title": title,
                "url": url,
                "description": description,
                "date": date,
                "source": "FederalRegister",
            })

        logger.info(f"Federal Register returned {len(results)} results")
        return results

    except Exception as e:
        logger.warning(f"Federal Register search failed: {e}")
        return []


def policy_search_sources(query: str, max_results: int = 10) -> List[Source]:
    """Search all policy sources in parallel and return Source objects."""
    all_results = []
    per_source = max(max_results // 3, 3)

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(_congress_gov_search_raw, query, per_source): "Congress.gov",
            executor.submit(_govtrack_search_raw, query, per_source): "GovTrack",
            executor.submit(_federal_register_search_raw, query, per_source): "FederalRegister",
        }

        for future in as_completed(futures):
            source_name = futures[future]
            try:
                results = future.result()
                if results:
                    all_results.extend(results)
                    logger.info(f"Policy: {source_name} returned {len(results)} results")
            except Exception as e:
                logger.warning(f"Policy: {source_name} failed: {e}")

    # Convert to Source objects
    sources = []
    tag_pattern_prefixes = ["[Congress.gov] ", "[GovTrack] ", "[FederalRegister] "]

    for result in all_results[:max_results]:
        url = result.get("url", "")
        title = result.get("title", "No title")
        source_id = Source.generate_id(url) if url else Source.generate_id(title)

        description = result.get("description", "")
        for prefix in tag_pattern_prefixes:
            if description.startswith(prefix):
                description = description[len(prefix):]
                break

        source = Source(
            source_id=source_id,
            url=url,
            title=title,
            source_type="policy",
            content_snippet=description,
            publication_date=result.get("date", ""),
        )
        sources.append(source)

    return sources
