"""Tests for SEP-065: FTS5 index for scouting RAG retrieval.

Covers:
  1. FTS5 virtual table created in ImagingDataStore schema.
  2. Rebuild method populates FTS index from existing feasibility_results rows.
  3. FTS search method returns ranked results via BM25 / FTS5 MATCH.
  4. Porter stemming: "regulation" matches data containing "regulatory" and vice versa.
  5. Non-matching queries return empty results.
  6. scouting_knowledge_sources() returns results via the FTS5 path.
  7. Incremental FTS indexing when upsert_feasibility_result() is called.
  8. Fallback behavior when FTS table is absent (backward-compatible).

All tests are expected to FAIL until SEP-065 is implemented.
"""

from __future__ import annotations

import pathlib
import sqlite3
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
# 1. FTS5 TABLE CREATION
# ===========================================================================


class TestFts5TableCreation:
    """ImagingDataStore._init_schema must create an FTS5 virtual table."""

    def test_fts5_table_exists_after_init(self, tmp_path):
        """A freshly created ImagingDataStore must have an FTS5 virtual table for
        scouting feasibility findings.

        The table name must be 'feasibility_fts'.
        """
        store = _make_imaging_store(tmp_path)
        cur = store.conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='feasibility_fts'"
        )
        row = cur.fetchone()
        store.close()
        assert row is not None, (
            "feasibility_fts FTS5 virtual table not found in imaging_data.db — "
            "SEP-065 requires ImagingDataStore._init_schema to create it using "
            "CREATE VIRTUAL TABLE feasibility_fts USING fts5(...)"
        )

    def test_fts5_table_uses_porter_stemming(self, tmp_path):
        """The FTS5 table must be created with Porter stemming enabled
        (tokenize='porter ascii' or equivalent).

        This is what allows 'regulation' to match 'regulatory'.
        """
        store = _make_imaging_store(tmp_path)
        cur = store.conn.cursor()
        # FTS5 stores its configuration in the _config shadow table
        cur.execute(
            "SELECT * FROM feasibility_fts_config WHERE k = 'tokenize'"
        )
        row = cur.fetchone()
        store.close()
        assert row is not None, (
            "feasibility_fts_config table not found — FTS5 config shadow table should "
            "exist when the virtual table is created with tokenize option"
        )
        # The tokenize value must include 'porter'
        tokenize_val = str(row[1] if not hasattr(row, '__getitem__') else row["v"])
        assert "porter" in tokenize_val.lower(), (
            f"FTS5 table must use Porter stemming, but tokenize config is: {tokenize_val!r}"
        )

    def test_fts5_table_has_expected_columns(self, tmp_path):
        """The FTS5 table must index fields relevant for retrieval:
        at minimum: content (concatenated searchable text), item_id.

        We verify by inserting a row and checking it can be queried.
        """
        store = _make_imaging_store(tmp_path)
        # If the table was created correctly, inserting a row should not raise
        try:
            store.conn.execute(
                "INSERT INTO feasibility_fts (item_id, content) VALUES (?, ?)",
                ("test_id", "solar energy feasibility in Zambia"),
            )
            store.conn.commit()
        except sqlite3.OperationalError as exc:
            store.close()
            pytest.fail(
                f"Could not insert into feasibility_fts with (item_id, content) columns: {exc}"
            )
        # Verify the row is retrievable via MATCH
        cur = store.conn.cursor()
        cur.execute(
            "SELECT item_id FROM feasibility_fts WHERE feasibility_fts MATCH ?",
            ("solar",),
        )
        rows = cur.fetchall()
        store.close()
        assert len(rows) == 1, (
            f"Expected 1 row from FTS MATCH 'solar', got {len(rows)}"
        )


# ===========================================================================
# 2. FTS INDEX REBUILD METHOD
# ===========================================================================


