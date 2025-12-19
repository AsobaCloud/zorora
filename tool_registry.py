"""Tool registry for tool definitions and function mapping."""

from typing import Dict, Callable, List, Dict as DictType, Any, Optional
from pathlib import Path
import subprocess
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


# Specialist tools that should return their results directly to the user
# instead of continuing the orchestrator iteration loop
SPECIALIST_TOOLS = [
    "use_codestral",
    "use_reasoning_model",
    "use_search_model",
    "use_intent_detector",  # Internal routing tool (not shown to user)
    "analyze_image",
    "generate_image"
]


def _create_specialist_client(role: str, model_config: Dict[str, Any]):
    """
    Create an LLMClient for a specialist role, using either local or remote endpoint.

    Args:
        role: Role name (e.g., "codestral", "reasoning", "search", "intent_detector")
        model_config: Model configuration dict from SPECIALIZED_MODELS

    Returns:
        LLMClient instance configured for the role
    """
    from llm_client import LLMClient
    import config

    # Check if we have endpoint mappings
    endpoint_key = "local"
    if hasattr(config, 'MODEL_ENDPOINTS') and role in config.MODEL_ENDPOINTS:
        endpoint_key = config.MODEL_ENDPOINTS[role]

    # If local, use LM Studio
    if endpoint_key == "local":
        return LLMClient(
            api_url=config.API_URL,
            model=model_config["model"],
            max_tokens=model_config["max_tokens"],
            temperature=model_config["temperature"],
            timeout=model_config["timeout"]
        )

    # Otherwise, use HF endpoint
    if hasattr(config, 'HF_ENDPOINTS') and endpoint_key in config.HF_ENDPOINTS:
        hf_config = config.HF_ENDPOINTS[endpoint_key]
        return LLMClient(
            api_url=hf_config["url"],
            model=hf_config["model_name"],
            max_tokens=model_config["max_tokens"],
            temperature=model_config["temperature"],
            timeout=hf_config.get("timeout", model_config["timeout"]),
            auth_token=config.HF_TOKEN if hasattr(config, 'HF_TOKEN') else None
        )

    # Fallback to local if endpoint not found
    logger.warning(f"Endpoint '{endpoint_key}' not found for role '{role}', falling back to local")
    return LLMClient(
        api_url=config.API_URL,
        model=model_config["model"],
        max_tokens=model_config["max_tokens"],
        temperature=model_config["temperature"],
        timeout=model_config["timeout"]
    )


# Tool function implementations
def _validate_path(path: str) -> tuple[bool, str]:
    """
    Validate file path for security.

    Returns:
        (is_valid, error_message)
    """
    try:
        file_path = Path(path).resolve()
        cwd = Path.cwd().resolve()

        # Prevent path traversal outside current directory
        if not str(file_path).startswith(str(cwd)):
            return False, f"Error: Path '{path}' is outside current directory"

        return True, ""
    except Exception as e:
        return False, f"Error: Invalid path '{path}': {e}"


def read_file(path: str) -> str:
    """Read contents of a file."""
    # Validate path security
    is_valid, error = _validate_path(path)
    if not is_valid:
        return error

    file_path = Path(path)
    if not file_path.exists():
        return f"Error: File '{path}' does not exist."
    if not file_path.is_file():
        return f"Error: '{path}' is not a file."

    # Check file size limit (10MB)
    if file_path.stat().st_size > 10_000_000:
        return f"Error: File '{path}' too large (>10MB)"

    try:
        return file_path.read_text()
    except UnicodeDecodeError:
        return f"Error: File '{path}' is not a text file"
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str) -> str:
    """Write content to a file (creates or overwrites)."""
    # Validate path security
    is_valid, error = _validate_path(path)
    if not is_valid:
        return error

    try:
        Path(path).write_text(content)
        return f"OK: Written {len(content)} characters to '{path}'"
    except Exception as e:
        return f"Error writing file: {e}"


def make_directory(path: str) -> str:
    """Create a new directory (including parent directories if needed)."""
    # Validate path security
    is_valid, error = _validate_path(path)
    if not is_valid:
        return error

    try:
        dir_path = Path(path)
        if dir_path.exists():
            if dir_path.is_dir():
                return f"OK: Directory '{path}' already exists"
            else:
                return f"Error: '{path}' exists but is not a directory"

        dir_path.mkdir(parents=True, exist_ok=True)
        return f"OK: Created directory '{path}'"
    except Exception as e:
        return f"Error creating directory: {e}"


