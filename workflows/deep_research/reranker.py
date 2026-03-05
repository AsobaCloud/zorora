"""Relevance reranking for deep research sources.

Scores each source against the query by keyword overlap. When
sentence-transformers is available, upgrades to cross-encoder scoring
for semantic relevance.
"""

import logging
import re
from typing import List

import config
from engine.models import Source

logger = logging.getLogger(__name__)

STOP_WORDS = frozenset({
    'why', 'did', 'does', 'how', 'what', 'when', 'where', 'who',
    'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and',
    'or', 'is', 'was', 'were', 'are', 'been', 'be', 'has', 'had',
    'do', 'with', 'from', 'about', 'that', 'this', 'it', 'not',
})


def _stem(word: str) -> str:
    """Lightweight stemmer — nltk PorterStemmer if available, else suffix rules."""
    try:
        from nltk.stem import PorterStemmer
        _stem._stemmer = getattr(_stem, '_stemmer', None) or PorterStemmer()
        return _stem._stemmer.stem(word)
    except ImportError:
        pass
    # Fallback: simple suffix stripping (covers ~80% of English cases)
    w = word.lower()
    if len(w) <= 3:
        return w
    if w.endswith("tion") or w.endswith("sion"):
        return w[:-3]
    if w.endswith("ment"):
        return w[:-4] if len(w) > 6 else w
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ing") and len(w) > 5:
        return w[:-3]
    if w.endswith("ed") and len(w) > 4:
        return w[:-2]
    if w.endswith("ly") and len(w) > 4:
        return w[:-2]
    if w.endswith("es") and len(w) > 4:
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _freshness_bonus(pub_date: str) -> float:
    """Small relevance bonus for recent publications."""
    from datetime import date
    year = None
    # Try ISO date format (2024-03-15)
    m = re.match(r"(\d{4})-\d{2}-\d{2}", pub_date)
    if m:
        year = int(m.group(1))
    else:
        # Try bare year (2024)
        m = re.match(r"^(\d{4})$", pub_date.strip())
        if m:
            year = int(m.group(1))
        else:
            # Try "N months/years ago" patterns
            m = re.match(r"(\d+)\s+year", pub_date, re.IGNORECASE)
            if m:
                year = date.today().year - int(m.group(1))
            else:
                m = re.match(r"(\d+)\s+month", pub_date, re.IGNORECASE)
                if m:
                    months = int(m.group(1))
                    year = date.today().year if months < 12 else date.today().year - 1
    if year is None:
        return 0.0
    age = date.today().year - year
    if age <= 2:
        return 0.05
    if age <= 5:
        return 0.02
    return 0.0


def extract_keywords(query: str) -> List[str]:
    """Extract substantive stemmed keywords from query."""
    return [_stem(w) for w in query.lower().split() if w not in STOP_WORDS and len(w) > 1]


def score_relevance(query: str, sources: List[Source],
                    extra_keywords: List[str] = None) -> List[Source]:
    """Score and sort sources by relevance to query.

    Primary: keyword overlap between query and source title + snippet.
    Upgrade: cross-encoder scoring if sentence-transformers installed.
    """
    keywords = extract_keywords(query)
    if extra_keywords:
        keywords = list(set(keywords) | {_stem(k) for k in extra_keywords})
    if not keywords:
        return sources

    use_cross_encoder = bool(
        getattr(config, "WEB_SEARCH", {}).get("relevance_cross_encoder_enabled", False)
    )
    # Keep keyword-union scoring deterministic unless semantic reranking is explicitly enabled.
    if use_cross_encoder and not extra_keywords:
        try:
            return _cross_encoder_score(query, sources)
        except ImportError:
            pass

    # Fallback: keyword overlap scoring (with stemming)
    for source in sources:
        haystack_words = {_stem(w) for w in f"{source.title} {source.content_snippet}".lower().split()}
        matches = sum(1 for kw in keywords if kw in haystack_words)
        source.relevance_score = matches / len(keywords)

        # Freshness bonus
        if source.publication_date:
            source.relevance_score += _freshness_bonus(source.publication_date)

    sources.sort(key=lambda s: s.relevance_score, reverse=True)
    return sources


def filter_relevant(sources: List[Source], min_score: float = 0.40,
                    max_sources: int = 60) -> List[Source]:
    """Filter to sources above minimum relevance, capped at max_sources.

    Sources with relevance_score == 0.0 (no keyword match at all) are
    dropped. Remaining sources are capped at max_sources, sorted by
    relevance descending.
    """
    relevant = [s for s in sources if s.relevance_score >= min_score]
    # If filtering removes everything, keep only top 5 by score (not all)
    if not relevant and sources:
        relevant = sorted(sources, key=lambda s: s.relevance_score, reverse=True)[:5]
    return relevant[:max_sources]


def _count_cross_references(source: Source, all_sources: List[Source],
                            overlap_threshold: float = 0.5) -> int:
    """Count cross-references via stemmed keyword overlap between sources.

    A source is considered a cross-reference if ≥ overlap_threshold of
    its stemmed title+snippet keywords overlap with the target source's.
    Returns at least 1 (self-reference).
    """
    src_words = {_stem(w) for w in f"{source.title} {source.content_snippet}".lower().split()}
    src_keywords = {w for w in src_words if w not in STOP_WORDS and len(w) > 1}
    if not src_keywords:
        return 1

    count = 1  # self-reference
    for other in all_sources:
        if other.source_id == source.source_id:
            continue
        other_words = {_stem(w) for w in f"{other.title} {other.content_snippet}".lower().split()}
        other_keywords = {w for w in other_words if w not in STOP_WORDS and len(w) > 1}
        if not other_keywords:
            continue
        overlap = len(src_keywords & other_keywords) / len(src_keywords)
        if overlap >= overlap_threshold:
            count += 1
    return count


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
