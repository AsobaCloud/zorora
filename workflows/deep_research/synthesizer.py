"""Synthesizer - two-stage synthesis pipeline (outline → per-section expansion)."""

import logging
import re
import time
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

_LOW_VALUE_SENTENCE_PATTERNS = [
    re.compile(r"\b(i cannot guarantee|cannot guarantee|can't guarantee)\b", re.IGNORECASE),
    re.compile(r"\bimportant to note\b", re.IGNORECASE),
    re.compile(r"\bshould be read in conjunction\b", re.IGNORECASE),
    re.compile(r"\bfurther research is needed\b", re.IGNORECASE),
    re.compile(r"\bconsult additional sources\b", re.IGNORECASE),
    re.compile(r"\bthis is a snapshot in time\b", re.IGNORECASE),
]

_LOW_QUALITY_SECTION_PATTERNS = [
    re.compile(r"\bhere are (?:my )?conclusions\b", re.IGNORECASE),
    re.compile(r"\bhere are (?:(?:some|the)\s+)?key findings(?: and insights)?\b", re.IGNORECASE),
    re.compile(r"\bkey findings and insights\b", re.IGNORECASE),
    re.compile(r"\bthe provided sources\b", re.IGNORECASE),
    re.compile(r"\bthe provided documents\b", re.IGNORECASE),
    re.compile(r"\bthe following (?:is|are)\b", re.IGNORECASE),
    re.compile(r"\bfirstly\b|\bsecondly\b|\bthirdly\b", re.IGNORECASE),
    re.compile(r"\baccording to the source\b", re.IGNORECASE),
    re.compile(r"\baccording to (?:the )?(?:report|article|document)\b", re.IGNORECASE),
    re.compile(r"^\s*this (?:section|analysis|paragraph)\s+(?:discusses|examines|provides|outlines)\b", re.IGNORECASE),
    re.compile(r"\bat a high level\b", re.IGNORECASE),
    re.compile(r"\bkey considerations for stakeholders\b", re.IGNORECASE),
    re.compile(r"\bbased on the provided evidence\b", re.IGNORECASE),
    re.compile(r"\bthe following conclusions can be drawn\b", re.IGNORECASE),
    re.compile(r"\bhere is a synthesized understanding\b", re.IGNORECASE),
    re.compile(r"^\s*the evidence (?:suggests|indicates) that\b", re.IGNORECASE),
    re.compile(r"\bthe situation is complex\b", re.IGNORECASE),
    re.compile(r"(?:^|\s)(?:first|second|third),\s", re.IGNORECASE),
]
_LOW_QUALITY_SUMMARY_PATTERNS = [
    re.compile(r"\bthe following are key insights\b", re.IGNORECASE),
    re.compile(r"\bhere are the key findings\b", re.IGNORECASE),
    re.compile(r"\bto address the question\b", re.IGNORECASE),
]
_LOW_VALUE_SOURCE_FACT_PATTERNS = [
    re.compile(r"^last updated\b", re.IGNORECASE),
    re.compile(r"^what you need to know\b", re.IGNORECASE),
    re.compile(r"^find us\b", re.IGNORECASE),
    re.compile(r"\bheadquarters\b", re.IGNORECASE),
    re.compile(r"^\s*citations?\s*:\s*\d+\b", re.IGNORECASE),
    re.compile(r"^copyright\b|^©", re.IGNORECASE),
]
_LOW_QUALITY_OUTLINE_SUMMARY_PATTERNS = [
    re.compile(r"\bthis (?:report|brief|analysis) (?:provides|presents|offers)\b", re.IGNORECASE),
    re.compile(r"\boverview of (?:key )?(?:themes|findings|considerations)\b", re.IGNORECASE),
    re.compile(r"\bthis section\b", re.IGNORECASE),
]
_GENERIC_OUTLINE_TITLE_PATTERNS = [
    re.compile(r"^thematic sections?$", re.IGNORECASE),
    re.compile(r"^key findings(?: and insights)?$", re.IGNORECASE),
    re.compile(r"^analysis$", re.IGNORECASE),
    re.compile(r"^conclusion$", re.IGNORECASE),
    re.compile(r"^conclusion\s*[:\-]?\s*$", re.IGNORECASE),
    re.compile(r"^(?:section|theme|topic|dimension)\s*\d+$", re.IGNORECASE),
    re.compile(r"^(?:section|theme|topic|dimension)\s*\d+\s*[:\-]", re.IGNORECASE),
    re.compile(r"^(?:thematic\s+)?(?:section|theme|topic|dimension)\s*\d+$", re.IGNORECASE),
    re.compile(r"^(?:thematic\s+)?(?:section|theme|topic|dimension)\s*\d+\s*[:\-]", re.IGNORECASE),
    re.compile(r"^(?:[ivxlcdm]{1,6})\.\s+.+", re.IGNORECASE),
    re.compile(r"^\d+\.\s+.+", re.IGNORECASE),
    re.compile(r"^\d+\)\s+.+", re.IGNORECASE),
]

_GENERIC_SECTION_OPENING_PATTERNS = [
    re.compile(r"^\s*(?:the\s+)?evidence\s+(?:suggests|indicates)\b", re.IGNORECASE),
    re.compile(r"^\s*this\s+(?:section|analysis|paragraph)\b", re.IGNORECASE),
    re.compile(r"^\s*based on\b", re.IGNORECASE),
]
_CAUSAL_SECTION_PATTERNS = [
    re.compile(r"\bdue to\b", re.IGNORECASE),
    re.compile(r"\bbecause\b", re.IGNORECASE),
    re.compile(r"\bdriven by\b", re.IGNORECASE),
    re.compile(r"\bled to\b", re.IGNORECASE),
    re.compile(r"\bcaused\b", re.IGNORECASE),
    re.compile(r"\bresult(?:ed|ing)\s+in\b", re.IGNORECASE),
    re.compile(r"\bpass-?through\b", re.IGNORECASE),
    re.compile(
        r"\b(?:tighten(?:ed|ing)?|constrain(?:ed|ing)?|disrupt(?:ed|ing)?|surge(?:d|ing)?|"
        r"spike(?:d|ing)?|declin(?:e|ed|ing)?|caps?|interventions?)\b.*\b"
        r"(?:push(?:ed|ing)?|raise(?:d|s|ing)?|lift(?:ed|ing)?|increase(?:d|s|ing)?|"
        r"reduce(?:d|s|ing)?|lower(?:ed|ing)?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bas\b[^.]{0,90}\b(?:tighten(?:s|ed|ing)?|widen(?:s|ed|ing)?|raise(?:s|d|ing)?|"
        r"lift(?:s|ed|ing)?|reduce(?:s|d|ing)?|lower(?:s|ed|ing)?|spike(?:s|d|ing)?)\b",
        re.IGNORECASE,
    ),
]

