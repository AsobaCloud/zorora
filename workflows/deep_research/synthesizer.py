"""Synthesizer for deep research output assembly and quality gating."""

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
    re.compile(r"^listen to this article\b", re.IGNORECASE),
    re.compile(r"^click here to share\b", re.IGNORECASE),
    re.compile(r"\bshare\s+(?:facebook|twitter|whatsapp|copylink)\b", re.IGNORECASE),
    re.compile(r"^\s*loading\b", re.IGNORECASE),
    re.compile(r"\bbuy now\b", re.IGNORECASE),
    re.compile(r"open account|download now|login now", re.IGNORECASE),
    re.compile(r"request sample|report format|table of contents|methodology", re.IGNORECASE),
    re.compile(r"blogs?\s+insights?\s+home\b", re.IGNORECASE),
    re.compile(r"welcome gift|claim now", re.IGNORECASE),
]
_LOW_QUALITY_OUTLINE_SUMMARY_PATTERNS = [
    re.compile(r"\bthis (?:report|brief|analysis) (?:provides|presents|offers)\b", re.IGNORECASE),
    re.compile(r"\boverview of (?:key )?(?:themes|findings|considerations)\b", re.IGNORECASE),
    re.compile(r"\bthis section\b", re.IGNORECASE),
]
_GENERIC_OUTLINE_TITLE_PATTERNS = [
    re.compile(r"^thematic sections?$", re.IGNORECASE),
    re.compile(r"^key findings(?: and insights)?$", re.IGNORECASE),
    re.compile(r"^evidence highlights?$", re.IGNORECASE),
    re.compile(r"^source coverage$", re.IGNORECASE),
    re.compile(r"^confidence and gaps$", re.IGNORECASE),
    re.compile(r"^gaps?$", re.IGNORECASE),
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
    "diligence": "Produce a structured acquisition diligence report. Estimate revenue potential, identify regulatory requirements, benchmark performance against targets, and assess vendor/counterparty relationships.",
}

_BACKGROUND_TERM_DEFINITIONS = {
    "lng": "LNG is liquefied natural gas, meaning natural gas cooled into a liquid so it can be shipped by sea.",
}

_RESEARCH_ANALYST_SYSTEM_PROMPT = (
    "You are a senior energy and electricity market research analyst. "
    "Write concise, evidence-grounded synthesis from supplied records only. "
    "Lead with conclusions, explain causal links, note conflicts, and cite inline "
    "using the provided source titles in square brackets. "
    "Do not produce planning steps, meta commentary, or procedural narration."
)

_DIRECT_RESEARCH_ANALYST_SYSTEM_PROMPT = (
    "You are a senior energy and electricity market research analyst. "
    "Answer the user's research question directly using the supplied records as primary evidence. "
    "Lead with conclusions, explain causal links, note conflicts, and cite inline "
    "using the provided source titles in square brackets. "
    "If the records leave a material gap, add concise general context marked "
    "[Background Knowledge]. "
    "Do not produce planning steps, meta commentary, or procedural narration."
)

