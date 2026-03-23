"""Tests for SEP-059: Deep Research Memory — feedback, chat persistence, scouting RAG.

Covers:
  1. Thumbs up/down feedback on chat responses persisted to SQLite.
     - storage.LocalStorage grows a research_feedback table.
     - POST /api/research/<id>/chat/<message_id>/feedback saves rating.
     - Feedback survives creating a new LocalStorage instance (restart).

  2. Chat thread persistence across restarts.
     - storage.LocalStorage grows a research_chat_history table.
     - Chat turns written by research_chat are stored in SQLite.
     - GET /api/research/<id>/chat/history returns persisted thread.
     - Thread survives a new LocalStorage instance.

  3. Scouting feasibility findings injected as internal sources.
     - aggregator.aggregate_sources accepts an optional scouting store or
       equivalent and returns Source objects with source_type='internal' for
       completed scouting cases (stage >= feasibility) topically relevant to
       the query.
     - scouting_knowledge_sources() helper exists in the aggregator module.
     - Internal sources are not returned for unrelated queries.
     - Internal sources include asset name, conclusion, and a URL-like identifier.

All tests are expected to FAIL until SEP-059 is implemented.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Module-level import of web app (graceful skip if heavy deps missing)
# ---------------------------------------------------------------------------

WEB_APP_IMPORT_ERROR = None
web_app = None
try:
    _APP_PATH = PROJECT_ROOT / "ui" / "web" / "app.py"
    _SPEC = importlib.util.spec_from_file_location("web_app_sep059", _APP_PATH)
    web_app = importlib.util.module_from_spec(_SPEC)
    sys.modules["web_app_sep059"] = web_app
    _SPEC.loader.exec_module(web_app)
except ModuleNotFoundError as exc:
    WEB_APP_IMPORT_ERROR = exc


def _skip_if_no_app():
    if WEB_APP_IMPORT_ERROR is not None:
        pytest.skip(f"web app unavailable: {WEB_APP_IMPORT_ERROR}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_local_storage(tmp_path):
    from engine.storage import LocalStorage
    return LocalStorage(db_path=str(tmp_path / "zorora.db"))


def _make_imaging_store(tmp_path):
    from tools.imaging.store import ImagingDataStore
    return ImagingDataStore(db_path=str(tmp_path / "imaging.db"))


def _make_brownfield_asset(name="Kafue Solar 100MW", country="Zambia",
                            technology="solar", capacity_mw=100.0):
    return {
        "properties": {
            "site_id": f"gen:{name.lower().replace(' ', '_')}",
            "name": name,
            "technology": technology,
            "capacity_mw": capacity_mw,
            "status": "operating",
            "operator": "Acme Energy",
            "owner": "Acme Energy",
            "country": country,
        },
        "geometry": {"type": "Point", "coordinates": [27.8, -15.4]},
    }


# ===========================================================================
# 1. STORAGE — research_feedback TABLE
# ===========================================================================


class TestFeedbackSchema:
    """LocalStorage must have a research_feedback table after SEP-059."""

    def test_feedback_table_exists(self, tmp_path):
        """LocalStorage._init_schema must create a research_feedback table."""
        store = _make_local_storage(tmp_path)
        cur = store.conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='research_feedback'"
        )
        row = cur.fetchone()
        store.close()
        assert row is not None, (
            "research_feedback table not found in zorora.db — "
            "SEP-059 requires LocalStorage._init_schema to create it"
        )

    def test_feedback_table_has_required_columns(self, tmp_path):
        """research_feedback must have: id, research_id, message_id, rating, created_at."""
        store = _make_local_storage(tmp_path)
        cur = store.conn.cursor()
        cur.execute("PRAGMA table_info(research_feedback)")
        columns = {row["name"] for row in cur.fetchall()}
        store.close()
        required = {"id", "research_id", "message_id", "rating", "created_at"}
        missing = required - columns
        assert not missing, (
            f"research_feedback table is missing columns: {missing}"
        )

    def test_save_feedback_method_exists_on_local_storage(self, tmp_path):
        """LocalStorage must have a save_feedback method (not just raise AttributeError)."""
        store = _make_local_storage(tmp_path)
        has_method = hasattr(store, "save_feedback") and callable(
            getattr(store, "save_feedback", None)
        )
        store.close()
        assert has_method, (
            "LocalStorage must expose a save_feedback(research_id, message_id, rating) method"
        )

    def test_rating_constrained_to_thumbs_values(self, tmp_path):
        """save_feedback must exist and reject ratings other than 'up' and 'down'."""
        store = _make_local_storage(tmp_path)
        # Must be a real validation error from save_feedback, not AttributeError.
        # If save_feedback doesn't exist this test fails with AttributeError caught
        # as a plain Exception — we want it to fail specifically because the method
        # DOES exist but rejects the invalid rating.
        assert hasattr(store, "save_feedback"), (
            "save_feedback method must exist before rating validation can be tested"
        )
        with pytest.raises((ValueError, Exception)):
            store.save_feedback(
                research_id="r1",
                message_id="m1",
                rating="sideways",
            )
        store.close()


class TestFeedbackPersistence:
    """save_feedback / get_feedback must round-trip through SQLite."""

    def test_save_feedback_up(self, tmp_path):
        """Saving a thumbs-up feedback must be readable back."""
        store = _make_local_storage(tmp_path)
        store.save_feedback(research_id="r1", message_id="m1", rating="up")
        rows = store.get_feedback(research_id="r1")
        store.close()
        assert len(rows) == 1, f"Expected 1 feedback row, got {len(rows)}"
        assert rows[0]["rating"] == "up"
        assert rows[0]["message_id"] == "m1"

    def test_save_feedback_down(self, tmp_path):
        """Saving a thumbs-down feedback must be readable back."""
        store = _make_local_storage(tmp_path)
        store.save_feedback(research_id="r1", message_id="m1", rating="down")
        rows = store.get_feedback(research_id="r1")
        store.close()
        assert len(rows) == 1
        assert rows[0]["rating"] == "down"

    def test_feedback_survives_restart(self, tmp_path):
        """Feedback written by one LocalStorage instance must be visible to a new one."""
        db_path = str(tmp_path / "zorora.db")
        from engine.storage import LocalStorage

        store_a = LocalStorage(db_path=db_path)
        store_a.save_feedback(research_id="r1", message_id="msg-42", rating="up")
        store_a.close()

        store_b = LocalStorage(db_path=db_path)
        rows = store_b.get_feedback(research_id="r1")
        store_b.close()

        assert len(rows) == 1, (
            "Feedback not found in new LocalStorage instance — "
            "must survive restart"
        )
        assert rows[0]["rating"] == "up"

    def test_multiple_feedbacks_for_same_research(self, tmp_path):
        """Multiple feedback rows for different messages in one research session."""
        store = _make_local_storage(tmp_path)
        store.save_feedback(research_id="r1", message_id="m1", rating="up")
        store.save_feedback(research_id="r1", message_id="m2", rating="down")
        rows = store.get_feedback(research_id="r1")
        store.close()
        assert len(rows) == 2, f"Expected 2 feedback rows, got {len(rows)}"

    def test_feedback_isolated_by_research_id(self, tmp_path):
        """get_feedback(research_id='r1') must not return rows for 'r2'."""
        store = _make_local_storage(tmp_path)
        store.save_feedback(research_id="r1", message_id="m1", rating="up")
        store.save_feedback(research_id="r2", message_id="m1", rating="down")
        rows = store.get_feedback(research_id="r1")
        store.close()
        assert all(r["research_id"] == "r1" for r in rows)

    def test_upsert_feedback_updates_existing_message(self, tmp_path):
        """Saving feedback twice for the same message_id must update, not duplicate."""
        store = _make_local_storage(tmp_path)
        store.save_feedback(research_id="r1", message_id="m1", rating="down")
        store.save_feedback(research_id="r1", message_id="m1", rating="up")
        rows = store.get_feedback(research_id="r1")
        store.close()
        assert len(rows) == 1, (
            "save_feedback must upsert — same message_id should not duplicate"
        )
        assert rows[0]["rating"] == "up", "Updated rating must be 'up'"


# ===========================================================================
# 2. STORAGE — research_chat_history TABLE
# ===========================================================================


class TestChatHistorySchema:
    """LocalStorage must have a research_chat_history table after SEP-059."""

    def test_chat_history_table_exists(self, tmp_path):
        """LocalStorage._init_schema must create a research_chat_history table."""
        store = _make_local_storage(tmp_path)
        cur = store.conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='research_chat_history'"
        )
        row = cur.fetchone()
        store.close()
        assert row is not None, (
            "research_chat_history table not found — "
            "SEP-059 requires LocalStorage._init_schema to create it"
        )

    def test_chat_history_has_required_columns(self, tmp_path):
        """research_chat_history must have: id, thread_key, role, content, created_at."""
        store = _make_local_storage(tmp_path)
        cur = store.conn.cursor()
        cur.execute("PRAGMA table_info(research_chat_history)")
        columns = {row["name"] for row in cur.fetchall()}
        store.close()
        required = {"id", "thread_key", "role", "content", "created_at"}
        missing = required - columns
        assert not missing, (
            f"research_chat_history table missing columns: {missing}"
        )

    def test_append_chat_turn_method_exists(self, tmp_path):
        """LocalStorage must have an append_chat_turn method."""
        store = _make_local_storage(tmp_path)
        has_method = hasattr(store, "append_chat_turn") and callable(
            getattr(store, "append_chat_turn", None)
        )
        store.close()
        assert has_method, (
            "LocalStorage must expose append_chat_turn(thread_key, role, content) method"
        )

    def test_load_chat_thread_method_exists(self, tmp_path):
        """LocalStorage must have a load_chat_thread method."""
        store = _make_local_storage(tmp_path)
        has_method = hasattr(store, "load_chat_thread") and callable(
            getattr(store, "load_chat_thread", None)
        )
        store.close()
        assert has_method, (
            "LocalStorage must expose load_chat_thread(thread_key) method"
        )


class TestChatHistoryPersistence:
    """append_chat_turn / load_chat_thread must round-trip through SQLite."""

    def test_append_and_load_single_turn(self, tmp_path):
        """append_chat_turn writes a row; load_chat_thread returns it."""
        store = _make_local_storage(tmp_path)
        store.append_chat_turn(
            thread_key="research:abc123",
            role="user",
            content="What is the LCOE for solar in Zambia?",
        )
        thread = store.load_chat_thread("research:abc123")
        store.close()
        assert len(thread) == 1, f"Expected 1 chat turn, got {len(thread)}"
        assert thread[0]["role"] == "user"
        assert "LCOE" in thread[0]["content"]

    def test_append_preserves_order(self, tmp_path):
        """Multiple appended turns must come back in insertion order."""
        store = _make_local_storage(tmp_path)
        store.append_chat_turn("research:r1", "user", "Question one")
        store.append_chat_turn("research:r1", "assistant", "Answer one")
        store.append_chat_turn("research:r1", "user", "Question two")
        thread = store.load_chat_thread("research:r1")
        store.close()
        assert len(thread) == 3
        assert thread[0]["role"] == "user"
        assert thread[1]["role"] == "assistant"
        assert thread[2]["content"] == "Question two"

    def test_chat_history_survives_restart(self, tmp_path):
        """Chat turns written by one LocalStorage must be visible to a new one."""
        db_path = str(tmp_path / "zorora.db")
        from engine.storage import LocalStorage

        store_a = LocalStorage(db_path=db_path)
        store_a.append_chat_turn("research:r1", "user", "Hello persistent world")
        store_a.close()

        store_b = LocalStorage(db_path=db_path)
        thread = store_b.load_chat_thread("research:r1")
        store_b.close()

        assert len(thread) == 1, (
            "Chat history not found in new LocalStorage instance — "
            "must survive restart"
        )
        assert "persistent" in thread[0]["content"]

    def test_load_empty_thread_returns_list(self, tmp_path):
        """load_chat_thread on an unknown thread_key must return an empty list."""
        store = _make_local_storage(tmp_path)
        thread = store.load_chat_thread("research:nonexistent")
        store.close()
        assert isinstance(thread, list)
        assert thread == []

    def test_threads_are_isolated_by_key(self, tmp_path):
        """load_chat_thread must only return turns for the requested thread_key."""
        store = _make_local_storage(tmp_path)
        store.append_chat_turn("research:r1", "user", "r1 message")
        store.append_chat_turn("research:r2", "user", "r2 message")
        thread_r1 = store.load_chat_thread("research:r1")
        store.close()
        assert all(t.get("content") != "r2 message" for t in thread_r1), (
            "Thread isolation broken — r2's messages leaked into r1"
        )


# ===========================================================================
# 3. FLASK API — POST /api/research/<id>/chat/<message_id>/feedback
# ===========================================================================


class TestFeedbackEndpoint:
    """POST /api/research/<id>/chat/<message_id>/feedback must persist rating."""

    def setup_method(self):
        _skip_if_no_app()

    def _post_feedback(self, research_id, message_id, rating):
        client = web_app.app.test_client()
        return client.post(
            f"/api/research/{research_id}/chat/{message_id}/feedback",
            json={"rating": rating},
            content_type="application/json",
        )

    def test_feedback_endpoint_exists_for_up(self):
        """POST …/feedback with rating='up' must not return 404."""
        resp = self._post_feedback("test-research-id", "msg-001", "up")
        assert resp.status_code != 404, (
            "Feedback endpoint not found — POST /api/research/<id>/chat/<mid>/feedback "
            "must be registered"
        )

    def test_feedback_endpoint_returns_ok(self):
        """Valid thumbs-up must return HTTP 200 with status ok."""
        resp = self._post_feedback("test-research-id", "msg-001", "up")
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.get_data(as_text=True)}"
        )
        data = resp.get_json()
        assert data is not None
        assert data.get("status") == "ok", f"Expected status='ok', got {data}"

    def test_feedback_down_returns_ok(self):
        """Valid thumbs-down must return HTTP 200."""
        resp = self._post_feedback("test-research-id", "msg-002", "down")
        assert resp.status_code == 200

    def test_invalid_rating_returns_400(self):
        """Invalid rating value must return HTTP 400."""
        resp = self._post_feedback("test-research-id", "msg-003", "meh")
        assert resp.status_code == 400, (
            f"Invalid rating should return 400, got {resp.status_code}"
        )

    def test_missing_rating_returns_400(self):
        """Request body without rating field must return HTTP 400."""
        client = web_app.app.test_client()
        resp = client.post(
            "/api/research/test-research-id/chat/msg-004/feedback",
            json={},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_feedback_response_contains_status_ok(self):
        """Feedback response body must include status='ok' when valid."""
        resp = self._post_feedback("my-research-42", "msg-001", "up")
        assert resp.status_code == 200, (
            f"Expected 200 for valid feedback, got {resp.status_code}"
        )
        data = resp.get_json() or {}
        assert data.get("status") == "ok", (
            f"Response body must include status='ok', got {data}"
        )


# ===========================================================================
# 4. FLASK API — GET /api/research/<id>/chat/history
# ===========================================================================


class TestChatHistoryEndpoint:
    """GET /api/research/<id>/chat/history must return persisted thread."""

    def setup_method(self):
        _skip_if_no_app()

    def test_history_endpoint_exists(self):
        """GET …/chat/history must not return 404."""
        client = web_app.app.test_client()
        resp = client.get("/api/research/nonexistent-id/chat/history")
        assert resp.status_code != 404, (
            "Chat history endpoint not found — "
            "GET /api/research/<id>/chat/history must be registered"
        )

    def test_history_for_nonexistent_research_returns_empty_list(self):
        """Unknown research_id must return 200 with an empty history list."""
        client = web_app.app.test_client()
        resp = client.get("/api/research/definitely-nonexistent-xyz/chat/history")
        assert resp.status_code == 200, (
            f"Expected 200 for unknown research_id, got {resp.status_code}. "
            "History endpoint must return empty list, not 404."
        )
        data = resp.get_json()
        assert data is not None, "Response must be JSON"
        # Accept {history: []} or {thread: []} or []
        if isinstance(data, dict):
            history = data.get("history") or data.get("thread") or []
        else:
            history = data
        assert isinstance(history, list), (
            f"History must be a list, got: {type(history)}"
        )
        assert history == [], (
            f"Unknown research_id must yield empty history, got: {history}"
        )

    def test_history_response_is_json(self):
        """History endpoint must return JSON content."""
        client = web_app.app.test_client()
        resp = client.get("/api/research/test-id/chat/history")
        assert resp.content_type and "json" in resp.content_type, (
            f"Expected JSON content-type, got {resp.content_type}"
        )

    def test_history_response_has_history_key(self):
        """History response must include a 'history' key containing a list."""
        client = web_app.app.test_client()
        resp = client.get("/api/research/test-id/chat/history")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data is not None
        assert "history" in data, (
            f"Response must have a 'history' key, got keys: {list(data.keys()) if isinstance(data, dict) else type(data)}"
        )
        assert isinstance(data["history"], list), (
            f"'history' value must be a list, got {type(data['history'])}"
        )


# ===========================================================================
# 5. CHAT ENDPOINT writes to SQLite (not just in-memory dict)
# ===========================================================================


class TestResearchChatPersistsToSQLite:
    """The existing POST /api/research/<id>/chat must now write turns to SQLite."""

    def setup_method(self):
        _skip_if_no_app()

    def test_chat_threads_dict_still_exists(self):
        """chat_threads module-level dict must still exist (backward compat)."""
        assert hasattr(web_app, "chat_threads"), (
            "chat_threads dict must remain on web_app module"
        )

    def test_app_has_storage_instance_or_uses_local_storage(self):
        """web app must reference LocalStorage for chat history persistence."""
        app_source = (PROJECT_ROOT / "ui" / "web" / "app.py").read_text()
        assert "LocalStorage" in app_source or "research_chat_history" in app_source, (
            "app.py must use LocalStorage or reference research_chat_history table "
            "to persist chat turns across restarts"
        )

    def test_app_uses_append_chat_turn_or_equivalent(self):
        """app.py must call append_chat_turn or save chat history to SQLite."""
        app_source = (PROJECT_ROOT / "ui" / "web" / "app.py").read_text()
        assert "append_chat_turn" in app_source or "research_chat_history" in app_source, (
            "app.py must call append_chat_turn() or write directly to "
            "research_chat_history table to persist chat turns"
        )


# ===========================================================================
# 6. AGGREGATOR — scouting_knowledge_sources() function
# ===========================================================================


class TestScoutingKnowledgeSources:
    """aggregator module must expose scouting_knowledge_sources()."""

    def test_function_exists_in_aggregator(self):
        """scouting_knowledge_sources must be importable from the aggregator."""
        from workflows.deep_research.aggregator import scouting_knowledge_sources
        assert callable(scouting_knowledge_sources), (
            "scouting_knowledge_sources must be a callable function"
        )

    def test_returns_list_of_sources(self, tmp_path):
        """scouting_knowledge_sources must return a list (possibly empty)."""
        from workflows.deep_research.aggregator import scouting_knowledge_sources
        imaging_store = _make_imaging_store(tmp_path)
        results = scouting_knowledge_sources(
            query="solar energy zambia",
            imaging_store=imaging_store,
        )
        imaging_store.close()
        assert isinstance(results, list), (
            f"Expected list, got {type(results)}"
        )

    def test_returns_empty_for_no_scouting_data(self, tmp_path):
        """When no scouting items exist, must return an empty list."""
        from workflows.deep_research.aggregator import scouting_knowledge_sources
        imaging_store = _make_imaging_store(tmp_path)
        results = scouting_knowledge_sources(
            query="solar energy zambia",
            imaging_store=imaging_store,
        )
        imaging_store.close()
        assert results == [], (
            f"No scouting data means no internal sources, got {results}"
        )

    def test_completed_case_returns_internal_source(self, tmp_path):
        """A completed feasibility case must appear as source_type='internal'."""
        from workflows.deep_research.aggregator import scouting_knowledge_sources

        imaging_store = _make_imaging_store(tmp_path)

        # Create a brownfield asset and set it to feasibility stage
        asset = _make_brownfield_asset(name="Kafue Solar 100MW", country="Zambia")
        saved = imaging_store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]
        imaging_store.update_scouting_stage("brownfield", item_id, "feasibility")

        # Add a completed feasibility result for this item
        imaging_store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="production",
            conclusion="viable",
            confidence="high",
            findings={
                "key_finding": "High solar irradiance in Zambia makes this site viable.",
                "risks": ["Grid connectivity"],
                "gaps": [],
                "sources": [],
            },
        )

        results = scouting_knowledge_sources(
            query="solar energy zambia feasibility production",
            imaging_store=imaging_store,
        )
        imaging_store.close()

        assert len(results) > 0, (
            "Expected at least one internal source for completed scouting case "
            "relevant to query 'solar energy zambia'"
        )
        source_types = [getattr(s, "source_type", None) or s.get("source_type") for s in results]
        assert "internal" in source_types, (
            f"Expected source_type='internal', got types: {source_types}"
        )

    def test_internal_source_has_asset_name_in_title(self, tmp_path):
        """Internal source title must include the scouting case's asset name."""
        from workflows.deep_research.aggregator import scouting_knowledge_sources

        imaging_store = _make_imaging_store(tmp_path)
        asset = _make_brownfield_asset(name="Limpopo Wind Farm", country="South Africa")
        saved = imaging_store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]
        imaging_store.update_scouting_stage("brownfield", item_id, "feasibility")
        imaging_store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="grid",
            conclusion="marginal",
            confidence="medium",
            findings={"key_finding": "Grid connection uncertain", "risks": [], "gaps": [], "sources": []},
        )

        results = scouting_knowledge_sources(
            query="wind farm south africa grid connection",
            imaging_store=imaging_store,
        )
        imaging_store.close()

        if results:
            titles = [getattr(s, "title", None) or s.get("title", "") for s in results]
            assert any("Limpopo" in t or "Wind Farm" in t for t in titles), (
                f"Expected asset name in source title, got titles: {titles}"
            )

    def test_internal_source_has_non_empty_url(self, tmp_path):
        """Internal source url must be a non-empty string identifier."""
        from workflows.deep_research.aggregator import scouting_knowledge_sources

        imaging_store = _make_imaging_store(tmp_path)
        asset = _make_brownfield_asset(name="Kitwe BESS", country="Zambia")
        saved = imaging_store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]
        imaging_store.update_scouting_stage("brownfield", item_id, "diligence")
        imaging_store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="financial",
            conclusion="viable",
            confidence="high",
            findings={"key_finding": "IRR exceeds hurdle rate", "risks": [], "gaps": [], "sources": []},
        )

        results = scouting_knowledge_sources(
            query="battery storage zambia financial",
            imaging_store=imaging_store,
        )
        imaging_store.close()

        for s in results:
            url = getattr(s, "url", None) or s.get("url", "")
            assert url, f"Internal source must have a non-empty url, got {url!r}"

    def test_unrelated_query_returns_no_internal_sources(self, tmp_path):
        """A query with no keyword overlap must not return scouting sources."""
        from workflows.deep_research.aggregator import scouting_knowledge_sources

        imaging_store = _make_imaging_store(tmp_path)
        asset = _make_brownfield_asset(name="Kafue Solar", country="Zambia",
                                        technology="solar")
        saved = imaging_store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]
        imaging_store.update_scouting_stage("brownfield", item_id, "feasibility")
        imaging_store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="production",
            conclusion="viable",
            confidence="high",
            findings={"key_finding": "Good solar resource", "risks": [], "gaps": [], "sources": []},
        )

        # Query with zero overlap with solar/zambia/kafue
        results = scouting_knowledge_sources(
            query="global cryptocurrency regulation SEC enforcement",
            imaging_store=imaging_store,
        )
        imaging_store.close()

        assert results == [], (
            f"Unrelated query must return no internal sources, got {results}"
        )

    def test_only_feasibility_or_later_stages_included(self, tmp_path):
        """Items in 'identified' or 'scored' stage must NOT appear as internal sources."""
        from workflows.deep_research.aggregator import scouting_knowledge_sources

        imaging_store = _make_imaging_store(tmp_path)
        asset = _make_brownfield_asset(name="Harare Solar", country="Zimbabwe",
                                        technology="solar")
        saved = imaging_store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]

        # Stage is 'identified' (default), not yet at feasibility
        # Do NOT advance stage — leave at identified

        imaging_store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="production",
            conclusion="viable",
            confidence="high",
            findings={"key_finding": "Good solar", "risks": [], "gaps": [], "sources": []},
        )

        results = scouting_knowledge_sources(
            query="solar zimbabwe harare production",
            imaging_store=imaging_store,
        )
        imaging_store.close()

        assert results == [], (
            "Items at 'identified' stage must not appear as internal sources — "
            "only feasibility, diligence, or decision stage items qualify"
        )

    def test_decision_stage_items_included(self, tmp_path):
        """Items at 'decision' stage must also appear as internal sources."""
        from workflows.deep_research.aggregator import scouting_knowledge_sources

        imaging_store = _make_imaging_store(tmp_path)
        asset = _make_brownfield_asset(name="Gaborone Wind", country="Botswana",
                                        technology="wind")
        saved = imaging_store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]
        imaging_store.update_scouting_stage("brownfield", item_id, "decision")
        imaging_store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="regulatory",
            conclusion="viable",
            confidence="high",
            findings={"key_finding": "Permits secured", "risks": [], "gaps": [], "sources": []},
        )

        results = scouting_knowledge_sources(
            query="wind power botswana regulatory permits",
            imaging_store=imaging_store,
        )
        imaging_store.close()

        assert len(results) > 0, (
            "Items at 'decision' stage with feasibility results must appear as internal sources"
        )


