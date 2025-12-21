"""Main orchestrator for /develop multi-step coding workflow."""

import os
import logging
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from rich.panel import Panel
from rich.markdown import Markdown

from workflows.codebase_explorer import CodebaseExplorer
from workflows.code_planner import CodePlanner
from workflows.code_executor import CodeExecutor
from workflows.code_tools import detect_project_type, install_dependencies

logger = logging.getLogger(__name__)


@dataclass
class DevelopWorkflowState:
    """State tracking for development workflow."""
    request: str
    working_directory: str
    codebase_summary: Optional[Dict] = None
    plan: Optional[Dict] = None
    modified_files: List[str] = field(default_factory=list)
    created_files: List[str] = field(default_factory=list)
    execution_log: List[str] = field(default_factory=list)
    current_phase: str = "exploration"
    status: str = "in_progress"  # in_progress, completed, cancelled, failed


class DevelopWorkflow:
    """Orchestrates multi-step code development workflow."""

    def __init__(self, tool_executor, llm_client, ui=None):
        """
        Initialize workflow.

        Args:
            tool_executor: ToolExecutor for tool access
            llm_client: LLM client for reasoning
            ui: Optional UI for user interaction
        """
        self.tool_executor = tool_executor
        self.llm_client = llm_client
        self.ui = ui
        self.state = None

    def execute(self, request: str, working_directory: str) -> str:
        """
        Execute complete development workflow.

        Args:
            request: User's development request
            working_directory: Current working directory

        Returns:
            Result summary string
        """
        logger.info(f"Starting /develop workflow: {request[:80]}")

        # Initialize state
        self.state = DevelopWorkflowState(
            request=request,
            working_directory=working_directory
        )

        # Phase 0: Pre-flight checks
        preflight_result = self._preflight_checks()
        if not preflight_result["success"]:
            return preflight_result["message"]

        # Phase 1: Exploration
        self.state.current_phase = "exploration"
        explorer = CodebaseExplorer(self.llm_client)
        self.state.codebase_summary = explorer.explore(working_directory, ui=self.ui)

        if "error" in self.state.codebase_summary:
            self.state.status = "failed"
            return f"Exploration failed: {self.state.codebase_summary['error']}"

        # Phase 2: Planning (with modification loop)
        plan_approved = False
        modified_request = request

        while not plan_approved:
            self.state.current_phase = "planning"
            planner = CodePlanner(self.llm_client)
            self.state.plan = planner.create_plan(
                modified_request,
                self.state.codebase_summary,
                ui=self.ui
            )

            if "error" in self.state.plan:
                self.state.status = "failed"
                return f"Planning failed: {self.state.plan['error']}"

            # Phase 3: User approval
            self.state.current_phase = "approval"
            approval_result = self._get_user_approval(planner)

            if approval_result["action"] == "approve":
                plan_approved = True
            elif approval_result["action"] == "modify":
                modified_request = approval_result["new_request"]
                if self.ui:
                    self.ui.console.print(f"\n[cyan]Replanning with modified request...[/cyan]")
            elif approval_result["action"] == "cancel":
                self.state.status = "cancelled"
                return "Development workflow cancelled by user."

        # Phase 4: Execution
        self.state.current_phase = "execution"
        executor = CodeExecutor(self.tool_executor, working_directory)
        exec_result = executor.execute_plan(
            self.state.plan,
            self.state.codebase_summary,
            ui=self.ui
        )

        self.state.modified_files = exec_result["modified_files"]
        self.state.created_files = exec_result["created_files"]
        self.state.execution_log = exec_result["execution_log"]

        if not exec_result["success"]:
            # Partial failure
            self.state.status = "failed"
            return self._generate_summary(exec_result, None)

        # Phase 5: Linting
        self.state.current_phase = "linting"
        project_type = self.state.codebase_summary.get("project_type", "unknown")
        lint_result = executor.validate_with_linting(project_type, ui=self.ui)

        # Phase 6: Dependency installation
        if self.state.plan.get("dependencies_to_add"):
            self._install_dependencies(project_type)

        # Phase 7: Completion
        self.state.current_phase = "completed"
        self.state.status = "completed"

        return self._generate_summary(exec_result, lint_result)

    def _preflight_checks(self) -> Dict:
        """
        Run pre-flight checks before starting workflow.

        Returns:
            Dict with success status and message
        """
        if self.ui:
            self.ui.console.print("\n[cyan]Pre-flight checks...[/cyan]")

        # Check 1: Git repository
        if not self._is_git_repository():
            msg = "Error: Not a git repository. /develop requires git for safety.\nRun 'git init' to initialize a repository."
            if self.ui:
                self.ui.console.print(f"[red]✗ {msg}[/red]")
            return {"success": False, "message": msg}

        if self.ui:
            self.ui.console.print("[green]  ✓ Git repository detected[/green]")

        # Check 2: Uncommitted changes warning
        if self._has_uncommitted_changes():
            if self.ui:
                self.ui.console.print("[yellow]  ⚠ You have uncommitted changes[/yellow]")
                self.ui.console.print("[dim]    Recommendation: Commit or stash changes first[/dim]")
                proceed = input("    Proceed anyway? (y/n): ").lower().strip()
                if proceed != 'y':
                    return {"success": False, "message": "Workflow cancelled by user."}

        return {"success": True, "message": "Pre-flight checks passed"}

    def _is_git_repository(self) -> bool:
        """Check if current directory is a git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.state.working_directory,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False

    def _has_uncommitted_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.state.working_directory,
                capture_output=True,
                text=True
            )
            return bool(result.stdout.strip())
        except Exception:
            return False

    def _get_user_approval(self, planner: CodePlanner) -> Dict:
        """
        Get user approval for plan.

        Returns:
            Dict with action and optional new_request
        """
        if not self.ui:
            # No UI - auto-approve
            return {"action": "approve"}

        # Display plan
        plan_text = planner.format_plan_for_display(self.state.plan)
        panel = Panel(
            Markdown(plan_text),
            title="Implementation Plan",
            border_style="cyan",
            padding=(1, 2)
        )
        self.ui.console.print("\n")
        self.ui.console.print(panel)

        # Get user choice
        self.ui.console.print("\n[bold cyan]Review the plan above:[/bold cyan]")
        self.ui.console.print("  [green]A[/green] - Approve and proceed")
        self.ui.console.print("  [yellow]M[/yellow] - Modify (provide new prompt)")
        self.ui.console.print("  [red]C[/red] - Cancel")

        while True:
            choice = input("\nYour choice [A/M/C]: ").strip().lower()

            if choice == 'a':
                return {"action": "approve"}
            elif choice == 'm':
                new_request = input("\nEnter modified development request: ").strip()
                if new_request:
                    return {"action": "modify", "new_request": new_request}
                else:
                    self.ui.console.print("[red]Please provide a modified request[/red]")
            elif choice == 'c':
                return {"action": "cancel"}
            else:
                self.ui.console.print("[red]Invalid choice. Please enter A, M, or C.[/red]")

    def _install_dependencies(self, project_type: str):
        """Install project dependencies."""
        if self.ui:
            self.ui.console.print("\n[cyan]Installing dependencies...[/cyan]")

        result = install_dependencies(self.state.working_directory, project_type)

        if result.get("success"):
            if self.ui:
                self.ui.console.print(f"[green]✓ Dependencies installed ({result['command']})[/green]")
        else:
            if self.ui:
                error = result.get("error", "Unknown error")
                self.ui.console.print(f"[yellow]⚠ Dependency installation failed: {error}[/yellow]")
                self.ui.console.print(f"[dim]Run manually: {result.get('command', 'package manager install')}[/dim]")

    def _generate_summary(self, exec_result: Dict, lint_result: Optional[Dict]) -> str:
        """
        Generate completion summary.

        Args:
            exec_result: Execution results
            lint_result: Linting results (if available)

        Returns:
            Summary string
        """
        lines = []
        lines.append("\n" + "=" * 60)

        if exec_result["success"]:
            lines.append("✅ DEVELOPMENT COMPLETE")
        else:
            lines.append("⚠️  DEVELOPMENT COMPLETED WITH ERRORS")

        lines.append("=" * 60)

        # Summary stats
        lines.append("\nSummary:")
        lines.append(f"  Files created: {len(self.state.created_files)}")
        lines.append(f"  Files modified: {len(self.state.modified_files)}")
        lines.append(f"  Tasks completed: {exec_result['tasks_completed']}")
        if exec_result['tasks_failed'] > 0:
            lines.append(f"  Tasks failed: {exec_result['tasks_failed']}")

        # Lint status
        if lint_result:
            lines.append(f"  Lint status: {lint_result['passed']} passed, {lint_result['failed']} failed")

        # Modified files
        if self.state.created_files or self.state.modified_files:
            lines.append("\nModified files:")
            for file in self.state.created_files:
                lines.append(f"  + {file} (new)")
            for file in self.state.modified_files:
                lines.append(f"  ~ {file} (modified)")

        # Next steps
        lines.append("\nNext steps:")

        # Dependency installation
        if self.state.plan.get("dependencies_to_add"):
            project_type = self.state.codebase_summary.get("project_type", "")
            if project_type == "nodejs":
                lines.append("  1. Dependencies installed automatically")
            elif project_type == "python":
                lines.append("  1. Dependencies installed automatically")
            else:
                lines.append("  1. Install dependencies manually")

        # Configuration
        if any(".env" in f for f in self.state.created_files):
            lines.append("  2. Configure environment variables in .env files")

        # Testing
        lines.append("  3. Test the changes:")
        if self.state.plan.get("testing_recommendations"):
            for i, rec in enumerate(self.state.plan["testing_recommendations"][:3], 1):
                lines.append(f"     - {rec}")

        # Git
        lines.append("  4. Review and commit:")
        lines.append("     git status")
        lines.append("     git diff")
        lines.append("     git add .")
        lines.append("     git commit -m \"your message\"")

        lines.append("\nReady for testing!")
        lines.append("=" * 60)

        summary = "\n".join(lines)

        # Display to user if UI available
        if self.ui:
            self.ui.console.print(summary)

        return summary
