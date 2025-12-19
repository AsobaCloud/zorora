"""Multi-step task planner for complex workflows."""

from typing import List, Dict, Any, Optional
import json
import re
import logging

logger = logging.getLogger(__name__)


class TaskPlanner:
    """Plans and executes multi-step tasks."""

    PLANNER_PROMPT = """You are a task planner. Break down the user's request into a sequence of tool calls.

Output ONLY valid JSON array (no markdown, no explanation):
[
  {{"tool": "tool_name", "input": "what to pass", "reason": "why this step"}},
  {{"tool": "tool_name", "input": "what to pass", "reason": "why this step"}}
]

Available tools:
- web_search: Search the internet for current information
- use_codestral: Generate or modify code (ANY code task)
- use_reasoning_model: Complex reasoning, analysis, planning
- use_search_model: Research using AI knowledge (not web)
- use_energy_analyst: Energy policy, FERC, ISO, NEM, regulations
- read_file: Read file contents
- write_file: Save content to a file
- edit_file: Modify part of an existing file
- make_directory: Create a new directory
- list_files: List directory contents
- run_shell: Execute shell commands
- generate_image: Create images from text descriptions

Guidelines:
- Keep plans concise (2-5 steps maximum)
- Order steps logically (research before implementation)
- Each step should build on previous results
- Use appropriate tools for each sub-task
- CRITICAL: For file analysis/summary requests, ALWAYS use 2 steps:
  Step 1: read_file (to get content)
  Step 2: use_reasoning_model (to analyze/summarize content)

Example 1:
User: "Research React hooks and create a custom hook for form handling"
Output:
[
  {{"tool": "web_search", "input": "React hooks best practices 2025", "reason": "Get current patterns"}},
  {{"tool": "use_search_model", "input": "Explain custom React hooks for forms", "reason": "Understand concept"}},
  {{"tool": "use_codestral", "input": "Create a custom React hook for form handling with validation", "reason": "Generate implementation"}}
]

Example 2:
User: "Analyze the config file and suggest improvements"
Output:
[
  {{"tool": "read_file", "input": "config.py", "reason": "Read current config"}},
  {{"tool": "use_reasoning_model", "input": "Analyze this config file and suggest improvements", "reason": "Generate recommendations"}}
]

Example 3:
User: "Provide a summary of the file gold_deep_dive.md"
Output:
[
  {{"tool": "read_file", "input": "gold_deep_dive.md", "reason": "Read file content"}},
  {{"tool": "use_reasoning_model", "input": "Provide a summary of this document", "reason": "Summarize the content"}}
]

Example 4:
User: "Create a new directory ~/projects/myapp and add a README file"
Output:
[
  {{"tool": "make_directory", "input": "~/projects/myapp", "reason": "Create project directory"}},
  {{"tool": "write_file", "input": "~/projects/myapp/README.md", "reason": "Create README in new directory"}}
]

User request: {user_input}

Remember: Output ONLY the JSON array, nothing else."""

    def __init__(self, llm_client, tool_executor):
        """
        Initialize TaskPlanner.

        Args:
            llm_client: LLMClient instance for planning
            tool_executor: ToolExecutor instance for executing steps
        """
        self.llm_client = llm_client
        self.tool_executor = tool_executor

    def should_plan(self, user_input: str) -> bool:
        """
        Determine if request needs multi-step planning.

        Indicators:
        - Contains "and then", "after that", "first..then"
        - Multiple distinct actions
        - Research + implementation patterns

        Args:
            user_input: User's request

        Returns:
            True if multi-step planning should be used
        """
        multi_step_indicators = [
            r'\band then\b',
            r'\bafter that\b',
            r'\bfirst.*then\b',
            r'\bthen\b.*\b(create|implement|build|write)\b',
            r'\bnext\b.*\b(create|implement|build|write)\b',
            r'\band (?:create|implement|build|write)\b',
            r'\bresearch.*and.*(?:create|implement|build|write)\b',
            r'\b(?:analyze|review|check).*and.*(?:create|implement|suggest|improve)\b',
            r'\b(?:read|show).*and.*(?:create|implement|modify|update|suggest|improve)\b',
            # Implicit multi-step: file analysis operations
            r'\b(?:summarize|analyze|review|explain|break down|evaluate)\b.*\b(?:file|document)\b',
            r'\bprovide\b.*\b(?:summary|analysis|overview)\b.*\b(?:of|for)\b.*\b(?:file|document)\b',
            # File analysis with filename mentioned (ends with extension)
            r'\b(?:summarize|analyze|review|explain|provide.*summary|break down)\b.*\.(md|txt|py|js|json|yaml|yml|csv|log|html|css)',
        ]

        for pattern in multi_step_indicators:
            if re.search(pattern, user_input, re.IGNORECASE):
                logger.info(f"Multi-step indicator found: {pattern}")
                return True

        return False

    def create_plan(self, user_input: str) -> List[Dict[str, Any]]:
        """
        Create execution plan for user request.

        Args:
            user_input: User's request

        Returns:
            List of steps: [{{"tool": "...", "input": "...", "reason": "..."}}]
        """
        prompt = self.PLANNER_PROMPT.format(user_input=user_input)

        try:
            response = self.llm_client.chat_complete(
                [{"role": "user", "content": prompt}],
                tools=None
            )

            content = self.llm_client.extract_content(response)

            # Parse JSON plan
            # Extract JSON array (handle markdown code blocks)
            code_block_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', content, re.DOTALL)
            if code_block_match:
                json_str = code_block_match.group(1)
            else:
                # Try to find JSON array directly
                json_match = re.search(r'\[.*\]', content, re.DOTALL)
                if not json_match:
                    logger.warning("No JSON array found in planner output")
                    return []
                json_str = json_match.group(0)

            plan = json.loads(json_str)

            # Validate plan structure
            if not isinstance(plan, list):
                logger.warning("Plan is not a list")
                return []

            if len(plan) == 0:
                logger.warning("Plan is empty")
                return []

            # Validate each step
            for i, step in enumerate(plan):
                if not isinstance(step, dict):
                    logger.warning(f"Step {i} is not a dict: {step}")
                    return []
                if not all(k in step for k in ["tool", "input"]):
                    logger.warning(f"Step {i} missing required fields: {step}")
                    return []

            logger.info(f"Created plan with {len(plan)} steps")

            # Validate and fix incomplete plans for file analysis
            plan = self._validate_and_fix_plan(user_input, plan)

            return plan

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse plan JSON: {e}")
            return []
        except Exception as e:
            logger.warning(f"Error creating plan: {e}")
            return []

    def _validate_and_fix_plan(self, user_input: str, plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate plan and fix common issues (e.g., missing analysis step for file operations).

        Args:
            user_input: Original user request
            plan: Generated plan

        Returns:
            Fixed plan
        """
        # Check if this is a file analysis/summary request
        file_analysis_pattern = r'\b(?:summarize|analyze|review|explain|break down)\b.*\.(md|txt|py|js|json|yaml|yml|csv|log|html|css)'
        is_file_analysis = bool(re.search(file_analysis_pattern, user_input, re.IGNORECASE))

        if not is_file_analysis:
            return plan

        # Check if plan only has read_file step
        if len(plan) == 1 and plan[0].get("tool") == "read_file":
            logger.warning("Incomplete plan detected: only read_file step for analysis request")
            logger.info("Adding missing reasoning step")

            # Extract filename from user input
            filename_match = re.search(r'([\w_-]+\.(md|txt|py|js|json|yaml|yml|csv|log|html|css))', user_input, re.IGNORECASE)
            filename = filename_match.group(1) if filename_match else "the file"

            # Add reasoning step
            analysis_step = {
                "tool": "use_reasoning_model",
                "input": f"Provide a concise summary of the main points, key findings, and conclusions",
                "reason": "Analyze and summarize the file content"
            }
            plan.append(analysis_step)
            logger.info(f"Fixed plan now has {len(plan)} steps")

        return plan

    def execute_plan(
        self,
        plan: List[Dict[str, Any]],
        ui=None,
        context: Optional[str] = None
    ) -> str:
        """
        Execute plan steps sequentially.

        Args:
            plan: List of steps from create_plan()
            ui: Optional UI for feedback
            context: Optional context to pass between steps

        Returns:
            Combined result from all steps
        """
        results = []
        accumulated_context = context or ""

        for i, step in enumerate(plan, 1):
            tool = step["tool"]
            user_input = step["input"]
            reason = step.get("reason", "")

            # Show step info
            if ui:
                ui.console.print(f"\n[cyan]Step {i}/{len(plan)}:[/cyan] {reason}")
                ui.console.print(f"[dim]  Tool: {tool}[/dim]")
                ui.console.print(f"[dim]  Input: {user_input[:80]}{'...' if len(user_input) > 80 else ''}[/dim]")

            logger.info(f"Executing step {i}/{len(plan)}: {tool}({user_input[:50]}...)")

            # Map tool to parameter name
            param_mapping = {
                "web_search": "query",
                "use_codestral": "code_context",
                "use_reasoning_model": "task",
                "use_search_model": "query",
                "use_energy_analyst": "query",
                "read_file": "path",
                "write_file": "content",  # Special case
                "edit_file": "path",  # Will need old_string and new_string from planner
                "make_directory": "path",
                "list_files": "path",
                "run_shell": "command",
                "generate_image": "prompt",
            }

            param_name = param_mapping.get(tool, "input")

            # For reasoning and codestral, inject accumulated context
            if tool in ["use_reasoning_model", "use_codestral"] and accumulated_context:
                # Clear formatting for the specialist model
                enhanced_input = f"{accumulated_context}\n\n---\n\nBased on the content above, {user_input}"
            else:
                enhanced_input = user_input

            arguments = {param_name: enhanced_input}

            # Execute tool
            try:
                result = self.tool_executor.execute(tool, arguments)

                # Show result preview
                if ui:
                    if result.startswith("Error:"):
                        ui.console.print(f"[red]  ✗ Error: {result[:100]}[/red]")
                    else:
                        ui.console.print(f"[green]  ✓ Success ({len(result)} chars)[/green]")

                results.append({
                    "step": i,
                    "tool": tool,
                    "reason": reason,
                    "result": result
                })

                # Accumulate context for next steps
                if not result.startswith("Error:"):
                    # Don't truncate read_file results - need full content for analysis
                    if tool == "read_file":
                        accumulated_context += f"\n\n[File Content from {arguments.get('path', 'file')}]:\n{result}"
                    else:
                        # Truncate other results to prevent bloat
                        truncated_result = result[:1000] + "..." if len(result) > 1000 else result
                        accumulated_context += f"\n\n[Step {i} - {tool}]:\n{truncated_result}"

            except Exception as e:
                error_msg = f"Error executing step {i}: {e}"
                logger.error(error_msg)
                results.append({
                    "step": i,
                    "tool": tool,
                    "reason": reason,
                    "result": f"Error: {e}"
                })
                # Continue with remaining steps despite error

        # Format combined results
        if len(results) == 0:
            return "Error: No steps were executed"

        # Return last successful result (most likely what user wants)
        # Or combine all results if needed
        final_results = []
        for r in results:
            if not r["result"].startswith("Error:"):
                final_results.append(r["result"])

        if not final_results:
            # All steps failed
            error_summary = "\n\n".join([f"Step {r['step']}: {r['result']}" for r in results])
            return f"Plan execution failed:\n\n{error_summary}"

        # Return last successful result (usually the final output)
        return final_results[-1]
