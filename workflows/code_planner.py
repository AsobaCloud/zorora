"""Code planning using reasoning model to create detailed implementation plans."""

import logging
import json
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CodePlanner:
    """Creates detailed implementation plans using reasoning model."""

    def __init__(self, llm_client):
        """
        Initialize planner.

        Args:
            llm_client: LLM client for planning (reasoning model)
        """
        self.llm_client = llm_client

    def create_plan(self, request: str, codebase_summary: Dict, ui=None) -> Dict:
        """
        Create detailed implementation plan.

        Args:
            request: User's development request
            codebase_summary: Output from CodebaseExplorer
            ui: Optional UI for progress feedback

        Returns:
            Dict with structured plan
        """
        logger.info(f"Creating plan for: {request[:80]}...")

        if ui:
            ui.console.print("\n[cyan]Phase 2: Planning[/cyan]")
            ui.console.print("[dim]📋 Creating implementation plan...[/dim]")

        # Build planning prompt
        planning_prompt = self._build_planning_prompt(request, codebase_summary)

        try:
            # Call reasoning model for plan generation
            response = self.llm_client.chat_complete(
                [{"role": "user", "content": planning_prompt}],
                tools=None
            )
            plan_text = self.llm_client.extract_content(response)

            # Parse plan from response
            plan = self._parse_plan(plan_text)

            # Validate plan structure
            if not self._validate_plan(plan):
                logger.error("Generated plan failed validation")
                return {
                    "error": "Failed to generate valid plan",
                    "raw_response": plan_text
                }

            plan["raw_text"] = plan_text

            if ui:
                task_count = len(plan.get("tasks", []))
                ui.console.print(f"[green]  ✓ Plan created with {task_count} tasks[/green]")

            logger.info(f"Plan created with {len(plan.get('tasks', []))} tasks")
            return plan

        except Exception as e:
            logger.error(f"Planning failed: {e}")
            return {
                "error": f"Planning failed: {e}",
                "request": request
            }

    def _build_planning_prompt(self, request: str, codebase_summary: Dict) -> str:
        """
        Build planning prompt with codebase context.

        Args:
            request: User's request
            codebase_summary: Codebase exploration results

        Returns:
            Planning prompt string
        """
        # Format codebase summary
        summary_text = self._format_codebase_summary(codebase_summary)

        prompt = f"""You are an expert software architect creating a detailed implementation plan.

CODEBASE CONTEXT:
{summary_text}

DEVELOPMENT REQUEST:
{request}

TASK:
Create a detailed, step-by-step implementation plan for this request. Your plan should:
1. Consider the existing codebase structure and patterns
2. Identify all files to create or modify
3. Specify dependencies to add (if any)
4. Provide clear, actionable tasks in execution order
5. Include error handling and edge cases
6. Follow the project's existing conventions and patterns

OUTPUT FORMAT:
Provide your plan as a JSON object with this exact structure:
{{
  "overview": "Brief description of what changes will be made",
  "tasks": [
    {{
      "type": "create_file" | "edit_file" | "add_dependency",
      "description": "Clear description of what this task does",
      "file_path": "relative/path/to/file.ext",
      "details": "Specific implementation details or code structure",
      "order": 1
    }}
  ],
  "dependencies_to_add": [
    {{
      "name": "package-name",
      "version": "^1.0.0",
      "package_manager": "npm" | "pip" | "go" | "cargo"
    }}
  ],
  "testing_recommendations": [
    "Test case 1",
    "Test case 2"
  ],
  "notes": "Any important considerations or warnings"
}}

IMPORTANT:
- For "edit_file" tasks, specify which parts of the file need to change
- Order tasks logically (dependencies first, then files that import them)
- Be specific about implementation details
- Consider existing patterns in the codebase
- Ensure all file paths are relative to the project root

Generate the plan now as valid JSON:"""

        return prompt

    def _format_codebase_summary(self, summary: Dict) -> str:
        """Format codebase summary for prompt."""
        lines = []

        lines.append(f"Project Type: {summary.get('project_type', 'unknown')}")
        if summary.get('framework'):
            lines.append(f"Framework: {summary['framework']}")
        if summary.get('language'):
            lines.append(f"Language: {summary['language']}")

        lines.append(f"\nTotal Files: {summary.get('file_count', 0)}")

        if summary.get('source_directories'):
            lines.append(f"Source Directories: {', '.join(summary['source_directories'])}")

        if summary.get('entry_points'):
            lines.append(f"Entry Points: {', '.join(summary['entry_points'])}")

        if summary.get('file_types'):
            lines.append("\nFile Types:")
            for ext, count in list(summary['file_types'].items())[:5]:
                lines.append(f"  {ext}: {count} files")

        if summary.get('dependencies'):
            dep_count = len(summary['dependencies'])
            lines.append(f"\nDependencies ({dep_count}):")
            for dep in summary['dependencies'][:15]:
                lines.append(f"  - {dep}")
            if dep_count > 15:
                lines.append(f"  ... and {dep_count - 15} more")

        # Include important file contents (truncated)
        if summary.get('important_files'):
            lines.append("\nConfiguration Files:")
            for file_path, content in summary['important_files'].items():
                lines.append(f"\n{file_path}:")
                if content.startswith("["):  # Error message
                    lines.append(f"  {content}")
                else:
                    # Truncate long files
                    truncated = content[:500] if len(content) > 500 else content
                    lines.append(f"  {truncated}")
                    if len(content) > 500:
                        lines.append("  ... [truncated]")

        return "\n".join(lines)

    def _parse_plan(self, plan_text: str) -> Dict:
        """
        Parse plan from LLM response.

        Args:
            plan_text: LLM response text

        Returns:
            Parsed plan dict
        """
        try:
            # Try to extract JSON from response
            # LLM might wrap JSON in markdown code blocks
            if "```json" in plan_text:
                json_start = plan_text.find("```json") + 7
                json_end = plan_text.find("```", json_start)
                json_text = plan_text[json_start:json_end].strip()
            elif "```" in plan_text:
                json_start = plan_text.find("```") + 3
                json_end = plan_text.find("```", json_start)
                json_text = plan_text[json_start:json_end].strip()
            else:
                # Try to find JSON object in text
                json_start = plan_text.find("{")
                json_end = plan_text.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_text = plan_text[json_start:json_end]
                else:
                    json_text = plan_text

            plan = json.loads(json_text)
            return plan

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse plan JSON: {e}")
            logger.debug(f"Plan text: {plan_text[:500]}")

            # Return minimal valid structure
            return {
                "overview": "Failed to parse plan",
                "tasks": [],
                "error": f"JSON parse error: {e}",
                "raw_text": plan_text
            }

    def _validate_plan(self, plan: Dict) -> bool:
        """
        Validate plan structure.

        Args:
            plan: Parsed plan dict

        Returns:
            True if valid
        """
        # Check required fields
        if "error" in plan:
            return False

        if "overview" not in plan:
            logger.error("Plan missing 'overview'")
            return False

        if "tasks" not in plan or not isinstance(plan["tasks"], list):
            logger.error("Plan missing 'tasks' list")
            return False

        if len(plan["tasks"]) == 0:
            logger.error("Plan has no tasks")
            return False

        # Validate task structure
        for i, task in enumerate(plan["tasks"]):
            if not isinstance(task, dict):
                logger.error(f"Task {i} is not a dict")
                return False

            if "type" not in task:
                logger.error(f"Task {i} missing 'type'")
                return False

            if task["type"] not in ["create_file", "edit_file", "add_dependency"]:
                logger.error(f"Task {i} has invalid type: {task['type']}")
                return False

            if "description" not in task:
                logger.error(f"Task {i} missing 'description'")
                return False

            # File tasks need file_path
            if task["type"] in ["create_file", "edit_file"] and "file_path" not in task:
                logger.error(f"Task {i} missing 'file_path'")
                return False

        return True

    def format_plan_for_display(self, plan: Dict) -> str:
        """
        Format plan for rich display to user.

        Args:
            plan: Plan dict

        Returns:
            Formatted markdown string
        """
        lines = []
        lines.append("# IMPLEMENTATION PLAN\n")

        # Overview
        lines.append("## Overview")
        lines.append(plan.get("overview", "No overview provided"))
        lines.append("")

        # Tasks
        tasks = plan.get("tasks", [])
        if tasks:
            lines.append("## Changes Required\n")

            create_tasks = [t for t in tasks if t["type"] == "create_file"]
            edit_tasks = [t for t in tasks if t["type"] == "edit_file"]
            dep_tasks = [t for t in tasks if t["type"] == "add_dependency"]

            if create_tasks:
                lines.append("### Files to Create:")
                for task in create_tasks:
                    lines.append(f"- **{task['file_path']}**")
                    lines.append(f"  {task['description']}")
                    if task.get("details"):
                        lines.append(f"  *{task['details']}*")
                lines.append("")

            if edit_tasks:
                lines.append("### Files to Modify:")
                for task in edit_tasks:
                    lines.append(f"- **{task['file_path']}**")
                    lines.append(f"  {task['description']}")
                    if task.get("details"):
                        lines.append(f"  *{task['details']}*")
                lines.append("")

            if dep_tasks:
                lines.append("### Dependencies:")
                for task in dep_tasks:
                    lines.append(f"- {task['description']}")
                lines.append("")

        # Dependencies
        if plan.get("dependencies_to_add"):
            lines.append("## Dependencies to Install")
            for dep in plan["dependencies_to_add"]:
                name = dep.get("name", "unknown")
                version = dep.get("version", "")
                pm = dep.get("package_manager", "")
                lines.append(f"- {name} {version} ({pm})")
            lines.append("")

        # Testing
        if plan.get("testing_recommendations"):
            lines.append("## Testing Recommendations")
            for rec in plan["testing_recommendations"]:
                lines.append(f"- {rec}")
            lines.append("")

        # Notes
        if plan.get("notes"):
            lines.append("## Notes")
            lines.append(plan["notes"])
            lines.append("")

        return "\n".join(lines)
