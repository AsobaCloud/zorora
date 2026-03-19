"""Shared deep research execution service for REPL and Web UI."""

from __future__ import annotations

import logging
import re
import threading
import time
import inspect
from datetime import date, datetime
from typing import Callable, List, Optional

import config
from engine.models import ResearchState, Source, Finding
from engine.query_refiner import SearchIntent, decompose_query, decompose_diligence_query
from workflows.deep_research.aggregator import aggregate_sources
from workflows.deep_research.credibility import score_source_credibility
from workflows.deep_research.reranker import score_relevance, filter_relevant, _count_cross_references
from workflows.deep_research.synthesizer import synthesize_direct


logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str, str], None]

# Backward-compat hook for existing tests: the shared service now routes
# through direct synthesis, but callers may still patch `synthesize`.
synthesize = synthesize_direct

_CLUSTERING_SYSTEM_PROMPT = (
    "You are a senior energy and electricity market intelligence analyst. "
    "Extract concise, evidence-grounded thematic findings from source records only. "
    "Avoid generic framing, planning language, and report boilerplate. "
    "Each finding must be specific, factual, and tied to listed source IDs."
)

_GENERIC_FINDING_PATTERNS = [
    re.compile(r"\bthe following (?:thematic )?findings\b", re.IGNORECASE),
    re.compile(r"\bprovided sources\b", re.IGNORECASE),
    re.compile(r"\bbased on the available evidence\b", re.IGNORECASE),
    re.compile(r"\bthis analysis\b", re.IGNORECASE),
    re.compile(r"\bto address the question\b", re.IGNORECASE),
]
_QUERY_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for",
    "from", "with", "by", "as", "is", "are", "was", "were", "be",
    "been", "being", "that", "this", "it", "its", "at", "into",
    "how", "what", "when", "where", "why", "which",
})


def _emit(progress_callback: Optional[ProgressCallback], phase: str, message: str, status: str = "running") -> None:
    """Emit progress update if callback is provided."""
    if progress_callback:
        progress_callback(status, phase, message)


def _build_diligence_context(asset_metadata: dict) -> tuple:
    """Build diligence context from local regulatory/imaging databases.

    Returns (context_text, raw_data_dict) for synthesis and chart generation.
    """
    country = asset_metadata.get("country", "")
    technology = asset_metadata.get("technology", "")
    state_code = asset_metadata.get("state", "")
    sections = []
    raw_data = {}

    try:
        from tools.regulatory.store import RegulatoryDataStore
        reg_store = RegulatoryDataStore()

        if state_code or country == "United States":
            eia_retail = reg_store.get_eia_series("retail-sales", state=state_code or None)
            if eia_retail:
                raw_data["eia_retail"] = eia_retail[:10]
                prices = [r.get("value") for r in eia_retail[:5] if r.get("value")]
                sections.append(f"EIA Retail Electricity Prices ({state_code or 'US'}): {prices}")

            utility_rates = reg_store.get_utility_rates(state=state_code or None, sector="commercial")
            if utility_rates:
                raw_data["utility_rates"] = utility_rates[:10]
                rate_names = [r.get("utility_name", "") for r in utility_rates[:5]]
                sections.append(f"Utility Rates ({state_code or 'US'}, commercial): {rate_names}")

            tech_map = {"Solar": "solar", "Wind": "wind", "Coal": "coal", "Gas": "gas"}
            fuel = tech_map.get(technology, "")
            eia_capacity = reg_store.get_eia_series(
                "operating-generator-capacity", state=state_code or None, fuel_type=fuel or None
            )
            if eia_capacity:
                raw_data["eia_capacity"] = eia_capacity[:10]
                caps = [r.get("value") for r in eia_capacity[:5] if r.get("value")]
                sections.append(f"EIA Operating Capacity ({technology}, {state_code or 'US'}): {caps}")

            rps = reg_store.get_rps_targets(state=state_code or None)
            if rps:
                raw_data["rps_targets"] = rps[:10]
                targets = [(r.get("year"), r.get("target_pct")) for r in rps[:5]]
                sections.append(f"RPS Targets ({state_code or 'US'}): {targets}")

            reg_events = reg_store.get_regulatory_events(jurisdiction=state_code or country or None, limit=5)
            if reg_events:
                raw_data["regulatory_events"] = reg_events
                titles = [r.get("title", r.get("event_type", "")) for r in reg_events[:3]]
                sections.append(f"Recent Regulatory Events: {titles}")
    except Exception as exc:
        logger.warning("Regulatory data fetch for diligence failed (non-fatal): %s", exc)

    try:
        from tools.imaging.store import ImagingDataStore
        img_store = ImagingDataStore()
        comparable = img_store.get_generation_assets(technology=technology or None, country=country or None)
        features = comparable.get("features", []) if isinstance(comparable, dict) else []
        if features:
            raw_data["comparable_plants"] = features[:20]
            capacities = [
                f.get("properties", {}).get("capacity_mw", 0)
                for f in features[:20]
                if f.get("properties", {}).get("capacity_mw")
            ]
            sections.append(f"Comparable {technology} Plants in {country}: {len(features)} found, capacities (MW): {capacities[:10]}")
    except Exception as exc:
        logger.warning("Imaging data fetch for diligence failed (non-fatal): %s", exc)

    if not sections and country and country != "United States":
        try:
            from tools.market.worldbank_client import WorldBankClient
            wb = WorldBankClient()
            elec_price = wb.fetch_indicator("EG.ELC.PETR.ZS", country=country)
            if elec_price:
                raw_data["worldbank_electricity"] = elec_price[:5]
                sections.append(f"World Bank Electricity Data ({country}): {len(elec_price)} records")
        except Exception as exc:
            logger.warning("World Bank fetch for diligence failed (non-fatal): %s", exc)

    if not sections:
        return "No local diligence data available for this asset.", raw_data

    return "\n".join(sections), raw_data


