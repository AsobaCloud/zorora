"""South Africa and Zimbabwe regulatory event clients."""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import config
from tools.regulatory.normalization import (
    build_raw_document,
    build_regulatory_event,
    build_transform_run,
    classify_event_type,
    slugify,
)

logger = logging.getLogger(__name__)

NERSA_HOME_URL = "https://www.nersa.org.za/"
IPPO_OLDNEWS_URL = "https://www.ipp-projects.co.za/PortalAPI/?etn=oldnews"
ZERA_PRESS_URL = "https://www.zera.co.zw/press-releases-public-notices/"


def _regulatory_config() -> dict[str, Any]:
    return getattr(config, "REGULATORY", {})


def _timeout_seconds() -> int:
    return int(_regulatory_config().get("timeout_seconds", 30) or 30)


def _user_agent() -> str:
    return "Mozilla/5.0 (compatible; ZororaRegulatoryBot/1.0; +https://github.com/AsobaCloud/zorora)"


def _empty_bundle() -> dict[str, list[dict]]:
    return {"events": [], "raw_documents": [], "transform_runs": []}


def _extract_link_text(anchor) -> tuple[str, str | None]:
    date_tag = anchor.find("span")
    date_text = date_tag.get_text(" ", strip=True) if date_tag else None
    if date_tag:
        date_tag.extract()
    title = anchor.get_text(" ", strip=True)
    return title, date_text


def _record_id_from_href(href: str | None, fallback_text: str) -> str:
    if href:
        trimmed = href.strip("/").split("/")[-1]
        if trimmed:
            return trimmed
    return slugify(fallback_text)


def _loads_json_list(text: str) -> list[dict[str, Any]]:
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    payload = text[start:end + 1]
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    return [item for item in data if isinstance(item, dict)]


def _looks_like_antibot(text: str) -> bool:
    lowered = text.lower()
    return "security verification" in lowered or "g-recaptcha-response" in lowered


def parse_nersa_homepage(html: str, *, source_url: str = NERSA_HOME_URL) -> dict[str, list[dict]]:
    soup = BeautifulSoup(html, "html.parser")
    bundle = _empty_bundle()

    section_specs = [
        {
            "selector": "#latest_news a.home-section-article",
            "source_system": "nersa_latest_news",
            "summary": "Latest News",
            "default_event_type": "announcement",
            "transform_name": "nersa_latest_news_v1",
            "transform_version": "nersa_latest_news.v1",
            "notes": "Parses #latest_news anchors from the NERSA homepage.",
        },
        {
            "selector": "#recent_decisions a.listing",
            "source_system": "nersa_recent_decisions",
            "summary": "Recent Regulator Decision",
            "default_event_type": "decision",
            "transform_name": "nersa_recent_decision_v1",
            "transform_version": "nersa_recent_decision.v1",
            "notes": "Parses #recent_decisions anchors from the NERSA homepage.",
        },
    ]

    for spec in section_specs:
        anchors = soup.select(spec["selector"])
        if not anchors:
            continue

        raw_document = build_raw_document(
            jurisdiction="ZA",
            source_system=spec["source_system"],
            source_url=source_url,
            payload=html,
            content_type="text/html",
            fetch_status="ok",
            http_status=200,
            metadata={"selector": spec["selector"], "record_count": len(anchors)},
        )
        transform_run = build_transform_run(
            jurisdiction="ZA",
            source_system=spec["source_system"],
            raw_document_id=raw_document["id"],
            transform_name=spec["transform_name"],
            transform_version=spec["transform_version"],
            mapping={
                "title": {"source": "anchor.text"},
                "published_date": {"source": "anchor > span"},
                "source_url": {"source": "anchor.href"},
                "source_record_id": {"source": "anchor.href"},
            },
            record_count=len(anchors),
            notes=spec["notes"],
        )

        events = []
        for anchor in anchors:
            href = anchor.get("href")
            title, date_text = _extract_link_text(anchor)
            if not title or not date_text:
                continue
            event = build_regulatory_event(
                jurisdiction="ZA",
                regulator="NERSA",
                event_type=classify_event_type(title, default=spec["default_event_type"]),
                title=title,
                summary=spec["summary"],
                published_date=date_text,
                source_url=urljoin(source_url, href or ""),
                source_system=spec["source_system"],
                source_record_id=_record_id_from_href(href, title),
                transform_version=spec["transform_version"],
                transform_run_id=transform_run["id"],
                raw_document_id=raw_document["id"],
                properties={"selector": spec["selector"]},
            )
            events.append(event)

        if events:
            bundle["events"].extend(events)
            bundle["raw_documents"].append(raw_document)
            bundle["transform_runs"].append(transform_run)

    return bundle


