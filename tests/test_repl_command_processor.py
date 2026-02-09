import unittest
from unittest.mock import Mock

from engine.repl_command_processor import REPLCommandProcessor


class _UI:
    def __init__(self):
        self.console = Mock()


class _ReplStub:
    def __init__(self):
        self.ui = _UI()
        self.remote_commands = {}
        self.model_selector = Mock()
        self.turn_processor = Mock()
        self.turn_processor.max_context_tools = 3
        self.turn_processor.recent_tool_outputs = []
        self.turn_processor.last_specialist_output = ""
        self.conversation = Mock()
        self.persistence = Mock()
        self.llm_client = Mock()
        self.tool_executor = Mock()

    def get_execution_context(self):
        return {"actor": "test", "environment": "test", "request_id": "1"}


class _RemoteCommand:
    def __init__(self):
        self.args = None

    def execute(self, args, context):
        self.args = args
        return "ok"


class REPLCommandProcessorTests(unittest.TestCase):
    def test_remote_command_parses_quoted_args_with_shlex(self):
        repl = _ReplStub()
        remote = _RemoteCommand()
        repl.remote_commands["ml-test"] = remote
        processor = REPLCommandProcessor(repl, remote_command_cls=object)

        result = processor.handle_workflow_command('ml-test customer-1 "model with spaces" --force')

        self.assertEqual(result, ("ok", 0))
        self.assertEqual(remote.args, ["customer-1", "model with spaces", "--force"])

    def test_save_command_supports_filename_with_spaces(self):
        repl = _ReplStub()
        processor = REPLCommandProcessor(repl)
        processor.save_output = Mock()

        processor.handle_slash_command('/save "my notes.md"')

        processor.save_output.assert_called_once_with("my notes.md")


if __name__ == "__main__":
    unittest.main()