_DILIGENCE_ANALYST_SYSTEM_PROMPT = (
    "You are a senior renewable energy due diligence analyst specializing in "
    "acquisition advisory for power generation assets in emerging markets. "
    "You produce structured diligence reports for investment committees. "
    "For each report section, synthesize the domain-specific sources provided, "
    "quantify where data permits, flag material gaps, and cite inline using "
    "exact source titles in square brackets. "
    "Do not produce planning steps, meta commentary, or procedural narration."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _emit_progress(callback, phase: str, message: str):
    if callback:
        callback("running", phase, message)


def _call_research_synthesis_model(
    prompt: str,
    system_prompt: Optional[str] = None,
) -> Optional[str]:
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
        analyst_system_prompt = system_prompt or _RESEARCH_ANALYST_SYSTEM_PROMPT

        messages = [
            {"role": "system", "content": analyst_system_prompt},
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
    title = (source.title or "").strip()
    title_norm = re.sub(r"\s+", " ", title) if title else ""

    def _is_low_value_sentence(sentence: str) -> bool:
        normalized = re.sub(r"\s+", " ", (sentence or "").strip())
        if not normalized:
            return True
        if any(pattern.search(normalized) for pattern in _LOW_VALUE_SOURCE_FACT_PATTERNS):
            return True
        token_count = len(re.findall(r"[A-Za-z0-9%$-]+", normalized))
        if token_count < 6:
            return True
        if normalized.count("|") >= 2:
            return True
        if normalized.count("...") >= 1 and token_count < 18:
            return True
        alpha_ratio = sum(ch.isalpha() for ch in normalized) / max(len(normalized), 1)
        if alpha_ratio < 0.45:
            return True
        return False

    def _clean_text(text: str) -> str:
        cleaned = re.sub(r"\s+", " ", (text or "")).strip()
        if not cleaned:
            return ""
        if title_norm:
            if cleaned.lower().startswith(title_norm.lower()):
                cleaned = cleaned[len(title_norm):].strip(" .:-")
            cleaned = cleaned.replace(title_norm, "").strip()
        cleaned = re.sub(r"\[[^\]]{30,}\]", "", cleaned).strip()
        return cleaned

    def _pick_sentence(text: str) -> str:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        best = ""
        for sentence in sentences:
            normalized = re.sub(
                r"^(firstly|secondly|thirdly|however|in summary),?\s+",
                "",
                sentence,
                flags=re.IGNORECASE,
            )
            if _is_low_value_sentence(normalized):
                continue
            if len(normalized) >= 30 and re.search(r"\d", normalized):
                return normalized
            if not best and len(normalized) >= 20:
                best = normalized
        return best

    # Prefer snippet first; full content often contains page-chrome noise.
    for candidate in (source.content_snippet or "", source.content_full or ""):
        cleaned = _clean_text(candidate)
        if not cleaned:
            continue
        chosen = _pick_sentence(cleaned)
        if not chosen:
            continue
        if chosen.count("[") > 1:
            continue
        if re.match(r"^[A-Z][a-z]{2,9}\s+\d{1,2},\s+\d{4}\b", chosen):
            continue
        return _normalize_sentence(chosen, max_chars=max_chars)

    return ""


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

    citation_index = 0
    for idx, sentence in enumerate(sentences):
        if citation_index >= len(citations):
            break
        if sentence.startswith("[Background Knowledge]"):
            continue
        if not _has_inline_citation(sentence):
            sentences[idx] = f"{sentence} {citations[citation_index]}"
            citation_index += 1

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
    conclusion = ""
    if lead and support:
        conclusion = (
            f"Together, these cited records indicate a consistent signal in {section_label.lower()}."
        )
    return " ".join(part for part in [lead, support, conclusion] if part)


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
            header_text = header_text.rstrip(":").strip()
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
# Direct synthesis
# ---------------------------------------------------------------------------

def _direct_synthesis_content_budget() -> int:
    budgets = [
        int(config.SYNTHESIS.get("content_budget", 0) or 0),
        int(config.SYNTHESIS.get("clustering_char_budget", 0) or 0),
        int(config.CONTENT_FETCH.get("prompt_content_budget", 0) or 0),
    ]
    return max([budget for budget in budgets if budget > 0] + [12000])


def _prompt_excerpt(text: str, max_chars: int) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def _format_direct_sources_for_prompt(sources: List[Source]) -> str:
    """Format ranked sources into a single prompt block within a shared char budget."""
    if not sources:
        return "No ranked sources were retrieved."

    total_budget = _direct_synthesis_content_budget()
    min_chars_per_source = int(config.SYNTHESIS.get("min_chars_per_source", 500) or 500)
    per_source_cap = max(min_chars_per_source, total_budget // max(len(sources), 1))
    per_source_cap = min(per_source_cap, 1200)

    entries: List[str] = []
    chars_used = 0

    for idx, source in enumerate(sources, start=1):
        title = (source.title or "").strip() or f"Source {idx}"
        url = (source.url or "").strip() or "N/A"
        source_type = (source.source_type or "unknown").strip() or "unknown"
        content = source.content_full or source.content_snippet or source.title or ""
        excerpt = _prompt_excerpt(content, max_chars=per_source_cap)

        entry = "\n".join(
            [
                f"{idx}. {title}",
                f"   URL: {url}",
                f"   Source Type: {source_type}",
                f"   Credibility Score: {float(source.credibility_score or 0.0):.2f}",
                f"   Relevance Score: {float(source.relevance_score or 0.0):.2f}",
                f"   Evidence: {excerpt or 'No usable excerpt available.'}",
            ]
        )

        if chars_used + len(entry) > total_budget and entries:
            remaining = total_budget - chars_used
            if remaining < 240:
                entries.append(
                    f"... {len(sources) - idx + 1} additional ranked sources omitted due to context budget."
                )
                break

            fixed_chars = len(entry) - len(excerpt)
            excerpt_cap = max(120, remaining - fixed_chars - 3)
            trimmed_excerpt = _prompt_excerpt(content, max_chars=excerpt_cap)
            entry = "\n".join(
                [
                    f"{idx}. {title}",
                    f"   URL: {url}",
                    f"   Source Type: {source_type}",
                    f"   Credibility Score: {float(source.credibility_score or 0.0):.2f}",
                    f"   Relevance Score: {float(source.relevance_score or 0.0):.2f}",
                    f"   Evidence: {trimmed_excerpt or 'No usable excerpt available.'}",
                ]
            )
            if chars_used + len(entry) > total_budget:
                entries.append(
                    f"... {len(sources) - idx + 1} additional ranked sources omitted due to context budget."
                )
                break

        entries.append(entry)
        chars_used += len(entry)

    return "\n\n".join(entries)


def _build_diligence_synthesis_prompt(
    state: ResearchState,
    diligence_context: str = "",
    asset_metadata: Optional[dict] = None,
) -> str:
    """Build a diligence-specific synthesis prompt with fixed report sections."""
    today = date.today().isoformat()
    search_topic = state.refined_query or state.original_query
    sources_text = _format_direct_sources_for_prompt(state.sources_checked)
    meta = asset_metadata or {}

    asset_block = (
        f"**ASSET UNDER REVIEW:**\n"
        f"- Name: {meta.get('name', 'Unknown')}\n"
        f"- Technology: {meta.get('technology', 'Unknown')}\n"
        f"- Capacity: {meta.get('capacity_mw', 'Unknown')} MW\n"
        f"- Country: {meta.get('country', 'Unknown')}\n"
        f"- Operator: {meta.get('operator', 'Unknown')}\n"
        f"- Owner: {meta.get('owner', 'Unknown')}\n"
        f"- Status: {meta.get('status', 'Unknown')}\n"
    )

    context_block = ""
    if diligence_context:
        context_block = (
            "\n**LOCAL DATA CONTEXT (use for quantitative analysis; do not cite as a source):**\n"
            f"{diligence_context}\n"
        )

    return f"""Today's date is {today}. Produce a structured acquisition diligence report for the asset described below.

{asset_block}
**RESEARCH QUESTION:** {state.original_query}
**SEARCH TOPIC / REFINEMENT:** {search_topic}

**RANKED SOURCES:**
{sources_text}
{context_block}
**Instructions:**
1. Use the local data context for quantitative analysis (tariff rates, capacity benchmarks, RPS targets).
2. Use the ranked sources for qualitative context (regulatory environment, vendor intelligence, market trends).
3. Cite evidence inline using exact source titles in square brackets.
4. If the sources leave a material gap, supplement with concise general knowledge marked as [Background Knowledge].
5. Use today's date ({today}) when interpreting relative dates.
6. No planning language, no meta-commentary, no boilerplate caveats.

**Output format (follow exactly; use ## for all headers):**

## Executive Summary
[2-4 sentences summarizing the diligence findings with key risk/opportunity highlights]

## Tariff & Revenue Potential
[Analysis of electricity tariffs, pricing mechanisms, and estimated revenue potential with inline citations]

## Regulatory & Licensing Requirements
[Required permits, regulatory approvals, compliance obligations with inline citations]

## Performance Gap Analysis
[Benchmarking against comparable plants, capacity factor analysis, performance targets with inline citations]

## Vendor & Counterparty Relationships
[Known offtake agreements, vendor dependencies, counterparty risk assessment with inline citations]

## Risk Summary & Recommendation
[Key risks, mitigants, and overall acquisition recommendation with inline citations]

Begin:
"""


def _build_diligence_synthesis_prompt_v2(
    state: ResearchState,
    diligence_context: str = "",
    asset_metadata: Optional[dict] = None,
) -> str:
    """Build a diligence prompt with per-section source grouping and analytical questions."""
    today = date.today().isoformat()
    search_topic = state.refined_query or state.original_query
    meta = asset_metadata or {}

    asset_block = (
        f"**ASSET UNDER REVIEW:**\n"
        f"- Name: {meta.get('name', 'Unknown')}\n"
        f"- Technology: {meta.get('technology', 'Unknown')}\n"
        f"- Capacity: {meta.get('capacity_mw', 'Unknown')} MW\n"
        f"- Country: {meta.get('country', 'Unknown')}\n"
        f"- Operator: {meta.get('operator', 'Unknown')}\n"
        f"- Owner: {meta.get('owner', 'Unknown')}\n"
        f"- Status: {meta.get('status', 'Unknown')}\n"
    )

    context_block = ""
    if diligence_context:
        context_block = (
            "\n**LOCAL DATA CONTEXT (use for quantitative analysis; do not cite as a source):**\n"
            f"{diligence_context}\n"
        )

    # Format parameters for question templates
    fmt = {
        "country": meta.get("country", "the target country"),
        "technology": meta.get("technology", "power"),
        "capacity_mw": meta.get("capacity_mw", ""),
        "name": meta.get("name", "the target asset"),
        "operator": meta.get("operator", "the operator"),
    }

    # Group sources by domain
    grouped = _format_sources_by_domain(state.sources_checked or [])

    # Build per-section blocks
    section_blocks: List[str] = []

    section_blocks.append(
        "## Executive Summary\n"
        "[2-4 sentences summarizing the diligence findings with key risk/opportunity highlights]"
    )

    for domain_key, section_title in _DILIGENCE_DOMAIN_SECTIONS.items():
        question_template = _DILIGENCE_SECTION_QUESTIONS.get(domain_key, "")
        question = question_template.format(**fmt) if question_template else ""
        sources_text = grouped.get(domain_key, "")
        if not sources_text:
            sources_text = (
                "No sources were retrieved for this domain. State this gap explicitly "
                "and provide brief [Background Knowledge] if possible."
            )

        block = f"## {section_title}\n"
        if question:
            block += f"**Question:** {question}\n"
        block += f"**Sources for this section:**\n{sources_text}"
        section_blocks.append(block)

    section_blocks.append(
        "## Risk Summary & Recommendation\n"
        "[Synthesize across all domains: key risks, mitigants, acquisition recommendation]"
    )

    sections_text = "\n\n".join(section_blocks)

    return f"""Today's date is {today}. Produce a structured acquisition diligence report for the asset described below.

{asset_block}
**RESEARCH QUESTION:** {state.original_query}
**SEARCH TOPIC / REFINEMENT:** {search_topic}
{context_block}
**Instructions:**
1. For each section below, analyze ONLY the domain-specific sources listed under that section.
2. Cite evidence inline using exact source titles in square brackets.
3. If a section has no sources, supplement with concise general knowledge marked as [Background Knowledge].
4. Use today's date ({today}) when interpreting relative dates.
5. No planning language, no meta-commentary, no boilerplate caveats.

**Output format (follow exactly; use ## for all headers):**

{sections_text}

Begin:
"""


def generate_diligence_charts(
    asset_metadata: dict,
    diligence_context: str = "",
) -> list:
    """Generate diligence charts as base64-encoded PNGs.

    Returns list of (section_title, data_uri) tuples.
    """
    import base64
    import io

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available for diligence charts")
        return []

    charts = []
    capacity_mw = float(asset_metadata.get("capacity_mw", 0) or 0)
    technology = asset_metadata.get("technology", "Power")
    country = asset_metadata.get("country", "")

    # Chart 1: Revenue estimate at low/mid/high tariff rates
    if capacity_mw > 0:
        try:
            capacity_factors = {"Solar": 0.20, "Wind": 0.30, "Coal": 0.70, "Gas": 0.50}
            cf = capacity_factors.get(technology, 0.35)
            annual_mwh = capacity_mw * cf * 8760

            low_rate, mid_rate, high_rate = 0.04, 0.07, 0.12
            revenues = [annual_mwh * r for r in (low_rate, mid_rate, high_rate)]

            fig, ax = plt.subplots(figsize=(8, 4))
            bars = ax.bar(
                ["Low ($0.04/kWh)", "Mid ($0.07/kWh)", "High ($0.12/kWh)"],
                [r / 1e6 for r in revenues],
                color=["#94a3b8", "#3b82f6", "#22c55e"],
            )
            ax.set_ylabel("Annual Revenue ($M)")
            ax.set_title(f"Estimated Annual Revenue — {capacity_mw:.0f} MW {technology} (CF={cf:.0%})")
            ax.grid(True, alpha=0.3, axis="y")
            for bar, rev in zip(bars, revenues):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                        f"${rev / 1e6:.1f}M", ha="center", va="bottom", fontsize=9)
            fig.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=100)
            plt.close(fig)
            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode("ascii")
            charts.append(("Revenue Estimate", f"data:image/png;base64,{b64}"))
        except Exception as exc:
            logger.warning("Revenue chart generation failed: %s", exc)

    # Chart 2: Capacity benchmark vs comparable plants
    try:
        from tools.imaging.store import ImagingDataStore
        img_store = ImagingDataStore()
        comparable = img_store.get_generation_assets(technology=technology or None, country=country or None)
        features = comparable.get("features", []) if isinstance(comparable, dict) else []
        capacities = [
            f.get("properties", {}).get("capacity_mw", 0)
            for f in features
            if f.get("properties", {}).get("capacity_mw")
        ]
        if capacities and capacity_mw > 0:
            import statistics
            avg_cap = statistics.mean(capacities)
            med_cap = statistics.median(capacities)

            fig, ax = plt.subplots(figsize=(8, 4))
            labels = ["This Asset", f"Average ({len(capacities)} plants)", "Median"]
            values = [capacity_mw, avg_cap, med_cap]
            colors = ["#f59e0b", "#3b82f6", "#8b5cf6"]
            ax.barh(labels, values, color=colors)
            ax.set_xlabel("Capacity (MW)")
            ax.set_title(f"Capacity Benchmark — {technology} in {country}")
            ax.grid(True, alpha=0.3, axis="x")
            for i, v in enumerate(values):
                ax.text(v + max(values) * 0.02, i, f"{v:.0f} MW", va="center", fontsize=9)
            fig.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=100)
            plt.close(fig)
            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode("ascii")
            charts.append(("Capacity Benchmark", f"data:image/png;base64,{b64}"))
    except Exception as exc:
        logger.warning("Capacity benchmark chart generation failed: %s", exc)

    return charts


