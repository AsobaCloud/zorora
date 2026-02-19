"""Integration tests for data analysis feature.

Section 1: End-to-end — load a real CSV then run real analysis code on it.
Section 2: Wiring — registration, routing, param fixes.
"""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import Mock

import numpy as np

from tools.data_analysis import session
from tools.data_analysis.execute import execute_analysis
from workflows.load_dataset import LoadDatasetWorkflow
from tools.registry import TOOL_FUNCTIONS, TOOLS_DEFINITION, SPECIALIST_TOOLS, ToolRegistry
from tool_executor import ToolExecutor
from simplified_router import SimplifiedRouter
from conversation import ConversationManager
from turn_processor import TurnProcessor


# ---------------------------------------------------------------------------
# 1. End-to-end: load CSV → run analysis → verify results
# ---------------------------------------------------------------------------

class TestLoadThenAnalyze(unittest.TestCase):
    """The core objective: load a file, then analyze it with code."""

    def setUp(self):
        session.clear_all()
        self.tmpdir = tempfile.mkdtemp()
        self.workflow = LoadDatasetWorkflow()

    def tearDown(self):
        session.clear_all()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _csv(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_load_then_describe(self):
        """Load CSV, run df.describe(), get real stats back."""
        path = self._csv("data.csv", "x,y\n1,10\n2,20\n3,30\n4,40\n5,50\n")
        self.workflow.execute(path)
        result = execute_analysis("result = df.describe()")
        data = json.loads(result)
        self.assertEqual(data["type"], "dataframe")
        self.assertIn("5", data["result"])  # count = 5

    def test_load_then_shape(self):
        """Load CSV, run df.shape, get correct dimensions."""
        path = self._csv("data.csv", "a,b,c\n1,2,3\n4,5,6\n")
        self.workflow.execute(path)
        result = execute_analysis("result = df.shape")
        data = json.loads(result)
        self.assertIn("2", data["result"])
        self.assertIn("3", data["result"])

    def test_load_then_mean(self):
        """Load CSV, compute column mean, verify correct value."""
        path = self._csv("data.csv", "val\n10\n20\n30\n")
        self.workflow.execute(path)
        result = execute_analysis("result = df['val'].mean()")
        data = json.loads(result)
        self.assertEqual(data["type"], "scalar")
        self.assertIn("20", data["result"])

    def test_load_then_filter(self):
        """Load CSV, filter rows, verify filtered count."""
        path = self._csv("data.csv", "score\n10\n50\n80\n90\n30\n")
        self.workflow.execute(path)
        result = execute_analysis("result = len(df[df['score'] > 40])")
        data = json.loads(result)
        self.assertIn("3", data["result"])  # 50, 80, 90

    def test_load_then_numpy_computation(self):
        """Load CSV, use numpy on loaded data."""
        path = self._csv("data.csv", "v\n2\n4\n6\n8\n")
        self.workflow.execute(path)
        result = execute_analysis("result = float(np.std(df['v']))")
        data = json.loads(result)
        self.assertEqual(data["type"], "scalar")
        # std of [2,4,6,8] = sqrt(5) ≈ 2.236
        self.assertAlmostEqual(float(data["result"]), np.std([2, 4, 6, 8]), places=2)

    def test_load_then_correlation(self):
        """Load CSV, compute correlation between columns."""
        path = self._csv("data.csv", "x,y\n1,2\n2,4\n3,6\n4,8\n5,10\n")
        self.workflow.execute(path)
        result = execute_analysis("result = df['x'].corr(df['y'])")
        data = json.loads(result)
        self.assertAlmostEqual(float(data["result"]), 1.0, places=5)

    def test_load_then_plot(self):
        """Load CSV, generate a plot, verify plot file created."""
        path = self._csv("data.csv", "x,y\n1,2\n2,4\n3,6\n")
        self.workflow.execute(path)
        plot_dir = tempfile.mkdtemp()
        try:
            code = "plt.figure(); plt.plot(df['x'], df['y']); plt.savefig('__zorora_plot__.png')"
            result = execute_analysis(code, plot_dir=plot_dir)
            data = json.loads(result)
            self.assertTrue(data["plot_generated"])
            self.assertTrue(os.path.exists(data["plot_path"]))
        finally:
            shutil.rmtree(plot_dir, ignore_errors=True)

    def test_load_then_groupby(self):
        """Load CSV, run groupby aggregation."""
        path = self._csv("data.csv", "cat,val\na,10\nb,20\na,30\nb,40\n")
        self.workflow.execute(path)
        result = execute_analysis("result = df.groupby('cat')['val'].sum().to_dict()")
        data = json.loads(result)
        self.assertIn("40", data["result"])   # a: 10+30
        self.assertIn("60", data["result"])   # b: 20+40

    def test_load_replaces_previous_then_analyze(self):
        """Loading a second file replaces the first; analysis sees new data."""
        path1 = self._csv("first.csv", "col\n1\n2\n3\n")
        path2 = self._csv("second.csv", "col\n100\n200\n")
        self.workflow.execute(path1)
        self.workflow.execute(path2)
        result = execute_analysis("result = df['col'].sum()")
        data = json.loads(result)
        self.assertIn("300", data["result"])  # 100+200, not 1+2+3

    def test_analysis_without_load_returns_error(self):
        """Running analysis without loading anything gives clear error."""
        result = execute_analysis("result = df.shape")
        self.assertTrue(result.startswith("Error"))
        self.assertIn("load", result.lower())


class TestLoadThenAnalyzeDemoData(unittest.TestCase):
    """End-to-end with the actual demo-data.csv."""

    def setUp(self):
        session.clear_all()
        self.workflow = LoadDatasetWorkflow()
        self.demo_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "docs", "demo-data.csv"
        )

    def tearDown(self):
        session.clear_all()

    def test_load_demo_then_row_count(self):
        if not os.path.exists(self.demo_path):
            self.skipTest("demo-data.csv not found")
        self.workflow.execute(self.demo_path)
        result = execute_analysis("result = len(df)")
        data = json.loads(result)
        self.assertEqual(int(data["result"]), 17569)

    def test_load_demo_then_column_count(self):
        if not os.path.exists(self.demo_path):
            self.skipTest("demo-data.csv not found")
        self.workflow.execute(self.demo_path)
        result = execute_analysis("result = len(df.columns)")
        data = json.loads(result)
        self.assertEqual(int(data["result"]), 3)

    def test_load_demo_then_max_power(self):
        if not os.path.exists(self.demo_path):
            self.skipTest("demo-data.csv not found")
        self.workflow.execute(self.demo_path)
        result = execute_analysis("result = float(df.iloc[:, 1].max())")
        data = json.loads(result)
        self.assertGreater(float(data["result"]), 100000)  # ~104982W

    def test_load_demo_then_time_span(self):
        if not os.path.exists(self.demo_path):
            self.skipTest("demo-data.csv not found")
        self.workflow.execute(self.demo_path)
        result = execute_analysis(
            "result = (df['Timestamp'].max() - df['Timestamp'].min()).days"
        )
        data = json.loads(result)
        self.assertEqual(int(data["result"]), 366)


