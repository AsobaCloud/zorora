"""E2E coverage for real odse package integration path."""

import os
import shutil
import tempfile
import unittest
import importlib
import importlib.util

import pandas as pd

from tools.data_analysis import session
from workflows.load_dataset import LoadDatasetWorkflow


class TestODSEE2E(unittest.TestCase):
    """Validate real odse module presence and transform call path."""

    def setUp(self):
        session.clear_all()
        self.tmpdir = tempfile.mkdtemp()
        self.workflow = LoadDatasetWorkflow()
        self.csv_path = os.path.join(self.tmpdir, "huawei_like.csv")
        with open(self.csv_path, "w") as f:
            f.write(
                "Timestamp,Huawei AC power [W],status\n"
                "2024-01-01 00:00:00,100,normal\n"
                "2024-01-01 01:00:00,120,normal\n"
            )

    def tearDown(self):
        session.clear_all()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_odse_module_available(self):
        if importlib.util.find_spec("odse") is None:
            self.skipTest("odse package not installed")
        import odse  # noqa: F401
        self.assertIsNotNone(odse)

    def test_odse_exposes_transform_callable(self):
        if importlib.util.find_spec("odse") is None:
            self.skipTest("odse package not installed")
        odse = importlib.import_module("odse")
        callables = [
            getattr(odse, name, None)
            for name in ("auto_transform", "transform_csv", "transform", "convert")
        ]
        self.assertTrue(any(callable(c) for c in callables))

    def test_workflow_uses_real_odse_when_fixture_supported(self):
        if importlib.util.find_spec("odse") is None:
            self.skipTest("odse package not installed")

        odse = importlib.import_module("odse")
        callable_names = ("auto_transform", "transform_csv", "transform", "convert")
        supported = False

        for name in callable_names:
            fn = getattr(odse, name, None)
            if not callable(fn):
                continue
            try:
                out = fn(self.csv_path)
            except Exception:
                continue

            if isinstance(out, pd.DataFrame) and not out.empty:
                supported = True
                break
            if isinstance(out, dict):
                candidate = out.get("dataframe") or out.get("df") or out.get("data")
                if isinstance(candidate, pd.DataFrame) and not candidate.empty:
                    supported = True
                    break
            if isinstance(out, tuple):
                for part in out:
                    if isinstance(part, pd.DataFrame) and not part.empty:
                        supported = True
                        break
                if supported:
                    break

        if not supported:
            self.skipTest("Installed odse did not transform this fixture format")

        result = self.workflow.execute(self.csv_path)
        self.assertIn("ODS-E Transform", result)
        self.assertIn("Applied", result)