def _build_direct_synthesis_prompt(state: ResearchState, market_context: str = "") -> str:
    """Build a single-pass question-answering prompt over the ranked source set."""
    today = date.today().isoformat()
    search_topic = state.refined_query or state.original_query
    lens_block = _research_lens_text(state.research_type)
    sources_text = _format_direct_sources_for_prompt(state.sources_checked)

    market_block = ""
    if market_context:
        market_block = (
            "\n**Market Context (context only; do not cite as a source):**\n"
            f"{market_context}\n"
        )

    return f"""Today's date is {today}. Answer the research question directly using the ranked source set below.

**RESEARCH QUESTION:** {state.original_query}
**SEARCH TOPIC / REFINEMENT:** {search_topic}
{lens_block}
**RANKED SOURCES:**
{sources_text}
{market_block}
**Instructions:**
1. Answer the research question directly in the executive summary and throughout the report.
2. Use the full ranked source set below as primary evidence; do not narrow to a routed subset.
3. Synthesize across sources instead of summarizing one source at a time.
4. Cite evidence inline using the exact source titles in square brackets, e.g. [Grid Operations Update].
5. If the sources leave a material gap, supplement with concise general knowledge and mark every such addition as [Background Knowledge].
6. Preserve uncertainty, disagreement, and evidence gaps when sources conflict or remain incomplete.
7. No planning language, no meta-commentary, no boilerplate caveats, and no procedural narration.
8. Do not invent sourced statistics, dates, or claims that are not supported by the ranked records.
9. Do not cite the market-context block as a source.
10. Use today's date ({today}) when interpreting relative dates in the evidence.

**Output format (follow exactly; use ## for all headers):**

## Executive Summary
[2-4 sentences that directly answer the question with inline citations]

## Direct Answer
[1 concise paragraph that synthesizes the main answer with inline citations]

## [Thematic Section Title]
[1 concise paragraph with inline citations]

## [Thematic Section Title]
[1 concise paragraph with inline citations]

[Use 2-4 thematic sections total, driven by the question rather than by individual sources.]

Begin:
"""


def _extract_markdown_section(text: str, title: str) -> str:
    pattern = re.compile(
        rf"(?ms)^##\s+{re.escape(title)}\s*\n(.*?)(?=^##\s+|\Z)"
    )
    match = pattern.search(text or "")
    if not match:
        return ""
    return match.group(1).strip()


def _replace_markdown_section(text: str, title: str, replacement: str) -> str:
    pattern = re.compile(
        rf"(?ms)^##\s+{re.escape(title)}\s*\n(.*?)(?=^##\s+|\Z)"
    )
    return pattern.sub(f"## {title}\n{replacement.strip()}\n\n", text, count=1).rstrip()


