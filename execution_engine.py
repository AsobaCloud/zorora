"""State machine execution engine for multi-step plans.

This replaces the chat-loop pattern with explicit state management.
The code controls iteration, not the model.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import logging
import json

logger = logging.getLogger(__name__)


@dataclass
class Step:
    """Single step in execution plan."""
    id: int
    tool: str
    input: str
    reason: str = ""
    depends_on: List[int] = field(default_factory=list)


@dataclass
class StepResult:
    """Result of executing a step."""
    step: Step
    success: bool
    result: Optional[str]
    summary: str
    error: Optional[str] = None


@dataclass
class ExecutionState:
    """Mutable state for plan execution."""
    plan: List[Step]
    original_query: str
    completed: List[StepResult] = field(default_factory=list)
    scratchpad: str = ""
    current_step_idx: int = 0

    def is_complete(self) -> bool:
        """Check if all steps are done."""
        return self.current_step_idx >= len(self.plan)

    def next_step(self) -> Optional[Step]:
        """Get next step to execute."""
        if self.is_complete():
            return None
        return self.plan[self.current_step_idx]

    def get_completed_step_ids(self) -> List[int]:
        """Get IDs of completed steps."""
        return [r.step.id for r in self.completed if r.success]


class ExecutionEngine:
    """
    Executes plans as state machine.

    Key principles:
    1. Code controls iteration, not the model
    2. Tool outputs are summarized before adding to context
    3. Scratchpad maintains explicit working memory
    4. Model cannot exit early - plan must complete
    5. Tool failures are logged and execution continues
    """

    def __init__(self, tool_executor, llm_client=None):
        """
        Initialize execution engine.

        Args:
            tool_executor: ToolExecutor instance
            llm_client: Optional LLMClient for summarization (if None, no summarization)
        """
        self.tool_executor = tool_executor
        self.llm_client = llm_client

    def execute_plan(
        self,
        plan_steps: List[Dict[str, Any]],
        original_query: str,
        ui=None
    ) -> str:
        """
        Execute plan as state machine.

        Args:
            plan_steps: List of step dicts from planner
            original_query: Original user query
            ui: Optional UI for progress feedback

        Returns:
            Final synthesized answer
        """
        # Convert dicts to Step objects
        steps = [
            Step(
                id=s["id"],
                tool=s["tool"],
                input=s["input"],
                reason=s.get("reason", ""),
                depends_on=s.get("depends_on", [])
            )
            for s in plan_steps
        ]

        state = ExecutionState(
            plan=steps,
            original_query=original_query
        )

        logger.info(f"Starting execution of {len(steps)}-step plan")

        # Execute steps sequentially
        while not state.is_complete():
            step = state.next_step()

            if ui:
                ui.console.print(f"\n[cyan]Step {step.id}/{len(steps)}:[/cyan] {step.reason}")
                ui.console.print(f"[dim]  Tool: {step.tool}[/dim]")
                ui.console.print(f"[dim]  Input: {step.input[:80]}{'...' if len(step.input) > 80 else ''}[/dim]")

            # Check dependencies
            if not self._dependencies_met(step, state):
                error_msg = f"Dependencies {step.depends_on} not met for step {step.id}"
                logger.error(error_msg)

                # Record failure but continue
                result = StepResult(
                    step=step,
                    success=False,
                    result=None,
                    summary=f"SKIPPED: {error_msg}",
                    error=error_msg
                )
                state.completed.append(result)
                state.scratchpad += f"\n[Step {step.id} SKIPPED]: {error_msg}"
                state.current_step_idx += 1

                if ui:
                    ui.console.print(f"[yellow]  ⚠ Skipped: dependencies not met[/yellow]")

                continue

            # Execute tool
            step_result = self._execute_step(step, state, ui)

            # Update state
            state.completed.append(step_result)
            state.scratchpad += f"\n[Step {step.id} - {step.tool}]: {step_result.summary}"
            state.current_step_idx += 1

            if ui:
                if step_result.success:
                    ui.console.print(f"[green]  ✓ Success ({len(step_result.result or '')} chars)[/green]")
                else:
                    ui.console.print(f"[red]  ✗ Failed: {step_result.error[:100]}[/red]")

        # All steps complete - synthesize final answer
        logger.info("All steps complete, synthesizing final answer")
        return self._synthesize_final_answer(state, ui)

    def _dependencies_met(self, step: Step, state: ExecutionState) -> bool:
        """Check if step dependencies are satisfied."""
        if not step.depends_on:
            return True

        completed_ids = state.get_completed_step_ids()
        return all(dep_id in completed_ids for dep_id in step.depends_on)

    def _execute_step(
        self,
        step: Step,
        state: ExecutionState,
        ui=None
    ) -> StepResult:
        """
        Execute a single step.

        Returns:
            StepResult with outcome
        """
        logger.info(f"Executing step {step.id}: {step.tool}({step.input[:50]}...)")

        try:
            # Map tool to proper arguments
            arguments = self._build_tool_arguments(step.tool, step.input)

            # Execute tool
            result = self.tool_executor.execute(step.tool, arguments)

            # Check for errors
            if result.startswith("Error:"):
                return StepResult(
                    step=step,
                    success=False,
                    result=result,
                    summary=result[:200],
                    error=result
                )

            # Summarize result (critical for 4B models)
            summary = self._summarize_result(result, step.tool)

            return StepResult(
                step=step,
                success=True,
                result=result,
                summary=summary
            )

        except Exception as e:
            error_msg = f"Error executing {step.tool}: {str(e)}"
            logger.error(error_msg, exc_info=True)

            return StepResult(
                step=step,
                success=False,
                result=None,
                summary=f"FAILED: {str(e)[:100]}",
                error=error_msg
            )

    def _build_tool_arguments(self, tool: str, input_str: str) -> Dict[str, Any]:
        """
        Convert plan step input to tool arguments.

        Args:
            tool: Tool name
            input_str: Input string from plan

        Returns:
            Arguments dict for tool
        """
        # Map tool to parameter name
        param_mapping = {
            "web_search": "query",
            "get_newsroom_headlines": None,  # No parameters
            "use_codestral": "code_context",
            "use_reasoning_model": "task",
            "use_search_model": "query",
            "use_energy_analyst": "query",
            "read_file": "path",
            "write_file": "content",
            "edit_file": "path",
            "make_directory": "path",
            "list_files": "path",
            "run_shell": "command",
            "generate_image": "prompt",
        }

        param_name = param_mapping.get(tool)

        if param_name is None:
            return {}  # Tool takes no parameters

        return {param_name: input_str}

    def _summarize_result(self, result: str, tool: str, max_bullets: int = 5) -> str:
        """
        Aggressively summarize tool output.

        Never feed raw tool output to 4B model - always compress first.

        Args:
            result: Raw tool output
            tool: Tool name (for context)
            max_bullets: Maximum bullet points

        Returns:
            Compressed summary
        """
        # If short enough, return as-is
        if len(result) < 300:
            return result

        # If no LLM client, just truncate
        if not self.llm_client:
            return result[:300] + "..."

        # Use LLM to summarize
        summary_prompt = f"""Summarize this {tool} output in {max_bullets} bullet points or less.
