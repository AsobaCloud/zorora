import importlib
import io
import logging
import sys
import types
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch


class MainStartupTests(unittest.TestCase):
    def _import_main_with_stub_repl(self):
        fake_repl_module = types.ModuleType("repl")
        fake_repl_module.REPL = lambda: SimpleNamespace(run=lambda: None, ui=SimpleNamespace(cleanup=lambda: None))

        with patch.dict(sys.modules, {"repl": fake_repl_module}), \
             patch("logging.FileHandler", return_value=logging.NullHandler()):
            if "main" in sys.modules:
                del sys.modules["main"]
            return importlib.import_module("main")

    def _run_main_and_capture_stdout(self, main_module):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            with self.assertRaises(SystemExit):
                main_module.main()
        return buffer.getvalue()

    def test_local_endpoint_runs_lmstudio_check(self):
        main_module = self._import_main_with_stub_repl()
        requests_stub = types.ModuleType("requests")
        requests_stub.get = Mock()
        requests_stub.get.return_value.raise_for_status.return_value = None

        with patch.object(main_module.config, "MODEL_ENDPOINTS", {"orchestrator": "local"}), \
             patch.dict(sys.modules, {"requests": requests_stub}):
            output = self._run_main_and_capture_stdout(main_module)

        self.assertIn("Orchestrator endpoint: local", output)
        self.assertIn("Testing LM Studio connection", output)
        requests_stub.get.assert_called_once()

    def test_openai_endpoint_skips_lmstudio_check(self):
        main_module = self._import_main_with_stub_repl()
        requests_stub = types.ModuleType("requests")
        requests_stub.get = Mock()

        with patch.object(main_module.config, "MODEL_ENDPOINTS", {"orchestrator": "openai_test"}), \
             patch.object(main_module.config, "OPENAI_ENDPOINTS", {"openai_test": {"model": "gpt-4"}}), \
             patch.object(main_module.config, "OPENAI_API_KEY", "sk-test"), \
             patch.dict(sys.modules, {"requests": requests_stub}):
            output = self._run_main_and_capture_stdout(main_module)

        self.assertIn("Orchestrator endpoint: openai_test", output)
        self.assertIn("Using OpenAI endpoint 'openai_test'", output)
        requests_stub.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
