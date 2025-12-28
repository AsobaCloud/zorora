"""Data models for deep research engine."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
import hashlib
import math


@dataclass
class Source:
    """Individual source document"""
    source_id: str
    url: str
    title: str
    authors: List[str] = field(default_factory=list)
    publication_date: str = ""
    source_type: str = ""              # 'academic', 'web', 'newsroom'
    credibility_score: float = 0.0
    credibility_category: str = ""
    content_snippet: str = ""
    cited_by_count: int = 0
    cites: List[str] = field(default_factory=list)

    @staticmethod
    def generate_id(url: str) -> str:
        """Generate unique source ID from URL"""
        return hashlib.md5(url.encode()).hexdigest()


@dataclass
class Finding:
    """Research finding (claim extracted from sources)"""
    claim: str
    sources: List[str]                 # List of source_ids
    confidence: str                    # 'high', 'medium', 'low'
    average_credibility: float


@dataclass
class ResearchState:
    """Complete research workflow state"""
    # Input
    original_query: str
    started_at: datetime = field(default_factory=datetime.now)

    # Configuration
    max_depth: int = 3
    max_iterations: int = 5

    # Progress
    current_depth: int = 0
    current_iteration: int = 0

    # Results
    sources_checked: List[Source] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    citation_graph: Dict[str, List[str]] = field(default_factory=dict)

    # Synthesis
    synthesis: Optional[str] = None
    synthesis_model: Optional[str] = None

    # Metadata
    completed_at: Optional[datetime] = None
    total_sources: int = 0

    def add_source(self, source: Source):
        """Add source and update citation graph"""
        self.sources_checked.append(source)
        self.total_sources += 1
        if source.cites:
            self.citation_graph[source.source_id] = source.cites

    def get_authoritative_sources(self, top_n: int = 10) -> List[Source]:
        """Get most authoritative sources (credibility + centrality)"""
        # Calculate centrality
        centrality = {}
        for source_id, cites_list in self.citation_graph.items():
            for cited_id in cites_list:
                centrality[cited_id] = centrality.get(cited_id, 0) + 1

        # Score = credibility * (1 + log(centrality))
        scored = []
        for source in self.sources_checked:
            cent = centrality.get(source.source_id, 0)
            authority = source.credibility_score * (1 + math.log(1 + cent))
            scored.append((authority, source))

        scored.sort(reverse=True, key=lambda x: x[0])
        return [s for _, s in scored[:top_n]]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for storage"""
        return {
            "original_query": self.original_query,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "config": {
                "max_depth": self.max_depth,
                "max_iterations": self.max_iterations
            },
            "progress": {
                "current_depth": self.current_depth,
                "current_iteration": self.current_iteration
            },
            "sources": [
                {
                    "source_id": s.source_id,
                    "url": s.url,
                    "title": s.title,
                    "authors": s.authors,
                    "publication_date": s.publication_date,
                    "source_type": s.source_type,
                    "credibility_score": s.credibility_score,
                    "credibility_category": s.credibility_category,
                    "cited_by_count": s.cited_by_count,
                    "cites": s.cites
                }
                for s in self.sources_checked
            ],
            "findings": [
                {
                    "claim": f.claim,
                    "sources": f.sources,
                    "confidence": f.confidence,
                    "average_credibility": f.average_credibility
                }
                for f in self.findings
            ],
            "citation_graph": self.citation_graph,
            "synthesis": self.synthesis,
            "synthesis_model": self.synthesis_model,
            "total_sources": self.total_sources
        }
