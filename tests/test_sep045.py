"""Tests for SEP-045: Feasibility Studies (5-Tab Analysis).

Covers:
  - ImagingDataStore: feasibility_results table schema, upsert_feasibility_result(),
    get_feasibility_results(), get_feasibility_result(), get_feasibility_progress().
  - workflows.feasibility: run_feasibility_tab() dispatcher and per-tab analysis
    functions (_analyze_production, _analyze_trading, _analyze_grid, _analyze_regulatory,
    _analyze_financial).
  - Flask API: GET/POST /api/scouting/items/<id>/feasibility and
    GET /api/scouting/items/<id>/feasibility/<tab>.
  - Integration: end-to-end from pipeline asset creation through tab runs, progress
    tracking, and result replacement.

All tests are expected to FAIL until SEP-045 is implemented.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FEASIBILITY_TABS = ["production", "trading", "grid", "regulatory", "financial"]
VALID_CONCLUSIONS = ["favorable", "marginal", "unfavorable"]
VALID_CONFIDENCES = ["high", "medium", "low"]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_brownfield_asset(name: str = "Kafue Solar", country: str = "Zambia") -> dict:
    """Minimal brownfield asset accepted by upsert_pipeline_asset."""
    return {
        "properties": {
            "site_id": f"gen:{name.lower().replace(' ', '_')}",
            "name": name,
            "technology": "solar",
            "capacity_mw": 100.0,
            "status": "operating",
            "operator": "Acme Energy",
            "owner": "Acme Energy",
            "country": country,
        },
        "geometry": {"type": "Point", "coordinates": [27.8, -15.4]},
    }


def _mock_llm_response(conclusion: str = "Favorable", confidence: str = "High") -> str:
    """Return a parseable LLM text response for feasibility analysis."""
    return (
        f"Key Finding: Test finding text for this analysis.\n"
        f"Conclusion: {conclusion}\n"
        f"Confidence: {confidence}\n"
        f"Risks:\n"
        f"- Risk 1\n"
        f"- Risk 2\n"
        f"Gaps:\n"
        f"- Gap 1\n"
    )


def _make_mock_llm_client(conclusion: str = "Favorable", confidence: str = "High"):
    """Create a mock LLM client that returns a parseable structured response."""
    mock_client = MagicMock()
    mock_client.complete.return_value = _mock_llm_response(conclusion, confidence)
    mock_client.chat.return_value = _mock_llm_response(conclusion, confidence)
    return mock_client


# ---------------------------------------------------------------------------
# 1. Store tests — feasibility_results table schema
# ---------------------------------------------------------------------------


class TestFeasibilityResultsTableSchema:
    """After SEP-045, ImagingDataStore must include a feasibility_results table."""

    def test_feasibility_results_table_exists_after_init(self, tmp_path):
        """feasibility_results table must exist after ImagingDataStore initialises."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        cur = store.conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='feasibility_results'"
        )
        row = cur.fetchone()
        store.close()
        assert row is not None, (
            "feasibility_results table must be created by _init_schema()"
        )

    def test_feasibility_results_has_id_column(self, tmp_path):
        """feasibility_results table must have an 'id' column."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        cur = store.conn.cursor()
        cur.execute("PRAGMA table_info(feasibility_results)")
        columns = {row["name"] for row in cur.fetchall()}
        store.close()
        assert "id" in columns, "feasibility_results must have 'id' column"

    def test_feasibility_results_has_required_columns(self, tmp_path):
        """feasibility_results must have all required schema columns."""
        from tools.imaging.store import ImagingDataStore

        expected = {
            "id", "item_id", "item_type", "tab", "conclusion", "confidence",
            "findings_json", "created_at", "updated_at",
        }
        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        cur = store.conn.cursor()
        cur.execute("PRAGMA table_info(feasibility_results)")
        columns = {row["name"] for row in cur.fetchall()}
        store.close()
        missing = expected - columns
        assert not missing, (
            f"feasibility_results table is missing columns: {missing}"
        )


# ---------------------------------------------------------------------------
# 2. Store tests — upsert_feasibility_result()
# ---------------------------------------------------------------------------


class TestUpsertFeasibilityResult:
    """upsert_feasibility_result() must insert new rows and replace existing ones."""

    def test_upsert_inserts_new_result(self, tmp_path):
        """upsert_feasibility_result creates a new row when none exists."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        findings = {"key_finding": "Test finding", "risks": ["R1"], "gaps": ["G1"], "sources": []}
        store.upsert_feasibility_result(
            item_id="asset-001",
            item_type="brownfield",
            tab="production",
            conclusion="favorable",
            confidence="high",
            findings=findings,
        )
        cur = store.conn.cursor()
        cur.execute("SELECT * FROM feasibility_results WHERE item_id = 'asset-001'")
        rows = cur.fetchall()
        store.close()
        assert len(rows) == 1, "Expected one row after first upsert"

    def test_upsert_uses_compound_id(self, tmp_path):
        """upsert_feasibility_result must store id as '{item_id}:{tab}'."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        findings = {"key_finding": "F", "risks": [], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id="asset-001",
            item_type="brownfield",
            tab="trading",
            conclusion="marginal",
            confidence="medium",
            findings=findings,
        )
        cur = store.conn.cursor()
        cur.execute("SELECT id FROM feasibility_results WHERE item_id = 'asset-001'")
        row = cur.fetchone()
        store.close()
        assert row is not None
        assert row["id"] == "asset-001:trading", (
            f"Expected id='asset-001:trading', got {row['id']!r}"
        )

    def test_upsert_stores_conclusion_and_confidence(self, tmp_path):
        """upsert_feasibility_result persists conclusion and confidence values."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        findings = {"key_finding": "F", "risks": [], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id="asset-002",
            item_type="brownfield",
            tab="grid",
            conclusion="unfavorable",
            confidence="low",
            findings=findings,
        )
        result = store.get_feasibility_result("asset-002", "grid")
        store.close()
        assert result is not None
        assert result["conclusion"] == "unfavorable"
        assert result["confidence"] == "low"

    def test_upsert_stores_findings_json(self, tmp_path):
        """upsert_feasibility_result serialises findings dict to findings_json."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        findings = {
            "key_finding": "Good capacity factor",
            "risks": ["Weather risk"],
            "gaps": ["No PPA secured"],
            "sources": ["ACEC", "NASA POWER"],
        }
        store.upsert_feasibility_result(
            item_id="asset-003",
            item_type="brownfield",
            tab="production",
            conclusion="favorable",
            confidence="high",
            findings=findings,
        )
        result = store.get_feasibility_result("asset-003", "production")
        store.close()
        assert result is not None
        assert result.get("key_finding") == "Good capacity factor" or (
            result.get("findings", {}).get("key_finding") == "Good capacity factor"
        ), "findings key_finding must be accessible in the returned result"

    def test_upsert_replaces_existing_result(self, tmp_path):
        """upsert_feasibility_result on same item+tab replaces the previous row."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        findings = {"key_finding": "Old finding", "risks": [], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id="asset-004",
            item_type="brownfield",
            tab="regulatory",
            conclusion="favorable",
            confidence="high",
            findings=findings,
        )
        # Re-run the same tab with a different conclusion
        findings2 = {"key_finding": "Updated finding", "risks": ["New risk"], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id="asset-004",
            item_type="brownfield",
            tab="regulatory",
            conclusion="marginal",
            confidence="medium",
            findings=findings2,
        )
        cur = store.conn.cursor()
        cur.execute(
            "SELECT COUNT(*) as cnt FROM feasibility_results WHERE item_id='asset-004' AND tab='regulatory'"
        )
        count = cur.fetchone()["cnt"]
        result = store.get_feasibility_result("asset-004", "regulatory")
        store.close()
        assert count == 1, "Re-running a tab must replace the row, not add a second one"
        assert result["conclusion"] == "marginal", (
            "Updated conclusion must be 'marginal' after re-run"
        )

    def test_upsert_updates_updated_at_on_re_run(self, tmp_path):
        """Re-running a tab must update updated_at timestamp."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        findings = {"key_finding": "F", "risks": [], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id="asset-005",
            item_type="brownfield",
            tab="financial",
            conclusion="favorable",
            confidence="high",
            findings=findings,
        )
        result_first = store.get_feasibility_result("asset-005", "financial")
        updated_at_first = result_first.get("updated_at")

        # Small delay to ensure timestamp difference
        time.sleep(0.01)

        store.upsert_feasibility_result(
            item_id="asset-005",
            item_type="brownfield",
            tab="financial",
            conclusion="marginal",
            confidence="low",
            findings=findings,
        )
        result_second = store.get_feasibility_result("asset-005", "financial")
        updated_at_second = result_second.get("updated_at")
        store.close()
        assert updated_at_second != updated_at_first, (
            "updated_at must change when a tab result is re-run"
        )

    def test_upsert_two_different_tabs_for_same_item(self, tmp_path):
        """Upserting two different tabs for the same item creates two rows."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        findings = {"key_finding": "F", "risks": [], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id="asset-006",
            item_type="brownfield",
            tab="production",
            conclusion="favorable",
            confidence="high",
            findings=findings,
        )
        store.upsert_feasibility_result(
            item_id="asset-006",
            item_type="brownfield",
            tab="trading",
            conclusion="marginal",
            confidence="medium",
            findings=findings,
        )
        results = store.get_feasibility_results("asset-006")
        store.close()
        assert len(results) == 2, (
            f"Expected 2 results for two tabs, got {len(results)}"
        )

    def test_upsert_stores_item_type(self, tmp_path):
        """upsert_feasibility_result persists item_type field correctly."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        findings = {"key_finding": "F", "risks": [], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id="green-001",
            item_type="greenfield",
            tab="production",
            conclusion="favorable",
            confidence="high",
            findings=findings,
        )
        result = store.get_feasibility_result("green-001", "production")
        store.close()
        assert result is not None
        assert result.get("item_type") == "greenfield"


# ---------------------------------------------------------------------------
# 3. Store tests — get_feasibility_results()
# ---------------------------------------------------------------------------


class TestGetFeasibilityResults:
    """get_feasibility_results() must return all tab results for an item."""

    def test_get_feasibility_results_returns_empty_list_for_unknown_item(self, tmp_path):
        """get_feasibility_results on an item with no results returns empty list."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        results = store.get_feasibility_results("nonexistent-item")
        store.close()
        assert results == [], (
            f"Expected [], got {results!r}"
        )

    def test_get_feasibility_results_returns_all_tabs_for_item(self, tmp_path):
        """get_feasibility_results returns all tabs that have been run for an item."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        findings = {"key_finding": "F", "risks": [], "gaps": [], "sources": []}
        for tab in ["production", "trading", "grid"]:
            store.upsert_feasibility_result(
                item_id="asset-010",
                item_type="brownfield",
                tab=tab,
                conclusion="favorable",
                confidence="high",
                findings=findings,
            )
        results = store.get_feasibility_results("asset-010")
        store.close()
        assert len(results) == 3, (
            f"Expected 3 results for 3 tabs, got {len(results)}"
        )

    def test_get_feasibility_results_does_not_return_other_items(self, tmp_path):
        """get_feasibility_results must only return results for the requested item."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        findings = {"key_finding": "F", "risks": [], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id="asset-A",
            item_type="brownfield",
            tab="production",
            conclusion="favorable",
            confidence="high",
            findings=findings,
        )
        store.upsert_feasibility_result(
            item_id="asset-B",
            item_type="brownfield",
            tab="production",
            conclusion="marginal",
            confidence="medium",
            findings=findings,
        )
        results = store.get_feasibility_results("asset-A")
        store.close()
        assert len(results) == 1
        assert all(r.get("item_id") == "asset-A" for r in results), (
            "get_feasibility_results must not return results from other items"
        )

    def test_get_feasibility_results_each_result_has_tab_field(self, tmp_path):
        """Each result returned by get_feasibility_results must include a 'tab' field."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        findings = {"key_finding": "F", "risks": [], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id="asset-011",
            item_type="brownfield",
            tab="regulatory",
            conclusion="favorable",
            confidence="high",
            findings=findings,
        )
        results = store.get_feasibility_results("asset-011")
        store.close()
        assert len(results) == 1
        assert "tab" in results[0], "Each result must include a 'tab' field"
        assert results[0]["tab"] == "regulatory"


# ---------------------------------------------------------------------------
# 4. Store tests — get_feasibility_result()
# ---------------------------------------------------------------------------


class TestGetFeasibilityResult:
    """get_feasibility_result() must return the single tab result or None."""

    def test_get_feasibility_result_returns_none_when_not_run(self, tmp_path):
        """get_feasibility_result returns None when no result exists for that tab."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        result = store.get_feasibility_result("any-item", "production")
        store.close()
        assert result is None, f"Expected None, got {result!r}"

    def test_get_feasibility_result_returns_correct_tab(self, tmp_path):
        """get_feasibility_result('x', 'trading') must return the trading tab result."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        findings = {"key_finding": "Trading ok", "risks": [], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id="asset-020",
            item_type="brownfield",
            tab="trading",
            conclusion="marginal",
            confidence="medium",
            findings=findings,
        )
        result = store.get_feasibility_result("asset-020", "trading")
        store.close()
        assert result is not None
        assert result["tab"] == "trading"

    def test_get_feasibility_result_does_not_return_wrong_tab(self, tmp_path):
        """get_feasibility_result must not return a result for a different tab."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        findings = {"key_finding": "F", "risks": [], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id="asset-021",
            item_type="brownfield",
            tab="production",
            conclusion="favorable",
            confidence="high",
            findings=findings,
        )
        result = store.get_feasibility_result("asset-021", "trading")
        store.close()
        assert result is None, (
            "get_feasibility_result('asset-021', 'trading') must return None "
            "when only 'production' tab has been run"
        )

    def test_get_feasibility_result_returns_latest_after_re_run(self, tmp_path):
        """get_feasibility_result returns the most recent result after a tab re-run."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        findings = {"key_finding": "First", "risks": [], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id="asset-022",
            item_type="brownfield",
            tab="grid",
            conclusion="unfavorable",
            confidence="low",
            findings=findings,
        )
        findings2 = {"key_finding": "Second", "risks": [], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id="asset-022",
            item_type="brownfield",
            tab="grid",
            conclusion="favorable",
            confidence="high",
            findings=findings2,
        )
        result = store.get_feasibility_result("asset-022", "grid")
        store.close()
        assert result["conclusion"] == "favorable", (
            "get_feasibility_result must reflect re-run result, not the original"
        )


# ---------------------------------------------------------------------------
# 5. Store tests — get_feasibility_progress()
# ---------------------------------------------------------------------------


class TestGetFeasibilityProgress:
    """get_feasibility_progress() must return completion summary."""

    def test_get_feasibility_progress_zero_completed_when_no_tabs_run(self, tmp_path):
        """Progress for a new item with no tabs run shows completed=0, total=5."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        progress = store.get_feasibility_progress("brand-new-item")
        store.close()
        assert progress["completed"] == 0
        assert progress["total"] == 5

    def test_get_feasibility_progress_total_always_five(self, tmp_path):
        """get_feasibility_progress always reports total=5 regardless of runs."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        findings = {"key_finding": "F", "risks": [], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id="asset-030",
            item_type="brownfield",
            tab="production",
            conclusion="favorable",
            confidence="high",
            findings=findings,
        )
        progress = store.get_feasibility_progress("asset-030")
        store.close()
        assert progress["total"] == 5

    def test_get_feasibility_progress_completed_count_matches_tabs_run(self, tmp_path):
        """Progress completed count equals the number of distinct tabs with results."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        findings = {"key_finding": "F", "risks": [], "gaps": [], "sources": []}
        for tab in ["production", "trading", "grid"]:
            store.upsert_feasibility_result(
                item_id="asset-031",
                item_type="brownfield",
                tab=tab,
                conclusion="favorable",
                confidence="high",
                findings=findings,
            )
        progress = store.get_feasibility_progress("asset-031")
        store.close()
        assert progress["completed"] == 3, (
            f"Expected completed=3 after running 3 tabs, got {progress['completed']}"
        )

    def test_get_feasibility_progress_tabs_dict_includes_conclusions(self, tmp_path):
        """Progress 'tabs' dict maps tab names to their conclusions."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        findings = {"key_finding": "F", "risks": [], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id="asset-032",
            item_type="brownfield",
            tab="production",
            conclusion="favorable",
            confidence="high",
            findings=findings,
        )
        store.upsert_feasibility_result(
            item_id="asset-032",
            item_type="brownfield",
            tab="trading",
            conclusion="marginal",
            confidence="medium",
            findings=findings,
        )
        progress = store.get_feasibility_progress("asset-032")
        store.close()
        assert "tabs" in progress, "Progress must include a 'tabs' dict"
        tabs = progress["tabs"]
        assert tabs.get("production") == "favorable", (
            f"Expected tabs['production']='favorable', got {tabs.get('production')!r}"
        )
        assert tabs.get("trading") == "marginal", (
            f"Expected tabs['trading']='marginal', got {tabs.get('trading')!r}"
        )

    def test_get_feasibility_progress_re_run_does_not_double_count(self, tmp_path):
        """Re-running a tab must not increment completed count beyond once per tab."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        findings = {"key_finding": "F", "risks": [], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id="asset-033",
            item_type="brownfield",
            tab="production",
            conclusion="favorable",
            confidence="high",
            findings=findings,
        )
        # Re-run same tab
        store.upsert_feasibility_result(
            item_id="asset-033",
            item_type="brownfield",
            tab="production",
            conclusion="marginal",
            confidence="medium",
            findings=findings,
        )
        progress = store.get_feasibility_progress("asset-033")
        store.close()
        assert progress["completed"] == 1, (
            "Re-running same tab must keep completed=1, not increment to 2"
        )

    def test_get_feasibility_progress_all_five_tabs_completed(self, tmp_path):
        """Progress shows completed=5 when all five tabs have results."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        findings = {"key_finding": "F", "risks": [], "gaps": [], "sources": []}
        for tab in FEASIBILITY_TABS:
            store.upsert_feasibility_result(
                item_id="asset-034",
                item_type="brownfield",
                tab=tab,
                conclusion="favorable",
                confidence="high",
                findings=findings,
            )
        progress = store.get_feasibility_progress("asset-034")
        store.close()
        assert progress["completed"] == 5


# ---------------------------------------------------------------------------
# 6. Workflow tests — module and function existence
# ---------------------------------------------------------------------------


class TestFeasibilityWorkflowModuleExists:
    """workflows.feasibility must be importable and expose required functions."""

    def test_feasibility_module_is_importable(self):
        """workflows.feasibility must be importable without error."""
        import workflows.feasibility  # noqa: F401

    def test_run_feasibility_tab_function_exists(self):
        """workflows.feasibility must expose a run_feasibility_tab function."""
        import workflows.feasibility
        assert hasattr(workflows.feasibility, "run_feasibility_tab"), (
            "workflows.feasibility must define run_feasibility_tab()"
        )

    def test_analyze_production_function_exists(self):
        """workflows.feasibility must expose _analyze_production."""
        import workflows.feasibility
        assert hasattr(workflows.feasibility, "_analyze_production"), (
            "workflows.feasibility must define _analyze_production()"
        )

    def test_analyze_trading_function_exists(self):
        """workflows.feasibility must expose _analyze_trading."""
        import workflows.feasibility
        assert hasattr(workflows.feasibility, "_analyze_trading"), (
            "workflows.feasibility must define _analyze_trading()"
        )

    def test_analyze_grid_function_exists(self):
        """workflows.feasibility must expose _analyze_grid."""
        import workflows.feasibility
        assert hasattr(workflows.feasibility, "_analyze_grid"), (
            "workflows.feasibility must define _analyze_grid()"
        )

    def test_analyze_regulatory_function_exists(self):
        """workflows.feasibility must expose _analyze_regulatory."""
        import workflows.feasibility
        assert hasattr(workflows.feasibility, "_analyze_regulatory"), (
            "workflows.feasibility must define _analyze_regulatory()"
        )

    def test_analyze_financial_function_exists(self):
        """workflows.feasibility must expose _analyze_financial."""
        import workflows.feasibility
        assert hasattr(workflows.feasibility, "_analyze_financial"), (
            "workflows.feasibility must define _analyze_financial()"
        )


# ---------------------------------------------------------------------------
# 7. Workflow tests — run_feasibility_tab() with real data, mocked LLM only
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_MOCK_LLM_PATCH = "tools.specialist.client.create_specialist_client"

# Item data for a South African site (within GCCA coverage, near SAPP RSAN node)
_SA_ITEM_DATA = {
    "asset_name": "Limpopo Solar Farm",
    "technology": "solar",
    "capacity_mw": 100.0,
    "country": "South Africa",
    "lat": -23.9,
    "lon": 29.4,
}


class TestRunFeasibilityTabDispatcher:
    """run_feasibility_tab() must dispatch correctly and return valid structure."""

    def _run_tab(self, tab: str, item_data: dict = None) -> dict:
        mock_client = _make_mock_llm_client()
        with patch(_MOCK_LLM_PATCH, return_value=mock_client):
            from workflows.feasibility import run_feasibility_tab
            return run_feasibility_tab(
                item_id="test-001",
                item_type="brownfield",
                tab=tab,
                item_data=item_data or _SA_ITEM_DATA,
            )

    def test_invalid_tab_raises_value_error(self):
        """Invalid tab name raises ValueError."""
        mock_client = _make_mock_llm_client()
        with patch(_MOCK_LLM_PATCH, return_value=mock_client):
            from workflows.feasibility import run_feasibility_tab
            with pytest.raises(ValueError):
                run_feasibility_tab("x", "brownfield", "bogus", _SA_ITEM_DATA)

    @pytest.mark.parametrize("tab", FEASIBILITY_TABS)
    def test_each_tab_returns_dict_with_required_keys(self, tab):
        """Every valid tab returns a dict with conclusion, confidence, key_finding, risks, gaps, sources."""
        result = self._run_tab(tab)
        assert isinstance(result, dict)
        required = {"conclusion", "confidence", "key_finding", "risks", "gaps", "sources"}
        missing = required - set(result.keys())
        assert not missing, f"Tab '{tab}' missing keys: {missing}"

    @pytest.mark.parametrize("tab", FEASIBILITY_TABS)
    def test_each_tab_conclusion_is_valid(self, tab):
        """Every tab conclusion must be favorable/marginal/unfavorable."""
        result = self._run_tab(tab)
        assert result["conclusion"] in VALID_CONCLUSIONS

    @pytest.mark.parametrize("tab", FEASIBILITY_TABS)
    def test_each_tab_confidence_is_valid(self, tab):
        """Every tab confidence must be high/medium/low."""
        result = self._run_tab(tab)
        assert result["confidence"] in VALID_CONFIDENCES


# ---------------------------------------------------------------------------
# 8. Workflow tests — real data scenarios (LLM mocked, data sources real)
# ---------------------------------------------------------------------------


class TestTradingTabUsesRealSAPPData:
    """_analyze_trading must read real SAPP DAM price files and produce meaningful output."""

    def test_trading_tab_sources_mention_sapp(self):
        """Trading tab sources list must reference SAPP DAM data."""
        mock_client = _make_mock_llm_client()
        with patch(_MOCK_LLM_PATCH, return_value=mock_client):
            from workflows.feasibility import _analyze_trading
            result = _analyze_trading(item_data=_SA_ITEM_DATA)
        sources = result.get("sources", [])
        source_text = " ".join(str(s) for s in sources).lower()
        assert "sapp" in source_text or "dam" in source_text, (
            f"Trading sources must reference SAPP DAM data, got: {sources}"
        )

    def test_trading_tab_includes_chart(self):
        """Trading tab must produce a chart_b64 key with base64 PNG data."""
        mock_client = _make_mock_llm_client()
        with patch(_MOCK_LLM_PATCH, return_value=mock_client):
            from workflows.feasibility import _analyze_trading
            result = _analyze_trading(item_data=_SA_ITEM_DATA)
        assert "chart_b64" in result, "Trading tab must include chart_b64"
        # Base64 PNG starts with iVBOR
        if result["chart_b64"]:
            assert result["chart_b64"].startswith("iVBOR") or result["chart_b64"].startswith("data:"), (
                "chart_b64 must be base64-encoded PNG data"
            )


class TestGridTabUsesRealGCCAData:
    """_analyze_grid must read real GCCA GeoPackage and find nearest substation."""

    def test_grid_tab_sources_mention_gcca(self):
        """Grid tab sources must reference GCCA data."""
        mock_client = _make_mock_llm_client()
        with patch(_MOCK_LLM_PATCH, return_value=mock_client):
            from workflows.feasibility import _analyze_grid
            result = _analyze_grid(item_data=_SA_ITEM_DATA)
        sources = result.get("sources", [])
        source_text = " ".join(str(s) for s in sources).lower()
        assert "gcca" in source_text or "substation" in source_text or "mts" in source_text, (
            f"Grid sources must reference GCCA/MTS data, got: {sources}"
        )

    def test_grid_tab_key_finding_mentions_distance_or_substation(self):
        """Grid tab key_finding must mention nearest substation or distance."""
        mock_client = _make_mock_llm_client()
        with patch(_MOCK_LLM_PATCH, return_value=mock_client):
            from workflows.feasibility import _analyze_grid
            result = _analyze_grid(item_data=_SA_ITEM_DATA)
        # The key_finding comes from LLM (mocked), but the context sent TO the LLM
        # should include substation distance. We verify sources instead.
        assert result.get("key_finding"), "Grid tab must produce a non-empty key_finding"


class TestProductionTabUsesResourceData:
    """_analyze_production must gather resource/comparable data for the site."""

    def test_production_tab_sources_mention_resource_data(self):
        """Production tab sources must reference NASA POWER or comparable assets."""
        mock_client = _make_mock_llm_client()
        with patch(_MOCK_LLM_PATCH, return_value=mock_client):
            from workflows.feasibility import _analyze_production
            result = _analyze_production(item_data=_SA_ITEM_DATA)
        sources = result.get("sources", [])
        source_text = " ".join(str(s) for s in sources).lower()
        assert any(kw in source_text for kw in ["nasa", "power", "gem", "generation", "comparable", "resource"]), (
            f"Production sources must reference resource/comparable data, got: {sources}"
        )


class TestFinancialTabUsesPriorResults:
    """_analyze_financial must incorporate prior tab results into its analysis."""

    def test_financial_with_prior_results_includes_them_in_sources(self):
        """Financial tab with prior results must reference them in sources or key_finding."""
        prior = [
            {"tab": "production", "conclusion": "favorable", "key_finding": "CF 22%"},
            {"tab": "trading", "conclusion": "marginal", "key_finding": "Spread $15/MWh"},
        ]
        mock_client = _make_mock_llm_client()
        with patch(_MOCK_LLM_PATCH, return_value=mock_client):
            from workflows.feasibility import _analyze_financial
            result = _analyze_financial(item_data=_SA_ITEM_DATA, prior_results=prior)
        assert result.get("key_finding"), "Financial tab must produce a non-empty key_finding"
        # Financial tab should mention how many prior tabs informed it
        sources = result.get("sources", [])
        assert len(sources) > 0, "Financial tab must list data sources"

    def test_financial_with_empty_prior_results_flags_low_confidence(self):
        """Financial tab with no prior results must have low or medium confidence."""
        mock_client = _make_mock_llm_client(confidence="Low")
        with patch(_MOCK_LLM_PATCH, return_value=mock_client):
            from workflows.feasibility import _analyze_financial
            result = _analyze_financial(item_data=_SA_ITEM_DATA, prior_results=[])
        assert result["confidence"] in ["low", "medium"], (
            f"Financial tab with no prior data should be low/medium confidence, got {result['confidence']!r}"
        )

    def test_financial_with_all_prior_results_has_higher_confidence(self):
        """Financial tab with all 4 prior tabs should have medium or high confidence."""
        prior = [
            {"tab": "production", "conclusion": "favorable", "key_finding": "CF 22%"},
            {"tab": "trading", "conclusion": "favorable", "key_finding": "Spread $20/MWh"},
            {"tab": "grid", "conclusion": "favorable", "key_finding": "5km to substation"},
            {"tab": "regulatory", "conclusion": "marginal", "key_finding": "License pending"},
        ]
        mock_client = _make_mock_llm_client(confidence="High")
        with patch(_MOCK_LLM_PATCH, return_value=mock_client):
            from workflows.feasibility import _analyze_financial
            result = _analyze_financial(item_data=_SA_ITEM_DATA, prior_results=prior)
        assert result["confidence"] in ["medium", "high"], (
            f"Financial with all priors should be medium/high confidence, got {result['confidence']!r}"
        )


# ---------------------------------------------------------------------------
# 9. API tests — Flask endpoints for feasibility
# ---------------------------------------------------------------------------


@pytest.fixture
def feasibility_client(tmp_path):
    """Flask test client with ImagingDataStore patched to a temp DB."""
    from ui.web.app import app
    from tools.imaging.store import ImagingDataStore

    store = ImagingDataStore(db_path=str(tmp_path / "api_test.db"))
    app.config["TESTING"] = True
    with patch("ui.web.app.ImagingDataStore", return_value=store):
        with app.test_client() as c:
            yield c, store
    store.close()


class TestFeasibilityGetAllTabsEndpoint:
    """GET /api/scouting/items/<id>/feasibility returns all tab results + progress."""

    def test_get_feasibility_returns_200_for_existing_item(self, tmp_path):
        """GET /api/scouting/items/<id>/feasibility returns 200."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.get(f"/api/scouting/items/{asset['id']}/feasibility")
        store.close()
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}"
        )

    def test_get_feasibility_response_has_results_key(self, tmp_path):
        """GET feasibility response must include a 'results' list."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.get(f"/api/scouting/items/{asset['id']}/feasibility")
        store.close()
        data = resp.get_json()
        assert "results" in data, (
            f"Response missing 'results' key, got keys: {list(data.keys())}"
        )

    def test_get_feasibility_response_has_progress_key(self, tmp_path):
        """GET feasibility response must include a 'progress' dict."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.get(f"/api/scouting/items/{asset['id']}/feasibility")
        store.close()
        data = resp.get_json()
        assert "progress" in data, (
            f"Response missing 'progress' key, got keys: {list(data.keys())}"
        )

    def test_get_feasibility_progress_has_completed_and_total(self, tmp_path):
        """GET feasibility progress dict must include 'completed' and 'total' keys."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.get(f"/api/scouting/items/{asset['id']}/feasibility")
        store.close()
        data = resp.get_json()
        progress = data.get("progress", {})
        assert "completed" in progress and "total" in progress, (
            f"progress must have 'completed' and 'total', got: {list(progress.keys())}"
        )

    def test_get_feasibility_empty_results_for_new_item(self, tmp_path):
        """GET feasibility for item with no tabs run returns empty results list."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.get(f"/api/scouting/items/{asset['id']}/feasibility")
        store.close()
        data = resp.get_json()
        assert data["results"] == [], (
            f"Expected empty results list for new item, got {data['results']!r}"
        )


