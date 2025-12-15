"""Tool registry for tool definitions and function mapping."""

from typing import Dict, Callable, List, Dict as DictType, Any, Optional
from pathlib import Path
import subprocess
import logging

logger = logging.getLogger(__name__)


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


def use_codestral(code_context: str) -> str:
    """
    Generate or refactor code using Codestral-22B model.

    Args:
        code_context: Description of code to generate, existing code to refactor,
                     or programming task to solve

    Returns:
        Generated code with explanations
    """
    if not code_context or not isinstance(code_context, str):
        return "Error: code_context must be a non-empty string"

    if len(code_context) > 8000:
        return "Error: code_context too long (max 8000 characters)"

    try:
        from llm_client import LLMClient
        import config

        logger.info(f"Delegating to Codestral: {code_context[:100]}...")

        model_config = config.SPECIALIZED_MODELS["codestral"]
        client = LLMClient(
            api_url=config.API_URL,
            model=model_config["model"],
            max_tokens=model_config["max_tokens"],
            temperature=model_config["temperature"],
            timeout=model_config["timeout"]
        )

        response = client.chat_complete([
            {
                "role": "system",
                "content": "You are an expert software engineer. Generate clean, well-documented, production-quality code. Include docstrings and comments for complex logic."
            },
            {
                "role": "user",
                "content": code_context
            }
        ])

        content = client.extract_content(response)
        if not content or not content.strip():
            return "Error: Codestral returned empty response"

        return content.strip()

    except Exception as e:
        logger.error(f"Codestral error: {e}")
        return f"Error: Failed to call Codestral: {str(e)}"


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

    if len(task) > 8000:
        return "Error: task too long (max 8000 characters)"

    try:
        from llm_client import LLMClient
        import config

        logger.info(f"Delegating to Reasoning model: {task[:100]}...")

        model_config = config.SPECIALIZED_MODELS["reasoning"]
        client = LLMClient(
            api_url=config.API_URL,
            model=model_config["model"],
            max_tokens=model_config["max_tokens"],
            temperature=model_config["temperature"],
            timeout=model_config["timeout"]
        )

        response = client.chat_complete([
            {
                "role": "system",
                "content": "You are a logical reasoning and planning expert. Break down complex problems into clear, actionable steps. Consider edge cases and trade-offs."
            },
            {
                "role": "user",
                "content": task
            }
        ])

        content = client.extract_content(response)
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

    if len(query) > 8000:
        return "Error: query too long (max 8000 characters)"

    try:
        from llm_client import LLMClient
        import config

        logger.info(f"Delegating to Search model: {query[:100]}...")

        model_config = config.SPECIALIZED_MODELS["search"]
        client = LLMClient(
            api_url=config.API_URL,
            model=model_config["model"],
            max_tokens=model_config["max_tokens"],
            temperature=model_config["temperature"],
            timeout=model_config["timeout"]
        )

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
    "list_files": list_files,
    "run_shell": run_shell,
    "apply_patch": apply_patch,
    "use_codestral": use_codestral,
    "use_reasoning_model": use_reasoning_model,
    "use_search_model": use_search_model,
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
