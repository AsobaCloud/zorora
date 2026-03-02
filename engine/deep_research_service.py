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
from workflows.deep_research.reranker import score_relevance, filter_relevant
from workflows.deep_research.synthesizer import synthesize


logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str, str], None]


def _emit(progress_callback: Optional[ProgressCallback], phase: str, message: str, status: str = "running") -> None:
    """Emit progress update if callback is provided."""
    if progress_callback:
        progress_callback(status, phase, message)


def _generate_query_variants(query: str, num_variants: int) -> List[str]:
    """
    Generate query variants via subtopic decomposition for broader search coverage.

    Uses the reasoning model to decompose the query into distinct subtopic
    search queries targeting different angles (e.g., economic, political,
    security, humanitarian). Falls back to deterministic keyword-based
    variants if the reasoning model is unavailable.

    Args:
        query: Original research query
        num_variants: Number of variants to produce (1-3)

    Returns:
        List of query strings (first is always the original)
    """
    if num_variants <= 1:
        return [query]

    variants = [query]

    # Try reasoning model for subtopic decomposition
    try:
        from tools.registry import TOOL_FUNCTIONS
        use_reasoning = TOOL_FUNCTIONS.get("use_reasoning_model")
        if use_reasoning:
            prompt = (
                f"Decompose this research query into {num_variants} distinct sub-topic "
                f"search queries. Each should target a different angle or dimension "
                f"(e.g., economic, political, security, humanitarian, diplomatic). "
                f"Return ONLY the queries, one per line, no numbering or explanation.\n\n"
                f"Query: {query}"
            )
            result = use_reasoning(prompt)
            if result and not result.startswith("Error:"):
                lines = [line.strip() for line in result.strip().split("\n") if line.strip()]
                # Filter out lines that look like explanations rather than queries
                lines = [ln for ln in lines if len(ln) > 5 and len(ln) < 300]
                if lines:
                    # Take up to num_variants-1 decomposed queries (original is variant[0])
                    for line in lines[:num_variants - 1]:
                        variants.append(line)
                    if len(variants) >= num_variants:
                        return variants[:num_variants]
    except Exception as e:
        logger.debug(f"Reasoning model subtopic decomposition failed: {e}")

    # Deterministic fallback — append perspective keywords
    question_words = r"^(what|why|how|when|where|who|is|are|do|does|did|can|could|should|will|would)\s+"
    stripped = re.sub(question_words, "", query, flags=re.IGNORECASE).strip()
    fallback_suffixes = [
        "economic impact analysis trends",
        "political implications challenges outlook",
        "social humanitarian effects consequences",
    ]
    while len(variants) < num_variants and (len(variants) - 1) < len(fallback_suffixes):
        idx = len(variants) - 1
        base = stripped if stripped and stripped != query else query
        variants.append(f"{base} {fallback_suffixes[idx]}")

    return variants[:num_variants]


def _cluster_findings(query: str, sources: List[Source]) -> List[Finding]:
    """
    Use the reasoning model to extract themed findings from all sources.

    Builds a text block of source summaries and asks the model to identify
    8-15 thematic findings, each citing which source numbers support it.
    Falls back to 1:1 source-to-finding mapping if the model is unavailable
    or parsing fails.

    Args:
        query: Original research query
        sources: List of scored Source objects

    Returns:
        List of Finding objects grouped by theme
    """
    # Build source summary block (cap at ~8000 chars)
    source_lines = []
    char_budget = 8000
    chars_used = 0
    for i, source in enumerate(sources, 1):
        snippet = source.content_snippet or source.title or ""
        line = f"{i}. {source.title or 'Untitled'}: {snippet[:300]}"
        if chars_used + len(line) > char_budget:
            break
        source_lines.append(line)
        chars_used += len(line)

    if not source_lines:
        return _fallback_findings(sources)

    source_text = "\n".join(source_lines)
    n = len(source_lines)

    try:
        from tools.registry import TOOL_FUNCTIONS
        use_reasoning = TOOL_FUNCTIONS.get("use_reasoning_model")
        if not use_reasoning:
            return _fallback_findings(sources)

        prompt = (
            f"Below are {n} sources about: {query}\n\n"
            f"{source_text}\n\n"
            f"Identify 8-15 distinct thematic findings. For each finding:\n"
            f"- Write a clear 1-2 sentence claim\n"
            f"- List the source numbers that support it\n"
            f"- Rate confidence: high (3+ sources), medium (2 sources), low (1 source)\n\n"
            f"Format each as:\n"
            f"FINDING: <claim>\n"
            f"SOURCES: <comma-separated numbers>\n"
            f"CONFIDENCE: <high|medium|low>\n"
        )
        result = use_reasoning(prompt)
        if not result or result.startswith("Error:"):
            return _fallback_findings(sources)

        findings = _parse_clustered_findings(result, sources)
        if findings:
            logger.info(f"Clustered {len(sources)} sources into {len(findings)} thematic findings")
            return findings

    except Exception as e:
        logger.debug(f"Finding clustering failed: {e}")

    return _fallback_findings(sources)