def edit_file(path: str, old_string: str, new_string: str) -> str:
    """
    Edit a file by replacing exact string match.

    Args:
        path: Path to the file to edit
        old_string: Exact string to find and replace
        new_string: String to replace with

    Returns:
        Success or error message
    """
    # Validate path security
    is_valid, error = _validate_path(path)
    if not is_valid:
        return error

    file_path = Path(path)
    if not file_path.exists():
        return f"Error: File '{path}' does not exist."
    if not file_path.is_file():
        return f"Error: '{path}' is not a file."

    try:
        # Read current content
        content = file_path.read_text()

        # Check if old_string exists
        if old_string not in content:
            return f"Error: String not found in file. Make sure the old_string matches exactly (including whitespace)."

        # Count occurrences
        occurrences = content.count(old_string)
        if occurrences > 1:
            return f"Error: String appears {occurrences} times in file. Use write_file for multiple replacements or be more specific."

        # Perform replacement
        new_content = content.replace(old_string, new_string, 1)
        file_path.write_text(new_content)

        return f"OK: Replaced 1 occurrence in '{path}'"
    except UnicodeDecodeError:
        return f"Error: File '{path}' is not a text file"
    except Exception as e:
        return f"Error editing file: {e}"


def list_files(path: str = ".") -> str:
    """List files and directories in a path."""
    # Validate path security
    is_valid, error = _validate_path(path)
    if not is_valid:
        return error

    try:
        dir_path = Path(path)
        if not dir_path.exists():
            return f"Error: Path '{path}' does not exist."
        if not dir_path.is_dir():
            return f"Error: '{path}' is not a directory."
        items = [p.name for p in dir_path.iterdir()]
        return "\n".join(sorted(items)) if items else "(empty directory)"
    except Exception as e:
        return f"Error listing files: {e}"


def analyze_image(path: str, task: str = "Convert this image to markdown format, preserving all text, tables, charts, and structure. Use OCR to extract any text.") -> str:
    """
    Analyze an image using a vision-language model (VL model) for OCR and content extraction.

    Args:
        path: Path to the image file
        task: Description of what to do with the image (default: OCR and convert to markdown)

    Returns:
        Analysis/OCR output from the VL model
    """
    # Validate path security
    is_valid, error = _validate_path(path)
    if not is_valid:
        return error

    file_path = Path(path)
    if not file_path.exists():
        return f"Error: File '{path}' does not exist."
    if not file_path.is_file():
        return f"Error: '{path}' is not a file."

    # Check if it's an image file by extension
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif', '.webp'}
    if file_path.suffix.lower() not in image_extensions:
        return f"Error: '{path}' does not appear to be an image file (supported: {', '.join(image_extensions)})"

    # Check file size limit (10MB for images)
    if file_path.stat().st_size > 10_000_000:
        return f"Error: Image file '{path}' too large (>10MB)"

    try:
        import base64
        import config

        logger.info(f"Analyzing image: {path} with task: {task[:100]}...")

        # Read and encode image as base64
        with open(file_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        # Determine image MIME type
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff',
            '.webp': 'image/webp'
        }
        mime_type = mime_types.get(file_path.suffix.lower(), 'image/png')

        # Create VL model client using specialized vision config
        model_config = config.SPECIALIZED_MODELS["vision"]
        client = _create_specialist_client("vision", model_config)

        # Create multimodal message with OpenAI-compatible format
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": task},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_data}"
                        }
                    }
                ]
            }
        ]

        logger.info(f"Sending image to VL model (size: {len(image_data)} bytes)")

        # Stream the response for real-time feedback
        print("\n", flush=True)  # New line before streaming
        full_response = []

        for chunk in client.chat_complete_stream(messages):
            print(chunk, end='', flush=True)
            full_response.append(chunk)

        print("\n", flush=True)  # New line after streaming

        content = ''.join(full_response)
        if not content or not content.strip():
            return "Error: VL model returned empty response"

        return content.strip()

    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        return f"Error: Failed to analyze image: {str(e)}"


