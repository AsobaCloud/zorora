"""Local SME corpus loader for diligence-focused deep research."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import config
from engine.models import Source

logger = logging.getLogger(__name__)


def _parse_frontmatter(text: str) -> Tuple[Dict[str, object], str]:
    """Parse lightweight YAML-like frontmatter from markdown text."""
    if not text.startswith("---\n"):
        return {}, text

    marker = "\n---\n"
    end_idx = text.find(marker, 4)
    if end_idx == -1:
        return {}, text

    header = text[4:end_idx]
    body = text[end_idx + len(marker):]
    meta: Dict[str, object] = {}

    for raw_line in header.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value.startswith("[") and value.endswith("]"):
            items = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
            meta[key] = items
        elif "," in value and key in {"domains", "technologies", "countries", "tags"}:
            items = [v.strip().strip("'\"") for v in value.split(",") if v.strip()]
            meta[key] = items
        elif key == "weight":
            try:
                meta[key] = float(value)
            except ValueError:
                meta[key] = 1.0
        else:
            meta[key] = value.strip("'\"")

    return meta, body


def _normalize_terms(values: object) -> List[str]:
    if not values:
        return []
    if isinstance(values, str):
        return [values.strip().lower()] if values.strip() else []
    if isinstance(values, list):
        return [str(v).strip().lower() for v in values if str(v).strip()]
    return [str(values).strip().lower()] if str(values).strip() else []


def _tokenize(text: str) -> set:
    return set(re.findall(r"[a-z0-9]{3,}", (text or "").lower()))


def _score_doc(
    query: str,
    metadata: Dict[str, object],
    body: str,
    intent_domain: Optional[str],
    asset_metadata: Optional[dict],
) -> float:
    query_tokens = _tokenize(query)
    doc_tokens = _tokenize(f"{metadata.get('title', '')} {metadata.get('orthodoxy', '')} {metadata.get('tags', '')} {body[:1500]}")
    overlap = len(query_tokens & doc_tokens)

    score = float(overlap)
    score += float(metadata.get("weight", 1.0))

    domains = _normalize_terms(metadata.get("domains"))
    technologies = _normalize_terms(metadata.get("technologies"))
    countries = _normalize_terms(metadata.get("countries"))

    if intent_domain and intent_domain.strip().lower() in domains:
        score += 4.0

    if asset_metadata:
        technology = str(asset_metadata.get("technology", "")).strip().lower()
        country = str(asset_metadata.get("country", "")).strip().lower()
        if technology and technology in technologies:
            score += 2.0
        if country and country in countries:
            score += 2.0

    return score


def load_local_sme_sources(
    query: str,
    intent_domain: Optional[str] = None,
    asset_metadata: Optional[dict] = None,
    max_results: int = 5,
) -> List[Source]:
    """Load diligence SME texts from local markdown files."""
    settings = getattr(config, "LOCAL_SME_CORPUS", {})
    if not settings.get("enabled", False):
        return []

    corpus_dir = Path(settings.get("path", "data/sme_orthodoxies"))
    if not corpus_dir.is_absolute():
        corpus_dir = Path(__file__).resolve().parents[2] / corpus_dir
    if not corpus_dir.exists():
        return []

    files = sorted(corpus_dir.rglob("*.md"))
    if not files:
        return []

    scored: List[Tuple[float, Source]] = []
    per_doc_snippet_chars = int(settings.get("snippet_chars", 320))
    per_doc_body_chars = int(settings.get("body_chars", 4000))

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("Unable to read SME corpus file %s: %s", path, exc)
            continue

        meta, body = _parse_frontmatter(text)
        title = str(meta.get("title") or path.stem.replace("_", " ").title())
        orthodoxy = str(meta.get("orthodoxy") or "Unspecified orthodoxy")
        domains = _normalize_terms(meta.get("domains"))
        domain_label = ", ".join(domains) if domains else "unspecified"

        score = _score_doc(query, meta, body, intent_domain=intent_domain, asset_metadata=asset_metadata)
        if score <= 0:
            continue

        rel_path = path.relative_to(corpus_dir)
        url = f"sme://{rel_path.as_posix()}"
        snippet = f"Orthodoxy: {orthodoxy} | Domains: {domain_label} | {body.strip()[:per_doc_snippet_chars]}"

        source = Source(
            source_id=Source.generate_id(url),
            url=url,
            title=f"[Internal SME] {title}",
            source_type="internal_sme",
            content_snippet=snippet,
            content_full=body.strip()[:per_doc_body_chars],
        )
        scored.append((score, source))

    scored.sort(key=lambda item: item[0], reverse=True)
    capped = int(settings.get("max_results_per_query", max_results))
    return [src for _, src in scored[: min(max_results, capped)]]
