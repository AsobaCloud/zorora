"""Configuration constants and settings.

IMPORTANT: Copy this file to config.py and update with your actual values.
DO NOT commit config.py to git (it contains API tokens).
"""

from pathlib import Path

# LM Studio API Configuration (OpenAI-compatible)
API_URL = "http://localhost:1234/v1/chat/completions"
MODEL = "your-model-name"  # Regular model - fast and decisive
MAX_TOKENS = 2048  # Increased from 1000 for longer responses
TIMEOUT = 60  # Increased from 30s for complex tool operations
TEMPERATURE = 0.2

# Specialized Model Configuration
SPECIALIZED_MODELS = {
    "codestral": {
        "model": "your-model-name",
        "max_tokens": 4096,
        "temperature": 0.3,
        "timeout": 90,
    },
    "reasoning": {
        "model": "your-model-name",
        "max_tokens": 3072,
        "temperature": 0.4,
        "timeout": 90,
    },
    "search": {
        "model": "your-model-name",
        "max_tokens": 2048,
        "temperature": 0.5,
        "timeout": 60,
    },
    "intent_detector": {
        "model": "your-model-name",  # Use fast non-thinking model
        "max_tokens": 256,  # Only need short JSON output
        "temperature": 0.1,  # Low temp for consistent structured output
        "timeout": 30,  # Fast response needed
    }
}

# External API Configuration
ENERGY_ANALYST = {
    "endpoint": "http://localhost:8000",  # Local or Production endpoint
    "timeout": 180,  # 3 minutes for slower LLM inference
    "enabled": True,  # Set to False to disable energy analyst tool
}
# Available endpoints:
# - Local: http://localhost:8000
# - Production: https://energyanalystragservice-production.up.railway.app

# ONA Platform API Configuration (Optional)
# For ML model observation workflows (ml-list-challengers, ml-show-metrics, etc.)
# Configure via environment variables:
#   export ONA_API_BASE_URL="https://p0c7u3j9wi.execute-api.af-south-1.amazonaws.com/api/v1"
#   export ONA_API_TOKEN="your-token-here"
#   export ONA_USE_IAM="false"  # Set to "true" for IAM authentication

# Newsroom API Configuration (Optional)
# For accessing Ona platform newsroom articles in research workflows.
# Get your JWT token from the Ona data-admin portal.
# See docs/TROUBLESHOOTING.md for setup instructions.
NEWSROOM_JWT_TOKEN = None  # Set to your JWT token string, or use env var NEWSROOM_JWT_TOKEN
NEWSROOM_DAYS_BACK = 90  # Number of days of articles to search (90 = last quarter)
NEWSROOM_MAX_RELEVANT = 25  # Max relevant articles to return after filtering

# Brave Search API Configuration
# Get your free API key at: https://brave.com/search/api/
# Free tier: 2000 queries/month (~66/day)
BRAVE_SEARCH = {
    "api_key": "YOUR_BRAVE_API_KEY_HERE",
    "endpoint": "https://api.search.brave.com/res/v1/web/search",
    "news_endpoint": "https://api.search.brave.com/res/v1/news/search",
    "image_endpoint": "https://api.search.brave.com/res/v1/images/search",
    "timeout": 10,
    "enabled": True,  # Set to False to force DuckDuckGo
}

# Web Search Enhancement Configuration
WEB_SEARCH = {
    # Caching
    "cache_enabled": True,
    "cache_ttl_hours": 1,  # General queries
    "cache_ttl_stable_hours": 24,  # Stable queries (e.g., "Python documentation")
    "cache_max_entries": 100,
    
    # Query Optimization
    "query_optimization": True,
    "intent_detection": True,
    
    # Multi-Source (Sprint 2)
    "parallel_enabled": False,  # Will enable in Sprint 2
    "max_domain_results": 2,  # Max results per domain
    
    # Content Extraction (Sprint 3 - opt-in)
    "extract_content": False,  # Set to True to enable
    "extract_top_n": 2,  # Extract from top N results
    
    # Synthesis (Sprint 3 - opt-in)
    "synthesize_results": False,  # Use LLM to synthesize
    "synthesize_threshold": 5,  # Min results to synthesize
    
    # Specialized Search (Sprint 4)
    "news_enabled": True,
    "image_enabled": False,
    "academic_max_results": 3,  # Max Scholar/PubMed results each (always included in web search)
    
    # Rate Limiting (Sprint 5)
    "rate_limit_enabled": False,  # Will enable in Sprint 5
    "brave_rate_limit": 66,  # queries per day (free tier: 2000/month)
    "ddg_rate_limit": 100,  # queries per hour (estimated)
}

# Academic Search Configuration
ACADEMIC_SEARCH = {
    "default_max_results": 10,
    "core_api_key": "bKT02ehoQ3GynrPZ7d4fwHFDVEsiXxl1",
    "scihub_mirrors": [
        "https://sci-hub.se",
        "https://sci-hub.st",
        "https://sci-hub.ru"
    ]
}

# Hugging Face Inference Endpoints
HF_TOKEN = "hf_YOUR_TOKEN_HERE"  # Replace with your Hugging Face API token
HF_ENDPOINTS = {
    "qwen-coder-32b": {
        "url": "https://your-endpoint.hf.space/v1/chat/completions",
        "model_name": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "timeout": 120,
        "enabled": True,
    },
    # Add more HF endpoints here as needed
}

# Model Endpoint Mapping (which endpoint each role uses)
# Values: "local" for LM Studio, or HF endpoint key (e.g., "qwen-coder-32b")
MODEL_ENDPOINTS = {
    "orchestrator": "local",
    "codestral": "local",
    "reasoning": "local",
    "search": "local",
    "intent_detector": "local",
}

# Context Management
MAX_CONTEXT_MESSAGES = 50  # Changed from None (unlimited) to prevent context overflow

# Tool Configuration
TOOL_CHOICE = "required"  # Force tool usage - was "auto"
PARALLEL_TOOL_CALLS = True  # Enable parallel tool execution

# Logging Configuration
import logging
LOGGING_LEVEL = logging.INFO
LOGGING_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = Path(__file__).parent / "repl.log"

# UI Configuration
UI_ENABLED = True  # Master switch for rich UI
UI_NO_COLOR = False  # Accessibility mode (respects NO_COLOR env var)
UI_MARKDOWN_RENDERING = True  # Render markdown in responses
UI_SYNTAX_HIGHLIGHTING = True  # Syntax highlight code blocks
UI_SPINNER_STYLE = "dots"  # Spinner animation: dots, line, arc, etc.
UI_SHOW_TOKEN_COUNT = True  # Display token usage in loading animation
UI_THEME = "monokai"  # Pygments theme for syntax highlighting

# System Prompt
SYSTEM_PROMPT_FILE = Path(__file__).parent / "system_prompt.txt"


def load_system_prompt() -> str:
    """Load system prompt from file."""
    if SYSTEM_PROMPT_FILE.exists():
        return SYSTEM_PROMPT_FILE.read_text().strip()
    return """You are a local coding assistant with tool access.

Rules:
- Use tools when you need filesystem information (files, directories, file contents).
- After a tool result is provided, respond naturally to the user's question.
- Be concise and direct in your responses.
"""