class TestFts5RebuildMethod:
    """ImagingDataStore must expose a method to rebuild the FTS index from
    existing feasibility_results rows.
    """

    def test_rebuild_fts_index_method_exists(self, tmp_path):
        """ImagingDataStore must have a rebuild_fts_index() method."""
        store = _make_imaging_store(tmp_path)
        has_method = hasattr(store, "rebuild_fts_index") and callable(
            getattr(store, "rebuild_fts_index", None)
        )
        store.close()
        assert has_method, (
            "ImagingDataStore must expose a rebuild_fts_index() method — "
            "SEP-065 requires it to populate the FTS index from existing rows"
        )

    def test_rebuild_fts_index_populates_from_existing_results(self, tmp_path):
        """rebuild_fts_index() must index all existing feasibility_results rows.

        After calling rebuild_fts_index(), a MATCH query must find results
        that were in feasibility_results before the rebuild.
        """
        store = _make_imaging_store(tmp_path)

        # Seed data: add a feasibility result directly without FTS indexing
        asset = _make_brownfield_asset(name="Lusaka Wind Farm", country="Zambia",
                                        technology="wind")
        saved = store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]
        store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="regulatory",
            conclusion="viable",
            confidence="high",
            findings={
                "key_finding": "Wind permits issued under ZEMA framework",
                "risks": [],
                "gaps": [],
                "sources": [],
            },
        )

        # Rebuild FTS index from existing data
        store.rebuild_fts_index()

        # The item should now be findable via FTS MATCH
        cur = store.conn.cursor()
        cur.execute(
            "SELECT item_id FROM feasibility_fts WHERE feasibility_fts MATCH ?",
            ("ZEMA",),
        )
        rows = cur.fetchall()
        store.close()
        assert len(rows) >= 1, (
            "rebuild_fts_index() did not index existing feasibility_results — "
            "MATCH for 'ZEMA' returned no rows after rebuild"
        )

    def test_rebuild_fts_index_clears_stale_entries(self, tmp_path):
        """rebuild_fts_index() must replace stale FTS content with current DB state.

        If a feasibility result is deleted and rebuild is called, the deleted
        item must no longer appear in FTS results.
        """
        store = _make_imaging_store(tmp_path)

        asset = _make_brownfield_asset(name="Cape Town BESS", country="South Africa",
                                        technology="bess")
        saved = store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]
        store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="financial",
            conclusion="viable",
            confidence="medium",
            findings={
                "key_finding": "BESS arbitrage economics are strong in Cape Town",
                "risks": [],
                "gaps": [],
                "sources": [],
            },
        )

        # Delete the feasibility result directly via SQL (bypassing triggers)
        store.conn.execute(
            "DELETE FROM feasibility_results WHERE item_id = ?",
            (item_id,),
        )
        store.conn.commit()

        # Rebuild should clear the stale FTS entry
        store.rebuild_fts_index()

        cur = store.conn.cursor()
        cur.execute(
            "SELECT item_id FROM feasibility_fts WHERE feasibility_fts MATCH ?",
            ("arbitrage",),
        )
        rows = cur.fetchall()
        store.close()
        assert len(rows) == 0, (
            "rebuild_fts_index() must remove stale FTS entries for deleted feasibility results"
        )


# ===========================================================================
# 3. FTS SEARCH METHOD WITH RANKED RESULTS
# ===========================================================================


