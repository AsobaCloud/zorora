"""Tests for nehanda_query — local FAISS vector search over policy corpus.

Real FAISS index ops and real file I/O. Embedding model is mocked
to avoid downloading 90MB sentence-transformers weights.
"""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from tools.data_analysis.nehanda_local import nehanda_query, _chunk_text


class TestReturnType(unittest.TestCase):
    """nehanda_query always returns a string."""

    def test_returns_string(self):
        result = nehanda_query("test query", corpus_dir="/nonexistent")
        self.assertIsInstance(result, str)

    def test_error_returns_string(self):
        result = nehanda_query("", corpus_dir="/nonexistent")
        self.assertIsInstance(result, str)


class TestJSONStructure(unittest.TestCase):
    """Successful results are JSON with expected keys."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create a small corpus
        with open(os.path.join(self.tmpdir, "policy1.txt"), "w") as f:
            f.write("Renewable energy policy requires 30% solar capacity by 2030.\n\n"
                    "Wind energy targets are set at 20% of total generation capacity.")
        with open(os.path.join(self.tmpdir, "policy2.txt"), "w") as f:
            f.write("Grid interconnection standards mandate frequency regulation.\n\n"
                    "Distribution companies must maintain power factor above 0.95.")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("tools.data_analysis.nehanda_local._get_embeddings")
    def test_has_results_key(self, mock_embed):
        mock_embed.side_effect = lambda texts: np.random.rand(len(texts), 384).astype(np.float32)
        result = nehanda_query("solar energy", corpus_dir=self.tmpdir)
        data = json.loads(result)
        self.assertIn("results", data)

    @patch("tools.data_analysis.nehanda_local._get_embeddings")
    def test_has_query_key(self, mock_embed):
        mock_embed.side_effect = lambda texts: np.random.rand(len(texts), 384).astype(np.float32)
        result = nehanda_query("solar energy", corpus_dir=self.tmpdir)
        data = json.loads(result)
        self.assertIn("query", data)
        self.assertEqual(data["query"], "solar energy")

    @patch("tools.data_analysis.nehanda_local._get_embeddings")
    def test_has_count_key(self, mock_embed):
        mock_embed.side_effect = lambda texts: np.random.rand(len(texts), 384).astype(np.float32)
        result = nehanda_query("solar energy", corpus_dir=self.tmpdir)
        data = json.loads(result)
        self.assertIn("count", data)
        self.assertIsInstance(data["count"], int)


class TestResultOrdering(unittest.TestCase):
    """Results ordered by score."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        with open(os.path.join(self.tmpdir, "doc.txt"), "w") as f:
            f.write("First paragraph about solar.\n\nSecond about wind.\n\nThird about hydro.")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("tools.data_analysis.nehanda_local._get_embeddings")
    def test_scores_descending(self, mock_embed):
        mock_embed.side_effect = lambda texts: np.random.rand(len(texts), 384).astype(np.float32)
        result = nehanda_query("solar", corpus_dir=self.tmpdir)
        data = json.loads(result)
        scores = [r["score"] for r in data["results"]]
        self.assertEqual(scores, sorted(scores, reverse=True))


