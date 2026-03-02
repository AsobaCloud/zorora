"""Relevance reranking for deep research sources.

Scores each source against the query by keyword overlap. When
sentence-transformers is available, upgrades to cross-encoder scoring
for semantic relevance.
"""

import logging
from typing import List

from engine.models import Source

logger = logging.getLogger(__name__)

STOP_WORDS = frozenset({
    'why', 'did', 'does', 'how', 'what', 'when', 'where', 'who',
    'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and',
    'or', 'is', 'was', 'were', 'are', 'been', 'be', 'has', 'had',
    'do', 'with', 'from', 'about', 'that', 'this', 'it', 'not',
})


def extract_keywords(query: str) -> List[str]:
    """Extract substantive keywords from query."""
    return [w for w in query.lower().split() if w not in STOP_WORDS and len(w) > 1]


def score_relevance(query: str, sources: List[Source]) -> List[Source]:
    """Score and sort sources by relevance to query.

    Primary: keyword overlap between query and source title + snippet.
    Upgrade: cross-encoder scoring if sentence-transformers installed.
    """
    keywords = extract_keywords(query)
    if not keywords:
        return sources

    # Try cross-encoder first (if available)
    try:
        return _cross_encoder_score(query, sources)
    except ImportError:
        pass

    # Fallback: keyword overlap scoring
    for source in sources:
        haystack = f"{source.title} {source.content_snippet}".lower()
        matches = sum(1 for kw in keywords if kw in haystack)
        source.relevance_score = matches / len(keywords)

    sources.sort(key=lambda s: s.relevance_score, reverse=True)
    return sources


def filter_relevant(sources: List[Source], min_score: float = 0.0,
                    max_sources: int = 60) -> List[Source]:
    """Filter to sources above minimum relevance, capped at max_sources.

    Sources with relevance_score == 0.0 (no keyword match at all) are
    dropped. Remaining sources are capped at max_sources, sorted by
    relevance descending.
    """
    relevant = [s for s in sources if s.relevance_score > min_score]
    # If filtering removes everything, keep top-K by relevance anyway
    if not relevant and sources:
        relevant = sorted(sources, key=lambda s: s.relevance_score, reverse=True)
    return relevant[:max_sources]


def _cross_encoder_score(query: str, sources: List[Source]) -> List[Source]:
    """Cross-encoder scoring via sentence-transformers (optional upgrade)."""
    from sentence_transformers import CrossEncoder
    model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', max_length=512)
    pairs = [(query, f"{s.title} {s.content_snippet}"[:512]) for s in sources]
    scores = model.predict(pairs)
    for source, score in zip(sources, scores):
        source.relevance_score = float(score)
    sources.sort(key=lambda s: s.relevance_score, reverse=True)
    logger.info("Using cross-encoder relevance scoring (sentence-transformers)")
    return sources