class TestFts5SearchMethod:
    """ImagingDataStore must expose a search_feasibility_fts() method that
    returns ranked results using BM25.
    """

    def test_search_feasibility_fts_method_exists(self, tmp_path):
        """ImagingDataStore must have a search_feasibility_fts() method."""
        store = _make_imaging_store(tmp_path)
        has_method = hasattr(store, "search_feasibility_fts") and callable(
            getattr(store, "search_feasibility_fts", None)
        )
        store.close()
        assert has_method, (
            "ImagingDataStore must expose a search_feasibility_fts(query, limit) method"
        )

    def test_search_returns_list(self, tmp_path):
        """search_feasibility_fts() must return a list (possibly empty)."""
        store = _make_imaging_store(tmp_path)
        results = store.search_feasibility_fts("solar energy")
        store.close()
        assert isinstance(results, list), (
            f"search_feasibility_fts() must return a list, got {type(results)}"
        )

    def test_search_returns_empty_for_empty_store(self, tmp_path):
        """search_feasibility_fts() must return [] when no data is indexed."""
        store = _make_imaging_store(tmp_path)
        results = store.search_feasibility_fts("solar wind regulation")
        store.close()
        assert results == [], (
            f"Expected empty list for empty store, got {results}"
        )

    def test_search_returns_item_id_in_results(self, tmp_path):
        """Each result from search_feasibility_fts() must include item_id."""
        store = _make_imaging_store(tmp_path)
        asset = _make_brownfield_asset(name="Kafue Solar", country="Zambia")
        saved = store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]
        store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="production",
            conclusion="viable",
            confidence="high",
            findings={
                "key_finding": "Kafue Gorge hydro system supports grid stability",
                "risks": [],
                "gaps": [],
                "sources": [],
            },
        )

        results = store.search_feasibility_fts("Kafue hydro grid")
        store.close()
        assert len(results) >= 1, (
            "search_feasibility_fts() returned no results for 'Kafue hydro grid' "
            "after indexing a feasibility result with those terms"
        )
        first = results[0]
        has_item_id = (
            (hasattr(first, "item_id") and first.item_id)
            or (isinstance(first, dict) and first.get("item_id"))
        )
        assert has_item_id, (
            f"Each search result must include item_id, got: {first}"
        )

    def test_search_ranks_more_relevant_result_higher(self, tmp_path):
        """BM25 ranking must place items with higher term frequency / specificity first.

        Item A mentions 'solar' 3 times; item B mentions it once.
        Item A must rank before B.
        """
        store = _make_imaging_store(tmp_path)

        asset_a = _make_brownfield_asset(name="Solar Site A", country="Zambia",
                                          technology="solar")
        saved_a = store.upsert_pipeline_asset("generation", asset_a)
        id_a = saved_a["id"]
        store.upsert_feasibility_result(
            item_id=id_a,
            item_type="brownfield",
            tab="production",
            conclusion="viable",
            confidence="high",
            findings={
                "key_finding": "Solar irradiance solar capacity solar output all excellent",
                "risks": [],
                "gaps": [],
                "sources": [],
            },
        )

        asset_b = _make_brownfield_asset(name="Wind Site B", country="Namibia",
                                          technology="wind")
        saved_b = store.upsert_pipeline_asset("generation", asset_b)
        id_b = saved_b["id"]
        store.upsert_feasibility_result(
            item_id=id_b,
            item_type="brownfield",
            tab="production",
            conclusion="viable",
            confidence="high",
            findings={
                "key_finding": "Wind is strong but solar access is limited",
                "risks": [],
                "gaps": [],
                "sources": [],
            },
        )

        results = store.search_feasibility_fts("solar", limit=10)
        store.close()
        assert len(results) >= 2, (
            f"Expected at least 2 results for 'solar', got {len(results)}"
        )
        # Extract item ids from results (support both dict and object)
        def get_item_id(r):
            return getattr(r, "item_id", None) or (r.get("item_id") if isinstance(r, dict) else None)

        first_id = get_item_id(results[0])
        assert first_id == id_a, (
            f"BM25 ranking must place item A (3x solar) before item B (1x solar). "
            f"Got first: {first_id!r}, expected {id_a!r}"
        )


# ===========================================================================
# 4. PORTER STEMMING — MORPHOLOGICAL VARIANT MATCHING
# ===========================================================================


