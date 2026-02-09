"""Shared deep research execution service for REPL and Web UI."""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Callable, Optional

from engine.models import ResearchState, Finding
from workflows.deep_research.aggregator import aggregate_sources
from workflows.deep_research.credibility import score_source_credibility
from workflows.deep_research.synthesizer import synthesize


ProgressCallback = Callable[[str, str, str], None]


def _emit(progress_callback: Optional[ProgressCallback], phase: str, message: str, status: str = "running") -> None:
    """Emit progress update if callback is provided."""
    if progress_callback:
        progress_callback(status, phase, message)


def run_deep_research(
    query: str,
    depth: int = 1,
    max_results_per_source: int = 10,
    progress_callback: Optional[ProgressCallback] = None,
) -> ResearchState:
    """Execute the shared deep-research pipeline and return populated state."""
    _emit(progress_callback, "aggregation", "Searching academic databases, web, and newsroom...")
    sources = aggregate_sources(query, max_results_per_source=max_results_per_source)

    # Deduplicate by URL, fallback to title when URL is absent.
    seen_keys = set()
    unique_sources = []
    for source in sources:
        key = source.url if source.url else source.title
        if key and key not in seen_keys:
            seen_keys.add(key)
            unique_sources.append(source)

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


def build_results_payload(state: ResearchState, query: str, research_id: Optional[str] = None, max_sources: int = 20) -> dict:
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
            }
            for s in state.sources_checked[:max_sources]
        ],
        "completed_at": state.completed_at.isoformat() if state.completed_at else None,
    }
