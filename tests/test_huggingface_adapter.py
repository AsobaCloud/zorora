"""Tests for HuggingFaceAdapter.chat_complete_stream() — streaming fix validation.

Validates the isinstance(chunk, list) guard that prevents
'list' object has no attribute 'get' crash when HF Inference Toolkit
returns a non-streaming list response over a streaming connection.

All network I/O is mocked — no external calls.
"""

import unittest
from unittest.mock import patch, MagicMock

from providers.huggingface_adapter import HuggingFaceAdapter


def _make_adapter(**kwargs):
    defaults = dict(
        api_url="https://example.com/generate",
        model="test-model",
        auth_token="tok-test",
        timeout=30,
    )
    defaults.update(kwargs)
    return HuggingFaceAdapter(**defaults)


def _mock_response(lines):
    """Build a fake requests.Response whose iter_lines() yields *lines*."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.iter_lines.return_value = iter(lines)
    return resp


MESSAGES = [{"role": "user", "content": "hello"}]


class TestStreamListResponse(unittest.TestCase):
    """HF Toolkit non-streaming fallback: response is a JSON list."""

    @patch("providers.huggingface_adapter.requests.post")
    def test_stream_list_response_yields_text(self, mock_post):
        """The original crash scenario — list response must yield generated_text."""
        mock_post.return_value = _mock_response([
            b'[{"generated_text": "hello world"}]',
        ])
        adapter = _make_adapter()
        chunks = list(adapter.chat_complete_stream(MESSAGES))
        self.assertEqual(chunks, ["hello world"])

    @patch("providers.huggingface_adapter.requests.post")
    def test_stream_list_response_empty_text_skipped(self, mock_post):
        """Empty generated_text should produce no output."""
        mock_post.return_value = _mock_response([
            b'[{"generated_text": ""}]',
        ])
        adapter = _make_adapter()
        chunks = list(adapter.chat_complete_stream(MESSAGES))
        self.assertEqual(chunks, [])

    @patch("providers.huggingface_adapter.requests.post")
    def test_stream_list_response_multiple_items(self, mock_post):
        """Multiple items in the list each yield their generated_text."""
        mock_post.return_value = _mock_response([
            b'[{"generated_text": "first"}, {"generated_text": "second"}]',
        ])
        adapter = _make_adapter()
        chunks = list(adapter.chat_complete_stream(MESSAGES))
        self.assertEqual(chunks, ["first", "second"])


class TestStreamTGIFormat(unittest.TestCase):
    """TGI streaming format: data: {"token": {"text": "..."}}"""

    @patch("providers.huggingface_adapter.requests.post")
    def test_stream_tgi_format_still_works(self, mock_post):
        """Regression guard — TGI token-by-token streaming must still work."""
        mock_post.return_value = _mock_response([
            b'data: {"token": {"text": "tok1"}}',
            b'data: {"token": {"text": "tok2"}}',
        ])
        adapter = _make_adapter()
        chunks = list(adapter.chat_complete_stream(MESSAGES))
        self.assertEqual(chunks, ["tok1", "tok2"])


class TestStreamEdgeCases(unittest.TestCase):
    """Malformed input, tools, and timeout handling."""

    @patch("providers.huggingface_adapter.requests.post")
    def test_stream_json_decode_error_skipped(self, mock_post):
        """Malformed lines are silently skipped; valid lines still yield."""
        mock_post.return_value = _mock_response([
            b'not json',
            b'[{"generated_text": "ok"}]',
        ])
        adapter = _make_adapter()
        chunks = list(adapter.chat_complete_stream(MESSAGES))
        self.assertEqual(chunks, ["ok"])

    def test_stream_tools_raises_valueerror(self):
        """Passing tools to streaming must raise ValueError."""
        adapter = _make_adapter()
        with self.assertRaises(ValueError):
            list(adapter.chat_complete_stream(MESSAGES, tools=[{}]))

    @patch("providers.huggingface_adapter.requests.post")
    def test_stream_timeout_raises_runtimeerror(self, mock_post):
        """requests.Timeout must surface as RuntimeError."""
        import requests
        mock_post.side_effect = requests.Timeout("timed out")
        adapter = _make_adapter()
        with self.assertRaises(RuntimeError):
            list(adapter.chat_complete_stream(MESSAGES))


if __name__ == "__main__":
    unittest.main()