class TestTopK(unittest.TestCase):
    """top_k parameter respected."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        with open(os.path.join(self.tmpdir, "big.txt"), "w") as f:
            for i in range(20):
                f.write(f"Paragraph {i} about energy policy topic number {i}.\n\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("tools.data_analysis.nehanda_local._get_embeddings")
    def test_top_k_limits_results(self, mock_embed):
        mock_embed.side_effect = lambda texts: np.random.rand(len(texts), 384).astype(np.float32)
        result = nehanda_query("energy", top_k=3, corpus_dir=self.tmpdir)
        data = json.loads(result)
        self.assertLessEqual(data["count"], 3)

    @patch("tools.data_analysis.nehanda_local._get_embeddings")
    def test_top_k_default(self, mock_embed):
        mock_embed.side_effect = lambda texts: np.random.rand(len(texts), 384).astype(np.float32)
        result = nehanda_query("energy", corpus_dir=self.tmpdir)
        data = json.loads(result)
        self.assertLessEqual(data["count"], 5)  # default top_k is 5


class TestChunking(unittest.TestCase):
    """Document chunking."""

    def test_splits_on_paragraphs(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = _chunk_text(text, "test.txt")
        self.assertEqual(len(chunks), 3)

    def test_chunk_has_source(self):
        text = "Some text here."
        chunks = _chunk_text(text, "policy.txt")
        self.assertEqual(chunks[0]["source"], "policy.txt")

    def test_chunk_has_position(self):
        text = "First.\n\nSecond."
        chunks = _chunk_text(text, "test.txt")
        self.assertEqual(chunks[0]["position"], 0)
        self.assertEqual(chunks[1]["position"], 1)

    def test_empty_paragraphs_skipped(self):
        text = "First.\n\n\n\n\nSecond."
        chunks = _chunk_text(text, "test.txt")
        self.assertEqual(len(chunks), 2)


class TestErrorHandling(unittest.TestCase):
    """Error cases."""

    def test_empty_query(self):
        result = nehanda_query("")
        self.assertTrue(result.startswith("Error"))

    def test_missing_corpus_dir(self):
        result = nehanda_query("test", corpus_dir="/nonexistent/path")
        self.assertTrue(result.startswith("Error"))

    @patch("tools.data_analysis.nehanda_local._get_embeddings")
    def test_empty_corpus(self, mock_embed):
        mock_embed.side_effect = lambda texts: np.random.rand(len(texts), 384).astype(np.float32)
        tmpdir = tempfile.mkdtemp()
        try:
            result = nehanda_query("test", corpus_dir=tmpdir)
            self.assertTrue(result.startswith("Error"))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestSourceMetadata(unittest.TestCase):
    """Results contain source filename and chunk position."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        with open(os.path.join(self.tmpdir, "regulation.txt"), "w") as f:
            f.write("Grid code compliance is mandatory.\n\nPenalties apply for violations.")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("tools.data_analysis.nehanda_local._get_embeddings")
    def test_source_filename(self, mock_embed):
        mock_embed.side_effect = lambda texts: np.random.rand(len(texts), 384).astype(np.float32)
        result = nehanda_query("grid code", corpus_dir=self.tmpdir)
        data = json.loads(result)
        sources = [r["source"] for r in data["results"]]
        self.assertTrue(any("regulation.txt" in s for s in sources))

    @patch("tools.data_analysis.nehanda_local._get_embeddings")
    def test_result_has_text(self, mock_embed):
        mock_embed.side_effect = lambda texts: np.random.rand(len(texts), 384).astype(np.float32)
        result = nehanda_query("grid code", corpus_dir=self.tmpdir)
        data = json.loads(result)
        for r in data["results"]:
            self.assertIn("text", r)
            self.assertGreater(len(r["text"]), 0)

    @patch("tools.data_analysis.nehanda_local._get_embeddings")
    def test_result_has_score(self, mock_embed):
        mock_embed.side_effect = lambda texts: np.random.rand(len(texts), 384).astype(np.float32)
        result = nehanda_query("grid code", corpus_dir=self.tmpdir)
        data = json.loads(result)
        for r in data["results"]:
            self.assertIn("score", r)
            self.assertIsInstance(r["score"], float)


class TestEdgeCases(unittest.TestCase):
    """Edge cases."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("tools.data_analysis.nehanda_local._get_embeddings")
    def test_single_doc(self, mock_embed):
        mock_embed.side_effect = lambda texts: np.random.rand(len(texts), 384).astype(np.float32)
        with open(os.path.join(self.tmpdir, "one.txt"), "w") as f:
            f.write("Single document content.")
        result = nehanda_query("document", corpus_dir=self.tmpdir)
        data = json.loads(result)
        self.assertGreater(data["count"], 0)

    @patch("tools.data_analysis.nehanda_local._get_embeddings")
    def test_special_characters_in_query(self, mock_embed):
        mock_embed.side_effect = lambda texts: np.random.rand(len(texts), 384).astype(np.float32)
        with open(os.path.join(self.tmpdir, "doc.txt"), "w") as f:
            f.write("Some content here.")
        result = nehanda_query("what's the policy on CO₂?", corpus_dir=self.tmpdir)
        # Should not crash
        self.assertNotIn("Error", result)


class TestDefaultCorpusResolution(unittest.TestCase):
    """No explicit corpus_dir should resolve to packaged docs/policy corpus."""

    @patch("tools.data_analysis.nehanda_local._get_embeddings")
    def test_default_corpus_works(self, mock_embed):
        mock_embed.side_effect = lambda texts: np.random.rand(len(texts), 384).astype(np.float32)
        result = nehanda_query("grid code requirements")
        self.assertNotIn("Error", result)
        data = json.loads(result)
        self.assertIn("results", data)


if __name__ == "__main__":
    unittest.main()
