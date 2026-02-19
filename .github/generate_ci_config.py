"""Generate a stub config.py for CI (the real one is gitignored)."""

from pathlib import Path

CONFIG = '''\
"""CI stub config — safe defaults for testing."""
from pathlib import Path
import logging
from datetime import datetime

API_URL = "http://localhost:1234/v1/chat/completions"
MODEL = "test-model"
MAX_TOKENS = 2048
TIMEOUT = 60
TEMPERATURE = 0.2
SPECIALIZED_MODELS = {
    "codestral": {"model": "test", "max_tokens": 4096, "temperature": 0.3, "timeout": 90},
    "reasoning": {"model": "test", "max_tokens": 3072, "temperature": 0.4, "timeout": 90},
    "search": {"model": "test", "max_tokens": 2048, "temperature": 0.5, "timeout": 60},
    "intent_detector": {"model": "test", "max_tokens": 256, "temperature": 0.1, "timeout": 30},
    "vision": {"model": "test", "max_tokens": 3072, "temperature": 0.2, "timeout": 90},
    "image_generation": {"model": "test", "max_tokens": None, "temperature": None, "timeout": 120},
}
NEHANDA = {"endpoint": "http://localhost:8000", "timeout": 180, "enabled": False}
HF_TOKEN = ""
HF_ENDPOINTS = {}
OPENAI_API_KEY = ""
OPENAI_ENDPOINTS = {}
ANTHROPIC_API_KEY = ""
ANTHROPIC_ENDPOINTS = {}
BRAVE_SEARCH = {
    "api_key": "", "endpoint": "http://localhost:8000",
    "news_endpoint": "", "image_endpoint": "",
    "timeout": 10, "enabled": False,
}
NEWSROOM_JWT_TOKEN = ""
NEWSROOM_DAYS_BACK = 90
NEWSROOM_MAX_RELEVANT = 25
DEVELOP = {
    "explorer_model": "orchestrator", "planner_model": "reasoning",
    "coder_model": "codestral", "max_files_explore": 1000,
    "enable_linting": True, "auto_fix_lint": True,
    "auto_install_deps": True, "require_git": True,
}
WEB_SEARCH = {
    "cache_enabled": False, "cache_ttl_hours": 1,
    "cache_ttl_stable_hours": 24, "cache_max_entries": 100,
    "query_optimization": False, "intent_detection": False,
    "parallel_enabled": False, "max_domain_results": 2,
    "extract_content": False, "extract_top_n": 2,
    "synthesize_results": False, "synthesize_threshold": 5,
    "news_enabled": False, "image_enabled": False,
    "rate_limit_enabled": False, "brave_rate_limit": 66,
    "ddg_rate_limit": 100,
}
ACADEMIC_SEARCH = {"default_max_results": 10, "core_api_key": "", "scihub_mirrors": []}
DATA_ANALYSIS = {"max_code_length": 10000, "execution_timeout": 30, "plot_output_dir": "plots"}
NEHANDA_LOCAL = {
    "corpus_dir": "", "index_cache_dir": "",
    "embedding_model": "all-MiniLM-L6-v2", "chunk_size": 512, "top_k_default": 5,
}
MODEL_ENDPOINTS = {
    "orchestrator": "local", "codestral": "local", "reasoning": "local",
    "search": "local", "intent_detector": "local", "vision": "local",
    "image_generation": "local",
}
MAX_CONTEXT_MESSAGES = 50
ENABLE_CONTEXT_SUMMARIZATION = True
CONTEXT_KEEP_RECENT = 15
TOOL_CHOICE = "required"
PARALLEL_TOOL_CALLS = True
USE_JSON_ROUTING = True
USE_HEURISTIC_ROUTER = True
CONFIDENCE_THRESHOLD_HIGH = 0.85
CONFIDENCE_THRESHOLD_LOW = 0.60
ENABLE_CONFIDENCE_FALLBACK = True
FALLBACK_MODEL_ENDPOINT = "local"
LOGGING_LEVEL = logging.INFO
LOGGING_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DIR = Path.home() / ".zorora" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"zorora_{datetime.now().strftime('%Y%m%d')}.log"
UI_ENABLED = True
UI_NO_COLOR = False
UI_MARKDOWN_RENDERING = True
UI_SYNTAX_HIGHLIGHTING = True
UI_SPINNER_STYLE = "dots"
UI_SHOW_TOKEN_COUNT = True
UI_THEME = "monokai"
SYSTEM_PROMPT_FILE = Path(__file__).parent / "system_prompt.txt"


def load_system_prompt():
    if SYSTEM_PROMPT_FILE.exists():
        return SYSTEM_PROMPT_FILE.read_text().strip()
    return "You are a local coding assistant with tool access."
'''

if __name__ == "__main__":
    Path("config.py").write_text(CONFIG)
    print("Created config.py stub for CI")
