"""Shared digest filtering and synthesis helpers."""

from __future__ import annotations

import logging
from datetime import datetime

import config
from tools.specialist.client import create_specialist_client

logger = logging.getLogger(__name__)


def parse_date(date_str: str):
    """Parse date string to date object (supports ISO prefixes)."""
    if not date_str:
        return None
    try:
        return datetime.strptime(str(date_str)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def filter_newsroom_articles(articles, topic=None, date_from=None, date_to=None, limit=100):
    """Filter newsroom articles by topic and date range."""
    topic_terms = [t.strip().lower() for t in (topic or "").split() if t.strip()]
    start_date = parse_date(date_from)
    end_date = parse_date(date_to)
    filtered = []

    for article in articles:
        article_date = parse_date(article.get("date"))
        if start_date and (not article_date or article_date < start_date):
            continue
        if end_date and (not article_date or article_date > end_date):
            continue

        if topic_terms:
            title = str(article.get("headline", "")).lower()
            source = str(article.get("source", "")).lower()
            tags = " ".join(str(t).lower() for t in article.get("topic_tags", []))
            haystack = f"{title} {source} {tags}"
            if not all(term in haystack for term in topic_terms):
                continue

        filtered.append(article)

    filtered.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    return filtered[:limit]


def news_intel_synthesis(articles, topic=None, date_from=None, date_to=None):
    """Synthesize filtered newsroom articles."""
    if not articles:
        return "No articles matched the selected filters."

    entries = []
    for article in articles[:80]:
        headline = article.get("headline", "Untitled")
        source = article.get("source", "Unknown")
        date_str = article.get("date", "")[:10]
        url = article.get("url", "")
        topics = ", ".join(article.get("topic_tags", [])[:6])
        entries.append(f"- [{date_str}] {headline} ({source})\n  Topics: {topics}\n  URL: {url}")

    scope = f"topic='{topic or 'all'}', date_from='{date_from or 'none'}', date_to='{date_to or 'none'}'"
    prompt = (
        "You are producing a newsroom intelligence brief from API-fetched articles.\n"
        f"Scope: {scope}\n"
        f"Total articles: {len(articles)}\n\n"
        "Provide:\n"
        "1) Executive Summary (4-6 bullets)\n"
        "2) Key Themes\n"
        "3) Notable Signals/Risks\n"
        "4) Watchlist (next 1-2 weeks)\n"
        "Use citations as [Headline].\n\n"
        "Articles:\n"
        + "\n\n".join(entries)
    )

    try:
        model_config = config.SPECIALIZED_MODELS["reasoning"]
        client = create_specialist_client("reasoning", model_config)
        messages = [
            {"role": "system", "content": "You are a concise intelligence analyst."},
            {"role": "user", "content": prompt},
        ]
        response = client.chat_complete(messages, tools=None)
        content = client.extract_content(response)
        if content and content.strip():
            return content.strip()
    except Exception as exc:
        logger.warning("News intel synthesis fallback triggered: %s", exc)

    theme_counts = {}
    for article in articles:
        for tag in article.get("topic_tags", [])[:3]:
            key = str(tag).strip()
            if key:
                theme_counts[key] = theme_counts.get(key, 0) + 1
    top_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    bullets = [f"- {name}: {count} mentions" for name, count in top_themes]
    latest = [f"- [{a.get('date', '')[:10]}] {a.get('headline', 'Untitled')}" for a in articles[:8]]
    return (
        f"News Intel Summary ({len(articles)} articles)\n\n"
        "Top Themes:\n"
        + ("\n".join(bullets) if bullets else "- No dominant themes detected")
        + "\n\nRecent Headlines:\n"
        + "\n".join(latest)
    )