def _build_market_context_for_query(query: str) -> str:
    """Build optional market context for market-oriented research queries."""
    try:
        from engine.query_refiner import detect_market_intent

        if not detect_market_intent(query):
            return ""

        logger.info("Market intent detected — injecting FRED context")
        from workflows.market_workflow import MarketWorkflow
        from tools.market.context import build_market_context

        workflow = MarketWorkflow()
        workflow.update_all()
        summaries = workflow.compute_summary()
        if summaries:
            return build_market_context(summaries)
    except Exception as exc:
        logger.warning("Market context build failed (non-fatal): %s", exc)

    return ""


def _query_terms(text: str) -> set:
    return {
        token
        for token in re.findall(r"[a-z0-9]{3,}", (text or "").lower())
        if token not in _QUERY_STOPWORDS
    }


def _is_generic_finding_claim(claim: str) -> bool:
    normalized = re.sub(r"\s+", " ", (claim or "").strip())
    if not normalized:
        return True
    return any(pattern.search(normalized) for pattern in _GENERIC_FINDING_PATTERNS)


def _call_clustering_model(prompt: str) -> Optional[str]:
    """Call reasoning endpoint with clustering-specific analyst instructions."""
    if not prompt or not prompt.strip():
        return None

    try:
        from tools.specialist.client import create_specialist_client

        model_config = config.SPECIALIZED_MODELS["reasoning"]
        client = create_specialist_client("reasoning", model_config)
        messages = [
            {"role": "system", "content": _CLUSTERING_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        response = client.chat_complete(messages, tools=None)
        content = client.extract_content(response)
        if content and str(content).strip():
            return str(content).strip()
        logger.warning("Clustering client returned empty content")
    except Exception as exc:
        logger.warning("Clustering client failed, trying tool fallback: %s", exc)

    try:
        from tools.registry import TOOL_FUNCTIONS

        use_reasoning = TOOL_FUNCTIONS.get("use_reasoning_model")
        if use_reasoning:
            raw = use_reasoning(prompt)
            if raw and not raw.startswith("Error:"):
                return raw.strip()
    except Exception as exc:
        logger.warning("Clustering tool fallback failed: %s", exc)

    return None


def _rank_findings(findings: List[Finding]) -> List[Finding]:
    """Rank findings by support breadth and confidence for synthesis routing."""
    confidence_rank = {"high": 3, "medium": 2, "low": 1}
    ranked = sorted(
        findings,
        key=lambda f: (
            len(f.sources),
            confidence_rank.get((f.confidence or "").lower(), 1),
            float(f.average_credibility or 0.0),
            len(_query_terms(f.claim)),
        ),
        reverse=True,
    )
    return ranked


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
_PROSE_SUBSTRINGS = (
    "query can be decomposed",
    "decompose this research query",
    "distinct sub-topic",
    "as follows",
    "return only the queries",
    "one per line",
    "no numbering or explanation",
)
_QUERY_STOPWORDS = frozenset({
    "what", "why", "how", "when", "where", "who", "which", "whose",
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
    "is", "was", "were", "are", "be", "been", "being", "do", "does", "did",
    "with", "from", "about", "that", "this", "it", "not", "as", "by",
    "query", "research", "search", "sub", "topic", "topics", "distinct",
    "decompose", "decomposed", "follows", "line", "lines", "return", "only",
    "please", "given", "into", "two", "three",
})
_GENERIC_QUERY_TERMS = frozenset({
    "market", "markets", "trend", "trends", "analysis", "data", "recent",
    "latest", "global", "sector", "sectors", "price", "prices", "outlook",
    "impact", "changes", "change", "history", "historical",
})


def _query_terms(text: str) -> set:
    """Extract normalized query terms for overlap checks."""
    return {
        token
        for token in re.findall(r"[a-z0-9]{3,}", (text or "").lower())
        if token not in _QUERY_STOPWORDS
    }


def _is_topically_related_variant(candidate: str, base_query: str) -> bool:
    """Keep decomposition variants tied to the original query topic."""
    candidate_terms = _query_terms(candidate)
    base_terms = _query_terms(base_query)
    if not candidate_terms or not base_terms:
        return False

    shared = candidate_terms & base_terms
    if len(shared) >= 2:
        return True

    if len(shared) == 1:
        only = next(iter(shared))
        # A single highly generic overlap is usually noise.
        if only in _GENERIC_QUERY_TERMS:
            return False
        # For short queries, one specific overlap (e.g., "lithium") is still useful.
        if len(base_terms) <= 5:
            return True

    return False


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
    lowered = cleaned.lower()
    if any(fragment in lowered for fragment in _PROSE_SUBSTRINGS):
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
                f"(e.g., supply chain, market trends, data analysis, regional impact). "
                f"Return ONLY the queries, one per line, no numbering or explanation.\n\n"
                f"Query: {query}"
            )
            result = use_reasoning(prompt)
            if result and not result.startswith("Error:"):
                raw_lines = result.strip().split("\n")
                lines = []
                for raw in raw_lines:
                    cleaned = _clean_query_line(raw)
                    if cleaned and _is_topically_related_variant(cleaned, query):
                        lines.append(cleaned)
                # Preserve order, remove duplicates.
                deduped_lines = []
                seen = set()
                for line in lines:
                    key = line.lower()
                    if key not in seen:
                        seen.add(key)
                        deduped_lines.append(line)
                lines = deduped_lines
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
        "recent developments data analysis",
        "market trends supply demand outlook",
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
        result = _call_clustering_model(prompt)
        logger.debug(f"Clustering raw output (first 500 chars): {(result or '')[:500]}")
        if not result:
            logger.warning(f"Clustering model returned empty/error — falling back to 1:1 mapping for {len(sources)} sources")
            return _fallback_findings(sources)

        findings = _parse_clustered_findings(result, sources, query=query)
        if findings:
            ranked = _rank_findings(findings)
            max_findings = config.SYNTHESIS.get("max_findings", 15)
            ranked = ranked[:max_findings]
            logger.info(f"Clustered {len(sources)} sources into {len(ranked)} thematic findings")
            return ranked

    except Exception as e:
        logger.warning(f"Finding clustering failed, falling back to 1:1 mapping: {e}")

    return _fallback_findings(sources)


def _parse_clustered_findings(text: str, sources: List[Source], query: Optional[str] = None) -> List[Finding]:
    """Parse FINDING/SOURCES/CONFIDENCE blocks from reasoning model output."""
    findings = []
    query_terms = _query_terms(query or "")
    source_count = max(len(sources), 1)

    # Normalize common model formatting variants:
    # - **FINDING:** -> FINDING:
    # - Finding:/Sources:/Confidence: -> uppercase labels
    normalized = re.sub(r"\*\*\s*(FINDING|SOURCES|CONFIDENCE)\s*:\s*\*\*", r"\1:", text, flags=re.IGNORECASE)
    normalized = re.sub(r"(?im)^\s*finding\s*:", "FINDING:", normalized)
    normalized = re.sub(r"(?im)^\s*sources\s*:", "SOURCES:", normalized)
    normalized = re.sub(r"(?im)^\s*confidence\s*:", "CONFIDENCE:", normalized)

    blocks = re.split(r"(?=FINDING:)", normalized)

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
        if _is_generic_finding_claim(claim):
            continue

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
        if source_count >= 4 and len(source_ids) >= source_count:
            logger.warning("Skipping finding citing all %d sources: %s", source_count, claim[:80])
            continue

        if query_terms:
            claim_terms = _query_terms(claim)
            overlap = claim_terms & query_terms
            if len(overlap) < 2:
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
    """Fallback: build concise source-backed findings when clustering fails."""
    low_signal = (
        "welcome gift package",
        "download now",
        "fear and greed index",
        "claim now",
        "app store",
        "google play",
    )
    findings = []
    for source in sources:
        title = (source.title or "").strip()
        snippet = (source.content_snippet or "").strip()
        claim_parts = [part for part in [title, snippet] if part]
        claim = ". ".join(claim_parts)
        claim = re.sub(r"\s+", " ", claim).strip()
        if len(claim) > 320:
            claim = claim[:317].rstrip() + "..."

        lowered = claim.lower()
        if not claim or any(token in lowered for token in low_signal):
            continue

        findings.append(Finding(
            claim=claim,
            sources=[source.source_id],
            confidence="low",
            average_credibility=source.credibility_score,
        ))

    if findings:
        return findings

    # Absolute fallback if all snippets were empty/noisy.
    for source in sources:
        claim = (source.title or "").strip()
        if claim:
            findings.append(Finding(
                claim=claim[:220],
                sources=[source.source_id],
                confidence="low",
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


def _extract_extra_keywords(base_query: str, variants: List[str]) -> List[str]:
    """Collect supplemental keywords from generated variants."""
    base_terms = set(re.findall(r"[a-z0-9]{2,}", base_query.lower()))
    extra_terms = set()
    for variant in variants[1:]:
        for term in re.findall(r"[a-z0-9]{2,}", (variant or "").lower()):
            if term not in base_terms:
                extra_terms.add(term)
    return list(extra_terms)


def _init_research_state(
    original_query: str,
    depth: int,
    refined_query: Optional[str],
    research_type: Optional[str],
    compare_subjects: Optional[List[str]],
    state_cls=ResearchState,
):
    """Build ResearchState with signature-compatible kwargs.

    This keeps the shared deep-research path resilient if a running process
    still has a legacy ResearchState constructor (e.g., no refined_query arg).
    """
    kwargs = {
        "original_query": original_query,
        "refined_query": refined_query,
        "research_type": research_type,
        "compare_subjects": list(compare_subjects or []),
        "max_depth": depth,
        "max_iterations": 1,
    }

    try:
        accepted = set(inspect.signature(state_cls).parameters.keys())
    except (TypeError, ValueError):
        accepted = set(kwargs.keys())

    filtered = {k: v for k, v in kwargs.items() if k in accepted}

    try:
        return state_cls(**filtered)
    except TypeError as exc:
        legacy = {k: kwargs[k] for k in ("original_query", "max_depth", "max_iterations")}
        logger.warning(
            "ResearchState signature mismatch (%s); falling back to legacy kwargs",
            exc,
        )
        return state_cls(**legacy)


def _score_and_filter_intent_sources(
    intent_query: str,
    sources: List[Source],
    variants: List[str],
    max_sources: int,
    relevance_min: float,
) -> List[Source]:
    """Run relevance scoring/filtering for one intent, then enforce topical gate."""
    extra_keywords = _extract_extra_keywords(intent_query, variants)
    scored_sources = score_relevance(intent_query, sources, extra_keywords=extra_keywords)
    filtered_sources = filter_relevant(scored_sources, min_score=relevance_min, max_sources=max_sources)

    # Service-level topical gate: enforce a stricter floor before synthesis.
    if not filtered_sources:
        return []

    strict_min = max(relevance_min, float(config.SYNTHESIS.get("service_topical_min_score", 0.25)))
    topical = [
        source
        for source in filtered_sources
        if (source.relevance_score or 0.0) >= strict_min
    ]
    if not topical:
        logger.info(
            "Topical gate dropped %d sources below %.2f for intent '%s'",
            len(filtered_sources),
            strict_min,
            intent_query[:80],
        )
        return []

    topical.sort(
        key=lambda s: (
            s.relevance_score or 0.0,
            s.credibility_score or 0.0,
        ),
        reverse=True,
    )
    return topical[:max_sources]


def run_deep_research(
    query: str,
    depth: int = 1,
    max_results_per_source: int = 10,
    progress_callback: Optional[ProgressCallback] = None,
    refined_query: Optional[str] = None,
    research_type: Optional[str] = None,
    compare_subjects: Optional[List[str]] = None,
    asset_metadata: Optional[dict] = None,
) -> ResearchState:
    """Execute the shared deep-research pipeline and return populated state."""
    # Use refined query for search/analysis when available
    search_query = refined_query or query

    # Look up depth profile
    profile = config.DEPTH_PROFILES.get(depth, config.DEPTH_PROFILES[1])
    effective_max_per_source = profile["max_results_per_source"]
    include_brave_news = profile["include_brave_news"]
    num_variants = profile["query_variants"]

    state = _init_research_state(
        original_query=query,
        depth=depth,
        refined_query=refined_query,
        research_type=research_type,
        compare_subjects=compare_subjects,
    )
    if asset_metadata:
        state.asset_metadata = asset_metadata

    is_diligence = research_type == "diligence" and asset_metadata
    if is_diligence:
        tech = (asset_metadata.get("technology") or "").lower()
        if tech in ("storage", "bess", "battery"):
            from engine.query_refiner import decompose_bess_diligence_query
            intents = decompose_bess_diligence_query(search_query, asset_metadata)
        else:
            intents = decompose_diligence_query(search_query, asset_metadata)
    else:
        intents = decompose_query(search_query)
    if not intents:
        intents = [SearchIntent(intent_query=search_query, parent_query=search_query, is_primary=True)]

    logger.info("Deep research depth=%d: %d intent(s) detected", depth, len(intents))

    max_sources = profile.get("max_sources", 25)
    relevance_min = config.SYNTHESIS.get("relevance_min_score", 0.15)
    merged_relevant_sources: List[Source] = []

    _US_COUNTRY_NAMES = {"united states", "us", "usa", "u.s.", "u.s.a."}
    is_us_asset = asset_metadata and asset_metadata.get("country", "").strip().lower() in _US_COUNTRY_NAMES
    force_policy_flag = bool(is_diligence and is_us_asset)
    suppress_policy_flag = bool(is_diligence and not is_us_asset)

    for intent_idx, intent in enumerate(intents, 1):
        intent_query = intent.intent_query.strip() or search_query
        effective_variants = 1 if is_diligence else num_variants
        variants = _generate_query_variants(intent_query, effective_variants)
        logger.info(
            "Intent %d/%d query variants: %d (%s)",
            intent_idx,
            len(intents),
            len(variants),
            intent_query[:80],
        )

        _emit(
            progress_callback,
            "aggregation",
            f"Intent {intent_idx}/{len(intents)}: searching with {len(variants)} query variant(s)...",
        )

        intent_raw_sources: List[Source] = []
        for variant_idx, variant in enumerate(variants, 1):
            _emit(
                progress_callback,
                "aggregation",
                f"Intent {intent_idx}/{len(intents)} query {variant_idx}/{len(variants)}: {variant[:60]}...",
            )
            variant_sources = aggregate_sources(
                variant,
                max_results_per_source=effective_max_per_source,
                include_brave_news=include_brave_news,
                force_policy=force_policy_flag,
                suppress_policy=suppress_policy_flag,
            )
            intent_raw_sources.extend(variant_sources)

        deduped_intent_sources = _deduplicate_sources(intent_raw_sources)
        logger.info(
            "Funnel: intent[%d] aggregation %d -> %d (dedup)",
            intent_idx,
            len(intent_raw_sources),
            len(deduped_intent_sources),
        )

        _emit(progress_callback, "relevance", f"Scoring relevance for intent {intent_idx}/{len(intents)}...")
        intent_relevant_sources = _score_and_filter_intent_sources(
            intent_query=intent_query,
            sources=deduped_intent_sources,
            variants=variants,
            max_sources=max_sources,
            relevance_min=relevance_min,
        )
        logger.info(
            "Funnel: intent[%d] relevance %d -> %d (min=%.2f)",
            intent_idx,
            len(deduped_intent_sources),
            len(intent_relevant_sources),
            relevance_min,
        )

        if is_diligence and intent.domain:
            for src in intent_relevant_sources:
                if not src.intent_domain:
                    src.intent_domain = intent.domain

        merged_relevant_sources.extend(intent_relevant_sources)

    # Deduplicate across intents and apply final source budget.
    unique_sources = _deduplicate_sources(merged_relevant_sources)
    unique_sources.sort(
        key=lambda s: (
            s.relevance_score or 0.0,
            s.credibility_score or 0.0,
        ),
        reverse=True,
    )
    unique_sources = unique_sources[:max_sources]
    logger.info(
        "Funnel: merged intents %d -> %d (dedup + budget=%d)",
        len(merged_relevant_sources),
        len(unique_sources),
        max_sources,
    )

    _emit(progress_callback, "credibility", f"Found {len(unique_sources)} relevant sources. Scoring credibility...")

    for i, source in enumerate(unique_sources):
        cross_ref_count = _count_cross_references(source, unique_sources)

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

    # Final deterministic ordering: relevance first, credibility second.
    state.sources_checked.sort(
        key=lambda s: (
            s.relevance_score or 0.0,
            s.credibility_score or 0.0,
        ),
        reverse=True,
    )
    state.total_sources = len(state.sources_checked)

    state.findings = []
    diligence_context = ""
    diligence_data = {}
    if is_diligence:
        diligence_context, diligence_data = _build_diligence_context(asset_metadata)
        market_context = ""
    else:
        market_context = _build_market_context_for_query(query)

    _emit(
        progress_callback,
        "cross_reference",
        f"Skipping finding clustering; sending {len(state.sources_checked)} ranked sources directly to synthesis.",
    )
    _emit(
        progress_callback,
        "synthesis",
        "Generating direct answer from ranked sources... This may take 15-25 seconds.",
    )

    synthesis_done = threading.Event()
    synthesis_start_time = time.time()

    def emit_heartbeat() -> None:
        heartbeat_count = 0
        messages = [
            "Analyzing ranked sources and answering the research question...",
            "Synthesizing evidence across the full ranked source set...",
            "Generating cited answer with structured sections...",
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
        state.synthesis = synthesize(
            state,
            market_context=market_context or diligence_context,
            progress_callback=progress_callback,
            asset_metadata=asset_metadata if is_diligence else None,
            diligence_context=diligence_context if is_diligence else "",
        )
        state.completed_at = datetime.now()
        state.current_iteration = 1
    finally:
        synthesis_done.set()
        heartbeat_thread.join(timeout=1)

    _emit(progress_callback, "complete", f"Research complete! Found {state.total_sources} sources.")
    return state


def build_results_payload(state: ResearchState, query: str, research_id: Optional[str] = None, max_sources: int = 25) -> dict:
    """Build API payload for web result rendering."""
    return {
        "research_id": research_id,
        "query": query,
        "refined_query": state.refined_query,
        "research_type": state.research_type,
        "compare_subjects": state.compare_subjects,
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
