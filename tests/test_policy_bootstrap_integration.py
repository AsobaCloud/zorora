"""Integration tests for local policy corpus bootstrap/index behavior."""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import tools.data_analysis.nehanda_local as nehanda_local
from tools.data_analysis.nehanda_local import nehanda_query


class TestPolicyBootstrapIntegration(unittest.TestCase):
    def setUp(self):
        nehanda_local._INDEX_CACHE.clear()
        self.tmpdir = tempfile.mkdtemp()
        self.doc = os.path.join(self.tmpdir, "policy.txt")
        with open(self.doc, "w") as f:
            f.write("Grid code requires compliance reporting.\n\nTariff updates need disclosure.")

    def tearDown(self):
        nehanda_local._INDEX_CACHE.clear()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("tools.data_analysis.nehanda_local._get_embeddings")
    def test_index_signature_updates_when_corpus_changes(self, mock_embed):
        mock_embed.side_effect = lambda texts: np.random.rand(len(texts), 384).astype(np.float32)

        first = nehanda_query("grid code", corpus_dir=self.tmpdir)
        self.assertNotIn("Error", first)
        sig1 = nehanda_local._INDEX_CACHE[self.tmpdir]["signature"]

        with open(self.doc, "a") as f:
            f.write("\n\nNew paragraph for reindex.")
        os.utime(self.doc, None)

        second = nehanda_query("grid code", corpus_dir=self.tmpdir)
        self.assertNotIn("Error", second)
        sig2 = nehanda_local._INDEX_CACHE[self.tmpdir]["signature"]
        self.assertNotEqual(sig1, sig2)

    def test_missing_corpus_has_actionable_error(self):
        missing = os.path.join(self.tmpdir, "missing_corpus")
        result = nehanda_query("policy", corpus_dir=missing)
        self.assertTrue(result.startswith("Error:"))
        self.assertIn("docs/policy", result)

    @patch("tools.data_analysis.nehanda_local._get_embeddings")
    def test_default_repo_policy_corpus_resolves(self, mock_embed):
        mock_embed.side_effect = lambda texts: np.random.rand(len(texts), 384).astype(np.float32)
        result = nehanda_query("grid code")
        self.assertNotIn("Error", result)
        payload = json.loads(result)
        self.assertGreaterEqual(payload["count"], 1)

