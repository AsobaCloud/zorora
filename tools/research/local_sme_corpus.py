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


def extract_pdf_plain_text(path: Path, max_pages: Optional[int] = None) -> str:
    """Extract plain text from a PDF. ``max_pages=None`` reads all pages.

    Used by the SME corpus loader (bounded pages) and by ``sme_pdf_to_markdown`` (often all pages).
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning(
            "pypdf is not installed; install with `pip install pypdf` to use SME PDFs. Skipping %s",
            path.name,
        )
        return ""

    try:
        reader = PdfReader(str(path))
        total = len(reader.pages)
        if total == 0:
            return ""
        if max_pages is None:
            n = total
        else:
            n = min(total, max(1, max_pages))
        parts: List[str] = []
        for i in range(n):
            page = reader.pages[i]
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text)
        return "\n".join(parts)
    except Exception as exc:
        logger.warning("PDF text extraction failed for %s: %s", path, exc)
        return ""


def display_title_from_path(path: Path) -> str:
    """Human-readable title from file path stem."""
    return path.stem.replace("_", " ").replace("-", " ").strip()


def inferred_meta_for_pdf(path: Path) -> Dict[str, object]:
    """Default frontmatter-style fields for ranking and display (PDFs or converted MD)."""
    stem_l = path.stem.lower()
    tags: List[str] = ["pdf", "sme reference"]
    technologies: List[str] = []
    domains: List[str] = []

    if any(k in stem_l for k in ("pv", "solar", "photovolt", "photovoltaic")):
        technologies.append("solar")
        tags.extend(["pv", "solar"])
    if any(
        k in stem_l
        for k in (
            "maintenance",
            "maintanance",
            "operations",
            "o-m",
            "o&m",
            "manual",
            "guideline",
        )
    ):
        domains.append("performance")
        tags.extend(["operations", "maintenance"])
    if "south-africa" in stem_l or "south_africa" in stem_l or "south africa" in stem_l:
        tags.append("south africa")
    if any(
        k in stem_l
        for k in (
            "tax",
            "credit",
            "equity",
            "incentive",
            "subsidy",
            "itc",
            "ptc",
            "treasury",
            "warehouse facility",
            "warehouse",
        )
    ):
        domains.append("commercial")
        tags.extend(["tax", "finance", "incentives"])
    if "finance" in stem_l or ("project" in stem_l and "finance" in stem_l):
        domains.append("commercial")
        tags.append("project finance")
    if any(k in stem_l for k in ("regulator", "license", "grid code", "crs ", "congress")):
        domains.append("licensing")
        tags.append("policy")

    meta: Dict[str, object] = {
        "title": display_title_from_path(path),
        "orthodoxy": "SME reference (PDF)",
        "weight": 1.0,
    }
    if domains:
        meta["domains"] = list(dict.fromkeys(domains))
    if technologies:
        meta["technologies"] = list(dict.fromkeys(technologies))
    meta["tags"] = list(dict.fromkeys(tags))
    return meta


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


def _collect_corpus_files(corpus_dir: Path) -> List[Path]:
    """Markdown (excluding template stub) and PDF files.

    If ``example.pdf`` and ``example.md`` both exist, only ``example.md`` is used so
    converted/edited Markdown is the single source of truth.
    """
    md_files = [
        p
        for p in sorted(corpus_dir.rglob("*.md"))
        if not p.name.upper().startswith("TEMPLATE_")
    ]
    md_stems = {p.stem for p in md_files}
    pdf_files = [p for p in sorted(corpus_dir.rglob("*.pdf")) if p.stem not in md_stems]
    return md_files + pdf_files


def load_local_sme_sources(
    query: str,
    intent_domain: Optional[str] = None,
    asset_metadata: Optional[dict] = None,
    max_results: int = 5,
) -> List[Source]:
    """Load diligence SME texts from local markdown and PDF files under the corpus directory."""
    settings = getattr(config, "LOCAL_SME_CORPUS", {})
    if not settings.get("enabled", False):
        return []

    corpus_dir = Path(settings.get("path", "data/sme_orthodoxies"))
    if not corpus_dir.is_absolute():
        corpus_dir = Path(__file__).resolve().parents[2] / corpus_dir
    if not corpus_dir.exists():
        return []

    files = _collect_corpus_files(corpus_dir)
    if not files:
        return []

    scored: List[Tuple[float, Source]] = []
    per_doc_snippet_chars = int(settings.get("snippet_chars", 320))
    per_doc_body_chars = int(settings.get("body_chars", 4000))
    pdf_max_pages = int(settings.get("pdf_max_pages", 35))

    for path in files:
        suffix = path.suffix.lower()
        if suffix == ".md":
            try:
                text = path.read_text(encoding="utf-8")
            except Exception as exc:
                logger.warning("Unable to read SME corpus file %s: %s", path, exc)
                continue
            meta, body = _parse_frontmatter(text)
            title = str(meta.get("title") or display_title_from_path(path))
            orthodoxy = str(meta.get("orthodoxy") or "Unspecified orthodoxy")
        elif suffix == ".pdf":
            raw_pdf = extract_pdf_plain_text(path, max_pages=pdf_max_pages)
            if not raw_pdf.strip():
                continue
            meta = inferred_meta_for_pdf(path)
            filename_hint = display_title_from_path(path)
            body = f"{filename_hint}\n\n{raw_pdf}"
            title = str(meta.get("title"))
            orthodoxy = str(meta.get("orthodoxy"))
        else:
            continue

        domains = _normalize_terms(meta.get("domains"))
        domain_label = ", ".join(domains) if domains else "unspecified"

        score = _score_doc(query, meta, body, intent_domain=intent_domain, asset_metadata=asset_metadata)
        if score <= 0:
            continue

        rel_path = path.relative_to(corpus_dir)
        url = f"sme://{rel_path.as_posix()}"
        body_trim = body.strip()
        snippet = f"Orthodoxy: {orthodoxy} | Domains: {domain_label} | {body_trim[:per_doc_snippet_chars]}"

        source = Source(
            source_id=Source.generate_id(url),
            url=url,
            title=f"[Internal SME] {title}",
            source_type="internal_sme",
            content_snippet=snippet,
            content_full=body_trim[:per_doc_body_chars],
        )
        scored.append((score, source))

    scored.sort(key=lambda item: item[0], reverse=True)
    capped = int(settings.get("max_results_per_query", max_results))
    return [src for _, src in scored[: min(max_results, capped)]]