class TestPorterStemming:
    """FTS5 with Porter stemming must match morphological variants that exact
    token overlap misses.
    """

    def test_regulation_matches_regulatory(self, tmp_path):
        """Searching for 'regulation' must match content containing 'regulatory'.

        This is the canonical stemming test from the SEP-065 requirement.
        The current token-overlap implementation CANNOT pass this test because
        'regulation' != 'regulatory' as tokens.
        """
        store = _make_imaging_store(tmp_path)
        asset = _make_brownfield_asset(name="Harare Grid Tie", country="Zimbabwe",
                                        technology="solar")
        saved = store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]
        store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="regulatory",
            conclusion="viable",
            confidence="high",
            findings={
                "key_finding": "The regulatory framework in Zimbabwe requires ZERA approval",
                "risks": ["Regulatory uncertainty"],
                "gaps": [],
                "sources": [],
            },
        )

        results = store.search_feasibility_fts("regulation")
        store.close()
        assert len(results) >= 1, (
            "Porter stemming must allow 'regulation' to match data containing 'regulatory'. "
            "This CANNOT be satisfied by the current token-overlap approach — "
            "the FTS5 implementation is required."
        )

    def test_regulatory_matches_regulation(self, tmp_path):
        """The inverse: searching 'regulatory' must match content containing 'regulation'."""
        store = _make_imaging_store(tmp_path)
        asset = _make_brownfield_asset(name="Lusaka Substation", country="Zambia",
                                        technology="transmission")
        saved = store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]
        store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="regulatory",
            conclusion="marginal",
            confidence="medium",
            findings={
                "key_finding": "New regulation under ERB complicates grid access permits",
                "risks": [],
                "gaps": [],
                "sources": [],
            },
        )

        results = store.search_feasibility_fts("regulatory")
        store.close()
        assert len(results) >= 1, (
            "Porter stemming must allow 'regulatory' to match data containing 'regulation'. "
            "This requires FTS5 with Porter tokenizer."
        )

    def test_invest_matches_investment(self, tmp_path):
        """Porter stemming must allow 'invest' to match 'investment'."""
        store = _make_imaging_store(tmp_path)
        asset = _make_brownfield_asset(name="Gaborone PV", country="Botswana",
                                        technology="solar")
        saved = store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]
        store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="financial",
            conclusion="viable",
            confidence="high",
            findings={
                "key_finding": "Total investment cost is USD 45M with 15% IRR",
                "risks": [],
                "gaps": [],
                "sources": [],
            },
        )

        results = store.search_feasibility_fts("invest")
        store.close()
        assert len(results) >= 1, (
            "Porter stemming must allow 'invest' to match content with 'investment'. "
            "This requires FTS5 with Porter tokenizer."
        )

    def test_connect_matches_connection(self, tmp_path):
        """Porter stemming must allow 'connect' to match 'connection'."""
        store = _make_imaging_store(tmp_path)
        asset = _make_brownfield_asset(name="Windhoek Wind", country="Namibia",
                                        technology="wind")
        saved = store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]
        store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="grid",
            conclusion="viable",
            confidence="medium",
            findings={
                "key_finding": "Grid connection requires 50km line extension to NamPower",
                "risks": [],
                "gaps": [],
                "sources": [],
            },
        )

        results = store.search_feasibility_fts("connect")
        store.close()
        assert len(results) >= 1, (
            "Porter stemming must allow 'connect' to match 'connection'. "
            "This requires FTS5 with Porter tokenizer."
        )

    def test_no_cross_stem_false_positives(self, tmp_path):
        """Stemming must not cause completely unrelated terms to match.

        'banana' must not match content about 'solar energy'.
        """
        store = _make_imaging_store(tmp_path)
        asset = _make_brownfield_asset(name="Solar Farm X", country="Zambia")
        saved = store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]
        store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="production",
            conclusion="viable",
            confidence="high",
            findings={
                "key_finding": "Solar irradiance is excellent in this region",
                "risks": [],
                "gaps": [],
                "sources": [],
            },
        )

        results = store.search_feasibility_fts("banana cryptocurrency")
        store.close()
        assert results == [], (
            f"Completely unrelated query 'banana cryptocurrency' must not match solar energy content, "
            f"got {results}"
        )


# ===========================================================================
# 5. NON-MATCHING QUERIES RETURN EMPTY
# ===========================================================================


class TestFts5NonMatchingQueries:
    """FTS5 search must return empty results when there is no relevant data."""

    def test_empty_query_string_returns_empty(self, tmp_path):
        """Empty or whitespace query must return empty list without raising."""
        store = _make_imaging_store(tmp_path)
        asset = _make_brownfield_asset(name="Kafue Solar", country="Zambia")
        saved = store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]
        store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="production",
            conclusion="viable",
            confidence="high",
            findings={"key_finding": "Great solar site", "risks": [], "gaps": [], "sources": []},
        )

        try:
            results = store.search_feasibility_fts("")
        except Exception as exc:
            pytest.fail(f"Empty query must not raise, got: {exc}")
        assert isinstance(results, list), (
            f"Empty query must return a list, got {type(results)}"
        )

    def test_query_with_no_vocabulary_overlap_returns_empty(self, tmp_path):
        """A query with vocabulary utterly absent from indexed content returns []."""
        store = _make_imaging_store(tmp_path)
        asset = _make_brownfield_asset(name="Lusaka Hydro", country="Zambia",
                                        technology="hydro")
        saved = store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]
        store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="production",
            conclusion="viable",
            confidence="high",
            findings={
                "key_finding": "Hydro resource assessment confirms viable flow rates",
                "risks": [],
                "gaps": [],
                "sources": [],
            },
        )

        results = store.search_feasibility_fts("cryptocurrency SEC enforcement NYSE")
        store.close()
        assert results == [], (
            "FTS5 search for completely unrelated terms must return empty list"
        )