def generate_image(prompt: str, filename: str = "") -> str:
    """
    Generate an image from a text prompt using Flux Schnell model.

    Args:
        prompt: Text description of the image to generate
        filename: Optional filename to save image (default: auto-generated with timestamp)

    Returns:
        Path to the generated image file
    """
    if not prompt or not isinstance(prompt, str):
        return "Error: prompt must be a non-empty string"

    if len(prompt) > 1000:
        return "Error: prompt too long (max 1000 characters)"

    try:
        import config

        logger.info(f"Generating image with Flux Schnell: {prompt[:100]}...")

        # Get image generation config
        model_config = config.SPECIALIZED_MODELS.get("image_generation")
        if not model_config:
            return "Error: Image generation not configured. Use /models to set up the image_generation endpoint."

        # Determine endpoint
        endpoint_key = config.MODEL_ENDPOINTS.get("image_generation", "local")
        if endpoint_key == "local":
            return "Error: Image generation requires a HuggingFace endpoint. Use /models to configure it."

        # Get HF endpoint config
        hf_config = config.HF_ENDPOINTS.get(endpoint_key)
        if not hf_config or not hf_config.get("enabled", True):
            return f"Error: HuggingFace endpoint '{endpoint_key}' not found or disabled."

        # Get HF token
        hf_token = getattr(config, 'HF_TOKEN', None)
        if not hf_token:
            return "Error: HF_TOKEN not configured. Use /models to set your HuggingFace token."

        # Prepare request
        url = hf_config["url"]
        headers = {
            "Authorization": f"Bearer {hf_token}",
            "Content-Type": "application/json"
        }

        # Flux Schnell optimized parameters (16:9 aspect ratio, 1344x768)
        payload = {
            "inputs": prompt,
            "parameters": {
                "guidance_scale": 0.0,  # Flux Schnell optimized
                "num_inference_steps": 4,  # Flux Schnell optimized for 4 steps
                "width": 1344,  # 16:9 aspect ratio
                "height": 768
            }
        }

        timeout = hf_config.get("timeout", 120)

        logger.info(f"Sending request to {url}")
        print(f"\n🎨 Generating image (1344x768, ~{timeout}s)...\n", flush=True)

        # Make request
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)

        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}"
            try:
                error_detail = response.json()
                error_msg += f": {error_detail}"
            except:
                error_msg += f": {response.text[:200]}"
            return f"Error: Image generation failed - {error_msg}"

        # Save image
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"generated_{timestamp}.png"

        # Ensure .png extension
        if not filename.endswith(('.png', '.jpg', '.jpeg')):
            filename += '.png'

        filepath = Path(filename)
        filepath.write_bytes(response.content)

        file_size = len(response.content) / 1024  # KB
        logger.info(f"Image saved to {filepath} ({file_size:.1f} KB)")

        return f"✅ Image generated successfully!\nSaved to: {filepath}\nSize: {file_size:.1f} KB\nResolution: 1344x768 (16:9)"

    except requests.Timeout:
        return f"Error: Image generation timed out after {timeout}s. Flux Schnell is usually fast - check endpoint status."
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        return f"Error: Failed to generate image: {str(e)}"


def run_shell(command: str) -> str:
    """Execute a shell command with enhanced security."""
    # Expanded banned patterns
    banned = [
        "rm ", "sudo", "su ", "shutdown", "reboot", "poweroff", "halt",
        "chmod 777", "chown", "kill -9",
        ">", ">>", "|", ";", "&&", "||",  # Prevent command chaining
        "`", "$(",  # Prevent command substitution
        "mkfs", "dd if=", "dd of=", "format", "deltree",
    ]
    command_lower = command.lower()
    matched_patterns = [p for p in banned if p in command_lower]
    if matched_patterns:
        return f"Error: Command blocked for safety (contains: {matched_patterns})"

    # Whitelist approach - only allow safe commands
    safe = ["ls", "pwd", "echo", "cat", "grep", "find", "wc", "head", "tail",
            "python", "python3", "node", "npm", "git", "pytest", "black", "flake8"]
    first_word = command.split()[0] if command.split() else ""
    if first_word not in safe:
        return f"Error: Command '{first_word}' not in whitelist. Allowed: {', '.join(safe)}"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
            timeout=30,
        )
        output = result.stdout if result.stdout else ""
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[exit: {result.returncode}]"
        return output if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds."
    except Exception as e:
        return f"Error executing command: {e}"


def apply_patch(path: str, unified_diff: str) -> str:
    """Apply a unified diff patch to a file."""
    file_path = Path(path)
    if not file_path.exists():
        return f"Error: File '{path}' does not exist."
    if not file_path.is_file():
        return f"Error: '{path}' is not a file."

    try:
        original_lines = file_path.read_text().splitlines(keepends=True)
        diff_lines = unified_diff.splitlines(keepends=True)
        patched_lines = list(original_lines)

        i = 0
        while i < len(diff_lines):
            line = diff_lines[i]
            if line.startswith("@@"):
                i += 1
                hunk_lines = []
                while i < len(diff_lines) and not diff_lines[i].startswith("@@"):
                    hunk_lines.append(diff_lines[i])
                    i += 1
                i -= 1

                for hunk_line in hunk_lines:
                    if hunk_line.startswith("+"):
                        patched_lines.append(hunk_line[1:])
                    elif hunk_line.startswith("-"):
                        target = hunk_line[1:]
                        if target in patched_lines:
                            patched_lines.remove(target)
            i += 1

        file_path.write_text("".join(patched_lines))
        return f"OK: Applied patch to '{path}'"
    except Exception as e:
        return f"Error applying patch: {e}"


