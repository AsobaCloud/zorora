"""Tests for SEP-058: Cache market/latest endpoint response."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import time

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent

WEB_APP_IMPORT_ERROR = None
web_app = None
try:
    _APP_PATH = PROJECT_ROOT / "ui" / "web" / "app.py"
    _SPEC = importlib.util.spec_from_file_location("web_app_sep058", _APP_PATH)
    web_app = importlib.util.module_from_spec(_SPEC)
    sys.modules["web_app_sep058"] = web_app
    _SPEC.loader.exec_module(web_app)
except ModuleNotFoundError as exc:
    WEB_APP_IMPORT_ERROR = exc


def _skip_if_no_app():
    if WEB_APP_IMPORT_ERROR is not None:
        pytest.skip(f"web app unavailable: {WEB_APP_IMPORT_ERROR}")


class TestMarketLatestCache:
    """The /api/market/latest endpoint must cache responses."""

    def setup_method(self):
        _skip_if_no_app()
        # Clear cache before each test
        web_app._market_latest_cache = None

    def test_cache_variable_exists(self):
        """Module must have a _market_latest_cache variable."""
        assert hasattr(web_app, "_market_latest_cache")

    def test_cache_ttl_exists(self):
        """Module must have a _MARKET_CACHE_TTL constant."""
        assert hasattr(web_app, "_MARKET_CACHE_TTL")
        assert web_app._MARKET_CACHE_TTL >= 30

    def test_second_call_faster_than_first(self):
        """Second call to market/latest should be significantly faster (cache hit)."""
        client = web_app.app.test_client()

        start1 = time.monotonic()
        resp1 = client.get("/api/market/latest")
        time1 = time.monotonic() - start1

        start2 = time.monotonic()
        resp2 = client.get("/api/market/latest")
        time2 = time.monotonic() - start2

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        # Cache hit should be at least 2x faster
        if time1 > 0.1:  # Only assert if first call was slow enough to measure
            assert time2 < time1 * 0.5, (
                f"Second call ({time2:.3f}s) should be much faster than first ({time1:.3f}s)")

    def test_cached_response_matches_fresh(self):
        """Cached response must return the same data as fresh computation."""
        client = web_app.app.test_client()
        resp1 = client.get("/api/market/latest")
        resp2 = client.get("/api/market/latest")
        assert resp1.get_json() == resp2.get_json()
