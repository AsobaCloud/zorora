"""Tests for SEP-046: BESS Scoring, Diligence Domains, and Synthesis.

These tests verify BESS intelligence from the investor's perspective:
- Can I identify which locations in SA are best for BESS?
- Does the system correctly use real market data (SAPP DAM, Eskom tariffs)?
- Does BESS diligence ask storage-specific questions, not solar/wind ones?
- Can I get charts showing actual price data for investment decisions?
"""

from __future__ import annotations

import base64
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ---------------------------------------------------------------------------
# User Story: "I want to compare BESS viability across SA locations"
# ---------------------------------------------------------------------------

class TestBessLocationComparison:
    """An investor comparing Gauteng vs Cape Town vs ocean for BESS siting
    should get meaningfully different scores driven by real market data."""

    def test_gauteng_scores_higher_than_cape_town(self):
        """Gauteng (RSAN, high demand, near substations) should score higher
        than Cape Town (RSAS, lower demand) for BESS."""
        from tools.imaging.site_score import score_bess_site

        gauteng = score_bess_site(lat=-26.0, lon=28.0, country="South Africa")
        cape_town = score_bess_site(lat=-34.0, lon=18.5, country="South Africa")
        assert gauteng["overall_score"] > cape_town["overall_score"], (
            f"Gauteng ({gauteng['overall_score']}) should score higher than "
            f"Cape Town ({cape_town['overall_score']}) for BESS"
        )

    def test_onshore_scores_higher_than_ocean(self):
        """Any SA onshore point should score higher than middle of ocean."""
        from tools.imaging.site_score import score_bess_site

        onshore = score_bess_site(lat=-26.0, lon=28.0, country="South Africa")
        ocean = score_bess_site(lat=-35.0, lon=10.0, country="South Africa")
        assert onshore["overall_score"] > ocean["overall_score"], (
            f"Onshore ({onshore['overall_score']}) should beat "
            f"ocean ({ocean['overall_score']})"
        )

    def test_score_reflects_real_dam_arbitrage_spread(self):
        """The arbitrage spread factor should contain the actual SAPP DAM
        peak-offpeak differential, not a placeholder."""
        from tools.imaging.site_score import score_bess_site

        result = score_bess_site(lat=-26.0, lon=28.0, country="South Africa")
        arb = next(f for f in result["factors"] if f["key"] == "arbitrage_spread")
        assert arb["status"] == "known"
        # SAPP DAM data has real prices — spread must be positive and non-trivial
        assert arb["value"] > 0, "Spread should be positive (peak > offpeak)"
        assert arb["value"] < 100, f"Spread {arb['value']} USD/MWh seems unrealistic"
        assert arb["unit"] == "USD/MWh"

    def test_score_reflects_real_eskom_tou_differential(self):
        """The TOU spread should reflect actual Eskom Megaflex tariff data:
        HD Peak 684.59 minus HD Off-Peak 114.09 = 570.50 c/kWh."""
        from tools.imaging.site_score import score_bess_site

        result = score_bess_site(lat=-26.0, lon=28.0, country="South Africa")
        tou = next(f for f in result["factors"] if f["key"] == "tou_spread")
        assert tou["status"] == "known"
        # The actual Megaflex spread is 570.50 c/kWh — allow for different
        # tariff types but it must be substantial (>400)
        assert tou["value"] > 400, f"TOU spread {tou['value']} c/kWh too low for Eskom tariffs"
        assert tou["unit"] == "c/kWh"

    def test_grid_proximity_distinguishes_near_vs_far(self):
        """A point near Johannesburg substations should score higher on
        grid proximity than a point in the middle of the ocean."""
        from tools.imaging.site_score import score_bess_site

        near = score_bess_site(lat=-26.2, lon=28.0, country="South Africa")
        far = score_bess_site(lat=-35.0, lon=10.0, country="South Africa")
        grid_near = next(f for f in near["factors"] if f["key"] == "grid_proximity")
        grid_far = next(f for f in far["factors"] if f["key"] == "grid_proximity")
        assert grid_near["score"] > grid_far["score"]

    def test_demand_level_higher_in_rsan(self):
        """RSAN (northern grid, Gauteng industrial load) should have higher
        demand score than RSAS (southern grid)."""
        from tools.imaging.site_score import score_bess_site

        rsan = score_bess_site(lat=-26.0, lon=28.0, country="South Africa")
        rsas = score_bess_site(lat=-34.0, lon=18.5, country="South Africa")
        d_rsan = next(f for f in rsan["factors"] if f["key"] == "demand_level")
        d_rsas = next(f for f in rsas["factors"] if f["key"] == "demand_level")
        assert d_rsan["score"] > d_rsas["score"]


