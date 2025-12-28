"""Synthesizer - generates final synthesis from research findings."""

import logging
from typing import List

from engine.models import ResearchState, Source, Finding

logger = logging.getLogger(__name__)


def format_findings_for_synthesis(state: ResearchState) -> str:
    """Format findings for synthesis prompt"""
    lines = []
    for i, finding in enumerate(state.findings[:20], 1):
        claim = finding.claim[:200] + "..." if len(finding.claim) > 200 else finding.claim
        lines.append(f"{i}. {claim}")
        lines.append(f"   Sources: {len(finding.sources)} | Confidence: {finding.confidence} | Avg Credibility: {finding.average_credibility:.2f}")
    return "\n".join(lines)


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
    Synthesize research findings using reasoning model.
    
    Args:
        state: ResearchState with findings and sources
        
    Returns:
        Synthesis text
    """
    logger.info("Synthesizing findings...")
    
    findings_text = format_findings_for_synthesis(state)
    credibility_text = format_credibility_scores(state)
    
    prompt = f"""You are a research synthesis expert. Synthesize findings from multiple sources.

**Topic:** {state.original_query}

**Findings:**
{findings_text}

**Source Credibility:**
{credibility_text}

**Instructions:**
1. Synthesize into 2-4 paragraphs
2. Use inline citations [Source Name]
3. Note confidence levels:
   - High: 3+ sources, avg credibility >0.7
   - Medium: 2 sources, avg credibility 0.5-0.7
   - Low: 1 source, avg credibility <0.5
4. Flag contradictions
5. Be concise and factual

Begin synthesis:
"""
    
    try:
        # Import use_reasoning_model from tool registry
        from tools.registry import TOOL_FUNCTIONS
        use_reasoning_model = TOOL_FUNCTIONS.get("use_reasoning_model")
        
        if not use_reasoning_model:
            logger.warning("use_reasoning_model not available, using fallback")
            return _fallback_synthesis(state)
        
        synthesis = use_reasoning_model(prompt)
        
        if synthesis and not synthesis.startswith("Error:"):
            state.synthesis = synthesis
            state.synthesis_model = "reasoning"
            logger.info("✓ Synthesis complete")
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
