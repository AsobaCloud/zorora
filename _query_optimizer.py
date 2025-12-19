"""Query optimization and intent detection for web search."""

import re
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """Optimize search queries for better results."""
    
    def __init__(self, enabled: bool = True):
        """
        Initialize query optimizer.
        
        Args:
            enabled: Whether optimization is enabled
        """
        self.enabled = enabled
        
        # Intent patterns
        self._news_patterns = [
            r'\b(latest|recent|today|yesterday|this week|breaking|news|update)\b.*\b(news|article|headline|story|report)\b',
            r'\b(what\'?s happening|what happened|announcement|announced)\b',
            r'\b(news|headlines|articles)\b.*\b(about|on|regarding)\b',
            r'\b(current|latest)\b.*\b(news|headlines|articles|updates)\b',
        ]
        
        self._technical_patterns = [
            r'\b(how to|tutorial|guide|documentation|docs|api|reference|example|code)\b',
            r'\b(github|stackoverflow|stack overflow|reddit|forum)\b',
            r'\b(error|bug|issue|problem|solution|fix)\b'
        ]
        
        self._definition_patterns = [
            r'\b(what is|what are|define|definition|explain|meaning of)\b'
        ]
    
    def optimize(self, query: str) -> Tuple[str, Dict[str, any]]:
        """
        Optimize a search query.
        
        Args:
            query: Original search query
            
        Returns:
            Tuple of (optimized_query, metadata_dict)
        """
        if not self.enabled:
            return query, {"intent": "general", "optimized": False}
        
        # Normalize query
        optimized = self._normalize(query)
        
        # Detect intent
        intent = self._detect_intent(optimized)
        
        # Apply intent-based optimization
        if intent == "technical":
            optimized = self._optimize_technical(optimized)
        elif intent == "news":
            optimized = self._optimize_news(optimized)
        elif intent == "definition":
            optimized = self._optimize_definition(optimized)
        
        metadata = {
            "intent": intent,
            "optimized": optimized != query,
            "original": query
        }
        
        if optimized != query:
            logger.debug(f"Query optimized: '{query}' -> '{optimized}' (intent: {intent})")
        
        return optimized, metadata
    
    def _normalize(self, query: str) -> str:
        """Normalize query: trim, remove extra spaces, fix common issues, remove meta-language."""
        # Trim whitespace
        query = query.strip()
        
        # Remove meta-language patterns that users might include
        meta_patterns = [
            r'^(let\'?s\s+)?(do\s+a\s+)?(web\s+)?search\s+(for|to|about|on)\s+',
            r'^(can\s+you\s+)?(please\s+)?(search\s+for|look\s+up|find\s+information\s+about)\s+',
            r'^(i\s+want\s+to\s+)?(search|find|look\s+up)\s+(for|about|on)\s+',
            r'^(help\s+me\s+)?(understand|learn|find\s+out)\s+(about|more\s+about)\s+',
            r'\s+(and\s+what\s+it\s+means|what\s+does\s+this\s+mean|what\s+is\s+the\s+context).*$',
            r'\s+(in\s+the\s+context\s+of|regarding|concerning).*$',
        ]
        
        for pattern in meta_patterns:
            query = re.sub(pattern, '', query, flags=re.IGNORECASE)
        
        # Remove extra spaces
        query = re.sub(r'\s+', ' ', query)
        
        # Remove leading/trailing punctuation that might confuse search engines
        query = re.sub(r'^[?!.,;:]+|[?!.,;:]+$', '', query)
        
        # Trim again after removals
        query = query.strip()
        
        return query
    
    def _detect_intent(self, query: str) -> str:
        """Detect query intent: news, technical, definition, or general."""
        query_lower = query.lower()
        
        # Check for news intent
        for pattern in self._news_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return "news"
        
        # Check for technical intent
        for pattern in self._technical_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return "technical"
        
        # Check for definition intent
        for pattern in self._definition_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return "definition"
        
        return "general"
    
    def _optimize_technical(self, query: str) -> str:
        """Optimize technical queries."""
        # For technical queries, we might want to add site: filters
        # But this can be too aggressive, so we'll keep it simple for now
        # Just ensure technical keywords are preserved
        
        # Remove redundant "how to" if query already has action words
        query = re.sub(r'\bhow to\s+', '', query, flags=re.IGNORECASE)
        
        return query.strip()
    
    def _optimize_news(self, query: str) -> str:
        """Optimize news queries."""
        # Remove redundant "latest" if query already has time indicators
        if re.search(r'\b(today|yesterday|this week|current)\b', query, re.IGNORECASE):
            query = re.sub(r'\blatest\s+', '', query, flags=re.IGNORECASE)
        
        return query.strip()
    
    def _optimize_definition(self, query: str) -> str:
        """Optimize definition queries."""
        # Remove redundant "what is" if query is clear
        # Keep it simple - definitions usually work well as-is
        return query.strip()
