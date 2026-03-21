"""Tests for SEP-056: Paginate news-intel articles endpoint.

Verifies that the articles endpoint supports pagination (offset + limit)
and returns total_count, and that the frontend does not request 10000 articles.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from unittest.mock import patch

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent

WEB_APP_IMPORT_ERROR = None
web_app = None
try:
    _APP_PATH = PROJECT_ROOT / "ui" / "web" / "app.py"
    _SPEC = importlib.util.spec_from_file_location("web_app_sep056", _APP_PATH)
    web_app = importlib.util.module_from_spec(_SPEC)
    sys.modules["web_app_sep056"] = web_app
    _SPEC.loader.exec_module(web_app)
except ModuleNotFoundError as exc:
    WEB_APP_IMPORT_ERROR = exc


MOCK_ARTICLES = [
    {"headline": f"Article {i}", "date": "2026-03-21", "source": "Test",
     "url": f"http://test/{i}", "topic_tags": ["Energy"],
     "geography_tags": [], "country_tags": []}
    for i in range(500)
]


def _skip_if_no_app():
    if WEB_APP_IMPORT_ERROR is not None:
        pytest.skip(f"web app unavailable: {WEB_APP_IMPORT_ERROR}")


class TestArticlesPagination:
    """The /api/news-intel/articles endpoint must support offset-based pagination."""

    def setup_method(self):
        _skip_if_no_app()

    def _post(self, data=None):
        client = web_app.app.test_client()
        return client.post("/api/news-intel/articles", json=data or {},
                           content_type="application/json")

    @patch("ui.web.app.fetch_newsroom_api", return_value=MOCK_ARTICLES)
    def test_response_includes_total_count(self, _mock):
        data = self._post({"limit": 50}).get_json()
        assert "total_count" in data, (
            f"Response must include total_count. Got keys: {list(data.keys())}")

    @patch("ui.web.app.fetch_newsroom_api", return_value=MOCK_ARTICLES)
    def test_total_count_gte_page_count(self, _mock):
        data = self._post({"limit": 50}).get_json()
        assert data.get("total_count", 0) >= data.get("count", 0)

    @patch("ui.web.app.fetch_newsroom_api", return_value=MOCK_ARTICLES)
    def test_offset_accepted(self, _mock):
        resp = self._post({"limit": 50, "offset": 100})
        assert resp.status_code == 200

    @patch("ui.web.app.fetch_newsroom_api", return_value=MOCK_ARTICLES)
    def test_offset_returns_different_page(self, _mock):
        d1 = self._post({"limit": 50, "offset": 0}).get_json()
        d2 = self._post({"limit": 50, "offset": 50}).get_json()
        a1 = [a["headline"] for a in d1.get("articles", [])]
        a2 = [a["headline"] for a in d2.get("articles", [])]
        if a1 and a2:
            assert a1[0] != a2[0], "offset not applied — same first article"

    @patch("ui.web.app.fetch_newsroom_api", return_value=MOCK_ARTICLES)
    def test_default_limit_200_or_less(self, _mock):
        data = self._post({}).get_json()
        assert len(data.get("articles", [])) <= 200, (
            f"Default returned {len(data.get('articles', []))} articles, want <= 200")

    @patch("ui.web.app.fetch_newsroom_api", return_value=MOCK_ARTICLES)
    def test_response_includes_offset_field(self, _mock):
        data = self._post({"offset": 25}).get_json()
        assert "offset" in data, (
            f"Response must include offset. Got keys: {list(data.keys())}")


class TestFrontendLimit:
    """Frontend must not request limit: 10000."""

    def test_no_limit_10000_in_frontend(self):
        html = (PROJECT_ROOT / "ui" / "web" / "templates" / "index.html").read_text()
        assert "limit: 10000" not in html, (
            "Frontend still requests limit: 10000 — sends 1.1MB on every tab load")
