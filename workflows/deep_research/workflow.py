"""Deep research workflow orchestrator - simplified MVP (no citation following)."""

import logging
from datetime import datetime
from typing import Optional

from engine.models import ResearchState, Source, Finding
from workflows.deep_research.aggregator import aggregate_sources
from workflows.deep_research.credibility import score_source_credibility
from workflows.deep_research.synthesizer import synthesize

logger = logging.getLogger(__name__)


class DeepResearchWorkflow:
    """
    Simplified MVP deep research workflow.
    
    Phases:
    1. Source Aggregation (academic, web, newsroom)
    2. Credibility Scoring
    3. Cross-Referencing (simplified)
    4. Synthesis
    
    Note: Citation following skipped for MVP (as per docs/ANSWERS_FOR_REVIEW.md)
    """

    def __init__(self, max_depth: int = 1):
        """
        Initialize workflow.
        
        Args:
            max_depth: Max depth (1 for MVP, citation following disabled)
        """
        self.max_depth = max_depth

    def execute(self, query: str) -> ResearchState:
        """
        Execute deep research workflow.
        
        Args:
            query: Research query
            
        Returns:
            ResearchState with results
        """
        logger.info(f"Starting deep research: {query[:60]}...")
        
        # Initialize state
        state = ResearchState(
            original_query=query,
            max_depth=self.max_depth,
            max_iterations=1  # MVP: single iteration
        )
        
        # Phase 1: Source Aggregation
        logger.info("Phase 1: Aggregating sources...")
        sources = aggregate_sources(query, max_results_per_source=10)
        
        # Deduplicate by URL
        seen_urls = set()
        unique_sources = []
        for source in sources:
            if source.url and source.url not in seen_urls:
                seen_urls.add(source.url)
                unique_sources.append(source)
            elif not source.url and source.title not in seen_urls:
                seen_urls.add(source.title)
                unique_sources.append(source)
        
        logger.info(f"✓ Aggregated {len(unique_sources)} unique sources")
        
        # Phase 2: Credibility Scoring
        logger.info("Phase 2: Scoring credibility...")
        for source in unique_sources:
            # Calculate cross-reference count (how many sources mention similar topics)
            # Simplified: count sources with similar titles/content
            cross_ref_count = 1
            for other_source in unique_sources:
                if other_source.source_id != source.source_id:
                    # Simple similarity check (in real impl, use embeddings)
                    if source.title.lower() in other_source.title.lower() or \
                       other_source.title.lower() in source.title.lower():
                        cross_ref_count += 1
            
            cred_result = score_source_credibility(
                url=source.url or source.title,
                citation_count=source.cited_by_count,
                cross_reference_count=cross_ref_count,
                source_title=source.title
            )
            
            source.credibility_score = cred_result["score"]
            source.credibility_category = cred_result["category"]
            state.add_source(source)
        
        logger.info(f"✓ Scored {len(state.sources_checked)} sources")
        
        # Phase 3: Cross-Referencing (simplified - create findings from sources)
        logger.info("Phase 3: Cross-referencing...")
        for source in state.sources_checked:
            # Create finding from source content
            claim = source.content_snippet or source.title
            if claim:
                finding = Finding(
                    claim=claim[:500],  # Truncate long claims
                    sources=[source.source_id],
                    confidence="medium",  # Default confidence
                    average_credibility=source.credibility_score
                )
                state.findings.append(finding)
        
        logger.info(f"✓ Created {len(state.findings)} findings")
        
        # Phase 4: Synthesis
        logger.info("Phase 4: Synthesizing...")
        synthesis_text = synthesize(state)
        state.synthesis = synthesis_text
        
        # Mark as completed
        state.completed_at = datetime.now()
        state.current_iteration = 1
        
        logger.info(f"✓ Deep research complete: {state.total_sources} sources, {len(state.findings)} findings")
        
        return state