def parse_ippo_press_releases(
    payload: Iterable[dict[str, Any]] | list[dict[str, Any]],
    *,
    source_url: str = IPPO_OLDNEWS_URL,
) -> dict[str, list[dict]]:
    records = [item for item in payload if isinstance(item, dict)]
    if not records:
        return _empty_bundle()

    raw_document = build_raw_document(
        jurisdiction="ZA",
        source_system="ippo_oldnews",
        source_url=source_url,
        payload=records,
        content_type="application/json",
        fetch_status="ok",
        http_status=200,
        metadata={"record_count": len(records)},
    )
    transform_run = build_transform_run(
        jurisdiction="ZA",
        source_system="ippo_oldnews",
        raw_document_id=raw_document["id"],
        transform_name="ippo_press_release_v1",
        transform_version="ippo_press_release.v1",
        mapping={
            "title": {"source": "headline"},
            "published_date": {"source": "date"},
            "source_record_id": {"source": "id"},
            "source_url": {"source": "noteid", "template": "/_entity/annotation/{noteid}"},
        },
        record_count=len(records),
        notes="Parses the IPP Office oldnews portal API feed.",
    )

    events = []
    for record in records:
        noteid = record.get("noteid")
        filename = record.get("filename")
        detail = record.get("detail")
        title = str(record.get("headline") or "").strip()
        if not title:
            continue
        event = build_regulatory_event(
            jurisdiction="ZA",
            regulator="IPP Office",
            event_type=classify_event_type(title, default="announcement"),
            title=title,
            summary=detail or "IPP Office press release",
            published_date=record.get("date"),
            source_url=urljoin("https://www.ipp-projects.co.za", f"/_entity/annotation/{noteid}") if noteid else source_url,
            source_system="ippo_oldnews",
            source_record_id=str(record.get("id") or slugify(title)),
            transform_version="ippo_press_release.v1",
            transform_run_id=transform_run["id"],
            raw_document_id=raw_document["id"],
            properties={
                "filename": filename,
                "thumbnail": record.get("thumbnail"),
                "websiteid": record.get("websiteid"),
                "websitename": record.get("websitename"),
            },
        )
        events.append(event)

    return {
        "events": events,
        "raw_documents": [raw_document],
        "transform_runs": [transform_run],
    }


def normalize_zera_seed_catalog(
    seed_records: Iterable[dict[str, Any]] | list[dict[str, Any]],
    *,
    source_url: str = ZERA_PRESS_URL,
    metadata: dict[str, Any] | None = None,
) -> dict[str, list[dict]]:
    records = [item for item in seed_records if isinstance(item, dict)]
    if not records:
        return _empty_bundle()

    raw_document = build_raw_document(
        jurisdiction="ZW",
        source_system="zera_seed_catalog",
        source_url=source_url,
        payload=records,
        content_type="application/json",
        fetch_status="seed_catalog",
        http_status=200,
        metadata=metadata or {"catalog": "zera_seed_events", "record_count": len(records)},
    )
    transform_run = build_transform_run(
        jurisdiction="ZW",
        source_system="zera_seed_catalog",
        raw_document_id=raw_document["id"],
        transform_name="zera_seed_catalog_v1",
        transform_version="zera_seed_catalog.v1",
        mapping={
            "title": {"source": "title"},
            "published_date": {"source": "published_date"},
            "summary": {"source": "summary"},
            "source_url": {"source": "source_url"},
        },
        record_count=len(records),
        notes="Normalizes the seeded fallback catalog for ZERA notices.",
    )

    events = []
    for record in records:
        title = str(record.get("title") or "").strip()
        if not title:
            continue
        event = build_regulatory_event(
            jurisdiction="ZW",
            regulator="ZERA",
            event_type=classify_event_type(title, default="public_notice"),
            title=title,
            summary=record.get("summary"),
            published_date=record.get("published_date"),
            source_url=record.get("source_url") or source_url,
            source_system="zera_seed_catalog",
            source_record_id=str(record.get("source_record_id") or slugify(title)),
            transform_version="zera_seed_catalog.v1",
            transform_run_id=transform_run["id"],
            raw_document_id=raw_document["id"],
            properties={"category": record.get("category")},
        )
        events.append(event)

    return {
        "events": events,
        "raw_documents": [raw_document],
        "transform_runs": [transform_run],
    }


def fetch_nersa_events() -> dict[str, list[dict]]:
    try:
        response = requests.get(
            NERSA_HOME_URL,
            timeout=_timeout_seconds(),
            headers={"User-Agent": _user_agent()},
        )
        response.raise_for_status()
    except Exception as exc:
        logger.warning("NERSA fetch failed: %s", exc)
        return _empty_bundle()
    return parse_nersa_homepage(response.text, source_url=NERSA_HOME_URL)


def fetch_ippo_press_releases() -> dict[str, list[dict]]:
    try:
        response = requests.get(
            IPPO_OLDNEWS_URL,
            timeout=_timeout_seconds(),
            headers={"User-Agent": _user_agent(), "Accept": "application/json,text/plain,*/*"},
        )
        response.raise_for_status()
    except Exception as exc:
        logger.warning("IPP Office press release fetch failed: %s", exc)
        return _empty_bundle()
    return parse_ippo_press_releases(_loads_json_list(response.text), source_url=IPPO_OLDNEWS_URL)


def fetch_zera_events() -> dict[str, list[dict]]:
    seed_records = _regulatory_config().get("zimbabwe_seed_events", [])
    metadata = {"catalog": "zera_seed_events", "record_count": len(seed_records)}
    try:
        response = requests.get(
            ZERA_PRESS_URL,
            timeout=_timeout_seconds(),
            headers={"User-Agent": _user_agent()},
        )
        metadata["official_status"] = response.status_code
        if _looks_like_antibot(response.text):
            metadata["fallback_reason"] = "anti_bot_gate"
        elif response.status_code >= 400:
            metadata["fallback_reason"] = f"http_{response.status_code}"
        else:
            metadata["fallback_reason"] = "official_page_parser_unavailable"
    except Exception as exc:
        logger.warning("ZERA fetch failed, using seeded fallback: %s", exc)
        metadata["fallback_reason"] = str(exc)
    return normalize_zera_seed_catalog(seed_records, source_url=ZERA_PRESS_URL, metadata=metadata)