_RESEARCH_TYPE_LENSES = {
    "trend_analysis": "Emphasize trend direction, timing, and primary market drivers.",
    "policy_review": "Emphasize regulatory mechanism, implementation status, and market pass-through effects.",
    "comparative": "Emphasize explicit contrasts, trade-offs, and relative outcomes across subjects.",
    "impact_assessment": "Emphasize causal chain from event/policy to prices, supply-demand balance, and risk.",
}

_RESEARCH_ANALYST_SYSTEM_PROMPT = (
    "You are a senior energy and electricity market research analyst. "
    "Write concise, evidence-grounded synthesis from supplied records only. "
    "Lead with conclusions, explain causal links, note conflicts, and cite inline "
    "using the provided source titles in square brackets. "
    "Do not produce planning steps, meta commentary, or procedural narration."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _emit_progress(callback, phase: str, message: str):
    if callback:
        callback("running", phase, message)


def _call_research_synthesis_model(prompt: str) -> Optional[str]:
    """Call the reasoning endpoint with a synthesis-specific analyst persona."""
    if not prompt or not prompt.strip():
        return None

    def _is_service_unavailable(exc: Exception) -> bool:
        text = str(exc or "")
        upper = text.upper()
        return "503" in upper or "SERVICE_UNAVAILABLE" in upper

    try:
        from tools.specialist.client import create_specialist_client

        model_config = config.SPECIALIZED_MODELS["reasoning"]
        client = create_specialist_client("reasoning", model_config)

        messages = [
            {"role": "system", "content": _RESEARCH_ANALYST_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        # Cold-start-aware retries for hosted inference endpoints.
        delays = [0, 65, 8]
        for attempt, delay in enumerate(delays, start=1):
            if delay:
                time.sleep(delay)
            try:
                response = client.chat_complete(messages, tools=None)
                content = client.extract_content(response)
                if content and str(content).strip():
                    return str(content).strip()
                logger.warning("Research synthesis client returned empty content")
                break
            except Exception as exc:
                if _is_service_unavailable(exc) and attempt < len(delays):
                    logger.warning(
                        "Research synthesis endpoint unavailable (attempt %d/%d); retrying after %ss",
                        attempt,
                        len(delays),
                        delays[attempt],
                    )
                    continue
                raise
    except Exception as exc:
        logger.warning("Research synthesis client failed, trying tool fallback: %s", exc)

    # Compatibility fallback for existing tool-path tests and older runtime wiring.
    try:
        from tools.registry import TOOL_FUNCTIONS

        fallback_reasoning = TOOL_FUNCTIONS.get("use_reasoning_model")
        if fallback_reasoning:
            raw = fallback_reasoning(prompt)
            if raw and not raw.startswith("Error:"):
                return raw.strip()
    except Exception as exc:
        logger.warning("Research synthesis tool fallback failed: %s", exc)

    return None


def _normalize_word(word: str) -> str:
    """Lightweight stemmer to reduce false grounding misses on morphology."""
    w = (word or "").strip().lower()
    if len(w) < 4:
        return w
    if w.endswith("ies") and len(w) > 5:
        return w[:-3] + "y"
    if w.endswith("ing") and len(w) > 6:
        return w[:-3]
    if w.endswith("ed") and len(w) > 5:
        return w[:-2]
    if w.endswith("es") and len(w) > 5:
        return w[:-2]
    if w.endswith("s") and len(w) > 4 and not w.endswith("ss"):
        return w[:-1]
    return w


def _research_lens_text(research_type: Optional[str]) -> str:
    if not isinstance(research_type, str):
        return ""
    lens = _RESEARCH_TYPE_LENSES.get(research_type.strip().lower())
    if not lens:
        return ""
    return f"\n**Research Lens:** {lens}\n"


def _extract_words(text: str) -> set:
    """Extract lowercase words ≥3 chars, minus stopwords."""
    normalized = set()
    for w in re.findall(r"[a-z]{3,}", text.lower()):
        if w in _ROUTE_STOPWORDS:
            continue
        stem = _normalize_word(w)
        if stem and stem not in _ROUTE_STOPWORDS and len(stem) >= 3:
            normalized.add(stem)
    return normalized


def _normalize_sentence(text: str, max_chars: int = 240) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) > max_chars:
        cleaned = cleaned[: max_chars - 3].rstrip() + "..."
    return cleaned


def _build_source_lookup(sources: List[Source]) -> dict:
    lookup = {}
    for source in sources:
        title = (source.title or "").strip() or "Untitled Source"
        lookup[source.source_id] = title
    return lookup


def _format_finding_citations(finding: Finding, source_lookup: dict, max_sources: int = 3) -> str:
    labels = []
    for source_id in finding.sources[:max_sources]:
        title = source_lookup.get(source_id)
        if title and title not in labels:
            labels.append(title)
    if not labels:
        return "[Unattributed Source]"
    return "".join(f"[{label}]" for label in labels)


def _format_claims_for_prompt(
    routed_findings: List[Finding],
    source_lookup: dict,
    max_sources_per_claim: int = 2,
) -> str:
    """Format routed finding claims with inline source titles for grounding."""
    if not routed_findings:
        return "- No high-signal claim routed; rely on source excerpts below."

    lines = []
    for finding in routed_findings:
        claim = _normalize_sentence(finding.claim, max_chars=260)
        if not claim:
            continue
        citations = _format_finding_citations(
            finding,
            source_lookup=source_lookup,
            max_sources=max_sources_per_claim,
        )
        lines.append(f"- {claim} {citations}")

    return "\n".join(lines) if lines else "- No high-signal claim routed; rely on source excerpts below."


def _extract_source_fact(source: Source, max_chars: int = 220) -> str:
    """Extract one compact, evidence-like sentence from a source."""
    text = source.content_full or source.content_snippet or ""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""

    title = (source.title or "").strip()
    if title:
        title_norm = re.sub(r"\s+", " ", title)
        if text.lower().startswith(title_norm.lower()):
            text = text[len(title_norm):].strip(" .:-")
        text = text.replace(title_norm, "").strip()

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    chosen = ""

    def _is_low_value_sentence(sentence: str) -> bool:
        normalized = re.sub(r"\s+", " ", (sentence or "").strip())
        if not normalized:
            return True
        if any(pattern.search(normalized) for pattern in _LOW_VALUE_SOURCE_FACT_PATTERNS):
            return True
        return False

    # Prefer concrete statements with numbers.
    for sentence in sentences:
        normalized = re.sub(r"^(firstly|secondly|thirdly|however|in summary),?\s+", "", sentence, flags=re.IGNORECASE)
        if _is_low_value_sentence(normalized):
            continue
        if len(normalized) >= 30 and re.search(r"\d", normalized):
            chosen = normalized
            break

    # Otherwise use first substantive non-boilerplate sentence.
    if not chosen:
        for sentence in sentences:
            normalized = re.sub(r"^(firstly|secondly|thirdly|however|in summary),?\s+", "", sentence, flags=re.IGNORECASE)
            if _is_low_value_sentence(normalized):
                continue
            if len(normalized) >= 20:
                chosen = normalized
                break

    if not chosen:
        chosen = text

    chosen = re.sub(r"\[[^\]]{30,}\]", "", chosen).strip()
    if chosen.count("[") > 1:
        return ""
    if re.match(r"^[A-Z][a-z]{2,9}\s+\d{1,2},\s+\d{4}\b", chosen):
        return ""
    return _normalize_sentence(chosen, max_chars=max_chars)


def _is_summary_source_usable(source: Source) -> bool:
    title = (source.title or "").strip()
    if not title:
        return False
    if len(title) > 160:
        return False
    if title.count("[") > 1:
        return False
    lowered = title.lower()
    if "..." in title or " | " in title and len(title) > 120:
        return False
    if "download" in lowered and "pdf" in lowered:
        return False
    return True


def _summary_source_priority(source: Source) -> int:
    source_type = (source.source_type or "").lower()
    if source_type in {"web", "news", "newsroom", "policy", "world_bank", "sec_filing"}:
        return 2
    if source_type == "academic":
        return 1
    return 0


def _summary_candidate_sources(state: ResearchState) -> List[Source]:
    ranked = sorted(
        state.sources_checked,
        key=lambda s: (
            _summary_source_priority(s),
            s.relevance_score or 0.0,
            s.credibility_score or 0.0,
        ),
        reverse=True,
    )
    return [s for s in ranked if _is_summary_source_usable(s)]


def _format_evidence_records(
    routed_sources: List[Source],
    routed_findings: List[Finding],
    source_lookup: dict,
    max_records: int = 6,
) -> str:
    """Build compact evidence records for synthesis prompts."""
    lines: List[str] = []

    for finding in routed_findings:
        claim = _normalize_sentence(finding.claim, max_chars=240)
        if not claim:
            continue
        citations = _format_finding_citations(finding, source_lookup=source_lookup, max_sources=2)
        lines.append(f"- {claim} {citations}")
        if len(lines) >= max_records:
            break

    if len(lines) < max_records:
        for source in routed_sources:
            title = (source.title or "").strip() or "Untitled Source"
            fact = _extract_source_fact(source, max_chars=220)
            if not fact:
                continue
            line = f"- {fact} [{title}]"
            if line in lines:
                continue
            lines.append(line)
            if len(lines) >= max_records:
                break

    return "\n".join(lines) if lines else "- No evidence records available."


def _strip_low_value_sentences(text: str) -> str:
    """Drop boilerplate hedging/disclaimer sentences from model output."""
    chunks = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    kept = []
    for chunk in chunks:
        sentence = chunk.strip()
        if not sentence:
            continue
        if any(pattern.search(sentence) for pattern in _LOW_VALUE_SENTENCE_PATTERNS):
            continue
        kept.append(sentence)
    return " ".join(kept).strip()


def _has_inline_citation(text: str) -> bool:
    return bool(re.search(r"\[[^\]]+\]", text or ""))


def _build_citation_pool(
    routed_findings: List[Finding],
    routed_sources: List[Source],
    source_lookup: dict,
    max_citations: int = 2,
) -> List[str]:
    """Build a small citation pool from routed evidence in priority order."""
    labels: List[str] = []
    seen = set()

    for finding in routed_findings:
        for source_id in finding.sources:
            title = source_lookup.get(source_id)
            if title and title not in seen:
                seen.add(title)
                labels.append(f"[{title}]")
                if len(labels) >= max_citations:
                    return labels

    for source in routed_sources:
        title = (source.title or "").strip() or "Untitled Source"
        if title not in seen:
            seen.add(title)
            labels.append(f"[{title}]")
            if len(labels) >= max_citations:
                return labels

    return labels


def _salvage_inline_citations(
    paragraph: str,
    routed_findings: List[Finding],
    routed_sources: List[Source],
    source_lookup: dict,
) -> str:
    """Inject minimal inline citations when section text is otherwise usable."""
    text = (paragraph or "").strip()
    if not text or _has_inline_citation(text):
        return text

    citations = _build_citation_pool(
        routed_findings=routed_findings,
        routed_sources=routed_sources,
        source_lookup=source_lookup,
    )
    if not citations:
        return text

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        return f"{text} {''.join(citations)}".strip()

    for idx in range(min(len(sentences), len(citations))):
        if not _has_inline_citation(sentences[idx]):
            sentences[idx] = f"{sentences[idx]} {citations[idx]}"

    rebuilt = " ".join(sentences).strip()
    if not _has_inline_citation(rebuilt):
        rebuilt = f"{rebuilt} {''.join(citations)}".strip()
    return rebuilt


def _is_evidence_grounded(
    paragraph: str,
    routed_findings: List[Finding],
    routed_sources: List[Source],
    min_overlap_terms: int = 2,
) -> bool:
    """Check that generated text overlaps with routed evidence terms."""
    paragraph_terms = _extract_words(paragraph or "")
    if not paragraph_terms:
        return False

    evidence_terms = set()
    for finding in routed_findings:
        evidence_terms.update(_extract_words(finding.claim))

    for source in routed_sources:
        title = source.title or ""
        fact = _extract_source_fact(source, max_chars=220)
        evidence_terms.update(_extract_words(f"{title} {fact}"))

    if not evidence_terms:
        return False

    overlap = paragraph_terms & evidence_terms
    return len(overlap) >= min_overlap_terms


def _has_answer_first_opening(text: str) -> bool:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]
    if not sentences:
        return False

    first = sentences[0]
    if any(pattern.search(first) for pattern in _GENERIC_SECTION_OPENING_PATTERNS):
        return False

    words = re.findall(r"[A-Za-z0-9%$-]+", first)
    if len(words) < 8:
        return False

    topic_terms = _extract_words(
        "price prices cost costs spread spreads volatility demand supply policy regulator "
        "regulatory cap caps tariff market markets import export dispatch risk"
    )
    if len(_extract_words(first) & topic_terms) < 1:
        return False

    return True


def _has_causal_link(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in _CAUSAL_SECTION_PATTERNS)


def _passes_section_quality_gate(paragraph: str, min_words: int = 10, max_words: int = 220) -> bool:
    """Reject low-signal section text that looks like report scaffolding."""
    text = (paragraph or "").strip()
    if not text:
        return False

    # Normalize to one paragraph for stable quality checks.
    if "\n" in text:
        text = re.sub(r"\s*\n+\s*", " ", text).strip()

    words = re.findall(r"[A-Za-z0-9%$-]+", text)
    if len(words) < min_words or len(words) > max_words:
        return False

    if any(pattern.search(text) for pattern in _LOW_QUALITY_SECTION_PATTERNS):
        return False

    # Require at least one citation; reject only obvious citation spam.
    citation_count = len(re.findall(r"\[[^\]]+\]", text))
    if citation_count < 1:
        return False
    if citation_count > 8 and citation_count > max(4, len(words) // 10):
        return False

    if not _has_answer_first_opening(text):
        return False

    if not _has_causal_link(text):
        return False

    return True


def _truncate_to_words(text: str, max_words: int) -> str:
    words = re.findall(r"\S+", text or "")
    if len(words) <= max_words:
        return (text or "").strip()
    return " ".join(words[:max_words]).strip().rstrip(",;:") + "..."


def _normalize_section_output(paragraph: str, max_sentences: int = 4, max_words: int = 170) -> str:
    """Coerce model output into a compact single analytical paragraph."""
    text = re.sub(r"\s+", " ", (paragraph or "").strip())
    if not text:
        return ""

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    kept: List[str] = []
    for sentence in sentences:
        sentence = re.sub(r"^\d+\.\s*", "", sentence).strip()
        sentence = re.sub(r"^\*\*[^*]+\*\*:\s*", "", sentence).strip()
        sentence = sentence.replace("**", "")
        sentence = re.sub(r":\s*\d+\.\s*", ": ", sentence)
        if not sentence:
            continue
        if any(pattern.search(sentence) for pattern in _LOW_VALUE_SENTENCE_PATTERNS):
            continue
        kept.append(sentence)
        if len(kept) >= max_sentences:
            break

    normalized = " ".join(kept).strip() if kept else text
    normalized = re.sub(r"(?:^|\s)\d+\.\s*$", "", normalized).strip()
    return _truncate_to_words(normalized, max_words=max_words)


def _summary_needs_rewrite(summary: str, max_words: int = 110) -> bool:
    text = re.sub(r"\s+", " ", (summary or "").strip())
    if not text:
        return True
    if not _has_inline_citation(text):
        return True
    if any(pattern.search(text) for pattern in _LOW_QUALITY_SUMMARY_PATTERNS):
        return True
    if "**" in text or re.search(r"\b1\.\s", text):
        return True
    words = re.findall(r"[A-Za-z0-9%$-]+", text)
    return len(words) > max_words


def _deterministic_executive_summary(state: ResearchState, max_points: int = 2) -> str:
    """Build a concise summary from top findings/sources when model summary is poor."""
    candidate_sources = {s.source_id: s for s in _summary_candidate_sources(state)}
    points: List[str] = []

    for finding in state.findings[:8]:
        source = None
        for sid in finding.sources:
            if sid in candidate_sources:
                source = candidate_sources[sid]
                break
        if not source:
            continue
        fact = _extract_source_fact(source, max_chars=180)
        title = source.title or "Untitled Source"
        if fact:
            points.append(f"{fact} [{title}]")
        if len(points) >= max_points:
            break

    if not points:
        top_sources = _summary_candidate_sources(state)[:max_points]
        for source in top_sources:
            fact = _extract_source_fact(source, max_chars=180)
            title = source.title or "Untitled Source"
            if fact:
                points.append(f"{fact} [{title}]")

    if not points:
        return "Retrieved evidence is limited; conclusions remain preliminary."

    if len(points) == 1:
        summary = f"Evidence indicates {points[0]}"
    else:
        summary = f"Evidence indicates three linked signals: {' '.join(points[:max_points])}"
    return _truncate_to_words(summary, max_words=90)


def _infer_signal_direction(text: str) -> str:
    lowered = (text or "").lower()
    if re.search(r"\b(rise|rose|rising|increase|increased|tighten|surge|spike|up)\b", lowered):
        return "tilted upward"
    if re.search(r"\b(fall|fell|falling|decline|declined|decrease|decreased|ease|down)\b", lowered):
        return "tilted downward"
    return "shifting materially"


def _select_deterministic_excerpts(
    section: OutlineSection,
    routed_sources: List[Source],
    max_excerpts: int = 2,
) -> List[Tuple[Source, str]]:
    """Select section-relevant excerpts, prioritizing credibility then relevance."""
    section_words = _extract_words(f"{section.title} {' '.join(section.bullets)}")
    candidates: List[Tuple[Tuple[int, float, float], Source, str]] = []

    for source in routed_sources:
        excerpt = _extract_source_fact(source, max_chars=220)
        if not excerpt:
            continue
        excerpt_words = _extract_words(f"{source.title or ''} {excerpt}")
        overlap = len(section_words & excerpt_words) if section_words else 1
        if section_words and overlap == 0:
            continue
        score = (
            overlap,
            float(source.credibility_score or 0.0),
            float(source.relevance_score or 0.0),
        )
        candidates.append((score, source, excerpt))

    if not candidates:
        for source in routed_sources:
            excerpt = _extract_source_fact(source, max_chars=220)
            if not excerpt:
                continue
            score = (
                0,
                float(source.credibility_score or 0.0),
                float(source.relevance_score or 0.0),
            )
            candidates.append((score, source, excerpt))

    candidates.sort(key=lambda item: item[0], reverse=True)

    selected: List[Tuple[Source, str]] = []
    seen_titles = set()
    for _, source, excerpt in candidates:
        title = (source.title or "Untitled Source").strip()
        if title in seen_titles:
            continue
        seen_titles.add(title)
        selected.append((source, excerpt))
        if len(selected) >= max_excerpts:
            break

    return selected


def _clean_section_title(title: str) -> str:
    text = re.sub(r"\s+", " ", (title or "").strip())
    if not text:
        return "this section"
    text = re.sub(r"^(?:[ivxlcdm]{1,6}\.)\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(?:section|theme|dimension)\s*\d+\s*[:\-]\s*", "", text, flags=re.IGNORECASE)
    text = text.strip(" :-")
    if not text:
        return "this section"
    return text


def _sentence_with_citation(fact: str, source_title: str) -> str:
    cleaned = _normalize_sentence(fact or "", max_chars=190).strip().rstrip(".")
    title = (source_title or "").strip() or "Untitled Source"
    if not cleaned:
        return ""
    return f"{cleaned} [{title}]."


def _deterministic_section_paragraph(
    section: OutlineSection,
    routed_sources: List[Source],
    routed_findings: List[Finding],
    source_lookup: dict,
) -> str:
    """Build an evidence-grounded section paragraph without relying on model output."""
    excerpt_pairs = _select_deterministic_excerpts(section, routed_sources, max_excerpts=2)
    evidence_sentences: List[str] = []
    section_label = _clean_section_title(section.title)

    for source, excerpt in excerpt_pairs:
        title = source.title or "Untitled Source"
        sentence = _sentence_with_citation(excerpt, title)
        if sentence:
            evidence_sentences.append(sentence)

    if not evidence_sentences:
        for finding in routed_findings[:2]:
            claim = _normalize_sentence(finding.claim, max_chars=220)
            if claim:
                evidence_sentences.append(
                    f"{claim} {_format_finding_citations(finding, source_lookup)}."
                )

    if not evidence_sentences:
        return f"Evidence for {section_label.lower()} is limited in the retrieved corpus."

    lead = evidence_sentences[0]
    support = evidence_sentences[1] if len(evidence_sentences) > 1 else ""
    direction = _infer_signal_direction(" ".join(evidence_sentences))
    implication = (
        f"Taken together, this indicates {section_label.lower()} remained {direction} "
        "because observed disruptions passed through market and policy channels."
    )
    return " ".join(part for part in [lead, support, implication] if part)


def _deterministic_evidence_synthesis(state: ResearchState, reason: str) -> str:
    """Structured deterministic synthesis path with no raw evidence dump sections."""
    source_lookup = _build_source_lookup(state.sources_checked)
    top_sources = sorted(
        state.sources_checked,
        key=lambda s: ((s.relevance_score or 0.0), (s.credibility_score or 0.0)),
        reverse=True,
    )[:5]

    def _insufficient(message: str) -> str:
        lines = [
            "## Executive Summary",
            "Insufficient usable evidence to answer this query reliably.",
            "",
            "## Evidence Status",
            _normalize_sentence(message, max_chars=240),
            "",
            "## Confidence and Gaps",
            (
                f"Retrieved sources: {len(state.sources_checked)}; extracted findings: {len(state.findings)}. "
                "The available corpus did not provide enough grounded, on-topic evidence for a reliable answer."
            ),
        ]
        synthesis_text = "\n".join(lines)
        state.synthesis = synthesis_text
        state.synthesis_model = "deterministic"
        return synthesis_text

    if not state.findings and not state.sources_checked:
        return _insufficient(f"No usable evidence was retrieved ({reason}).")

    evidence_sentences: List[str] = []
    seen = set()

    for finding in state.findings[:8]:
        claim = _normalize_sentence(finding.claim, max_chars=210).rstrip(".")
        citations = _format_finding_citations(finding, source_lookup)
        sentence = f"{claim} {citations}." if claim and citations else ""
        if sentence and sentence not in seen:
            seen.add(sentence)
            evidence_sentences.append(sentence)
        if len(evidence_sentences) >= 3:
            break

    if len(evidence_sentences) < 3:
        for source in top_sources:
            fact = _extract_source_fact(source, max_chars=210)
            title = source.title or "Untitled Source"
            if not fact:
                continue
            sentence = f"{fact.rstrip('.')} [{title}]."
            if sentence in seen:
                continue
            seen.add(sentence)
            evidence_sentences.append(sentence)
            if len(evidence_sentences) >= 3:
                break

    if not evidence_sentences:
        return _insufficient("Retrieved records lacked extractable, query-grounded claims with usable citations.")

    direction = _infer_signal_direction(" ".join(evidence_sentences))
    executive_summary = (
        f"Available evidence indicates {direction} market pressure in the current window; "
        "the answer below is limited to retrieved, cited records."
    )
    answer_body = " ".join(evidence_sentences[:2]).strip()
    if not _has_causal_link(answer_body):
        answer_body += " This pattern suggests disruption and policy channels affected observed outcomes."

    confidence_text = (
        f"Confidence is constrained by source quality dispersion across {len(state.sources_checked)} retrieved "
        f"sources and {len(state.findings)} extracted findings; unresolved conflicts remain where records diverge."
    )

    synthesis = "\n".join([
        "## Executive Summary",
        _normalize_sentence(executive_summary, max_chars=220),
        "",
        "## Answer",
        _normalize_sentence(answer_body, max_chars=360),
        "",
        "## Confidence and Gaps",
        _normalize_sentence(confidence_text, max_chars=260),
    ])
    state.synthesis = synthesis
    state.synthesis_model = "deterministic"
    return synthesis


def _build_evidence_outline_fallback(state: ResearchState) -> Optional[OutlineResult]:
    """Build a deterministic, non-template outline so section synthesis can still run."""
    if not state.findings and not state.sources_checked:
        return None

    executive_summary = _deterministic_executive_summary(state)
    if not executive_summary:
        executive_summary = (
            "Available evidence is limited; sections below prioritize the strongest grounded signals."
        )

    if state.compare_subjects and len(state.compare_subjects) >= 2:
        subject_a, subject_b = state.compare_subjects[0], state.compare_subjects[1]
        sections = [
            OutlineSection(
                title="Relative Market Outcomes",
                bullets=[
                    f"Compare observed outcome direction and magnitude for {subject_a} versus {subject_b}.",
                    "Cite strongest evidence for both convergence and divergence.",
                ],
            ),
            OutlineSection(
                title="Causal Driver Contrast",
                bullets=[
                    f"Trace the main drivers affecting {subject_a} and {subject_b}.",
                    "Distinguish structural factors from short-term shocks.",
                ],
            ),
            OutlineSection(
                title="Policy and Risk Divergence",
                bullets=[
                    "Compare regulatory interventions and implementation timelines.",
                    "Highlight forward risks, uncertainty, and key monitoring indicators.",
                ],
            ),
        ]
        return OutlineResult(
            executive_summary=executive_summary,
            sections=sections,
            is_comparison=True,
            subjects=[subject_a, subject_b],
        )

    # Single-topic fallback: derive section bullets from findings when possible.
    finding_rows = [(finding, _extract_words(finding.claim)) for finding in state.findings[:12]]
    section_specs = [
        (
            "Market Signals and Observed Changes",
            {"price", "cost", "spread", "volatil", "tariff", "rate", "demand", "supply"},
            [
                "Establish the strongest observed market moves and timing.",
                "Quantify direction and persistence where evidence supports it.",
            ],
        ),
        (
            "Driver and Transmission Pathways",
            {"shipping", "fuel", "import", "export", "geopolit", "outage", "logistic", "pipeline"},
            [
                "Trace causal pathways from disruption to market outcomes.",
                "Separate first-order shocks from secondary transmission effects.",
            ],
        ),
        (
            "Policy and Regulatory Response",
            {"policy", "regulator", "regulatory", "commission", "cap", "intervention", "rule"},
            [
                "Identify interventions, implementation status, and enforcement timing.",
                "Assess pass-through dampening or displacement effects.",
            ],
        ),
        (
            "Forward Risks and Monitoring Signals",
            {"risk", "outlook", "forecast", "future", "storage", "uncertainty", "scenario"},
            [
                "Highlight near-term risk triggers and leading indicators.",
                "Call out unresolved uncertainty and evidence conflicts.",
            ],
        ),
    ]

    sections: List[OutlineSection] = []
    for title, keyword_set, defaults in section_specs:
        bullets: List[str] = []
        for finding, words in finding_rows:
            if not (words & keyword_set):
                continue
            claim_bullet = _normalize_sentence(finding.claim, max_chars=118)
            if claim_bullet and claim_bullet not in bullets:
                bullets.append(claim_bullet)
            if len(bullets) >= 2:
                break
        for default in defaults:
            if len(bullets) >= 2:
                break
            bullets.append(default)
        sections.append(OutlineSection(title=title, bullets=bullets[:3]))

    return OutlineResult(
        executive_summary=executive_summary,
        sections=sections,
        is_comparison=False,
        subjects=None,
    )


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

def _build_outline_prompt(
    search_topic: str,
    claims_text: str,
    today: str,
    research_type: Optional[str] = None,
) -> str:
    """Build the standard thematic outline prompt."""
    min_sections, max_sections = config.SYNTHESIS.get("outline_sections", [4, 6])
    lens_block = _research_lens_text(research_type)
    return f"""Today's date is {today}. You are a research analyst. Create an outline for a briefing on the topic below.

**Topic:** {search_topic}
{lens_block}

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
    search_topic: str,
    subject_a: str,
    subject_b: str,
    claims_text: str,
    today: str,
    research_type: Optional[str] = None,
) -> str:
    """Build comparison outline prompt naming both subjects."""
    min_sections, max_sections = config.SYNTHESIS.get("outline_sections", [4, 6])
    lens_block = _research_lens_text(research_type)
    return f"""Today's date is {today}. You are a research analyst. Create an outline for a comparative briefing.

**Topic:** {search_topic}
**Comparing:** {subject_a} vs {subject_b}
{lens_block}

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


def _is_generic_outline_title(title: str) -> bool:
    normalized = re.sub(r"\s+", " ", (title or "").strip())
    if not normalized:
        return True
    return any(pattern.match(normalized) for pattern in _GENERIC_OUTLINE_TITLE_PATTERNS)


def _is_source_like_outline_title(title: str) -> bool:
    normalized = re.sub(r"\s+", " ", (title or "").strip())
    if not normalized:
        return True
    lowered = normalized.lower()
    words = re.findall(r"[a-z0-9%]+", lowered)

    if "|" in normalized:
        return True
    if re.search(r"\bhttps?://|\bwww\.", lowered):
        return True
    if " - " in normalized and len(words) >= 10:
        return True
    if len(words) > 14:
        return True
    if re.search(r"\b(linkedin|intereconomics|ieefa|volume no|volumes?)\b", lowered):
        return True

    return False


def _passes_outline_quality_gate(outline: OutlineResult) -> bool:
    """Reject parsed outlines that are structurally valid but generic/template-like."""
    summary = re.sub(r"\s+", " ", (outline.executive_summary or "").strip())
    if not summary:
        return False
    if any(pattern.search(summary) for pattern in _LOW_QUALITY_OUTLINE_SUMMARY_PATTERNS):
        return False

    if not outline.sections:
        return False

    generic_titles = [section.title for section in outline.sections if _is_generic_outline_title(section.title)]
    if generic_titles:
        logger.warning("Outline quality failed due to generic section titles: %s", generic_titles)
        return False

    source_like_titles = [section.title for section in outline.sections if _is_source_like_outline_title(section.title)]
    if source_like_titles:
        logger.warning("Outline quality failed due to source-like section titles: %s", source_like_titles)
        return False

    return True


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
        # Reliability guard: keep usable partial outlines (>=2 sections)
        # instead of dropping to deterministic fallback.
        if len(sections) >= 2:
            logger.warning(
                "Outline parse below target: %d sections < min %d (accepting partial outline)",
                len(sections),
                min_sections,
            )
        else:
            logger.warning("Outline parse failed: %d sections < min %d", len(sections), min_sections)
            return None

    # Cap at max
    sections = sections[:max_sections]

    result = OutlineResult(
        executive_summary=executive_summary,
        sections=sections,
        is_comparison=is_comparison,
        subjects=subjects,
    )
    if not _passes_outline_quality_gate(result):
        logger.warning("Outline parse failed quality gate")
        return None

    return result


def _build_outline_retry_prompt(base_prompt: str, rejected_output: str, failure_reason: str) -> str:
    """Build a constrained retry prompt for one failed outline generation."""
    reason_label = failure_reason.replace("_", " ")
    rejected = _normalize_sentence(rejected_output or "", max_chars=1400)
    return (
        f"{base_prompt}\n\n"
        "REWRITE REQUIRED:\n"
        f"- Previous outline failed due to: {reason_label}.\n"
        "- Provide specific analytical section headers (no generic labels like "
        "'Thematic Sections', 'Key Findings', 'Analysis', or 'Conclusion').\n"
        "- Do not use source headlines, article titles, publisher tags, pipes, or links as section headers.\n"
        "- Executive Summary must state a concrete evidence-backed conclusion, not report framing.\n"
        "- Keep format strict: ## Executive Summary then ## Section Title with 2-3 bullets each.\n"
        f"- Rejected outline snippet: {rejected}\n\n"
        "Rewrite now:\n"
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
        prompt = _build_comparison_outline_prompt(
            search_topic,
            subjects[0],
            subjects[1],
            claims_text,
            today,
            research_type=state.research_type,
        )
    else:
        prompt = _build_outline_prompt(
            search_topic,
            claims_text,
            today,
            research_type=state.research_type,
        )

    # Enforce char budget
    max_chars = config.MODEL_BUDGETS.get("synthesis_outline", {}).get("max_input_chars", 5250)
    if len(prompt) > max_chars:
        overshoot = len(prompt) - max_chars
        # Trim claims_text from the end
        claims_text = claims_text[:len(claims_text) - overshoot]
        if is_comparison:
            prompt = _build_comparison_outline_prompt(
                search_topic,
                subjects[0],
                subjects[1],
                claims_text,
                today,
                research_type=state.research_type,
            )
        else:
            prompt = _build_outline_prompt(
                search_topic,
                claims_text,
                today,
                research_type=state.research_type,
            )

    try:
        raw = _call_research_synthesis_model(prompt)
        if not raw:
            logger.warning("Outline model returned empty/error")
            return None

        raw = _normalize_outline_headers(raw)
        parsed = _parse_outline(raw, is_comparison, subjects)
        if parsed:
            return parsed

        # Single constrained retry before deterministic fallback.
        retry_prompt = _build_outline_retry_prompt(
            base_prompt=prompt,
            rejected_output=raw,
            failure_reason="outline_quality_or_parse_failure",
        )
        retry_raw = _call_research_synthesis_model(retry_prompt)
        if not retry_raw:
            return None
        retry_raw = _normalize_outline_headers(retry_raw)
        return _parse_outline(retry_raw, is_comparison, subjects)

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
    """Select sources by section overlap, then source relevance, then credibility."""
    if max_sources is None:
        max_sources = config.SYNTHESIS.get("max_sources_per_section", 4)

    # Build word set from section title + bullets
    section_text = section.title + " " + " ".join(section.bullets)
    section_words = _extract_words(section_text)
    if not section_words:
        return sorted(
            sources,
            key=lambda s: ((s.relevance_score or 0.0), (s.credibility_score or 0.0)),
            reverse=True,
        )[:max_sources]

    scored: List[Tuple[Tuple[float, float, float], Source]] = []
    for source in sources:
        source_text = f"{source.title or ''} {source.content_snippet or ''} {source.content_full or ''}"
        source_words = _extract_words(source_text)
        overlap_count = len(section_words & source_words)
        overlap_ratio = overlap_count / max(len(section_words), 1)
        score = (
            overlap_ratio,
            source.relevance_score or 0.0,
            source.credibility_score or 0.0,
        )
        scored.append((score, source))

    scored.sort(key=lambda t: t[0], reverse=True)

    # If section overlap is weak everywhere, fall back to global relevance ordering.
    if scored and scored[0][0][0] == 0.0:
        return sorted(
            sources,
            key=lambda s: ((s.relevance_score or 0.0), (s.credibility_score or 0.0)),
            reverse=True,
        )[:max_sources]

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

    confidence_rank = {"high": 3.0, "medium": 2.0, "low": 1.0}
    scored: List[Tuple[Tuple[float, float, float, float], Finding]] = []
    for finding in findings:
        finding_words = _extract_words(finding.claim)
        overlap = float(len(section_words & finding_words))
        support = float(len(finding.sources))
        confidence = confidence_rank.get((finding.confidence or "").lower(), 1.0)
        avg_cred = float(finding.average_credibility or 0.0)
        scored.append(((overlap, support, confidence, avg_cred), finding))

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
    source_lookup: Optional[dict] = None,
    market_context: str = "",
    research_type: Optional[str] = None,
) -> str:
    """Build a standard section expansion prompt."""
    claims = _format_claims_for_prompt(
        routed_findings,
        source_lookup=source_lookup or _build_source_lookup(routed_sources),
    )

    evidence_records = _format_evidence_records(
        routed_sources=routed_sources,
        routed_findings=routed_findings,
        source_lookup=source_lookup or _build_source_lookup(routed_sources),
    )

    source_notes = []
    for src in routed_sources:
        title = (src.title or "").strip() or "Untitled Source"
        fact = _extract_source_fact(src, max_chars=220)
        if fact:
            source_notes.append(f"- [{title}] {fact}")
    sources_text = "\n".join(source_notes) if source_notes else "- No source notes available."

    bullets_text = "\n".join(f"- {b}" for b in section.bullets)

    market_block = ""
    if market_context:
        market_block = f"\n**Market Data (for context — do not cite as a 'source'):**\n{market_context}\n"
    lens_block = _research_lens_text(research_type)

    return f"""Today's date is {today}. Write one analytical paragraph for the section below.

**Section:** {section.title}
{lens_block}
**Directions:**
{bullets_text}

**Relevant claims:**
{claims}

**Evidence records (prioritized facts):**
{evidence_records}

**Source notes:**
{sources_text}
{market_block}
**Rules:**
1. Open with the strongest evidence-backed conclusion for this section.
2. Synthesize across sources — do not summarize one source at a time.
3. Cite inline: "costs fell 40% [Source Title]". Every claim must name its source.
4. Include at least 2 cited facts and explicitly mention any key conflict/uncertainty in evidence.
5. No boilerplate caveats ("I cannot guarantee...", "consult more sources", etc.).
6. One paragraph only. No sub-headings.
7. Only cite facts from the provided sources — do not invent data.
8. Do not paste long source snippets or copy headlines verbatim.

Begin:
"""


def _build_comparison_section_prompt(
    section: OutlineSection,
    routed_sources: List[Source],
    routed_findings: List[Finding],
    subjects: List[str],
    today: str,
    source_lookup: Optional[dict] = None,
    market_context: str = "",
    research_type: Optional[str] = None,
) -> str:
    """Build a comparison section expansion prompt."""
    claims = _format_claims_for_prompt(
        routed_findings,
        source_lookup=source_lookup or _build_source_lookup(routed_sources),
    )

    evidence_records = _format_evidence_records(
        routed_sources=routed_sources,
        routed_findings=routed_findings,
        source_lookup=source_lookup or _build_source_lookup(routed_sources),
    )

    source_notes = []
    for src in routed_sources:
        title = (src.title or "").strip() or "Untitled Source"
        fact = _extract_source_fact(src, max_chars=220)
        if fact:
            source_notes.append(f"- [{title}] {fact}")
    sources_text = "\n".join(source_notes) if source_notes else "- No source notes available."

    bullets_text = "\n".join(f"- {b}" for b in section.bullets)

    market_block = ""
    if market_context:
        market_block = f"\n**Market Data (for context — do not cite as a 'source'):**\n{market_context}\n"
    lens_block = _research_lens_text(research_type)

    return f"""Today's date is {today}. Write one analytical paragraph comparing {subjects[0]} and {subjects[1]} on this dimension.

**Dimension:** {section.title}
{lens_block}
**Directions:**
{bullets_text}

**Relevant claims:**
{claims}

**Evidence records (prioritized facts):**
{evidence_records}

**Source notes:**
{sources_text}
{market_block}
**Rules:**
1. Compare BOTH {subjects[0]} and {subjects[1]} on this dimension.
2. Open with the strongest evidence-backed comparison conclusion.
3. Highlight similarities AND differences with specific cited evidence.
4. Cite inline: "costs fell 40% [Source Title]". Every claim must name its source.
5. Include at least 2 cited facts and mention key uncertainty/conflict if present.
6. No boilerplate caveats ("I cannot guarantee...", "consult more sources", etc.).
7. One paragraph only. No sub-headings.
8. Only cite facts from the provided sources — do not invent data.
9. Do not paste long source snippets or copy headlines verbatim.

Begin:
"""


def _build_section_retry_prompt(base_prompt: str, rejected_output: str, failure_reason: str) -> str:
    """Build a constrained retry prompt for one failed section generation."""
    reason_label = failure_reason.replace("_", " ")
    rejected = _normalize_sentence(rejected_output or "", max_chars=800)
    return (
        f"{base_prompt}\n\n"
        "REWRITE REQUIRED:\n"
        f"- Previous draft failed quality checks due to: {reason_label}.\n"
        "- Rewrite as exactly one analytical paragraph (no list framing, no numbered points).\n"
        "- Keep every substantive claim tied to provided evidence and cited inline [Source Title].\n"
        "- Keep output under 170 words and avoid boilerplate language.\n"
        f"- Rejected draft snippet: {rejected}\n\n"
        "Rewrite now:\n"
    )


def _evaluate_section_candidate(
    raw_output: str,
    section: OutlineSection,
    findings: List[Finding],
    sources: List[Source],
    source_lookup: Optional[dict] = None,
) -> Tuple[Optional[str], str]:
    """Normalize and validate section output, returning (paragraph, failure_reason)."""
    # Strip accidental markdown headers from output.
    lines = (raw_output or "").strip().split("\n")
    cleaned = []
    for line in lines:
        if re.match(r"^#{1,6}\s", line.strip()):
            continue
        cleaned.append(line)
    paragraph = "\n".join(cleaned).strip()
    paragraph = _strip_low_value_sentences(paragraph)
    if not paragraph:
        return None, "empty_output"

    if not _is_evidence_grounded(paragraph, findings, sources):
        logger.warning("Section expansion dropped due to weak evidence grounding: %s", section.title)
        return None, "weak_evidence_grounding"

    # Citation salvage before and after normalization.
    paragraph = _salvage_inline_citations(
        paragraph=paragraph,
        routed_findings=findings,
        routed_sources=sources,
        source_lookup=source_lookup or _build_source_lookup(sources),
    )
    paragraph = _normalize_section_output(paragraph)
    if not _has_inline_citation(paragraph):
        paragraph = _salvage_inline_citations(
            paragraph=paragraph,
            routed_findings=findings,
            routed_sources=sources,
            source_lookup=source_lookup or _build_source_lookup(sources),
        )

    if not _has_inline_citation(paragraph):
        logger.warning("Section expansion dropped due to missing inline citations: %s", section.title)
        return None, "missing_inline_citations"

    if not _passes_section_quality_gate(paragraph):
        logger.warning("Section expansion dropped due to low section quality: %s", section.title)
        return None, "low_section_quality"

    return paragraph, ""


def synthesize_section(
    section: OutlineSection,
    sources: List[Source],
    findings: List[Finding],
    state: ResearchState,
    is_comparison: bool,
    subjects: Optional[List[str]],
    source_lookup: Optional[dict] = None,
    market_context: str = "",
) -> Optional[str]:
    """Stage 2: Expand a single section via reasoning model."""
    today = date.today().isoformat()

    if is_comparison and subjects:
        prompt = _build_comparison_section_prompt(
            section,
            sources,
            findings,
            subjects,
            today,
            source_lookup=source_lookup,
            market_context=market_context,
            research_type=state.research_type,
        )
    else:
        prompt = _build_section_prompt(
            section,
            sources,
            findings,
            today,
            source_lookup=source_lookup,
            market_context=market_context,
            research_type=state.research_type,
        )

    try:
        raw = _call_research_synthesis_model(prompt)
        if not raw:
            return None
        paragraph, reason = _evaluate_section_candidate(
            raw_output=raw,
            section=section,
            findings=findings,
            sources=sources,
            source_lookup=source_lookup,
        )
        if paragraph:
            return paragraph

        # Single constrained retry before deterministic fallback.
        retry_prompt = _build_section_retry_prompt(
            base_prompt=prompt,
            rejected_output=raw,
            failure_reason=reason or "quality_repair",
        )
        retry_raw = _call_research_synthesis_model(retry_prompt)
        if not retry_raw:
            return None
        retry_paragraph, _ = _evaluate_section_candidate(
            raw_output=retry_raw,
            section=section,
            findings=findings,
            sources=sources,
            source_lookup=source_lookup,
        )
        return retry_paragraph

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
        logger.warning("Outline generation failed; using deterministic evidence outline fallback")
        outline = _build_evidence_outline_fallback(state)
        if outline is None:
            logger.warning("Deterministic outline fallback unavailable; using deterministic evidence synthesis")
            return _deterministic_evidence_synthesis(state, reason="outline_unavailable")
        _emit_progress(
            progress_callback,
            "synthesis",
            f"Outline fallback generated: {len(outline.sections)} sections. Expanding...",
        )
    if _summary_needs_rewrite(outline.executive_summary):
        outline.executive_summary = _deterministic_executive_summary(state)

    if progress_callback:
        _emit_progress(
            progress_callback, "synthesis",
            f"Outline ready: {len(outline.sections)} sections. Expanding...",
        )

    # Stage 2: Per-section expansion
    expanded_sections: List[Optional[str]] = []
    model_section_count = 0
    deterministic_section_count = 0
    source_lookup = _build_source_lookup(state.sources_checked)

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
            source_lookup=source_lookup,
            market_context=market_context,
        )
        if paragraph:
            model_section_count += 1
        else:
            paragraph = _deterministic_section_paragraph(section, routed_src, routed_fnd, source_lookup)
            deterministic_section_count += 1

        expanded_sections.append(paragraph)

    if model_section_count == 0:
        logger.warning(
            "All section expansions unavailable from model; assembling deterministic section output"
        )

    # Stage 3: Assembly
    _emit_progress(progress_callback, "synthesis", "Assembling final synthesis...")
    synthesis = assemble_synthesis(outline, expanded_sections)

    state.synthesis = synthesis
    if model_section_count == 0 and deterministic_section_count > 0:
        state.synthesis_model = "deterministic"
    elif deterministic_section_count > 0:
        state.synthesis_model = "mixed"
    else:
        state.synthesis_model = "reasoning"
    logger.info(
        "Synthesis complete (%d model sections, %d deterministic fallback sections, total=%d)",
        model_section_count,
        deterministic_section_count,
        len(outline.sections),
    )
    return synthesis


def _fallback_synthesis(state: ResearchState) -> str:
    """Final minimal fallback only when no useful evidence is available."""
    lines = [
        "## Executive Summary",
        "Insufficient usable evidence to answer this query reliably.",
        "",
        "## Evidence Status",
        "No reliable, query-grounded findings could be extracted from the current source set.",
        "",
        "## Confidence and Gaps",
        (
            f"Retrieved sources: {state.total_sources}. "
            "Broaden or refine the query and retry to collect stronger evidence."
        ),
    ]

    synthesis = "\n".join(lines)
    state.synthesis = synthesis
    state.synthesis_model = "fallback"
    return synthesis
