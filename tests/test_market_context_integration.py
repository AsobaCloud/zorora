"""Tests for market context integration in deep research synthesis."""

import unittest
from unittest.mock import patch, MagicMock


class TestMarketContextImportAndBuild(unittest.TestCase):
    def test_tools_market_exports_clients(self):
        """tools.market package should expose fred_client and yfinance_client modules."""
        import tools.market as market_pkg

        self.assertTrue(hasattr(market_pkg, "fred_client"))
        self.assertTrue(hasattr(market_pkg, "yfinance_client"))

    @patch("workflows.deep_research.synthesizer.synthesize_outline")
    @patch("workflows.deep_research.synthesizer.synthesize_section")
    @patch("workflows.market_workflow.MarketWorkflow")
    @patch("tools.market.context.build_market_context")
    @patch("engine.query_refiner.detect_market_intent", return_value=True)
    def test_synthesize_injects_market_context_when_market_intent(
        self,
        _mock_intent,
        mock_build_context,
        mock_market_workflow_cls,
        mock_synth_section,
        mock_outline,
    ):
        """Market context should be built and passed into section synthesis for market intent."""
        from engine.models import ResearchState, Finding
        from workflows.deep_research.synthesizer import synthesize, OutlineResult, OutlineSection

        wf = MagicMock()
        wf.compute_summary.return_value = {"DGS10": {"current": 4.2}}
        mock_market_workflow_cls.return_value = wf
        mock_build_context.return_value = "[Market Data Context]"

        mock_outline.return_value = OutlineResult(
            executive_summary="Summary [Source A]",
            sections=[OutlineSection(title="Drivers", bullets=["pricing"])],
            is_comparison=False,
            subjects=None,
        )
        mock_synth_section.return_value = "Prices rose amid tighter LNG balances [Source A]."

        state = ResearchState(original_query="energy market price and regulation impacts")
        src = MagicMock()
        src.source_id = "s1"
        src.title = "Source A"
        src.relevance_score = 0.7
        src.credibility_score = 0.7
        src.content_snippet = "Snippet"
        src.content_full = ""
        state.sources_checked = [src]
        state.findings = [
            Finding(
                claim="Prices rose amid tighter LNG balances.",
                sources=["s1"],
                confidence="high",
                average_credibility=0.7,
            )
        ]
        state.total_sources = 1

        _ = synthesize(state)

        self.assertTrue(mock_build_context.called)
        self.assertTrue(mock_synth_section.called)
        passed_market_context = mock_synth_section.call_args.kwargs.get("market_context", "")
        self.assertIn("[Market Data Context]", passed_market_context)


if __name__ == "__main__":
    unittest.main()
