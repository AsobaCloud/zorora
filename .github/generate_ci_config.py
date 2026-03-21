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
DEPTH_PROFILES = {
    1: {"max_results_per_source": 10, "max_sources": 25, "max_domain_results": 3, "query_variants": 1, "include_brave_news": False},
    2: {"max_results_per_source": 20, "max_sources": 40, "max_domain_results": 3, "query_variants": 2, "include_brave_news": False},
    3: {"max_results_per_source": 20, "max_sources": 60, "max_domain_results": 4, "query_variants": 3, "include_brave_news": True},
}
RESEARCH_TYPES = {
    "trend_analysis": {"label": "Trend Analysis", "description": "Historical trends over time"},
    "comparative": {"label": "Comparative", "description": "Compare two subjects", "requires_subjects": True},
    "factor_analysis": {"label": "Factor Analysis", "description": "Causal factors and drivers"},
    "sbar": {"label": "SBAR", "description": "Situation-Background-Assessment-Recommendation"},
}
QUERY_DECOMPOSITION = {
    "enabled": True, "max_intents": 4, "min_clause_length": 10, "resolve_cross_refs": True,
}
CONTENT_FETCH = {
    "enabled": True, "max_sources": 20, "timeout_per_url": 10,
    "skip_types": ["academic"], "max_workers": 8, "prompt_content_budget": 15000,
}
MODEL_BUDGETS = {
    "subtopic_decomposition": {"max_input_chars": 1750, "max_output_tokens": 1024},
    "finding_clustering": {"max_input_chars": 8750, "max_output_tokens": 2048},
    "synthesis_outline": {"max_input_chars": 5250, "max_output_tokens": 1024},
    "synthesis_section": {"max_input_chars": 5250, "max_output_tokens": 1024},
}
SYNTHESIS = {
    "content_budget": 5000, "max_sources_for_content": 20, "max_findings": 15,
    "min_chars_per_source": 500, "max_credibility_sources": 10, "max_alternatives": 3,
    "outline_sections": [4, 6], "max_sources_per_section": 4, "max_findings_per_section": 3,
    "relevance_min_score": 0.15, "clustering_char_budget": 8000,
    "clustering_max_sources": 25, "clustering_snippet_chars": 300,
}
ACADEMIC_SEARCH = {"default_max_results": 10, "core_api_key": "", "scihub_mirrors": []}
OPENALEX = {"enabled": True, "endpoint": "https://api.openalex.org/works", "timeout": 15, "polite_email": ""}
SEMANTIC_SCHOLAR = {"enabled": True, "endpoint": "https://api.semanticscholar.org/graph/v1/paper/search", "timeout": 15, "api_key": ""}
WORLD_BANK = {"enabled": True, "search_endpoint": "https://search.worldbank.org/api/v2/wds", "timeout": 15}
CONGRESS_GOV = {"enabled": True, "endpoint": "https://api.congress.gov/v3/bill", "timeout": 15, "api_key": ""}
GOVTRACK = {"enabled": True, "endpoint": "https://www.govtrack.us/api/v2/bill", "timeout": 15}
FEDERAL_REGISTER = {"enabled": True, "endpoint": "https://www.federalregister.gov/api/v1/documents.json", "timeout": 15}
SEC_EDGAR = {"enabled": True, "endpoint": "https://efts.sec.gov/LATEST/search-index", "timeout": 15, "user_agent": "CI test@test.com"}
CROSSREF = {"enabled": True, "endpoint": "https://api.crossref.org/works", "timeout": 15, "polite_email": ""}
ARXIV = {"enabled": True, "endpoint": "http://export.arxiv.org/api/query", "timeout": 15}
WORLD_BANK_INDICATORS = {"enabled": True, "endpoint": "https://api.worldbank.org/v2", "timeout": 45, "default_country": "all"}
DATA_ANALYSIS = {"max_code_length": 10000, "execution_timeout": 30, "plot_output_dir": "plots"}
FRED = {"api_key": "", "timeout": 30, "enabled": True}
EIA = {"api_key": "", "base_url": "https://api.eia.gov/v2", "timeout": 30, "enabled": True, "max_rows_per_request": 5000}
OPENEI = {"api_key": "", "base_url": "https://api.openei.org", "timeout": 30, "enabled": True}
REGULATORY = {
    "stale_threshold_hours": 168, "timeout_seconds": 30, "rps_workbook_dir": "data",
    "jurisdictions": ["US", "ZA", "ZW"],
    "utility_rate_locations": [{"name": "Denver", "state": "CO", "lat": 39.7392, "lon": -104.9903}],
    "zimbabwe_seed_events": [
        {"title": "Public Notice - Fuel Notice 4 October 2025", "published_date": "2025-10-06",
         "source_url": "https://www.zera.co.zw/press-releases-public-notices/",
         "summary": "PUBLIC NOTICE: NOTIFICATION OF PETROLEUM PRODUCT PRICES", "category": "Press Releases"},
        {"title": "Public Notice - Fuel Notice 4 September 2025", "published_date": "2025-09-04",
         "source_url": "https://www.zera.co.zw/press-releases-public-notices/",
         "summary": "PUBLIC NOTICE: NOTIFICATION OF PETROLEUM PRODUCT PRICES", "category": "Press Releases"},
    ],
}
ALERTS = {"enabled": True, "check_interval_seconds": 300, "max_results_per_alert": 50}
YFINANCE = {"enabled": True, "timeout": 30}
MARKET_DATA = {
    "stale_threshold_hours": 24, "chart_output_dir": "plots", "chart_dpi": 150,
    "chart_style": "seaborn-v0_8-darkgrid", "analysis_lookback_days": [30, 90, 365],
    "correlation_min_observations": 30,
}
IMAGING = {
    "enabled": True,
    "mrds_wfs_endpoint": "https://mrdata.usgs.gov/services/wfs/mrds",
    "mrds_timeout": 60, "mrds_bbox": [15, -35, 40, -15],
    "stale_threshold_hours": 168,
    "satellite_tile_url": "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2021_3857/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg",
    "viirs_tile_url": "",
    "solar_overlay_tile_url": "",
    "solar_overlay_attribution": "Global Solar Atlas PVOUT",
    "resource_point_endpoint": "https://power.larc.nasa.gov/api/temporal/climatology/point",
    "resource_timeout_seconds": 30,
    "target_commodities": ["Rare earths", "Niobium", "Tantalum", "Lithium", "Cobalt",
                           "Platinum", "Chromium", "Manganese", "Vanadium"],
}
SAPP = {
    "enabled": True, "data_dir": "data",
    "dam_files": {"rsan": "DAM_RSAN.xlsx", "rsas": "DAM_RSAS.xlsx", "zim": "DAM_ZIM.xlsx"},
}
ESKOM = {
    "enabled": True, "data_dir": "data",
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
EMBER = {"enabled": True, "api_key": "", "endpoint": "https://api.ember-energy.org/v1", "timeout": 30}
GCCA = {"enabled": True, "gpkg_path": "data/GCCA 2025 GIS/AREAS_GCCA2025.gpkg"}
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
UI_PROGRESS_ENABLED = True
UI_PROGRESS_VERBOSE = False
UI_PROGRESS_COLLAPSIBLE = True
UI_PROGRESS_PERSIST = False
UI_PROGRESS_SHOW_ETA = True
SYSTEM_PROMPT_FILE = Path(__file__).parent / "system_prompt.txt"


def load_system_prompt():
    if SYSTEM_PROMPT_FILE.exists():
        return SYSTEM_PROMPT_FILE.read_text().strip()
    return "You are a local coding assistant with tool access."
'''

if __name__ == "__main__":
    Path("config.py").write_text(CONFIG)
    print("Created config.py stub for CI")
