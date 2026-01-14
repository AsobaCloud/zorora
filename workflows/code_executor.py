"""Code execution using Codestral to implement planned changes."""

import logging
from pathlib import Path
from typing import Dict, List
import json

from workflows.code_tools import write_file, edit_file, lint_file, install_dependencies

logger = logging.getLogger(__name__)


class CodeExecutor:
    """Executes implementation plan using code generation model."""

    def __init__(self, tool_executor, working_directory: str):
        """
        Initialize executor.

        Args:
            tool_executor: ToolExecutor with access to codestral
            working_directory: Base directory for file operations
        """
        self.tool_executor = tool_executor
        self.working_directory = working_directory
        self.modified_files = []
        self.created_files = []
        self.execution_log = []

    def execute_plan(self, plan: Dict, codebase_summary: Dict, ui=None) -> Dict:
        """
        Execute implementation plan.

        Args:
            plan: Plan from CodePlanner
            codebase_summary: Codebase exploration results
            ui: Optional UI for progress feedback

        Returns:
            Dict with execution results
        """
        logger.info("Starting plan execution")

        if ui:
            ui.console.print("\n[cyan]Phase 4: Code Execution[/cyan]")
            ui.console.print("[dim]⚙️  Executing plan...[/dim]")

        # Sort tasks by order if specified
        tasks = plan.get("tasks", [])
        tasks = sorted(tasks, key=lambda t: t.get("order", 999))

        success_count = 0
        error_count = 0

        # Execute each task
        for i, task in enumerate(tasks, 1):
            task_type = task.get("type")
            description = task.get("description", "Unknown task")

            if ui:
                ui.console.print(f"  [{i}/{len(tasks)}] {description}")

            try:
                if task_type == "create_file":
                    result = self._execute_create_file(task, codebase_summary)
                elif task_type == "edit_file":
                    result = self._execute_edit_file(task, codebase_summary)
                elif task_type == "add_dependency":
                    result = self._execute_add_dependency(task, codebase_summary)
                else:
                    result = f"Unknown task type: {task_type}"
                    error_count += 1

                self.execution_log.append({
                    "task": description,
                    "result": result,
                    "success": not result.startswith("Error")
                })

                if result.startswith("Error"):
                    error_count += 1
                    if ui:
                        ui.console.print(f"    [red]✗ {result}[/red]")
                else:
                    success_count += 1
                    if ui:
                        ui.console.print(f"    [green]{result}[/green]")

            except Exception as e:
                error_msg = f"Error executing task: {e}"
                logger.error(error_msg)
                self.execution_log.append({
                    "task": description,
                    "result": error_msg,
                    "success": False
                })
                error_count += 1
                if ui:
                    ui.console.print(f"    [red]✗ {error_msg}[/red]")

        if ui:
            ui.console.print(f"\n  [cyan]Completed: {success_count} succeeded, {error_count} failed[/cyan]")

        return {
            "success": error_count == 0,
            "tasks_completed": success_count,
            "tasks_failed": error_count,
            "modified_files": self.modified_files,
            "created_files": self.created_files,
            "execution_log": self.execution_log
        }

    def _execute_create_file(self, task: Dict, codebase_summary: Dict) -> str:
        """
        Execute file creation task.

        Returns:
            Result message
        """
        file_path = task.get("file_path")
        if not file_path:
            return "Error: No file_path specified"

        # Use codestral to generate file content
        generation_prompt = self._build_file_generation_prompt(task, codebase_summary)

        try:
            # Call codestral for code generation
            result = self.tool_executor.execute("use_codestral", {
                "code_context": generation_prompt
            })

            # Extract code from result
            code_content = self._extract_code_from_response(result)

            # Write file
            write_result = write_file(file_path, code_content, self.working_directory)

            if not write_result.startswith("Error"):
                self.created_files.append(file_path)

            return write_result

        except Exception as e:
            return f"Error generating file: {e}"

    def _execute_edit_file(self, task: Dict, codebase_summary: Dict, max_retries: int = 3) -> str:
        """
        Execute file edit task with retry loop.

        The model gets feedback on failed edits and can retry with corrected approach.

        Args:
            task: Task dict with file_path, description, details
            codebase_summary: Codebase exploration results
            max_retries: Maximum retry attempts (default: 3)

        Returns:
            Result message
        """
        file_path = task.get("file_path")
        if not file_path:
            return "Error: No file_path specified"

        full_path = Path(self.working_directory) / file_path

        if not full_path.exists():
            return f"Error: File {file_path} does not exist"

        last_error = None

        for attempt in range(max_retries):
            try:
                # Always re-read file (content may have changed in previous attempt)
                current_content = full_path.read_text(encoding='utf-8')

                # Build prompt (include error context on retry)
                if attempt == 0:
                    edit_prompt = self._build_file_edit_prompt(task, current_content, codebase_summary)
                else:
                    edit_prompt = self._build_retry_edit_prompt(
                        task=task,
                        current_content=current_content,
                        codebase_summary=codebase_summary,
                        previous_error=last_error,
                        attempt=attempt
                    )

                # Generate edit
                result = self.tool_executor.execute("use_codestral", {
                    "code_context": edit_prompt
                })

                # Extract instructions
                edit_instructions = self._extract_edit_instructions(result, current_content)

                if not edit_instructions:
                    last_error = "Could not parse edit instructions from model response"
                    logger.warning(f"Edit attempt {attempt+1}: {last_error}")
                    continue

                old_content = edit_instructions["old"]
                new_content = edit_instructions["new"]

                # Apply edit
                edit_result = edit_file(file_path, old_content, new_content, self.working_directory)

                if not edit_result.startswith("Error"):
                    # Success!
                    self.modified_files.append(file_path)
                    if attempt > 0:
                        logger.info(f"Edit succeeded on attempt {attempt+1}")
                    return edit_result

                # Failed - capture error for next attempt
                last_error = edit_result
                logger.warning(f"Edit attempt {attempt+1} failed: {edit_result}")

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Edit attempt {attempt+1} exception: {e}")

        return f"Error: Failed after {max_retries} attempts. Last error: {last_error}"

    def _build_retry_edit_prompt(self, task: Dict, current_content: str,
                                  codebase_summary: Dict, previous_error: str,
                                  attempt: int) -> str:
        """Build prompt for retry attempt with error context."""
        file_path = task.get("file_path")
        description = task.get("description", "")

        # Add line numbers for precision
        numbered_content = self._add_line_numbers(current_content)

        # Truncate if very large
        if len(numbered_content) > 15000:
            lines = numbered_content.split('\n')
            numbered_content = '\n'.join(lines[:200]) + '\n... (truncated) ...\n' + '\n'.join(lines[-100:])

        prompt = f"""RETRY ATTEMPT {attempt + 1}: Your previous edit failed.

ERROR: {previous_error}

FILE: {file_path}

CURRENT CONTENT (with line numbers - use these for reference):
{numbered_content}

TASK: {description}

IMPORTANT:
1. The OLD_CODE must match EXACTLY what's in the file (including whitespace)
2. Copy the exact text from the file above, preserving indentation
3. If the string appears multiple times, include more context to make it unique
4. Do NOT include line numbers in your OLD_CODE - just the actual code

Output in this format:
OLD_CODE:
```
[exact code to replace - copy from file above, without line numbers]
```

NEW_CODE:
```
[replacement code]
```"""

        return prompt

    def _add_line_numbers(self, content: str) -> str:
        """Add line numbers to content for reference."""
        lines = content.splitlines()
        numbered = [f"{i:4d} | {line}" for i, line in enumerate(lines, 1)]
        return "\n".join(numbered)

    def _execute_add_dependency(self, task: Dict, codebase_summary: Dict) -> str:
        """
        Execute add dependency task.

        Returns:
            Result message
        """
        description = task.get("description", "")

        # For now, just log - actual dependency adding happens in dependency installation phase
        logger.info(f"Dependency task: {description}")
        return f"✓ Noted: {description}"

    def _build_file_generation_prompt(self, task: Dict, codebase_summary: Dict) -> str:
        """Build prompt for generating new file."""
        file_path = task.get("file_path")
        description = task.get("description", "")
        details = task.get("details", "")

        prompt = f"""Generate code for a new file in a {codebase_summary.get('project_type', 'software')} project.

FILE: {file_path}

PURPOSE: {description}

DETAILS: {details}

PROJECT CONTEXT:
- Framework: {codebase_summary.get('framework', 'none')}
- Language: {codebase_summary.get('language', 'unknown')}
- Existing patterns: Follow standard conventions for this project type

REQUIREMENTS:
1. Generate complete, production-ready code
2. Include proper error handling
3. Add clear comments for complex logic
4. Follow the project's existing code style
5. Include necessary imports/dependencies
6. Make it modular and maintainable

Output ONLY the complete file content, no explanations or markdown formatting."""

        return prompt

    def _build_file_edit_prompt(self, task: Dict, current_content: str, codebase_summary: Dict) -> str:
        """Build prompt for editing existing file with smart truncation."""
        file_path = task.get("file_path")
        description = task.get("description", "")
        details = task.get("details", "")

        # Smart truncation based on file size
        truncation_note = ""
        if len(current_content) <= 8000:
            # Small-medium files: include full content with line numbers
            content_section = self._add_line_numbers(current_content)
        elif len(current_content) <= 20000:
            # Large files: include relevant sections
            content_section = self._smart_truncate_for_edit(current_content, task)
            truncation_note = "\n[Note: File truncated to relevant sections. Line numbers preserved for reference.]"
        else:
            # Very large files: focused extraction
            content_section = self._extract_edit_region(current_content, task)
            truncation_note = f"\n[Note: Large file ({len(current_content)} chars) - showing region around edit target.]"

        prompt = f"""Modify an existing file in a {codebase_summary.get('project_type', 'software')} project.

FILE: {file_path}

CURRENT CONTENT (with line numbers for reference):
{content_section}
{truncation_note}

MODIFICATION NEEDED: {description}

DETAILS: {details}

REQUIREMENTS:
1. The OLD_CODE must match EXACTLY what's in the file (including whitespace/indentation)
2. Copy the text precisely from the content above (do NOT include line numbers)
3. If string appears multiple times, include enough context to make it unique
4. Preserve existing code style

Output in this format:
OLD_CODE:
```
[exact code to replace - copy from above, without line numbers]
```

NEW_CODE:
```
[replacement code]
```"""

        return prompt

    def _smart_truncate_for_edit(self, content: str, task: Dict) -> str:
        """Smart truncation that preserves edit-relevant context with line numbers."""
        lines = content.splitlines()
        numbered = []

        # Always include first 50 lines (imports, class definitions)
        for i, line in enumerate(lines[:50], 1):
            numbered.append(f"{i:4d} | {line}")

        if len(lines) > 100:
            numbered.append("     | ... (middle section omitted) ...")

        # Include last 50 lines
        if len(lines) > 50:
            start = max(50, len(lines) - 50)
            for i, line in enumerate(lines[start:], start + 1):
                numbered.append(f"{i:4d} | {line}")

        return "\n".join(numbered)

    def _extract_edit_region(self, content: str, task: Dict) -> str:
        """Extract region around likely edit target for very large files."""
        description = task.get("description", "").lower()
        lines = content.splitlines()

        # Try to find relevant function/class based on keywords
        target_keywords = []
        for word in description.split():
            if len(word) > 3 and word.isalnum():
                target_keywords.append(word)

        # Find lines containing keywords
        relevant_indices = set()
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(kw in line_lower for kw in target_keywords):
                # Include context around match (20 lines before, 30 after)
                for j in range(max(0, i - 20), min(len(lines), i + 30)):
                    relevant_indices.add(j)

        if relevant_indices:
            relevant_indices = sorted(relevant_indices)
            numbered = []
            prev_idx = -2

            for idx in relevant_indices:
                if prev_idx >= 0 and idx > prev_idx + 1:
                    numbered.append("     | ...")
                numbered.append(f"{idx+1:4d} | {lines[idx]}")
                prev_idx = idx

            return "\n".join(numbered)

        # Fallback to head/tail
        return self._smart_truncate_for_edit(content, task)

    def _extract_code_from_response(self, response: str) -> str:
        """Extract code content from codestral response."""
        # Remove markdown code blocks if present
        if "```" in response:
            # Find first code block
            start = response.find("```")
            if start >= 0:
                # Skip language identifier
                newline = response.find("\n", start)
                if newline >= 0:
                    start = newline + 1
                    # Find end
                    end = response.find("```", start)
                    if end >= 0:
                        return response[start:end].strip()

        # If no code blocks, return as-is (codestral might output plain code)
        return response.strip()

    def _extract_edit_instructions(self, response: str, current_content: str) -> Dict:
        """Extract old and new code sections from edit response."""
        try:
            # Look for OLD_CODE and NEW_CODE markers
            if "OLD_CODE:" in response and "NEW_CODE:" in response:
                old_start = response.find("OLD_CODE:") + 9
                old_end = response.find("NEW_CODE:")
                new_start = response.find("NEW_CODE:") + 9

                old_section = response[old_start:old_end].strip()
                new_section = response[new_start:].strip()

                # Remove code block markers
                old_code = self._extract_code_from_response(old_section)
                new_code = self._extract_code_from_response(new_section)

                # Verify old_code exists in current content
                if old_code in current_content:
                    return {"old": old_code, "new": new_code}
                else:
                    logger.warning("OLD_CODE not found in current file")
                    # Try fuzzy matching or just return None
                    return None

            return None

        except Exception as e:
            logger.error(f"Error extracting edit instructions: {e}")
            return None

    def validate_with_linting(self, project_type: str, ui=None) -> Dict:
        """
        Run linting on all modified files.

        Args:
            project_type: Type of project (for linter selection)
            ui: Optional UI for progress feedback

        Returns:
            Dict with linting results
        """
        if ui:
            ui.console.print("\n[cyan]Phase 5: Linting & Validation[/cyan]")
            ui.console.print("[dim]🔧 Validating code quality...[/dim]")

        all_files = self.created_files + self.modified_files
        lint_results = []
        passed_count = 0
        failed_count = 0

        for file_path in all_files:
            result = lint_file(file_path, self.working_directory)

            lint_results.append({
                "file": file_path,
                "result": result
            })

            if result.get("skipped"):
                if ui:
                    ui.console.print(f"  [dim]{file_path} - Skipped (no linter)[/dim]")
                passed_count += 1
            elif result.get("success"):
                auto_fixed = " (auto-fixed)" if result.get("auto_fixed") else ""
                if ui:
                    ui.console.print(f"  [green]✓ {file_path} - Passed{auto_fixed}[/green]")
                passed_count += 1
            else:
                if ui:
                    ui.console.print(f"  [red]✗ {file_path} - Failed[/red]")
                    if result.get("output"):
                        ui.console.print(f"    [dim]{result['output'][:200]}[/dim]")
                failed_count += 1

        return {
            "passed": passed_count,
            "failed": failed_count,
            "results": lint_results,
            "all_passed": failed_count == 0
        }