# ===========================================================================
# 6. scouting_knowledge_sources() USES FTS5 PATH
# ===========================================================================


class TestScoutingKnowledgeSourcesFts5:
    """scouting_knowledge_sources() must use the FTS5 path, not token overlap."""

    def test_scouting_knowledge_sources_uses_fts_when_available(self, tmp_path):
        """scouting_knowledge_sources() must return results via FTS5 for a
        Porter-stemmable query.

        The asset name, technology, country are chosen so they share ZERO exact
        tokens with the query. The only path to a match is Porter stemming:
        query='permitting' matches stored word 'permits' via stemming.

        The old token-overlap logic cannot match 'permitting' against 'permits'
        because they are different tokens. This test distinguishes FTS5 from
        token overlap definitively.

        Token overlap proof:
          query_tokens = {'permitting', 'grid', 'interconnection'}
          haystack_tokens includes: {'alpha', 'substation', 'transmission',
            'botswana', 'eskom', 'issued', 'connection', 'permits', 'viable',
            'regulatory'}
          intersection after len>3 filter = {} (empty)
          → old logic returns []
        """
        from workflows.deep_research.aggregator import scouting_knowledge_sources

        imaging_store = _make_imaging_store(tmp_path)
        asset = _make_brownfield_asset(
            name="Alpha Substation",
            country="Botswana",
            technology="transmission",
        )
        saved = imaging_store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]
        imaging_store.update_scouting_stage("brownfield", item_id, "feasibility")
        imaging_store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="regulatory",
            conclusion="viable",
            confidence="high",
            findings={
                # 'permits' is the only relevant word; query uses 'permitting'
                # Token overlap: 'permitting' != 'permits' → no match
                # Porter stem: both stem to 'permit' → FTS5 matches
                "key_finding": "Eskom issued connection permits for the substation",
                "risks": [],
                "gaps": [],
                "sources": [],
            },
        )

        results = scouting_knowledge_sources(
            query="permitting grid interconnection",
            imaging_store=imaging_store,
        )
        imaging_store.close()

        assert len(results) > 0, (
            "scouting_knowledge_sources() must return results when query='permitting' "
            "and data contains 'permits' — both stem to 'permit' under Porter stemming. "
            "Token overlap CANNOT satisfy this: 'permitting' != 'permits'. "
            "The FTS5 implementation is required."
        )

    def test_scouting_knowledge_sources_returns_internal_type_via_fts(self, tmp_path):
        """scouting_knowledge_sources() must return source_type='internal' via FTS5.

        Asset name/technology/country share zero exact tokens with the query.
        The match is solely through Porter stemming:
        query='invested' matches stored 'investment' (both stem to 'invest').

        Token overlap proof:
          query_tokens = {'invested', 'outlay', 'financing'}
          haystack_tokens includes: {'beta', 'station', 'geothermal', 'ethiopia',
            'total', 'investment', 'committed', 'viable', 'financial'}
          intersection after len>3 filter = {} (empty)
          → old logic returns []
        """
        from workflows.deep_research.aggregator import scouting_knowledge_sources

        imaging_store = _make_imaging_store(tmp_path)
        asset = _make_brownfield_asset(
            name="Beta Station",
            country="Ethiopia",
            technology="geothermal",
        )
        saved = imaging_store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]
        imaging_store.update_scouting_stage("brownfield", item_id, "diligence")
        imaging_store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="financial",
            conclusion="viable",
            confidence="high",
            findings={
                # query has 'invested'; findings have 'investment'
                # No shared tokens between query and findings/name/tech/country
                # Porter: 'invested' and 'investment' both stem to 'invest'
                "key_finding": "Total investment of USD 80M committed by the DFI",
                "risks": [],
                "gaps": [],
                "sources": [],
            },
        )

        results = scouting_knowledge_sources(
            query="invested outlay financing",
            imaging_store=imaging_store,
        )
        imaging_store.close()

        assert len(results) > 0, (
            "scouting_knowledge_sources() via FTS5 must match 'invested' to 'investment'. "
            "Token overlap cannot do this: 'invested' != 'investment'. "
            "FTS5 Porter stemming is required."
        )
        source_types = [
            getattr(s, "source_type", None) or (s.get("source_type") if isinstance(s, dict) else None)
            for s in results
        ]
        assert "internal" in source_types, (
            f"scouting_knowledge_sources() must return source_type='internal', got: {source_types}"
        )

    def test_scouting_knowledge_sources_bm25_prefers_more_relevant_result(self, tmp_path):
        """When two items match, BM25 ranking must return the more relevant one first.

        Item A: mentions 'regulatory' three times (high BM25 score for 'regulation').
        Item B: mentions 'regulatory' once.
        Query: 'regulation' (stems to same root as 'regulatory' under Porter).
        Neither asset name/technology/country overlaps with the query token 'regulation',
        so the old token-overlap logic cannot produce either result. Only FTS5
        can match and rank both.
        """
        from workflows.deep_research.aggregator import scouting_knowledge_sources

        imaging_store = _make_imaging_store(tmp_path)

        # Item A: high frequency of 'regulatory' — high BM25 score for query 'regulation'
        asset_a = _make_brownfield_asset(
            name="Gamma Station",
            country="Tanzania",
            technology="geothermal",
        )
        saved_a = imaging_store.upsert_pipeline_asset("generation", asset_a)
        id_a = saved_a["id"]
        imaging_store.update_scouting_stage("brownfield", id_a, "feasibility")
        imaging_store.upsert_feasibility_result(
            item_id=id_a,
            item_type="brownfield",
            tab="regulatory",
            conclusion="viable",
            confidence="high",
            findings={
                "key_finding": "Regulatory approval regulatory permits regulatory compliance all secured",
                "risks": [],
                "gaps": [],
                "sources": [],
            },
        )

        # Item B: low frequency of 'regulatory' — lower BM25 score
        asset_b = _make_brownfield_asset(
            name="Delta Station",
            country="Kenya",
            technology="geothermal",
        )
        saved_b = imaging_store.upsert_pipeline_asset("generation", asset_b)
        id_b = saved_b["id"]
        imaging_store.update_scouting_stage("brownfield", id_b, "feasibility")
        imaging_store.upsert_feasibility_result(
            item_id=id_b,
            item_type="brownfield",
            tab="financial",
            conclusion="viable",
            confidence="high",
            findings={
                "key_finding": "IRR is 18% subject to one regulatory condition",
                "risks": [],
                "gaps": [],
                "sources": [],
            },
        )

        # Query: 'regulation' — stems to same root as 'regulatory' under Porter
        # Token overlap: 'regulation' != 'regulatory' → old logic returns [] for both
        # FTS5 Porter: both match, A ranks higher due to frequency
        results = scouting_knowledge_sources(
            query="regulation approval",
            imaging_store=imaging_store,
        )
        imaging_store.close()

        assert len(results) >= 2, (
            f"Expected at least 2 results for 'regulation approval' (both items have 'regulatory'), "
            f"got {len(results)}. This requires FTS5 with Porter stemming."
        )
        first_url = getattr(results[0], "url", None) or (
            results[0].get("url") if isinstance(results[0], dict) else None
        )
        assert id_a in first_url, (
            f"BM25 must rank item A (3x regulatory) before item B (1x regulatory) "
            f"for query 'regulation'. First result URL was: {first_url!r}, expected to contain {id_a!r}"
        )

    def test_scouting_knowledge_sources_no_fts_match_returns_empty(self, tmp_path):
        """scouting_knowledge_sources() must return [] when FTS5 finds no match.

        The FTS5 path must not fall back to returning all items — it must
        return only results that actually match.

        This is verified by checking the search_feasibility_fts() method exists
        (FTS5 path) AND that a truly unrelated query produces no results.
        """
        from workflows.deep_research.aggregator import scouting_knowledge_sources

        # Confirm search_feasibility_fts exists (FTS5 path is in place)
        imaging_store = _make_imaging_store(tmp_path)
        assert hasattr(imaging_store, "search_feasibility_fts"), (
            "ImagingDataStore.search_feasibility_fts must exist — "
            "this confirms the FTS5 path is implemented"
        )

        asset = _make_brownfield_asset(name="Kafue Solar Farm", country="Zambia",
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
            findings={
                "key_finding": "Solar irradiance excellent in Kafue region",
                "risks": [],
                "gaps": [],
                "sources": [],
            },
        )

        results = scouting_knowledge_sources(
            query="cryptocurrency blockchain DeFi SEC enforcement",
            imaging_store=imaging_store,
        )
        imaging_store.close()
        assert results == [], (
            f"scouting_knowledge_sources() must return [] for completely unrelated query, "
            f"got {results}"
        )