# ===========================================================================
# 7. AGGREGATOR — aggregate_sources integrates scouting sources
# ===========================================================================


class TestAggregateSourcesIntegration:
    """aggregate_sources must accept and propagate scouting knowledge."""

    def test_aggregate_sources_accepts_imaging_store_kwarg(self, tmp_path):
        """aggregate_sources must accept an optional imaging_store parameter."""
        from workflows.deep_research.aggregator import aggregate_sources
        import inspect
        sig = inspect.signature(aggregate_sources)
        assert "imaging_store" in sig.parameters, (
            "aggregate_sources must accept an 'imaging_store' keyword argument "
            "for scouting RAG integration"
        )

    def test_aggregate_sources_includes_internal_sources_when_relevant(self, tmp_path):
        """aggregate_sources with imaging_store must include internal source type."""
        from unittest.mock import patch
        from workflows.deep_research.aggregator import aggregate_sources

        imaging_store = _make_imaging_store(tmp_path)
        asset = _make_brownfield_asset(name="Ndola Solar", country="Zambia")
        saved = imaging_store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]
        imaging_store.update_scouting_stage("brownfield", item_id, "feasibility")
        imaging_store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="production",
            conclusion="viable",
            confidence="high",
            findings={"key_finding": "Excellent resource", "risks": [], "gaps": [], "sources": []},
        )

        # Patch external fetchers to return empty lists so only internal matters
        with (
            patch("workflows.deep_research.aggregator.academic_search_sources", return_value=[]),
            patch("workflows.deep_research.aggregator.web_search_sources", return_value=[]),
            patch("workflows.deep_research.aggregator.fetch_newsroom_api", return_value=[]),
            patch("workflows.deep_research.aggregator.worldbank_search_sources", return_value=[]),
            patch("workflows.deep_research.aggregator.policy_search_sources", return_value=[]),
            patch("workflows.deep_research.aggregator.sec_search_sources", return_value=[]),
        ):
            sources = aggregate_sources(
                query="solar energy zambia production feasibility",
                imaging_store=imaging_store,
            )

        imaging_store.close()

        internal = [s for s in sources if getattr(s, "source_type", None) == "internal"]
        assert len(internal) > 0, (
            "aggregate_sources with relevant scouting data must include at least one "
            "source with source_type='internal'"
        )

    def test_aggregate_sources_without_imaging_store_unchanged(self):
        """Calling aggregate_sources without imaging_store must not raise errors."""
        from unittest.mock import patch
        from workflows.deep_research.aggregator import aggregate_sources

        with (
            patch("workflows.deep_research.aggregator.academic_search_sources", return_value=[]),
            patch("workflows.deep_research.aggregator.web_search_sources", return_value=[]),
            patch("workflows.deep_research.aggregator.fetch_newsroom_api", return_value=[]),
            patch("workflows.deep_research.aggregator.worldbank_search_sources", return_value=[]),
            patch("workflows.deep_research.aggregator.policy_search_sources", return_value=[]),
            patch("workflows.deep_research.aggregator.sec_search_sources", return_value=[]),
        ):
            # Must not raise — imaging_store should default to None
            sources = aggregate_sources(query="solar zambia")

        assert isinstance(sources, list)


