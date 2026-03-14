"""Canonical regulatory event normalization helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Optional


REGULATORY_EVENT_SCHEMA_VERSION = "regulatory-event.v1"


def _stable_id(*parts: Any) -> str:
    raw = "|".join("" if part is None else str(part) for part in parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _payload_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, sort_keys=True)


def slugify(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
    return "-".join(part for part in cleaned.split("-") if part)


def parse_date(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None

    for fmt in (
        "%Y-%m-%d",
        "%d %B %Y",
        "%d %b %Y",
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text[:10] if len(text) >= 10 else text


def build_raw_document(
    *,
    jurisdiction: str,
    source_system: str,
    source_url: str,
    payload: Any,
    content_type: str,
    fetch_status: str,
    http_status: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    payload_text = _payload_text(payload)
    document_hash = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    return {
        "id": _stable_id(source_system, source_url, document_hash),
        "jurisdiction": jurisdiction,
        "source_system": source_system,
        "source_url": source_url,
        "content_type": content_type,
        "fetch_status": fetch_status,
        "http_status": http_status,
        "document_hash": f"sha256:{document_hash}",
        "payload_text": payload_text,
        "metadata": metadata or {},
    }


def build_transform_run(
    *,
    jurisdiction: str,
    source_system: str,
    raw_document_id: str,
    transform_name: str,
    transform_version: str,
    mapping: dict[str, Any],
    record_count: int,
    notes: str,
) -> dict[str, Any]:
    return {
        "id": _stable_id(source_system, raw_document_id, transform_name, transform_version),
        "jurisdiction": jurisdiction,
        "source_system": source_system,
        "raw_document_id": raw_document_id,
        "transform_name": transform_name,
        "schema_version": REGULATORY_EVENT_SCHEMA_VERSION,
        "transform_version": transform_version,
        "mapping": mapping,
        "record_count": record_count,
        "notes": notes,
    }


def build_regulatory_event(
    *,
    jurisdiction: str,
    regulator: str,
    event_type: str,
    title: str,
    published_date: Any,
    source_url: str,
    source_system: str,
    source_record_id: str,
    transform_version: str,
    transform_run_id: str,
    raw_document_id: str,
    summary: Optional[str] = None,
    effective_date: Any = None,
    deadline_date: Any = None,
    properties: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    return {
        "jurisdiction": jurisdiction,
        "regulator": regulator,
        "event_type": event_type,
        "title": title.strip(),
        "summary": summary,
        "effective_date": parse_date(effective_date),
        "deadline_date": parse_date(deadline_date),
        "published_date": parse_date(published_date),
        "source_url": source_url,
        "source_system": source_system,
        "source_record_id": source_record_id,
        "schema_version": REGULATORY_EVENT_SCHEMA_VERSION,
        "transform_version": transform_version,
        "transform_run_id": transform_run_id,
        "raw_document_id": raw_document_id,
        "properties": properties or {},
    }


def classify_event_type(title: str, *, default: str = "notice") -> str:
    lowered = title.lower()
    if "decision" in lowered or "approves" in lowered or "approval" in lowered:
        return "decision"
    if "comment" in lowered or "hearing" in lowered or "invitation" in lowered:
        return "consultation"
    if "bidder" in lowered or "procurement" in lowered or "rfq" in lowered:
        return "procurement_update"
    if "tariff" in lowered or "price" in lowered or "fuel notice" in lowered:
        return "public_notice"
    return default
