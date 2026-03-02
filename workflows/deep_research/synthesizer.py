"""Synthesizer - generates final synthesis from research findings."""

import logging

import config
from engine.models import ResearchState

logger = logging.getLogger(__name__)


def format_findings_for_synthesis(state: ResearchState) -> str:
    """Format findings for synthesis prompt — full claims, capped at 30 findings."""
    lines = []
    for i, finding in enumerate(state.findings[:30], 1):
        lines.append(f"{i}. {finding.claim}")
        lines.append(f"   Sources: {len(finding.sources)} | Confidence: {finding.confidence} | Avg Credibility: {finding.average_credibility:.2f}")
    return "\n".join(lines)


def format_source_content(state: ResearchState) -> str:
    """Format top source content for synthesis, distributing the content budget.

    Sorts sources by credibility score descending, prefers content_full over
    content_snippet, and distributes the prompt_content_budget (default 15000
    chars) across top sources.
    """
    budget = config.CONTENT_FETCH.get("prompt_content_budget", 15000)
    sorted_sources = sorted(
        state.sources_checked,
        key=lambda s: s.credibility_score or 0.0,
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
    authoritative = state.get_authoritative_sources(top_n=15)
    for source in authoritative:
        lines.append(f"- {source.title[:60]} ({source.url[:50]}...)")
        lines.append(f"  Credibility: {source.credibility_score:.2f} ({source.credibility_category})")
    return "\n".join(lines)


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

    prompt = f"""You are a research analyst producing an in-depth briefing.

**Topic:** {state.original_query}

**Thematic Findings:**
{findings_text}

**Source Content:**
{source_content}

**Source Credibility Overview:**
{credibility_text}

**Instructions:**
1. Structure your analysis by theme/subtopic, using markdown headers (##)
2. For each theme: state the finding, analyze implications and downstream effects, note areas of agreement/disagreement across sources
3. Use inline citations [Source Name] — cite specific claims from the source content provided above
4. Include a "Gaps and Uncertainties" section noting what the sources don't cover
5. Confidence markers: High confidence (3+ corroborating sources), Medium (2 sources), Low (single source) — state these inline
6. If sources don't cover an important dimension of the topic, note it as a gap rather than filling with background knowledge
7. Aim for comprehensive analytical depth — this is a research briefing, not a news summary

Begin analysis:
"""

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
