"""E2E tests for `/load --confirm-map` command path."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import Mock

from engine.repl_command_processor import REPLCommandProcessor
from tools.data_analysis import session


class TestREPLLoadConfirmMapE2E(unittest.TestCase):
    def setUp(self):
        session.clear_all()
        self.tmpdir = tempfile.mkdtemp()
        self.csv_path = os.path.join(self.tmpdir, "generic.csv")
        with open(self.csv_path, "w") as f:
            f.write(
                "datetime,energy_kwh,power,status\n"
                "2024-01-01 00:00:00,1.2,500,normal\n"
                "2024-01-01 01:00:00,1.4,520,warning\n"
            )

        self.repl = Mock()
        self.repl.ui = Mock()
        self.repl.ui.console = Mock()
        self.repl.turn_processor = Mock()
        self.repl.conversation = Mock()
        self.processor = REPLCommandProcessor(self.repl)

    def tearDown(self):
        session.clear_all()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_confirm_map_command_applies_mapping(self):
        cmd = f"/load --confirm-map {self.csv_path}"
        result = self.processor.handle_workflow_command(cmd)
        self.assertIsNotNone(result)

        loaded = session.get_df()
        self.assertIsNotNone(loaded)
        lowered = [c.lower() for c in loaded.columns]
        self.assertIn("timestamp", lowered)
        self.assertIn("kwh", lowered)
        self.assertIn("power_w", lowered)