def _insert_after_section(text: str, title: str, content: str) -> str:
    """Insert content at the end of a named markdown section."""
    pattern = re.compile(
        rf"(?ms)(^##\s+{re.escape(title)}\s*\n.*?)(?=^##\s+|\Z)"
    )
    match = pattern.search(text or "")
    if not match:
        return text + content
    end = match.end()
    return text[:end].rstrip() + content + "\n" + text[end:]


def _parse_markdown_sections(text: str) -> List[Tuple[str, str]]:
    sections: List[Tuple[str, str]] = []
    matches = list(re.finditer(r"(?m)^##\s+(.+)$", text or ""))
    for idx, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text or "")
        body = (text or "")[start:end].strip()
        sections.append((title, body))
    return sections


def _has_ranked_source_citation(text: str, sources: List[Source]) -> bool:
    titles = {
        (source.title or "").strip()
        for source in sources
        if (source.title or "").strip()
    }
    if not titles:
        return False
    citations = re.findall(r"\[([^\]]+)\]", text or "")
    return any(citation.strip() in titles for citation in citations)


def _count_ranked_source_citations(text: str, sources: List[Source]) -> int:
    titles = {
        (source.title or "").strip()
        for source in sources
        if (source.title or "").strip()
    }
    citations = {citation.strip() for citation in re.findall(r"\[([^\]]+)\]", text or "")}
    return len(citations & titles)


def _build_direct_synthesis_retry_prompt(base_prompt: str, rejected_output: str, failure_reason: str) -> str:
    rejected = _normalize_sentence(rejected_output or "", max_chars=1200)
    reason_label = failure_reason.replace("_", " ")
    return (
        f"{base_prompt}\n\n"
        "REWRITE REQUIRED:\n"
        f"- Previous draft failed quality checks because: {reason_label}.\n"
        "- Replace placeholder headers with specific analytical section titles.\n"
        "- Every section paragraph, including ## Direct Answer, must contain at least one inline source-title citation.\n"
        "- Do not say that further research is needed, that sources are incomplete, or that the answer is only partial.\n"
        "- Keep the report focused on directly answering the question from the supplied evidence.\n"
        "- If you add general context beyond the sources, mark it [Background Knowledge].\n"
        f"- Rejected draft snippet: {rejected}\n\n"
        "Rewrite now:\n"
    )


def _normalize_direct_citation_labels(text: str) -> str:
    normalized = re.sub(
        r"\[\s*Source\s+\d+\s*:\s*([^\]]+?)\s*\]",
        r"[\1]",
        text or "",
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"\[\s*Sources?\s+\d+\s*:\s*([^\]]+?)\s*\]",
        r"[\1]",
        normalized,
        flags=re.IGNORECASE,
    )
    return normalized


def _derive_direct_section_title(body: str, index: int) -> str:
    first_sentence = re.split(r"(?<=[.!?])\s+", (body or "").strip())[0]
    cleaned = re.sub(r"\[[^\]]+\]", "", first_sentence)
    cleaned = re.sub(
        r"^(?:the sources?|these sources?)\s+"
        r"(?:provide insights into|highlight|offer insights into|indicate|show|suggest)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^here are the key points:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" .:-")
    words = re.findall(r"[A-Za-z0-9/&-]+", cleaned)
    if not words:
        return f"Section {index}"

    title = " ".join(words[:6]).title()
    title = title.replace("Lng", "LNG").replace("Eu", "EU").replace("Iea", "IEA")
    return title


def _normalize_direct_section_title(title: str) -> str:
    fixed = re.sub(r"\*{1,2}(.*?)\*{1,2}", r"\1", title or "").strip()
    fixed = fixed.rstrip(":").strip()

    match = re.match(
        r"^(?:thematic\s+)?(?:section|theme|topic|dimension)\s*:\s*(.+)$",
        fixed,
        re.IGNORECASE,
    )
    if match:
        fixed = match.group(1).strip()

    return fixed


def _mark_background_knowledge_sentences(
    body: str,
    query: str = "",
    sources_define_term: bool = False,
) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body or "") if s.strip()]
    if not sentences:
        return (body or "").strip()

    term = _definition_term_from_query(query)
    term_lower = term.lower()

    rebuilt: List[str] = []
    mark_next_uncited = False
    for sentence in sentences:
        if (
            term_lower
            and not sources_define_term
            and not _has_inline_citation(sentence)
            and (
                re.search(rf"\b{re.escape(term_lower)}\s+(?:is|stands for|refers to)\b", sentence, re.IGNORECASE)
                or (term_lower == "lng" and "liquefied natural gas" in sentence.lower())
            )
            and not sentence.startswith("[Background Knowledge]")
        ):
            sentence = f"[Background Knowledge] {sentence}"

        if re.search(
            r"\b(?:sources?|documents?|records?)\s+do\s+not\b|\bdo\s+not\s+(?:specifically\s+)?define\b",
            sentence,
            re.IGNORECASE,
        ):
            if not _has_inline_citation(sentence) and not sentence.startswith("[Background Knowledge]"):
                sentence = f"[Background Knowledge] {sentence}"
            rebuilt.append(sentence)
            mark_next_uncited = True
            continue

        if mark_next_uncited and not _has_inline_citation(sentence):
            if not sentence.startswith("[Background Knowledge]"):
                sentence = f"[Background Knowledge] {sentence}"
            mark_next_uncited = False

        rebuilt.append(sentence)

    return " ".join(rebuilt).strip()


def _is_background_knowledge_only_section(body: str) -> bool:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body or "") if s.strip()]
    if not sentences:
        return False
    return all(sentence.startswith("[Background Knowledge]") for sentence in sentences)


def _definition_sentence_from_sections(sections: List[Tuple[str, str]], query: str) -> str:
    term = _definition_term_from_query(query)
    if not term:
        return ""

    term_lower = term.lower()
    for _title, body in sections:
        for sentence in [s.strip() for s in re.split(r"(?<=[.!?])\s+", body or "") if s.strip()]:
            lowered = sentence.lower()
            if re.search(rf"\b{re.escape(term_lower)}\s+(?:is|stands for|refers to)\b", lowered):
                return sentence
            if term_lower == "lng" and "liquefied natural gas" in lowered:
                return sentence
    return ""


def _ensure_direct_answer_definition(text: str, state: ResearchState) -> str:
    if _direct_answer_covers_definition(text, state.original_query):
        return text

    term = _definition_term_from_query(state.original_query)
    if not term:
        return text

    definition_fact, definition_title = _find_definition_fact(term, state.sources_checked)
    if definition_fact and definition_title:
        definition_sentence = f"{definition_fact.rstrip('.')} [{definition_title}]."
    else:
        definition_sentence = _definition_sentence_from_sections(
            _parse_markdown_sections(text),
            state.original_query,
        )
        if definition_sentence and not _has_inline_citation(definition_sentence):
            definition_sentence = f"[Background Knowledge] {definition_sentence}"

    if not definition_sentence:
        return text

    direct_answer = _extract_markdown_section(text, "Direct Answer")
    if not direct_answer:
        return text

    if definition_sentence in direct_answer:
        return text

    return _replace_markdown_section(
        text,
        "Direct Answer",
        f"{definition_sentence} {direct_answer}".strip(),
    )


