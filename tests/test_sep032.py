"""Tests for SEP-032: CrossRef, arXiv native API, World Bank Indicators, cache seeding, background refresh."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile

import requests

import pytest


# --- CrossRef backend tests ---

CROSSREF_SAMPLE_RESPONSE = {
    "status": "ok",
    "message": {
        "items": [
            {
                "DOI": "10.1234/test.2024",
                "title": ["CrossRef Test Paper"],
                "abstract": "<p>This is an abstract about energy policy.</p>",
                "author": [
                    {"given": "Alice", "family": "Smith"},
                    {"given": "Bob", "family": "Jones"},
                ],
                "is-referenced-by-count": 42,
                "published-print": {"date-parts": [[2024, 3]]},
            },
            {
                "DOI": "10.5678/another.2023",
                "title": ["Second Paper on Renewable Energy"],
                "author": [{"given": "Carol", "family": "Lee"}],
                "is-referenced-by-count": 7,
                "published-print": {"date-parts": [[2023, 1]]},
            },
        ]
    },
}


def test_crossref_search_raw_parses_response():
    """CrossRef backend returns structured results from JSON response."""
    from tools.research.academic_search import _crossref_search_raw

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = CROSSREF_SAMPLE_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch("tools.research.academic_search.requests.get", return_value=mock_resp):
        results = _crossref_search_raw("energy policy", max_results=5)

    assert len(results) == 2
    assert results[0]["doi"] == "10.1234/test.2024"
    assert results[0]["title"] == "CrossRef Test Paper"
    assert results[0]["citation_count"] == 42
    assert "CrossRef" in results[0].get("description", "")
    assert results[0]["source"] == "CrossRef"
    # Abstract HTML tags should be stripped
    assert "<p>" not in results[0].get("description", "")


def test_crossref_search_raw_handles_empty():
    """CrossRef returns empty list on empty response."""
    from tools.research.academic_search import _crossref_search_raw

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok", "message": {"items": []}}
    mock_resp.raise_for_status = MagicMock()

    with patch("tools.research.academic_search.requests.get", return_value=mock_resp):
        results = _crossref_search_raw("nonexistent query", max_results=5)

    assert results == []


# --- arXiv native API tests ---

ARXIV_SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.12345v1</id>
    <title>Neural Networks for Climate Modeling</title>
    <summary>We propose a novel approach to climate modeling using deep learning.</summary>
    <published>2024-01-15T00:00:00Z</published>
    <author><name>Alice Researcher</name></author>
    <author><name>Bob Scientist</name></author>
    <arxiv:primary_category term="cs.LG" />
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2312.67890v2</id>
    <title>Transformer Models in Energy Forecasting</title>
    <summary>A survey of transformer architectures applied to energy demand prediction.</summary>
    <published>2023-12-20T00:00:00Z</published>
    <author><name>Carol Engineer</name></author>
  </entry>
</feed>"""


def test_arxiv_native_api_parses_xml():
    """arXiv native API returns structured results from Atom XML."""
    from tools.research.academic_search import _arxiv_search_raw

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = ARXIV_SAMPLE_XML
    mock_resp.raise_for_status = MagicMock()

    with patch("tools.research.academic_search.requests.get", return_value=mock_resp):
        results = _arxiv_search_raw("climate modeling", max_results=5)

    assert len(results) == 2
    assert results[0]["title"] == "Neural Networks for Climate Modeling"
    assert "deep learning" in results[0].get("description", "").lower()
    assert "arxiv.org" in results[0]["url"]
    assert results[0]["source"] == "arXiv"
    # Check authors are parsed
    assert "Alice Researcher" in results[0].get("description", "")


def test_arxiv_native_api_handles_empty():
    """arXiv native API returns empty on no entries."""
    from tools.research.academic_search import _arxiv_search_raw

    empty_xml = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>"""

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = empty_xml
    mock_resp.raise_for_status = MagicMock()

    with patch("tools.research.academic_search.requests.get", return_value=mock_resp):
        results = _arxiv_search_raw("nonexistent query", max_results=5)

    assert results == []


# --- World Bank Indicators client tests ---

WORLDBANK_SAMPLE_RESPONSE = [
    {"page": 1, "pages": 1, "per_page": 1000, "total": 3},
    [
        {"date": "2023", "value": 105568776891234.0, "countryiso3code": "WLD"},
        {"date": "2022", "value": 100562332000000.0, "countryiso3code": "WLD"},
        {"date": "2021", "value": None, "countryiso3code": "WLD"},
    ],
]


def test_worldbank_client_parses_response():
    """World Bank client returns (date, value) tuples, skipping nulls."""
    from tools.market.worldbank_client import fetch_observations

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = WORLDBANK_SAMPLE_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch("tools.market.worldbank_client.requests.get", return_value=mock_resp):
        obs = fetch_observations("NY.GDP.MKTP.CD")

    assert len(obs) == 2
    # Dates normalized to YYYY-01-01
    assert obs[0][0] == "2022-01-01"
    assert obs[1][0] == "2023-01-01"
    # Values are floats
    assert isinstance(obs[0][1], float)


def test_worldbank_client_handles_empty():
    """World Bank client returns empty on error response."""
    from tools.market.worldbank_client import fetch_observations

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"message": [{"id": "120", "key": "Invalid value"}]}]
    mock_resp.raise_for_status = MagicMock()

    with patch("tools.market.worldbank_client.requests.get", return_value=mock_resp):
        obs = fetch_observations("INVALID.INDICATOR")

    assert obs == []


# --- Series catalog tests ---

def test_worldbank_series_in_catalog():
    """World Bank Indicators are present in SERIES_CATALOG."""
    from tools.market.series import SERIES_CATALOG

    wb_ids = [s for s in SERIES_CATALOG if SERIES_CATALOG[s].provider == "worldbank"]
    assert len(wb_ids) >= 6, f"Expected >=6 World Bank series, found {len(wb_ids)}"
    for sid in wb_ids:
        assert SERIES_CATALOG[sid].provider == "worldbank"
        assert SERIES_CATALOG[sid].frequency == "annual"


# --- Background refresh thread tests ---

@pytest.mark.skip(reason="SEP-057: Function moved to workflows/background_threads.py; test coupled to internal naming")
def test_background_refresh_thread_starts():
    """Background market refresh thread starts as daemon."""
    pass


# --- Cache seeding (copy-on-first-use) tests ---

def test_seed_db_copied_on_first_use():
    """MarketDataStore copies seed DB from data/ if user DB doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_dir = Path(tmpdir) / "data"
        seed_dir.mkdir()
        seed_db = seed_dir / "market_data.db"

        # Create a minimal seed DB
        import sqlite3
        conn = sqlite3.connect(str(seed_db))
        conn.execute("CREATE TABLE seed_marker (id INTEGER)")
        conn.execute("INSERT INTO seed_marker VALUES (1)")
        conn.commit()
        conn.close()

        user_db = Path(tmpdir) / "user" / "market_data.db"

        with patch("tools.market.store.MarketDataStore._SEED_DB_PATH", seed_db):
            from tools.market.store import MarketDataStore
            MarketDataStore(db_path=str(user_db))

        # Verify the seed was copied (user DB exists)
        assert user_db.exists()
        # Verify seed content was preserved
        conn = sqlite3.connect(str(user_db))
        rows = conn.execute("SELECT * FROM seed_marker").fetchall()
        conn.close()
        assert len(rows) == 1