# ---------------------------------------------------------------------------
# 2. Wiring — registration, routing, param fixes
# ---------------------------------------------------------------------------


class TestDataAnalysisRegistration(unittest.TestCase):
    """Tools registered in TOOL_FUNCTIONS and TOOLS_DEFINITION."""

    def setUp(self):
        self.registry = ToolRegistry()

    def test_execute_analysis_in_tool_functions(self):
        self.assertIn("execute_analysis", TOOL_FUNCTIONS)

    def test_nehanda_query_in_tool_functions(self):
        self.assertIn("nehanda_query", TOOL_FUNCTIONS)

    def test_execute_analysis_resolves_via_registry(self):
        func = self.registry.get_function("execute_analysis")
        self.assertIsNotNone(func)
        self.assertTrue(callable(func))

    def test_nehanda_query_resolves_via_registry(self):
        func = self.registry.get_function("nehanda_query")
        self.assertIsNotNone(func)
        self.assertTrue(callable(func))

    def test_execute_analysis_has_openai_definition(self):
        names = {d["function"]["name"] for d in TOOLS_DEFINITION if "function" in d}
        self.assertIn("execute_analysis", names)

    def test_nehanda_query_has_openai_definition(self):
        names = {d["function"]["name"] for d in TOOLS_DEFINITION if "function" in d}
        self.assertIn("nehanda_query", names)

    def test_execute_analysis_in_specialist_tools(self):
        self.assertIn("execute_analysis", SPECIALIST_TOOLS)


class TestDataAnalysisRouting(unittest.TestCase):
    """Router detects data analysis intent."""

    def setUp(self):
        self.router = SimplifiedRouter()

    def test_analyze_data_routes_to_data_analysis(self):
        result = self.router.route("analyze this data")
        self.assertEqual(result["workflow"], "data_analysis")

    def test_plot_routes_to_data_analysis(self):
        result = self.router.route("plot the power output over time")
        self.assertEqual(result["workflow"], "data_analysis")

    def test_calculate_routes_to_data_analysis(self):
        result = self.router.route("calculate the mean power output")
        self.assertEqual(result["workflow"], "data_analysis")

    def test_non_analysis_does_not_route(self):
        result = self.router.route("what is the weather today")
        self.assertNotEqual(result["workflow"], "data_analysis")

    def test_cross_domain_routes_to_cross_domain(self):
        result = self.router.route(
            "My dataset shows production drop in July; what policy obligations and market context apply?"
        )
        self.assertEqual(result["workflow"], "cross_domain")