# ===========================================================================
# 7. INCREMENTAL FTS INDEXING ON UPSERT
# ===========================================================================


class TestIncrementalFtsIndexing:
    """upsert_feasibility_result() must maintain the FTS index incrementally —
    new rows must be immediately searchable without calling rebuild_fts_index().
    """

    def test_new_feasibility_result_immediately_searchable(self, tmp_path):
        """After upsert_feasibility_result(), the result must be findable via
        search_feasibility_fts() without an explicit rebuild.
        """
        store = _make_imaging_store(tmp_path)
        asset = _make_brownfield_asset(name="Maamba Coal-to-Gas", country="Zambia",
                                        technology="gas")
        saved = store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]

        # Upsert — must trigger incremental FTS update
        store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="environmental",
            conclusion="marginal",
            confidence="low",
            findings={
                "key_finding": "Environmental impact assessment pending for gas conversion",
                "risks": ["Emissions"],
                "gaps": [],
                "sources": [],
            },
        )

        # Must be findable immediately — no rebuild needed
        results = store.search_feasibility_fts("environmental impact assessment")
        store.close()
        assert len(results) >= 1, (
            "After upsert_feasibility_result(), the result must be immediately searchable "
            "via FTS5 without calling rebuild_fts_index(). "
            "This requires either an AFTER INSERT trigger on feasibility_results "
            "or explicit FTS indexing inside upsert_feasibility_result()."
        )

    def test_updated_feasibility_result_updates_fts_index(self, tmp_path):
        """When upsert_feasibility_result() updates an existing row, the FTS
        index must reflect the new content.
        """
        store = _make_imaging_store(tmp_path)
        asset = _make_brownfield_asset(name="Ndola Substation", country="Zambia",
                                        technology="transmission")
        saved = store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]

        # First upsert: mentions 'hydrology'
        store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="environmental",
            conclusion="viable",
            confidence="high",
            findings={
                "key_finding": "Hydrology studies show minimal flood risk",
                "risks": [],
                "gaps": [],
                "sources": [],
            },
        )

        # Second upsert (update): replaces with text about 'seismic'
        store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="environmental",
            conclusion="viable",
            confidence="high",
            findings={
                "key_finding": "Seismic assessment completed with no risks identified",
                "risks": [],
                "gaps": [],
                "sources": [],
            },
        )

        # Must find with new term, not old term
        new_results = store.search_feasibility_fts("seismic")
        old_results = store.search_feasibility_fts("hydrology")
        store.close()

        assert len(new_results) >= 1, (
            "After updating a feasibility result, the new content ('seismic') "
            "must be findable via FTS5"
        )
        assert len(old_results) == 0, (
            "After updating a feasibility result, the old content ('hydrology') "
            "must no longer appear in FTS5 results"
        )

    def test_multiple_tabs_all_indexed_independently(self, tmp_path):
        """Multiple feasibility tabs for the same item must all be indexed,
        and their content must be independently searchable.
        """
        store = _make_imaging_store(tmp_path)
        asset = _make_brownfield_asset(name="Johannesburg Solar", country="South Africa",
                                        technology="solar")
        saved = store.upsert_pipeline_asset("generation", asset)
        item_id = saved["id"]

        store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="production",
            conclusion="viable",
            confidence="high",
            findings={"key_finding": "Excellent photovoltaic output", "risks": [], "gaps": [], "sources": []},
        )
        store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="grid",
            conclusion="marginal",
            confidence="medium",
            findings={"key_finding": "Eskom interconnection requires upgrade", "risks": [], "gaps": [], "sources": []},
        )
        store.upsert_feasibility_result(
            item_id=item_id,
            item_type="brownfield",
            tab="financial",
            conclusion="viable",
            confidence="high",
            findings={"key_finding": "IRR of 17% attractive to DFI investors", "risks": [], "gaps": [], "sources": []},
        )

        # Each tab's unique term should be independently findable
        r1 = store.search_feasibility_fts("photovoltaic")
        r2 = store.search_feasibility_fts("interconnection Eskom")
        r3 = store.search_feasibility_fts("DFI investors")
        store.close()

        assert len(r1) >= 1, "Tab 'production' content ('photovoltaic') must be indexed"
        assert len(r2) >= 1, "Tab 'grid' content ('interconnection Eskom') must be indexed"
        assert len(r3) >= 1, "Tab 'financial' content ('DFI investors') must be indexed"


