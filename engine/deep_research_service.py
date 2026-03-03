"""Shared deep research execution service for REPL and Web UI."""

from __future__ import annotations

import logging
import re
import threading
import time
from datetime import date, datetime
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


_PROSE_PREFIXES = re.compile(
    r"^(this query|this is|this provides|this examines|this looks|"
    r"these |it's important|it could|it may|it might|"
    r"note:|here are|the above|the following|the goal|the aim|"
    r"i would|let me|below|in summary|to summarize|however|"
    r"for example|for instance)",
    re.IGNORECASE,
)
_MD_STRIP = re.compile(
    r"^\*\*|^\#{1,4}\s*|^__|"      # leading ** ## __
    r"\*\*\s*$|__\s*$|"            # trailing ** __
    r"^\d+\.\s+|"                  # numbered list "1. "
    r"^[-*+]\s+"                   # bullet list "- "
)


def _clean_query_line(line: str) -> Optional[str]:
    """Strip markdown formatting and reject prose/degenerate lines."""
    cleaned = line.strip()
    if not cleaned:
        return None
    prev = None
    while prev != cleaned:
        prev = cleaned
        cleaned = _MD_STRIP.sub("", cleaned).strip()
    cleaned = cleaned.rstrip(":")
    if len(cleaned) < 10 or len(cleaned) > 150:
        return None
    if _PROSE_PREFIXES.match(cleaned):
        return None
    if " " not in cleaned:
        return None
    if len(cleaned.split()) < 4:
        return None
    return cleaned


_CATEGORY_SUFFIXES_RE = re.compile(
    r"\s+(?:technologies|technology|tech|solutions|types|options|alternatives|systems|methods)$",
    re.IGNORECASE,
)

_SKIP_QUALIFIERS = frozenset({
    "other", "new", "the", "a", "an", "some", "many", "various",
    "different", "these", "those", "all", "comparing", "compare",
    "versus", "between", "about", "called", "named", "using", "like", "than",
})


