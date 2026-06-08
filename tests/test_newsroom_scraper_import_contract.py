from __future__ import annotations

import importlib.util
import io
import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRAPER_PATH = PROJECT_ROOT / "infra" / "lambda" / "newsroom_scraper" / "news_scraper.py"


class _FakePaginator:
    def paginate(self, **kwargs):
        return []


class _FakeS3Client:
    class exceptions:
        class NoSuchKey(Exception):
            pass

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        return _FakePaginator()

    def get_object(self, **kwargs):
        return {"Body": io.BytesIO(b"{}")}



def _load_scraper_module(monkeypatch):
    assert SCRAPER_PATH.exists(), f"expected imported scraper at {SCRAPER_PATH}"

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "unit-test-lambda")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")

    import boto3

    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: _FakeS3Client())

    spec = importlib.util.spec_from_file_location("newsroom_scraper_under_test", SCRAPER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["newsroom_scraper_under_test"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module



def test_imported_scraper_file_exists_at_expected_path():
    assert SCRAPER_PATH.exists(), (
        "authoritative newsroom scraper must be imported into "
        "infra/lambda/newsroom_scraper/news_scraper.py"
    )



def test_imported_scraper_reuses_repo_article_tagger(monkeypatch):
    module = _load_scraper_module(monkeypatch)

    from tools.research.article_tagger import tag_article

    assert module.tag_article is tag_article



def test_imported_scraper_exposes_expected_entrypoints(monkeypatch):
    module = _load_scraper_module(monkeypatch)

    assert callable(module.process_single_rss_feed)
    assert callable(module.scrape_website_articles)
    assert callable(module.main)
