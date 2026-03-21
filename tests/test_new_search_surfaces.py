"""Tests for new search surfaces (SEP-031).

Covers: OpenAlex, Semantic Scholar, World Bank, Congress.gov, GovTrack,
Federal Register, SEC EDGAR — parsing, Source conversion, intent detection,
aggregator channel inclusion, and credibility baselines.
"""

import unittest
import importlib
from unittest.mock import patch, MagicMock

from engine.models import Source


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _mock_response(json_data, status_code=200):
    """Create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# OpenAlex raw parsing
# ---------------------------------------------------------------------------
class TestOpenAlexRaw(unittest.TestCase):
    SAMPLE_RESPONSE = {
        "results": [
            {
                "id": "https://openalex.org/W123",
                "title": "Solar Energy in Sub-Saharan Africa",
                "doi": "https://doi.org/10.1234/solar",
                "publication_date": "2023-06-15",
                "cited_by_count": 42,
                "authorships": [
                    {"author": {"display_name": "Jane Doe"}},
                    {"author": {"display_name": "John Smith"}},
                ],
                "abstract_inverted_index": {
                    "Solar": [0],
                    "energy": [1],
                    "is": [2],
                    "growing": [3],
                    "in": [4],
                    "Africa": [5],
                },
            }
        ]
    }

    def test_openalex_raw_parsing(self):
        academic_module = importlib.import_module("tools.research.academic_search")
        with patch.object(academic_module.requests, "get") as mock_get:
            mock_get.return_value = _mock_response(self.SAMPLE_RESPONSE)
            results = academic_module._openalex_search_raw("solar africa", max_results=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Solar Energy in Sub-Saharan Africa")
        self.assertIn("Solar energy is growing in Africa", results[0]["description"])
        self.assertEqual(results[0]["citation_count"], 42)
        self.assertEqual(results[0]["source"], "OpenAlex")

    def test_openalex_empty_abstract(self):
        academic_module = importlib.import_module("tools.research.academic_search")
        data = {"results": [{"id": "W1", "title": "Test", "abstract_inverted_index": None}]}
        with patch.object(academic_module.requests, "get") as mock_get:
            mock_get.return_value = _mock_response(data)
            results = academic_module._openalex_search_raw("test")

        self.assertEqual(len(results), 1)
        # Should not crash on None abstract

    def test_openalex_abstract_reconstruction(self):
        from tools.research.academic_search import _reconstruct_abstract

        inverted = {"Hello": [0], "world": [1], "foo": [3], "bar": [2]}
        self.assertEqual(_reconstruct_abstract(inverted), "Hello world bar foo")

    def test_openalex_empty_results(self):
        academic_module = importlib.import_module("tools.research.academic_search")
        with patch.object(academic_module.requests, "get") as mock_get:
            mock_get.return_value = _mock_response({"results": []})
            results = academic_module._openalex_search_raw("nonexistent")

        self.assertEqual(results, [])

    def test_openalex_uses_provider_sanitized_query(self):
        academic_module = importlib.import_module("tools.research.academic_search")
        query = "power prices | geography: Europe | focus on regulatory and policy shifts"
        with patch.object(academic_module.requests, "get") as mock_get:
            mock_get.return_value = _mock_response({"results": []})
            academic_module._openalex_search_raw(query, max_results=5)

        self.assertTrue(mock_get.called)
        params = mock_get.call_args.kwargs.get("params", {})
        sent_query = params.get("search", "")
        self.assertNotIn("|", sent_query)
        self.assertNotIn("geography:", sent_query.lower())
        self.assertNotIn("focus on", sent_query.lower())


# ---------------------------------------------------------------------------
# Semantic Scholar raw parsing
# ---------------------------------------------------------------------------
class TestSemanticScholarRaw(unittest.TestCase):
    SAMPLE_RESPONSE = {
        "data": [
            {
                "paperId": "abc123",
                "title": "Machine Learning for Climate",
                "url": "https://api.semanticscholar.org/graph/v1/paper/abc123",
                "year": 2024,
                "citationCount": 15,
                "abstract": "We study ML methods for climate prediction.",
                "authors": [{"name": "Alice"}, {"name": "Bob"}],
                "externalIds": {"DOI": "10.5678/ml-climate"},
            }
        ]
    }

    def test_semantic_scholar_raw_parsing(self):
        academic_module = importlib.import_module("tools.research.academic_search")
        with patch.object(academic_module.requests, "get") as mock_get:
            mock_get.return_value = _mock_response(self.SAMPLE_RESPONSE)
            academic_module._PROVIDER_COOLDOWN_UNTIL.clear()
            results = academic_module._semantic_scholar_search_raw("ML climate", max_results=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Machine Learning for Climate")
        self.assertEqual(results[0]["citation_count"], 15)
        self.assertEqual(results[0]["source"], "SemanticScholar")
        self.assertEqual(results[0]["doi"], "10.5678/ml-climate")

    def test_semantic_scholar_429_returns_empty(self):
        academic_module = importlib.import_module("tools.research.academic_search")
        resp = MagicMock()
        resp.status_code = 429
        resp.headers = {}
        resp.raise_for_status.side_effect = Exception("429 Too Many Requests")
        with patch.object(academic_module.requests, "get") as mock_get:
            mock_get.return_value = resp
            academic_module._PROVIDER_COOLDOWN_UNTIL.clear()
            results = academic_module._semantic_scholar_search_raw("test")

        self.assertEqual(results, [])
        self.assertEqual(mock_get.call_count, 1)

    def test_semantic_scholar_respects_retry_after_header(self):
        academic_module = importlib.import_module("tools.research.academic_search")
        throttled = MagicMock()
        throttled.status_code = 429
        throttled.headers = {"Retry-After": "0.5"}
        throttled.raise_for_status.side_effect = Exception("429 Too Many Requests")
        with patch.object(academic_module.requests, "get") as mock_get:
            mock_get.return_value = throttled
            academic_module._PROVIDER_COOLDOWN_UNTIL.clear()
            first = academic_module._semantic_scholar_search_raw("power price policy shipping", max_results=5)

        self.assertEqual(first, [])
        self.assertEqual(mock_get.call_count, 1)

        # Second call should short-circuit due provider cooldown window.
        second = academic_module._semantic_scholar_search_raw("power price policy shipping", max_results=5)
        self.assertEqual(second, [])
        self.assertEqual(mock_get.call_count, 1)


class TestProviderQuerySanitization(unittest.TestCase):
    def test_sanitize_provider_query_removes_refinement_artifacts(self):
        from tools.research.academic_search import _sanitize_provider_query

        raw = "eu power prices | geography: Europe | time period: 2025 | focus on regulatory and policy shifts"
        cleaned = _sanitize_provider_query(raw, provider="openalex")

        self.assertNotIn("|", cleaned)
        self.assertNotIn("geography:", cleaned.lower())
        self.assertNotIn("time period:", cleaned.lower())
        self.assertNotIn("focus on", cleaned.lower())


# ---------------------------------------------------------------------------
# World Bank raw parsing
# ---------------------------------------------------------------------------
class TestWorldBankRaw(unittest.TestCase):
    SAMPLE_RESPONSE = {
        "documents": {
            "doc1": {
                "display_title": "Africa Development Report 2023",
                "abstracts": "Economic growth trends in Sub-Saharan Africa.",
                "pdfurl": "https://documents.worldbank.org/doc1.pdf",
                "docdt": "2023-01-15",
                "count": "Kenya;Tanzania",
                "subtopic": "Economic Policy",
            },
            "facet": "not_a_doc",
        },
        "total": 1,
    }

    @patch("tools.research.worldbank_search.requests.get")
    def test_worldbank_raw_parsing(self, mock_get):
        mock_get.return_value = _mock_response(self.SAMPLE_RESPONSE)
        from tools.research.worldbank_search import _worldbank_document_search_raw

        results = _worldbank_document_search_raw("africa development")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Africa Development Report 2023")
        self.assertIn("Economic growth", results[0]["description"])

    @patch("tools.research.worldbank_search.requests.get")
    def test_worldbank_uses_provider_sanitized_query(self, mock_get):
        mock_get.return_value = _mock_response({"documents": {}, "total": 0})
        from tools.research.worldbank_search import _worldbank_document_search_raw

        _worldbank_document_search_raw(
            "power prices | geography: Europe | focus on regulatory shifts",
            max_results=5,
        )
        params = mock_get.call_args.kwargs.get("params", {})
        sent = params.get("qterm", "")
        self.assertNotIn("|", sent)
        self.assertNotIn("geography:", sent.lower())

    @patch("tools.research.worldbank_search.requests.get")
    def test_worldbank_sources_conversion(self, mock_get):
        mock_get.return_value = _mock_response(self.SAMPLE_RESPONSE)
        from tools.research.worldbank_search import worldbank_search_sources

        sources = worldbank_search_sources("africa development")
        self.assertIsInstance(sources, list)
        self.assertTrue(all(isinstance(s, Source) for s in sources))
        self.assertEqual(sources[0].source_type, "world_bank")

    @patch("tools.research.worldbank_search.requests.get")
    def test_worldbank_skips_facet_key(self, mock_get):
        mock_get.return_value = _mock_response(self.SAMPLE_RESPONSE)
        from tools.research.worldbank_search import _worldbank_document_search_raw

        results = _worldbank_document_search_raw("test")
        # "facet" key should be skipped (it's not a dict)
        self.assertEqual(len(results), 1)


# ---------------------------------------------------------------------------
# Policy search (Congress.gov, GovTrack, Federal Register)
# ---------------------------------------------------------------------------
class TestPolicySearchRaw(unittest.TestCase):
    CONGRESS_RESPONSE = {
        "bills": [
            {
                "number": "1234",
                "title": "Clean Energy Act",
                "type": "HR",
                "congress": 118,
                "latestAction": {"text": "Passed House", "actionDate": "2024-03-01"},
                "url": "https://api.congress.gov/v3/bill/118/hr/1234",
            }
        ]
    }

    GOVTRACK_RESPONSE = {
        "objects": [
            {
                "id": 5678,
                "title": "Federal Carbon Tax Act",
                "bill_type": "senate_bill",
                "congress": 118,
                "current_status": "introduced",
                "link": "https://www.govtrack.us/congress/bills/118/s5678",
                "introduced_date": "2024-02-15",
            }
        ]
    }

    FEDERAL_REGISTER_RESPONSE = {
        "results": [
            {
                "title": "EPA Clean Air Rule",
                "abstract": "New standards for emissions control.",
                "html_url": "https://www.federalregister.gov/d/2024-01234",
                "publication_date": "2024-01-20",
                "agencies": [{"name": "Environmental Protection Agency"}],
                "type": "Rule",
                "document_number": "2024-01234",
            }
        ]
    }

    @patch("tools.research.policy_search.requests.get")
    @patch("tools.research.policy_search.config.CONGRESS_GOV", {"enabled": True, "endpoint": "https://api.congress.gov/v3/bill", "timeout": 15, "api_key": "test-dummy-key"})
    def test_congress_raw_parsing(self, mock_get):
        mock_get.return_value = _mock_response(self.CONGRESS_RESPONSE)
        from tools.research.policy_search import _congress_gov_search_raw

        results = _congress_gov_search_raw("clean energy")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Clean Energy Act")
        self.assertEqual(results[0]["source"], "Congress.gov")

    @patch("tools.research.policy_search.requests.get")
    @patch("tools.research.policy_search.config.CONGRESS_GOV", {"enabled": True, "endpoint": "https://api.congress.gov/v3/bill", "timeout": 15, "api_key": "test-dummy-key"})
    def test_policy_queries_are_sanitized(self, mock_get):
        mock_get.return_value = _mock_response({"bills": []})
        from tools.research.policy_search import _congress_gov_search_raw

        _congress_gov_search_raw("clean energy | scope: policy | focus on emissions", max_results=5)
        params = mock_get.call_args.kwargs.get("params", {})
        sent = params.get("query", "")
        self.assertNotIn("|", sent)
        self.assertNotIn("scope:", sent.lower())

    @patch("tools.research.policy_search.requests.get")
    def test_govtrack_raw_parsing(self, mock_get):
        mock_get.return_value = _mock_response(self.GOVTRACK_RESPONSE)
        from tools.research.policy_search import _govtrack_search_raw

        results = _govtrack_search_raw("carbon tax")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Federal Carbon Tax Act")
        self.assertEqual(results[0]["source"], "GovTrack")

    @patch("tools.research.policy_search.requests.get")
    def test_federal_register_raw_parsing(self, mock_get):
        mock_get.return_value = _mock_response(self.FEDERAL_REGISTER_RESPONSE)
        from tools.research.policy_search import _federal_register_search_raw

        results = _federal_register_search_raw("EPA emissions")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "EPA Clean Air Rule")
        self.assertEqual(results[0]["source"], "FederalRegister")

    @patch("tools.research.policy_search.requests.get")
    def test_policy_sources_conversion(self, mock_get):
        # Return different data per call: congress, govtrack, federal register
        mock_get.side_effect = [
            _mock_response(self.CONGRESS_RESPONSE),
            _mock_response(self.GOVTRACK_RESPONSE),
            _mock_response(self.FEDERAL_REGISTER_RESPONSE),
        ]
        from tools.research.policy_search import policy_search_sources

        sources = policy_search_sources("clean energy regulation")
        self.assertIsInstance(sources, list)
        self.assertTrue(all(isinstance(s, Source) for s in sources))
        self.assertTrue(all(s.source_type == "policy" for s in sources))


# ---------------------------------------------------------------------------
# SEC EDGAR raw parsing
# ---------------------------------------------------------------------------
class TestSECEdgarRaw(unittest.TestCase):
    SAMPLE_RESPONSE = {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "file_description": "Annual Report",
                        "display_names": ["Tesla Inc"],
                        "ciks": ["1318605"],
                        "adsh": "0001318605-24-000001",
                        "root_forms": ["10-K"],
                        "period_of_report": "2023-12-31",
                        "file_date": "2024-02-15",
                    }
                }
            ]
        }
    }

    @patch("tools.research.sec_search.requests.get")
    def test_sec_raw_parsing(self, mock_get):
        mock_get.return_value = _mock_response(self.SAMPLE_RESPONSE)
        from tools.research.sec_search import _sec_edgar_search_raw

        results = _sec_edgar_search_raw("Tesla annual report")
        self.assertEqual(len(results), 1)
        self.assertIn("Tesla", results[0]["title"])
        self.assertEqual(results[0]["source"], "SEC_EDGAR")

    @patch("tools.research.sec_search.requests.get")
    def test_sec_query_is_sanitized(self, mock_get):
        mock_get.return_value = _mock_response({"hits": {"hits": []}})
        from tools.research.sec_search import _sec_edgar_search_raw

        _sec_edgar_search_raw("Tesla filing | scope: policy | focus on compliance")
        params = mock_get.call_args.kwargs.get("params", {})
        sent = params.get("q", "")
        self.assertNotIn("|", sent)
        self.assertNotIn("scope:", sent.lower())

    @patch("tools.research.sec_search.requests.get")
    def test_sec_sources_conversion(self, mock_get):
        mock_get.return_value = _mock_response(self.SAMPLE_RESPONSE)
        from tools.research.sec_search import sec_search_sources

        sources = sec_search_sources("Tesla 10-K")
        self.assertIsInstance(sources, list)
        self.assertTrue(all(isinstance(s, Source) for s in sources))
        self.assertEqual(sources[0].source_type, "sec_filing")


# ---------------------------------------------------------------------------
# Intent detection (keyword matching)
# ---------------------------------------------------------------------------
class TestIntentDetection(unittest.TestCase):
    def test_policy_keywords_detected(self):
        from workflows.deep_research.aggregator import _query_matches_keywords, POLICY_KEYWORDS

        self.assertTrue(_query_matches_keywords("federal regulation of emissions", POLICY_KEYWORDS))
        self.assertTrue(_query_matches_keywords("new legislation on tariffs", POLICY_KEYWORDS))
        self.assertFalse(_query_matches_keywords("solar panel efficiency", POLICY_KEYWORDS))

    def test_sec_keywords_detected(self):
        from workflows.deep_research.aggregator import _query_matches_keywords, SEC_KEYWORDS

        self.assertTrue(_query_matches_keywords("Tesla 10-K filing analysis", SEC_KEYWORDS))
        self.assertTrue(_query_matches_keywords("annual report revenue growth", SEC_KEYWORDS))
        self.assertFalse(_query_matches_keywords("photosynthesis in plants", SEC_KEYWORDS))

    def test_case_insensitive(self):
        from workflows.deep_research.aggregator import _query_matches_keywords, POLICY_KEYWORDS

        self.assertTrue(_query_matches_keywords("FEDERAL REGULATION", POLICY_KEYWORDS))


# ---------------------------------------------------------------------------
# Aggregator channel inclusion
# ---------------------------------------------------------------------------
class TestAggregatorChannels(unittest.TestCase):
    @patch("workflows.deep_research.aggregator.sec_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.policy_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.worldbank_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.web_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.academic_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.fetch_newsroom_api", return_value=[])
    def test_worldbank_always_included(self, *mocks):
        from workflows.deep_research.aggregator import aggregate_sources

        aggregate_sources("solar energy efficiency", max_results_per_source=5)
        # worldbank_search_sources is mocks[2] (3rd from right)
        wb_mock = mocks[2]
        wb_mock.assert_called_once()

    @patch("workflows.deep_research.aggregator.sec_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.policy_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.worldbank_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.web_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.academic_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.fetch_newsroom_api", return_value=[])
    def test_policy_channel_included_for_policy_query(self, *mocks):
        # mocks[5]=sec (outermost), mocks[4]=policy, mocks[3]=worldbank, etc.
        from workflows.deep_research.aggregator import aggregate_sources

        aggregate_sources("federal regulation of carbon emissions", max_results_per_source=5)
        policy_mock = mocks[4]
        policy_mock.assert_called_once()

    @patch("workflows.deep_research.aggregator.sec_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.policy_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.worldbank_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.web_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.academic_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.fetch_newsroom_api", return_value=[])
    def test_sec_channel_included_for_financial_query(self, *mocks):
        # mocks[5]=sec (outermost), mocks[4]=policy, mocks[3]=worldbank, etc.
        from workflows.deep_research.aggregator import aggregate_sources

        aggregate_sources("Tesla 10-K annual report filing", max_results_per_source=5)
        sec_mock = mocks[5]
        sec_mock.assert_called_once()

    @patch("workflows.deep_research.aggregator.sec_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.policy_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.worldbank_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.web_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.academic_search_sources", return_value=[])
    @patch("workflows.deep_research.aggregator.fetch_newsroom_api", return_value=[])
    def test_sec_not_included_for_generic_query(self, *mocks):
        from workflows.deep_research.aggregator import aggregate_sources

        aggregate_sources("photosynthesis biology", max_results_per_source=5)
        sec_mock = mocks[5]
        sec_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Credibility baselines for new domains
# ---------------------------------------------------------------------------
class TestNewCredibilityBaselines(unittest.TestCase):
    def test_openalex_credibility(self):
        from workflows.deep_research.credibility import BASE_CREDIBILITY

        self.assertIn("openalex.org", BASE_CREDIBILITY)
        self.assertGreaterEqual(BASE_CREDIBILITY["openalex.org"]["score"], 0.70)

    def test_semantic_scholar_credibility(self):
        from workflows.deep_research.credibility import BASE_CREDIBILITY

        self.assertIn("api.semanticscholar.org", BASE_CREDIBILITY)

    def test_worldbank_credibility(self):
        from workflows.deep_research.credibility import BASE_CREDIBILITY

        self.assertIn("worldbank.org", BASE_CREDIBILITY)
        self.assertGreaterEqual(BASE_CREDIBILITY["worldbank.org"]["score"], 0.80)

    def test_congress_gov_credibility(self):
        from workflows.deep_research.credibility import BASE_CREDIBILITY

        self.assertIn("api.congress.gov", BASE_CREDIBILITY)
        self.assertGreaterEqual(BASE_CREDIBILITY["api.congress.gov"]["score"], 0.85)

    def test_govtrack_credibility(self):
        from workflows.deep_research.credibility import BASE_CREDIBILITY

        self.assertIn("govtrack.us", BASE_CREDIBILITY)

    def test_federal_register_credibility(self):
        from workflows.deep_research.credibility import BASE_CREDIBILITY

        self.assertIn("federalregister.gov", BASE_CREDIBILITY)

    def test_sec_credibility(self):
        from workflows.deep_research.credibility import BASE_CREDIBILITY

        self.assertIn("sec.gov", BASE_CREDIBILITY)
        self.assertGreaterEqual(BASE_CREDIBILITY["sec.gov"]["score"], 0.80)

    def test_efts_sec_credibility(self):
        from workflows.deep_research.credibility import BASE_CREDIBILITY

        self.assertIn("efts.sec.gov", BASE_CREDIBILITY)


if __name__ == "__main__":
    unittest.main()