# ---------------------------------------------------------------------------
# User Story: "BESS diligence should ask storage questions, not solar ones"
# ---------------------------------------------------------------------------

class TestBessDiligenceIsStorageSpecific:
    """When running diligence on a BESS asset, the system should search for
    storage-specific information — not PPAs, capacity factors, or offtakers
    that only apply to generation assets."""

    def test_bess_queries_mention_battery_or_storage(self):
        """Every BESS diligence query should contain battery/storage keywords,
        not generation-specific terms like 'capacity factor' or 'PPA'."""
        from engine.query_refiner import decompose_bess_diligence_query

        intents = decompose_bess_diligence_query(
            "BESS opportunity",
            {"name": "Apollo BESS", "technology": "Storage",
             "country": "South Africa", "capacity_mw": 100, "operator": "TestCo"},
        )
        all_queries = " ".join(i.intent_query.lower() for i in intents)
        assert "battery" in all_queries or "storage" in all_queries or "bess" in all_queries
        # Should NOT contain brownfield-specific terms
        assert "capacity factor" not in all_queries, "BESS queries shouldn't mention capacity factor"
        assert "feed-in tariff" not in all_queries, "BESS queries shouldn't mention feed-in tariff"

    def test_bess_and_brownfield_ask_different_questions(self):
        """BESS diligence domains must be entirely different from brownfield
        domains — they represent different investment due diligence frameworks."""
        from engine.query_refiner import decompose_bess_diligence_query, decompose_diligence_query

        bess = decompose_bess_diligence_query(
            "test", {"name": "T", "technology": "Storage",
                     "country": "South Africa", "capacity_mw": 50, "operator": ""},
        )
        brownfield = decompose_diligence_query(
            "test", {"name": "T", "technology": "Solar",
                     "country": "South Africa", "capacity_mw": 50, "operator": ""},
        )
        bess_domains = {i.domain for i in bess}
        brownfield_domains = {i.domain for i in brownfield}
        overlap = bess_domains & brownfield_domains
        assert len(overlap) == 0, (
            f"BESS and brownfield domains should not overlap, but share: {overlap}"
        )

    def test_country_appears_in_all_queries(self):
        """Diligence queries must be jurisdiction-specific — a Zimbabwe BESS
        project should produce queries mentioning Zimbabwe."""
        from engine.query_refiner import decompose_bess_diligence_query

        intents = decompose_bess_diligence_query(
            "BESS assessment",
            {"name": "T", "technology": "Storage", "country": "Zimbabwe",
             "capacity_mw": 20, "operator": ""},
        )
        for intent in intents:
            assert "zimbabwe" in intent.intent_query.lower(), (
                f"Domain '{intent.domain}' query should mention Zimbabwe"
            )

    def test_six_distinct_domains(self):
        """BESS diligence should cover 6 distinct analytical domains
        with 6 distinct search queries."""
        from engine.query_refiner import decompose_bess_diligence_query

        intents = decompose_bess_diligence_query(
            "BESS diligence",
            {"name": "T", "technology": "Storage", "country": "South Africa",
             "capacity_mw": 50, "operator": ""},
        )
        assert len(intents) == 6
        assert len({i.domain for i in intents}) == 6, "All domains should be distinct"
        assert len({i.intent_query for i in intents}) == 6, "All queries should be distinct"


# ---------------------------------------------------------------------------
# User Story: "I need charts showing real price data for my investment memo"
# ---------------------------------------------------------------------------