def use_codestral(code_context: str, ui=None) -> str:
    """
    Generate or refactor code using Codestral-22B model with planning approval.

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

        logger.info(f"Delegating to Codestral: {code_context[:100]}...")

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
        client = _create_specialist_client("codestral", model_config)

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
        client = _create_specialist_client("reasoning", model_config)

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
        import re
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        content = re.sub(r'<thinking>.*?</thinking>', '', content, flags=re.DOTALL)

        return content.strip()

    except Exception as e:
        logger.error(f"Planning error: {e}")
        return f"Error: Failed to generate plan: {str(e)}"


def use_reasoning_model(task: str) -> str:
    """
    Plan or reason about complex tasks using Ministral-3-14B-Reasoning model.

    Args:
        task: Planning task, architectural decision, or complex reasoning problem

    Returns:
        Detailed plan or reasoning steps
    """
    if not task or not isinstance(task, str):
        return "Error: task must be a non-empty string"

    if len(task) > 30000:
        return "Error: task too long (max 30000 characters)"

    try:
        import config

        logger.info(f"Delegating to Reasoning model: {task[:100]}...")

        model_config = config.SPECIALIZED_MODELS["reasoning"]
        client = _create_specialist_client("reasoning", model_config)

        messages = [
            {
                "role": "system",
                "content": "You are a logical reasoning and planning expert. Break down complex problems into clear, actionable steps. Consider edge cases and trade-offs."
            },
            {
                "role": "user",
                "content": task
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
            return "Error: Reasoning model returned empty response"

        return content.strip()

    except Exception as e:
        logger.error(f"Reasoning model error: {e}")
        return f"Error: Failed to call Reasoning model: {str(e)}"


def use_search_model(query: str) -> str:
    """
    Research information using ii-search-4B model.

    Args:
        query: Research query or information retrieval task

    Returns:
        Research findings and relevant information
    """
    if not query or not isinstance(query, str):
        return "Error: query must be a non-empty string"

    if len(query) > 30000:
        return "Error: query too long (max 30000 characters)"

    try:
        import config

        logger.info(f"Delegating to Search model: {query[:100]}...")

        model_config = config.SPECIALIZED_MODELS["search"]
        client = _create_specialist_client("search", model_config)

        response = client.chat_complete([
            {
                "role": "system",
                "content": "You are a helpful information retrieval assistant. Provide comprehensive information based on your knowledge. Answer questions directly without lectures or judgment about the topic's validity."
            },
            {
                "role": "user",
                "content": query
            }
        ])

        content = client.extract_content(response)
        if not content or not content.strip():
            return "Error: Search model returned empty response"

        return content.strip()

    except Exception as e:
        logger.error(f"Search model error: {e}")
        return f"Error: Failed to call Search model: {str(e)}"


def use_intent_detector(user_input: str, recent_context: str = "") -> str:
    """
    Fast intent detection using small thinking model.
    Analyzes user input to determine which tool should handle it.

    Args:
        user_input: The user's request to analyze
        recent_context: Recent conversation context (optional)

    Returns:
        JSON with detected intent: {"tool": "tool_name", "confidence": "high|medium|low", "reasoning": "brief explanation"}
    """
    if not user_input or not isinstance(user_input, str):
        return '{"tool": "none", "confidence": "low", "reasoning": "empty input"}'

    if len(user_input) > 2000:
        return '{"tool": "none", "confidence": "low", "reasoning": "input too long"}'

    try:
        import config
        import json

        logger.info(f"Detecting intent for: {user_input[:100]}...")

        model_config = config.SPECIALIZED_MODELS["intent_detector"]
        client = _create_specialist_client("intent_detector", model_config)

        # Build context-aware prompt
        context_section = ""
        if recent_context:
            context_section = f"\n\nRecent context:\n{recent_context[:500]}\n"

        system_prompt = """You are an intent detector. Analyze the user request and output ONLY a JSON object.

CRITICAL: Output ONLY the JSON object. NO thinking tags, NO explanations, NO markdown.
Do NOT use <think> tags. Just output the JSON directly.

