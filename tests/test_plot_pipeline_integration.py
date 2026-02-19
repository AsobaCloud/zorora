"""Integration tests for plot persistence and display pipeline."""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from engine.repl_command_processor import REPLCommandProcessor
from tools.data_analysis import session
from tools.data_analysis.execute import execute_analysis
from ui import ZororaUI


class TestPlotPersistenceIntegration(unittest.TestCase):
    def setUp(self):
        session.clear_all()
        session.set_df(pd.DataFrame({"x": [1, 2, 3], "y": [3, 5, 7]}))

    def tearDown(self):
        session.clear_all()

    def test_execute_analysis_persists_plot_artifact(self):
        code = "plt.figure(); plt.plot(df['x'], df['y']); plt.savefig('__zorora_plot__.png')"
        result = execute_analysis(code)
        payload = json.loads(result)
        self.assertTrue(payload["plot_generated"])
        self.assertTrue(payload["plot_saved"])
        self.assertTrue(os.path.exists(payload["plot_saved"]))


class TestPlotDisplayFallback(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.png_path = os.path.join(self.tmpdir, "plot.png")
        with open(self.png_path, "wb") as f:
            # Minimal png signature for display-path tests
            f.write(b"\x89PNG\r\n\x1a\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_display_image_fallback_prints_path(self):
        ui = ZororaUI(no_color=True)
        with patch.dict(os.environ, {"TERM_PROGRAM": "", "TERM": "xterm-256color"}, clear=False):
            with patch.object(ui.console, "print") as mock_print:
                ui.display_image(self.png_path)
                rendered = " ".join(str(a) for c in mock_print.call_args_list for a in c.args)
                self.assertIn("Plot saved:", rendered)


class TestAnalyzeCommandDisplayIntegration(unittest.TestCase):
    def test_analyze_command_calls_display_image_when_plot_generated(self):
        repl = Mock()
        repl.ui = Mock()
        repl.ui.console = Mock()
        repl.ui.display_image = Mock()
        repl.turn_processor = Mock()
        repl.conversation = Mock()
        processor = REPLCommandProcessor(repl)

        with patch("tools.data_analysis.execute.execute_analysis") as mock_exec:
            mock_exec.return_value = json.dumps(
                {
                    "result": "ok",
                    "type": "string",
                    "plot_generated": True,
                    "plot_path": "/tmp/__zorora_plot__.png",
                    "plot_saved": "/tmp/plot_saved.png",
                }
            )
            processor.handle_workflow_command("/analyze result = df.shape")

        repl.ui.display_image.assert_called_once_with("/tmp/plot_saved.png")
