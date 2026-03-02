"""Shared deep research execution service for REPL and Web UI."""

from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime
from typing import Callable, List, Optional

import config
from engine.models import ResearchState, Source, Finding
from workflows.deep_research.aggregator import aggregate_sources
from workflows.deep_research.credibility import score_source_credibility
from workflows.deep_research.synthesizer import synthesize


logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str, str], None]


def _emit(progress_callback: Optional[ProgressCallback], phase: str, message: str, status: str = "running") -> None:
    """Emit progress update if callback is provided."""
    if progress_callback:
        progress_callback(status, phase, message)


def _generate_query_variants(query: str, num_variants: int) -> List[str]:
    """
    Generate query variants for broader search coverage.

    Args:
        query: Original research query
        num_variants: Number of variants to produce (1-3)

    Returns:
        List of query strings (first is always the original)
    """
    if num_variants <= 1:
        return [query]

    variants = [query]

    # Variant 2: deterministic reformulation — strip question words, add analysis terms
    question_words = r"^(what|why|how|when|where|who|is|are|do|does|did|can|could|should|will|would)\s+"
    stripped = re.sub(question_words, "", query, flags=re.IGNORECASE).strip()
    if stripped and stripped != query:
        variant2 = f"{stripped} analysis trends overview"
    else:
        variant2 = f"{query} analysis trends overview"
    variants.append(variant2)

    if num_variants <= 2:
        return variants

    # Variant 3: try reasoning model for a creative reformulation, fall back to deterministic
    try:
        from tools.registry import TOOL_FUNCTIONS
        use_reasoning = TOOL_FUNCTIONS.get("use_reasoning_model")
        if use_reasoning:
            prompt = (
                f"Rewrite this research query as a different search query that would find complementary information. "
                f"Return ONLY the rewritten query, nothing else.\n\nQuery: {query}"
            )
            result = use_reasoning(prompt)
            if result and not result.startswith("Error:") and len(result.strip()) > 5:
                variant3 = result.strip().split("\n")[0][:200]
                variants.append(variant3)
                return variants
    except Exception as e:
        logger.debug(f"Reasoning model variant generation failed: {e}")

    # Deterministic fallback for variant 3
    variant3 = f"{stripped or query} implications challenges outlook"
    variants.append(variant3)
    return variants


def _deduplicate_sources(sources: List[Source]) -> List[Source]:
    """Deduplicate sources by URL, fallback to title when URL is absent."""
    seen_keys: set = set()
    unique: List[Source] = []
    for source in sources:
        key = source.url if source.url else source.title
        if key and key not in seen_keys:
            seen_keys.add(key)
            unique.append(source)
    return unique


