"""Multi-step task planner for complex workflows."""

from typing import List, Dict, Any, Optional
import json
import re
import logging

logger = logging.getLogger(__name__)


class TaskPlanner:
    """Plans and executes multi-step tasks."""

    PLANNER_PROMPT = """You are a task planner. Break down the user's request into a sequence of tool calls.

Output ONLY valid JSON object (no markdown, no explanation):
{{
  "steps": [
    {{"id": 1, "tool": "tool_name", "input": "what to pass", "reason": "why this step"}},
    {{"id": 2, "tool": "tool_name", "input": "what to pass", "reason": "why this step", "depends_on": [1]}}
  ]
}}

CRITICAL:
- Each step MUST have: id (integer), tool (string), input (string), reason (string)
- Optional: depends_on (array of step IDs that must complete first)
- Step IDs must be sequential starting from 1
- Output ONLY the JSON object, no markdown code blocks, no explanations

Available tools:
- web_search: Search the internet for current information
- get_newsroom_headlines: Fetch today's compiled articles from Asoba newsroom (no input required)
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
- CRITICAL: For multi-source queries (mentions newsroom AND web search), ALWAYS:
  Step 1: get_newsroom_headlines (to fetch newsroom data)
  Step 2: web_search (to fetch web data)
  Step 3: use_reasoning_model (to synthesize both sources)

Example 1:
User: "Research React hooks and create a custom hook for form handling"
Output:
{{
  "steps": [
    {{"id": 1, "tool": "web_search", "input": "React hooks best practices 2025", "reason": "Get current patterns"}},
    {{"id": 2, "tool": "use_search_model", "input": "Explain custom React hooks for forms", "reason": "Understand concept"}},
    {{"id": 3, "tool": "use_codestral", "input": "Create a custom React hook for form handling with validation", "reason": "Generate implementation", "depends_on": [1, 2]}}
  ]
}}

Example 2:
User: "Analyze the config file and suggest improvements"
Output:
{{
  "steps": [
    {{"id": 1, "tool": "read_file", "input": "config.py", "reason": "Read current config"}},
    {{"id": 2, "tool": "use_reasoning_model", "input": "Analyze this config file and suggest improvements", "reason": "Generate recommendations", "depends_on": [1]}}
  ]
}}

Example 3:
User: "Based on the newsroom as well as web search, what are the major themes of 2025 in Africa?"
Output:
{{
  "steps": [
    {{"id": 1, "tool": "get_newsroom_headlines", "input": "", "reason": "Fetch compiled newsroom articles"}},
    {{"id": 2, "tool": "web_search", "input": "2025 Africa major themes AI energy geopolitics", "reason": "Get web search results"}},
    {{"id": 3, "tool": "use_reasoning_model", "input": "Based on newsroom and web results, identify 5-6 major themes of 2025 in Africa across AI, energy, and geopolitics", "reason": "Synthesize multi-source analysis", "depends_on": [1, 2]}}
  ]
}}

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
            # Multi-source queries: mentions multiple data sources
            r'\b(?:based on|using|from|with)\b.*\b(?:and|as well as|with|plus)\b.*\b(?:newsroom|web search|search)\b',
            r'\b(?:newsroom|headlines).*\b(?:and|as well as|with|plus)\b.*\bweb search\b',
            r'\bweb search.*\b(?:and|as well as|with|plus)\b.*\b(?:newsroom|headlines)\b',
            # Multiple tool mentions in one query
            r'\b(?:search|newsroom).*\b(?:and|as well as).*\b(?:analyze|summarize|identify|find)\b',
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

    def create_plan(self, user_input: str, max_retries: int = 3) -> List[Dict[str, Any]]:
        """
        Create execution plan for user request with strict schema validation.

        Args:
            user_input: User's request
            max_retries: Maximum retry attempts for invalid JSON

        Returns:
            List of steps with enforced schema

        Raises:
            ValueError: If unable to generate valid plan after retries
        """
        prompt = self.PLANNER_PROMPT.format(user_input=user_input)

        for attempt in range(max_retries):
            try:
                response = self.llm_client.chat_complete(
                    [{"role": "user", "content": prompt}],
                    tools=None
                )

                content = self.llm_client.extract_content(response)

                # Extract JSON (handle markdown code blocks)
                json_str = self._extract_json(content)

                if not json_str:
                    logger.warning(f"Attempt {attempt + 1}: No JSON found in output")
                    if attempt < max_retries - 1:
                        prompt = "Output ONLY valid JSON. No markdown, no explanation:\n" + prompt
                        continue
                    return []

                # Parse JSON
                plan_obj = json.loads(json_str)

                # Validate schema
                steps = self._validate_plan_schema(plan_obj)

                if not steps:
                    logger.warning(f"Attempt {attempt + 1}: Schema validation failed")
                    if attempt < max_retries - 1:
                        prompt = "You must output valid JSON with 'steps' array. Each step needs id, tool, input, reason:\n" + prompt
                        continue
                    return []

                logger.info(f"Created valid plan with {len(steps)} steps")
                return steps

            except json.JSONDecodeError as e:
                logger.warning(f"Attempt {attempt + 1}: JSON parse error: {e}")
                if attempt < max_retries - 1:
                    prompt = "Invalid JSON. Output ONLY valid JSON object:\n" + prompt
                    continue
                return []

            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: Unexpected error: {e}")
                if attempt < max_retries - 1:
                    continue
                return []

        logger.error("Failed to generate valid plan after all retries")
        return []

    def _extract_json(self, content: str) -> Optional[str]:
        """Extract JSON from response content."""
        # Try markdown code block first
        code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if code_block_match:
            return code_block_match.group(1)

        # Try finding JSON object directly
        json_match = re.search(r'\{[^{}]*"steps"[^{}]*\[.*?\]\s*\}', content, re.DOTALL)
        if json_match:
            return json_match.group(0)

        # Last resort: try to find any JSON object
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json_match.group(0)

        return None

    def _validate_plan_schema(self, plan_obj: Any) -> List[Dict[str, Any]]:
        """
        Validate plan schema and return steps list.

        Expected schema:
        {
          "steps": [
            {"id": 1, "tool": "...", "input": "...", "reason": "...", "depends_on": [...]}
          ]
        }

        Args:
            plan_obj: Parsed JSON object

        Returns:
            List of validated steps, or empty list if invalid
        """
        # Check top-level structure
        if not isinstance(plan_obj, dict):
            logger.warning("Plan is not a dict")
            return []

        if "steps" not in plan_obj:
            logger.warning("Plan missing 'steps' key")
            return []

        steps = plan_obj["steps"]

        if not isinstance(steps, list):
            logger.warning("'steps' is not a list")
            return []

        if len(steps) == 0:
            logger.warning("'steps' is empty")
            return []

        # Validate each step
        valid_tools = [
            "web_search", "get_newsroom_headlines", "use_codestral",
            "use_reasoning_model", "use_search_model", "use_energy_analyst",
            "read_file", "write_file", "edit_file", "make_directory",
            "list_files", "run_shell", "generate_image"
        ]

        validated_steps = []
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                logger.warning(f"Step {i} is not a dict: {step}")
                return []

            # Check required fields
            required_fields = ["tool", "input"]
            if not all(k in step for k in required_fields):
                logger.warning(f"Step {i} missing required fields: {step}")
                return []

            # Validate tool name
            if step["tool"] not in valid_tools:
                logger.warning(f"Step {i} has invalid tool: {step['tool']}")
                return []

            # Add missing fields with defaults
            if "id" not in step:
                step["id"] = i + 1

            if "reason" not in step:
                step["reason"] = f"Execute {step['tool']}"

            if "depends_on" not in step:
                step["depends_on"] = []

            validated_steps.append(step)

        return validated_steps

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
                "get_newsroom_headlines": None,  # Takes no parameters
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

            # Handle tools that take no parameters
            if param_name is None:
                arguments = {}
            else:
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
