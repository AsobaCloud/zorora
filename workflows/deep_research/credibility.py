"""Credibility scorer - multi-factor credibility scoring for sources."""

import re
from typing import Dict, Any, Optional

# Base credibility by domain (starting point, NOT final score!)
BASE_CREDIBILITY = {
    # Tier 1: High-quality peer-reviewed (0.70-0.85 base)
    "nature": {"score": 0.85, "reason": "Nature journal (high impact)"},
    "science.org": {"score": 0.85, "reason": "Science journal (high impact)"},
    "cell.com": {"score": 0.80, "reason": "Cell Press journal"},
    "nejm.org": {"score": 0.85, "reason": "New England Journal of Medicine"},
    "thelancet.com": {"score": 0.85, "reason": "The Lancet (high impact)"},
    "pubmed.ncbi": {"score": 0.70, "reason": "PubMed indexed (peer-reviewed)"},

    # Tier 2: Preprints (0.50 - NOT automatically credible!)
    "arxiv.org": {"score": 0.50, "reason": "ArXiv preprint (NOT peer-reviewed)"},
    "biorxiv.org": {"score": 0.50, "reason": "bioRxiv preprint (NOT peer-reviewed)"},
    "medrxiv.org": {"score": 0.50, "reason": "medRxiv preprint (NOT peer-reviewed)"},
    "doi:": {"score": 0.65, "reason": "Has DOI (may be peer-reviewed)"},

    # Tier 3: Government (0.75-0.85)
    ".gov": {"score": 0.85, "reason": "Government source"},
    ".edu": {"score": 0.75, "reason": "Educational institution"},
    "europa.eu": {"score": 0.80, "reason": "European Union"},
    "un.org": {"score": 0.80, "reason": "United Nations"},

    # Tier 4: Curated news (0.75)
    "newsroom:": {"score": 0.75, "reason": "Asoba curated newsroom"},
    "asoba.co/newsroom": {"score": 0.75, "reason": "Asoba newsroom"},

    # Tier 5: Major news (0.60-0.70)
    "reuters.com": {"score": 0.70, "reason": "Reuters (news wire)"},
    "bloomberg.com": {"score": 0.70, "reason": "Bloomberg (financial news)"},
    "apnews.com": {"score": 0.70, "reason": "Associated Press"},
    "bbc.com": {"score": 0.65, "reason": "BBC News"},
    "wsj.com": {"score": 0.65, "reason": "Wall Street Journal"},

    # Tier 6: General web (0.25-0.40)
    "medium.com": {"score": 0.40, "reason": "Blog platform"},
    "substack.com": {"score": 0.40, "reason": "Newsletter platform"},
    "reddit.com": {"score": 0.25, "reason": "User-generated content"},
}

# Predatory publishers (override to 0.2)
PREDATORY_PUBLISHERS = [
    "scirp.org", "waset.org", "omicsonline.org", "hilarispublisher.com",
    "austinpublishinggroup.com", "crimsonpublishers.com", "lupinepublishers.com",
]

# Known retractions (override to 0.0)
KNOWN_RETRACTIONS = {
    "10.1016/S0140-6736(97)11096-0": "Wakefield MMR-autism paper (retracted 2010)",
}


def calculate_citation_modifier(citation_count: int) -> float:
    """More citations = higher credibility (logarithmic)"""
    if citation_count == 0:
        return 0.8
    elif citation_count < 10:
        return 0.9
    elif citation_count < 100:
        return 1.0
    elif citation_count < 1000:
        return 1.1
    else:
        return 1.2


def calculate_cross_reference_modifier(agreement_count: int) -> float:
    """More sources agree = higher credibility"""
    if agreement_count <= 1:
        return 0.9
    elif agreement_count <= 3:
        return 1.0
    elif agreement_count <= 6:
        return 1.1
    else:
        return 1.15


def check_retraction_status(url: str, doi: Optional[str] = None) -> Dict[str, Any]:
    """Check if paper is retracted (local cache)"""
    if doi and doi in KNOWN_RETRACTIONS:
        return {"retracted": True, "reason": KNOWN_RETRACTIONS[doi]}
    return {"retracted": False, "reason": ""}


def is_predatory_publisher(url: str) -> bool:
    """Check if URL is from known predatory publisher"""
    return any(pub in url.lower() for pub in PREDATORY_PUBLISHERS)


def extract_doi_from_url(url: str) -> Optional[str]:
    """Extract DOI from URL if present"""
    match = re.search(r'10\.\d{4,}/[^\s]+', url)
    return match.group(0) if match else None


def score_source_credibility(
    url: str,
    citation_count: int = 0,
    cross_reference_count: int = 1,
    publication_year: Optional[int] = None,
    source_title: Optional[str] = None
) -> Dict[str, Any]:
    """
    Multi-factor credibility scoring

    Returns: {
        "score": float (0.0-0.95),
        "base_score": float,
        "category": str,
        "modifiers": {...},
        "breakdown": str (human-readable)
    }
    """
    url_lower = url.lower()

    # Step 1: Get base score
    base_score = 0.50
    base_reason = "Unknown source"
    for domain, info in BASE_CREDIBILITY.items():
        if domain in url_lower:
            base_score = info["score"]
            base_reason = info["reason"]
            break
    
    # Use source title for display if available and no known domain match
    if base_reason == "Unknown source" and source_title:
        # Extract domain from URL for display, or use title
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url if url.startswith('http') else f'https://{url}')
            domain = parsed.netloc or parsed.path.split('/')[0] if parsed.path else None
            if domain:
                base_reason = domain
            else:
                base_reason = source_title[:50]  # Truncate long titles
        except:
            base_reason = source_title[:50] if source_title else "Unknown source"

    # Step 2: Check predatory publishers (override)
    if is_predatory_publisher(url):
        return {
            "score": 0.20,
            "base_score": base_score,
            "category": "predatory_publisher",
            "modifiers": {},
            "breakdown": "⚠️ PREDATORY PUBLISHER"
        }

    # Step 3: Check retractions (override)
    doi = extract_doi_from_url(url)
    retraction = check_retraction_status(url, doi)
    if retraction["retracted"]:
        return {
            "score": 0.0,
            "base_score": base_score,
            "category": "retracted",
            "modifiers": {},
            "breakdown": f"❌ RETRACTED - {retraction['reason']}"
        }

    # Step 4: Apply modifiers
    cite_mod = calculate_citation_modifier(citation_count)
    cross_mod = calculate_cross_reference_modifier(cross_reference_count)

    # Step 5: Calculate final (cap at 0.95)
    final_score = min(0.95, base_score * cite_mod * cross_mod)

    # Step 6: Build explanation
    parts = [f"Base: {base_score:.2f} ({base_reason})"]
    if cite_mod != 1.0:
        parts.append(f"Citations: {cite_mod:.2f}x ({citation_count} cites)")
    if cross_mod != 1.0:
        parts.append(f"Cross-refs: {cross_mod:.2f}x ({cross_reference_count} sources)")
    parts.append(f"→ {final_score:.2f}")

    return {
        "score": final_score,
        "base_score": base_score,
        "category": base_reason,
        "modifiers": {"citation": cite_mod, "cross_reference": cross_mod},
        "breakdown": " | ".join(parts)
    }