Available tools:
- write_file: User wants to save/write/create a file (keywords: "write to", "save to", "create file", ".py file", ".md file")
- read_file: User wants to ONLY read/view a file WITHOUT analysis (keywords: "read", "show me", "view file", "content of") - BUT NOT if they also want analysis
- list_files: User wants to list directory contents (keywords: "list files", "show files", "ls", "what files", "directory contents")
- analyze_image: User wants to analyze/OCR/convert an EXISTING image (keywords: "analyze image", "convert image", "OCR", "extract text from image", ".png", ".jpg", "image to markdown", "what's in this image")
- generate_image: User wants to CREATE/GENERATE a new image from text (keywords: "generate image", "create image", "make an image", "draw", "visualize", "illustration of", "picture of")
- use_codestral: User wants to generate/modify code (keywords: "write function", "create script", "generate code")
- use_reasoning_model: User wants analysis/planning/thinking (keywords: "analyze", "deep dive", "implications", "think deeply", "examine", "investigate") - PRIORITIZE this over read_file if analysis keywords present
- web_search: User wants current web information (keywords: "search", "latest", "current news", "what's happening")
- get_newsroom_headlines: User wants today's news from Asoba newsroom (keywords: "today's news", "newsroom", "headlines today")
- use_energy_analyst: User wants energy policy/regulatory info (keywords: "FERC", "ISO", "NEM", "tariff", "energy regulation")
- use_search_model: User wants general knowledge questions (keywords: "what is", "explain", "how does")

CRITICAL PRIORITY RULES:
1. If user mentions BOTH a file AND analysis keywords ("analyze", "deep dive", "implications", "think about"), choose use_reasoning_model NOT read_file. The reasoning model can request file reads if needed.
2. If user mentions an EXISTING image file (.png, .jpg, etc.) or image analysis/OCR keywords, choose analyze_image.
3. If user wants to CREATE/GENERATE a new image from text description, choose generate_image.

Output format (ONLY this, nothing else):
{"tool": "tool_name", "confidence": "high|medium|low", "reasoning": "one sentence why"}

Examples:
Input: "write this to report.md"
Output: {"tool": "write_file", "confidence": "high", "reasoning": "explicit file write request with filename"}

Input: "read the file nuclear.md"
Output: {"tool": "read_file", "confidence": "high", "reasoning": "simple file read without analysis"}

Input: "show me what's in config.py"
Output: {"tool": "read_file", "confidence": "high", "reasoning": "view file contents without analysis"}

Input: "deep dive analysis about news_themes.md"
Output: {"tool": "use_reasoning_model", "confidence": "high", "reasoning": "analysis request - reasoning model will read file if needed"}

Input: "analyze the implications in the file we just read"
Output: {"tool": "use_reasoning_model", "confidence": "high", "reasoning": "analysis/implications request requires reasoning"}

Input: "list files in the current directory"
Output: {"tool": "list_files", "confidence": "high", "reasoning": "request to list directory contents"}

Input: "convert gdp.png to markdown"
Output: {"tool": "analyze_image", "confidence": "high", "reasoning": "image file with conversion request requires vision model"}

Input: "what's in this screenshot.jpg?"
Output: {"tool": "analyze_image", "confidence": "high", "reasoning": "image analysis request"}

Input: "generate an image of a sunset over mountains"
Output: {"tool": "generate_image", "confidence": "high", "reasoning": "text-to-image generation request"}

Input: "create a python script for clustering"
Output: {"tool": "use_codestral", "confidence": "high", "reasoning": "code generation request"}

Input: "save the plan to plan.md"
Output: {"tool": "write_file", "confidence": "high", "reasoning": "save/write with filename"}

Remember: Output ONLY the JSON. No thinking process, no tags, no extra text."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{context_section}\nUser request: {user_input}\n\nOutput (JSON only, no thinking):"}
        ]

        # Non-streaming for fast JSON response
        response = client.chat_complete(messages)
        content = client.extract_content(response)

        if not content or not content.strip():
            return '{"tool": "none", "confidence": "low", "reasoning": "empty response from model"}'

        # Try to extract JSON from response (model might wrap it in markdown or thinking tags)
        content = content.strip()
        import re

        # Remove thinking tags first - they often wrap the entire response
        # Remove everything from <think> to </think> (inclusive)
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)

        # If there's a dangling <think> tag, remove everything from it onwards
        if '<think>' in content:
            content = content[:content.index('<think>')]

        content = content.strip()

        # Remove markdown code blocks
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(l for l in lines if not l.startswith("```"))
            content = content.strip()

        # Now try to extract JSON object
        # Look for a line that starts with { and contains "tool"
        # Use a more permissive regex that handles multi-line JSON
        json_match = re.search(r'\{.*?"tool".*?\}', content, re.DOTALL)
        if json_match:
            content = json_match.group(0)
        else:
            # Fallback: if content starts with {, assume it's all JSON
            if content.startswith('{'):
                # Try to find the matching closing brace
                brace_count = 0
                for i, char in enumerate(content):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            content = content[:i+1]
                            break

        # Validate JSON
        try:
            parsed = json.loads(content)
            if "tool" not in parsed:
                parsed["tool"] = "none"
            if "confidence" not in parsed:
                parsed["confidence"] = "low"
            if "reasoning" not in parsed:
                parsed["reasoning"] = "no reasoning provided"
            return json.dumps(parsed)
        except json.JSONDecodeError:
            logger.warning(f"Intent detector returned invalid JSON after cleaning: {content[:200]}")
            return '{"tool": "none", "confidence": "low", "reasoning": "invalid JSON from model"}'

    except Exception as e:
        logger.error(f"Intent detector error: {e}")
        return f'{{"tool": "none", "confidence": "low", "reasoning": "error: {str(e)}"}}'