def _repair_direct_synthesis_output(text: str, state: ResearchState) -> str:
    sections = _parse_markdown_sections(text)
    if not sections:
        return text

    source_lookup = _build_source_lookup(state.sources_checked)
    definition_term = _definition_term_from_query(state.original_query)
    sources_define_term = bool(
        _find_definition_fact(definition_term, state.sources_checked)[0]
    )
    repaired: List[str] = []
    seen_titles = set()
    thematic_sections_kept = 0
    dropped_titles = {
        "sources",
        "gaps",
        "uncertainty",
        "background knowledge",
        "caveats",
        "conclusion",
        "conclusions",
    }

    for index, (title, body) in enumerate(sections, start=1):
        fixed_title = _normalize_direct_section_title(title)
        if re.fullmatch(r"\[Thematic Section Title\]|Thematic Section \d+", fixed_title):
            fixed_title = _derive_direct_section_title(body, index=index)
        if fixed_title.lower() in dropped_titles:
            continue

        fixed_body = (body or "").strip()
        if fixed_title.lower() != "executive summary":
            fixed_body = _mark_background_knowledge_sentences(
                fixed_body,
                query=state.original_query,
                sources_define_term=sources_define_term,
            )
            fixed_body = _normalize_section_output(fixed_body, max_sentences=5, max_words=190)
            if not _has_ranked_source_citation(fixed_body, state.sources_checked):
                fixed_body = _salvage_inline_citations(
                    paragraph=fixed_body,
                    routed_findings=[],
                    routed_sources=state.sources_checked,
                    source_lookup=source_lookup,
                )

        normalized_title = fixed_title.lower()
        if normalized_title == "executive summary":
            pass
        elif normalized_title == "direct answer":
            if normalized_title in seen_titles:
                continue
        else:
            if normalized_title in seen_titles:
                continue
            if thematic_sections_kept >= 3:
                continue
            thematic_sections_kept += 1

        seen_titles.add(normalized_title)
        repaired.append(f"## {fixed_title}")
        repaired.append(fixed_body)
        repaired.append("")

    repaired_text = "\n".join(repaired).strip()
    return _ensure_direct_answer_definition(repaired_text, state)


def _passes_direct_synthesis_quality_gate(text: str, state: ResearchState) -> bool:
    normalized = (text or "").strip()
    if not normalized:
        return False

    sections = _parse_markdown_sections(normalized)
    if len(sections) < 3:
        return False
    if sections[0][0].strip().lower() != "executive summary":
        return False
    if not any(title.strip().lower() == "direct answer" for title, _ in sections[1:]):
        return False
    min_source_citations = 2 if len(state.sources_checked) >= 2 else 1
    if _count_ranked_source_citations(normalized, state.sources_checked) < min_source_citations:
        return False

    executive_summary = sections[0][1]
    if executive_summary and _summary_needs_rewrite(executive_summary):
        return False
    if not _direct_answer_covers_definition(normalized, state.original_query):
        return False

    for title, body in sections[1:]:
        cleaned_title = re.sub(r"\s+", " ", title).strip()
        if not cleaned_title:
            return False
        if cleaned_title == "[Thematic Section Title]":
            return False
        if cleaned_title.lower() in {
            "market data context",
            "market context",
            "commodities",
            "treasuries",
            "fx",
            "rates",
            "metals",
        }:
            return False
        if _is_generic_outline_title(cleaned_title):
            return False
        if cleaned_title.lower() in {"conclusion", "conclusions"}:
            return False
        if (
            not _has_ranked_source_citation(body, state.sources_checked)
            and not _is_background_knowledge_only_section(body)
        ):
            return False
        if re.search(r"\bdoes not address the specific question\b", body, re.IGNORECASE):
            return False
        if re.search(r"\bdoes not provide any information\b", body, re.IGNORECASE):
            return False
        if any(pattern.search(body) for pattern in _LOW_VALUE_SENTENCE_PATTERNS):
            return False
        if any(pattern.search(body) for pattern in _LOW_QUALITY_SECTION_PATTERNS):
            return False

    return True


def _passes_diligence_quality_gate(text: str, state: ResearchState) -> bool:
    """Quality gate for diligence reports — does NOT require 'Direct Answer'."""
    normalized = (text or "").strip()
    if not normalized:
        return False

    sections = _parse_markdown_sections(normalized)
    if len(sections) < 4:
        return False
    if sections[0][0].strip().lower() != "executive summary":
        return False

    # Must have at least 3 of the 6 diligence section titles (brownfield or BESS)
    diligence_titles = list(_DILIGENCE_DOMAIN_SECTIONS.values()) + list(_BESS_DOMAIN_SECTIONS.values())
    matched = 0
    for title, _ in sections[1:]:
        cleaned = re.sub(r"\s+", " ", title).strip()
        if any(dt.lower() in cleaned.lower() for dt in diligence_titles):
            matched += 1
    if matched < 3:
        return False

    # Minimum source citations
    min_source_citations = 2 if len(state.sources_checked) >= 2 else 1
    if _count_ranked_source_citations(normalized, state.sources_checked) < min_source_citations:
        return False

    # Executive summary must not be generic
    executive_summary = sections[0][1]
    if executive_summary and _summary_needs_rewrite(executive_summary):
        return False

    return True


def _repair_diligence_synthesis_output(text: str, state: ResearchState) -> str:
    """Lighter repair for diligence — does NOT cap thematic sections at 3."""
    sections = _parse_markdown_sections(text)
    if not sections:
        return text

    source_lookup = _build_source_lookup(state.sources_checked)
    repaired: List[str] = []
    seen_titles = set()
    dropped_titles = {
        "sources",
        "gaps",
        "uncertainty",
        "background knowledge",
        "caveats",
    }

    for index, (title, body) in enumerate(sections, start=1):
        fixed_title = _normalize_direct_section_title(title)
        if fixed_title.lower() in dropped_titles:
            continue

        fixed_body = (body or "").strip()
        if fixed_title.lower() != "executive summary":
            fixed_body = _mark_background_knowledge_sentences(
                fixed_body,
                query=state.original_query,
                sources_define_term=False,
            )
            if not _has_ranked_source_citation(fixed_body, state.sources_checked):
                fixed_body = _salvage_inline_citations(
                    paragraph=fixed_body,
                    routed_findings=[],
                    routed_sources=state.sources_checked,
                    source_lookup=source_lookup,
                )

        normalized_title = fixed_title.lower()
        if normalized_title in seen_titles and normalized_title != "executive summary":
            continue
        seen_titles.add(normalized_title)

        repaired.append(f"## {fixed_title}")
        repaired.append(fixed_body)
        repaired.append("")

    return "\n".join(repaired).strip()


def _definition_term_from_query(query: str) -> str:
    match = re.search(r"\bwhat\s+is\s+([^?,.]+)", query or "", re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).strip()


def _direct_answer_covers_definition(text: str, query: str) -> bool:
    term = _definition_term_from_query(query)
    if not term:
        return True

    direct_answer = _extract_markdown_section(text, "Direct Answer").lower()
    term_lower = term.lower()
    if not direct_answer:
        return False
    if re.search(rf"\b{re.escape(term_lower)}\s+(?:is|stands for|refers to)\b", direct_answer):
        return True
    if term_lower == "lng" and "liquefied natural gas" in direct_answer:
        return True
    return False


def _find_definition_fact(term: str, sources: List[Source]) -> Tuple[str, str]:
    if not term:
        return "", ""

    term_pattern = re.escape(term.strip())
    for source in sources:
        text = source.content_snippet or source.content_full or ""
        if not text:
            continue
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        for sentence in sentences:
            lowered = sentence.lower()
            if not re.search(term_pattern, sentence, re.IGNORECASE):
                continue
            if " stands for " in lowered or " is " in lowered or " refers to " in lowered:
                return _normalize_sentence(sentence, max_chars=220), source.title or "Untitled Source"
    return "", ""


