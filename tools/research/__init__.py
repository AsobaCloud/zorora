"""
Research tools - modular implementation.

Provides academic search, web search, and newsroom access.
"""

from tools.research.academic_search import academic_search
from tools.research.web_search import web_search
from tools.research.newsroom import get_newsroom_headlines

__all__ = [
    "academic_search",
    "web_search",
    "get_newsroom_headlines",
]
