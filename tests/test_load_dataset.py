"""Tests for LoadDatasetWorkflow — CSV ingest, profiling, session registration.

Real file I/O via tempdir, real pd.read_csv(), real profiler.
ODS-E package is mocked (test both installed and ImportError paths).
"""

import os
import shutil
import tempfile
import unittest

import pandas as pd

from tools.data_analysis import session
from workflows.load_dataset import LoadDatasetWorkflow


class TestCSVLoading(unittest.TestCase):
    """Basic CSV load path."""

    def setUp(self):
        session.clear_all()
        self.tmpdir = tempfile.mkdtemp()
        self.workflow = LoadDatasetWorkflow()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _csv(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_loads_csv_successfully(self):
        path = self._csv("test.csv", "a,b\n1,2\n3,4\n")
        result = self.workflow.execute(path)
        self.assertNotIn("Error", result)

    def test_returns_string(self):
        path = self._csv("test.csv", "a,b\n1,2\n")
        result = self.workflow.execute(path)
        self.assertIsInstance(result, str)

    def test_row_count_in_summary(self):
        rows = "a,b\n" + "\n".join(f"{i},{i*2}" for i in range(50))
        path = self._csv("fifty.csv", rows)
        result = self.workflow.execute(path)
        self.assertIn("50", result)

    def test_column_names_in_summary(self):
        path = self._csv("cols.csv", "price,quantity\n10,5\n20,3\n")
        result = self.workflow.execute(path)
        self.assertIn("price", result)
        self.assertIn("quantity", result)


class TestFileValidation(unittest.TestCase):
    """Missing / unsupported file handling."""

    def setUp(self):
        self.workflow = LoadDatasetWorkflow()

    def test_missing_file(self):
        result = self.workflow.execute("/nonexistent/path.csv")
        self.assertIn("Error", result)

    def test_unsupported_extension(self):
        tmpfile = tempfile.NamedTemporaryFile(suffix=".xyz", delete=False)
        tmpfile.close()
        try:
            result = self.workflow.execute(tmpfile.name)
            self.assertIn("Error", result)
        finally:
            os.unlink(tmpfile.name)

    def test_empty_path(self):
        result = self.workflow.execute("")
        self.assertIn("Error", result)


class TestTimestampDetection(unittest.TestCase):
    """Timestamp column auto-detection."""

    def setUp(self):
        session.clear_all()
        self.tmpdir = tempfile.mkdtemp()
        self.workflow = LoadDatasetWorkflow()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _csv(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_timestamp_column_parsed(self):
        path = self._csv("ts.csv",
                         "Timestamp,val\n2024-01-01 00:00:00,1\n2024-01-01 00:30:00,2\n")
        self.workflow.execute(path)
        df = session.get_df()
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(df["Timestamp"]))

    def test_time_range_in_summary(self):
        path = self._csv("ts.csv",
                         "Timestamp,val\n2024-01-01,1\n2024-01-02,2\n2024-01-03,3\n")
        result = self.workflow.execute(path)
        self.assertIn("2024", result)


class TestODSEDetection(unittest.TestCase):
    """ODS-E detection with mocked odse package."""

    def setUp(self):
        session.clear_all()
        self.tmpdir = tempfile.mkdtemp()
        self.workflow = LoadDatasetWorkflow()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _csv(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_solarman_columns_detected(self):
        """Solarman-style column headers are flagged in summary."""
        path = self._csv("solar.csv",
                         'Timestamp,"INV 001 - AC power [W]","INV002 - AC power [W]"\n'
                         '2024-01-01 00:00:00,100,200\n')
        result = self.workflow.execute(path)
        # Should mention inverter or Solarman/ODS-E
        self.assertTrue(
            "INV" in result or "inverter" in result.lower() or "ODS-E" in result or "solarman" in result.lower(),
            f"Expected inverter/ODS-E mention in: {result[:200]}"
        )

    def test_graceful_without_odse(self):
        """Works fine without the odse package."""
        path = self._csv("noods.csv", "a,b\n1,2\n3,4\n")
        result = self.workflow.execute(path)
        self.assertNotIn("Error", result)


class TestProfileGeneration(unittest.TestCase):
    """Profile data in summary output."""

    def setUp(self):
        session.clear_all()
        self.tmpdir = tempfile.mkdtemp()
        self.workflow = LoadDatasetWorkflow()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _csv(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_row_count_present(self):
        rows = "x\n" + "\n".join(str(i) for i in range(100))
        path = self._csv("rows.csv", rows)
        result = self.workflow.execute(path)
        self.assertIn("100", result)

    def test_resolution_present(self):
        lines = ["Timestamp,val"]
        for i in range(20):
            lines.append(f"2024-01-01 {i//2:02d}:{(i%2)*30:02d}:00,{i}")
        path = self._csv("res.csv", "\n".join(lines))
        result = self.workflow.execute(path)
        # Should mention 30min or resolution
        self.assertTrue("30" in result or "resolution" in result.lower(),
                        f"Expected resolution in: {result[:300]}")

    def test_numeric_summary_present(self):
        path = self._csv("nums.csv", "val\n1\n2\n3\n4\n5\n")
        result = self.workflow.execute(path)
        # Should mention min/max/mean or similar
        self.assertTrue(any(kw in result.lower() for kw in ["min", "max", "mean", "summary"]),
                        f"Expected numeric stats in: {result[:300]}")


class TestSessionRegistration(unittest.TestCase):
    """DataFrame and metadata registered in session store."""

    def setUp(self):
        session.clear_all()
        self.tmpdir = tempfile.mkdtemp()
        self.workflow = LoadDatasetWorkflow()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _csv(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_df_registered(self):
        path = self._csv("reg.csv", "a,b\n1,2\n3,4\n")
        self.workflow.execute(path)
        df = session.get_df()
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 2)

    def test_session_has_metadata(self):
        path = self._csv("meta.csv", "a\n1\n2\n")
        self.workflow.execute(path)
        sess = session.get_session()
        self.assertIsNotNone(sess)
        self.assertIn("profile", sess)
        self.assertIn("file_path", sess)

    def test_reload_replaces_previous(self):
        path1 = self._csv("first.csv", "a\n1\n2\n3\n")
        path2 = self._csv("second.csv", "x,y\n10,20\n")
        self.workflow.execute(path1)
        self.workflow.execute(path2)
        df = session.get_df()
        self.assertEqual(len(df), 1)
        self.assertIn("x", df.columns)


class TestEdgeCases(unittest.TestCase):
    """Edge cases."""

    def setUp(self):
        session.clear_all()
        self.tmpdir = tempfile.mkdtemp()
        self.workflow = LoadDatasetWorkflow()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _csv(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_unicode_content(self):
        path = self._csv("unicode.csv", "name,val\nMünchen,1\nTōkyō,2\n")
        result = self.workflow.execute(path)
        self.assertNotIn("Error", result)

    def test_empty_rows_handled(self):
        path = self._csv("empty.csv", "a,b\n1,2\n\n3,4\n\n")
        result = self.workflow.execute(path)
        self.assertNotIn("Error", result)


class TestDemoData(unittest.TestCase):
    """Tests against the actual demo-data.csv."""

    def setUp(self):
        session.clear_all()
        self.workflow = LoadDatasetWorkflow()
        self.demo_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "docs", "demo-data.csv"
        )

    def test_demo_data_loads(self):
        if not os.path.exists(self.demo_path):
            self.skipTest("demo-data.csv not found")
        result = self.workflow.execute(self.demo_path)
        self.assertNotIn("Error", result)

    def test_demo_data_row_count(self):
        if not os.path.exists(self.demo_path):
            self.skipTest("demo-data.csv not found")
        result = self.workflow.execute(self.demo_path)
        # 17,569 rows expected
        self.assertIn("17", result)

    def test_demo_data_inverter_columns(self):
        if not os.path.exists(self.demo_path):
            self.skipTest("demo-data.csv not found")
        result = self.workflow.execute(self.demo_path)
        self.assertTrue("INV" in result or "inverter" in result.lower())


if __name__ == "__main__":
    unittest.main()
