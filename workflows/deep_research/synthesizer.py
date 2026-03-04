"""Synthesizer - two-stage synthesis pipeline (outline → per-section expansion)."""

import logging
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Tuple

import config
from engine.models import Finding, ResearchState, Source

logger = logging.getLogger(__name__)


@dataclass
class OutlineSection:
    title: str
    bullets: List[str]


@dataclass
class OutlineResult:
    executive_summary: str
    sections: List[OutlineSection]
    is_comparison: bool
    subjects: Optional[List[str]]


# ---------------------------------------------------------------------------
# Stopwords used by route_sources / route_findings keyword overlap
# ---------------------------------------------------------------------------
_ROUTE_STOPWORDS = frozenset({
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and",
    "or", "is", "was", "were", "are", "been", "be", "has", "had",
    "do", "with", "from", "about", "that", "this", "it", "not",
    "by", "as", "but", "its", "how", "what", "when", "where", "who",
    "why", "did", "does", "can", "may", "will", "should", "would",
})


_CATEGORY_SUFFIXES = re.compile(
    r"\s+(?:technologies|technology|tech|solutions|types|options|alternatives|systems|methods)$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _emit_progress(callback, phase: str, message: str):
    if callback:
        callback("running", phase, message)


def _extract_words(text: str) -> set:
    """Extract lowercase words ≥3 chars, minus stopwords."""
    return {
        w for w in re.findall(r"[a-z]{3,}", text.lower())
        if w not in _ROUTE_STOPWORDS
    }


def _resolve_generic_subject(
    generic_subject: str,
    specific_subject: str,
    state: ResearchState,
    max_alternatives: int = None,
) -> str:
    if max_alternatives is None:
        max_alternatives = config.SYNTHESIS.get("max_alternatives", 3)
    """Replace a generic subject like 'other battery tech' with specific names from sources.

    Scans source titles, content snippets, and finding claims for
    '<qualifier> <category-root>' patterns (e.g., 'sodium-ion battery'),
    filters out the known specific subject, and returns top alternatives
    by frequency. Returns the original subject unchanged if nothing found.
    """
    # Extract category from "other X" -> X
    cat_match = re.match(r"^other\s+(.+)$", generic_subject.strip(), re.IGNORECASE)
    if not cat_match:
        return generic_subject
    category = cat_match.group(1).strip()

    # Derive root noun: "battery technologies" -> "batter"
    root = _CATEGORY_SUFFIXES.sub("", category).strip()
    if root.endswith("ies"):
        root = root[:-3]      # "batteries" -> "batter"
    elif root.endswith("y"):
        root = root[:-1]      # "battery" -> "batter"
    elif root.endswith("s") and not root.endswith("ss"):
        root = root[:-1]      # "cells" -> "cell"

    if len(root) < 3:
        return generic_subject

    # Build corpus from sources and findings
    text_blocks = []
    for source in state.sources_checked:
        if source.title:
            text_blocks.append(source.title)
        if source.content_snippet:
            text_blocks.append(source.content_snippet[:300])
    for finding in state.findings:
        text_blocks.append(finding.claim)
    corpus = "\n".join(text_blocks)

    # Find "<qualifier> <root>..." patterns ([ \t]+ avoids matching across lines)
    pattern = re.compile(
        r"\b((?:[A-Za-z][\w-]*[ \t]+){0,2}[A-Za-z][\w-]*)[ \t]+" + re.escape(root) + r"\w*\b",
        re.IGNORECASE,
    )
    matches = pattern.findall(corpus)

    # Count and filter
    specific_lower = specific_subject.lower().replace("-", " ")
    skip = {"other", "new", "the", "a", "an", "some", "many", "various", "different", "these", "those", "all",
            "comparing", "compare", "versus", "between", "about", "called", "named", "using", "like", "than"}
    candidates: Counter = Counter()
    for match in matches:
        name = match.strip().lower()
        if not name or name in skip:
            continue
        first_word = name.split()[0]
        if first_word in skip:
            continue
        if name in specific_lower or specific_lower.startswith(name):
            continue
        candidates[name] += 1

    top = [name for name, _ in candidates.most_common(max_alternatives)]
    if not top:
        return generic_subject

    # Format: "Solid-State Batteries, Sodium-Ion Batteries, and Flow Batteries"
    def fmt(qualifier: str) -> str:
        full = f"{qualifier} {root}ies" if root.endswith("er") or root.endswith("r") else f"{qualifier} {root}s"
        return full.title()

    names = [fmt(t) for t in top]
    if len(names) == 1:
        return names[0]
    elif len(names) == 2:
        return f"{names[0]} and {names[1]}"
    else:
        return f"{', '.join(names[:-1])}, and {names[-1]}"


# ---------------------------------------------------------------------------
# Stage 0: Format claims (replaces format_findings_for_synthesis)
# ---------------------------------------------------------------------------

def format_claims_only(state: ResearchState) -> str:
    """Return finding claims without metadata (no source count, confidence, credibility)."""
    max_findings = config.SYNTHESIS.get("max_findings", 15)
    lines = []
    for i, finding in enumerate(state.findings[:max_findings], 1):
        lines.append(f"{i}. {finding.claim}")
    return "\n".join(lines)


def _normalize_outline_headers(raw: str) -> str:
    """Normalize any markdown header level (##–######) to ## and strip bold/italic markers from header text."""
    lines = []
    for line in raw.split("\n"):
        stripped = line.lstrip()
        match = re.match(r"^(#{2,6})\s+(.*)", stripped)
        if match:
            header_text = match.group(2).strip()
            # Strip bold/italic markers: **text** → text, *text* → text
            header_text = re.sub(r"\*{1,2}(.*?)\*{1,2}", r"\1", header_text)
            lines.append(f"## {header_text}")
        else:
            lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage 1: Outline generation
# ---------------------------------------------------------------------------

def _build_outline_prompt(search_topic: str, claims_text: str, today: str) -> str:
    """Build the standard thematic outline prompt."""
    min_sections, max_sections = config.SYNTHESIS.get("outline_sections", [4, 6])
    return f"""Today's date is {today}. You are a research analyst. Create an outline for a briefing on the topic below.

**Topic:** {search_topic}

**Key claims from research:**
{claims_text}

**Rules:**
1. Write an Executive Summary (2-3 sentences: the single most important conclusion).
2. Then list {min_sections}-{max_sections} thematic sections. For each section give a title and 2-3 bullet directions.
3. Group related claims across sources into themes. Do NOT organize by individual source.

**Output format (follow exactly — use ## for ALL headers, never ### or ####):**

## Executive Summary
[2-3 sentences]

## [Theme Title]
- [bullet direction 1]
- [bullet direction 2]

## [Theme Title]
- [bullet direction 1]
- [bullet direction 2]
- [bullet direction 3]

[Continue for {min_sections}-{max_sections} total thematic sections.]

Begin:
"""


def _build_comparison_outline_prompt(
    search_topic: str, subject_a: str, subject_b: str, claims_text: str, today: str,
) -> str:
    """Build comparison outline prompt naming both subjects."""
    min_sections, max_sections = config.SYNTHESIS.get("outline_sections", [4, 6])
    return f"""Today's date is {today}. You are a research analyst. Create an outline for a comparative briefing.

**Topic:** {search_topic}
**Comparing:** {subject_a} vs {subject_b}

**Key claims from research:**
{claims_text}

**Rules:**
1. Write an Executive Summary (2-3 sentences: key comparison conclusion).
2. Then list {min_sections}-{max_sections} comparison dimensions. For each give a title and 2-3 bullet directions.
3. Every dimension must compare BOTH {subject_a} and {subject_b}.

**Output format (follow exactly — use ## for ALL headers, never ### or ####):**

## Executive Summary
[2-3 sentences]

## [Comparison Dimension Title]
- [bullet about {subject_a}]
- [bullet about {subject_b}]

## [Comparison Dimension Title]
- [bullet direction 1]
- [bullet direction 2]

[Continue for {min_sections}-{max_sections} total comparison dimensions.]

Begin:
"""


def _parse_outline(raw: str, is_comparison: bool, subjects: Optional[List[str]]) -> Optional[OutlineResult]:
    """Parse outline markdown into OutlineResult. Returns None on failure."""
    min_sections = config.SYNTHESIS.get("outline_sections", [4, 6])[0]
    max_sections = config.SYNTHESIS.get("outline_sections", [4, 6])[1]

    executive_summary = ""
    sections: List[OutlineSection] = []
    current_title: Optional[str] = None
    current_bullets: List[str] = []
    in_exec_summary = False
    exec_lines: List[str] = []

    for line in raw.split("\n"):
        stripped = line.strip()

        # Section header
        if stripped.startswith("## "):
            # Save previous section
            if current_title is not None:
                sections.append(OutlineSection(title=current_title, bullets=current_bullets))
                current_title = None
                current_bullets = []

            header_text = stripped[3:].strip()

            if header_text.lower().startswith("executive summary"):
                in_exec_summary = True
                continue
            else:
                in_exec_summary = False
                current_title = header_text
                current_bullets = []
                continue

        # Bullet line
        if stripped.startswith("- ") or stripped.startswith("* "):
            bullet_text = stripped[2:].strip()
            if in_exec_summary:
                exec_lines.append(bullet_text)
            elif current_title is not None:
                current_bullets.append(bullet_text)
            continue

        # Plain text under executive summary
        if in_exec_summary and stripped:
            exec_lines.append(stripped)
            continue

    # Save last section
    if current_title is not None:
        sections.append(OutlineSection(title=current_title, bullets=current_bullets))

    executive_summary = " ".join(exec_lines).strip()

    # Validate
    if not executive_summary:
        logger.warning("Outline parse failed: empty executive summary")
        return None
    if len(sections) < min_sections:
        logger.warning("Outline parse failed: %d sections < min %d", len(sections), min_sections)
        return None

    # Cap at max
    sections = sections[:max_sections]

    return OutlineResult(
        executive_summary=executive_summary,
        sections=sections,
        is_comparison=is_comparison,
        subjects=subjects,
    )


def synthesize_outline(state: ResearchState) -> Optional[OutlineResult]:
    """Stage 1: Generate outline from claims via reasoning model."""
    claims_text = format_claims_only(state)
    today = date.today().isoformat()
    search_topic = state.refined_query or state.original_query

    # Detect comparison
    from engine.query_refiner import detect_comparison, _is_generic_subject
    comparison = detect_comparison(search_topic)
    is_comparison = comparison["is_comparative"] and len(comparison["subjects"]) >= 2
    subjects = None

    if is_comparison:
        subjects = list(comparison["subjects"])
        for i, subj in enumerate(subjects):
            if _is_generic_subject(subj):
                resolved = _resolve_generic_subject(subj, subjects[1 - i], state)
                if resolved != subj:
                    logger.info("Resolved generic subject '%s' -> '%s'", subj, resolved)
                    subjects[i] = resolved
        prompt = _build_comparison_outline_prompt(search_topic, subjects[0], subjects[1], claims_text, today)
    else:
        prompt = _build_outline_prompt(search_topic, claims_text, today)

    # Enforce char budget
    max_chars = config.MODEL_BUDGETS.get("synthesis_outline", {}).get("max_input_chars", 5250)
    if len(prompt) > max_chars:
        overshoot = len(prompt) - max_chars
        # Trim claims_text from the end
        claims_text = claims_text[:len(claims_text) - overshoot]
        if is_comparison:
            prompt = _build_comparison_outline_prompt(search_topic, subjects[0], subjects[1], claims_text, today)
        else:
            prompt = _build_outline_prompt(search_topic, claims_text, today)

    try:
        from tools.registry import TOOL_FUNCTIONS
        use_reasoning_model = TOOL_FUNCTIONS.get("use_reasoning_model")
        if not use_reasoning_model:
            logger.warning("use_reasoning_model not available for outline")
            return None

        raw = use_reasoning_model(prompt)
        if not raw or raw.startswith("Error:"):
            logger.warning("Outline model returned empty/error")
            return None

        raw = _normalize_outline_headers(raw)
        return _parse_outline(raw, is_comparison, subjects)

    except Exception as e:
        logger.error("Outline generation failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Routing: select per-section relevant content
# ---------------------------------------------------------------------------

def route_sources(
    section: OutlineSection,
    sources: List[Source],
    max_sources: int = None,
) -> List[Source]:
    """Select sources most relevant to this section via keyword overlap scoring."""
    if max_sources is None:
        max_sources = config.SYNTHESIS.get("max_sources_per_section", 4)

    # Build word set from section title + bullets
    section_text = section.title + " " + " ".join(section.bullets)
    section_words = _extract_words(section_text)
    if not section_words:
        # Fallback: top sources by credibility
        return sorted(sources, key=lambda s: s.credibility_score or 0.0, reverse=True)[:max_sources]

    scored: List[Tuple[float, Source]] = []
    for source in sources:
        source_text = f"{source.title or ''} {source.content_snippet or ''} {source.content_full or ''}"
        source_words = _extract_words(source_text)
        overlap = len(section_words & source_words)
        # Credibility tiebreaker
        score = overlap + (source.credibility_score or 0.0) * 0.1
        scored.append((score, source))

    scored.sort(key=lambda t: t[0], reverse=True)

    # If no keyword overlap at all, fall back to credibility
    if scored and scored[0][0] < 0.2:
        return sorted(sources, key=lambda s: s.credibility_score or 0.0, reverse=True)[:max_sources]

    return [s for _, s in scored[:max_sources]]


def route_findings(
    section: OutlineSection,
    findings: List[Finding],
    max_findings: int = None,
) -> List[Finding]:
    """Select findings most relevant to this section via keyword overlap scoring."""
    if max_findings is None:
        max_findings = config.SYNTHESIS.get("max_findings_per_section", 3)

    section_text = section.title + " " + " ".join(section.bullets)
    section_words = _extract_words(section_text)
    if not section_words:
        return findings[:max_findings]

    scored: List[Tuple[float, Finding]] = []
    for finding in findings:
        finding_words = _extract_words(finding.claim)
        overlap = len(section_words & finding_words)
        scored.append((overlap, finding))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [f for _, f in scored[:max_findings]]


# ---------------------------------------------------------------------------
# Stage 2: Per-section expansion
# ---------------------------------------------------------------------------

def _build_section_prompt(
    section: OutlineSection,
    routed_sources: List[Source],
    routed_findings: List[Finding],
    today: str,
    market_context: str = "",
) -> str:
    """Build a standard section expansion prompt."""
    max_chars = config.MODEL_BUDGETS.get("synthesis_section", {}).get("max_input_chars", 5250)

    # Format finding claims
    claims = "\n".join(f"- {f.claim}" for f in routed_findings)

    # Format source excerpts with per-source budget
    overhead = 600  # prompt template + section title + bullets + claims
    source_budget = max(200, (max_chars - overhead) // max(len(routed_sources), 1))
    source_blocks = []
    for i, src in enumerate(routed_sources, 1):
        content = src.content_full or src.content_snippet or ""
        excerpt = content[:source_budget]
        title = src.title or "Untitled"
        source_blocks.append(f"[{i}] {title}\n{excerpt}")
    sources_text = "\n\n".join(source_blocks)

    bullets_text = "\n".join(f"- {b}" for b in section.bullets)

    market_block = ""
    if market_context:
        market_block = f"\n**Market Data (for context — do not cite as a 'source'):**\n{market_context}\n"

    return f"""Today's date is {today}. Write one analytical paragraph for the section below.

**Section:** {section.title}
**Directions:**
{bullets_text}

**Relevant claims:**
{claims}

**Source excerpts:**
{sources_text}
{market_block}
**Rules:**
1. Synthesize across sources — do not summarize one source at a time.
2. Cite inline: "costs fell 40% [Source Title]". Every claim must name its source.
3. One paragraph only. No sub-headings.
4. Only cite facts from the provided sources — do not invent data.

Begin:
"""


def _build_comparison_section_prompt(
    section: OutlineSection,
    routed_sources: List[Source],
    routed_findings: List[Finding],
    subjects: List[str],
    today: str,
    market_context: str = "",
) -> str:
    """Build a comparison section expansion prompt."""
    max_chars = config.MODEL_BUDGETS.get("synthesis_section", {}).get("max_input_chars", 5250)

    claims = "\n".join(f"- {f.claim}" for f in routed_findings)

    overhead = 600
    source_budget = max(200, (max_chars - overhead) // max(len(routed_sources), 1))
    source_blocks = []
    for i, src in enumerate(routed_sources, 1):
        content = src.content_full or src.content_snippet or ""
        excerpt = content[:source_budget]
        title = src.title or "Untitled"
        source_blocks.append(f"[{i}] {title}\n{excerpt}")
    sources_text = "\n\n".join(source_blocks)

    bullets_text = "\n".join(f"- {b}" for b in section.bullets)

    market_block = ""
    if market_context:
        market_block = f"\n**Market Data (for context — do not cite as a 'source'):**\n{market_context}\n"

    return f"""Today's date is {today}. Write one analytical paragraph comparing {subjects[0]} and {subjects[1]} on this dimension.

**Dimension:** {section.title}
**Directions:**
{bullets_text}

**Relevant claims:**
{claims}

**Source excerpts:**
{sources_text}
{market_block}
**Rules:**
1. Compare BOTH {subjects[0]} and {subjects[1]} on this dimension.
2. Highlight similarities AND differences with specific evidence.
3. Cite inline: "costs fell 40% [Source Title]". Every claim must name its source.
4. One paragraph only. No sub-headings.
5. Only cite facts from the provided sources — do not invent data.

Begin:
"""


def synthesize_section(
    section: OutlineSection,
    sources: List[Source],
    findings: List[Finding],
    state: ResearchState,
    is_comparison: bool,
    subjects: Optional[List[str]],
    market_context: str = "",
) -> Optional[str]:
    """Stage 2: Expand a single section via reasoning model."""
    today = date.today().isoformat()

    if is_comparison and subjects:
        prompt = _build_comparison_section_prompt(section, sources, findings, subjects, today, market_context=market_context)
    else:
        prompt = _build_section_prompt(section, sources, findings, today, market_context=market_context)

    try:
        from tools.registry import TOOL_FUNCTIONS
        use_reasoning_model = TOOL_FUNCTIONS.get("use_reasoning_model")
        if not use_reasoning_model:
            return None

        raw = use_reasoning_model(prompt)
        if not raw or raw.startswith("Error:"):
            return None

        # Strip accidental markdown headers from output
        lines = raw.strip().split("\n")
        cleaned = []
        for line in lines:
            if re.match(r"^#{1,6}\s", line.strip()):
                continue
            cleaned.append(line)
        return "\n".join(cleaned).strip() or None

    except Exception as e:
        logger.error("Section expansion failed for '%s': %s", section.title, e)
        return None


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def assemble_synthesis(outline: OutlineResult, expanded_sections: List[Optional[str]]) -> str:
    """Mechanically concatenate outline + expanded sections into final markdown."""
    parts = []

    parts.append("## Executive Summary")
    parts.append(outline.executive_summary)
    parts.append("")

    for i, section in enumerate(outline.sections):
        parts.append(f"## {section.title}")
        expanded = expanded_sections[i] if i < len(expanded_sections) else None
        if expanded:
            parts.append(expanded)
        else:
            # Stub for failed sections
            parts.append("*[Section could not be fully expanded. Key points:]*")
            for bullet in section.bullets:
                parts.append(f"- {bullet}")
        parts.append("")

    parts.append("**Gaps:** Further investigation needed on dimensions not covered by available sources.")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def synthesize(state: ResearchState, progress_callback=None) -> str:
    """
    Two-stage synthesis pipeline: outline → per-section expansion → assembly.

    Args:
        state: ResearchState with findings and sources
        progress_callback: Optional callback(status, phase, message)

    Returns:
        Synthesis text
    """
    logger.info("Synthesizing findings (two-stage pipeline)...")

    # Build market context if query involves financial topics
    market_context = ""
    try:
        from engine.query_refiner import detect_market_intent
        if detect_market_intent(state.original_query):
            logger.info("Market intent detected — injecting FRED context")
            from workflows.market_workflow import MarketWorkflow
            from tools.market.context import build_market_context
            wf = MarketWorkflow()
            wf.update_all()
            summaries = wf.compute_summary()
            if summaries:
                market_context = build_market_context(summaries)
    except Exception as exc:
        logger.warning("Market context build failed (non-fatal): %s", exc)

    # Stage 1: Outline
    _emit_progress(progress_callback, "synthesis", "Generating outline from findings...")
    outline = synthesize_outline(state)
    if outline is None:
        logger.warning("Outline generation failed, using fallback synthesis")
        return _fallback_synthesis(state)

    _emit_progress(
        progress_callback, "synthesis",
        f"Outline ready: {len(outline.sections)} sections. Expanding...",
    )

    # Stage 2: Per-section expansion
    expanded_sections: List[Optional[str]] = []
    success_count = 0

    for i, section in enumerate(outline.sections):
        _emit_progress(
            progress_callback, "synthesis",
            f"Expanding section {i + 1}/{len(outline.sections)}: {section.title}",
        )

        routed_src = route_sources(section, state.sources_checked)
        routed_fnd = route_findings(section, state.findings)

        paragraph = synthesize_section(
            section, routed_src, routed_fnd, state,
            outline.is_comparison, outline.subjects,
            market_context=market_context,
        )
        expanded_sections.append(paragraph)
        if paragraph:
            success_count += 1

    if success_count == 0:
        logger.warning("All section expansions failed, using fallback synthesis")
        return _fallback_synthesis(state)

    # Stage 3: Assembly
    _emit_progress(progress_callback, "synthesis", "Assembling final synthesis...")
    synthesis = assemble_synthesis(outline, expanded_sections)

    state.synthesis = synthesis
    state.synthesis_model = "reasoning"
    logger.info("Synthesis complete (%d/%d sections expanded)", success_count, len(outline.sections))
    return synthesis


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