Be concise. Preserve key facts only.

OUTPUT:
{result[:2000]}

SUMMARY (bullet points only):"""

        try:
            response = self.llm_client.chat_complete(
                [{"role": "user", "content": summary_prompt}],
                tools=None
            )
            summary = self.llm_client.extract_content(response)
            return summary.strip()
        except Exception as e:
            logger.warning(f"Summarization failed: {e}, using truncation")
            return result[:300] + "..."

    def _synthesize_final_answer(self, state: ExecutionState, ui=None) -> str:
        """
        Synthesize final answer from completed steps.

        This is called ONLY after all steps complete.
        Model cannot exit early.

        Args:
            state: Execution state with completed steps
            ui: Optional UI

        Returns:
            Final answer
        """
        if ui:
            ui.console.print("\n[cyan]Synthesizing final answer...[/cyan]")

        # Build synthesis prompt from scratchpad
        synthesis_prompt = f"""You are synthesizing results from multiple steps.

ORIGINAL QUESTION:
{state.original_query}

COMPLETED STEPS:
{state.scratchpad}

Based on the completed steps above, provide a comprehensive final answer.
- Cite specific steps when making claims
- Be concise but complete
- Structure your response clearly

FINAL ANSWER:"""

        if not self.llm_client:
            # No LLM for synthesis - just return scratchpad
            return f"Plan completed:\n{state.scratchpad}"

        try:
            response = self.llm_client.chat_complete(
                [{"role": "user", "content": synthesis_prompt}],
                tools=None
            )
            final_answer = self.llm_client.extract_content(response)
            return final_answer.strip()

        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return f"Error synthesizing answer: {e}\n\nRaw results:\n{state.scratchpad}"
