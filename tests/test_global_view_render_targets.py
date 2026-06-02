from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = PROJECT_ROOT / "ui" / "web" / "templates" / "index.html"


def _html() -> str:
    return TEMPLATE_PATH.read_text()


def test_global_view_loading_state_preserves_dataset_render_target():
    html = _html()

    assert "datasetsTab.innerHTML = '<div class=\"gv-loading-state\"" not in html
    assert "const datasetGrid = document.getElementById('datasetCardsGrid');" in html
    assert "datasetGrid.innerHTML = '<div class=\"gv-loading-state\"" in html


def test_global_view_loading_state_preserves_article_render_targets():
    html = _html()

    assert "articlesTab.innerHTML = '<div class=\"gv-loading-state\"" not in html
    assert "const articlesBody = document.getElementById('gvArticlesBody');" in html
    assert "const articlesPagination = document.getElementById('gvPagination');" in html
    assert "articlesBody.innerHTML = '<tr><td colspan=\"6\"" in html


def test_global_view_error_state_does_not_replace_parent_tabs():
    html = _html()

    assert "articlesTab.innerHTML = '<div class=\"gv-error-state\"" not in html
    assert "datasetsTab.innerHTML = '<div class=\"gv-error-state\"" not in html
    assert "datasetGrid.innerHTML = '<div class=\"gv-error-state\"" in html
    assert "articlesBody.innerHTML = '<tr><td colspan=\"6\"" in html
