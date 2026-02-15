"""Tests for data profiler — pure pandas, no mocks.

All tests build real DataFrames and verify profile_dataframe() output.
"""

import unittest
from datetime import datetime

import numpy as np
import pandas as pd

from tools.data_analysis.profiler import profile_dataframe


class TestProfileShape(unittest.TestCase):
    """Basic shape metrics."""

    def setUp(self):
        self.df = pd.DataFrame({
            "Timestamp": pd.date_range("2024-01-01", periods=100, freq="30min"),
            "value_a": np.random.rand(100),
            "value_b": np.random.rand(100) * 100,
        })

    def test_row_count(self):
        profile = profile_dataframe(self.df)
        self.assertEqual(profile["row_count"], 100)

    def test_column_count(self):
        profile = profile_dataframe(self.df)
        self.assertEqual(profile["column_count"], 3)

    def test_columns_list_has_correct_names(self):
        profile = profile_dataframe(self.df)
        names = [c["name"] for c in profile["columns"]]
        self.assertEqual(names, ["Timestamp", "value_a", "value_b"])

    def test_columns_have_dtype(self):
        profile = profile_dataframe(self.df)
        for col in profile["columns"]:
            self.assertIn("dtype", col)
            self.assertIsInstance(col["dtype"], str)

    def test_columns_have_null_count(self):
        profile = profile_dataframe(self.df)
        for col in profile["columns"]:
            self.assertIn("null_count", col)
            self.assertIn("null_pct", col)


class TestTimeRange(unittest.TestCase):
    """Time range detection from datetime columns."""

    def test_time_range_detected(self):
        df = pd.DataFrame({
            "Timestamp": pd.date_range("2024-02-01", periods=48, freq="30min"),
            "val": range(48),
        })
        profile = profile_dataframe(df)
        self.assertIsNotNone(profile["time_range"])
        self.assertIn("start", profile["time_range"])
        self.assertIn("end", profile["time_range"])
        self.assertIn("span_days", profile["time_range"])

    def test_time_range_none_without_datetime(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        profile = profile_dataframe(df)
        self.assertIsNone(profile["time_range"])

    def test_time_range_span_days_correct(self):
        df = pd.DataFrame({
            "ts": pd.date_range("2024-01-01", periods=49, freq="h"),
            "val": range(49),
        })
        profile = profile_dataframe(df)
        # 48 hours = 2 days
        self.assertAlmostEqual(profile["time_range"]["span_days"], 2.0, places=1)


class TestResolution(unittest.TestCase):
    """Resolution inference from timestamp column."""

    def test_30min_resolution(self):
        df = pd.DataFrame({
            "Timestamp": pd.date_range("2024-01-01", periods=100, freq="30min"),
            "val": range(100),
        })
        profile = profile_dataframe(df)
        self.assertIn("30", profile["resolution"])

    def test_1h_resolution(self):
        df = pd.DataFrame({
            "ts": pd.date_range("2024-01-01", periods=100, freq="h"),
            "val": range(100),
        })
        profile = profile_dataframe(df)
        # Should contain "60" or "1h" or "1H" or "h"
        res = profile["resolution"].lower()
        self.assertTrue("60" in res or "h" in res, f"Expected hourly, got: {profile['resolution']}")

    def test_15min_resolution(self):
        df = pd.DataFrame({
            "ts": pd.date_range("2024-01-01", periods=100, freq="15min"),
            "val": range(100),
        })
        profile = profile_dataframe(df)
        self.assertIn("15", profile["resolution"])

    def test_irregular_resolution(self):
        timestamps = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 1, 0, 30),
            datetime(2024, 1, 1, 1, 15),  # irregular gap
            datetime(2024, 1, 1, 2, 0),
        ]
        df = pd.DataFrame({"ts": timestamps, "val": range(4)})
        profile = profile_dataframe(df)
        # Should indicate irregular or return the median
        self.assertIsNotNone(profile["resolution"])

    def test_resolution_none_without_datetime(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        profile = profile_dataframe(df)
        self.assertIsNone(profile["resolution"])


class TestGapDetection(unittest.TestCase):
    """Gaps in time series data."""

    def test_detects_gap(self):
        # Create 30min data with a 2-hour gap
        ts1 = pd.date_range("2024-01-01 00:00", periods=10, freq="30min")
        ts2 = pd.date_range("2024-01-01 07:00", periods=10, freq="30min")
        ts = ts1.append(ts2)
        df = pd.DataFrame({"Timestamp": ts, "val": range(20)})
        profile = profile_dataframe(df)
        self.assertGreater(len(profile["gaps"]), 0)

    def test_gap_has_start_end_duration(self):
        ts1 = pd.date_range("2024-01-01 00:00", periods=5, freq="30min")
        ts2 = pd.date_range("2024-01-01 05:00", periods=5, freq="30min")
        ts = ts1.append(ts2)
        df = pd.DataFrame({"Timestamp": ts, "val": range(10)})
        profile = profile_dataframe(df)
        if profile["gaps"]:
            gap = profile["gaps"][0]
            self.assertIn("start", gap)
            self.assertIn("end", gap)
            self.assertIn("duration", gap)

    def test_no_gaps_in_regular_data(self):
        df = pd.DataFrame({
            "Timestamp": pd.date_range("2024-01-01", periods=100, freq="30min"),
            "val": range(100),
        })
        profile = profile_dataframe(df)
        self.assertEqual(len(profile["gaps"]), 0)


class TestNumericSummary(unittest.TestCase):
    """Per-column numeric summaries."""

    def test_numeric_summary_present(self):
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [10.0, 20.0, 30.0]})
        profile = profile_dataframe(df)
        self.assertIn("numeric_summary", profile)
        self.assertIn("a", profile["numeric_summary"])
        self.assertIn("b", profile["numeric_summary"])

    def test_numeric_summary_has_stats(self):
        df = pd.DataFrame({"val": [1.0, 2.0, 3.0, 4.0, 5.0]})
        profile = profile_dataframe(df)
        summary = profile["numeric_summary"]["val"]
        self.assertAlmostEqual(summary["min"], 1.0)
        self.assertAlmostEqual(summary["max"], 5.0)
        self.assertAlmostEqual(summary["mean"], 3.0)
        self.assertIn("std", summary)
        self.assertIn("zeros_pct", summary)

    def test_zeros_pct_correct(self):
        df = pd.DataFrame({"val": [0.0, 0.0, 1.0, 2.0, 3.0]})
        profile = profile_dataframe(df)
        self.assertAlmostEqual(profile["numeric_summary"]["val"]["zeros_pct"], 40.0)

    def test_non_numeric_excluded_from_summary(self):
        df = pd.DataFrame({"name": ["a", "b", "c"], "val": [1, 2, 3]})
        profile = profile_dataframe(df)
        self.assertNotIn("name", profile["numeric_summary"])
        self.assertIn("val", profile["numeric_summary"])


