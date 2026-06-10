import io
import logging
import sys
import types
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch


class MainStartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Mock background threads and logging during initial import to avoid side effects
        fake_repl_module = types.ModuleType("repl")
        fake_repl_module.REPL = lambda: SimpleNamespace(run=lambda: None, ui=SimpleNamespace(cleanup=lambda: None))

        with patch.dict(sys.modules, {"repl": fake_repl_module}), \
             patch("logging.FileHandler", return_value=logging.NullHandler()), \
             patch("workflows.background_threads.start_all_background_threads"):
            import main
            cls.main_module = main

    def _run_main_and_capture_stdout(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            with self.assertRaises(SystemExit):
                self.main_module.main()
        return buffer.getvalue()

    def test_local_endpoint_runs_lmstudio_check(self):
        requests_stub = types.ModuleType("requests")
        requests_stub.get = Mock()
        requests_stub.get.return_value.raise_for_status.return_value = None

        with patch.object(self.main_module.config, "MODEL_ENDPOINTS", {"orchestrator": "local"}), \
             patch.dict(sys.modules, {"requests": requests_stub}):
            output = self._run_main_and_capture_stdout()

        self.assertIn("Orchestrator endpoint: local", output)
        self.assertIn("Testing LM Studio connection", output)
        requests_stub.get.assert_called_once()

    def test_openai_endpoint_skips_lmstudio_check(self):
        requests_stub = types.ModuleType("requests")
        requests_stub.get = Mock()

        with patch.object(self.main_module.config, "MODEL_ENDPOINTS", {"orchestrator": "openai_test"}), \
             patch.object(self.main_module.config, "OPENAI_ENDPOINTS", {"openai_test": {"model": "gpt-4"}}), \
             patch.object(self.main_module.config, "OPENAI_API_KEY", "sk-test"), \
             patch.dict(sys.modules, {"requests": requests_stub}):
            output = self._run_main_and_capture_stdout()

        self.assertIn("Orchestrator endpoint: openai_test", output)
        self.assertIn("Using OpenAI endpoint 'openai_test'", output)
        requests_stub.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
