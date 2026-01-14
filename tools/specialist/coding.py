"""
Coding agent tool using configured code generation model.
"""

import logging
import re
from tools.specialist.client import create_specialist_client

logger = logging.getLogger(__name__)


def _generate_plan(planning_prompt: str) -> str:
    """
    Generate an implementation plan using the reasoning model.

    Args:
        planning_prompt: Prompt describing what to plan

    Returns:
        Generated plan as string
    """
    try:
        import config

        model_config = config.SPECIALIZED_MODELS["reasoning"]
        client = create_specialist_client("reasoning", model_config)

        messages = [
            {
                "role": "system",
                "content": "You are a software architect. Create clear, actionable implementation plans. Be concise and specific."
            },
            {
                "role": "user",
                "content": planning_prompt
            }
        ]

        # Get plan without streaming (we want to review before showing)
        response = client.chat_complete(messages, tools=None)
        content = client.extract_content(response)

        if not content or not content.strip():
            return "Error: Planning model returned empty response"

        # Strip thinking tags if present (for reasoning models)
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        content = re.sub(r'<thinking>.*?</thinking>', '', content, flags=re.DOTALL)

        return content.strip()

    except Exception as e:
        logger.error(f"Planning error: {e}")
        return f"Error: Failed to generate plan: {str(e)}"


def use_coding_agent(code_context: str, ui=None) -> str:
    """
    Generate or refactor code using the configured coding model with planning approval.

    This is a model-agnostic coding agent that uses whatever model is configured
    for the 'codestral' role (can be local 4B, HuggingFace 32B, etc.).

    Args:
        code_context: Description of code to generate, existing code to refactor,
                     or programming task to solve
        ui: Optional UI instance for interactive planning approval

    Returns:
        Generated code with explanations
    """
    if not code_context or not isinstance(code_context, str):
        return "Error: code_context must be a non-empty string"

    if len(code_context) > 30000:
        return "Error: code_context too long (max 30000 characters)"

    try:
        import config
        from rich.panel import Panel
        from rich.prompt import Prompt
        from rich.markdown import Markdown

        logger.info(f"Delegating to coding_agent: {code_context[:100]}...")

        # PHASE 1: Generate implementation plan (if UI is available)
        plan_approved = False
        final_plan = None

        if ui is not None:
            ui.console.print("\n[cyan]━━━ Planning Phase ━━━[/cyan]\n")

            # Generate plan using reasoning model
            planning_prompt = f"""Create a detailed implementation plan for the following coding task:

{code_context}

Provide a clear, structured plan that includes:
1. Overview of the approach
2. Key components/functions to implement
3. Important considerations (edge cases, error handling, etc.)
4. Any assumptions being made

Keep the plan concise but complete (aim for 5-15 bullet points)."""

            logger.info("Generating implementation plan...")
            plan = _generate_plan(planning_prompt)

            if plan.startswith("Error:"):
                ui.console.print(f"[yellow]Warning: Could not generate plan: {plan}[/yellow]")
                ui.console.print("[yellow]Proceeding without plan approval...[/yellow]\n")
            else:
                # Display plan and get user approval
                while not plan_approved:
                    ui.console.print(Panel(
                        Markdown(plan),
                        title="[bold cyan]Implementation Plan[/bold cyan]",
                        border_style="cyan"
                    ))
                    ui.console.print()

                    # Prompt for approval
                    choice = Prompt.ask(
                        "[bold yellow]Approve this plan?[/bold yellow]",
                        choices=["accept", "modify", "cancel"],
                        default="accept"
                    )

                    if choice == "accept":
                        plan_approved = True
                        final_plan = plan
                        ui.console.print("[green]✓ Plan approved! Proceeding with implementation...[/green]\n")
                    elif choice == "modify":
                        ui.console.print()
                        modifications = Prompt.ask("[bold]What changes would you like to the plan?[/bold]")

                        # Regenerate plan with user's modifications
                        ui.console.print("[dim]Regenerating plan with your changes...[/dim]")
                        modified_prompt = f"""Create a detailed implementation plan for the following coding task:

{code_context}

User requested these modifications to the previous plan:
{modifications}

Provide a clear, structured plan that includes:
1. Overview of the approach
2. Key components/functions to implement
3. Important considerations (edge cases, error handling, etc.)
4. Any assumptions being made

Keep the plan concise but complete (aim for 5-15 bullet points)."""

                        plan = _generate_plan(modified_prompt)
                        if plan.startswith("Error:"):
                            ui.console.print(f"[red]Error regenerating plan: {plan}[/red]")
                            ui.console.print("[yellow]Reverting to previous plan...[/yellow]\n")
                            # Keep the old plan and show it again
                        else:
                            ui.console.print("[green]✓ Plan updated![/green]\n")
                    else:  # cancel
                        ui.console.print("[red]✗ Implementation cancelled by user[/red]\n")
                        return "Implementation cancelled by user"

        # PHASE 2: Generate code based on approved plan
        ui.console.print("[cyan]━━━ Implementation Phase ━━━[/cyan]\n") if ui else None

        model_config = config.SPECIALIZED_MODELS["codestral"]
        client = create_specialist_client("codestral", model_config)

        # Include the plan in the code generation prompt if we have one
        if final_plan:
            code_prompt = f"""Based on the following approved implementation plan:

{final_plan}

Now implement the solution for:
{code_context}

Generate clean, well-documented, production-quality code. Include docstrings and comments for complex logic."""
        else:
            code_prompt = code_context

        messages = [
            {
                "role": "system",
                "content": "You are an expert software engineer. Generate clean, well-documented, production-quality code. Include docstrings and comments for complex logic. Do NOT include thinking or planning - just provide the implementation."
            },
            {
                "role": "user",
                "content": code_prompt
            }
        ]

        # Stream the response for real-time feedback
        print("\n", flush=True)  # New line before streaming
        full_response = []

        for chunk in client.chat_complete_stream(messages):
            print(chunk, end='', flush=True)
            full_response.append(chunk)

        print("\n", flush=True)  # New line after streaming

        content = ''.join(full_response)
        if not content or not content.strip():
            return "Error: Codestral returned empty response"

        return content.strip()

    except Exception as e:
        logger.error(f"Codestral error: {e}")
        return f"Error: Failed to call Codestral: {str(e)}"