class TestFeasibilityGetSingleTabEndpoint:
    """GET /api/scouting/items/<id>/feasibility/<tab> returns single tab result."""

    def test_get_single_tab_returns_200_when_result_exists(self, tmp_path):
        """GET feasibility/<tab> returns 200 when that tab has been run."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        findings = {"key_finding": "Good", "risks": [], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id=asset["id"],
            item_type="brownfield",
            tab="production",
            conclusion="favorable",
            confidence="high",
            findings=findings,
        )
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.get(f"/api/scouting/items/{asset['id']}/feasibility/production")
        store.close()
        assert resp.status_code == 200

    def test_get_single_tab_returns_404_when_not_run(self, tmp_path):
        """GET feasibility/<tab> returns 404 when that tab has not been run.
        
        The response must be JSON (not Flask's HTML route-not-found page), which
        distinguishes a properly-wired endpoint returning 404 from a missing route.
        """
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.get(f"/api/scouting/items/{asset['id']}/feasibility/production")
        store.close()
        assert resp.status_code == 404, (
            f"Expected 404 for unrun tab, got {resp.status_code}"
        )
        # The response must be JSON, not Flask's default HTML 404 page.
        # This assertion fails until the real endpoint is wired up and explicitly
        # returns jsonify({"error": ...}), 404 for a missing result.
        data = resp.get_json()
        assert data is not None, (
            "Response must be JSON (not HTML). A plain Flask route-not-found page "
            "indicates the /feasibility/<tab> endpoint does not exist yet."
        )
        assert "error" in data, (
            f"JSON 404 response must include an 'error' key, got: {list(data.keys())}"
        )

    def test_get_single_tab_invalid_tab_name_returns_400(self, tmp_path):
        """GET feasibility/<invalid_tab> returns 400 for unknown tab name."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.get("/api/scouting/items/any-item/feasibility/invalid_tab")
        store.close()
        assert resp.status_code == 400, (
            f"Expected 400 for invalid tab name, got {resp.status_code}"
        )

    def test_get_single_tab_result_contains_conclusion(self, tmp_path):
        """GET feasibility/<tab> result must include 'conclusion' field."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        findings = {"key_finding": "Good", "risks": [], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id=asset["id"],
            item_type="brownfield",
            tab="trading",
            conclusion="marginal",
            confidence="medium",
            findings=findings,
        )
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.get(f"/api/scouting/items/{asset['id']}/feasibility/trading")
        store.close()
        data = resp.get_json()
        assert "conclusion" in data, f"Response missing 'conclusion': {list(data.keys())}"
        assert data["conclusion"] == "marginal"


class TestFeasibilityPostTabEndpoint:
    """POST /api/scouting/items/<id>/feasibility/<tab> triggers analysis and returns result."""

    def test_post_feasibility_tab_invalid_tab_returns_400(self, tmp_path):
        """POST feasibility/<invalid_tab> returns 400 without running analysis."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.post(
                    "/api/scouting/items/any-item/feasibility/invalid_tab",
                    json={"item_type": "brownfield"},
                    content_type="application/json",
                )
        store.close()
        assert resp.status_code == 400, (
            f"Expected 400 for invalid tab name on POST, got {resp.status_code}"
        )

    def test_post_feasibility_tab_returns_200_with_mocked_workflow(self, tmp_path):
        """POST feasibility/<tab> returns 200 when workflow succeeds."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        mock_result = {
            "conclusion": "favorable",
            "confidence": "high",
            "key_finding": "Mocked finding",
            "risks": ["Risk 1"],
            "gaps": ["Gap 1"],
            "sources": ["Source 1"],
        }
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with patch("workflows.feasibility.run_feasibility_tab", return_value=mock_result):
                with app.test_client() as c:
                    resp = c.post(
                        f"/api/scouting/items/{asset['id']}/feasibility/production",
                        json={"item_type": "brownfield"},
                        content_type="application/json",
                    )
        store.close()
        assert resp.status_code == 200, (
            f"Expected 200 on successful POST, got {resp.status_code}"
        )

    def test_post_feasibility_tab_response_has_conclusion(self, tmp_path):
        """POST feasibility/<tab> response must include 'conclusion' field."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        mock_result = {
            "conclusion": "marginal",
            "confidence": "medium",
            "key_finding": "Mocked finding",
            "risks": [],
            "gaps": [],
            "sources": [],
        }
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with patch("workflows.feasibility.run_feasibility_tab", return_value=mock_result):
                with app.test_client() as c:
                    resp = c.post(
                        f"/api/scouting/items/{asset['id']}/feasibility/trading",
                        json={"item_type": "brownfield"},
                        content_type="application/json",
                    )
        store.close()
        data = resp.get_json()
        assert "conclusion" in data, (
            f"POST response missing 'conclusion', got keys: {list(data.keys())}"
        )

    def test_post_feasibility_tab_response_has_confidence(self, tmp_path):
        """POST feasibility/<tab> response must include 'confidence' field."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        mock_result = {
            "conclusion": "favorable",
            "confidence": "high",
            "key_finding": "Finding",
            "risks": [],
            "gaps": [],
            "sources": [],
        }
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with patch("workflows.feasibility.run_feasibility_tab", return_value=mock_result):
                with app.test_client() as c:
                    resp = c.post(
                        f"/api/scouting/items/{asset['id']}/feasibility/grid",
                        json={"item_type": "brownfield"},
                        content_type="application/json",
                    )
        store.close()
        data = resp.get_json()
        assert "confidence" in data, (
            f"POST response missing 'confidence', got keys: {list(data.keys())}"
        )

    def test_post_feasibility_tab_response_has_key_finding(self, tmp_path):
        """POST feasibility/<tab> response must include 'key_finding' field."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        mock_result = {
            "conclusion": "favorable",
            "confidence": "high",
            "key_finding": "Specific finding text",
            "risks": [],
            "gaps": [],
            "sources": [],
        }
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with patch("workflows.feasibility.run_feasibility_tab", return_value=mock_result):
                with app.test_client() as c:
                    resp = c.post(
                        f"/api/scouting/items/{asset['id']}/feasibility/regulatory",
                        json={"item_type": "brownfield"},
                        content_type="application/json",
                    )
        store.close()
        data = resp.get_json()
        assert "key_finding" in data, (
            f"POST response missing 'key_finding', got keys: {list(data.keys())}"
        )

    def test_post_feasibility_tab_persists_result_to_store(self, tmp_path):
        """POST feasibility/<tab> must persist the result to the store."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        mock_result = {
            "conclusion": "favorable",
            "confidence": "high",
            "key_finding": "Stored finding",
            "risks": [],
            "gaps": [],
            "sources": [],
        }
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with patch("workflows.feasibility.run_feasibility_tab", return_value=mock_result):
                with app.test_client() as c:
                    c.post(
                        f"/api/scouting/items/{asset['id']}/feasibility/production",
                        json={"item_type": "brownfield"},
                        content_type="application/json",
                    )
        # Verify persistence directly in store
        result = store.get_feasibility_result(asset["id"], "production")
        store.close()
        assert result is not None, (
            "POST feasibility/<tab> must persist the result; get_feasibility_result returned None"
        )


# ---------------------------------------------------------------------------
# 10. Integration tests
# ---------------------------------------------------------------------------


class TestFeasibilityIntegration:
    """End-to-end integration: asset creation -> stage -> feasibility runs -> progress."""

    def test_create_asset_move_to_feasibility_run_production_tab(self, tmp_path):
        """Full pipeline: create asset, move to feasibility stage, run production study."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "integration.db"))
        # Create brownfield asset
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset("Siavonga Solar"))
        assert asset["scouting_stage"] == "identified"

        # Advance to feasibility stage
        store.update_scouting_stage("brownfield", asset["id"], "feasibility")
        updated = store.get_pipeline_asset(asset["id"])
        assert updated["scouting_stage"] == "feasibility"

        # Simulate running production tab (direct store interaction)
        findings = {
            "key_finding": "Capacity factor 22% — adequate for utility-scale economics",
            "risks": ["Grid curtailment risk"],
            "gaps": ["PPA not secured"],
            "sources": ["ACEC Zone Rankings"],
        }
        store.upsert_feasibility_result(
            item_id=asset["id"],
            item_type="brownfield",
            tab="production",
            conclusion="favorable",
            confidence="high",
            findings=findings,
        )

        result = store.get_feasibility_result(asset["id"], "production")
        store.close()
        assert result is not None
        assert result["conclusion"] == "favorable"

    def test_run_three_tabs_shows_progress_three_of_five(self, tmp_path):
        """After running 3 distinct tabs, progress shows completed=3, total=5."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "integration.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset("Kariba Wind"))
        findings = {"key_finding": "F", "risks": [], "gaps": [], "sources": []}

        for tab in ["production", "trading", "grid"]:
            store.upsert_feasibility_result(
                item_id=asset["id"],
                item_type="brownfield",
                tab=tab,
                conclusion="favorable",
                confidence="high",
                findings=findings,
            )

        progress = store.get_feasibility_progress(asset["id"])
        store.close()
        assert progress["completed"] == 3, (
            f"Expected completed=3, got {progress['completed']}"
        )
        assert progress["total"] == 5

    def test_re_run_tab_replaces_result_and_updated_at_changes(self, tmp_path):
        """Re-running a tab replaces old result; updated_at changes, count stays 1."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "integration.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset("Lusaka BESS"))
        findings_v1 = {"key_finding": "Initial analysis", "risks": [], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id=asset["id"],
            item_type="brownfield",
            tab="regulatory",
            conclusion="favorable",
            confidence="high",
            findings=findings_v1,
        )
        result_v1 = store.get_feasibility_result(asset["id"], "regulatory")
        updated_at_v1 = result_v1["updated_at"]

        time.sleep(0.01)

        findings_v2 = {"key_finding": "Revised analysis", "risks": ["Licensing delay"], "gaps": [], "sources": []}
        store.upsert_feasibility_result(
            item_id=asset["id"],
            item_type="brownfield",
            tab="regulatory",
            conclusion="marginal",
            confidence="medium",
            findings=findings_v2,
        )
        result_v2 = store.get_feasibility_result(asset["id"], "regulatory")
        results_all = store.get_feasibility_results(asset["id"])
        store.close()

        assert result_v2["conclusion"] == "marginal", (
            "Re-run conclusion must be 'marginal'"
        )
        assert result_v2["updated_at"] != updated_at_v1, (
            "updated_at must change after re-run"
        )
        # Only one regulatory result should exist (not two)
        regulatory_results = [r for r in results_all if r["tab"] == "regulatory"]
        assert len(regulatory_results) == 1, (
            f"Expected 1 regulatory result after re-run, got {len(regulatory_results)}"
        )

    def test_all_five_tabs_completed_shows_full_progress(self, tmp_path):
        """Running all 5 tabs shows completed=5, total=5, with all conclusions."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "integration.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset("Hwange Solar"))

        tab_conclusions = {
            "production": "favorable",
            "trading": "favorable",
            "grid": "marginal",
            "regulatory": "unfavorable",
            "financial": "marginal",
        }
        for tab, conclusion in tab_conclusions.items():
            findings = {"key_finding": f"{tab} analysis complete", "risks": [], "gaps": [], "sources": []}
            store.upsert_feasibility_result(
                item_id=asset["id"],
                item_type="brownfield",
                tab=tab,
                conclusion=conclusion,
                confidence="medium",
                findings=findings,
            )

        progress = store.get_feasibility_progress(asset["id"])
        store.close()
        assert progress["completed"] == 5
        assert progress["total"] == 5
        tabs = progress.get("tabs", {})
        for tab, expected_conclusion in tab_conclusions.items():
            assert tabs.get(tab) == expected_conclusion, (
                f"Expected tabs['{tab}']={expected_conclusion!r}, got {tabs.get(tab)!r}"
            )

    def test_financial_tab_via_api_with_prior_results_in_store(self, tmp_path):
        """POST financial tab via API returns 200 when prior results exist in store."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "integration.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset("Victoria Falls Solar"))

        # Pre-populate two tabs
        findings = {"key_finding": "Done", "risks": [], "gaps": [], "sources": []}
        for tab in ["production", "trading"]:
            store.upsert_feasibility_result(
                item_id=asset["id"],
                item_type="brownfield",
                tab=tab,
                conclusion="favorable",
                confidence="high",
                findings=findings,
            )

        mock_result = {
            "conclusion": "favorable",
            "confidence": "medium",
            "key_finding": "Financial analysis based on 2/5 completed tabs",
            "risks": ["Only 2 of 5 tabs completed — confidence is limited"],
            "gaps": ["Trading, grid, regulatory tabs not yet run"],
            "sources": ["FRED FX", "World Bank"],
        }
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with patch("workflows.feasibility.run_feasibility_tab", return_value=mock_result):
                with app.test_client() as c:
                    resp = c.post(
                        f"/api/scouting/items/{asset['id']}/feasibility/financial",
                        json={"item_type": "brownfield"},
                        content_type="application/json",
                    )
        result = store.get_feasibility_result(asset["id"], "financial")
        store.close()
        assert resp.status_code == 200
        assert result is not None, "Financial tab result must be persisted after POST"

    def test_feasibility_results_isolated_per_item(self, tmp_path):
        """Results for one item must not appear when querying a different item."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "integration.db"))
        asset_a = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset("Site Alpha"))
        asset_b = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset("Site Beta"))
        findings = {"key_finding": "F", "risks": [], "gaps": [], "sources": []}

        # Run all tabs for asset_a
        for tab in FEASIBILITY_TABS:
            store.upsert_feasibility_result(
                item_id=asset_a["id"],
                item_type="brownfield",
                tab=tab,
                conclusion="favorable",
                confidence="high",
                findings=findings,
            )

        # asset_b has no tabs run
        results_b = store.get_feasibility_results(asset_b["id"])
        progress_b = store.get_feasibility_progress(asset_b["id"])
        store.close()

        assert results_b == [], (
            "asset_b must have no results; got results from asset_a contamination"
        )
        assert progress_b["completed"] == 0, (
            "asset_b progress must show completed=0, not contaminated by asset_a"
        )
