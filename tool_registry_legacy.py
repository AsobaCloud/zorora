"""Tool registry for tool definitions and function mapping."""

from typing import Dict, Callable, List, Dict as DictType, Any, Optional
from pathlib import Path
import subprocess
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

# Suppress BeautifulSoup encoding warnings globally
logging.getLogger("bs4.dammit").setLevel(logging.ERROR)


# Specialist tools that should return their results directly to the user
# instead of continuing the orchestrator iteration loop
SPECIALIST_TOOLS = [
    "use_codestral",
    "use_reasoning_model",
    "use_search_model",
    "use_intent_detector",  # Internal routing tool (not shown to user)
    "analyze_image",
    "generate_image",
    "academic_search"  # Returns formatted academic results directly
]


def _create_specialist_client(role: str, model_config: Dict[str, Any]):
    """
    Create an LLMClient for a specialist role, using local, HF, OpenAI, or Anthropic endpoint.

    Args:
        role: Role name (e.g., "codestral", "reasoning", "search", "intent_detector")
        model_config: Model configuration dict from SPECIALIZED_MODELS

    Returns:
        LLMClient instance configured for the role
    """
    from llm_client import LLMClient
    import config
    import os

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

    # Check OpenAI endpoints (matches HF pattern)
    if hasattr(config, 'OPENAI_ENDPOINTS') and endpoint_key in config.OPENAI_ENDPOINTS:
        openai_config = config.OPENAI_ENDPOINTS[endpoint_key]
        # Get API key from config or environment variable
        api_key = config.OPENAI_API_KEY if hasattr(config, 'OPENAI_API_KEY') and config.OPENAI_API_KEY else os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(f"OPENAI_API_KEY not configured for endpoint '{endpoint_key}'. Set it in config.py or OPENAI_API_KEY environment variable.")
        
        # Create LLMClient wrapper for OpenAI (uses OpenAIAdapter internally)
        from providers.openai_adapter import OpenAIAdapter
        adapter = OpenAIAdapter(
            api_key=api_key,
            model=openai_config.get("model", endpoint_key),
            timeout=openai_config.get("timeout", model_config["timeout"]),
        )
        # Wrap adapter in LLMClient-compatible interface
        client = LLMClient.__new__(LLMClient)
        client.adapter = adapter
        client.api_url = f"https://api.openai.com/v1/chat/completions"
        client.model = openai_config.get("model", endpoint_key)
        client.max_tokens = model_config["max_tokens"]
        client.temperature = model_config["temperature"]
        client.timeout = openai_config.get("timeout", model_config["timeout"])
        client.tool_choice = "auto"
        client.parallel_tool_calls = True
        client.auth_token = api_key
        return client

    # Check Anthropic endpoints (matches HF pattern)
    if hasattr(config, 'ANTHROPIC_ENDPOINTS') and endpoint_key in config.ANTHROPIC_ENDPOINTS:
        anthropic_config = config.ANTHROPIC_ENDPOINTS[endpoint_key]
        # Get API key from config or environment variable
        api_key = config.ANTHROPIC_API_KEY if hasattr(config, 'ANTHROPIC_API_KEY') and config.ANTHROPIC_API_KEY else os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(f"ANTHROPIC_API_KEY not configured for endpoint '{endpoint_key}'. Set it in config.py or ANTHROPIC_API_KEY environment variable.")
        
        # Create LLMClient wrapper for Anthropic (uses AnthropicAdapter internally)
        from providers.anthropic_adapter import AnthropicAdapter
        adapter = AnthropicAdapter(
            api_key=api_key,
            model=anthropic_config.get("model", endpoint_key),
            timeout=anthropic_config.get("timeout", model_config["timeout"]),
        )
        # Wrap adapter in LLMClient-compatible interface
        client = LLMClient.__new__(LLMClient)
        client.adapter = adapter
        client.api_url = f"https://api.anthropic.com/v1/messages"
        client.model = anthropic_config.get("model", endpoint_key)
        client.max_tokens = model_config["max_tokens"]
        client.temperature = model_config["temperature"]
        client.timeout = anthropic_config.get("timeout", model_config["timeout"])
        client.tool_choice = "auto"
        client.parallel_tool_calls = True
        client.auth_token = api_key
        return client

    # Check HF endpoints (existing logic)
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
def _resolve_path(path: str, working_directory=None):
    """
    Resolve a path against the working directory.

    Args:
        path: Path to resolve (can be relative, absolute, or use ~)
        working_directory: Current working directory (Path object or None)

    Returns:
        Resolved Path object
    """
    from pathlib import Path

    # Expand ~ to home directory
    path_obj = Path(path).expanduser()

    # If absolute, use as-is
    if path_obj.is_absolute():
        return path_obj

    # If relative and working_directory provided, resolve against it
    if working_directory is not None:
        return (working_directory / path_obj).resolve()

    # Otherwise use current working directory
    return path_obj.resolve()


def _validate_path(path: str) -> tuple[bool, str]:
    """
    Validate file path for security.

    Returns:
        (is_valid, error_message)
    """
    try:
        file_path = Path(path).resolve()
        home_dir = Path.home().resolve()

        # Prevent path traversal outside home directory
        # (More permissive than CWD to allow stateful navigation)
        if not str(file_path).startswith(str(home_dir)):
            return False, f"Error: Path must be within home directory ({home_dir})"

        return True, ""
    except Exception as e:
        return False, f"Error: Invalid path '{path}': {e}"


def read_file(path: str, working_directory=None, show_line_numbers: bool = True) -> str:
    """
    Read contents of a file with line numbers for precise editing.

    Args:
        path: Path to the file to read
        working_directory: Optional working directory for path resolution
        show_line_numbers: If True, prefix each line with line number (default: True)

    Returns:
        File contents with line numbers (format: "   123\t<content>")
    """
    # Resolve path against working directory if provided
    resolved_path = _resolve_path(path, working_directory)

    # Validate path security
    is_valid, error = _validate_path(str(resolved_path))
    if not is_valid:
        return error

    file_path = Path(resolved_path)
    if not file_path.exists():
        return f"Error: File '{path}' does not exist."
    if not file_path.is_file():
        return f"Error: '{path}' is not a file."

    # Check file size limit (10MB)
    if file_path.stat().st_size > 10_000_000:
        return f"Error: File '{path}' too large (>10MB)"

    try:
        content = file_path.read_text()

        if show_line_numbers:
            lines = content.splitlines()
            # Format like cat -n: right-aligned line number + tab + content
            numbered = []
            for i, line in enumerate(lines, 1):
                numbered.append(f"{i:6d}\t{line}")
            return "\n".join(numbered)
        else:
            return content
    except UnicodeDecodeError:
        return f"Error: File '{path}' is not a text file"
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str, working_directory=None) -> str:
    """Write content to a file (creates or overwrites)."""
    # Resolve path against working directory if provided
    resolved_path = _resolve_path(path, working_directory)

    # Validate path security
    is_valid, error = _validate_path(str(resolved_path))
    if not is_valid:
        return error

    try:
        Path(resolved_path).write_text(content)
        return f"OK: Written {len(content)} characters to '{resolved_path}'"
    except Exception as e:
        return f"Error writing file: {e}"


def make_directory(path: str, working_directory=None) -> str:
    """Create a new directory (including parent directories if needed)."""
    # Resolve path against working directory if provided
    resolved_path = _resolve_path(path, working_directory)

    try:
        dir_path = Path(resolved_path).resolve()
        home_dir = Path.home().resolve()

        # Security: Only allow creating directories within home directory
        if not str(dir_path).startswith(str(home_dir)):
            return f"Error: Can only create directories within home directory ({home_dir})"

        if dir_path.exists():
            if dir_path.is_dir():
                return f"OK: Directory '{resolved_path}' already exists"
            else:
                return f"Error: '{resolved_path}' exists but is not a directory"

        dir_path.mkdir(parents=True, exist_ok=True)
        return f"OK: Created directory '{resolved_path}'"
    except PermissionError:
        return f"Error: Permission denied to create directory '{resolved_path}'"
    except Exception as e:
        return f"Error creating directory: {e}"