# ===========================================================================
# 8. FALLBACK WHEN FTS TABLE IS ABSENT
# ===========================================================================


class TestFts5FallbackBehavior:
    """When the FTS5 table is not available (e.g., legacy DB without migration),
    scouting_knowledge_sources() must not crash — it must either fall back
    gracefully or return an empty list.
    """

    def test_scouting_knowledge_sources_survives_missing_fts_table(self, tmp_path):
        """If the FTS5 table is dropped manually (simulating a legacy DB),
        scouting_knowledge_sources() must not raise an unhandled exception.

        It must return a list. This tests the graceful degradation contract:
        the FTS-dependent path must be guarded so that a missing table
        causes a fallback, not a crash.

        We verify this requires the FTS5 path to be implemented in the first
        place by asserting search_feasibility_fts() exists before dropping the table.
        """
        from workflows.deep_research.aggregator import scouting_knowledge_sources

        imaging_store = _make_imaging_store(tmp_path)

        # Verify FTS5 is implemented (method must exist)
        assert hasattr(imaging_store, "search_feasibility_fts"), (
            "ImagingDataStore.search_feasibility_fts must exist — "
            "SEP-065 must be implemented before fallback can be tested"
        )

        # Seed data with a matching query
        asset = _make_brownfield_asset(name="Harare Solar BESS", country="Zimbabwe",
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
            findings={
                "key_finding": "Solar BESS hybrid viable in Harare",
                "risks": [],
                "gaps": [],
                "sources": [],
            },
        )

        # Simulate legacy DB: drop the FTS5 table
        try:
            imaging_store.conn.execute("DROP TABLE IF EXISTS feasibility_fts")
            imaging_store.conn.commit()
        except Exception:
            pass

        # Must not raise after FTS table is gone
        try:
            results = scouting_knowledge_sources(
                query="solar battery zimbabwe harare",
                imaging_store=imaging_store,
            )
        except Exception as exc:
            imaging_store.close()
            pytest.fail(
                f"scouting_knowledge_sources() must not raise when FTS table is missing. "
                f"Got: {type(exc).__name__}: {exc}"
            )

        imaging_store.close()
        assert isinstance(results, list), (
            f"scouting_knowledge_sources() must return a list even when FTS table is absent, "
            f"got {type(results)}"
        )

    def test_search_feasibility_fts_returns_empty_not_error_on_missing_table(self, tmp_path):
        """search_feasibility_fts() must handle a missing FTS table gracefully.

        If the FTS table is dropped, search_feasibility_fts() must return []
        rather than propagating a sqlite3.OperationalError.
        """
        store = _make_imaging_store(tmp_path)

        # Verify FTS5 is implemented (method must exist before we can drop the table)
        assert hasattr(store, "search_feasibility_fts"), (
            "ImagingDataStore.search_feasibility_fts must exist — "
            "this test requires SEP-065 to be implemented"
        )

        # Drop the FTS table to simulate pre-migration DB
        try:
            store.conn.execute("DROP TABLE IF EXISTS feasibility_fts")
            store.conn.commit()
        except Exception:
            pass

        try:
            results = store.search_feasibility_fts("solar energy")
        except Exception as exc:
            store.close()
            pytest.fail(
                f"search_feasibility_fts() must return [] when FTS table is missing, "
                f"not raise: {type(exc).__name__}: {exc}"
            )

        store.close()
        assert isinstance(results, list), (
            "search_feasibility_fts() must return a list even on missing FTS table"
        )