def _background_definition_fact(term: str) -> str:
    if not term:
        return ""
    return _BACKGROUND_TERM_DEFINITIONS.get(term.strip().lower(), "")


def _extractive_summarize(texts: List[str], query: str, max_sentences: int = 3) -> str:
    """Select the most query-relevant sentences from *texts* using TF-IDF
    cosine similarity.  Falls back to first *max_sentences* if scikit-learn
    is unavailable."""
    if not texts:
        return ""
    # Split each text into sentences and flatten
    import re as _re
    sentences: List[str] = []
    for t in texts:
        sentences.extend(s.strip() for s in _re.split(r'(?<=[.!?])\s+', t) if s.strip())
    if not sentences:
        return " ".join(texts[:max_sentences])
    # Score sentences by keyword overlap with query (no external deps)
    query_tokens = set(query.lower().split())
    scored = []
    for i, sent in enumerate(sentences):
        sent_tokens = set(sent.lower().split())
        overlap = len(query_tokens & sent_tokens)
        scored.append((overlap, i, sent))
    scored.sort(key=lambda x: (-x[0], x[1]))
    # Only include sentences with at least 1 query-term overlap
    selected = [s for overlap, _, s in scored[:max_sentences] if overlap > 0]
    if not selected:
        selected = [scored[0][2]]
    return " ".join(selected)


# Domain label → report section header mapping for diligence fallback
_DILIGENCE_DOMAIN_SECTIONS = {
    "commercial": "Tariff & Revenue",
    "licensing": "Regulatory & Licensing",
    "environmental": "Environmental & Grid Connection",
    "performance": "Performance",
    "counterparty": "Vendor & Counterparty",
    "asset_specific": "Asset Intelligence",
}

_DILIGENCE_SECTION_QUESTIONS = {
    "commercial": (
        "What are the specific electricity tariff rates, PPA terms, and feed-in tariff "
        "structures in {country}? Estimate annual revenue for a {capacity_mw}MW "
        "{technology} plant using the local data context."
    ),
    "licensing": (
        "What specific permits, licenses, and regulatory approvals are required to "
        "develop and operate a {technology} power plant in {country}? Identify the "
        "regulator and licensing process."
    ),
    "environmental": (
        "What environmental impact assessment requirements and grid connection "
        "procedures apply to a {capacity_mw}MW {technology} plant in {country}?"
    ),
    "performance": (
        "What are measured capacity factors and performance ratios for operational "
        "{technology} plants in {country} or comparable markets? How does this asset "
        "compare to the benchmark?"
    ),
    "counterparty": (
        "Who are the key counterparties — offtaker, grid operator, developer — "
        "and what is their track record in {country}?"
    ),
    "asset_specific": (
        "What is known about {name} specifically — ownership changes, financing, "
        "operational history, recent news?"
    ),
}


# --- BESS-specific domain mappings ---

_BESS_DOMAIN_SECTIONS = {
    "revenue_model": "Revenue Model",
    "grid_connection": "Grid Connection",
    "tariff_charging": "Tariff & Charging Cost",
    "regulatory_licensing": "Regulatory & Licensing",
    "market_structure": "Market Structure",
    "risk_assessment": "Risk Assessment",
}

_BESS_SECTION_QUESTIONS = {
    "revenue_model": (
        "What is the bankable annual revenue from DAM arbitrage, TOU arbitrage, "
        "and peaker displacement for a {capacity_mw}MW BESS in {country}? "
        "What are the peak-offpeak price differentials and how many arbitrage "
        "cycles per day are feasible?"
    ),
    "grid_connection": (
        "What substation, voltage level, and transmission zone would serve a "
        "{capacity_mw}MW BESS in {country}? What are the grid connection "
        "requirements and typical timeline?"
    ),
    "tariff_charging": (
        "What does it cost to charge a BESS under the applicable Eskom tariff "
        "schedule in {country}? What are the seasonal TOU rate differentials "
        "(high demand Jun-Aug vs low demand Sep-May) for peak, standard, and "
        "off-peak periods?"
    ),
    "regulatory_licensing": (
        "What NERSA licensing requirements apply to battery energy storage in "
        "{country}? What grid code compliance is needed for BESS? Are there "
        "storage-specific regulatory frameworks or is storage treated as "
        "generation?"
    ),
    "market_structure": (
        "How does the SAPP Day-Ahead Market work for storage dispatch in "
        "{country}? What is the DAM trading volume and liquidity? Are bilateral "
        "PPAs or cross-border trading viable alternatives?"
    ),
    "risk_assessment": (
        "What are the key investment risks for BESS in {country}? Consider "
        "ZAR/USD currency exposure, Eskom tariff escalation trajectory, "
        "competing storage projects in pipeline, demand growth outlook, "
        "and battery technology obsolescence risk."
    ),
}

_BESS_ANALYST_SYSTEM_PROMPT = (
    "You are a senior battery energy storage investment analyst specializing in "
    "storage dispatch optimization and arbitrage revenue modeling in Southern "
    "African power markets. You produce structured investment memos for BESS "
    "projects, quantifying arbitrage spreads, TOU differentials, and grid "
    "services revenue. For each section, synthesize domain-specific sources, "
    "quantify where data permits, flag material risks and unanswered questions, "
    "and cite inline using exact source titles in square brackets. "
    "Do not produce planning steps, meta commentary, or procedural narration."
)


