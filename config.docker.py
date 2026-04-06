"""Configuration constants and settings."""

import logging
import os
from datetime import datetime
from pathlib import Path

def _env_flag(name: str, default: bool) -> bool:
    """Parse boolean feature flags from environment variables."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

# LM Studio API Configuration (OpenAI-compatible)
API_URL = os.environ.get("LLM_API_URL", "http://localhost:1234/v1/chat/completions")
MODEL = "qwen/qwen3-vl-4b"  # Regular model - fast and decisive
MAX_TOKENS = 2048  # Increased from 1000 for longer responses
TIMEOUT = 60  # Increased from 30s for complex tool operations
TEMPERATURE = 0.2

# Specialized Model Configuration
SPECIALIZED_MODELS = {
    "codestral": {
        "model": "qwen/qwen3-vl-4b",
        "max_tokens": 4096,
        "temperature": 0.3,
        "timeout": 90,
    },
    "reasoning": {
        "model": "asoba/nehanda-v1-7b",
        "max_tokens": 3072,
        "temperature": 0.4,
        "timeout": 90,
    },
    "search": {
        "model": "asoba/nehanda-v1-7b",
        "max_tokens": 2048,
        "temperature": 0.5,
        "timeout": 60,
    },
    "intent_detector": {
        "model": "qwen/qwen3-vl-4b",  # Use same model as orchestrator (non-thinking)
        "max_tokens": 256,  # Only need short JSON output
        "temperature": 0.1,  # Low temp for consistent structured output
        "timeout": 30,  # Fast response needed
    },
    "vision": {
        "model": "qwen/qwen3-vl-4b",  # Vision-language model for OCR and image analysis
        "max_tokens": 3072,
        "temperature": 0.2,
        "timeout": 90,
    },
    "image_generation": {
        "model": "black-forest-labs/FLUX.1-schnell",  # Text-to-image generation
        "max_tokens": None,  # Not applicable for image generation
        "temperature": None,  # Not applicable for image generation
        "timeout": 120,  # Flux Schnell is fast, but allow time for generation
    }
}

# External API Configuration
NEHANDA = {
    "endpoint": "https://nehandarag-production.up.railway.app",  # Local or Production endpoint
    "timeout": 180,  # 3 minutes for slower LLM inference
    "enabled": True,  # Set to False to disable Nehanda energy analyst tool
}
# Available endpoints:
# - Local: http://localhost:8000
# - Production: https://energyanalystragservice-production.up.railway.app

# Hugging Face Inference Endpoints
HF_TOKEN = os.environ.get("HF_TOKEN", "")
HF_ENDPOINTS = {
    "qwen-coder-32b": {
        "url": "https://bhp3ng580aqunifx.us-east4.gcp.endpoints.huggingface.cloud/v1/chat/completions",
        "model_name": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "api_format": "openai",
        "timeout": 120,
        "enabled": True,
    },
    "flux-schnell": {
        "url": "https://unt2lkqyzp7onojo.us-east-1.aws.endpoints.huggingface.cloud",
        "model_name": "black-forest-labs/FLUX.1-schnell",
        "timeout": 120,
        "enabled": True,
    },
    "nehanda-v3": {
        "url": "https://tmlbj0s0e5y41gft.us-east-1.aws.endpoints.huggingface.cloud",
        "model_name": "asoba/nehanda-v1-7b",
        "api_format": "hf_inference",
        "chat_template": "mistral",
        "timeout": 120,
        "enabled": True,
    },
    # Add more HF endpoints here as needed
}

# OpenAI API Configuration (matches HF_ENDPOINTS pattern)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_ENDPOINTS = {
    "gpt-4": {
        "model": "gpt-4",
        "timeout": 60,
        "enabled": True,
        "max_tokens": 4096,
    },
    "gpt-4-turbo": {
        "model": "gpt-4-turbo-preview",
        "timeout": 60,
        "enabled": True,
        "max_tokens": 4096,
    },
    "gpt-3.5-turbo": {
        "model": "gpt-3.5-turbo",
        "timeout": 30,
        "enabled": True,
        "max_tokens": 2048,
    },
    # Add more OpenAI models here as needed
}

# Anthropic API Configuration (matches HF_ENDPOINTS pattern)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_ENDPOINTS = {
    "claude-opus": {
        "model": "claude-3-opus-20240229",
        "timeout": 120,
        "enabled": True,
        "max_tokens": 4096,
    },
    "claude-sonnet": {
        "model": "claude-3-sonnet-20240229",
        "timeout": 60,
        "enabled": True,
        "max_tokens": 4096,
    },
    "claude-haiku": {
        "model": "claude-3-haiku-20240307",
        "timeout": 30,
        "enabled": True,
        "max_tokens": 4096,
    },
    # Add more Anthropic models here as needed
}

# Brave Search API Configuration
# Get your free API key at: https://brave.com/search/api/
# Free tier: 2000 queries/month (~66/day)
BRAVE_SEARCH = {
    "api_key": os.environ.get("BRAVE_SEARCH_API_KEY", ""),
    "endpoint": "https://api.search.brave.com/res/v1/web/search",
    "news_endpoint": "https://api.search.brave.com/res/v1/news/search",
    "image_endpoint": "https://api.search.brave.com/res/v1/images/search",
    "timeout": 10,
    "enabled": True,  # Set to False to force DuckDuckGo
}

# Newsroom Configuration
# JWT token for Ona data-admin newsroom API (valid for 1 year from Jan 2026)
NEWSROOM_JWT_TOKEN = os.environ.get("NEWSROOM_JWT_TOKEN", "")
NEWSROOM_DAYS_BACK = 90  # Number of days of articles to search (90 = last quarter)
NEWSROOM_MAX_RELEVANT = 25  # Max relevant articles to return after filtering

# Development Workflow (/develop) Configuration
DEVELOP = {
    "explorer_model": "orchestrator",  # Use orchestrator model for exploration (cost-effective)
    "planner_model": "reasoning",      # Use reasoning model for planning (better quality)
    "coder_model": "codestral",        # Use codestral for code generation
    "max_files_explore": 1000,         # Warn if more than this many files
    "enable_linting": True,            # Enable lint phase after code execution
    "auto_fix_lint": True,             # Auto-fix lint errors if possible
    "auto_install_deps": True,         # Auto-run npm install / pip install after execution
    "require_git": True,               # Require git repository for safety
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
    "parallel_enabled": True,  # Search multiple sources simultaneously
    "max_domain_results": 3,  # Max results per domain

    # Content Extraction (Sprint 3 - opt-in)
    "extract_content": False,  # Set to True to enable
    "extract_top_n": 2,  # Extract from top N results

    # Synthesis (Sprint 3 - opt-in)
    "synthesize_results": False,  # Use LLM to synthesize
    "synthesize_threshold": 5,  # Min results to synthesize

    # Specialized Search (Sprint 4)
    "news_enabled": True,
    "image_enabled": False,

    # Rate Limiting (Sprint 5)
    "rate_limit_enabled": False,  # Will enable in Sprint 5
    "brave_rate_limit": 66,  # queries per day (free tier: 2000/month)
    "ddg_rate_limit": 100,  # queries per hour (estimated)
}

# Deep Research Depth Profiles
DEPTH_PROFILES = {
    1: {"max_results_per_source": 10, "max_sources": 25, "max_domain_results": 3, "query_variants": 1, "include_brave_news": False},
    2: {"max_results_per_source": 20, "max_sources": 40, "max_domain_results": 3, "query_variants": 2, "include_brave_news": False},
    3: {"max_results_per_source": 20, "max_sources": 60, "max_domain_results": 4, "query_variants": 3, "include_brave_news": True},
}

# Research Type Configuration (SEP-027)
RESEARCH_TYPES = {
    "trend_analysis": {
        "label": "Trend Analysis",
        "description": "Historical trends over time",
    },
    "comparative": {
        "label": "Comparative",
        "description": "Compare two subjects",
        "requires_subjects": True,
    },
    "factor_analysis": {
        "label": "Factor Analysis",
        "description": "Causal factors and drivers",
    },
    "sbar": {
        "label": "SBAR",
        "description": "Situation-Background-Assessment-Recommendation",
    },
}

# Query Decomposition Configuration (SEP-026)
QUERY_DECOMPOSITION = {
    "enabled": True,
    "max_intents": 4,
    "min_clause_length": 10,
    "resolve_cross_refs": True,
}

# Content Fetching Configuration (SEP-005)
CONTENT_FETCH = {
    "enabled": True,
    "max_sources": 20,
    "timeout_per_url": 10,
    "skip_types": ["academic"],
    "max_workers": 8,
    "prompt_content_budget": 15000,
}

# Model Token Budgets (SEP-019: max ~3000 input tokens per reasoning call)
# Values in chars; divide by 3.5 for approximate token count.
MODEL_BUDGETS = {
    "subtopic_decomposition": {"max_input_chars": 1750, "max_output_tokens": 1024},
    "finding_clustering":     {"max_input_chars": 8750, "max_output_tokens": 2048},
    "synthesis_outline":      {"max_input_chars": 5250, "max_output_tokens": 1024},
    "synthesis_section":      {"max_input_chars": 5250, "max_output_tokens": 1024},
}

# Synthesis Configuration (SEP-019)
SYNTHESIS = {
    "content_budget": 5000,           # Max chars for source content in prompt
    "max_sources_for_content": 20,    # Sources formatted into prompt
    "max_findings": 15,               # Findings included in prompt
    "min_chars_per_source": 500,      # Floor for per-source excerpt
    "max_credibility_sources": 10,    # Top authoritative sources in credibility section
    "max_alternatives": 3,            # Max alternative names for generic subjects
    "outline_sections": [4, 6],       # Min/max thematic sections
    "max_sources_per_section": 4,     # Sources routed to each section expansion
    "max_findings_per_section": 3,    # Findings routed to each section expansion
    "relevance_min_score": 0.15,      # Minimum relevance score for filtering
    "clustering_char_budget": 8000,   # Char budget for clustering prompt
    "clustering_max_sources": 25,     # Max sources fed to clustering
    "clustering_snippet_chars": 300,  # Per-source snippet cap in clustering
}

# Academic Search Configuration
ACADEMIC_SEARCH = {
    "default_max_results": 10,
    "core_api_key": os.environ.get("CORE_API_KEY", ""),
    "scihub_mirrors": [
        "https://sci-hub.se",
        "https://sci-hub.st",
        "https://sci-hub.ru"
    ]
}

# OpenAlex Configuration (free, no auth, polite pool with email)
OPENALEX = {
    "enabled": True,
    "endpoint": "https://api.openalex.org/works",
    "timeout": 15,
    "polite_email": "admin@asoba.co",
}

# Semantic Scholar Configuration (free, 100 req/5min, optional API key)
SEMANTIC_SCHOLAR = {
    "enabled": True,
    "endpoint": "https://api.semanticscholar.org/graph/v1/paper/search",
    "timeout": 15,
    "api_key": "",
}

# World Bank Open Data Configuration (free, no auth)
WORLD_BANK = {
    "enabled": True,
    "search_endpoint": "https://search.worldbank.org/api/v2/wds",
    "timeout": 15,
}

# Congress.gov Configuration (free, API key required)
CONGRESS_GOV = {
    "enabled": True,
    "endpoint": "https://api.congress.gov/v3/bill",
    "timeout": 15,
    "api_key": os.environ.get("CONGRESS_GOV_API_KEY", ""),
}

# GovTrack Configuration (free, no auth)
GOVTRACK = {
    "enabled": True,
    "endpoint": "https://www.govtrack.us/api/v2/bill",
    "timeout": 15,
}

# Federal Register Configuration (free, no auth)
FEDERAL_REGISTER = {
    "enabled": True,
    "endpoint": "https://www.federalregister.gov/api/v1/documents.json",
    "timeout": 15,
}

# SEC EDGAR Configuration (free, User-Agent required)
SEC_EDGAR = {
    "enabled": True,
    "endpoint": "https://efts.sec.gov/LATEST/search-index",
    "timeout": 15,
    "user_agent": "Asoba admin@asoba.co",
}

# CrossRef API Configuration (free, polite pool with mailto)
CROSSREF = {
    "enabled": True,
    "endpoint": "https://api.crossref.org/works",
    "timeout": 15,
    "polite_email": "admin@asoba.co",
}

# arXiv API Configuration (free, no auth, 1 req/s)
ARXIV = {
    "enabled": True,
    "endpoint": "http://export.arxiv.org/api/query",
    "timeout": 15,
}

# World Bank Indicators API Configuration (free, no auth)
WORLD_BANK_INDICATORS = {
    "enabled": True,
    "endpoint": "https://api.worldbank.org/v2",
    "timeout": 45,
    "default_country": "all",
}

# Data Analysis Configuration
DATA_ANALYSIS = {
    "max_code_length": 10000,      # Max characters of code to execute
    "execution_timeout": 30,        # Seconds before killing analysis
    "plot_output_dir": "plots",     # Directory for generated plots
}

# FRED (Federal Reserve Economic Data) Configuration
FRED = {
    "api_key": os.environ.get("FRED_API_KEY", ""),
    "timeout": 30,
    "enabled": True,
}

# EIA Open Data v2 Configuration
EIA = {
    "api_key": os.environ.get("EIA_API_KEY", ""),
    "base_url": "https://api.eia.gov/v2",
    "timeout": 30,
    "enabled": True,
    "max_rows_per_request": 5000,
}

# OpenEI Utility Rate Database Configuration
OPENEI = {
    "api_key": os.environ.get("OPENEI_API_KEY", ""),
    "base_url": "https://api.openei.org",
    "timeout": 30,
    "enabled": True,
}

# Regulatory ingest configuration
REGULATORY = {
    "stale_threshold_hours": 168,
    "timeout_seconds": 30,
    "rps_workbook_dir": "data",
    "jurisdictions": ["US", "ZA", "ZW"],
    "utility_rate_locations": [
        {"name": "Denver", "state": "CO", "lat": 39.7392, "lon": -104.9903},
    ],
    "zimbabwe_seed_events": [
        {
            "title": "Public Notice - Fuel Notice 4 October 2025",
            "published_date": "2025-10-06",
            "source_url": "https://www.zera.co.zw/press-releases-public-notices/",
            "summary": "PUBLIC NOTICE: NOTIFICATION OF PETROLEUM PRODUCT PRICES",
            "category": "Press Releases",
        },
        {
            "title": "Public Notice - Fuel Notice 4 September 2025",
            "published_date": "2025-09-04",
            "source_url": "https://www.zera.co.zw/press-releases-public-notices/",
            "summary": "PUBLIC NOTICE: NOTIFICATION OF PETROLEUM PRODUCT PRICES",
            "category": "Press Releases",
        },
    ],
}

# Recurring digest alerts configuration
ALERTS = {
    "enabled": True,
    "check_interval_seconds": 300,
    "max_results_per_alert": 50,
}

# yfinance Configuration (no API key needed)
YFINANCE = {
    "enabled": True,
    "timeout": 30,
}

# Market Data Analysis Configuration
MARKET_DATA = {
    "stale_threshold_hours": 24,
    "chart_output_dir": "plots",
    "chart_dpi": 150,
    "chart_style": "seaborn-v0_8-darkgrid",
    "analysis_lookback_days": [30, 90, 365],
    "correlation_min_observations": 30,
}

# Imaging (OSINT mineral intelligence) Configuration
IMAGING = {
    "enabled": True,
    "mrds_wfs_endpoint": "https://mrdata.usgs.gov/services/wfs/mrds",
    "mrds_timeout": 60,
    "mrds_bbox": [15, -35, 40, -15],  # lon_min, lat_min, lon_max, lat_max
    "stale_threshold_hours": 168,  # 7 days — static datasets
    "satellite_tile_url": "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2021_3857/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg",
    "viirs_tile_url": "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_SNPP_DayNightBand_AtSensor_M15/default/2024-01-01/GoogleMapsCompatible_Level8/{z}/{y}/{x}.png",
    "solar_overlay_tile_url": "https://d2asdkx1wwwi7q.cloudfront.net/v20250327/pvout_csi_global/{z}/z{z}_{x}x{y}.jpg",
    "solar_overlay_attribution": "Global Solar Atlas PVOUT",
    "resource_point_endpoint": "https://power.larc.nasa.gov/api/temporal/climatology/point",
    "resource_timeout_seconds": 30,
    "target_commodities": ["Rare earths", "Niobium", "Tantalum", "Lithium", "Cobalt",
                           "Platinum", "Chromium", "Manganese", "Vanadium"],
}

# SAPP (Southern African Power Pool) DAM Configuration
SAPP = {
    "enabled": True,
    "data_dir": "data",
    "dam_files": {
        "rsan": "DAM_RSAN_01-Jan-2025_To_31-Mar-2026_152.xlsx",
        "rsas": "DAM_RSAS_01-Jan-2025_To_31-Mar-2026_140.xlsx",
        "zim": "DAM_ZIM_01-Jan-2025_To_31-Mar-2026_109.xlsx",
    },
}

# Eskom Operational Data Configuration
ESKOM = {
    "enabled": True,
    "data_dir": "data",
    "demand_file": "System_hourly_actual_and_forecasted_demand.csv",
    "generation_file": "Hourly_Generation.csv",
    "station_buildup_file": "Station_Build_Up.csv",
    "tariff_file": "Eskom-tariffs-1-April-2025-ver-2.xlsm",
    "fetch_urls": {
        "station_buildup": "https://www.eskom.co.za/dataportal/wp-content/uploads/{year}/{month:02d}/Station_Build_Up.csv",
        "demand": "https://www.eskom.co.za/dataportal/wp-content/uploads/{year}/{month:02d}/System_hourly_actual_and_forecasted_demand.csv",
        "generation": "https://www.eskom.co.za/dataportal/wp-content/uploads/{year}/{month:02d}/Hourly_Generation.csv",
    },
}

# Ember Energy API Configuration
EMBER = {
    "enabled": True,
    "api_key": os.environ.get("EMBER_API_KEY", ""),
    "endpoint": "https://api.ember-energy.org/v1",
    "timeout": 30,
}

# GCCA (Grid Connection Capacity Assessment) Configuration
GCCA = {
    "enabled": True,
    "gpkg_path": "data/GCCA 2025 GIS/AREAS_GCCA2025.gpkg",
}

# Nehanda Local (offline policy search) Configuration
NEHANDA_LOCAL = {
    "corpus_dir": "",               # Directory containing .txt policy documents
    "index_cache_dir": "",          # Directory to cache FAISS index
    "embedding_model": "all-MiniLM-L6-v2",
    "chunk_size": 512,              # Max tokens per chunk
    "top_k_default": 5,            # Default number of results
}

# Local SME corpus for diligence deep research
LOCAL_SME_CORPUS = {
    "enabled": _env_flag("ZORORA_LOCAL_SME_CORPUS_ENABLED", True),
    "path": os.environ.get("ZORORA_LOCAL_SME_CORPUS_PATH", "data/sme_orthodoxies"),
    "max_results_per_query": 6,
    "snippet_chars": 320,
    "body_chars": 4000,
    "pdf_max_pages": 35,
}

# Model Endpoint Mapping (which endpoint each role uses)
# Values: "local" for LM Studio, or HF endpoint key (e.g., "qwen-coder-32b")
MODEL_ENDPOINTS = {
    "orchestrator": "local",
    "codestral": "local",
    "reasoning": "nehanda-v3",
    "search": "nehanda-v3",
    "intent_detector": "local",
    "vision": "local",
    "image_generation": "local",  # Set to HF endpoint key via /models
}

# Context Management
MAX_CONTEXT_MESSAGES = 50  # Changed from None (unlimited) to prevent context overflow
ENABLE_CONTEXT_SUMMARIZATION = True  # Summarize old messages instead of deleting them
CONTEXT_KEEP_RECENT = 15  # Keep this many recent messages after summarization (conservative for VRAM)

# Tool Configuration
TOOL_CHOICE = "required"  # Force tool usage - was "auto"
PARALLEL_TOOL_CALLS = True  # Enable parallel tool execution

# Routing Configuration
USE_JSON_ROUTING = True  # Use new JSON-based routing system (vs legacy string-based)
USE_HEURISTIC_ROUTER = True  # Enable fast keyword-based routing before LLM
CONFIDENCE_THRESHOLD_HIGH = 0.85  # Execute immediately if confidence >= this
CONFIDENCE_THRESHOLD_LOW = 0.60   # Fallback to larger model if confidence < this
ENABLE_CONFIDENCE_FALLBACK = True  # Use larger model for low-confidence routing
FALLBACK_MODEL_ENDPOINT = "local"  # Endpoint for 8B fallback model (if different from orchestrator)

# Logging Configuration
LOGGING_LEVEL = logging.INFO
LOGGING_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
# Logs directory
LOG_DIR = Path.home() / ".zorora" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
# Log file with date suffix
LOG_FILE = LOG_DIR / f"zorora_{datetime.now().strftime('%Y%m%d')}.log"

# Product Surface Configuration
# In containerized deployments, web workflows are primary for customers.
WEB_RESEARCH_ENABLED = _env_flag("ZORORA_WEB_RESEARCH_ENABLED", True)
WEB_MARKET_INTEL_ENABLED = _env_flag("ZORORA_WEB_MARKET_INTEL_ENABLED", True)
REPL_LEGACY_ENABLED = _env_flag("ZORORA_REPL_LEGACY_ENABLED", False)
REPL_CODEGEN_ENABLED = _env_flag("ZORORA_REPL_CODEGEN_ENABLED", False)

# UI Configuration
UI_ENABLED = True  # Master switch for rich UI
UI_NO_COLOR = False  # Accessibility mode (respects NO_COLOR env var)
UI_MARKDOWN_RENDERING = True  # Render markdown in responses
UI_SYNTAX_HIGHLIGHTING = True  # Syntax highlight code blocks
UI_SPINNER_STYLE = "dots"  # Spinner animation: dots, line, arc, etc.
UI_SHOW_TOKEN_COUNT = True  # Display token usage in loading animation
UI_THEME = "monokai"  # Pygments theme for syntax highlighting

# Progress Display Configuration
UI_PROGRESS_ENABLED = True      # Enable/disable progress display
UI_PROGRESS_VERBOSE = False      # Show detailed tool calls by default
UI_PROGRESS_COLLAPSIBLE = True   # Allow expanding/collapsing details (future)
UI_PROGRESS_PERSIST = False      # Save progress events to disk (future)
UI_PROGRESS_SHOW_ETA = True      # Show estimated time remaining (future)

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
