"""Synthesizer - generates final synthesis from research findings."""

import logging
from datetime import date

from engine.models import ResearchState

logger = logging.getLogger(__name__)

# Synthesis-specific content budget — smaller than the fetching budget (15K)
# to keep the full prompt within the 7B model's ~8K context window.
_SYNTHESIS_CONTENT_BUDGET = 5000


def format_findings_for_synthesis(state: ResearchState) -> str:
    """Format findings for synthesis prompt — full claims, capped at 15 findings."""
    lines = []
    for i, finding in enumerate(state.findings[:15], 1):
        lines.append(f"{i}. {finding.claim}")
        lines.append(f"   Sources: {len(finding.sources)} | Confidence: {finding.confidence} | Avg Credibility: {finding.average_credibility:.2f}")
    return "\n".join(lines)


def format_source_content(state: ResearchState, max_sources: int = 20) -> str:
    """Format top source content for synthesis, distributing the content budget.

    Sorts sources by credibility score descending, prefers content_full over
    content_snippet, and distributes the synthesis content budget across top
    sources (capped to max_sources to limit prompt size for small models).
    """
    budget = _SYNTHESIS_CONTENT_BUDGET
    sorted_sources = sorted(
        state.sources_checked[:max_sources],
        key=lambda s: (s.relevance_score or 0.0, s.credibility_score or 0.0),
        reverse=True,
    )

    lines = []
    chars_used = 0
    for i, source in enumerate(sorted_sources, 1):
        content = source.content_full or source.content_snippet or ""
        if not content:
            continue

        # Distribute budget: allow each source a share, but cap individual excerpts
        remaining = budget - chars_used
        if remaining <= 0:
            break
        max_per_source = max(remaining // 3, 500)  # at least 500 chars per source
        excerpt = content[:max_per_source]

        title = source.title or "Untitled"
        url = source.url or ""
        header = f"{i}. [{title}]({url}) — Credibility: {source.credibility_score:.2f}"
        entry = f"{header}\n{excerpt}"

        lines.append(entry)
        chars_used += len(entry)
        if chars_used >= budget:
            break

    return "\n\n".join(lines)


def format_credibility_scores(state: ResearchState) -> str:
    """Format credibility scores for synthesis prompt"""
    lines = []
    authoritative = state.get_authoritative_sources(top_n=10)
    for source in authoritative:
        lines.append(f"- {source.title[:60]} ({source.url[:50]}...)")
        lines.append(f"  Credibility: {source.credibility_score:.2f} ({source.credibility_category})")
    return "\n".join(lines)


def _build_standard_prompt(
    search_topic: str,
    findings_text: str,
    source_content: str,
    credibility_text: str,
    today: str,
) -> str:
    """Build the standard thematic synthesis prompt for non-comparative queries."""
    return f"""Today's date is {today}. You are a research analyst. Write an 800-1200 word briefing on the topic below.

**Topic:** {search_topic}

**Research Findings:**
{findings_text}

**Source Content:**
{source_content}

**Source Credibility:**
{credibility_text}

**Rules (follow exactly):**
1. NEVER organize by source. Group related findings across sources into 4-6 thematic sections.
2. Every sentence must add new information. No filler, no repetition, no boilerplate sub-headings.
3. Cite inline: "costs fell 40% [Bloomberg]". Every claim must name its source. Only cite facts from the provided sources — do not invent data.
4. Note confidence inline: (High — 3+ sources), (Medium — 2 sources), (Low — 1 source).
5. End with one sentence on what the sources do not cover.

**Output format (follow this skeleton exactly):**

## Executive Summary
[2-3 sentences: the single most important conclusion, supported by the strongest evidence.]

## [Theme 1 Title]
[One analytical paragraph synthesizing findings from multiple sources. Cite each claim inline.]

## [Theme 2 Title]
[One analytical paragraph synthesizing findings from multiple sources. Cite each claim inline.]

[Continue for 4-6 total thematic sections. Do NOT add subsections within themes.]

**Gaps:** [One sentence on uncovered dimensions.]

Begin:
"""


def _build_comparison_prompt(
    search_topic: str,
    subject_a: str,
    subject_b: str,
    findings_text: str,
    source_content: str,
    credibility_text: str,
    today: str,
) -> str:
    """Build a comparison synthesis prompt for comparative queries."""
    return f"""Today's date is {today}. You are a research analyst. Write an 800-1200 word comparative briefing on the topic below.

**Topic:** {search_topic}
**Comparing:** {subject_a} vs {subject_b}

**Research Findings:**
{findings_text}

**Source Content:**
{source_content}

**Source Credibility:**
{credibility_text}

**Rules (follow exactly):**
1. Structure as a COMPARISON between {subject_a} and {subject_b}. Every section must discuss BOTH subjects.
2. Highlight similarities AND differences with specific evidence from the sources.
3. Cite inline: "costs fell 40% [Bloomberg]". Every claim must name its source. Only cite facts from the provided sources — do not invent data.
4. Note confidence inline: (High — 3+ sources), (Medium — 2 sources), (Low — 1 source).
5. End with one sentence on what the sources do not cover.

**Output format (follow this skeleton exactly):**

## Executive Summary
[2-3 sentences: key comparison conclusion — which is stronger in what dimensions, supported by the strongest evidence.]

## [Comparison Dimension 1, e.g., "Performance & Efficiency"]
[One analytical paragraph comparing {subject_a} and {subject_b} on this dimension. Cite each claim inline.]

## [Comparison Dimension 2, e.g., "Cost & Accessibility"]
[One analytical paragraph comparing {subject_a} and {subject_b} on this dimension. Cite each claim inline.]

[Continue for 4-6 total comparison dimensions. Do NOT add subsections within dimensions.]

**Gaps:** [One sentence on uncovered dimensions.]

Begin:
"""


def synthesize(state: ResearchState) -> str:
    """
    Synthesize research findings using reasoning model with analytical depth.

    Args:
        state: ResearchState with findings and sources

    Returns:
        Synthesis text
    """
    logger.info("Synthesizing findings...")

    findings_text = format_findings_for_synthesis(state)
    source_content = format_source_content(state)
    credibility_text = format_credibility_scores(state)

    today = date.today().isoformat()
    search_topic = state.refined_query or state.original_query

    # Select prompt based on whether query is comparative
    from engine.query_refiner import detect_comparison
    comparison = detect_comparison(search_topic)
    if comparison["is_comparative"] and len(comparison["subjects"]) >= 2:
        subjects = comparison["subjects"]
        logger.info("Using comparison synthesis template for: %s vs %s", subjects[0], subjects[1])
        prompt = _build_comparison_prompt(
            search_topic, subjects[0], subjects[1],
            findings_text, source_content, credibility_text, today,
        )
    else:
        prompt = _build_standard_prompt(
            search_topic, findings_text, source_content, credibility_text, today,
        )

    try:
        from tools.registry import TOOL_FUNCTIONS
        use_reasoning_model = TOOL_FUNCTIONS.get("use_reasoning_model")

        if not use_reasoning_model:
            logger.warning("use_reasoning_model not available, using fallback")
            return _fallback_synthesis(state)

        synthesis = use_reasoning_model(prompt)

        if synthesis and not synthesis.startswith("Error:"):
            state.synthesis = synthesis
            state.synthesis_model = "reasoning"
            logger.info("Synthesis complete")
            return synthesis
        else:
            logger.warning("Synthesis failed, using fallback")
            return _fallback_synthesis(state)

    except Exception as e:
        logger.error(f"Synthesis error: {e}")
        return _fallback_synthesis(state)


def _fallback_synthesis(state: ResearchState) -> str:
    """Fallback synthesis if LLM unavailable"""
    lines = [f"# Research Synthesis: {state.original_query}\n"]
    lines.append(f"\n**Total Sources:** {state.total_sources}\n")
    
    if state.findings:
        lines.append("## Key Findings:\n")
        for i, finding in enumerate(state.findings[:10], 1):
            lines.append(f"{i}. {finding.claim[:150]}...")
            lines.append(f"   Confidence: {finding.confidence} | Avg Credibility: {finding.average_credibility:.2f}\n")
    
    if state.sources_checked:
        lines.append("## Top Sources:\n")
        authoritative = state.get_authoritative_sources(top_n=10)
        for source in authoritative:
            lines.append(f"- {source.title}")
            lines.append(f"  {source.url}")
            lines.append(f"  Credibility: {source.credibility_score:.2f}\n")
    
    synthesis = "\n".join(lines)
    state.synthesis = synthesis
    state.synthesis_model = "fallback"
    return synthesis
