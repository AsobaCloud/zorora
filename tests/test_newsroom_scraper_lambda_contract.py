from __future__ import annotations

import builtins
import importlib.util
import pathlib
import sys
import types

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
LAMBDA_PATH = PROJECT_ROOT / "infra" / "lambda" / "newsroom_scraper" / "lambda_news_scraper.py"



def _load_lambda_module():
    assert LAMBDA_PATH.exists(), f"expected lambda entrypoint at {LAMBDA_PATH}"

    spec = importlib.util.spec_from_file_location("newsroom_lambda_under_test", LAMBDA_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["newsroom_lambda_under_test"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module



def test_lambda_handler_file_exists_at_expected_path():
    assert LAMBDA_PATH.exists(), (
        "repo-local newsroom Lambda entrypoint must exist at "
        "infra/lambda/newsroom_scraper/lambda_news_scraper.py"
    )



def test_lambda_handler_invokes_news_scraper_main_only(monkeypatch):
    module = _load_lambda_module()
    calls = []

    fake_news_scraper = types.ModuleType("news_scraper")

    def _main():
        calls.append("news")

    fake_news_scraper.main = _main
    monkeypatch.setitem(sys.modules, "news_scraper", fake_news_scraper)

    forbidden = {
        "legislation_scraper",
        "polymarket_scraper",
        "economy_politics_scraper",
        "lambda_wrapper",
    }
    real_import = builtins.__import__

    def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        root = name.split(".", 1)[0]
        if root in forbidden:
            raise AssertionError(f"forbidden import attempted: {name}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _guarded_import)

    result = module.lambda_handler({}, None)

    assert result["statusCode"] == 200
    assert calls == ["news"]



def test_lambda_handler_returns_500_when_news_scraper_fails(monkeypatch):
    module = _load_lambda_module()

    fake_news_scraper = types.ModuleType("news_scraper")

    def _main():
        raise RuntimeError("boom")

    fake_news_scraper.main = _main
    monkeypatch.setitem(sys.modules, "news_scraper", fake_news_scraper)

    result = module.lambda_handler({}, None)

    assert result["statusCode"] == 500
    assert "boom" in result["body"]
