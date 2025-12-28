"""ResearchEngine - high-level interface for deep research."""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from engine.models import ResearchState, Source, Finding
from engine.storage import LocalStorage
from workflows.deep_research.workflow import DeepResearchWorkflow

logger = logging.getLogger(__name__)


class ResearchEngine:
    """
    High-level interface for deep research.
    
    Provides clean API for:
    - Starting research
    - Loading past research
    - Searching research history
    - Executing deep research workflow
    """

    def __init__(self, storage: Optional[LocalStorage] = None):
        """Initialize research engine with storage backend."""
        self.storage = storage or LocalStorage()

    def start_research(
        self,
        query: str,
        max_depth: int = 3,
        max_iterations: int = 5
    ) -> ResearchState:
        """
        Create a new research state for a query.
        
        Args:
            query: Research query
            max_depth: Maximum citation depth (default: 3)
            max_iterations: Maximum workflow iterations (default: 5)
            
        Returns:
            ResearchState instance
        """
        state = ResearchState(
            original_query=query,
            max_depth=max_depth,
            max_iterations=max_iterations
        )
        logger.info(f"Started research: {query[:60]}...")
        return state

    def deep_research(self, query: str, depth: int = 1) -> ResearchState:
        """
        Execute deep research workflow.
        
        Args:
            query: Research query
            depth: Research depth (1=Quick, 2=Balanced, 3=Thorough)
                   Note: MVP only supports depth=1 (citation following disabled)
            
        Returns:
            ResearchState with results
        """
        logger.info(f"Executing deep research: {query[:60]}... (depth={depth})")
        
        # Create workflow
        workflow = DeepResearchWorkflow(max_depth=depth)
        
        # Execute workflow
        state = workflow.execute(query)
        
        # Save to storage
        research_id = self.save_research(state)
        logger.info(f"✓ Research saved: {research_id}")
        
        return state

    def save_research(self, state: ResearchState) -> str:
        """
        Save research state to storage.
        
        Args:
            state: ResearchState to save
            
        Returns:
            research_id string
        """
        if not state.completed_at:
            state.completed_at = datetime.now()
        return self.storage.save_research(state)

    def load_research(self, research_id: str) -> Optional[Dict[str, Any]]:
        """
        Load research by ID.
        
        Args:
            research_id: Research ID from save_research()
            
        Returns:
            Research data dict or None if not found
        """
        return self.storage.load_research(research_id)

    def search_research(self, query: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search past research.
        
        Args:
            query: Search query (optional)
            limit: Max results (default: 10)
            
        Returns:
            List of research metadata dicts
        """
        return self.storage.search_research(query=query, limit=limit)
