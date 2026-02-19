"""Validation tests for dependency/install profile coherence."""

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestInstallProfiles(unittest.TestCase):
    def test_requirements_contains_non_llm_data_stack(self):
        requirements = (ROOT / "requirements.txt").read_text()
        for dep in ("pandas", "numpy", "matplotlib", "scipy", "odse"):
            self.assertIn(dep, requirements)

    def test_setup_py_declares_profile_extras(self):
        setup_text = (ROOT / "setup.py").read_text()
        self.assertIn("extras_require", setup_text)
        self.assertIn('"policy"', setup_text)
        self.assertIn('"full"', setup_text)
        self.assertIn("sentence-transformers", setup_text)
        self.assertIn("faiss-cpu", setup_text)

    def test_manifest_includes_policy_corpus(self):
        manifest = (ROOT / "MANIFEST.in").read_text()
        self.assertIn("docs/policy", manifest)
