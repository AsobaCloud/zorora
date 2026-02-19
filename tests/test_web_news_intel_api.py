import unittest
import importlib.util
import pathlib
import sys
from unittest.mock import Mock, patch

WEB_APP_IMPORT_ERROR = None
web_app = None

try:
    _APP_PATH = pathlib.Path(__file__).resolve().parents[1] / "ui" / "web" / "app.py"
    _SPEC = importlib.util.spec_from_file_location("web_app_under_test", _APP_PATH)
    web_app = importlib.util.module_from_spec(_SPEC)
    sys.modules["web_app_under_test"] = web_app
    _SPEC.loader.exec_module(web_app)
except ModuleNotFoundError as exc:
    WEB_APP_IMPORT_ERROR = exc


class WebNewsIntelApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if WEB_APP_IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"web app dependencies unavailable: {WEB_APP_IMPORT_ERROR}")

    @classmethod
    def tearDownClass(cls):
        storage = getattr(getattr(web_app, "research_engine", None), "storage", None)
        if storage and hasattr(storage, "close"):
            storage.close()

    def setUp(self):
        self.client = web_app.app.test_client()

    def test_get_research_prefers_exact_id_lookup(self):
        with patch.object(web_app.research_engine, "load_research", return_value={"research_id": "rid-1", "query": "q1"}) as load_mock, \
             patch.object(web_app.research_engine, "search_research", return_value=[{"research_id": "rid-1"}]) as search_mock:
            response = self.client.get("/api/research/rid-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["research_id"], "rid-1")
        load_mock.assert_called_once_with("rid-1")
        search_mock.assert_not_called()

    def test_get_research_falls_back_to_search_when_exact_lookup_misses(self):
        with patch.object(
            web_app.research_engine,
            "load_research",
            side_effect=[None, {"research_id": "rid-2", "query": "restored"}],
        ) as load_mock, patch.object(
            web_app.research_engine,
            "search_research",
            return_value=[{"research_id": "rid-2"}],
        ) as search_mock:
            response = self.client.get("/api/research/missing-id")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["research_id"], "rid-2")
        self.assertEqual(load_mock.call_count, 2)
        search_mock.assert_called_once_with(query="missing-id", limit=1)

    def test_news_intel_articles_filters_topic_and_date(self):
        sample_articles = [
            {"headline": "Energy grid shifts", "date": "2026-01-10", "source": "Desk", "url": "https://a", "topic_tags": ["energy", "grid"]},
            {"headline": "Healthcare policy update", "date": "2026-01-09", "source": "Desk", "url": "https://b", "topic_tags": ["health"]},
            {"headline": "Energy financing outlook", "date": "2025-11-05", "source": "Desk", "url": "https://c", "topic_tags": ["energy", "finance"]},
        ]
        with patch.object(web_app, "fetch_newsroom_api", return_value=sample_articles):
            response = self.client.post(
                "/api/news-intel/articles",
                json={"topic": "energy", "date_from": "2026-01-01", "date_to": "2026-01-31", "limit": 50},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["articles"][0]["headline"], "Energy grid shifts")

    def test_news_intel_synthesize_uses_filtered_articles(self):
        sample_articles = [
            {"headline": "Energy grid shifts", "date": "2026-01-10", "source": "Desk", "url": "https://a", "topic_tags": ["energy", "grid"]},
            {"headline": "Healthcare policy update", "date": "2026-01-09", "source": "Desk", "url": "https://b", "topic_tags": ["health"]},
        ]
        synth_mock = Mock(return_value="intel brief")
        with patch.object(web_app, "fetch_newsroom_api", return_value=sample_articles), \
             patch.object(web_app, "_news_intel_synthesis", synth_mock):
            response = self.client.post(
                "/api/news-intel/synthesize",
                json={"topic": "energy", "date_from": "2026-01-01", "date_to": "2026-01-31", "limit": 50},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["synthesis"], "intel brief")
        self.assertEqual(payload["articles"][0]["headline"], "Energy grid shifts")
        synth_mock.assert_called_once()
        filtered_articles = synth_mock.call_args.args[0]
        self.assertEqual(len(filtered_articles), 1)
        self.assertEqual(filtered_articles[0]["headline"], "Energy grid shifts")

    def test_news_intel_rejects_invalid_date_range(self):
        with patch.object(web_app, "fetch_newsroom_api") as fetch_mock:
            response = self.client.post(
                "/api/news-intel/synthesize",
                json={"topic": "energy", "date_from": "2026-02-01", "date_to": "2026-01-01"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("date_from must be <= date_to", response.get_json()["error"])
        fetch_mock.assert_not_called()

    def test_research_chat_uses_loaded_research_context(self):
        research_data = {
            "original_query": "AI infrastructure spending",
            "synthesis": "Capex remains elevated across hyperscalers.",
            "sources": [
                {"source_id": "s1", "title": "Quarterly capex update", "url": "https://example.com/a", "source_type": "web"},
                {"source_id": "s2", "title": "Cloud demand report", "url": "https://example.com/b", "source_type": "newsroom"},
            ],
        }
        fake_client = Mock()
        fake_client.chat_complete.return_value = {"choices": []}
        fake_client.extract_content.return_value = "Grounded follow-up answer [Quarterly capex update]."

        with patch.object(web_app, "_load_research_by_id", return_value=research_data), \
             patch.object(web_app, "create_specialist_client", return_value=fake_client):
            response = self.client.post(
                "/api/research/rid-123/chat",
                json={"message": "What is the weakest part of this thesis?", "history": [], "strict_citations": True},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("Grounded follow-up answer", payload["reply"])
        self.assertEqual(payload["mode"], "evidence")
        self.assertIn("s1", payload["used_source_ids"])

    def test_news_intel_chat_replies_for_article_context(self):
        fake_client = Mock()
        fake_client.chat_complete.return_value = {"choices": []}
        fake_client.extract_content.return_value = "Watch shipment trends [Energy grid shifts]."

        with patch.object(web_app, "create_specialist_client", return_value=fake_client):
            response = self.client.post(
                "/api/news-intel/chat",
                json={
                    "message": "What should we monitor next week?",
                    "topic": "energy",
                    "date_from": "2026-01-01",
                    "date_to": "2026-01-31",
                    "articles": [
                        {"headline": "Energy grid shifts", "date": "2026-01-10", "source": "Desk", "url": "https://a"},
                        {"headline": "Battery procurement rises", "date": "2026-01-08", "source": "Desk", "url": "https://b"},
                    ],
                    "synthesis": "Grid themes are broadening.",
                    "history": [],
                    "strict_citations": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("Watch shipment trends", payload["reply"])
        self.assertEqual(payload["mode"], "evidence")

    def test_research_chat_stream_mode_returns_sse(self):
        research_data = {
            "original_query": "AI infrastructure spending",
            "synthesis": "Capex remains elevated across hyperscalers.",
            "sources": [{"source_id": "s1", "title": "Quarterly capex update", "url": "https://example.com/a", "source_type": "web"}],
        }
        fake_client = Mock()
        fake_client.chat_complete.return_value = {"choices": []}
        fake_client.extract_content.return_value = "Grounded stream reply [Quarterly capex update]."

        with patch.object(web_app, "_load_research_by_id", return_value=research_data), \
             patch.object(web_app, "create_specialist_client", return_value=fake_client):
            response = self.client.post(
                "/api/research/rid-stream/chat",
                json={"message": "Stream this", "history": [], "strict_citations": True, "stream": True},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/event-stream")
        body = response.get_data(as_text=True)
        self.assertIn("data:", body)
        self.assertIn("Grounded stream reply", body)

    def test_news_intel_chat_stream_mode_returns_sse(self):
        fake_client = Mock()
        fake_client.chat_complete.return_value = {"choices": []}
        fake_client.extract_content.return_value = "Watch stream signals [Energy grid shifts]."

        with patch.object(web_app, "create_specialist_client", return_value=fake_client):
            response = self.client.post(
                "/api/news-intel/chat",
                json={
                    "message": "Stream this",
                    "topic": "energy",
                    "date_from": "2026-01-01",
                    "date_to": "2026-01-31",
                    "articles": [{"headline": "Energy grid shifts", "date": "2026-01-10", "source": "Desk", "url": "https://a"}],
                    "synthesis": "Grid themes are broadening.",
                    "history": [],
                    "strict_citations": True,
                    "stream": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/event-stream")
        body = response.get_data(as_text=True)
        self.assertIn("data:", body)
        self.assertIn("Watch stream signals", body)


if __name__ == "__main__":
    unittest.main()
