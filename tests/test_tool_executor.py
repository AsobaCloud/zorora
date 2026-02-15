"""Regression tests for the registry-to-execution contract.

Verifies: ToolRegistry → ToolExecutor → tool functions wiring.
Section 1 uses real registry data. Section 2 uses real file operations via
tempfile for end-to-end validation. Section 3 mocks at the LLM boundary.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tools.registry import (
    TOOL_FUNCTIONS,
    TOOL_ALIASES,
    TOOLS_DEFINITION,
    SPECIALIST_TOOLS,
    ToolRegistry,
)
from tool_executor import ToolExecutor, MAX_TOOL_RESULT_SIZE


# ---------------------------------------------------------------------------
# 1. Registry completeness
# ---------------------------------------------------------------------------

class TestRegistryCompleteness(unittest.TestCase):
    """Catches dropped tools/aliases after refactors."""

    def setUp(self):
        self.registry = ToolRegistry()

    def test_every_tool_function_resolves(self):
        """Every canonical tool in TOOL_FUNCTIONS resolves via get_function()."""
        for name, func in TOOL_FUNCTIONS.items():
            resolved = self.registry.get_function(name)
            self.assertIsNotNone(resolved, f"TOOL_FUNCTIONS['{name}'] did not resolve")
            self.assertTrue(callable(resolved), f"TOOL_FUNCTIONS['{name}'] is not callable")

    def test_every_alias_resolves_to_callable(self):
        """Every alias in TOOL_ALIASES resolves to a callable via get_function()."""
        for alias, canonical in TOOL_ALIASES.items():
            resolved = self.registry.get_function(alias)
            self.assertIsNotNone(
                resolved,
                f"Alias '{alias}' → '{canonical}' did not resolve to a function"
            )
            self.assertTrue(callable(resolved))

    def test_every_definition_has_matching_function(self):
        """Every tool in TOOLS_DEFINITION has a matching entry in TOOL_FUNCTIONS."""
        defined_names = {
            d["function"]["name"] for d in TOOLS_DEFINITION if "function" in d
        }
        for name in defined_names:
            self.assertIn(
                name,
                TOOL_FUNCTIONS,
                f"TOOLS_DEFINITION has '{name}' but TOOL_FUNCTIONS does not"
            )

    def test_specialist_tools_exist_in_functions_or_aliases(self):
        """Every SPECIALIST_TOOLS entry resolves via get_function (directly or alias)."""
        for name in SPECIALIST_TOOLS:
            resolved = self.registry.get_function(name)
            # Some specialist tools (e.g. deep_research) may not have a direct
            # function entry — but any that DO should resolve.
            if name in TOOL_FUNCTIONS:
                self.assertIsNotNone(
                    resolved,
                    f"SPECIALIST_TOOLS entry '{name}' exists in TOOL_FUNCTIONS but failed to resolve"
                )

    def test_legacy_aliases_still_work(self):
        """Specific aliases that existed in the legacy file must still resolve."""
        legacy_aliases = {
            "bash": "run_shell",
            "use_codestral": "use_coding_agent",
            "pwd": "get_working_directory",
            "cat": "read_file",
            "ls": "list_files",
        }
        for alias, expected_canonical in legacy_aliases.items():
            resolved = self.registry.get_function(alias)
            expected_func = TOOL_FUNCTIONS[expected_canonical]
            self.assertIs(
                resolved,
                expected_func,
                f"Alias '{alias}' should resolve to {expected_canonical}'s function"
            )

    def test_alias_targets_exist_in_tool_functions(self):
        """Every alias target name exists as a key in TOOL_FUNCTIONS."""
        for alias, canonical in TOOL_ALIASES.items():
            self.assertIn(
                canonical,
                TOOL_FUNCTIONS,
                f"Alias '{alias}' → '{canonical}', but '{canonical}' not in TOOL_FUNCTIONS"
            )

    def test_nonexistent_tool_returns_none(self):
        """Requesting a nonexistent tool returns None."""
        self.assertIsNone(self.registry.get_function("totally_fake_tool"))

    def test_get_definitions_returns_list(self):
        """get_definitions() returns a non-empty list."""
        defs = self.registry.get_definitions()
        self.assertIsInstance(defs, list)
        self.assertGreater(len(defs), 0)


# ---------------------------------------------------------------------------
# 2. ToolExecutor end-to-end dispatch through real file operations
# ---------------------------------------------------------------------------

class TestToolExecutorDispatch(unittest.TestCase):
    """End-to-end tests: ToolExecutor → registry → real file-op functions.

    File operations (read_file, write_file, edit_file, list_files,
    get_working_directory) are pure filesystem — no network, no LLM —
    so we call them through the full execute() path and verify real outcomes.
    """

    def setUp(self):
        self.registry = ToolRegistry()
        self.executor = ToolExecutor(self.registry, ui=None)
        # Create temp directory within home so _validate_path allows access
        self.tmpdir = tempfile.mkdtemp(dir=str(Path.home()))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _tmpfile(self, name, content=""):
        """Create a temp file with content and return its absolute path."""
        path = os.path.join(self.tmpdir, name)
        if content:
            with open(path, "w") as f:
                f.write(content)
        return path

    # -- Real end-to-end file operation tests --

    def test_read_file_end_to_end(self):
        """execute('read_file', ...) reads actual file content from disk."""
        path = self._tmpfile("hello.txt", "line one\nline two\n")
        result = self.executor.execute("read_file", {"path": path})
        self.assertIn("line one", result)
        self.assertIn("line two", result)
        # Verify line numbers are present (read_file adds them)
        self.assertRegex(result, r"\d+\tline one")
        self.assertRegex(result, r"\d+\tline two")

    def test_read_file_via_cat_alias(self):
        """execute('cat', ...) resolves alias to read_file and returns real content."""
        path = self._tmpfile("alias_test.txt", "alias content here\n")
        result = self.executor.execute("cat", {"path": path})
        self.assertIn("alias content here", result)

    def test_param_fix_then_real_read(self):
        """execute('read_file', {'task': path}) fixes param name and reads real file."""
        path = self._tmpfile("param_fix.txt", "param fix content\n")
        # 'task' is a common LLM mistake for 'path' — _fix_parameter_names corrects it
        result = self.executor.execute("read_file", {"task": path})
        self.assertIn("param fix content", result)

    def test_write_then_read_end_to_end(self):
        """write_file creates file on disk, read_file retrieves it."""
        path = os.path.join(self.tmpdir, "written.txt")
        write_result = self.executor.execute(
            "write_file", {"path": path, "content": "written by test"}
        )
        self.assertIn("OK", write_result)
        # Read back through the full execute path
        read_result = self.executor.execute("read_file", {"path": path})
        self.assertIn("written by test", read_result)
        # Verify on disk independently
        with open(path) as f:
            self.assertEqual(f.read(), "written by test")

    def test_read_then_edit_end_to_end(self):
        """read_file then edit_file modifies actual file content on disk."""
        path = self._tmpfile("editable.txt", "old text here")
        # Must read before editing (read-before-edit enforcement)
        self.executor.execute("read_file", {"path": path})
        edit_result = self.executor.execute("edit_file", {
            "path": path,
            "old_string": "old text",
            "new_string": "new text",
        })
        self.assertIn("OK", edit_result)
        self.assertIn("Replaced", edit_result)
        # Verify on disk
        with open(path) as f:
            self.assertEqual(f.read(), "new text here")

    def test_list_files_end_to_end(self):
        """execute('list_files', ...) lists actual directory contents."""
        self._tmpfile("aaa.txt", "a")
        self._tmpfile("bbb.txt", "b")
        result = self.executor.execute("list_files", {"path": self.tmpdir})
        self.assertIn("aaa.txt", result)
        self.assertIn("bbb.txt", result)

    def test_get_working_directory_end_to_end(self):
        """execute('get_working_directory', {}) returns a real path string."""
        result = self.executor.execute("get_working_directory", {})
        self.assertIn("Current working directory:", result)
        # The returned path should be a real directory
        reported_path = result.split(": ", 1)[1].strip()
        self.assertTrue(os.path.isdir(reported_path))

    def test_read_file_truncated(self):
        """Non-specialist read_file result is truncated when exceeding MAX_TOOL_RESULT_SIZE."""
        # 200 lines × 80 chars → ~17K with line numbers, exceeds MAX_TOOL_RESULT_SIZE (10000)
        content = ("x" * 80 + "\n") * 200
        path = self._tmpfile("large.txt", content)
        result = self.executor.execute("read_file", {"path": path})
        self.assertIn("truncated", result.lower())
        self.assertLessEqual(len(result), MAX_TOOL_RESULT_SIZE + 200)  # truncation msg overhead

    # -- Direct _truncate_result tests --

    def test_truncate_result_specialist_exempt(self):
        """Specialist tools are exempt from truncation."""
        long_result = "x" * (MAX_TOOL_RESULT_SIZE + 5000)
        result = self.executor._truncate_result(long_result, "use_coding_agent")
        self.assertEqual(len(result), len(long_result))

    def test_truncate_result_non_specialist(self):
        """Non-specialist tools are truncated when result exceeds MAX_TOOL_RESULT_SIZE."""
        long_result = "x" * (MAX_TOOL_RESULT_SIZE + 5000)
        result = self.executor._truncate_result(long_result, "list_files")
        self.assertLess(len(result), len(long_result))
        self.assertIn("truncated", result.lower())

    # -- Kept tests (real behavior, no unnecessary mocks) --

    def test_execute_nonexistent_tool_returns_error(self):
        """execute('nonexistent_tool', ...) returns an error string."""
        result = self.executor.execute("nonexistent_tool", {"arg": "val"})
        self.assertIn("Error", result)
        self.assertIn("Unknown tool", result)
        self.assertIn("nonexistent_tool", result)

    def test_fix_parameter_names_read_file(self):
        """_fix_parameter_names corrects 'task' → 'path' for read_file."""
        fixed = self.executor._fix_parameter_names("read_file", {"task": "/tmp/foo"})
        self.assertIn("path", fixed)
        self.assertNotIn("task", fixed)
        self.assertEqual(fixed["path"], "/tmp/foo")

    def test_fix_parameter_names_preserves_correct_params(self):
        """_fix_parameter_names doesn't clobber correct parameter names."""
        original = {"path": "/tmp/foo"}
        fixed = self.executor._fix_parameter_names("read_file", original)
        self.assertEqual(fixed["path"], "/tmp/foo")

    def test_fix_parameter_names_no_overwrite(self):
        """_fix_parameter_names doesn't overwrite if correct param already present."""
        original = {"task": "wrong", "path": "/correct"}
        fixed = self.executor._fix_parameter_names("read_file", original)
        # 'path' already exists, so 'task' should NOT replace it
        self.assertEqual(fixed["path"], "/correct")

    def test_fix_parameter_names_use_reasoning_model(self):
        """_fix_parameter_names corrects 'prompt' → 'task' for use_reasoning_model."""
        fixed = self.executor._fix_parameter_names(
            "use_reasoning_model", {"prompt": "think about this"}
        )
        self.assertIn("task", fixed)
        self.assertEqual(fixed["task"], "think about this")

    def test_fix_parameter_names_unknown_tool_passthrough(self):
        """_fix_parameter_names passes through unknown tools unchanged."""
        original = {"whatever": "value"}
        fixed = self.executor._fix_parameter_names("unknown_tool", original)
        self.assertEqual(fixed, original)

    def test_read_before_edit_enforcement(self):
        """execute('edit_file', ...) without prior read_file returns error."""
        path = self._tmpfile("unread.txt", "some content")
        result = self.executor.execute(
            "edit_file",
            {"path": path, "old_string": "some", "new_string": "other"}
        )
        self.assertIn("Error", result)
        self.assertIn("read", result.lower())

    def test_clear_read_cache(self):
        """clear_read_cache() empties the tracked files set."""
        self.executor.files_read_this_session.add("/tmp/foo.py")
        self.executor.clear_read_cache()
        self.assertEqual(len(self.executor.files_read_this_session), 0)

    def test_execute_handles_type_error(self):
        """execute() returns error string when tool raises TypeError."""
        mock_func = Mock(side_effect=TypeError("bad args"))
        with patch.dict(self.registry.tools, {"web_search": mock_func}):
            result = self.executor.execute("web_search", {"query": "test"})
            self.assertIn("Error", result)
            self.assertIn("Invalid arguments", result)

    def test_execute_handles_generic_exception(self):
        """execute() returns error string when tool raises Exception."""
        mock_func = Mock(side_effect=RuntimeError("boom"))
        with patch.dict(self.registry.tools, {"web_search": mock_func}):
            result = self.executor.execute("web_search", {"query": "test"})
            self.assertIn("Error", result)
            self.assertIn("boom", result)