def use_energy_analyst(query: str) -> str:
    """
    Analyze energy policy and regulatory compliance using EnergyAnalyst RAG.

    Args:
        query: Energy policy or regulatory compliance question

    Returns:
        Detailed analysis with RAG-sourced context from energy policy documents
    """
    if not query or not isinstance(query, str):
        return "Error: query must be a non-empty string"

    if len(query) > 2000:
        return "Error: query too long (max 2000 characters)"

    try:
        import requests
        import config

        # Check if EnergyAnalyst is enabled
        if not config.ENERGY_ANALYST.get("enabled", True):
            return "Error: EnergyAnalyst is disabled. Enable it with /models command."

        logger.info(f"Delegating to EnergyAnalyst: {query[:100]}...")

        # Get endpoint and timeout from config
        endpoint = config.ENERGY_ANALYST.get("endpoint", "http://localhost:8000")
        timeout = config.ENERGY_ANALYST.get("timeout", 180)
        api_url = f"{endpoint.rstrip('/')}/chat"

        logger.info(f"Using EnergyAnalyst endpoint: {endpoint}")

        # Make API request
        response = requests.post(
            api_url,
            json={"message": query, "use_rag": True},
            timeout=timeout
        )
        response.raise_for_status()

        data = response.json()

        # Extract response and sources
        answer = data.get("response", "")
        sources = data.get("rag_sources", [])
        rag_used = data.get("rag_context_used", False)

        if not answer or not answer.strip():
            return "Error: EnergyAnalyst returned empty response"

        # Format response with sources
        formatted = [answer.strip()]

        if rag_used and sources:
            formatted.append("\n\n📚 Sources:")
            for source in sources:
                formatted.append(f"  - {source}")

        return "\n".join(formatted)

    except requests.ConnectionError:
        endpoint = config.ENERGY_ANALYST.get("endpoint", "http://localhost:8000")
        if "localhost" in endpoint:
            return f"Error: Could not connect to EnergyAnalyst API at {endpoint}. Is the local API server running? Start it with: cd ~/Workbench/energyanalyst-v0.1 && python api/server.py"
        else:
            return f"Error: Could not connect to EnergyAnalyst API at {endpoint}. Check endpoint configuration with /models command."

    except requests.Timeout:
        return "Error: EnergyAnalyst API request timed out after 180 seconds. The model may be generating a very long response or LM Studio may be overloaded."

    except requests.HTTPError as e:
        return f"Error: EnergyAnalyst API error (HTTP {e.response.status_code}): {e.response.text}"

    except Exception as e:
        logger.error(f"EnergyAnalyst error: {e}")
        return f"Error: Failed to call EnergyAnalyst: {str(e)}"