def run_deep_research(
    query: str,
    depth: int = 1,
    max_results_per_source: int = 10,
    progress_callback: Optional[ProgressCallback] = None,
) -> ResearchState:
    """Execute the shared deep-research pipeline and return populated state."""
    # Look up depth profile
    profile = config.DEPTH_PROFILES.get(depth, config.DEPTH_PROFILES[1])
    effective_max_per_source = profile["max_results_per_source"]
    include_brave_news = profile["include_brave_news"]
    num_variants = profile["query_variants"]

    # Generate query variants
    variants = _generate_query_variants(query, num_variants)
    logger.info(f"Deep research depth={depth}: {len(variants)} query variant(s)")

    _emit(progress_callback, "aggregation", f"Searching with {len(variants)} query variant(s) (depth {depth})...")

    # Aggregate sources for each variant
    all_sources: List[Source] = []
    for i, variant in enumerate(variants):
        _emit(progress_callback, "aggregation", f"Query {i + 1}/{len(variants)}: {variant[:60]}...")
        sources = aggregate_sources(
            variant,
            max_results_per_source=effective_max_per_source,
            include_brave_news=include_brave_news,
        )
        all_sources.extend(sources)

    # Deduplicate combined results
    unique_sources = _deduplicate_sources(all_sources)

    _emit(progress_callback, "credibility", f"Found {len(unique_sources)} sources. Scoring credibility...")

    state = ResearchState(original_query=query, max_depth=depth, max_iterations=1)

    for i, source in enumerate(unique_sources):
        cross_ref_count = 1
        for other_source in unique_sources:
            if other_source.source_id != source.source_id:
                if source.title.lower() in other_source.title.lower() or other_source.title.lower() in source.title.lower():
                    cross_ref_count += 1

        if not source.title or source.title.strip() == "":
            source.title = source.url if source.url else f"Source {i + 1}"

        cred_result = score_source_credibility(
            url=source.url or source.title,
            citation_count=source.cited_by_count or 0,
            cross_reference_count=cross_ref_count,
            source_title=source.title,
        )

        source.credibility_score = cred_result["score"]
        source.credibility_category = cred_result["category"]
        state.add_source(source)

        if (i + 1) % 5 == 0 or (i + 1) == len(unique_sources):
            _emit(progress_callback, "credibility", f"Scored {i + 1}/{len(unique_sources)} sources...")

    # Content fetching phase (SEP-005)
    try:
        cf = config.CONTENT_FETCH
        if cf.get("enabled", False):
            _emit(progress_callback, "content_fetch", "Fetching full article text...")
            from tools.utils._content_extractor import ContentExtractor
            extractor = ContentExtractor(enabled=True)
            fetched = extractor.fetch_content_for_sources(
                state.sources_checked,
                max_sources=cf.get("max_sources", 20),
                timeout_per_url=cf.get("timeout_per_url", 10),
                skip_types=cf.get("skip_types", ["academic"]),
                max_workers=cf.get("max_workers", 8),
            )
            _emit(progress_callback, "content_fetch", f"Fetched full text for {fetched} sources.")
    except Exception as e:
        logger.warning(f"Content fetch phase failed (non-fatal): {e}")

    _emit(progress_callback, "cross_reference", "Cross-referencing findings and grouping similar claims...")

    for i, source in enumerate(state.sources_checked):
        claim = source.content_snippet or source.title
        if claim:
            finding = Finding(
                claim=claim[:500],
                sources=[source.source_id],
                confidence="medium",
                average_credibility=source.credibility_score,
            )
            state.findings.append(finding)

        if (i + 1) % 10 == 0:
            _emit(
                progress_callback,
                "cross_reference",
                f"Processed {i + 1}/{len(state.sources_checked)} sources for cross-referencing...",
            )

    _emit(progress_callback, "synthesis", "Generating synthesis from findings... This may take 15-25 seconds.")

    synthesis_done = threading.Event()
    synthesis_start_time = time.time()

    def emit_heartbeat() -> None:
        heartbeat_count = 0
        messages = [
            "Analyzing sources and generating synthesis...",
            "Processing findings and cross-referencing...",
            "Generating comprehensive answer with citations...",
            "Finalizing synthesis...",
        ]

        while not synthesis_done.wait(5):
            heartbeat_count += 1
            if heartbeat_count <= len(messages):
                _emit(progress_callback, "synthesis", messages[heartbeat_count - 1])
            else:
                elapsed = int(time.time() - synthesis_start_time)
                _emit(progress_callback, "synthesis", f"Still synthesizing... ({elapsed}s elapsed)")

    heartbeat_thread = threading.Thread(target=emit_heartbeat, daemon=True)
    heartbeat_thread.start()

    try:
        state.synthesis = synthesize(state)
        state.completed_at = datetime.now()
        state.current_iteration = 1
    finally:
        synthesis_done.set()
        heartbeat_thread.join(timeout=1)

    _emit(progress_callback, "complete", f"Research complete! Found {state.total_sources} sources.", status="completed")
    return state


def build_results_payload(state: ResearchState, query: str, research_id: Optional[str] = None, max_sources: int = 25) -> dict:
    """Build API payload for web result rendering."""
    return {
        "research_id": research_id,
        "query": query,
        "synthesis": state.synthesis,
        "total_sources": state.total_sources,
        "findings_count": len(state.findings),
        "sources": [
            {
                "source_id": s.source_id,
                "title": s.title or "Untitled Source",
                "url": s.url or "",
                "credibility_score": s.credibility_score or 0.0,
                "credibility_category": s.credibility_category or "Unknown",
                "source_type": s.source_type or "unknown",
                "publication_date": s.publication_date or "",
                "content_snippet": s.content_snippet or "",
                "content_full": s.content_full or "",
            }
            for s in state.sources_checked[:max_sources]
        ],
        "completed_at": state.completed_at.isoformat() if state.completed_at else None,
    }
