"""Tests for execute_analysis — sandboxed code execution.

Real exec(), real pandas/numpy/scipy/matplotlib, real file I/O for plots.
Session store is injected via the module-level dict.
"""

import json
import shutil
import tempfile
import unittest

import pandas as pd

from tools.data_analysis import session
from tools.data_analysis.execute import execute_analysis


class TestReturnType(unittest.TestCase):
    """execute_analysis always returns a string."""

    def setUp(self):
        session.clear_all()
        session.set_df(pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]}))

    def test_returns_string(self):
        result = execute_analysis("df.shape")
        self.assertIsInstance(result, str)

    def test_error_returns_string(self):
        result = execute_analysis("1/0")
        self.assertIsInstance(result, str)


class TestJSONStructure(unittest.TestCase):
    """Successful results are JSON with expected keys."""

    def setUp(self):
        session.clear_all()
        session.set_df(pd.DataFrame({"a": [1, 2, 3]}))

    def test_has_result_key(self):
        result = execute_analysis("df.shape")
        data = json.loads(result)
        self.assertIn("result", data)

    def test_has_type_key(self):
        result = execute_analysis("df.shape")
        data = json.loads(result)
        self.assertIn("type", data)

    def test_has_plot_generated_key(self):
        result = execute_analysis("df.shape")
        data = json.loads(result)
        self.assertIn("plot_generated", data)
        self.assertFalse(data["plot_generated"])


class TestSandboxGlobals(unittest.TestCase):
    """Sandbox provides df, pd, np, scipy, plt."""

    def setUp(self):
        session.clear_all()
        session.set_df(pd.DataFrame({"val": [1.0, 2.0, 3.0]}))

    def test_df_available(self):
        result = execute_analysis("result = df.shape")
        data = json.loads(result)
        self.assertIn("(3, 1)", data["result"])

    def test_pd_available(self):
        result = execute_analysis("result = pd.__name__")
        data = json.loads(result)
        self.assertIn("pandas", data["result"])

    def test_np_available(self):
        result = execute_analysis("result = np.mean([1, 2, 3])")
        data = json.loads(result)
        self.assertIn("2.0", data["result"])

    def test_scipy_available(self):
        result = execute_analysis("from scipy import stats; result = stats.pearsonr([1,2,3],[1,2,3])")
        self.assertNotIn("Error", result)

    def test_plt_available(self):
        result = execute_analysis("result = type(plt).__name__")
        data = json.loads(result)
        self.assertIn("module", data["result"])


class TestSecurity(unittest.TestCase):
    """Dangerous operations are blocked."""

    def setUp(self):
        session.clear_all()
        session.set_df(pd.DataFrame({"a": [1]}))

    def test_import_os_blocked(self):
        result = execute_analysis("import os")
        self.assertTrue(result.startswith("Error"))

    def test_import_subprocess_blocked(self):
        result = execute_analysis("import subprocess")
        self.assertTrue(result.startswith("Error"))

    def test_import_sys_blocked(self):
        result = execute_analysis("import sys")
        self.assertTrue(result.startswith("Error"))

    def test_open_blocked(self):
        result = execute_analysis("f = open('/etc/passwd')")
        self.assertTrue(result.startswith("Error"))

    def test_eval_blocked(self):
        result = execute_analysis("eval('1+1')")
        self.assertTrue(result.startswith("Error"))

    def test_dunder_import_blocked(self):
        result = execute_analysis("__import__('os')")
        self.assertTrue(result.startswith("Error"))


class TestComputation(unittest.TestCase):
    """Computation correctness."""

    def setUp(self):
        session.clear_all()
        session.set_df(pd.DataFrame({
            "x": [1.0, 2.0, 3.0, 4.0, 5.0],
            "y": [2.0, 4.0, 6.0, 8.0, 10.0],
        }))

    def test_describe(self):
        result = execute_analysis("result = df.describe()")
        data = json.loads(result)
        self.assertEqual(data["type"], "dataframe")

    def test_scalar_result(self):
        result = execute_analysis("result = df['x'].mean()")
        data = json.loads(result)
        self.assertEqual(data["type"], "scalar")
        self.assertIn("3.0", data["result"])

    def test_series_result(self):
        result = execute_analysis("result = df['x'] * 2")
        data = json.loads(result)
        self.assertEqual(data["type"], "series")

    def test_string_result(self):
        result = execute_analysis("result = 'hello world'")
        data = json.loads(result)
        self.assertEqual(data["type"], "string")
        self.assertIn("hello world", data["result"])


class TestPlotDetection(unittest.TestCase):
    """Plot generation and detection."""

    def setUp(self):
        session.clear_all()
        session.set_df(pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]}))
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_plot_detected(self):
        code = "plt.figure(); plt.plot(df['x'], df['y']); plt.savefig('__zorora_plot__.png')"
        result = execute_analysis(code, plot_dir=self.tmpdir)
        data = json.loads(result)
        self.assertTrue(data["plot_generated"])
        self.assertIn("plot_path", data)
        self.assertIn("plot_saved", data)
        self.assertTrue(data["plot_saved"])
        self.assertTrue(data["plot_saved"].endswith(".png"))

    def test_no_plot_when_no_savefig(self):
        result = execute_analysis("result = df.shape", plot_dir=self.tmpdir)
        data = json.loads(result)
        self.assertFalse(data["plot_generated"])


class TestErrorHandling(unittest.TestCase):
    """Error cases."""

    def setUp(self):
        session.clear_all()
        session.set_df(pd.DataFrame({"a": [1]}))

    def test_syntax_error(self):
        result = execute_analysis("def f(")
        self.assertTrue(result.startswith("Error"))

    def test_runtime_error(self):
        result = execute_analysis("result = 1 / 0")
        self.assertTrue(result.startswith("Error"))

    def test_empty_code(self):
        result = execute_analysis("")
        self.assertTrue(result.startswith("Error"))

    def test_whitespace_only_code(self):
        result = execute_analysis("   \n  ")
        self.assertTrue(result.startswith("Error"))


class TestSessionManagement(unittest.TestCase):
    """Session store integration."""

    def setUp(self):
        session.clear_all()

    def test_no_session_returns_error(self):
        result = execute_analysis("df.shape")
        self.assertTrue(result.startswith("Error"))

    def test_custom_session_id(self):
        session.set_df(pd.DataFrame({"z": [10, 20]}), session_id="custom")
        result = execute_analysis("result = df['z'].sum()", session_id="custom")
        data = json.loads(result)
        self.assertIn("30", data["result"])

    def test_default_session_id(self):
        session.set_df(pd.DataFrame({"q": [5]}))
        result = execute_analysis("result = len(df)")
        data = json.loads(result)
        self.assertIn("1", data["result"])


if __name__ == "__main__":
    unittest.main()