def get_newsroom_headlines() -> str:
    """
    Fetch today's compiled articles from Asoba newsroom via AWS S3.

    Returns:
        List of today's article headlines with sources and URLs
    """
    from datetime import datetime
    import json
    import subprocess
    import tempfile
    from pathlib import Path

    try:
        # Get today's date folder
        today = datetime.now().strftime("%Y-%m-%d")
        bucket = "news-collection-website"
        date_prefix = f"news/{today}/"

        logger.info(f"Fetching newsroom headlines for {today}...")

        # Use persistent cache to avoid re-downloading same day's articles
        import os
        cache_dir = Path(tempfile.gettempdir()) / "newsroom_cache" / today

        if cache_dir.exists():
            logger.info(f"Using cached articles from {cache_dir}")
            metadata_files = list(cache_dir.rglob("*.json"))
        else:
            # Download to cache directory
            cache_dir.mkdir(parents=True, exist_ok=True)

            sync_cmd = [
                "aws", "s3", "sync",
                f"s3://{bucket}/{date_prefix}",
                str(cache_dir),
                "--exclude", "*",
                "--include", "*/metadata/*.json",
                "--quiet"
            ]

            result = subprocess.run(
                sync_cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                return f"Error: AWS S3 sync failed: {result.stderr}"

            metadata_files = list(cache_dir.rglob("*.json"))
            logger.info(f"Downloaded and cached {len(metadata_files)} articles")

        if not metadata_files:
            return f"No articles found in newsroom for {today}"

        logger.info(f"Processing {len(metadata_files)} metadata files")

        headlines = []
        for file_path in metadata_files:  # Process all articles
                try:
                    with open(file_path, 'r') as f:
                        metadata = json.load(f)
                        headline = {
                            "title": metadata.get("title", "No title"),
                            "source": metadata.get("source", "Unknown"),
                            "url": metadata.get("url", ""),
                            "tags": metadata.get("tags", []),
                        }
                        headlines.append(headline)
                except (json.JSONDecodeError, IOError):
                    continue

        if not headlines:
            return f"Found {len(metadata_files)} files but couldn't parse any metadata"

        # Calculate tag distribution for overview
        from collections import Counter
        all_topics = []
        for h in headlines:
            # Extract core_topics from tags dict
            if h['tags'] and isinstance(h['tags'], dict):
                core_topics = h['tags'].get('core_topics', [])
                if isinstance(core_topics, list):
                    all_topics.extend([str(t) for t in core_topics if t])
        topic_counts = Counter(all_topics)

        # Format output with topic distribution and ALL headlines
        formatted = [f"Newsroom Headlines for {today} ({len(headlines)} articles)\n"]
        formatted.append("=" * 80 + "\n")

        if topic_counts:
            formatted.append("\nTopic Distribution:")
            for topic, count in topic_counts.most_common(15):
                formatted.append(f"  • {topic}: {count} articles")
            formatted.append("\n" + "=" * 80 + "\n")

            # Group headlines by primary core_topic
            from collections import defaultdict
            by_topic = defaultdict(list)
            for h in headlines:
                if h['tags'] and isinstance(h['tags'], dict):
                    core_topics = h['tags'].get('core_topics', [])
                    if core_topics and isinstance(core_topics, list) and len(core_topics) > 0:
                        primary_topic = str(core_topics[0])
                        by_topic[primary_topic].append(h)

            # Show ALL headlines grouped by topic (not just samples)
            formatted.append("\nAll Headlines by Topic:\n")
            for topic, count in topic_counts.most_common():
                if topic in by_topic:
                    formatted.append(f"\n{topic.upper()} ({count} articles):")
                    for h in by_topic[topic]:
                        formatted.append(f"  • {h['title']}")
        else:
            # Fallback: just list all headlines if no topics
            for idx, h in enumerate(headlines, 1):
                formatted.append(f"\n{idx}. {h['title']}")
                formatted.append(f"   Source: {h['source']}")

        return "\n".join(formatted)

    except subprocess.TimeoutExpired:
        return "Error: AWS S3 sync timed out (taking longer than 60s)"
    except FileNotFoundError:
        return "Error: AWS CLI not found. Install with: brew install awscli"
    except Exception as e:
        logger.error(f"Newsroom headlines error: {e}")
        return f"Error: Failed to fetch newsroom headlines: {str(e)}"


def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo.

    Args:
        query: Search query
        max_results: Maximum number of results to return (default: 5)

    Returns:
        Formatted search results with titles, URLs, and snippets
    """
    if not query or not isinstance(query, str):
        return "Error: query must be a non-empty string"

    if len(query) > 500:
        return "Error: query too long (max 500 characters)"

    import time

    max_retries = 3
    retry_delay = 2  # seconds

    for attempt in range(max_retries):
        try:
            from ddgs import DDGS

            logger.info(f"Web search: {query[:100]}... (attempt {attempt + 1}/{max_retries})")

            # Add small delay between requests to avoid rate limiting
            if attempt > 0:
                time.sleep(retry_delay * attempt)

            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            if not results:
                return f"No results found for: {query}"

            # Format results
            formatted = [f"Web search results for: {query}\n"]
            for i, result in enumerate(results, 1):
                title = result.get("title", "No title")
                url = result.get("href", "")
                snippet = result.get("body", "No description")
                formatted.append(f"\n{i}. {title}\n   URL: {url}\n   {snippet}")

            return "\n".join(formatted)

        except Exception as e:
            logger.warning(f"Web search attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                continue
            # All retries failed
            logger.error(f"Web search failed after {max_retries} attempts: {e}")
            return f"Error: Web search failed after {max_retries} attempts. Try again or rephrase query."


# Tool function mapping
TOOL_FUNCTIONS: Dict[str, Callable[..., str]] = {
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "make_directory": make_directory,
    "list_files": list_files,
    "analyze_image": analyze_image,
    "generate_image": generate_image,
    "run_shell": run_shell,
    "apply_patch": apply_patch,
    "use_codestral": use_codestral,
    "use_reasoning_model": use_reasoning_model,
    "use_search_model": use_search_model,
    "use_intent_detector": use_intent_detector,
    "use_energy_analyst": use_energy_analyst,
    "web_search": web_search,
    "get_newsroom_headlines": get_newsroom_headlines,
    "search": use_search_model,  # Simple alias
    "generate_code": use_codestral,  # Simple alias
    "plan": use_reasoning_model,  # Simple alias
}

# Tool aliases
TOOL_ALIASES: Dict[str, str] = {
    "run_bash": "run_shell",
    "bash": "run_shell",
    "shell": "run_shell",
    "exec": "run_shell",
    "ls": "list_files",
    "cat": "read_file",
    "open": "read_file",
    "code": "use_codestral",
    "plan": "use_reasoning_model",
    "research": "use_search_model",
}

# Tool definitions in OpenAI function calling format
TOOLS_DEFINITION: List[DictType[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories in a given path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path (default: current directory '.')"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_image",
            "description": "Analyze an image using a vision-language model for OCR and content extraction. Use this to convert images to text/markdown, extract data from charts/graphs, or understand image content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the image file (PNG, JPG, GIF, BMP, TIFF, WebP)"
                    },
                    "task": {
                        "type": "string",
                        "description": "What to do with the image (default: convert to markdown with OCR). Examples: 'Extract all text', 'Describe this chart', 'Convert table to markdown'"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Generate an image from a text prompt using Flux Schnell model. Creates high-quality 16:9 images (1344x768) from descriptions. Use for creating illustrations, visualizations, or any image content from text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Text description of the image to generate. Be specific and detailed for best results."
                    },
                    "filename": {
                        "type": "string",
                        "description": "Optional filename to save the image (default: auto-generated with timestamp). Example: 'sunset.png'"
                    }
                },
                "required": ["prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file (creates or overwrites)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to write"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit an existing file by replacing an exact string match. Use this when you need to modify part of a file without rewriting the entire file. The old_string must match exactly (including whitespace).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to edit"
                    },
                    "old_string": {
                        "type": "string",
                        "description": "Exact string to find and replace (must match exactly including whitespace)"
                    },
                    "new_string": {
                        "type": "string",
                        "description": "String to replace with"
                    }
                },
                "required": ["path", "old_string", "new_string"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "make_directory",
            "description": "Create a new directory. Creates parent directories if they don't exist (like 'mkdir -p'). Safe to call even if directory already exists.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path of the directory to create"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Execute a shell command",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": "Apply a unified diff patch to a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to patch"
                    },
                    "unified_diff": {
                        "type": "string",
                        "description": "Unified diff format patch to apply"
                    }
                },
                "required": ["path", "unified_diff"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "use_codestral",
            "description": "Generate or refactor code",
            "parameters": {
                "type": "object",
                "properties": {
                    "code_context": {
                        "type": "string",
                        "description": "Code generation task or refactoring request"
                    }
                },
                "required": ["code_context"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "use_reasoning_model",
            "description": "Plan or reason about complex tasks",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Planning or reasoning task"
                    }
                },
                "required": ["task"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "use_search_model",
            "description": "Research information or answer questions",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Research query or question"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search for information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_code",
            "description": "Generate code",
            "parameters": {
                "type": "object",
                "properties": {
                    "code_context": {
                        "type": "string",
                        "description": "Code to generate"
                    }
                },
                "required": ["code_context"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "plan",
            "description": "Plan a task",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Task to plan"
                    }
                },
                "required": ["task"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web using DuckDuckGo for current information, news, or real-time data",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for the web"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "use_energy_analyst",
            "description": "Analyze energy policy, regulations, and compliance using EnergyAnalyst RAG system. Use this for FERC orders, ISO/RTO rules, utility regulations, solar/storage/wind compliance, interconnection requirements, NEM policies, tariff analysis, and energy market questions. Retrieves context from energy policy documents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Energy policy or regulatory compliance question"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_newsroom_headlines",
            "description": "Fetch today's compiled news articles from Asoba newsroom (AWS S3). Returns headlines from energy, AI, blockchain, and legislation articles collected today. Use when user asks about today's news, current articles, newsroom content, or wants to analyze news themes.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]


class ToolRegistry:
    """Registry for tool definitions and function lookup."""

    def __init__(self):
        self.tools = TOOL_FUNCTIONS.copy()
        self.aliases = TOOL_ALIASES.copy()
        self.definitions = TOOLS_DEFINITION.copy()

    def get_function(self, tool_name: str) -> Optional[Callable[..., str]]:
        """Get tool function by name, resolving aliases."""
        resolved = self.aliases.get(tool_name, tool_name)
        return self.tools.get(resolved)

    def get_definitions(self) -> List[DictType[str, Any]]:
        """Get tool definitions in OpenAI format."""
        return self.definitions