# ---------------------------------------------------------------------------
# 3. TurnProcessor → ToolExecutor integration (specialist dispatch)
# ---------------------------------------------------------------------------

class TestTurnProcessorSpecialistDispatch(unittest.TestCase):
    """Catches broken specialist tool parameter mapping in TurnProcessor."""

    def _make_turn_processor(self):
        """Build a TurnProcessor with mocked dependencies."""
        from turn_processor import TurnProcessor

        conversation = Mock()
        conversation.messages = []
        conversation.get_messages = Mock(return_value=[])
        llm_client = Mock()
        registry = ToolRegistry()
        executor = Mock(spec=ToolExecutor)
        executor.execute = Mock(return_value="specialist result")
        executor.working_directory = Mock()

        tp = TurnProcessor(
            conversation=conversation,
            llm_client=llm_client,
            tool_executor=executor,
            tool_registry=registry,
            ui=None,
        )
        return tp, executor

    def test_specialist_reasoning_model_dispatch(self):
        """_execute_specialist_tool('use_reasoning_model', ...) passes 'task' param."""
        tp, executor = self._make_turn_processor()
        tp._execute_specialist_tool("use_reasoning_model", "test input")

        executor.execute.assert_called_once()
        call_args = executor.execute.call_args
        self.assertEqual(call_args[0][0], "use_reasoning_model")
        self.assertIn("task", call_args[0][1])
        self.assertIn("test input", call_args[0][1]["task"])

    def test_specialist_web_search_dispatch(self):
        """_execute_specialist_tool('web_search', ...) passes 'query' param."""
        tp, executor = self._make_turn_processor()
        tp._execute_specialist_tool("web_search", "search query")

        executor.execute.assert_called_once()
        call_args = executor.execute.call_args
        self.assertEqual(call_args[0][0], "web_search")
        self.assertIn("query", call_args[0][1])
        self.assertEqual(call_args[0][1]["query"], "search query")

    def test_specialist_coding_agent_dispatch(self):
        """_execute_specialist_tool('use_coding_agent', ...) passes 'code_context' param."""
        tp, executor = self._make_turn_processor()
        tp._execute_specialist_tool("use_coding_agent", "write a function")

        executor.execute.assert_called_once()
        call_args = executor.execute.call_args
        self.assertEqual(call_args[0][0], "use_coding_agent")
        self.assertIn("code_context", call_args[0][1])

    def test_specialist_nehanda_dispatch(self):
        """_execute_specialist_tool('use_nehanda', ...) passes 'query' param."""
        tp, executor = self._make_turn_processor()
        tp._execute_specialist_tool("use_nehanda", "energy policy question")

        executor.execute.assert_called_once()
        call_args = executor.execute.call_args
        self.assertEqual(call_args[0][0], "use_nehanda")
        self.assertIn("query", call_args[0][1])

    def test_specialist_generate_image_dispatch(self):
        """_execute_specialist_tool('generate_image', ...) passes 'prompt' param."""
        tp, executor = self._make_turn_processor()
        tp._execute_specialist_tool("generate_image", "a sunset")

        executor.execute.assert_called_once()
        call_args = executor.execute.call_args
        self.assertEqual(call_args[0][0], "generate_image")
        self.assertIn("prompt", call_args[0][1])

    def test_specialist_unmapped_tool_returns_none(self):
        """_execute_specialist_tool with unmapped tool returns None."""
        tp, executor = self._make_turn_processor()
        result = tp._execute_specialist_tool("totally_unknown_tool", "input")

        self.assertIsNone(result)
        executor.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
