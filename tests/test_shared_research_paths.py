import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from engine.repl_command_processor import REPLCommandProcessor


class SharedResearchPathTests(unittest.TestCase):
    def test_web_app_uses_shared_service_symbols(self):
        app_path = "/Users/shingi/Workbench/zorora/ui/web/app.py"
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("from engine.deep_research_service import run_deep_research, build_results_payload", content)
        self.assertIn("state = run_deep_research(", content)
        self.assertIn('"results": build_results_payload(', content)

    def test_repl_deep_command_uses_shared_service_imports(self):
        repl = SimpleNamespace()
        repl.ui = SimpleNamespace(console=Mock())
        repl.remote_commands = {}
        repl.model_selector = Mock()
        repl.turn_processor = SimpleNamespace(
            last_specialist_output="",
            recent_tool_outputs=[],
            max_context_tools=3,
        )
        repl.conversation = Mock()
        repl.persistence = Mock()
        repl.llm_client = Mock()
        repl.tool_executor = Mock()
        repl.get_execution_context = Mock(return_value={})

        processor = REPLCommandProcessor(repl)

        state = SimpleNamespace(
            synthesis="deep summary",
            sources_checked=[],
            total_sources=0,
            findings=[],
        )

        fake_deep_mod = types.ModuleType("engine.deep_research_service")
        fake_deep_mod.run_deep_research = Mock(return_value=state)

        fake_research_engine_mod = types.ModuleType("engine.research_engine")

        class _ResearchEngine:
            def save_research(self, _state):
                return "rid-2"

        fake_research_engine_mod.ResearchEngine = _ResearchEngine

        with patch.dict(
            sys.modules,
            {
                "engine.deep_research_service": fake_deep_mod,
                "engine.research_engine": fake_research_engine_mod,
            },
        ):
            result = processor.handle_workflow_command("/deep test query")

        self.assertIsNotNone(result)
        self.assertIn("Research ID", result[0])
        fake_deep_mod.run_deep_research.assert_called_once_with(
            query="test query",
            depth=1,
            max_results_per_source=10,
        )


if __name__ == "__main__":
    unittest.main()
