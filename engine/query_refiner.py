"""Query refinement module for deep research.

Analyzes user queries to detect missing dimensions (time period, geography,
analysis type, scope) using rule-based keyword/regex matching, and returns
structured refinement suggestions with option pills for the UI.
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import config

logger = logging.getLogger(__name__)


@dataclass
class SearchIntent:
    """A decomposed search intent derived from a parent query."""

    intent_query: str
    parent_query: str
    is_primary: bool = False

# ---------------------------------------------------------------------------
# Keyword / regex definitions for each dimension
# ---------------------------------------------------------------------------

_TIME_PERIOD_PATTERN = re.compile(
    r"""
    \b(?:
        \d{4}(?:\s*[-–]\s*\d{4})?          # 2024, 2024-2025
      | Q[1-4]\s*\d{4}                      # Q1 2025
      | (?:last|past|recent|since|next)      # relative markers
        \s+\d*\s*(?:day|week|month|year|quarter)s?
      | this\s+(?:year|quarter|month|week)
      | current|latest|today|yesterday
      | (?:last|past)\s+(?:year|quarter|month|week|decade)
      | recent(?:ly)?
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

_GEOGRAPHIC_KEYWORDS = {
    # Continents
    "africa", "europe", "asia", "north america", "south america",
    "latin america", "oceania", "antarctica", "middle east",
    # Major regions / blocs
    "eu", "european union", "sadc", "apac", "asia-pacific",
    "asia pacific", "mena", "asean", "nafta", "usmca",
    "sub-saharan", "sub saharan", "east africa", "west africa",
    "southern africa", "north africa", "central africa",
    "southeast asia", "south asia", "east asia", "central asia",
    "western europe", "eastern europe", "northern europe",
    "southern europe", "caribbean", "pacific islands",
    # G20 countries
    "argentina", "australia", "brazil", "canada", "china", "france",
    "germany", "india", "indonesia", "italy", "japan", "mexico",
    "russia", "saudi arabia", "south africa", "south korea",
    "turkey", "turkiye", "united kingdom", "uk", "united states",
    "us", "usa", "america",
    # Additional notable countries
    "nigeria", "kenya", "egypt", "morocco", "ghana", "ethiopia",
    "tanzania", "rwanda", "zimbabwe", "zambia", "mozambique",
    "botswana", "namibia", "angola", "senegal", "uganda",
    "singapore", "malaysia", "thailand", "vietnam", "philippines",
    "new zealand", "colombia", "chile", "peru", "israel",
    "uae", "united arab emirates", "qatar", "kuwait",
    "norway", "sweden", "denmark", "finland", "switzerland",
    "netherlands", "belgium", "spain", "portugal", "poland",
    "czech republic", "austria", "ireland", "scotland", "wales",
    # Generic terms
    "global", "worldwide", "international", "domestic", "regional",
}

_ANALYSIS_TYPE_KEYWORDS = {
    "trend", "trends", "market", "overview", "comparison", "compare",
    "forecast", "outlook", "impact", "assessment", "review", "benchmark",
    "benchmarking", "cost analysis", "risk", "risk analysis",
    "swot", "pestle", "pestel", "gap analysis", "competitive analysis",
    "landscape", "deep dive", "case study", "survey", "audit",
    "evaluation", "projection", "prediction", "scenario",
    "policy review", "policy analysis", "market overview",
    "trend analysis", "impact assessment",
}

_SCOPE_KEYWORDS = {
    "residential", "commercial", "industrial", "enterprise",
    "sme", "smes", "small business", "fortune 500", "startup",
    "startups", "public sector", "private sector", "government",
    "military", "defense", "defence", "healthcare", "health care",
    "education", "retail", "wholesale", "manufacturing",
    "agriculture", "mining", "construction", "transportation",
    "logistics", "telecom", "telecommunications", "fintech",
    "banking", "insurance", "real estate", "hospitality",
    "tourism", "media", "entertainment", "pharmaceutical",
    "biotech", "automotive", "aerospace", "consumer",
    "b2b", "b2c", "nonprofit", "non-profit", "utility",
    "utilities", "oil and gas", "oil & gas",
}

# ---------------------------------------------------------------------------
# Comparative query detection patterns
# ---------------------------------------------------------------------------

_COMPARISON_PATTERNS = [
    # "comparison/compare between/of X and Y"
    re.compile(r"\b(?:comparison|compare|comparing)\s+(?:between|of)\s+(.+?)\s+and\s+(.+)", re.IGNORECASE),
    # "compare X and/with/to/vs Y"
    re.compile(r"\b(?:compare|comparing)\s+(.+?)\s+(?:and|with|to|versus|vs\.?)\s+(.+)", re.IGNORECASE),
    # "X vs/versus Y"
    re.compile(r"(.+?)\s+(?:vs\.?|versus)\s+(.+)", re.IGNORECASE),
    # "X compared to/with Y"
    re.compile(r"(.+?)\s+compared\s+(?:to|with)\s+(.+)", re.IGNORECASE),
    # "difference(s) between X and Y"
    re.compile(r"\bdifferences?\s+between\s+(.+?)\s+and\s+(.+)", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Static gap definitions (question + option pills per dimension)
# ---------------------------------------------------------------------------

_GAP_DEFINITIONS = {
    "time_period": {
        "question": "What time period should this cover?",
        "options": [
            "Last 30 days",
            "Last 3 months",
            "Last 12 months",
            "2024-2025",
            "2020-2025",
        ],
    },
    "geographic_focus": {
        "question": "What geographic focus?",
        "options": [
            "Global",
            "United States",
            "Europe",
            "Africa",
            "Asia-Pacific",
        ],
    },
    "analysis_type": {
        "question": "What type of analysis?",
        "options": [
            "Market overview",
            "Trend analysis",
            "Policy review",
            "Impact assessment",
        ],
    },
    "scope": {
        "question": "What scope?",
        "options": [
            "All sectors",
            "Residential",
            "Commercial & industrial",
            "Government & policy",
        ],
    },
}

# ---------------------------------------------------------------------------
# Dimension detection helpers
# ---------------------------------------------------------------------------


def _detect_time_period(query_lower: str) -> Tuple[bool, Optional[str]]:
    """Detect time period references via regex."""
    match = _TIME_PERIOD_PATTERN.search(query_lower)
    if match:
        return True, match.group(0).strip()
    return False, None


def _detect_keyword_set(query_lower: str, keywords: Set[str]) -> Tuple[bool, Optional[str]]:
    """Check whether any keyword from the set appears in the query.

    Tries longest keywords first so multi-word phrases are matched
    preferentially (e.g. "south africa" before "africa").
    """
    for kw in sorted(keywords, key=len, reverse=True):
        # Word-boundary match to avoid partial hits
        if re.search(r"\b" + re.escape(kw) + r"\b", query_lower):
            return True, kw
    return False, None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def refine_query(raw_query: str) -> dict:
    """Analyze a research query and return structured refinement suggestions.

    Uses deterministic keyword/regex matching to detect which dimensions are
    present vs. missing, then returns a structured dict with detected
    dimensions, gaps (with suggested options), and the original query string.

    Args:
        raw_query: The user's original research question.

    Returns:
        dict with keys: status, original_query, dimensions, gaps,
        refined_query, skip_refinement.
    """
    if not raw_query or not raw_query.strip():
        return _passthrough(raw_query)

    query_lower = raw_query.lower().strip()

    # Topic is always detected if query is non-empty
    dimensions: Dict[str, dict] = {
        "topic": {"detected": True, "value": raw_query.strip()},
    }

    # Detect each dimension
    detected_tp, value_tp = _detect_time_period(query_lower)
    dimensions["time_period"] = {"detected": detected_tp, "value": value_tp}

    detected_geo, value_geo = _detect_keyword_set(query_lower, _GEOGRAPHIC_KEYWORDS)
    dimensions["geographic_focus"] = {"detected": detected_geo, "value": value_geo}

    detected_at, value_at = _detect_keyword_set(query_lower, _ANALYSIS_TYPE_KEYWORDS)
    dimensions["analysis_type"] = {"detected": detected_at, "value": value_at}

    detected_sc, value_sc = _detect_keyword_set(query_lower, _SCOPE_KEYWORDS)
    dimensions["scope"] = {"detected": detected_sc, "value": value_sc}

    # Build gaps list for undetected dimensions
    gaps = []
    for dim_name in ("time_period", "geographic_focus", "analysis_type", "scope"):
        if not dimensions[dim_name]["detected"]:
            defn = _GAP_DEFINITIONS[dim_name]
            gaps.append({
                "dimension": dim_name,
                "question": defn["question"],
                "options": defn["options"],
            })

    missing_count = len(gaps)
    # Force refinement when any dimension is missing.
    status = "needs_refinement" if missing_count > 0 else "well_specified"
    skip = missing_count == 0

    result = {
        "status": status,
        "original_query": raw_query,
        "dimensions": dimensions,
        "gaps": gaps,
        "refined_query": raw_query,
        "skip_refinement": skip,
    }

    logger.info(
        "Refinement result: status=%s, gaps=%d, skip=%s",
        status, len(gaps), skip,
    )
    return result


_REFINEMENT_SEGMENT_PATTERNS = [
    re.compile(r"\bfocus timeframe:\s*([^.|]+)", re.IGNORECASE),
    re.compile(r"\bgeography:\s*([^.|]+)", re.IGNORECASE),
    re.compile(r"\banalysis:\s*([^.|]+)", re.IGNORECASE),
    re.compile(r"\bscope:\s*([^.|]+)", re.IGNORECASE),
    re.compile(r"\btime period:\s*([^|.]+)", re.IGNORECASE),
    re.compile(r"\bgeographic focus:\s*([^|.]+)", re.IGNORECASE),
    re.compile(r"\banalysis type:\s*([^|.]+)", re.IGNORECASE),
]

_FOCUS_FACETS = [
    (
        "price",
        re.compile(r"\b(price|prices|pricing|cost|volatility|spread)\b", re.IGNORECASE),
        "price movement and market dynamics",
    ),
    (
        "geopolitical",
        re.compile(r"\b(geopolitic|sanction|war|conflict|security|supply shock|event)\b", re.IGNORECASE),
        "geopolitical drivers and event causality",
    ),
    (
        "regulatory",
        re.compile(r"\b(regulat|policy|tariff|rule|market reform|compliance)\b", re.IGNORECASE),
        "regulatory and policy shifts",
    ),
]


def _normalize_clause(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    return cleaned.strip(" ,;:.")


def _extract_refinement_segments(query: str) -> List[str]:
    """Extract wizard-added segments from refined query text."""
    segments: List[str] = []
    for pattern in _REFINEMENT_SEGMENT_PATTERNS:
        match = pattern.search(query)
        if match:
            value = _normalize_clause(match.group(1))
            if value:
                segments.append(value)
    return segments


def decompose_query(query: str) -> List[SearchIntent]:
    """Decompose query into targeted intents while preserving full context."""
    normalized_query = _normalize_clause(query)
    if not normalized_query:
        return []

    # Strip explicit wizard labels from the base query text.
    core_query = normalized_query
    for pattern in _REFINEMENT_SEGMENT_PATTERNS:
        core_query = pattern.sub("", core_query)
    core_query = _normalize_clause(core_query) or normalized_query

    intents: List[SearchIntent] = [
        SearchIntent(intent_query=core_query, parent_query=normalized_query, is_primary=True)
    ]

    # Add refinement-segment intents (time/geography/analysis/scope),
    # but always retain the full query context.
    for segment in _extract_refinement_segments(normalized_query):
        intent_query = _normalize_clause(f"{core_query} {segment}")
        if intent_query:
            intents.append(
                SearchIntent(
                    intent_query=intent_query,
                    parent_query=normalized_query,
                    is_primary=False,
                )
            )

    # Add explicit facet intents derived from the question itself.
    for _, pattern, focus_text in _FOCUS_FACETS:
        if pattern.search(core_query):
            intent_query = _normalize_clause(f"{core_query} focus on {focus_text}")
            if intent_query:
                intents.append(
                    SearchIntent(
                        intent_query=intent_query,
                        parent_query=normalized_query,
                        is_primary=False,
                    )
                )

    # Legacy separator support: split on "|" if present, but preserve context.
    if "|" in normalized_query:
        for part in normalized_query.split("|"):
            clause = _normalize_clause(part)
            if clause:
                intent_query = _normalize_clause(f"{core_query} {clause}")
                intents.append(
                    SearchIntent(
                        intent_query=intent_query,
                        parent_query=normalized_query,
                        is_primary=False,
                    )
                )

    # Deduplicate by normalized intent_query and cap count.
    decomposition_cfg = getattr(config, "QUERY_DECOMPOSITION", {})
    max_intents = int(decomposition_cfg.get("max_intents", 4))
    deduped: List[SearchIntent] = []
    seen = set()
    for intent in intents:
        key = _normalize_clause(intent.intent_query).lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(intent)
        if len(deduped) >= max_intents:
            break

    return deduped


# ---------------------------------------------------------------------------
# Comparative query detection
# ---------------------------------------------------------------------------


def _clean_subject(text: str) -> str:
    """Strip trailing punctuation and leading articles/prepositions from a subject."""
    cleaned = text.strip()
    # Strip trailing punctuation
    cleaned = re.sub(r"[?.!,;:]+$", "", cleaned).strip()
    # Strip leading articles and prepositions
    cleaned = re.sub(r"^(?:the|a|an|of|in|on|for|to|with)\s+", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def detect_comparison(query: str) -> dict:
    """Detect whether a query is comparative and extract subjects.

    Iterates through compiled regex patterns to identify comparative
    queries (e.g., "X vs Y", "compare X and Y", "differences between X and Y").

    Args:
        query: The user's research query.

    Returns:
        dict with keys:
            is_comparative (bool): Whether a comparison was detected.
            subjects (list[str]): Extracted subjects (2 items if comparative, else empty).
    """
    if not query or not query.strip():
        return {"is_comparative": False, "subjects": []}

    for pattern in _COMPARISON_PATTERNS:
        match = pattern.search(query)
        if match:
            subject_a = _clean_subject(match.group(1))
            subject_b = _clean_subject(match.group(2))
            if subject_a and subject_b:
                logger.info("Comparative query detected: [%s] vs [%s]", subject_a, subject_b)
                return {"is_comparative": True, "subjects": [subject_a, subject_b]}

    return {"is_comparative": False, "subjects": []}


_GENERIC_SUBJECT_PATTERNS = [
    re.compile(r"^\s*other\s+.+", re.IGNORECASE),
    re.compile(r"^\s*alternatives?\s*(?:to|for)?\s*.+", re.IGNORECASE),
    re.compile(r"^\s*.+\s+alternatives?\s*$", re.IGNORECASE),
    re.compile(r"^\s*.+\s+technolog(?:y|ies)\s*$", re.IGNORECASE),
    re.compile(r"^\s*.+\s+types?\s*$", re.IGNORECASE),
    re.compile(r"^\s*.+\s+options?\s*$", re.IGNORECASE),
]

_GENERIC_SUBJECT_TERMS = {
    "others",
    "other technologies",
    "other tech",
    "alternatives",
    "alternative technologies",
    "options",
    "types",
    "systems",
    "methods",
}


def _is_generic_subject(subject: str) -> bool:
    """Return True when a comparison subject is category-level, not specific."""
    if not subject or not subject.strip():
        return True

    normalized = _clean_subject(subject).lower()
    if normalized in _GENERIC_SUBJECT_TERMS:
        return True

    if len(normalized.split()) <= 2 and normalized in {"other", "others", "alternatives"}:
        return True

    return any(pattern.match(normalized) for pattern in _GENERIC_SUBJECT_PATTERNS)


_MARKET_INTENT_KEYWORDS = {
    "energy",
    "electricity",
    "power market",
    "grid",
    "commodity",
    "commodities",
    "price",
    "pricing",
    "tariff",
    "tariffs",
    "regulation",
    "regulatory",
    "policy",
    "market",
    "demand",
    "supply",
    "volatility",
    "natural gas",
    "crude",
    "oil",
    "lng",
    "coal",
    "lithium",
    "copper",
    "uranium",
    "carbon",
    "emissions trading",
    "capacity market",
}


def detect_market_intent(query: str) -> bool:
    """Detect whether a query likely needs market/regulatory context."""
    if not query or not query.strip():
        return False

    lowered = query.lower()
    return any(re.search(r"\b" + re.escape(term) + r"\b", lowered) for term in _MARKET_INTENT_KEYWORDS)


def _passthrough(raw_query: str) -> dict:
    """Return a passthrough response that skips refinement."""
    return {
        "status": "well_specified",
        "original_query": raw_query or "",
        "dimensions": {
            "topic": {"detected": True, "value": raw_query or ""},
        },
        "gaps": [],
        "refined_query": raw_query or "",
        "skip_refinement": True,
    }