def edit_file(path: str, old_string: str, new_string: str,
              replace_all: bool = False, working_directory=None) -> str:
    """
    Edit a file by replacing exact string match.

    You MUST read the file first with read_file before editing.
    The old_string must match exactly including whitespace and indentation.

    Args:
        path: Path to the file to edit
        old_string: Exact string to find and replace (must be unique or use replace_all)
        new_string: String to replace with
        replace_all: If True, replace all occurrences (default: False)
        working_directory: Optional working directory for path resolution

    Returns:
        Success or error message
    """
    # Resolve path against working directory if provided
    resolved_path = _resolve_path(path, working_directory)

    # Validate path security
    is_valid, error = _validate_path(str(resolved_path))
    if not is_valid:
        return error

    file_path = Path(resolved_path)
    if not file_path.exists():
        return f"Error: File '{path}' does not exist."
    if not file_path.is_file():
        return f"Error: '{path}' is not a file."

    try:
        # Read current content
        content = file_path.read_text()

        # Check if old_string exists
        if old_string not in content:
            # Try to find similar text to help the user
            similar = _find_similar_substring(content, old_string)
            if similar:
                return f"Error: Exact string not found. Similar text found:\n---\n{similar[:400]}\n---\nMake sure whitespace and indentation match exactly. Use read_file to see current content."
            return "Error: String not found in file. Use read_file to see current content and copy the exact text."

        # Count occurrences
        occurrences = content.count(old_string)

        if occurrences > 1 and not replace_all:
            # Show line numbers where string appears
            locations = _find_line_numbers(content, old_string)
            return f"Error: String appears {occurrences} times at lines {locations}. Either:\n1. Include more surrounding context to make it unique, or\n2. Set replace_all=True to replace all occurrences"

        # Perform replacement
        if replace_all:
            new_content = content.replace(old_string, new_string)
            file_path.write_text(new_content)
            return f"OK: Replaced {occurrences} occurrence(s) in '{resolved_path}'"
        else:
            new_content = content.replace(old_string, new_string, 1)
            file_path.write_text(new_content)
            return f"OK: Replaced 1 occurrence in '{resolved_path}'"

    except UnicodeDecodeError:
        return f"Error: File '{path}' is not a text file"
    except Exception as e:
        return f"Error editing file: {e}"


def _find_similar_substring(content: str, target: str, context_chars: int = 100) -> str:
    """
    Find similar substring in content (handles whitespace differences).

    Returns a snippet of similar text if found, empty string otherwise.
    """
    # Normalize whitespace for comparison
    normalized_target = ' '.join(target.split())
    normalized_content = ' '.join(content.split())

    if len(normalized_target) < 10:
        return ""  # Too short to meaningfully match

    if normalized_target in normalized_content:
        # Find approximate location in original content
        # Search for first significant word from target
        words = [w for w in target.split() if len(w) > 3]
        if words:
            first_word = words[0]
            idx = content.find(first_word)
            if idx >= 0:
                start = max(0, idx - context_chars)
                end = min(len(content), idx + len(target) + context_chars)
                return content[start:end]
    return ""


def _find_line_numbers(content: str, substring: str) -> str:
    """
    Find line numbers where substring appears.

    Returns comma-separated list of line numbers (truncated if >10).
    """
    lines = content.splitlines()
    locations = []

    # For multi-line substrings, find which lines contain the start
    sub_first_line = substring.split('\n')[0] if '\n' in substring else substring

    for i, line in enumerate(lines, 1):
        if sub_first_line in line:
            locations.append(str(i))
        elif substring in line:
            locations.append(str(i))

    if len(locations) > 10:
        return ", ".join(locations[:10]) + f"... ({len(locations)} total)"
    return ", ".join(locations) if locations else "unknown"


def list_files(path: str = ".", working_directory=None) -> str:
    """List files and directories in a path."""
    # Resolve path against working directory if provided
    resolved_path = _resolve_path(path, working_directory)

    # Validate path security
    is_valid, error = _validate_path(str(resolved_path))
    if not is_valid:
        return error

    try:
        dir_path = Path(resolved_path)
        if not dir_path.exists():
            return f"Error: Path '{path}' does not exist."
        if not dir_path.is_dir():
            return f"Error: '{path}' is not a directory."
        items = [p.name for p in dir_path.iterdir()]
        return "\n".join(sorted(items)) if items else "(empty directory)"
    except Exception as e:
        return f"Error listing files: {e}"


def get_working_directory(working_directory=None) -> str:
    """Get the current working directory."""
    if working_directory is not None:
        return f"Current working directory: {working_directory}"
    else:
        return f"Current working directory: {Path.cwd()}"


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
            "python", "python3", "node", "npm", "git", "pytest", "black", "flake8",
            "mkdir", "cd", "touch", "mv", "cp"]
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


def _filter_newsroom_by_relevance(headlines: List[Dict], query: str, max_results: int) -> List[Dict]:
    """
    Filter and rank newsroom articles by relevance to query.

    Args:
        headlines: List of article dicts with title, tags, source
        query: Search query
        max_results: Max results to return

    Returns:
        Filtered and ranked list of most relevant articles
    """
    import re

    # Extract keywords from query
    query_lower = query.lower()
    # Remove common stop words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'is', 'are', 'what', 'how', 'why', 'when', 'where'}
    query_words = [w for w in re.findall(r'\b\w+\b', query_lower) if w not in stop_words and len(w) > 2]

    # Score each article
    scored_headlines = []
    for h in headlines:
        score = 0
        title_lower = h['title'].lower()
        source_lower = h['source'].lower()

        # Title matches (highest weight)
        for word in query_words:
            if word in title_lower:
                score += 10

        # Tag matches (medium weight)
        if h.get('tags') and isinstance(h['tags'], dict):
            core_topics = h['tags'].get('core_topics', [])
            for topic in core_topics:
                topic_lower = str(topic).lower()
                for word in query_words:
                    if word in topic_lower:
                        score += 5

        # Source matches (low weight)
        for word in query_words:
            if word in source_lower:
                score += 2

        # Exact phrase match (bonus)
        if query_lower in title_lower:
            score += 20

        if score > 0:
            h['relevance_score'] = score
            scored_headlines.append(h)

    # Sort by relevance score (highest first) and return top N
    scored_headlines.sort(key=lambda x: x['relevance_score'], reverse=True)
    return scored_headlines[:max_results]