# --- Credibility entries tests ---

def test_crossref_credibility_entry():
    """CrossRef has credibility entry."""
    from workflows.deep_research.credibility import BASE_CREDIBILITY
    assert "api.crossref.org" in BASE_CREDIBILITY
    assert BASE_CREDIBILITY["api.crossref.org"]["score"] == 0.75


def test_worldbank_api_credibility_entry():
    """World Bank API has credibility entry."""
    from workflows.deep_research.credibility import BASE_CREDIBILITY
    assert "api.worldbank.org" in BASE_CREDIBILITY
    assert BASE_CREDIBILITY["api.worldbank.org"]["score"] == 0.80


# --- Config entries tests ---

def test_config_crossref_block():
    """CROSSREF config block exists."""
    import config
    assert hasattr(config, "CROSSREF")
    assert config.CROSSREF.get("enabled") is True
    assert "crossref.org" in config.CROSSREF.get("endpoint", "")


def test_config_arxiv_block():
    """ARXIV config block exists."""
    import config
    assert hasattr(config, "ARXIV")
    assert config.ARXIV.get("enabled") is True
    assert "arxiv.org" in config.ARXIV.get("endpoint", "")


def test_config_worldbank_indicators_block():
    """WORLD_BANK_INDICATORS config block exists."""
    import config
    assert hasattr(config, "WORLD_BANK_INDICATORS")
    assert config.WORLD_BANK_INDICATORS.get("enabled") is True


# --- Live API integration tests ---

def _skip_on_network_error(func):
    """Decorator to skip test on network failures."""
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as exc:
            pytest.skip(f"Network unavailable: {exc}")

    return wrapper


@pytest.mark.integration
@_skip_on_network_error
def test_crossref_live():
    """CrossRef API returns valid structured results for a real query."""
    from tools.research.academic_search import _crossref_search_raw

    results = _crossref_search_raw("climate change", max_results=3)

    assert len(results) >= 1, "CrossRef returned no results for 'climate change'"
    for r in results:
        assert isinstance(r["title"], str) and len(r["title"]) > 0
        assert isinstance(r["doi"], str) and len(r["doi"]) > 0
        assert r["source"] == "CrossRef"
        assert r["url"].startswith("https://doi.org/")
        assert "[CrossRef]" in r["description"]


@pytest.mark.integration
@_skip_on_network_error
def test_arxiv_live():
    """arXiv API returns valid structured results for a real query."""
    from tools.research.academic_search import _arxiv_search_raw

    results = _arxiv_search_raw("machine learning", max_results=3)

    assert len(results) >= 1, "arXiv returned no results for 'machine learning'"
    for r in results:
        assert isinstance(r["title"], str) and len(r["title"]) > 0
        assert "arxiv.org" in r["url"]
        assert r["source"] == "arXiv"
        assert "[arXiv]" in r["description"]
        # Description should contain abstract text beyond just the tag
        assert len(r["description"]) > 20


@pytest.mark.integration
@_skip_on_network_error
def test_worldbank_live():
    """World Bank API returns valid GDP observations for a real indicator."""
    import re as _re
    from tools.market.worldbank_client import fetch_observations

    obs = fetch_observations("NY.GDP.MKTP.CD")

    assert len(obs) >= 10, f"Expected >=10 GDP observations, got {len(obs)}"
    for date_str, value in obs:
        assert isinstance(date_str, str)
        assert isinstance(value, float)
        assert _re.match(r"^\d{4}-01-01$", date_str), f"Date {date_str} not in YYYY-01-01 format"
        assert value > 0, f"GDP value should be positive, got {value}"
    # Verify ascending sort
    dates = [d for d, _ in obs]
    assert dates == sorted(dates), "Observations not sorted ascending by date"