class TestLoadCommandDispatch(unittest.TestCase):
    """/load command recognized by REPL command processor."""

    def test_load_command_recognized(self):
        from engine.repl_command_processor import REPLCommandProcessor
        # Create minimal mock REPL
        repl = Mock()
        repl.ui = Mock()
        repl.ui.console = Mock()
        repl.turn_processor = Mock()
        repl.turn_processor.process = Mock(return_value=("loaded", 0.1))

        processor = REPLCommandProcessor(repl)
        result = processor.handle_workflow_command("/load docs/demo-data.csv")
        # Should be handled (not return None)
        self.assertIsNotNone(result)

    def test_load_missing_arg_shows_usage(self):
        from engine.repl_command_processor import REPLCommandProcessor
        repl = Mock()
        repl.ui = Mock()
        repl.ui.console = Mock()

        processor = REPLCommandProcessor(repl)
        result = processor.handle_workflow_command("/load")
        # Should show usage (return None since it prints and doesn't dispatch)
        self.assertIsNone(result)


class TestToolExecutorDataAnalysisDispatch(unittest.TestCase):
    """ToolExecutor parameter fixing for new tools."""

    def setUp(self):
        self.registry = ToolRegistry()
        self.executor = ToolExecutor(self.registry, ui=None)

    def test_execute_analysis_param_fix_task_to_code(self):
        fixed = self.executor._fix_parameter_names(
            "execute_analysis", {"task": "df.shape"}
        )
        self.assertIn("code", fixed)
        self.assertEqual(fixed["code"], "df.shape")

    def test_execute_analysis_param_fix_prompt_to_code(self):
        fixed = self.executor._fix_parameter_names(
            "execute_analysis", {"prompt": "df.describe()"}
        )
        self.assertIn("code", fixed)

    def test_nehanda_query_param_fix_task_to_query(self):
        fixed = self.executor._fix_parameter_names(
            "nehanda_query", {"task": "energy policy"}
        )
        self.assertIn("query", fixed)
        self.assertEqual(fixed["query"], "energy policy")


class TestDataSessionPromptContext(unittest.TestCase):
    """Runtime system prompt should include active dataset context."""

    def setUp(self):
        session.clear_all()
        self.tmpdir = tempfile.mkdtemp()
        workflow = LoadDatasetWorkflow()
        path = os.path.join(self.tmpdir, "data.csv")
        with open(path, "w") as f:
            f.write("timestamp,kwh\n2024-01-01 00:00:00,1.0\n2024-01-01 01:00:00,2.0\n")
        workflow.execute(path)

    def tearDown(self):
        session.clear_all()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_runtime_context_is_injected(self):
        conv = ConversationManager(system_prompt="base")
        tp = TurnProcessor(
            conversation=conv,
            llm_client=Mock(),
            tool_executor=Mock(),
            tool_registry=ToolRegistry(),
            ui=None,
        )
        tp._sync_data_session_context()
        sys_msg = conv.get_messages()[0]["content"]
        self.assertIn("Runtime Context", sys_msg)
        self.assertIn("Active dataset context", sys_msg)


class TestCrossDomainWorkflow(unittest.TestCase):
    """Cross-domain deterministic orchestration path."""

    def test_cross_domain_chains_tools(self):
        conv = ConversationManager(system_prompt="base")
        tool_exec = Mock()
        tool_exec.execute.side_effect = lambda name, args: {
            "execute_analysis": '{"result":"drop validated","type":"string"}',
            "nehanda_query": '{"results":[{"source":"policy.txt","text":"reporting threshold"}]}',
            "web_search": "market context",
        }.get(name, "ok")

        tp = TurnProcessor(
            conversation=conv,
            llm_client=Mock(),
            tool_executor=tool_exec,
            tool_registry=ToolRegistry(),
            ui=None,
        )

        def specialist_side_effect(name, user_input):
            if name == "use_coding_agent":
                return "result = df.shape"
            if name == "use_reasoning_model":
                return "Synthesized grounded response"
            return "ok"

        tp._execute_specialist_tool = Mock(side_effect=specialist_side_effect)
        result = tp._execute_cross_domain_query(
            "My data shows a production drop. What policy obligations apply and what does market context say?"
        )

        self.assertIn("Synthesized", result)
        called_tools = [c.args[0] for c in tool_exec.execute.call_args_list]
        self.assertIn("execute_analysis", called_tools)
        self.assertIn("nehanda_query", called_tools)
        self.assertIn("web_search", called_tools)


if __name__ == "__main__":
    unittest.main()