# ===========================================================================
# 8. FRONTEND — thumbs up/down UI elements exist in index.html
# ===========================================================================


class TestFrontendFeedbackUI:
    """The research chat UI must render thumbs feedback buttons on assistant messages."""

    def _html(self):
        return (PROJECT_ROOT / "ui" / "web" / "templates" / "index.html").read_text()

    def test_thumbs_up_reference_exists_in_html(self):
        """index.html must contain an explicit thumbs-up feedback element."""
        html = self._html()
        # Require one of the unambiguous explicit markers for thumbs-up
        has_up = (
            "thumbs-up" in html
            or "thumb_up" in html
            or "thumbsUp" in html
            or "\U0001f44d" in html  # 👍 emoji
        )
        assert has_up, (
            "index.html must contain an explicit thumbs-up feedback element for chat messages. "
            "Expected 'thumbs-up', 'thumbsUp', 'thumb_up', or the 👍 emoji. "
            "The word 'rating' alone is not sufficient."
        )

    def test_thumbs_down_reference_exists_in_html(self):
        """index.html must contain an explicit thumbs-down feedback element."""
        html = self._html()
        has_down = (
            "thumbs-down" in html
            or "thumb_down" in html
            or "thumbsDown" in html
            or "\U0001f44e" in html  # 👎 emoji
        )
        assert has_down, (
            "index.html must contain an explicit thumbs-down feedback element for chat messages. "
            "Expected 'thumbs-down', 'thumbsDown', 'thumb_down', or the 👎 emoji."
        )

    def test_feedback_api_call_in_html(self):
        """index.html must contain a fetch/XHR call to the feedback endpoint."""
        html = self._html()
        assert "/feedback" in html, (
            "index.html must call the feedback API endpoint "
            "(.../chat/<message_id>/feedback)"
        )