def get_newsroom_headlines(query: str = None, days_back: int = None, max_results: int = None) -> str:
    """
    Fetch recent compiled articles from Asoba newsroom via AWS S3.
    Searches across multiple days and filters by relevance to query.

    Args:
        query: Search query to filter articles by relevance (optional)
        days_back: Number of days to search back (default from config)
        max_results: Max relevant articles to return (default from config)

    Returns:
        List of relevant article headlines with sources and URLs
    """
    from datetime import datetime, timedelta
    import json
    import subprocess
    import tempfile
    from pathlib import Path
    import config

    # Get configuration
    if days_back is None:
        days_back = getattr(config, 'NEWSROOM_DAYS_BACK', 90)
    if max_results is None:
        max_results = getattr(config, 'NEWSROOM_MAX_RELEVANT', 25)

    try:
        bucket = "news-collection-website"

        # Calculate date range
        today = datetime.now()
        start_date = today - timedelta(days=days_back - 1)

        logger.info(f"Fetching newsroom articles from last {days_back} days (filtered by relevance)...")

        # Use persistent cache for all days
        base_cache_dir = Path(tempfile.gettempdir()) / "newsroom_cache"
        base_cache_dir.mkdir(parents=True, exist_ok=True)

        # Generate list of dates to fetch
        dates_to_fetch = []
        current_date = start_date
        while current_date <= today:
            dates_to_fetch.append(current_date)
            current_date += timedelta(days=1)

        # Function to download a single day
        def download_day(date_obj):
            date_str = date_obj.strftime("%Y-%m-%d")
            day_cache_dir = base_cache_dir / date_str
            date_prefix = f"news/{date_str}/"

            if day_cache_dir.exists():
                # Use cached articles for this day
                day_files = list(day_cache_dir.rglob("*.json"))
                if day_files:
                    logger.debug(f"Using {len(day_files)} cached articles from {date_str}")
                    return day_files
                return []
            else:
                # Download this day's articles
                day_cache_dir.mkdir(parents=True, exist_ok=True)

                sync_cmd = [
                    "aws", "s3", "sync",
                    f"s3://{bucket}/{date_prefix}",
                    str(day_cache_dir),
                    "--exclude", "*",
                    "--include", "*/metadata/*.json",
                    "--quiet"
                ]

                result = subprocess.run(
                    sync_cmd,
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                if result.returncode == 0:
                    day_files = list(day_cache_dir.rglob("*.json"))
                    if day_files:
                        logger.info(f"Downloaded {len(day_files)} articles for {date_str}")
                        return day_files
                else:
                    logger.warning(f"Failed to sync {date_str}: {result.stderr}")
                return []

        # Download days in parallel (max 15 workers to avoid overwhelming S3)
        from concurrent.futures import ThreadPoolExecutor, as_completed
        all_metadata_files = []

        with ThreadPoolExecutor(max_workers=15) as executor:
            future_to_date = {executor.submit(download_day, date): date for date in dates_to_fetch}

            for future in as_completed(future_to_date):
                try:
                    day_files = future.result()
                    all_metadata_files.extend(day_files)
                except Exception as e:
                    date = future_to_date[future]
                    logger.error(f"Error downloading {date.strftime('%Y-%m-%d')}: {e}")

        if not all_metadata_files:
            return f"No articles found in newsroom for last {days_back} days"

        logger.info(f"Processing {len(all_metadata_files)} articles from {days_back} days")

        # Parse all articles
        headlines = []
        for file_path in all_metadata_files:
            try:
                with open(file_path, 'r') as f:
                    metadata = json.load(f)
                    headline = {
                        "title": metadata.get("title", "No title"),
                        "source": metadata.get("source", "Unknown"),
                        "url": metadata.get("url", ""),
                        "tags": metadata.get("tags", []),
                        "date": file_path.parent.parent.parent.name,  # Extract date from path
                    }
                    headlines.append(headline)
            except (json.JSONDecodeError, IOError):
                continue

        if not headlines:
            return f"Found {len(all_metadata_files)} files but couldn't parse any metadata"

        # Filter by relevance if query provided
        if query:
            headlines = _filter_newsroom_by_relevance(headlines, query, max_results)
            logger.info(f"Filtered to {len(headlines)} most relevant articles for query: {query[:60]}...")
        else:
            # No query - return most recent articles up to max_results
            headlines = sorted(headlines, key=lambda x: x.get('date', ''), reverse=True)[:max_results]
            logger.info(f"No query provided - returning {len(headlines)} most recent articles")

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
            formatted.append("\nRelevant Headlines by Topic:\n")
            for topic, count in topic_counts.most_common():
                if topic in by_topic:
                    formatted.append(f"\n{topic.upper()} ({count} articles):")
                    for h in by_topic[topic]:
                        date_str = h.get('date', 'Unknown date')
                        formatted.append(f"  • {h['title']} [{date_str}]")
                        if h.get('url'):
                            formatted.append(f"    URL: {h['url']}")
                        formatted.append(f"    Source: {h['source']}")
                        if h.get('relevance_score'):
                            formatted.append(f"    Relevance: {h['relevance_score']}")
        else:
            # Fallback: just list all headlines if no topics
            for idx, h in enumerate(headlines, 1):
                date_str = h.get('date', 'Unknown date')
                formatted.append(f"\n{idx}. {h['title']} [{date_str}]")
                formatted.append(f"   Source: {h['source']}")
                if h.get('url'):
                    formatted.append(f"   URL: {h['url']}")
                if h.get('relevance_score'):
                    formatted.append(f"   Relevance: {h['relevance_score']}")

        return "\n".join(formatted)

    except subprocess.TimeoutExpired:
        return "Error: AWS S3 sync timed out (taking longer than 60s)"
    except FileNotFoundError:
        return "Error: AWS CLI not found. Install with: brew install awscli"
    except Exception as e:
        logger.error(f"Newsroom headlines error: {e}")
        return f"Error: Failed to fetch newsroom headlines: {str(e)}"


def _synthesize_results(results: List[Dict[str, Any]], original_query: str, optimized_query: str, query_metadata: dict = None) -> str:
    """
    Synthesize search results using LLM models.
    
    Args:
        results: List of search result dictionaries
        original_query: Original user query
        optimized_query: Optimized query used for search
        query_metadata: Optional metadata from query optimization
        
    Returns:
        Synthesized answer string
    """
    import config
    
    # Build context from results
    context_parts = []
    for i, result in enumerate(results[:5], 1):  # Use top 5 for synthesis
        title = result.get("title", "No title")
        url = result.get("url", "")
        description = result.get("description", "No description")
        extracted = result.get("extracted_content", "")
        
        context_parts.append(f"{i}. {title} ({url})")
        context_parts.append(f"   {description}")
        if extracted:
            context_parts.append(f"   [Content]: {extracted[:500]}...")  # Truncate extracted content
    
    context = "\n".join(context_parts)
    
    # Use search model for synthesis
    try:
        synthesis_prompt = f"""Based on the following web search results for "{original_query}", provide a comprehensive answer:

{context}

Please synthesize the information from these sources to answer: {original_query}

Provide a clear, well-structured answer that combines information from multiple sources. Cite sources when making specific claims."""
        
        # Use existing use_search_model function
        synthesized = use_search_model(synthesis_prompt)
        
        if synthesized and not synthesized.startswith("Error:"):
            # Add source attribution
            sources_list = "\n".join([f"- {r.get('title', 'Unknown')} ({r.get('url', '')})" for r in results[:5]])
            return f"{synthesized}\n\nSources:\n{sources_list}"
        
        return synthesized
        
    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        return f"Error: Failed to synthesize results: {e}"


def _format_search_results(query: str, results: List[Dict[str, Any]], source: str = "Unknown", query_metadata: dict = None, include_extracted: bool = False) -> str:
    """
    Format search results with enhanced metadata.
    
    Args:
        query: Original search query
        results: List of result dictionaries with 'title', 'url', 'description'
        source: Search engine source name
        query_metadata: Optional metadata from query optimization
        
    Returns:
        Formatted string with enhanced metadata
    """
    from urllib.parse import urlparse
    from datetime import datetime
    
    if not results:
        return f"No results found for: {query}"
    
    formatted = [f"Web search results for: {query}"]
    
    # Add source and intent info if available
    if query_metadata and query_metadata.get("intent") != "general":
        formatted[0] += f" (intent: {query_metadata['intent']})"
    formatted[0] += f" [{source}]\n"
    
    for i, result in enumerate(results, 1):
        title = result.get("title", "No title")
        url = result.get("url", "")
        description = result.get("description", "No description")
        
        # Extract domain from URL
        domain = ""
        if url:
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.replace("www.", "")
            except Exception:
                pass
        
        # Extract date if available (Brave API sometimes includes age)
        date_info = ""
        if "age" in result:
            age = result.get("age")
            if age:
                date_info = f" | Age: {age}"
        elif "published_date" in result:
            pub_date = result.get("published_date")
            if pub_date:
                date_info = f" | Published: {pub_date}"
        
        # Format result entry
        formatted.append(f"\n{i}. {title}")
        formatted.append(f"   URL: {url}")
        
        # Add metadata line if available
        if domain or date_info:
            meta_parts = []
            if domain:
                meta_parts.append(f"Domain: {domain}")
            if date_info:
                meta_parts.append(date_info.strip(" |"))
            if meta_parts:
                formatted.append(f"   {' | '.join(meta_parts)}")
        
        formatted.append(f"   {description}")
        
        # Add extracted content if available and enabled
        if include_extracted:
            extracted = result.get("extracted_content", "")
            if extracted:
                formatted.append(f"\n   [Extracted Content]: {extracted[:500]}...")  # Truncate for display
    
    return "\n".join(formatted)


def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using Brave Search API (with DuckDuckGo fallback).
    Enhanced with caching, query optimization, and improved formatting.

    Args:
        query: Search query (may include meta-language like "search for" - will be cleaned)
        max_results: Maximum number of results to return (default: 5)

    Returns:
        Formatted search results with titles, URLs, and snippets
    """
    if not query or not isinstance(query, str):
        return "Error: query must be a non-empty string"

    if len(query) > 500:
        return "Error: query too long (max 500 characters)"

    import config
    
    # Pre-process query to remove meta-language before optimization
    # This helps when users say "search for X" instead of just "X"
    import re
    original_query = query
    query = query.strip()
    
    # Remove common meta-language prefixes
    meta_prefixes = [
        r'^(let\'?s\s+)?(do\s+a\s+)?(web\s+)?search\s+(for|to|about|on)\s+',
        r'^(can\s+you\s+)?(please\s+)?(search\s+for|look\s+up|find\s+information\s+about)\s+',
        r'^(i\s+want\s+to\s+)?(search|find|look\s+up)\s+(for|about|on)\s+',
        r'^(help\s+me\s+)?(understand|learn|find\s+out)\s+(about|more\s+about)\s+',
    ]
    
    for pattern in meta_prefixes:
        query = re.sub(pattern, '', query, flags=re.IGNORECASE)
        query = query.strip()
    
    # Remove meta-language in the middle/end (but preserve substantive context)
    # First, remove "and what it means" but preserve what comes after if substantive
    query = re.sub(r'\s+and\s+what\s+it\s+means\s+', ' ', query, flags=re.IGNORECASE)
    query = query.strip()
    
    # Remove other meta-language suffixes
    meta_suffixes = [
        r'\s+what\s+does\s+this\s+mean.*$',
        r'\s+what\s+is\s+the\s+context.*$',
        r'\s+to\s+better\s+understand.*$',
        r'\s+to\s+understand.*$',
    ]
    
    for pattern in meta_suffixes:
        query = re.sub(pattern, '', query, flags=re.IGNORECASE)
        query = query.strip()
    
    # Remove "better understand the context around" type phrases
    query = re.sub(r'\b(better\s+)?understand\s+(the\s+)?context\s+around\s+', '', query, flags=re.IGNORECASE)
    query = query.strip()
    
    # Remove "the context behind/around/for" type phrases
    query = re.sub(r'\bthe\s+context\s+(behind|around|for|of)\s+', '', query, flags=re.IGNORECASE)
    query = query.strip()
    
    # Remove "behind" when used as meta-language (but keep if it's part of substantive content)
    # Only remove if it's at the start or after "context"
    query = re.sub(r'^(behind|about|regarding)\s+', '', query, flags=re.IGNORECASE)
    query = query.strip()
    
    if not query:
        return "Error: Query became empty after removing meta-language. Please provide a search query."
    
    # Log if query was cleaned
    if query != original_query:
        logger.info(f"Query cleaned: '{original_query[:60]}...' -> '{query[:60]}...'")
    
    # Initialize cache if enabled
    cache = None
    if config.WEB_SEARCH.get("cache_enabled", True):
        try:
            from tools.utils._search_cache import SearchCache
            cache = SearchCache(
                max_entries=config.WEB_SEARCH.get("cache_max_entries", 100),
                default_ttl_hours=config.WEB_SEARCH.get("cache_ttl_hours", 1),
                stable_ttl_hours=config.WEB_SEARCH.get("cache_ttl_stable_hours", 24)
            )
            # Check cache first
            cached_result = cache.get(query, max_results)
            if cached_result:
                logger.info(f"Returning cached result for: {query[:50]}...")
                return cached_result
        except ImportError as e:
            logger.warning(f"Cache module not available: {e}, continuing without cache")
        except Exception as e:
            logger.warning(f"Cache initialization failed: {e}, continuing without cache")
    
    # Optimize query if enabled
    optimized_query = query
    query_metadata = {}
    if config.WEB_SEARCH.get("query_optimization", True):
        try:
            from tools.utils._query_optimizer import QueryOptimizer
            optimizer = QueryOptimizer(enabled=config.WEB_SEARCH.get("intent_detection", True))
            optimized_query, query_metadata = optimizer.optimize(query)
        except ImportError as e:
            logger.warning(f"Query optimizer module not available: {e}, using original query")
        except Exception as e:
            logger.warning(f"Query optimization failed: {e}, using original query")
    
    # Route to specialized search types based on intent
    intent = query_metadata.get("intent", "general")
    
    # News search - only route if query explicitly mentions news-related terms
    # This prevents false positives like "what is the current directory?" being routed to news
    if intent == "news" and config.WEB_SEARCH.get("news_enabled", True):
        # Additional check: ensure query actually contains news-related keywords
        news_keywords = ['news', 'headline', 'article', 'breaking', 'update', 'announcement', 'happening', 'happened']
        query_lower = optimized_query.lower()
        has_news_keyword = any(keyword in query_lower for keyword in news_keywords)
        
        if has_news_keyword and config.BRAVE_SEARCH.get("enabled") and config.BRAVE_SEARCH.get("api_key"):
            try:
                result = _brave_news_search(optimized_query, max_results, query_metadata)
                # Cache result
                if cache and result and not result.startswith("Error:"):
                    try:
                        cache.set(query, max_results, result)
                    except Exception:
                        pass
                return result
            except Exception as e:
                logger.warning(f"News search failed: {e}, falling back to regular search")
                # Fall through to regular search
    
    # Note: Image search is available as a separate tool: web_image_search()
    # It's not automatically routed from web_search() to maintain separation of concerns

    # Check if parallel search is enabled
    parallel_enabled = config.WEB_SEARCH.get("parallel_enabled", False)
    brave_available = config.BRAVE_SEARCH.get("enabled") and config.BRAVE_SEARCH.get("api_key")
    
    # Get raw results for processing
    raw_results = None
    academic_max_results = config.WEB_SEARCH.get("academic_max_results", 3)
    
    if parallel_enabled and brave_available:
        # Parallel search: search both Brave and DuckDuckGo simultaneously
        logger.info(f"Using parallel search (Brave + DuckDuckGo) for: {optimized_query[:60]}...")
        raw_results = _parallel_search_raw(optimized_query, max_results)
    else:
        # Sequential search: try Brave first, fallback to DuckDuckGo
        if brave_available:
            logger.info(f"Attempting Brave Search for: {optimized_query[:60]}...")
            try:
                raw_results = _brave_search_raw(optimized_query, max_results)
                if raw_results:
                    logger.info(f"Brave Search succeeded: {len(raw_results)} results")
                else:
                    logger.warning(f"Brave Search returned no results, falling back to DuckDuckGo")
            except Exception as e:
                logger.warning(f"Brave Search failed: {e}, falling back to DuckDuckGo")
        
        # Fallback to DuckDuckGo if Brave failed or not configured
        if raw_results is None:
            logger.info(f"Using DuckDuckGo fallback for: {optimized_query[:60]}...")
            try:
                raw_results = _duckduckgo_search_raw(optimized_query, max_results)
                if raw_results:
                    logger.info(f"DuckDuckGo search succeeded: {len(raw_results)} results")
                else:
                    logger.warning(f"DuckDuckGo returned no results")
            except Exception as e:
                logger.error(f"DuckDuckGo search failed: {e}")
                return f"Error: Web search failed: {e}. Try again or rephrase query."
    
    # Always include academic sources (Scholar + PubMed)
    academic_results = []
    academic_sources_used = []
    try:
        logger.info(f"Searching academic sources (Scholar + PubMed) for: {optimized_query[:60]}...")
        scholar_results = _scholar_search_raw(optimized_query, academic_max_results)
        if scholar_results:
            academic_results.extend(scholar_results)
            academic_sources_used.append("Scholar")
    except Exception as e:
        logger.warning(f"Scholar search failed: {e}, continuing without Scholar results")
    
    try:
        pubmed_results = _pubmed_search_raw(optimized_query, academic_max_results)
        if pubmed_results:
            academic_results.extend(pubmed_results)
            academic_sources_used.append("PubMed")
    except Exception as e:
        logger.warning(f"PubMed search failed: {e}, continuing without PubMed results")
    
    # Merge web and academic results
    if academic_results:
        if raw_results:
            # Combine results for processing
            raw_results = raw_results + academic_results
            logger.info(f"Merged {len(academic_results)} academic results with {len(raw_results) - len(academic_results)} web results")
        else:
            # Only academic results available
            raw_results = academic_results
            logger.info(f"Using {len(academic_results)} academic results only")
    
    if not raw_results:
        # Log which search sources were attempted
        sources_tried = []
        if parallel_enabled and brave_available:
            sources_tried.append("Brave (parallel)")
            sources_tried.append("DuckDuckGo (parallel)")
        elif brave_available:
            sources_tried.append("Brave")
            sources_tried.append("DuckDuckGo (fallback)")
        else:
            sources_tried.append("DuckDuckGo")
        
        logger.warning(f"No results found from {', '.join(sources_tried)} for query: {query[:60]}...")
        return f"No results found for: {query}\n\nTry:\n- Rephrasing the query\n- Using more specific keywords\n- Checking if the search terms are spelled correctly"
    
    # Process results (deduplication, ranking, domain diversity)
    import config
    try:
        # Try importing from current directory first
        from tools.utils._result_processor import ResultProcessor
        processor = ResultProcessor(
            max_domain_results=config.WEB_SEARCH.get("max_domain_results", 2)
        )
        processed_results = processor.process_results(raw_results, optimized_query)
        processed_results = processed_results[:max_results]
    except ImportError as e:
        logger.warning(f"Result processor module not available: {e}, using raw results")
        processed_results = raw_results[:max_results]
    except Exception as e:
        logger.warning(f"Result processing failed: {e}, using raw results")
        processed_results = raw_results[:max_results]
    
    # Extract content from top results if enabled
    extract_content = config.WEB_SEARCH.get("extract_content", False)
    if extract_content:
        try:
            # Try importing from current directory first
            from tools.utils._content_extractor import ContentExtractor
            extractor = ContentExtractor(
                enabled=True,
                extract_top_n=config.WEB_SEARCH.get("extract_top_n", 2),
                max_content_length=2000
            )
            processed_results = extractor.extract_from_results(processed_results, optimized_query)
        except ImportError as e:
            logger.warning(f"Content extractor module not available: {e}, continuing without extraction")
        except Exception as e:
            logger.warning(f"Content extraction failed: {e}, continuing without extraction")
    
    # Synthesize results if enabled
    synthesize = config.WEB_SEARCH.get("synthesize_results", False)
    if synthesize and len(processed_results) >= config.WEB_SEARCH.get("synthesize_threshold", 5):
        try:
            synthesized = _synthesize_results(processed_results, query, optimized_query, query_metadata)
            if synthesized and not synthesized.startswith("Error:"):
                # Cache synthesized result
                if cache:
                    try:
                        cache.set(query, max_results, synthesized)
                    except Exception:
                        pass
                return synthesized
        except Exception as e:
            logger.warning(f"Result synthesis failed: {e}, using regular formatting")
    
    # Format results with academic sources included
    sources_parts = []
    if parallel_enabled and brave_available:
        sources_parts.append("Brave + DuckDuckGo")
    elif brave_available:
        sources_parts.append("Brave")
    else:
        sources_parts.append("DuckDuckGo")
    
    # Add academic sources if we have academic results
    if academic_sources_used:
        sources_parts.append(" + ".join(academic_sources_used))
    
    sources_str = " + ".join(sources_parts)
    result = _format_search_results(query, processed_results, sources_str, query_metadata, extract_content)
    
    # Cache result if cache is available
    if cache and result and not result.startswith("Error:"):
        try:
            cache.set(query, max_results, result)
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")
    
    return result


def _parallel_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search multiple sources in parallel and return raw results.
    
    Args:
        query: Search query
        max_results: Number of results to return
        
    Returns:
        List of result dictionaries
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import config
    
    logger.info(f"Parallel search (raw): {query[:100]}...")
    
    # Prepare search tasks
    tasks = []
    
    # Add Brave search task
    if config.BRAVE_SEARCH.get("enabled") and config.BRAVE_SEARCH.get("api_key"):
        tasks.append(("brave", _brave_search_raw, query, max_results))
    
    # Add DuckDuckGo search task
    tasks.append(("duckduckgo", _duckduckgo_search_raw, query, max_results))
    
    if not tasks:
        return []
    
    # Execute searches in parallel
    result_sets = []
    
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        # Submit all tasks
        future_to_source = {}
        for source, func, *args in tasks:
            future = executor.submit(func, *args)
            future_to_source[future] = source
        
        # Collect results as they complete
        for future in as_completed(future_to_source):
            source = future_to_source[future]
            try:
                results = future.result()
                if results:
                    result_sets.append(results)
                    logger.info(f"Parallel search: {source} returned {len(results)} results")
            except Exception as e:
                logger.warning(f"Parallel search: {source} failed: {e}")
    
    if not result_sets:
        logger.warning("Parallel search: No result sets collected")
        return []
    
    # Merge results
    try:
        # Try importing from current directory first
        from tools.utils._result_processor import ResultProcessor
        processor = ResultProcessor(
            max_domain_results=config.WEB_SEARCH.get("max_domain_results", 2)
        )
        merged_results = processor.merge_results(result_sets, query)
        logger.info(f"Parallel search: Merged {len(result_sets)} result sets into {len(merged_results)} results")
        return merged_results[:max_results]
    except ImportError as e:
        logger.warning(f"Result processor module not available: {e}, using raw results")
        # Fallback: return first successful result set
        if result_sets:
            logger.info(f"Parallel search fallback: Using first result set ({len(result_sets[0])} results)")
            return result_sets[0][:max_results]
        return []
    except Exception as e:
        logger.error(f"Failed to merge parallel search results: {e}")
        # Fallback: return first successful result set
        if result_sets:
            logger.info(f"Parallel search fallback: Using first result set ({len(result_sets[0])} results)")
            return result_sets[0][:max_results]
        return []


def _parallel_search(query: str, max_results: int = 5, query_metadata: dict = None) -> str:
    """
    Search multiple sources in parallel and merge results.
    
    Args:
        query: Search query
        max_results: Number of results to return
        query_metadata: Optional metadata from query optimization
        
    Returns:
        Formatted search results from merged sources
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import config
    
    logger.info(f"Parallel search: {query[:100]}...")
    
    # Prepare search tasks
    tasks = []
    
    # Add Brave search task
    if config.BRAVE_SEARCH.get("enabled") and config.BRAVE_SEARCH.get("api_key"):
        tasks.append(("brave", _brave_search_raw, query, max_results))
    
    # Add DuckDuckGo search task
    tasks.append(("duckduckgo", _duckduckgo_search_raw, query, max_results))
    
    if not tasks:
        return "Error: No search sources available"
    
    # Execute searches in parallel
    result_sets = []
    sources_used = []
    
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        # Submit all tasks
        future_to_source = {}
        for source, func, *args in tasks:
            future = executor.submit(func, *args)
            future_to_source[future] = source
        
        # Collect results as they complete
        for future in as_completed(future_to_source):
            source = future_to_source[future]
            try:
                results = future.result()
                if results:
                    result_sets.append(results)
                    sources_used.append(source)
                    logger.info(f"Parallel search: {source} returned {len(results)} results")
            except Exception as e:
                logger.warning(f"Parallel search: {source} failed: {e}")
    
    if not result_sets:
        return f"Error: All search sources failed for query: {query}"
    
    # Merge and process results
    try:
        # Try importing from current directory first
        from tools.utils._result_processor import ResultProcessor
        processor = ResultProcessor(
            max_domain_results=config.WEB_SEARCH.get("max_domain_results", 2)
        )
        
        merged_results = processor.merge_results(result_sets, query)
        
        # Limit to max_results
        merged_results = merged_results[:max_results]
        
        # Format results
        sources_str = " + ".join(sources_used)
        return _format_search_results(query, merged_results, sources_str, query_metadata)
    except ImportError as e:
        logger.warning(f"Result processor module not available: {e}, using raw results")
        # Fallback: use first successful result set
        if result_sets:
            return _format_search_results(query, result_sets[0][:max_results], sources_used[0], query_metadata)
        return f"Error: Failed to process search results: {e}"
    except Exception as e:
        logger.error(f"Failed to process parallel search results: {e}")
        # Fallback: use first successful result set
        if result_sets:
            return _format_search_results(query, result_sets[0][:max_results], sources_used[0], query_metadata)
        return f"Error: Failed to process search results: {e}"


def _brave_news_search(query: str, max_results: int = 5, query_metadata: dict = None) -> str:
    """
    Search news using Brave News API.
    
    Args:
        query: Search query
        max_results: Number of results (max 20 for free tier)
        query_metadata: Optional metadata from query optimization
        
    Returns:
        Formatted news search results
    """
    import config
    import requests
    
    logger.info(f"Brave News Search: {query[:100]}...")
    
    # Brave News API endpoint
    news_endpoint = config.BRAVE_SEARCH.get("news_endpoint", "https://api.search.brave.com/res/v1/news/search")
    
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": config.BRAVE_SEARCH["api_key"]
    }
    
    params = {
        "q": query,
        "count": min(max_results, 20),  # Max 20 for free tier
        "search_lang": "en",
        "freshness": "pd"  # Past day - prioritize recent news
    }
    
    try:
        response = requests.get(
            news_endpoint,
            headers=headers,
            params=params,
            timeout=config.BRAVE_SEARCH["timeout"]
        )
        response.raise_for_status()
        
        data = response.json()
        news_results = data.get("results", [])
        
        if not news_results:
            return f"No news found for: {query}"
        
        # Format news results with dates prominently displayed
        formatted = [f"News search results for: {query}"]
        if query_metadata and query_metadata.get("intent") == "news":
            formatted[0] += " (intent: news)"
        formatted[0] += " [Brave News]\n"
        
        for i, result in enumerate(news_results, 1):
            title = result.get("title", "No title")
            url = result.get("url", "")
            description = result.get("description", "No description")
            
            # Extract date information
            date_info = ""
            if "age" in result:
                age = result.get("age")
                if age:
                    date_info = f" | Published: {age} ago"
            elif "published_date" in result:
                pub_date = result.get("published_date")
                if pub_date:
                    date_info = f" | Published: {pub_date}"
            
            # Extract source
            source = result.get("meta_url", {}).get("hostname", "") if isinstance(result.get("meta_url"), dict) else ""
            if not source and url:
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    source = parsed.netloc.replace("www.", "")
                except Exception:
                    pass
            
            formatted.append(f"\n{i}. {title}")
            formatted.append(f"   URL: {url}")
            
            # Add metadata with date prominently displayed
            meta_parts = []
            if source:
                meta_parts.append(f"Source: {source}")
            if date_info:
                meta_parts.append(date_info.strip(" |"))
            if meta_parts:
                formatted.append(f"   {' | '.join(meta_parts)}")
            
            formatted.append(f"   {description}")
        
        return "\n".join(formatted)
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Brave News Search API error: {e}")
        raise