class TestBessChartsUseRealData:
    """Charts must contain actual rendered data from SAPP DAM prices and
    Eskom tariff schedules — not placeholder images."""

    def test_three_charts_with_real_content(self):
        """Should produce exactly 3 charts, each with enough rendered content
        to contain axes, labels, and data (>5KB PNG, not blank ~200 bytes)."""
        from workflows.deep_research.synthesizer import generate_bess_diligence_charts

        charts = generate_bess_diligence_charts(
            {"name": "Apollo BESS", "technology": "Storage",
             "country": "South Africa", "capacity_mw": 100},
            {},
        )
        assert len(charts) == 3, f"Expected 3 charts, got {len(charts)}"
        for title, data_uri in charts:
            assert data_uri.startswith("data:image/png;base64,")
            png_bytes = base64.b64decode(data_uri.split(",", 1)[1])
            assert len(png_bytes) > 5000, (
                f"Chart '{title}' is only {len(png_bytes)} bytes — "
                f"likely blank or trivial, not real data"
            )

    def test_dam_price_chart_exists(self):
        """Must include a DAM price profile chart for arbitrage analysis."""
        from workflows.deep_research.synthesizer import generate_bess_diligence_charts

        charts = generate_bess_diligence_charts(
            {"name": "T", "technology": "Storage",
             "country": "South Africa", "capacity_mw": 50},
            {},
        )
        titles = [t.lower() for t, _ in charts]
        assert any("price" in t or "dam" in t for t in titles), (
            f"No DAM price chart found. Titles: {titles}"
        )

    def test_tariff_chart_exists(self):
        """Must include an Eskom tariff chart for TOU arbitrage analysis."""
        from workflows.deep_research.synthesizer import generate_bess_diligence_charts

        charts = generate_bess_diligence_charts(
            {"name": "T", "technology": "Storage",
             "country": "South Africa", "capacity_mw": 50},
            {},
        )
        titles = [t.lower() for t, _ in charts]
        assert any("tariff" in t for t in titles), (
            f"No tariff chart found. Titles: {titles}"
        )


# ---------------------------------------------------------------------------
# User Story: "BESS reports should pass quality checks with storage sections"
# ---------------------------------------------------------------------------

class TestBessReportQuality:
    """The quality gate must accept reports structured around BESS domains
    (Revenue Model, Grid Connection, etc.) — not reject them because they
    don't contain brownfield section titles."""

    def test_quality_gate_accepts_bess_report(self):
        from workflows.deep_research.synthesizer import _passes_diligence_quality_gate

        text = """## Executive Summary
This BESS opportunity shows strong arbitrage potential [SAPP Market Report].

## Revenue Model
The DAM arbitrage spread is favorable at 10.2 USD/MWh [SAPP Market Report].

## Grid Connection
Nearest MTS substation is Apollo at 15km [GCCA Grid Assessment].

## Tariff & Charging Cost
Megaflex TOU spread of 570 c/kWh under high demand season [SAPP Market Report].

## Regulatory & Licensing
NERSA licensing for battery storage is required [GCCA Grid Assessment].

## Market Structure
SAPP DAM trading is the primary revenue mechanism [SAPP Market Report].

## Risk Assessment
Key risks include ZAR/USD volatility and tariff escalation [GCCA Grid Assessment].

## Risk Summary & Recommendation
Proceed with feasibility study [SAPP Market Report][GCCA Grid Assessment].
"""

        class FakeState:
            sources_checked = [
                type("S", (), {"url": "http://sapp.co.zw/report", "title": "SAPP Market Report"})(),
                type("S", (), {"url": "http://ntcsa.co.za/gcca", "title": "GCCA Grid Assessment"})(),
            ]

        result = _passes_diligence_quality_gate(text, FakeState())
        assert result is True, "Quality gate should accept BESS section titles"


# ---------------------------------------------------------------------------
# Synthesis config: BESS analyst persona and section mapping
# ---------------------------------------------------------------------------

class TestBessSynthesisConfig:
    """The synthesis pipeline must have BESS-specific domain mappings and
    an analyst persona that understands storage economics."""

    def test_bess_analyst_understands_storage(self):
        from workflows.deep_research.synthesizer import _BESS_ANALYST_SYSTEM_PROMPT

        prompt_lower = _BESS_ANALYST_SYSTEM_PROMPT.lower()
        assert "storage" in prompt_lower or "battery" in prompt_lower, (
            "BESS analyst prompt should mention storage or battery"
        )
        assert "arbitrage" in prompt_lower or "dispatch" in prompt_lower or "revenue" in prompt_lower, (
            "BESS analyst prompt should mention arbitrage, dispatch, or revenue"
        )

    def test_every_bess_domain_has_section_title_and_question(self):
        """Each BESS diligence domain must map to both a section title
        (for report structure) and an analytical question (for LLM prompting)."""
        from workflows.deep_research.synthesizer import (
            _BESS_DOMAIN_SECTIONS, _BESS_SECTION_QUESTIONS,
        )

        assert set(_BESS_DOMAIN_SECTIONS.keys()) == set(_BESS_SECTION_QUESTIONS.keys()), (
            "Domain sections and questions must cover the same domain keys"
        )