def generate_bess_diligence_charts(
    asset_metadata: dict,
    diligence_context: str = "",
) -> list:
    """Generate BESS-specific diligence charts as base64-encoded PNGs.

    Returns list of (section_title, data_uri) tuples:
    1. 24h DAM Price Profile with peak/offpeak shading
    2. Monthly Arbitrage Revenue Estimate (low/mid/high)
    3. Eskom TOU Tariff Waterfall by season
    """
    import base64 as b64mod
    import io

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available for BESS charts")
        return []

    charts = []
    country = (asset_metadata.get("country") or "South Africa").strip()

    # --- Chart 1: 24h DAM Price Profile ---
    try:
        from tools.imaging.grid_metrics import classify_peak_hours
        from tools.market.sapp_client import parse_all_dam_files

        dam_data = parse_all_dam_files()
        # Pick node based on country
        if "zimbabwe" in country.lower():
            node = "zim"
        else:
            node = "rsan"  # default to RSAN for SA
        usd_obs = dam_data.get(node, {}).get("usd", [])

        if usd_obs:
            hourly_sums: dict[int, list[float]] = {h: [] for h in range(24)}
            for dt_str, price in usd_obs:
                try:
                    hour = int(dt_str[11:13])
                    hourly_sums[hour].append(price)
                except (ValueError, IndexError):
                    continue

            hours = list(range(24))
            avg_prices = [
                sum(hourly_sums[h]) / len(hourly_sums[h]) if hourly_sums[h] else 0
                for h in hours
            ]

            fig, ax = plt.subplots(figsize=(9, 4.5))
            # Peak shading
            for h in hours:
                if classify_peak_hours(h) == "peak":
                    ax.axvspan(h - 0.5, h + 0.5, alpha=0.12, color="#dc2626")
            ax.plot(hours, avg_prices, color="#2563eb", linewidth=2, marker="o", markersize=4)
            ax.fill_between(hours, avg_prices, alpha=0.15, color="#2563eb")
            ax.set_xlabel("Hour of Day")
            ax.set_ylabel("Avg Price (USD/MWh)")
            ax.set_title(f"SAPP DAM 24h Price Profile — {node.upper()}")
            ax.set_xticks(range(0, 24, 2))
            ax.grid(True, alpha=0.3)
            # Add peak label
            ax.text(7, max(avg_prices) * 0.95, "Peak", color="#dc2626",
                    fontsize=8, ha="center", fontweight="bold")
            ax.text(18, max(avg_prices) * 0.95, "Peak", color="#dc2626",
                    fontsize=8, ha="center", fontweight="bold")
            fig.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=100)
            plt.close(fig)
            buf.seek(0)
            b64_str = b64mod.b64encode(buf.read()).decode("ascii")
            charts.append(("SAPP DAM 24h Price Profile", f"data:image/png;base64,{b64_str}"))
    except Exception as exc:
        logger.warning("DAM price profile chart failed: %s", exc)

    # --- Chart 2: Arbitrage Revenue Estimate ---
    try:
        from tools.imaging.grid_metrics import compute_node_price_stats
        from tools.market.sapp_client import parse_all_dam_files

        if not dam_data:
            dam_data = parse_all_dam_files()
        stats = compute_node_price_stats(dam_data)
        node_stat = stats.get(node, {})
        spread = node_stat.get("arbitrage_spread_usd", 0)

        if spread > 0:
            # Estimate: cycles/day * spread * capacity * days/month * RTE
            cycles_per_day = [1, 1.5, 2]  # low/mid/high
            rte = 0.85
            capacity_mw = float(asset_metadata.get("capacity_mw", 100) or 100)
            duration_h = 4  # 4-hour BESS

            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            # High season: Jun-Aug, Low season: Sep-May
            high_season = {5, 6, 7}  # 0-indexed months
            days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
            season_mult = [1.3 if m in high_season else 1.0 for m in range(12)]

            fig, ax = plt.subplots(figsize=(10, 4.5))
            x = range(12)
            width = 0.25
            labels = ["Conservative", "Base", "Optimistic"]
            colors = ["#94a3b8", "#3b82f6", "#22c55e"]

            for i, (cpd, label, color) in enumerate(zip(cycles_per_day, labels, colors)):
                rev = [
                    cpd * spread * capacity_mw * duration_h * rte * days_per_month[m]
                    * season_mult[m] / 1000
                    for m in range(12)
                ]
                bars = ax.bar([xi + i * width for xi in x], rev, width,
                              label=label, color=color)

            ax.set_ylabel("Revenue ($k/month)")
            ax.set_title(f"Monthly Arbitrage Revenue — {capacity_mw:.0f} MW / {duration_h}h BESS")
            ax.set_xticks([xi + width for xi in x])
            ax.set_xticklabels(months, fontsize=8)
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3, axis="y")
            fig.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=100)
            plt.close(fig)
            buf.seek(0)
            b64_str = b64mod.b64encode(buf.read()).decode("ascii")
            charts.append(("Monthly Arbitrage Revenue Estimate", f"data:image/png;base64,{b64_str}"))
    except Exception as exc:
        logger.warning("Arbitrage revenue chart failed: %s", exc)

    # --- Chart 3: Eskom TOU Tariff Waterfall ---
    try:
        from tools.regulatory.eskom_tariff_client import get_rate

        periods = ["Peak", "Standard", "Off-Peak"]
        seasons = [("High Demand\n(Jun-Aug)", "high"), ("Low Demand\n(Sep-May)", "low")]
        rate_values = []
        bar_labels = []
        bar_colors = []
        period_colors = {"Peak": "#dc2626", "Standard": "#f59e0b", "Off-Peak": "#22c55e"}

        for season_label, season_key in seasons:
            for period in periods:
                rate = get_rate("Megaflex", tx_zone=0, voltage=1,
                                season=season_key, period=period.lower().replace("-", ""))
                rate_values.append(rate or 0)
                bar_labels.append(f"{period}\n{season_label}")
                bar_colors.append(period_colors[period])

        fig, ax = plt.subplots(figsize=(10, 4.5))
        bars = ax.bar(range(len(rate_values)), rate_values, color=bar_colors)
        ax.set_ylabel("Rate (c/kWh excl VAT)")
        ax.set_title("Eskom Megaflex TOU Tariff Schedule 2025/26")
        ax.set_xticks(range(len(bar_labels)))
        ax.set_xticklabels(bar_labels, fontsize=7, ha="center")
        ax.grid(True, alpha=0.3, axis="y")
        for bar, val in zip(bars, rate_values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
                    f"{val:.0f}", ha="center", va="bottom", fontsize=8)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100)
        plt.close(fig)
        buf.seek(0)
        b64_str = b64mod.b64encode(buf.read()).decode("ascii")
        charts.append(("Eskom TOU Tariff Waterfall", f"data:image/png;base64,{b64_str}"))
    except Exception as exc:
        logger.warning("Tariff waterfall chart failed: %s", exc)

    return charts


def _format_sources_by_domain(sources: List[Source]) -> dict:
    """Group sources by intent_domain and format each group.

    Returns ``{domain_key: formatted_text}``.  Sources with empty/missing
    ``intent_domain`` are placed under ``"other"``.
    """
    domain_buckets: dict[str, List[Source]] = {}
    for s in sources:
        key = s.intent_domain or "other"
        domain_buckets.setdefault(key, []).append(s)

    result = {}
    for domain_key, bucket in domain_buckets.items():
        result[domain_key] = _format_direct_sources_for_prompt(bucket)
    return result


def _deterministic_diligence_synthesis(state: ResearchState, asset_metadata: Optional[dict] = None) -> str:
    """Structured diligence fallback when the LLM is unavailable.

    Groups sources by ``intent_domain``, produces extractive summaries per
    domain section, and assembles a report with the fixed diligence headers.
    """
    meta = asset_metadata or {}
    query = state.original_query or ""
    sources = state.sources_checked or []

    # Group sources by domain
    domain_sources: dict[str, List[Source]] = {}
    for s in sources:
        domain = s.intent_domain or "other"
        domain_sources.setdefault(domain, []).append(s)

    sections: List[str] = []

    # Executive Summary
    n_sources = len(sources)
    domains_found = [d for d in _DILIGENCE_DOMAIN_SECTIONS if d in domain_sources]
    exec_summary = (
        f"Deterministic diligence report for {meta.get('name', 'the target asset')} "
        f"({meta.get('technology', 'power')}, {meta.get('country', 'unknown country')}). "
        f"Based on {n_sources} source(s) across {len(domains_found)} domain(s). "
        f"LLM synthesis was unavailable; content below is extracted directly from sources."
    )
    sections.append(f"## Executive Summary\n{exec_summary}")

    # Domain sections
    for domain_key, section_title in _DILIGENCE_DOMAIN_SECTIONS.items():
        ds = domain_sources.get(domain_key, [])
        if not ds:
            sections.append(f"## {section_title}\nNo sources found for this domain.")
            continue
        texts = [s.content_full or s.content_snippet for s in ds if (s.content_full or s.content_snippet)]
        titles = [s.title or "Untitled" for s in ds]
        summary = _extractive_summarize(texts, query, max_sentences=4)
        citations = ", ".join(f"[{t}]" for t in titles[:3])
        sections.append(f"## {section_title}\n{summary}\n\n*Sources: {citations}*")

    # Risk Summary
    sections.append(
        "## Risk Summary & Recommendation\n"
        "Unable to generate risk assessment without LLM synthesis. "
        "Review the domain sections above for key findings."
    )

    synthesis = "\n\n".join(sections)
    state.synthesis = synthesis
    state.synthesis_model = "deterministic_diligence"
    return synthesis