def web_image_search(query: str, max_results: int = 5) -> str:
    """
    Search images using Brave Image Search API.
    
    Args:
        query: Search query
        max_results: Number of results (max 20 for free tier)
        
    Returns:
        Formatted image search results with image URLs
    """
    import config
    import requests
    
    logger.info(f"Brave Image Search: {query[:100]}...")
    
    # Brave Image API endpoint
    image_endpoint = config.BRAVE_SEARCH.get("image_endpoint", "https://api.search.brave.com/res/v1/images/search")
    
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": config.BRAVE_SEARCH["api_key"]
    }
    
    params = {
        "q": query,
        "count": min(max_results, 20),  # Max 20 for free tier
        "search_lang": "en",
        "safesearch": "moderate"
    }
    
    try:
        response = requests.get(
            image_endpoint,
            headers=headers,
            params=params,
            timeout=config.BRAVE_SEARCH["timeout"]
        )
        response.raise_for_status()
        
        data = response.json()
        image_results = data.get("results", [])
        
        if not image_results:
            return f"No images found for: {query}"
        
        # Format image results
        formatted = [f"Image search results for: {query} [Brave Images]\n"]
        
        for i, result in enumerate(image_results, 1):
            title = result.get("title", "No title")
            url = result.get("url", "")
            thumbnail = result.get("thumbnail", {}).get("src", "") if isinstance(result.get("thumbnail"), dict) else ""
            source = result.get("source", "")
            
            formatted.append(f"\n{i}. {title}")
            if thumbnail:
                formatted.append(f"   Thumbnail: {thumbnail}")
            formatted.append(f"   Image URL: {url}")
            if source:
                formatted.append(f"   Source: {source}")
        
        return "\n".join(formatted)
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Brave Image Search API error: {e}")
        raise