def _parse_clustered_findings(text: str, sources: List[Source]) -> List[Finding]:
    """Parse FINDING/SOURCES/CONFIDENCE blocks from reasoning model output."""
    findings = []
    blocks = re.split(r"(?=FINDING:)", text)

    for block in blocks:
        block = block.strip()
        if not block.startswith("FINDING:"):
            continue

        claim_match = re.search(r"FINDING:\s*(.+?)(?=\nSOURCES:|\Z)", block, re.DOTALL)
        sources_match = re.search(r"SOURCES:\s*(.+?)(?=\nCONFIDENCE:|\Z)", block, re.DOTALL)
        confidence_match = re.search(r"CONFIDENCE:\s*(high|medium|low)", block, re.IGNORECASE)

        if not claim_match:
            continue

        claim = claim_match.group(1).strip()

        # Parse source numbers and map to source_ids
        source_ids = []
        if sources_match:
            nums_text = sources_match.group(1).strip()
            for num_str in re.findall(r"\d+", nums_text):
                idx = int(num_str) - 1  # 1-indexed in prompt
                if 0 <= idx < len(sources):
                    source_ids.append(sources[idx].source_id)

        if not source_ids:
            continue

        confidence = confidence_match.group(1).lower() if confidence_match else "medium"

        # Compute average credibility from backing sources
        cred_scores = []
        for sid in source_ids:
            for s in sources:
                if s.source_id == sid:
                    cred_scores.append(s.credibility_score)
                    break
        avg_cred = sum(cred_scores) / len(cred_scores) if cred_scores else 0.0

        findings.append(Finding(
            claim=claim,
            sources=source_ids,
            confidence=confidence,
            average_credibility=avg_cred,
        ))

    return findings


def _fallback_findings(sources: List[Source]) -> List[Finding]:
    """Fallback: 1:1 source-to-finding mapping (pre-SEP-006 behavior)."""
    findings = []
    for source in sources:
        claim = source.content_snippet or source.title
        if claim:
            findings.append(Finding(
                claim=claim[:500],
                sources=[source.source_id],
                confidence="medium",
                average_credibility=source.credibility_score,
            ))
    return findings


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

    # Rerank by relevance to original query
    _emit(progress_callback, "relevance", "Scoring source relevance...")
    scored_sources = score_relevance(query, list(state.sources_checked))

    # Enforce source budget from depth profile
    max_sources = profile.get("max_sources", 25)
    relevant_sources = filter_relevant(scored_sources, min_score=0.0, max_sources=max_sources)

    _emit(progress_callback, "relevance",
          f"Filtered to {len(relevant_sources)}/{len(state.sources_checked)} relevant sources.")

    # Replace state sources with relevance-filtered set
    state.sources_checked = relevant_sources
    state.total_sources = len(relevant_sources)

    _emit(progress_callback, "cross_reference", "Clustering findings by theme across sources...")

    state.findings = _cluster_findings(query, state.sources_checked)

    _emit(
        progress_callback,
        "cross_reference",
        f"Identified {len(state.findings)} thematic findings from {len(state.sources_checked)} sources.",
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
                "relevance_score": s.relevance_score or 0.0,
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