def _extract_specific_alternatives(
    sources: List[Source],
    generic_subject: str,
    specific_subject: str,
    max_alternatives: int = 3,
) -> List[str]:
    """Extract specific alternative names from preliminary search results.

    Scans source titles and content snippets for '<qualifier> <category-root>'
    patterns, filters out the known specific subject, and returns top
    alternatives by frequency as complete search terms.

    Returns empty list if extraction fails (caller should fall back).
    """
    from collections import Counter

    cat_match = re.match(r"^other\s+(.+)$", generic_subject.strip(), re.IGNORECASE)
    if not cat_match:
        return []
    category = cat_match.group(1).strip()

    root = _CATEGORY_SUFFIXES_RE.sub("", category).strip()
    if root.endswith("ies"):
        root = root[:-3]
    elif root.endswith("y"):
        root = root[:-1]
    elif root.endswith("s") and not root.endswith("ss"):
        root = root[:-1]
    if len(root) < 3:
        return []

    text_blocks = []
    for source in sources:
        if source.title:
            text_blocks.append(source.title)
        if source.content_snippet:
            text_blocks.append(source.content_snippet[:300])
    corpus = "\n".join(text_blocks)
    if not corpus.strip():
        return []

    pattern = re.compile(
        r"\b((?:[A-Za-z][\w-]*[ \t]+){0,2}[A-Za-z][\w-]*)[ \t]+"
        + re.escape(root) + r"\w*\b",
        re.IGNORECASE,
    )
    matches = pattern.findall(corpus)

    specific_lower = specific_subject.lower().replace("-", " ")
    candidates: Counter = Counter()
    for match in matches:
        name = match.strip().lower()
        if not name or name in _SKIP_QUALIFIERS:
            continue
        if name.split()[0] in _SKIP_QUALIFIERS:
            continue
        if name in specific_lower or specific_lower.startswith(name):
            continue
        candidates[name] += 1

    top = [name for name, _ in candidates.most_common(max_alternatives)]
    if not top:
        return []

    def to_search_term(qualifier: str) -> str:
        if root.endswith("r"):
            return f"{qualifier} {root}ies"
        return f"{qualifier} {root}s"

    return [to_search_term(q) for q in top]


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
    # Comparative queries: generate subject-specific variants for balanced coverage
    from engine.query_refiner import detect_comparison
    comparison = detect_comparison(query)
    if comparison["is_comparative"] and len(comparison["subjects"]) >= 2:
        from engine.query_refiner import _is_generic_subject

        subjects = comparison["subjects"]
        generic_indices = [i for i, s in enumerate(subjects) if _is_generic_subject(s)]

        if generic_indices and len(generic_indices) < len(subjects):
            # One specific + one generic subject
            specific = subjects[1 - generic_indices[0]]
            generic = subjects[generic_indices[0]]

            # Quick preliminary search to discover specific alternatives
            logger.info("Resolving generic subject '%s' via preliminary search", generic)
            preliminary_sources = aggregate_sources(
                f"{specific} alternatives",
                max_results_per_source=3,
                include_brave_news=False,
            )
            alternatives = _extract_specific_alternatives(
                preliminary_sources, generic, specific, max_alternatives=3,
            )

            if alternatives:
                variants = [specific] + alternatives
                logger.info("Resolved generic '%s' to search terms: %s", generic, alternatives)
            else:
                # Fallback: current behavior
                logger.info("No alternatives extracted, falling back to generic search")
                variants = [specific, f"{specific} alternatives comparison"]

            return variants[:max(num_variants, 3)]
        else:
            # Both subjects specific — use them as variants directly
            variants = list(subjects)
            if num_variants >= 3:
                variants.append(query)
            return variants[:max(num_variants, 2)]

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
                raw_lines = result.strip().split("\n")
                lines = []
                for raw in raw_lines:
                    cleaned = _clean_query_line(raw)
                    if cleaned:
                        lines.append(cleaned)
                logger.info(f"Query variants: {len(raw_lines)} raw lines -> {len(lines)} cleaned")
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
    # Build source summary block (cap at clustering char budget from config)
    source_lines = []
    char_budget = config.SYNTHESIS.get("clustering_char_budget", 8000)
    snippet_chars = config.SYNTHESIS.get("clustering_snippet_chars", 300)
    chars_used = 0
    for i, source in enumerate(sources, 1):
        snippet = source.content_full or source.content_snippet or source.title or ""
        line = f"{i}. {source.title or 'Untitled'}: {snippet[:snippet_chars]}"
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

        today = date.today().isoformat()
        prompt = (
            f"Today's date is {today}.\n\n"
            f"Below are {n} sources about: {query}\n\n"
            f"{source_text}\n\n"
            f"Identify 8-15 distinct thematic findings. For each finding:\n"
            f"- Write a clear 1-2 sentence claim\n"
            f"- List ONLY the 1-5 source numbers that DIRECTLY support the specific claim\n"
            f"- Rate confidence: high (3+ sources), medium (2 sources), low (1 source)\n\n"
            f"IMPORTANT: Cite only the sources that contain evidence for each specific "
            f"claim. Do NOT list all sources — most findings should cite 2-4 sources. "
            f"A finding citing more than 5 sources is almost certainly wrong.\n\n"
            f"Output ONLY in the exact format shown below. Do not write preamble, explanations, or summary paragraphs.\n\n"
            f"Format each as:\n"
            f"FINDING: <claim>\n"
            f"SOURCES: <comma-separated numbers>\n"
            f"CONFIDENCE: <high|medium|low>\n\n"
            f"Example 1:\n"
            f"FINDING: Renewable energy investment surged 30% in 2025, driven by policy incentives and falling costs.\n"
            f"SOURCES: 1, 4, 7\n"
            f"CONFIDENCE: high\n\n"
            f"Example 2:\n"
            f"FINDING: Water scarcity in the region may worsen due to upstream dam construction.\n"
            f"SOURCES: 9\n"
            f"CONFIDENCE: low\n\n"
            f"IMPORTANT: Only extract claims directly stated in the sources above. "
            f"Do NOT invent events, dates, or statistics not found in the provided text. "
            f"Do not reference events after today's date as established fact.\n\n"
            f"Now analyze the sources above:\n"
        )
        result = use_reasoning(prompt)
        logger.debug(f"Clustering raw output (first 500 chars): {(result or '')[:500]}")
        if not result or result.startswith("Error:"):
            logger.warning(f"Clustering model returned empty/error — falling back to 1:1 mapping for {len(sources)} sources")
            return _fallback_findings(sources)

        findings = _parse_clustered_findings(result, sources)
        if findings:
            logger.info(f"Clustered {len(sources)} sources into {len(findings)} thematic findings")
            return findings

    except Exception as e:
        logger.warning(f"Finding clustering failed, falling back to 1:1 mapping: {e}")

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

        max_allowed = max(5, len(sources) // 2)
        if len(source_ids) > max_allowed:
            logger.warning(
                f"Skipping degenerate finding citing {len(source_ids)}/{len(sources)} "
                f"sources (max {max_allowed}): {claim[:80]}..."
            )
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

    max_findings = config.SYNTHESIS.get("max_findings", 15)
    if len(findings) > max_findings:
        logger.info(f"Capping {len(findings)} parsed findings to {max_findings}")
        findings = findings[:max_findings]
    return findings


def _fallback_findings(sources: List[Source]) -> List[Finding]:
    """Fallback: 1:1 source-to-finding mapping (pre-SEP-006 behavior)."""
    findings = []
    for source in sources:
        claim = source.content_full or source.content_snippet or source.title
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
    refined_query: Optional[str] = None,
) -> ResearchState:
    """Execute the shared deep-research pipeline and return populated state."""
    # Use refined query for search/analysis when available
    search_query = refined_query or query

    # Look up depth profile
    profile = config.DEPTH_PROFILES.get(depth, config.DEPTH_PROFILES[1])
    effective_max_per_source = profile["max_results_per_source"]
    include_brave_news = profile["include_brave_news"]
    num_variants = profile["query_variants"]

    # Generate query variants
    variants = _generate_query_variants(search_query, num_variants)
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

    state = ResearchState(original_query=query, refined_query=refined_query, max_depth=depth, max_iterations=1)

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
    scored_sources = score_relevance(search_query, list(state.sources_checked))

    # Enforce source budget from depth profile
    max_sources = profile.get("max_sources", 25)
    relevance_min = config.SYNTHESIS.get("relevance_min_score", 0.15)
    relevant_sources = filter_relevant(scored_sources, min_score=relevance_min, max_sources=max_sources)

    _emit(progress_callback, "relevance",
          f"Filtered to {len(relevant_sources)}/{len(state.sources_checked)} relevant sources.")

    # Replace state sources with relevance-filtered set
    state.sources_checked = relevant_sources
    state.total_sources = len(relevant_sources)

    _emit(progress_callback, "cross_reference", "Clustering findings by theme across sources...")

    # Cap clustering input — 7B model produces structured output reliably
    # with ≤25 sources (each gets ~320 chars in 8000-char budget)
    clustering_max = config.SYNTHESIS.get("clustering_max_sources", 25)
    clustering_sources = state.sources_checked[:clustering_max]
    state.findings = _cluster_findings(search_query, clustering_sources)

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
        state.synthesis = synthesize(state, progress_callback=progress_callback)
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
        "refined_query": state.refined_query,
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