def _brave_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search using Brave Search API and return raw results (not formatted).
    
    Args:
        query: Search query
        max_results: Number of results (max 20 for free tier)
        
    Returns:
        List of result dictionaries
    """
    import config
    import requests

    logger.info(f"Brave Search API call: {query[:100]}...")

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": config.BRAVE_SEARCH["api_key"]
    }

    params = {
        "q": query,
        "count": min(max_results, 20),
        "text_decorations": False,
        "search_lang": "en"
    }

    try:
        response = requests.get(
            config.BRAVE_SEARCH["endpoint"],
            headers=headers,
            params=params,
            timeout=config.BRAVE_SEARCH["timeout"]
        )
        response.raise_for_status()

        data = response.json()
        web_results = data.get("web", {}).get("results", [])

        if not web_results:
            logger.warning(f"Brave Search returned no results for query: {query[:60]}...")
            return []

        # Convert to standard format
        standardized = []
        for result in web_results:
            standardized.append({
                "title": result.get("title", "No title"),
                "url": result.get("url", ""),
                "description": result.get("description", "No description"),
                "age": result.get("age"),  # Preserve age if available
                "published_date": result.get("published_date")  # Preserve date if available
            })
        
        logger.info(f"Brave Search returned {len(standardized)} results for: {query[:60]}...")
        return standardized

    except requests.exceptions.RequestException as e:
        logger.error(f"Brave Search API error: {e}")
        raise


def _duckduckgo_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search using DuckDuckGo and return raw results (not formatted).
    
    Args:
        query: Search query
        max_results: Number of results
        
    Returns:
        List of result dictionaries
    """
    import time
    import ssl

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            from ddgs import DDGS
            import warnings

            logger.info(f"DuckDuckGo search: {query[:100]}... (attempt {attempt + 1}/{max_retries})")

            if attempt > 0:
                time.sleep(retry_delay * attempt)

            # Create SSL context that avoids TLS 1.3 issues
            # The ddgs library has issues with TLS 1.3 on some systems (0x304 = TLS 1.3)
            try:
                ssl_context = ssl.create_default_context()
                # Limit to TLS 1.2 maximum to avoid "Unsupported protocol version 0x304" error
                if hasattr(ssl_context, 'maximum_version'):
                    ssl_context.maximum_version = ssl.TLSVersion.TLSv1_2
            except (AttributeError, ValueError):
                # Fallback if maximum_version not available or can't be set
                ssl_context = ssl.create_default_context()

            # Suppress SSL/TLS warnings from ddgs library
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*protocol version.*")
                warnings.filterwarnings("ignore", message=".*Unsupported protocol.*")
                try:
                    with DDGS(verify=ssl_context) as ddgs:
                        results = list(ddgs.text(query, max_results=max_results))
                except ValueError as e:
                    # Handle "Unsupported protocol version 0x304" error
                    if "protocol version" in str(e) or "0x304" in str(e):
                        logger.debug(f"TLS 1.3 issue detected, retrying with different SSL config: {e}")
                        # Try without custom SSL context
                        with DDGS() as ddgs:
                            results = list(ddgs.text(query, max_results=max_results))
                    else:
                        raise

            if not results:
                logger.warning(f"DuckDuckGo returned no results for query: {query[:60]}... (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    continue
                return []

            # Convert to standard format
            standardized = []
            for result in results:
                standardized.append({
                    "title": result.get("title", "No title"),
                    "url": result.get("href", ""),
                    "description": result.get("body", "No description")
                })
            
            logger.info(f"DuckDuckGo returned {len(standardized)} results for: {query[:60]}...")
            return standardized

        except Exception as e:
            logger.warning(f"DuckDuckGo search attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                continue
            raise


def _scholar_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search Google Scholar using DuckDuckGo with site: filter.
    
    Args:
        query: Search query
        max_results: Number of results
        
    Returns:
        List of result dictionaries with [Scholar] tag in description
    """
    scholar_query = f"site:scholar.google.com {query}"
    results = _duckduckgo_search_raw(scholar_query, max_results)
    
    # Tag results as Scholar
    for result in results:
        if "description" in result:
            result["description"] = f"[Scholar] {result['description']}"
        else:
            result["description"] = "[Scholar] Academic paper"
    
    logger.info(f"Scholar search returned {len(results)} results for: {query[:60]}...")
    return results


def _pubmed_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search PubMed using DuckDuckGo with site: filter.
    
    Args:
        query: Search query
        max_results: Number of results
        
    Returns:
        List of result dictionaries with [PubMed] tag in description
    """
    pubmed_query = f"site:pubmed.ncbi.nlm.nih.gov {query}"
    results = _duckduckgo_search_raw(pubmed_query, max_results)
    
    # Tag results as PubMed
    for result in results:
        if "description" in result:
            result["description"] = f"[PubMed] {result['description']}"
        else:
            result["description"] = "[PubMed] Research article"
    
    logger.info(f"PubMed search returned {len(results)} results for: {query[:60]}...")
    return results


def _core_api_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search CORE API for open access academic papers.
    
    Args:
        query: Search query
        max_results: Number of results
        
    Returns:
        List of result dictionaries with [CORE] tag
    """
    import config
    
    academic_config = getattr(config, 'ACADEMIC_SEARCH', {})
    api_key = academic_config.get("core_api_key")
    if not api_key:
        logger.warning("CORE API key not configured, skipping CORE search")
        return []
    
    endpoint = "https://api.core.ac.uk/v3/search/works/"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    params = {
        "q": query,
        "limit": min(max_results, 10),  # CORE API limit
        "page": 1
    }
    
    try:
        response = requests.get(endpoint, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        works = data.get("results", [])
        
        results = []
        for work in works:
            # Extract authors
            authors = [author.get("name", "") for author in work.get("authors", [])]
            authors_str = ", ".join(authors[:3])  # First 3 authors
            if len(authors) > 3:
                authors_str += " et al."
            
            # Build description
            desc_parts = ["[CORE]"]
            if authors_str:
                desc_parts.append(authors_str)
            if work.get("yearPublished"):
                desc_parts.append(f"({work['yearPublished']})")
            if work.get("citationCount") is not None:
                desc_parts.append(f"Citations: {work['citationCount']}")
            
            description = " ".join(desc_parts)
            if work.get("abstract"):
                description += f" - {work['abstract'][:200]}"
            
            # Use downloadUrl if available, otherwise use display link
            url = work.get("downloadUrl") or work.get("links", [{}])[0].get("url", "")
            if not url and work.get("links"):
                for link in work.get("links", []):
                    if link.get("type") == "display":
                        url = link.get("url", "")
                        break
            
            results.append({
                "title": work.get("title", "No title"),
                "url": url,
                "description": description,
                "doi": work.get("doi"),
                "year": work.get("yearPublished"),
                "citation_count": work.get("citationCount", 0),
                "source": "CORE"
            })
        
        logger.info(f"CORE API returned {len(results)} results for: {query[:60]}...")
        return results
        
    except Exception as e:
        logger.warning(f"CORE API search failed: {e}")
        return []


def _arxiv_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search arXiv via DuckDuckGo."""
    arxiv_query = f"site:arxiv.org {query}"
    results = _duckduckgo_search_raw(arxiv_query, max_results)
    for result in results:
        result["description"] = f"[arXiv] {result.get('description', 'Preprint')}"
    logger.info(f"arXiv search returned {len(results)} results")
    return results


def _biorxiv_search_raw(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """Search bioRxiv via DuckDuckGo."""
    biorxiv_query = f"site:biorxiv.org {query}"
    results = _duckduckgo_search_raw(biorxiv_query, max_results)
    for result in results:
        result["description"] = f"[bioRxiv] {result.get('description', 'Biology preprint')}"
    logger.info(f"bioRxiv search returned {len(results)} results")
    return results


def _medrxiv_search_raw(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """Search medRxiv via DuckDuckGo."""
    medrxiv_query = f"site:medrxiv.org {query}"
    results = _duckduckgo_search_raw(medrxiv_query, max_results)
    for result in results:
        result["description"] = f"[medRxiv] {result.get('description', 'Medical preprint')}"
    logger.info(f"medRxiv search returned {len(results)} results")
    return results


def _pmc_search_raw(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search PubMed Central via DuckDuckGo."""
    # DuckDuckGo site: filters are unreliable for PMC, so use keyword search + URL filtering
    # Search with PMC keywords and filter results to PMC URLs
    pmc_keywords = ["PMC", "open access", "PubMed Central"]
    
    # Try queries with PMC keywords (avoid site: filter which causes errors)
    search_queries = [
        f"{query} {' '.join(pmc_keywords)}",
        f"{query} PMC",
        f"{query} PubMed Central open access",
    ]
    
    for search_query in search_queries:
        try:
            # Get more results than needed to account for filtering
            results = _duckduckgo_search_raw(search_query, max_results * 3)
            
            # Filter to only PMC URLs
            pmc_results = []
            for result in results:
                url = result.get("url", "").lower()
                # Check for PMC URL patterns
                if any(pattern in url for pattern in [
                    "pubmed.ncbi.nlm.nih.gov/pmc",
                    "pmc.ncbi.nlm.nih.gov",
                    "/pmc/articles/",
                    "/pmc/",
                ]):
                    result["description"] = f"[PMC] {result.get('description', 'Open access article')}"
                    pmc_results.append(result)
                    if len(pmc_results) >= max_results:
                        break
            
            if pmc_results:
                logger.info(f"PMC search returned {len(pmc_results)} results")
                return pmc_results
                
        except Exception as e:
            logger.debug(f"PMC search with query '{search_query}' failed: {e}, trying next format")
            continue
    
    logger.warning("PMC search failed with all query formats")
    return []


def _check_scihub_availability(doi: Optional[str] = None, title: Optional[str] = None) -> Optional[str]:
    """
    Check if a paper is available on Sci-Hub and return PDF URL.
    
    Args:
        doi: DOI of the paper
        title: Title of the paper
        
    Returns:
        PDF URL if found, None otherwise
    """
    import config
    import re
    from urllib.parse import quote
    import logging
    
    # Suppress BeautifulSoup encoding warnings at module level
    bs4_logger = logging.getLogger("bs4.dammit")
    bs4_logger.setLevel(logging.ERROR)
    
    if not doi and not title:
        return None
    
    academic_config = getattr(config, 'ACADEMIC_SEARCH', {})
    scihub_mirrors = academic_config.get("scihub_mirrors", [
        "https://sci-hub.se",
        "https://sci-hub.st",
        "https://sci-hub.ru"
    ])
    
    search_term = doi if doi else title
    
    for mirror in scihub_mirrors:
        try:
            url = f"{mirror}/{quote(search_term)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            
            if response.status_code == 200:
                try:
                    from bs4 import BeautifulSoup
                    import warnings
                    import logging
                    
                    # Suppress BeautifulSoup encoding warnings at both warning and logging levels
                    warnings.filterwarnings("ignore", category=UserWarning, module="bs4.dammit")
                    warnings.filterwarnings("ignore", message=".*could not be decoded.*")
                    
                    # Suppress at logger level (bs4.dammit uses logging, not warnings)
                    bs4_logger = logging.getLogger("bs4.dammit")
                    original_level = bs4_logger.level
                    bs4_logger.setLevel(logging.ERROR)
                    
                    try:
                        # Parse with explicit encoding handling
                        soup = BeautifulSoup(response.content, 'html.parser', from_encoding='utf-8')
                    finally:
                        # Restore original log level
                        bs4_logger.setLevel(original_level)
                    
                    # Look for PDF embed or download link
                    pdf_embed = soup.find('embed', {'type': 'application/pdf'})
                    if pdf_embed:
                        pdf_url = pdf_embed.get('src', '')
                        if not pdf_url.startswith('http'):
                            pdf_url = mirror + pdf_url if pdf_url.startswith('/') else f"{mirror}/{pdf_url}"
                        return pdf_url
                    
                    # Look for PDF download button/link
                    pdf_link = soup.find('a', href=re.compile(r'\.pdf|download'))
                    if pdf_link:
                        pdf_url = pdf_link.get('href', '')
                        if not pdf_url.startswith('http'):
                            pdf_url = mirror + pdf_url if pdf_url.startswith('/') else f"{mirror}/{pdf_url}"
                        return pdf_url
                        
                except ImportError:
                    logger.warning("BeautifulSoup4 not available for Sci-Hub parsing")
                    return None
                except Exception as e:
                    logger.debug(f"Sci-Hub parsing failed for {mirror}: {e}")
                    continue
                    
        except requests.exceptions.RequestException:
            continue
        except Exception as e:
            logger.debug(f"Sci-Hub check failed for {mirror}: {e}")
            continue
    
    return None


def academic_search(query: str, max_results: int = 10) -> str:
    """
    Search multiple academic sources and check Sci-Hub for full-text access.
    
    Args:
        query: Search query
        max_results: Maximum number of results to return
        
    Returns:
        Formatted academic search results with citations and full-text indicators
    """
    import config
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    logger.info(f"Academic search: {query[:100]}...")
    
    # Get config with defaults
    academic_config = getattr(config, 'ACADEMIC_SEARCH', {})
    academic_max = academic_config.get("default_max_results", 10)
    max_results = min(max_results, academic_max)
    
    # Search all sources in parallel
    all_results = []
    
    try:
        with ThreadPoolExecutor(max_workers=7) as executor:
            futures = {
                executor.submit(_scholar_search_raw, query, max_results // 2): "Scholar",
                executor.submit(_pubmed_search_raw, query, max_results // 2): "PubMed",
                executor.submit(_core_api_search, query, max_results // 2): "CORE",
                executor.submit(_arxiv_search_raw, query, max_results // 4): "arXiv",
                executor.submit(_biorxiv_search_raw, query, max_results // 6): "bioRxiv",
                executor.submit(_medrxiv_search_raw, query, max_results // 6): "medRxiv",
                executor.submit(_pmc_search_raw, query, max_results // 4): "PMC"
            }
            
            for future in as_completed(futures):
                source = futures[future]
                try:
                    results = future.result(timeout=None)  # Allow interrupt during wait
                    if results:
                        all_results.extend(results)
                        logger.info(f"Academic search: {source} returned {len(results)} results")
                except KeyboardInterrupt:
                    # Cancel remaining futures and re-raise
                    logger.info(f"Academic search interrupted, cancelling remaining searches...")
                    for f in futures:
                        f.cancel()
                    raise
                except Exception as e:
                    logger.warning(f"Academic search: {source} failed: {e}")
    except KeyboardInterrupt:
        logger.info("Academic search interrupted by user")
        raise
    
    if not all_results:
        return f"No academic results found for: {query}\n\nTry:\n- Using more specific keywords\n- Checking spelling\n- Using academic terminology"
    
    # Check Sci-Hub for full-text access in parallel
    logger.info(f"Checking Sci-Hub availability for {len(all_results)} papers...")
    
    def check_scihub_for_result(result):
        """Helper function to check Sci-Hub for a single result."""
        doi = result.get("doi")
        title = result.get("title")
        
        if doi or title:
            scihub_url = _check_scihub_availability(doi=doi, title=title)
            if scihub_url:
                result["scihub_url"] = scihub_url
                result["full_text_available"] = True
                # Update description to indicate full text
                desc = result.get("description", "")
                if "[Full Text Available]" not in desc:
                    result["description"] = f"{desc} [Full Text Available]"
        return result
    
    # Check Sci-Hub in parallel (up to 10 concurrent checks)
    if all_results:
        try:
            with ThreadPoolExecutor(max_workers=min(10, len(all_results))) as executor:
                futures = [executor.submit(check_scihub_for_result, result) for result in all_results]
                for future in as_completed(futures):
                    try:
                        future.result(timeout=None)  # Allow interrupt during wait
                    except KeyboardInterrupt:
                        # Cancel remaining futures and re-raise
                        logger.info("Sci-Hub checking interrupted, cancelling remaining checks...")
                        for f in futures:
                            f.cancel()
                        raise
        except KeyboardInterrupt:
            logger.info("Sci-Hub checking interrupted by user")
            raise
    
    # Deduplicate by title/DOI
    seen = set()
    unique_results = []
    for result in all_results:
        key = result.get("doi") or result.get("title", "").lower()
        if key and key not in seen:
            seen.add(key)
            unique_results.append(result)
    
    # Limit results
    unique_results = unique_results[:max_results]
    
    # Format results
    formatted = [f"Academic search results for: {query}\n"]
    
    for i, result in enumerate(unique_results, 1):
        title = result.get("title", "No title")
        url = result.get("url", "")
        description = result.get("description", "")
        
        formatted.append(f"\n{i}. {title}")
        if url:
            formatted.append(f"   URL: {url}")
        
        # Add DOI if available
        if result.get("doi"):
            formatted.append(f"   DOI: {result['doi']}")
        
        # Add year and citations if available
        meta_parts = []
        if result.get("year"):
            meta_parts.append(f"Year: {result['year']}")
        if result.get("citation_count") is not None:
            meta_parts.append(f"Citations: {result['citation_count']}")
        if meta_parts:
            formatted.append(f"   {' | '.join(meta_parts)}")
        
        # Add Sci-Hub link if available
        if result.get("scihub_url"):
            formatted.append(f"   [Full Text] Sci-Hub: {result['scihub_url']}")
        
        formatted.append(f"   {description}")
    
    # Add summary
    full_text_count = sum(1 for r in unique_results if r.get("full_text_available"))
    formatted.append(f"\n\nSummary: Found {len(unique_results)} papers")
    if full_text_count > 0:
        formatted.append(f" ({full_text_count} with full-text access via Sci-Hub)")
    
    return "\n".join(formatted)


def _brave_search(query: str, max_results: int = 5, query_metadata: dict = None) -> str:
    """
    Search using Brave Search API with enhanced formatting.

    Args:
        query: Search query
        max_results: Number of results (max 20 for free tier)
        query_metadata: Optional metadata from query optimization

    Returns:
        Formatted search results with enhanced metadata
    """
    logger.info(f"Brave Search: {query[:100]}...")
    
    try:
        # Get raw results
        raw_results = _brave_search_raw(query, max_results)
        
        if not raw_results:
            return f"No results found for: {query}"
        
        # Process results (deduplication, ranking, domain diversity)
        import config
        try:
            from tools.utils._result_processor import ResultProcessor
            processor = ResultProcessor(
                max_domain_results=config.WEB_SEARCH.get("max_domain_results", 2)
            )
            processed_results = processor.process_results(raw_results, query)
            processed_results = processed_results[:max_results]
        except Exception as e:
            logger.warning(f"Result processing failed: {e}, using raw results")
            processed_results = raw_results[:max_results]
        
        # Format results with enhanced metadata
        return _format_search_results(query, processed_results, "Brave", query_metadata)

    except Exception as e:
        logger.error(f"Brave Search error: {e}")
        raise


def _duckduckgo_search(query: str, max_results: int = 5, query_metadata: dict = None) -> str:
    """
    Fallback search using DuckDuckGo with enhanced formatting.

    Args:
        query: Search query
        max_results: Number of results
        query_metadata: Optional metadata from query optimization

    Returns:
        Formatted search results with enhanced metadata
    """
    logger.info(f"DuckDuckGo search: {query[:100]}...")
    
    try:
        # Get raw results
        raw_results = _duckduckgo_search_raw(query, max_results)
        
        if not raw_results:
            return f"No results found for: {query}"
        
        # Process results (deduplication, ranking, domain diversity)
        import config
        try:
            # Try importing from current directory first
            from tools.utils._result_processor import ResultProcessor
            processor = ResultProcessor(
                max_domain_results=config.WEB_SEARCH.get("max_domain_results", 2)
            )
            processed_results = processor.process_results(raw_results, query)
            processed_results = processed_results[:max_results]
        except ImportError as e:
            logger.warning(f"Result processor module not available: {e}, using raw results")
            processed_results = raw_results[:max_results]
        except Exception as e:
            logger.warning(f"Result processing failed: {e}, using raw results")
            processed_results = raw_results[:max_results]
        
        # Format results with enhanced metadata
        return _format_search_results(query, processed_results, "DuckDuckGo", query_metadata)

    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        return f"Error: Web search failed: {e}. Try again or rephrase query."


# Tool function mapping
TOOL_FUNCTIONS: Dict[str, Callable[..., str]] = {
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "make_directory": make_directory,
    "list_files": list_files,
    "get_working_directory": get_working_directory,
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
    "web_image_search": web_image_search,
    "academic_search": academic_search,
    "get_newsroom_headlines": get_newsroom_headlines,
    "search": use_search_model,  # Simple alias
    "generate_code": use_codestral,  # Simple alias
    "plan": use_reasoning_model,  # Simple alias
    "pwd": get_working_directory,  # Shell alias
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
            "description": "Edit a file by replacing exact string match. You MUST read the file first with read_file. The old_string must match exactly including whitespace and indentation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to edit"
                    },
                    "old_string": {
                        "type": "string",
                        "description": "Exact string to find and replace (must be unique in file, or use replace_all=true)"
                    },
                    "new_string": {
                        "type": "string",
                        "description": "String to replace with"
                    },
                    "replace_all": {
                        "type": "boolean",
                        "description": "If true, replace all occurrences of old_string. Default is false (single replacement)."
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
            "description": "Search the web using Brave Search API (with DuckDuckGo fallback) for current information, news, or real-time data. Automatically routes to news search when news intent is detected.",
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