class TestDescribe(unittest.TestCase):
    """df.describe() output included."""

    def test_describe_present(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        profile = profile_dataframe(df)
        self.assertIn("describe", profile)
        self.assertIsInstance(profile["describe"], dict)


class TestNullHandling(unittest.TestCase):
    """Null/NaN handling."""

    def test_null_count_correct(self):
        df = pd.DataFrame({"a": [1.0, None, 3.0, None, 5.0]})
        profile = profile_dataframe(df)
        col_info = [c for c in profile["columns"] if c["name"] == "a"][0]
        self.assertEqual(col_info["null_count"], 2)
        self.assertAlmostEqual(col_info["null_pct"], 40.0)

    def test_all_null_column(self):
        df = pd.DataFrame({"empty": [None, None, None], "full": [1, 2, 3]})
        profile = profile_dataframe(df)
        col_info = [c for c in profile["columns"] if c["name"] == "empty"][0]
        self.assertEqual(col_info["null_count"], 3)
        self.assertAlmostEqual(col_info["null_pct"], 100.0)


class TestEdgeCases(unittest.TestCase):
    """Edge cases: empty, single row, etc."""

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        profile = profile_dataframe(df)
        self.assertEqual(profile["row_count"], 0)
        self.assertEqual(profile["column_count"], 0)

    def test_single_row(self):
        df = pd.DataFrame({"a": [42], "b": [3.14]})
        profile = profile_dataframe(df)
        self.assertEqual(profile["row_count"], 1)
        self.assertEqual(profile["column_count"], 2)

    def test_returns_dict(self):
        df = pd.DataFrame({"x": [1, 2, 3]})
        profile = profile_dataframe(df)
        self.assertIsInstance(profile, dict)


if __name__ == "__main__":
    unittest.main()