def _deterministic_direct_synthesis(state: ResearchState, reason: str) -> str:
    """Question-answer-oriented deterministic fallback for direct synthesis."""
    ranked_sources = _summary_candidate_sources(state)
    if not ranked_sources:
        ranked_sources = sorted(
            state.sources_checked,
            key=lambda s: ((s.relevance_score or 0.0), (s.credibility_score or 0.0)),
            reverse=True,
        )
    top_sources = ranked_sources[:5]

    if not top_sources:
        return _deterministic_evidence_synthesis(state, reason=reason)

    direct_points: List[str] = []
    seen = set()

    term = _definition_term_from_query(state.original_query)
    definition_fact, definition_title = _find_definition_fact(term, state.sources_checked or top_sources)
    if definition_fact and definition_title:
        sentence = f"{definition_fact.rstrip('.')} [{definition_title}]."
        direct_points.append(sentence)
        seen.add(sentence)
    else:
        background_definition = _background_definition_fact(term)
        if background_definition:
            sentence = f"[Background Knowledge] {background_definition.rstrip('.')}."
            direct_points.append(sentence)
            seen.add(sentence)

    for source in top_sources:
        fact = _extract_source_fact(source, max_chars=220)
        title = source.title or "Untitled Source"
        if not fact:
            continue
        sentence = f"{fact.rstrip('.')} [{title}]."
        if sentence in seen:
            continue
        seen.add(sentence)
        direct_points.append(sentence)
        if len(direct_points) >= 3:
            break

    if not direct_points:
        return _deterministic_evidence_synthesis(state, reason=reason)

    summary = _truncate_to_words(" ".join(direct_points[:2]), max_words=75)
    if term:
        direct_answer = _truncate_to_words(" ".join(direct_points[:3]), max_words=150)
    else:
        question_text = (state.original_query or "the research question").strip().rstrip("?")
        answer_intro = f"On the question of {question_text.lower()}, the strongest retrieved evidence indicates:"
        direct_answer = _truncate_to_words(
            f"{answer_intro} {' '.join(direct_points[:3])}",
            max_words=150,
        )
    evidence_text = _truncate_to_words(" ".join(direct_points), max_words=180)
    confidence_text = (
        f"Confidence is limited by the quality and topical fit of {len(state.sources_checked)} retrieved sources; "
        "this fallback answers the question directly from the strongest cited facts, without uncited extrapolation."
    )

    synthesis = "\n".join([
        "## Executive Summary",
        summary,
        "",
        "## Direct Answer",
        direct_answer,
        "",
        "## Supporting Evidence",
        evidence_text,
        "",
        "## Confidence and Gaps",
        _normalize_sentence(confidence_text, max_chars=260),
    ])
    state.synthesis = synthesis
    state.synthesis_model = "deterministic"
    return synthesis


def synthesize_direct(
    state: ResearchState,
    market_context: str = "",
    progress_callback=None,
    asset_metadata: Optional[dict] = None,
    diligence_context: str = "",
) -> str:
    """Single-pass synthesis that answers the original research question directly."""
    logger.info("Synthesizing ranked sources (direct-answer pipeline)...")
    _emit_progress(progress_callback, "synthesis", "Preparing direct answer from ranked sources...")

    is_diligence = state.research_type == "diligence" and asset_metadata
    if is_diligence:
        prompt = _build_diligence_synthesis_prompt_v2(
            state, diligence_context=diligence_context, asset_metadata=asset_metadata,
        )
        system_prompt = _DILIGENCE_ANALYST_SYSTEM_PROMPT
    else:
        prompt = _build_direct_synthesis_prompt(state, market_context=market_context)
        system_prompt = _DIRECT_RESEARCH_ANALYST_SYSTEM_PROMPT

    try:
        raw = _call_research_synthesis_model(prompt, system_prompt=system_prompt)
    except Exception as exc:
        logger.error("Direct synthesis failed: %s", exc)
        raw = None

    if not raw:
        logger.warning("Direct synthesis returned empty output; using deterministic fallback")
        if is_diligence:
            return _deterministic_diligence_synthesis(state, asset_metadata=asset_metadata)
        return _deterministic_direct_synthesis(state, reason="direct_synthesis_unavailable")

    normalized = _normalize_outline_headers(raw).strip()
    normalized = _normalize_direct_citation_labels(normalized)
    if is_diligence:
        normalized = _repair_diligence_synthesis_output(normalized, state)
    else:
        normalized = _repair_direct_synthesis_output(normalized, state)
    executive_summary = _extract_markdown_section(normalized, "Executive Summary")
    if executive_summary and _summary_needs_rewrite(executive_summary):
        normalized = _replace_markdown_section(
            normalized,
            "Executive Summary",
            _deterministic_executive_summary(state),
        )

    _quality_gate = _passes_diligence_quality_gate if is_diligence else _passes_direct_synthesis_quality_gate
    if not _quality_gate(normalized, state):
        retry_prompt = _build_direct_synthesis_retry_prompt(
            base_prompt=prompt,
            rejected_output=normalized,
            failure_reason="direct_synthesis_quality_failure",
        )
        retry_raw = _call_research_synthesis_model(retry_prompt, system_prompt=system_prompt)
        if retry_raw:
            normalized = _normalize_outline_headers(retry_raw).strip()
            normalized = _normalize_direct_citation_labels(normalized)
            if is_diligence:
                normalized = _repair_diligence_synthesis_output(normalized, state)
            else:
                normalized = _repair_direct_synthesis_output(normalized, state)
            executive_summary = _extract_markdown_section(normalized, "Executive Summary")
            if executive_summary and _summary_needs_rewrite(executive_summary):
                normalized = _replace_markdown_section(
                    normalized,
                    "Executive Summary",
                    _deterministic_executive_summary(state),
                )

    if not _quality_gate(normalized, state):
        logger.warning("Direct synthesis failed quality gate after retry; using deterministic fallback")
        if is_diligence:
            return _deterministic_diligence_synthesis(state, asset_metadata=asset_metadata)
        return _deterministic_direct_synthesis(state, reason="direct_synthesis_quality_failure")

    # Insert diligence charts into the appropriate sections
    if is_diligence:
        try:
            charts = generate_diligence_charts(asset_metadata, diligence_context)
            for chart_title, data_uri in charts:
                img_md = f"\n\n![{chart_title}]({data_uri})\n"
                if "Revenue" in chart_title:
                    normalized = _insert_after_section(normalized, "Tariff & Revenue", img_md)
                elif "Benchmark" in chart_title or "Capacity" in chart_title:
                    normalized = _insert_after_section(normalized, "Performance Gap Analysis", img_md)
        except Exception as exc:
            logger.warning("Diligence chart insertion failed (non-fatal): %s", exc)

    state.synthesis = normalized
    state.synthesis_model = "direct"
    return normalized


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
