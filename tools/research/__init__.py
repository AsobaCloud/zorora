"""
Research tools - modular implementation.

Provides academic search, web search, newsroom access, and specialized
search surfaces (World Bank, policy, SEC EDGAR).
"""

from tools.research.academic_search import academic_search
from tools.research.web_search import web_search
from tools.research.newsroom import get_newsroom_headlines
from tools.research.worldbank_search import worldbank_search_sources
from tools.research.policy_search import policy_search_sources
from tools.research.sec_search import sec_search_sources

__all__ = [
    "academic_search",
    "web_search",
    "get_newsroom_headlines",
    "worldbank_search_sources",
    "policy_search_sources",
    "sec_search_sources",
]
