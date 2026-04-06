"""Flask web application for Zorora deep research UI."""

import logging
import threading
import uuid
import json
from datetime import date, datetime, timezone
from flask import Flask, render_template, request, jsonify, Response, stream_with_context

from engine.research_engine import ResearchEngine
from engine.storage import LocalStorage
from engine.deep_research_service import run_deep_research, build_results_payload
from engine.query_refiner import refine_query, infer_research_type
from ui.web.config_manager import ConfigManager, ModelFetcher
from tools.research.newsroom import fetch_newsroom_cached
from tools.specialist.client import create_specialist_client
from tools.market.store import MarketDataStore
from tools.market.series import SERIES_CATALOG
from tools.imaging.store import ImagingDataStore
from tools.imaging.viability import score_all_deposits
from tools.imaging.mrds_client import fetch_deposits
from tools.imaging.generation_client import load_generation_assets
from tools.imaging.resource_client import fetch_resource_summary
from tools.imaging.site_score import score_bess_site, score_site
from tools.regulatory.store import RegulatoryDataStore
from tools.alerts.store import AlertStore
from workflows.regulatory_workflow import RegulatoryWorkflow
from workflows.digest_synthesis import (
    parse_date as shared_parse_date,
    filter_newsroom_articles as shared_filter_newsroom_articles,
    news_intel_synthesis as shared_news_intel_synthesis,
)
import config
from config import LOGGING_LEVEL, LOGGING_FORMAT, LOG_FILE

# Configure logging for web UI (mirrors main.py setup)
if not logging.root.handlers:
    logging.basicConfig(
        level=LOGGING_LEVEL,
        format=LOGGING_FORMAT,
        handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE)],
    )

logger = logging.getLogger(__name__)

app = Flask(__name__,
            template_folder='templates',
            static_folder='static')

# Initialize research engine
research_engine = ResearchEngine()

# Initialize config managers
config_manager = ConfigManager()
model_fetcher = ModelFetcher()

# Persistent storage for feedback and chat history (SEP-059)
_local_storage = LocalStorage()

# Progress tracking for research workflows
research_progress = {}  # {research_id: {"status": str, "message": str, "phase": str}}
chat_threads = {}  # lightweight in-memory thread store keyed by context id
newsroom_api_warning = None
_market_latest_cache = None  # (timestamp, response_list)
_MARKET_CACHE_TTL = 60  # seconds


def _parse_date(date_str: str):
    """Parse date string to date object (supports ISO prefixes)."""
    return shared_parse_date(date_str)


def _filter_newsroom_articles(articles, topic=None, date_from=None, date_to=None, limit=100):
    """Filter newsroom articles by topic and date range."""
    return shared_filter_newsroom_articles(
        articles,
        topic=topic,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )


def _news_intel_synthesis(articles, topic=None, date_from=None, date_to=None):
    """Synthesize filtered newsroom articles."""
    return shared_news_intel_synthesis(
        articles,
        topic=topic,
        date_from=date_from,
        date_to=date_to,
    )


def fetch_newsroom_api(max_results=10000):
    """Compatibility wrapper that exposes newsroom articles for API handlers/tests."""
    global newsroom_api_warning
    articles, warning = fetch_newsroom_cached(max_results=max_results)
    newsroom_api_warning = warning
    return articles


COUNTRY_ALIASES = {
    "US": "United States", "USA": "United States", "Usa": "United States",
    "Us": "United States", "America": "United States",
    "UK": "United Kingdom", "Uk": "United Kingdom", "Britain": "United Kingdom",
    "Great Britain": "United Kingdom",
    "UAE": "United Arab Emirates", "Uae": "United Arab Emirates",
    "EU": "European Union", "Eu": "European Union",
    "South Korea": "South Korea", "Republic of Korea": "South Korea",
    "Russia": "Russia", "Russian Federation": "Russia",
    "DRC": "Democratic Republic of the Congo",
    "Congo DR": "Democratic Republic of the Congo",
    "SA": "South Africa", "RSA": "South Africa",
}


def normalize_country(name: str) -> str:
    """Normalize a country name/alias to its canonical form."""
    return COUNTRY_ALIASES.get(name, name)


def _load_research_by_id(research_id: str):
    """Load research by exact ID with metadata fallback."""
    research_data = research_engine.load_research(research_id)
    if research_data:
        return research_data

    results = research_engine.search_research(query=research_id, limit=1)
    if not results:
        return None
    return research_engine.load_research(results[0]["research_id"])


def _compose_chat_reply(
    message: str,
    context_label: str,
    context_summary: str,
    sources: list,
    history: list,
    strict_citations: bool = True,
):
    """Generate a grounded chat reply for research/news follow-ups."""
    source_lines = []
    content_budget = config.CONTENT_FETCH.get("prompt_content_budget", 15000)
    content_used = 0
    for source in sources[:20]:
        title = source.get("title") or source.get("headline") or "Untitled"
        source_type = source.get("source_type") or source.get("source") or "unknown"
        url = source.get("url", "")
        publication_date = str(source.get("publication_date") or source.get("date") or "")[:10]
        line = f"- {title} | {source_type} | {publication_date} | {url}"
        full_content = (source.get("content_full") or "").strip()
        snippet = (source.get("content_snippet") or "").strip()
        if full_content and content_used < content_budget:
            remaining = max(500, content_budget - content_used)
            truncated = full_content[:remaining]
            content_used += len(truncated)
            line += f"\n  Content: {truncated}"
        elif snippet and content_used < content_budget:
            truncated = snippet[:300]
            content_used += len(truncated)
            line += f"\n  Content: {truncated}"
        source_lines.append(line)

    history_lines = []
    for item in history[-8:]:
        role = "User" if item.get("role") == "user" else "Assistant"
        content = str(item.get("content", ""))[:900]
        if content:
            history_lines.append(f"{role}: {content}")

    strict_instructions = (
        "Primarily use provided context and sources. If evidence is insufficient, supplement with your own knowledge and clearly mark it as [Background Knowledge]."
        if strict_citations
        else "Prioritize provided context and sources; clearly label any inference beyond them."
    )

    today = date.today().isoformat()

    prompt = (
        f"Today's date is {today}.\n"
        "You are an evidence-grounded research assistant responding to a follow-up discussion prompt.\n"
        f"Context: {context_label}\n"
        f"Context summary:\n{context_summary[:4000]}\n\n"
        f"Source list:\n{chr(10).join(source_lines) if source_lines else '- No sources provided'}\n\n"
        f"Prior conversation:\n{chr(10).join(history_lines) if history_lines else '- No previous messages'}\n\n"
        f"User question: {message}\n\n"
        f"Rules: {strict_instructions}\n"
        "Keep response concise, cite sources inline using bracket format [Source Title].\n"
        f"Only cite facts present in the provided sources. Do NOT invent events, dates, or statistics. "
        f"Today is {today} — do not reference events after this date as established fact.\n"
    )

    try:
        model_config = config.SPECIALIZED_MODELS["reasoning"]
        client = create_specialist_client("reasoning", model_config)
        response = client.chat_complete(
            [
                {"role": "system", "content": "You provide grounded follow-up analysis with clear citations."},
                {"role": "user", "content": prompt},
            ],
            tools=None,
        )
        content = client.extract_content(response)
        if content and content.strip():
            return content.strip()
    except Exception as e:
        logger.warning(f"Chat reply fallback triggered: {e}")

    fallback = []
    if sources:
        fallback.append("Evidence available from current sources:")
        for source in sources[:4]:
            title = source.get("title") or source.get("headline") or "Untitled"
            fallback.append(f"- [{title}]")
    fallback.append("I could not run full synthesis; please retry this follow-up.")
    return "\n".join(fallback)


def _stream_reply_events(reply: str):
    """Yield SSE events that incrementally stream a reply."""
    chunk_size = 120
    for i in range(0, len(reply), chunk_size):
        delta = reply[i:i + chunk_size]
        payload = {"delta": delta, "done": False}
        yield f"data: {json.dumps(payload)}\n\n"
    yield f"data: {json.dumps({'delta': '', 'done': True})}\n\n"


@app.route('/health')
def health():
    """Health check endpoint for container orchestrators."""
    return jsonify({"status": "ok"})


@app.route('/')
def index():
    """Render main research UI"""
    return render_template('index.html')


def _run_research_with_progress(
    research_id: str,
    query: str,
    depth: int,
    refined_query: str = None,
    research_type: str = None,
    asset_metadata: dict = None,
):
    """Run research workflow in background thread and emit progress updates."""
    try:
        def on_progress(status: str, phase: str, message: str):
            research_progress[research_id] = {
                "status": status,
                "message": message,
                "phase": phase
            }

        profile = config.DEPTH_PROFILES.get(depth, config.DEPTH_PROFILES[1])

        state = run_deep_research(
            query=query,
            depth=depth,
            max_results_per_source=profile["max_results_per_source"],
            progress_callback=on_progress,
            refined_query=refined_query,
            research_type=research_type,
            asset_metadata=asset_metadata,
        )

        research_id_actual = research_engine.save_research(state)

        research_progress[research_id] = {
            "status": "completed",
            "message": f"Research complete! Found {state.total_sources} sources.",
            "phase": "complete",
            "results": build_results_payload(state, query, research_id=research_id_actual, max_sources=profile["max_sources"]),
        }
        
    except Exception as e:
        logger.error(f"Research error: {e}", exc_info=True)
        research_progress[research_id] = {
            "status": "error",
            "message": f"Error: {str(e)}",
            "phase": "error"
        }


@app.route('/api/research/refine', methods=['POST'])
def refine_research_query():
    """Analyze a research query and return structured refinement suggestions."""
    try:
        data = request.get_json()
        query = (data.get('query') or '').strip()
        if not query:
            return jsonify({"error": "Query is required"}), 400

        result = refine_query(query)
        return jsonify(result)
    except Exception as e:
        logger.warning(f"Query refinement error (non-fatal): {e}")
        return jsonify({
            "status": "well_specified",
            "original_query": query,
            "dimensions": {"topic": {"detected": True, "value": query}},
            "gaps": [],
            "refined_query": query,
            "skip_refinement": True,
        })


@app.route('/api/research', methods=['POST'])
def start_research():
    """
    Start deep research workflow (async with progress tracking).
    
    Request body:
    {
        "query": str,
        "depth": int (1-3, default: 1)
    }
    
    Returns:
    {
        "research_id": str,
        "status": "started",
        "query": str
    }
    """
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        depth = int(data.get('depth', 1))
        refined_query = (data.get('refined_query') or '').strip() or None
        research_type = (data.get('research_type') or '').strip() or None
        asset_metadata = data.get('asset_metadata') or None
        if not research_type:
            research_type = infer_research_type(refined_query or query)

        if not query:
            return jsonify({"error": "Query is required"}), 400
        
        if depth not in [1, 2, 3]:
            return jsonify({"error": "Depth must be 1, 2, or 3"}), 400
        
        logger.info(f"Starting research: {query} (depth={depth})")
        
        # Generate unique research ID for progress tracking
        research_id = str(uuid.uuid4())
        
        # Initialize progress
        research_progress[research_id] = {
            "status": "starting",
            "message": "Initializing research workflow...",
            "phase": "init"
        }
        
        # Start research in background thread
        thread = threading.Thread(
            target=_run_research_with_progress,
            args=(research_id, query, depth),
            kwargs={
                "refined_query": refined_query,
                "research_type": research_type,
                "asset_metadata": asset_metadata,
            },
            daemon=True
        )
        thread.start()
        
        return jsonify({
            "research_id": research_id,
            "status": "started",
            "query": query,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "strict_citations_default": False,
        })
        
    except Exception as e:
        logger.error(f"Research error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/research/<research_id>/progress', methods=['GET'])
def get_research_progress(research_id):
    """
    Get progress updates for research (Server-Sent Events).
    
    Returns:
    SSE stream with progress updates
    """
    def generate():
        """Generate SSE events for progress updates."""
        import time
        last_status = None
        last_message = None
        
        while True:
            if research_id not in research_progress:
                yield f"data: {json.dumps({'error': 'Research not found'})}\n\n"
                break
            
            progress = research_progress[research_id]
            status = progress.get("status")
            message = progress.get("message")
            
            # Send update if status or message changed
            if status != last_status or message != last_message:
                yield f"data: {json.dumps(progress)}\n\n"
                last_status = status
                last_message = message
                
                # Close connection if completed or error
                if status in ["completed", "error"]:
                    break
            
            time.sleep(0.5)  # Poll every 500ms
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'  # Disable nginx buffering
        }
    )


@app.route('/api/research/<research_id>', methods=['GET'])
def get_research(research_id):
    """
    Get research results by ID.
    
    Returns:
    {
        "research_id": str,
        "query": str,
        "synthesis": str,
        "sources": [...],
        ...
    }
    """
    try:
        research_data = _load_research_by_id(research_id)
        if not research_data:
            return jsonify({"error": "Research data not found"}), 404
        
        return jsonify(research_data)
        
    except Exception as e:
        logger.error(f"Get research error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/research/<research_id>/chat', methods=['POST'])
def research_chat(research_id):
    """Follow-up chat for a research session."""
    try:
        data = request.get_json() or {}
        message = (data.get("message") or "").strip()
        if not message:
            return jsonify({"error": "message is required"}), 400

        strict_citations = bool(data.get("strict_citations", False))
        history = data.get("history") or []
        selected_source_ids = set(data.get("selected_source_ids") or [])

        research_data = _load_research_by_id(research_id)
        if not research_data:
            return jsonify({"error": "Research not found"}), 404

        original_query = research_data.get("query") or research_data.get("original_query") or "research query"
        synthesis = research_data.get("synthesis") or ""
        sources = research_data.get("sources") or []

        # On-demand content fetch for older sessions without content_full (SEP-005)
        try:
            cf = config.CONTENT_FETCH
            if cf.get("enabled", False):
                missing = [s for s in sources if s.get("url") and not s.get("content_full")]
                if missing:
                    from engine.models import Source as _Source
                    from tools.utils._content_extractor import ContentExtractor
                    source_objs = []
                    obj_map = {}
                    for sd in missing:
                        obj = _Source(
                            source_id=sd.get("source_id", ""),
                            url=sd.get("url", ""),
                            title=sd.get("title", ""),
                            source_type=sd.get("source_type", ""),
                            credibility_score=sd.get("credibility_score", 0.0),
                        )
                        source_objs.append(obj)
                        obj_map[id(obj)] = sd
                    extractor = ContentExtractor(enabled=True)
                    extractor.fetch_content_for_sources(
                        source_objs,
                        max_sources=cf.get("max_sources", 20),
                        timeout_per_url=cf.get("timeout_per_url", 10),
                        skip_types=cf.get("skip_types", ["academic"]),
                        max_workers=cf.get("max_workers", 8),
                    )
                    for obj in source_objs:
                        if obj.content_full:
                            obj_map[id(obj)]["content_full"] = obj.content_full
        except Exception as e:
            logger.warning(f"On-demand content fetch failed (non-fatal): {e}")

        if selected_source_ids:
            scoped_sources = [s for s in sources if (s.get("source_id") in selected_source_ids)]
        else:
            scoped_sources = sources

        context_summary = f"Query: {original_query}\n\nSynthesis:\n{synthesis}"
        reply = _compose_chat_reply(
            message=message,
            context_label=f"Deep Research ({research_id})",
            context_summary=context_summary,
            sources=scoped_sources,
            history=history,
            strict_citations=strict_citations,
        )

        thread_key = f"research:{research_id}"
        thread = chat_threads.setdefault(thread_key, [])
        thread.append({"role": "user", "content": message, "at": datetime.now(timezone.utc).isoformat()})
        thread.append({"role": "assistant", "content": reply, "at": datetime.now(timezone.utc).isoformat()})
        try:
            _local_storage.append_chat_turn(thread_key, "user", message)
            _local_storage.append_chat_turn(thread_key, "assistant", reply)
        except Exception as _e:
            logger.warning(f"Chat history persistence failed (non-fatal): {_e}")

        if bool(data.get("stream", False)):
            return Response(
                stream_with_context(_stream_reply_events(reply)),
                mimetype='text/event-stream',
                headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
            )

        return jsonify(
            {
                "reply": reply,
                "mode": "evidence" if strict_citations else "advisory",
                "used_source_ids": [s.get("source_id") for s in scoped_sources[:8] if s.get("source_id")],
                "thread_size": len(thread),
                "source_count": len(scoped_sources),
                "strict_citations": strict_citations,
                "used_background_knowledge": "[Background Knowledge]" in reply,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"Research chat error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/research/<research_id>/chat/<message_id>/feedback', methods=['POST'])
def research_chat_feedback(research_id, message_id):
    """Persist thumbs up/down feedback for a research chat message (SEP-059)."""
    try:
        data = request.get_json() or {}
        rating = data.get("rating")
        if rating not in ("up", "down"):
            return jsonify({"error": "rating must be 'up' or 'down'"}), 400
        _local_storage.save_feedback(
            research_id=research_id,
            message_id=message_id,
            rating=rating,
        )
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Feedback save error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/research/<research_id>/chat/history', methods=['GET'])
def research_chat_history(research_id):
    """Return persisted chat history for a research session (SEP-059)."""
    try:
        thread_key = f"research:{research_id}"
        rows = _local_storage.load_chat_thread(thread_key)
        history = [
            {"role": r["role"], "content": r["content"], "at": r.get("created_at", "")}
            for r in rows
        ]
        return jsonify({"history": history})
    except Exception as e:
        logger.error(f"Chat history load error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/news-intel/facets', methods=['GET'])
def get_news_intel_facets():
    """Return available topics, sources, and date range from cached articles."""
    try:
        from collections import Counter

        articles = fetch_newsroom_api(max_results=5000)

        topic_counts = Counter()
        source_counts = Counter()
        dates = []

        for article in articles:
            for tag in (article.get("topic_tags") or []):
                topic_counts[tag] += 1
            src = article.get("source")
            if src:
                source_counts[src] += 1
            d = (article.get("date") or "")[:10]
            if d:
                dates.append(d)

        topics = [{"name": name, "count": count}
                  for name, count in topic_counts.most_common()]
        sources = [{"name": name, "count": count}
                   for name, count in source_counts.most_common()]
        date_range = {
            "min": min(dates) if dates else None,
            "max": max(dates) if dates else None,
        }

        return jsonify({"topics": topics, "sources": sources, "date_range": date_range})
    except Exception as e:
        logger.error(f"News intel facets error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/news-intel/articles', methods=['POST'])
def get_news_intel_articles():
    """Fetch newsroom articles from API and filter by topic/date range."""
    try:
        data = request.get_json() or {}
        topic = (data.get("topic") or "").strip()
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        limit = int(data.get("limit", 200))
        limit = max(1, min(limit, 10000))
        offset = int(data.get("offset", 0))
        offset = max(0, offset)

        start_date = _parse_date(date_from)
        end_date = _parse_date(date_to)
        if start_date and end_date and start_date > end_date:
            return jsonify({"error": "date_from must be <= date_to"}), 400

        articles = fetch_newsroom_api()
        warning = newsroom_api_warning
        filtered = _filter_newsroom_articles(
            articles,
            topic=topic,
            date_from=date_from,
            date_to=date_to,
            limit=100000,
        )

        total_count = len(filtered)
        page = filtered[offset:offset + limit]

        serialized = [
            {
                "headline": article.get("headline", "Untitled"),
                "date": article.get("date", ""),
                "source": article.get("source", "Unknown"),
                "url": article.get("url", ""),
                "topic_tags": article.get("topic_tags", []),
                "geography_tags": article.get("geography_tags", []),
                "country_tags": article.get("country_tags", []),
            }
            for article in page
        ]
        return jsonify({"count": len(serialized), "total_count": total_count, "offset": offset, "articles": serialized, "warning": warning})
    except Exception as e:
        logger.error(f"News intel articles error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/news-intel/synthesize', methods=['POST'])
def synthesize_news_intel():
    """Synthesize filtered newsroom articles fetched via newsroom API."""
    try:
        data = request.get_json() or {}
        topic = (data.get("topic") or "").strip()
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        limit = int(data.get("limit", 200))
        limit = max(1, min(limit, 10000))

        start_date = _parse_date(date_from)
        end_date = _parse_date(date_to)
        if start_date and end_date and start_date > end_date:
            return jsonify({"error": "date_from must be <= date_to"}), 400

        articles = fetch_newsroom_api()
        filtered = _filter_newsroom_articles(
            articles,
            topic=topic,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
        # Merge staged articles from client
        staged_articles = data.get("staged_articles") or []
        if staged_articles:
            filtered = staged_articles + filtered
        synthesis = _news_intel_synthesis(filtered, topic=topic, date_from=date_from, date_to=date_to)

        return jsonify(
            {
                "topic": topic,
                "date_from": date_from,
                "date_to": date_to,
                "count": len(filtered),
                "synthesis": synthesis,
                "articles": [
                    {
                        "headline": article.get("headline", "Untitled"),
                        "date": article.get("date", ""),
                        "source": article.get("source", "Unknown"),
                        "url": article.get("url", ""),
                        "topic_tags": article.get("topic_tags", []),
                    }
                    for article in filtered
                ],
            }
        )
    except Exception as e:
        logger.error(f"News intel synthesis error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/news-intel/chat', methods=['POST'])
def news_intel_chat():
    """Follow-up chat for a news-intel synthesis session."""
    try:
        data = request.get_json() or {}
        message = (data.get("message") or "").strip()
        if not message:
            return jsonify({"error": "message is required"}), 400

        topic = (data.get("topic") or "").strip()
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        strict_citations = bool(data.get("strict_citations", True))
        history = data.get("history") or []
        articles = data.get("articles") or []
        synthesis = data.get("synthesis") or ""
        session_id = (data.get("session_id") or "").strip() or f"{topic}:{date_from}:{date_to}"

        if not articles:
            return jsonify({"error": "articles are required for news-intel chat context"}), 400

        context_summary = (
            f"Topic: {topic or 'All'}\nDate From: {date_from or 'Any'}\nDate To: {date_to or 'Any'}\n\n"
            f"Synthesis:\n{synthesis}"
        )
        reply = _compose_chat_reply(
            message=message,
            context_label=f"News Intel ({session_id})",
            context_summary=context_summary,
            sources=articles,
            history=history,
            strict_citations=strict_citations,
        )

        thread_key = f"news:{session_id}"
        thread = chat_threads.setdefault(thread_key, [])
        thread.append({"role": "user", "content": message, "at": datetime.now(timezone.utc).isoformat()})
        thread.append({"role": "assistant", "content": reply, "at": datetime.now(timezone.utc).isoformat()})

        if bool(data.get("stream", False)):
            return Response(
                stream_with_context(_stream_reply_events(reply)),
                mimetype='text/event-stream',
                headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
            )

        return jsonify(
            {
                "reply": reply,
                "mode": "evidence" if strict_citations else "advisory",
                "thread_size": len(thread),
                "source_count": len(articles),
                "strict_citations": strict_citations,
                "used_background_knowledge": "[Background Knowledge]" in reply,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"News intel chat error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/news-intel/stats', methods=['POST'])
def get_news_intel_stats():
    """Aggregate articles by normalized country for map display."""
    try:
        data = request.get_json() or {}
        topic = (data.get("topic") or "").strip()
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        limit = int(data.get("limit", 10000))
        limit = max(1, min(limit, 10000))

        articles, warning = fetch_newsroom_cached(max_results=10000)
        filtered = _filter_newsroom_articles(
            articles, topic=topic, date_from=date_from, date_to=date_to, limit=limit,
        )

        country_agg = {}
        geo_tagged = 0
        for article in filtered:
            tags = article.get("country_tags") or []
            if tags:
                geo_tagged += 1
            for raw_tag in tags:
                country = normalize_country(raw_tag.strip())
                if not country:
                    continue
                if country not in country_agg:
                    country_agg[country] = {"count": 0, "topics": {}, "sources": {}}
                entry = country_agg[country]
                entry["count"] += 1
                for t in (article.get("topic_tags") or [])[:4]:
                    entry["topics"][t] = entry["topics"].get(t, 0) + 1
                src = article.get("source", "Unknown")
                entry["sources"][src] = entry["sources"].get(src, 0) + 1

        stats = [
            {"country": c, "count": v["count"], "topics": v["topics"], "sources": v["sources"]}
            for c, v in sorted(country_agg.items(), key=lambda x: x[1]["count"], reverse=True)
        ]

        return jsonify({
            "total_articles": len(filtered),
            "geo_tagged_articles": geo_tagged,
            "stats": stats,
            "warning": warning,
        })
    except Exception as e:
        logger.error(f"News intel stats error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/alerts', methods=['POST'])
def create_alert():
    """Create a recurring digest alert from current Digest state."""
    try:
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        interval = (data.get("interval") or "daily").strip().lower()
        if not name:
            return jsonify({"error": "name is required"}), 400
        if interval not in {"daily", "weekly"}:
            return jsonify({"error": "interval must be daily or weekly"}), 400

        store = AlertStore()
        alert_id = store.create_alert(
            name=name,
            topic=(data.get("topic") or "").strip(),
            date_window_days=int(data.get("date_window_days", 7)),
            article_limit=int(data.get("article_limit", 100)),
            staged_series=data.get("staged_series") or [],
            interval=interval,
        )
        store.close()
        return jsonify({"alert_id": alert_id, "status": "created"})
    except Exception as e:
        logger.error(f"Create alert error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/alerts', methods=['GET'])
def list_alerts():
    """List recurring digest alerts."""
    try:
        store = AlertStore()
        alerts = store.list_alerts()
        store.close()
        return jsonify({"alerts": alerts, "unread_total": sum(alert.get("unread_count", 0) for alert in alerts)})
    except Exception as e:
        logger.error(f"List alerts error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/alerts/<alert_id>/results', methods=['GET'])
def get_alert_results(alert_id):
    """Return paginated alert results."""
    try:
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
        store = AlertStore()
        results = store.get_results(alert_id, limit=limit, offset=offset)
        store.close()
        return jsonify({"results": results})
    except Exception as e:
        logger.error(f"Get alert results error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/alerts/<alert_id>', methods=['PATCH'])
def update_alert(alert_id):
    """Update alert settings."""
    try:
        data = request.get_json() or {}
        updates = {}
        for key in ("name", "topic", "date_window_days", "article_limit", "interval", "enabled", "last_run_at"):
            if key in data:
                updates[key] = data[key]
        if "staged_series" in data:
            updates["staged_series"] = data["staged_series"]
        store = AlertStore()
        store.update_alert(alert_id, **updates)
        alert = store.get_alert(alert_id)
        store.close()
        return jsonify({"status": "updated", "alert": alert})
    except Exception as e:
        logger.error(f"Update alert error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/alerts/<alert_id>', methods=['DELETE'])
def delete_alert(alert_id):
    """Delete an alert and its results."""
    try:
        store = AlertStore()
        store.delete_alert(alert_id)
        store.close()
        return jsonify({"status": "deleted"})
    except Exception as e:
        logger.error(f"Delete alert error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/alerts/<alert_id>/read', methods=['POST'])
def mark_alert_read(alert_id):
    """Mark all alert results as read."""
    try:
        store = AlertStore()
        store.mark_all_read(alert_id)
        store.close()
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Mark alert read error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/market/latest', methods=['GET'])
def get_market_latest():
    """Return latest observation per series from MarketDataStore."""
    import time as _time
    global _market_latest_cache
    if _market_latest_cache is not None:
        cached_at, cached_data = _market_latest_cache
        if _time.time() - cached_at < _MARKET_CACHE_TTL:
            return jsonify(cached_data)
    try:
        store = MarketDataStore()
        results = []
        for sid, series in SERIES_CATALOG.items():
            try:
                df = store.get_series_df(sid, provider=series.provider)
                if df.empty:
                    continue
                latest_val = float(df["value"].iloc[-1])
                latest_date = str(df.index[-1].date())
                prev_val = float(df["value"].iloc[-2]) if len(df) >= 2 else None
                pct_change = None
                if prev_val and prev_val != 0:
                    pct_change = round(((latest_val - prev_val) / abs(prev_val)) * 100, 2)
                # Compute freshness from fetch_metadata
                staleness_hours = store.get_staleness(sid, provider=series.provider)
                last_fetched = None
                # Only compute last_fetched when staleness_hours is numeric
                if isinstance(staleness_hours, (int, float)):
                    from datetime import datetime, timedelta
                    last_fetched = (datetime.utcnow() - timedelta(hours=staleness_hours)).isoformat() + "Z"

                results.append({
                    "series_id": sid,
                    "name": series.label,
                    "group": series.group,
                    "unit": series.unit,
                    "source": series.provider,
                    "latest_value": latest_val,
                    "latest_date": latest_date,
                    "prev_value": prev_val,
                    "pct_change": pct_change,
                    "last_fetched": last_fetched,
                })
            except Exception as e:
                logger.debug(f"Skipping series {sid}: {e}")
        store.close()
        _market_latest_cache = (_time.time(), results)
        return jsonify(results)
    except Exception as e:
        logger.error(f"Market latest error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/market/refresh', methods=['POST'])
def refresh_market_data_all():
    """Force-refresh all market data immediately."""
    try:
        from workflows.market_workflow import MarketWorkflow
        wf = MarketWorkflow()
        count = wf.update_all(force=True)
        return jsonify({"status": "ok", "updated": count})
    except Exception as e:
        logger.error(f"Market refresh error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def _strip_bulk_fields(items, extra_keys=()):
    """Remove *_json bulk fields and any extra keys from response dicts."""
    strip = {"properties_json", "metadata_json", "mapping_json"} | set(extra_keys)
    return [{k: v for k, v in item.items() if k not in strip} for item in items]


@app.route('/api/regulatory/rps', methods=['GET'])
def get_regulatory_rps():
    """Return parsed RPS/CES targets with optional state/year filters."""
    try:
        state = request.args.get("state")
        year = request.args.get("year", type=int)
        standard_type = request.args.get("standard_type")
        limit = request.args.get("limit", type=int)
        store = RegulatoryDataStore()
        items = store.get_rps_targets(state=state, year=year, standard_type=standard_type)
        store.close()
        total = len(items)
        if limit is not None:
            items = items[:limit]
        return jsonify({"count": total, "items": _strip_bulk_fields(items)})
    except Exception as e:
        logger.error(f"Regulatory RPS error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/regulatory/eia/capacity', methods=['GET'])
def get_regulatory_capacity():
    """Return EIA operating generator capacity rows."""
    try:
        state = request.args.get("state")
        fuel_type = request.args.get("fuel_type")
        limit = request.args.get("limit", type=int)
        store = RegulatoryDataStore()
        items = store.get_eia_series("operating-generator-capacity", state=state, fuel_type=fuel_type)
        store.close()
        total = len(items)
        if limit is not None:
            items = items[:limit]
        return jsonify({"count": total, "items": _strip_bulk_fields(items)})
    except Exception as e:
        logger.error(f"Regulatory capacity error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/regulatory/eia/generation', methods=['GET'])
def get_regulatory_generation():
    """Return EIA generation rows from operational data."""
    try:
        state = request.args.get("state")
        fuel_type = request.args.get("fuel_type")
        limit = request.args.get("limit", type=int)
        store = RegulatoryDataStore()
        items = store.get_eia_series("electric-power-operational-data", state=state, fuel_type=fuel_type)
        store.close()
        total = len(items)
        if limit is not None:
            items = items[:limit]
        return jsonify({"count": total, "items": _strip_bulk_fields(items)})
    except Exception as e:
        logger.error(f"Regulatory generation error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/regulatory/rates', methods=['GET'])
def get_regulatory_rates():
    """Return stored utility rate records."""
    try:
        state = request.args.get("state")
        sector = request.args.get("sector")
        limit = request.args.get("limit", type=int)
        store = RegulatoryDataStore()
        items = store.get_utility_rates(state=state, sector=sector)
        store.close()
        total = len(items)
        if limit is not None:
            items = items[:limit]
        return jsonify({"count": total, "items": _strip_bulk_fields(items)})
    except Exception as e:
        logger.error(f"Regulatory rates error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/regulatory/events', methods=['GET'])
def get_regulatory_events():
    """Return structured regulatory events."""
    try:
        jurisdiction = request.args.get("jurisdiction")
        event_type = request.args.get("event_type")
        source_system = request.args.get("source_system")
        limit = request.args.get("limit", type=int)
        store = RegulatoryDataStore()
        query_args = {}
        if jurisdiction:
            query_args["jurisdiction"] = jurisdiction
        if event_type:
            query_args["event_type"] = event_type
        if source_system:
            query_args["source_system"] = source_system
        items = store.get_regulatory_events(**query_args)
        store.close()
        total = len(items)
        if limit is not None:
            items = items[:limit]
        return jsonify({"count": total, "items": _strip_bulk_fields(items)})
    except Exception as e:
        logger.error(f"Regulatory events error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/regulatory/provenance', methods=['GET'])
def get_regulatory_provenance():
    """Return raw-document and transform-run provenance for regulatory event sources."""
    try:
        jurisdiction = request.args.get("jurisdiction")
        source_system = request.args.get("source_system")
        store = RegulatoryDataStore()
        query_args = {}
        if jurisdiction:
            query_args["jurisdiction"] = jurisdiction
        if source_system:
            query_args["source_system"] = source_system
        raw_documents = store.get_raw_documents(**query_args)
        transform_runs = store.get_transform_runs(**query_args)
        store.close()
        return jsonify({
            "raw_documents": _strip_bulk_fields(raw_documents, extra_keys=("payload_text",)),
            "transform_runs": _strip_bulk_fields(transform_runs),
            "raw_document_count": len(raw_documents),
            "transform_run_count": len(transform_runs),
        })
    except Exception as e:
        logger.error(f"Regulatory provenance error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/regulatory/refresh', methods=['POST'])
def refresh_regulatory_data():
    """Force-refresh regulatory ingest sources."""
    try:
        workflow = RegulatoryWorkflow()
        updated = workflow.update_all(force=True)
        return jsonify({"status": "ok", "updated_sources": updated})
    except Exception as e:
        logger.error(f"Regulatory refresh error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Brownfield pipeline endpoints
# ---------------------------------------------------------------------------

@app.route('/api/pipeline/assets', methods=['GET'])
def list_pipeline_assets():
    """List brownfield acquisition pipeline assets."""
    try:
        technology = request.args.get("technology")
        country = request.args.get("country")
        store = ImagingDataStore()
        items = store.list_pipeline_assets(technology=technology, country=country)
        store.close()
        return jsonify({"items": items, "count": len(items)})
    except Exception as e:
        logger.error(f"Pipeline list error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/pipeline/assets', methods=['POST'])
def create_pipeline_asset():
    """Persist a generation or deposit asset into the brownfield pipeline."""
    try:
        data = request.get_json() or {}
        source_type = (data.get("source_type") or "").strip()
        asset = data.get("asset") or {}
        if not source_type:
            return jsonify({"error": "source_type is required"}), 400
        if not asset:
            return jsonify({"error": "asset is required"}), 400

        store = ImagingDataStore()
        saved = store.upsert_pipeline_asset(source_type=source_type, asset=asset)
        store.close()
        return jsonify({"status": "ok", "asset": saved})
    except Exception as e:
        logger.error(f"Pipeline create error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/pipeline/assets/<asset_id>', methods=['DELETE'])
def delete_pipeline_asset(asset_id):
    """Delete a brownfield pipeline asset."""
    try:
        store = ImagingDataStore()
        store.delete_pipeline_asset(asset_id)
        store.close()
        return jsonify({"status": "deleted"})
    except Exception as e:
        logger.error(f"Pipeline delete error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Scouting kanban endpoints (SEP-044)
# ---------------------------------------------------------------------------

VALID_SCOUTING_TYPES = {"brownfield", "greenfield", "bess"}
VALID_SCOUTING_STAGES = {"identified", "scored", "feasibility", "diligence", "decision"}


@app.route('/api/scouting/items', methods=['GET'])
def list_scouting_items():
    """List scouting kanban items by type, optionally filtered by stage."""
    try:
        item_type = (request.args.get("type") or "").strip()
        if item_type not in VALID_SCOUTING_TYPES:
            return jsonify({"error": f"type must be one of {sorted(VALID_SCOUTING_TYPES)}"}), 400
        stage = request.args.get("stage")
        store = ImagingDataStore()
        items = store.list_scouting_items(item_type, stage=stage)
        store.close()
        return jsonify({"items": items, "count": len(items)})
    except Exception as e:
        logger.error(f"Scouting list error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/scouting/items/<item_id>/stage', methods=['PUT'])
def update_scouting_item_stage(item_id):
    """Move a scouting item to a different pipeline stage."""
    try:
        data = request.get_json(silent=True) or {}
        item_type = (data.get("type") or "").strip()
        stage = (data.get("stage") or "").strip()
        if not item_type:
            return jsonify({"error": "type is required"}), 400
        if not stage:
            return jsonify({"error": "stage is required"}), 400
        if item_type not in VALID_SCOUTING_TYPES:
            return jsonify({"error": f"type must be one of {sorted(VALID_SCOUTING_TYPES)}"}), 400
        if stage not in VALID_SCOUTING_STAGES:
            return jsonify({"error": f"stage must be one of {sorted(VALID_SCOUTING_STAGES)}"}), 400
        store = ImagingDataStore()
        store.update_scouting_stage(item_type, item_id, stage)
        if item_type == "greenfield":
            item = store.get_watchlist_site(item_id)
        else:
            item = store.get_pipeline_asset(item_id)
        store.close()
        return jsonify({"status": "ok", "item": item})
    except Exception as e:
        logger.error(f"Scouting stage update error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def _compute_greenfield_score(
    store: ImagingDataStore,
    lat: float,
    lon: float,
    technology: str,
    name: str | None = None,
    country: str | None = None,
) -> dict:
    """Run greenfield rubric using DB-backed generation and pipeline lists."""
    resource_summary = fetch_resource_summary(lat=lat, lon=lon)
    generation_assets = store.get_generation_assets().get("features", [])
    pipeline_assets = store.list_pipeline_assets()
    return score_site(
        lat=lat,
        lon=lon,
        technology=technology,
        resource_summary=resource_summary,
        generation_assets=generation_assets,
        pipeline_assets=pipeline_assets,
        name=name,
        country=country,
    )


def _scoring_snapshot_from_site(site: dict) -> dict:
    out = {}
    for key in (
        "overall_score",
        "score_label",
        "strength_tier",
        "factors",
        "resource_summary",
        "known_factor_count",
        "unknown_factor_count",
        "rubric_earned",
        "rubric_possible",
        "diligence_screening",
    ):
        if key in site:
            out[key] = site[key]
    return out


@app.route("/api/scouting/items/<item_id>/score-preview", methods=["POST"])
def score_preview_scouting_item(item_id):
    """Compute scoring payload for a kanban item without persisting."""
    try:
        data = request.get_json(silent=True) or {}
        item_type = (data.get("type") or "").strip()
        if item_type not in VALID_SCOUTING_TYPES:
            return (
                jsonify(
                    {"error": f"type must be one of {sorted(VALID_SCOUTING_TYPES)}"}
                ),
                400,
            )
        technology_override = (data.get("technology") or "").strip().lower()
        store = ImagingDataStore()
        try:
            if item_type == "greenfield":
                row = store.get_watchlist_site(item_id)
                if not row:
                    return jsonify({"error": "not found"}), 404
                tech = technology_override or (row.get("technology") or "").strip().lower()
                if not tech:
                    return jsonify({"error": "technology is required"}), 400
                site = _compute_greenfield_score(
                    store,
                    float(row["lat"]),
                    float(row["lon"]),
                    tech,
                    row.get("name"),
                    row.get("country"),
                )
                site["id"] = row["id"]
                site["notes"] = row.get("notes") or ""
                return jsonify({"site": site})

            row = store.get_pipeline_asset(item_id)
            if not row:
                return jsonify({"error": "not found"}), 404

            if item_type == "bess":
                if row.get("source_type") != "bess":
                    return jsonify({"error": "item is not a BESS pipeline row"}), 400
                lat, lon = float(row["lat"]), float(row["lon"])
                site = score_bess_site(
                    lat,
                    lon,
                    row.get("asset_name"),
                    row.get("country"),
                )
            elif item_type == "brownfield":
                if row.get("source_type") == "bess":
                    return jsonify({"error": "use type bess for this item"}), 400
                tech = technology_override or (row.get("technology") or "").strip().lower()
                if not tech:
                    return jsonify({"error": "technology is required"}), 400
                site = _compute_greenfield_score(
                    store,
                    float(row["lat"]),
                    float(row["lon"]),
                    tech,
                    row.get("asset_name"),
                    row.get("country"),
                )
            else:
                return jsonify({"error": "unsupported type"}), 400

            site["id"] = row["id"]
            site["notes"] = row.get("notes") or ""
            return jsonify({"site": site})
        finally:
            store.close()
    except Exception as e:
        logger.error(f"Scouting score-preview error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/scouting/items/<item_id>/apply-score", methods=["POST"])
def apply_scouting_score(item_id):
    """Persist score-preview output and set scouting_stage to scored."""
    try:
        data = request.get_json(silent=True) or {}
        item_type = (data.get("type") or "").strip()
        site = data.get("site")
        if not item_type or item_type not in VALID_SCOUTING_TYPES:
            return (
                jsonify(
                    {"error": f"type must be one of {sorted(VALID_SCOUTING_TYPES)}"}
                ),
                400,
            )
        if not isinstance(site, dict):
            return jsonify({"error": "site object is required"}), 400
        if site.get("id") != item_id:
            return jsonify({"error": "site.id must match URL item id"}), 400

        store = ImagingDataStore()
        try:
            if item_type == "greenfield":
                to_save = dict(site)
                to_save["scouting_stage"] = "scored"
                saved = store.upsert_watchlist_site(to_save)
            else:
                snapshot = _scoring_snapshot_from_site(site)
                store.save_pipeline_scouting_score(item_id, snapshot)
                store.update_scouting_stage(item_type, item_id, "scored")
                saved = store.get_pipeline_asset(item_id)
        finally:
            store.close()
        return jsonify({"status": "ok", "item": saved})
    except Exception as e:
        logger.error(f"Scouting apply-score error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/scouting/items', methods=['POST'])
def create_scouting_item():
    """Create a scouting item via the unified endpoint."""
    try:
        data = request.get_json() or {}
        item_type = (data.get("type") or "").strip()
        if item_type not in VALID_SCOUTING_TYPES:
            return jsonify({"error": f"type must be one of {sorted(VALID_SCOUTING_TYPES)}"}), 400
        store = ImagingDataStore()
        if item_type == "greenfield":
            site = data.get("site") or {}
            if not site:
                return jsonify({"error": "site is required for greenfield"}), 400
            saved = store.upsert_watchlist_site(site)
            store.close()
            return jsonify({"status": "ok", "item": saved})
        else:
            source_type = (data.get("source_type") or item_type).strip()
            asset = data.get("asset") or {}
            if not asset:
                return jsonify({"error": "asset is required"}), 400
            saved = store.upsert_pipeline_asset(source_type=source_type, asset=asset)
            store.close()
            return jsonify({"status": "ok", "item": saved})
    except Exception as e:
        logger.error(f"Scouting create error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/scouting/items/<item_id>', methods=['GET', 'DELETE'])
def scouting_item_get_or_delete(item_id):
    """Fetch one scouting item (GET) or delete it (DELETE)."""
    try:
        item_type = (request.args.get("type") or "").strip()
        if not item_type:
            return jsonify({"error": "type query parameter is required"}), 400
        if item_type not in VALID_SCOUTING_TYPES:
            return jsonify({"error": f"type must be one of {sorted(VALID_SCOUTING_TYPES)}"}), 400
        store = ImagingDataStore()
        try:
            if request.method == "GET":
                if item_type == "greenfield":
                    item = store.get_watchlist_site(item_id)
                else:
                    item = store.get_pipeline_asset(item_id)
                if not item:
                    return jsonify({"error": "not found"}), 404
                return jsonify({"item": item})
            if item_type == "greenfield":
                store.delete_watchlist_site(item_id)
            else:
                store.delete_pipeline_asset(item_id)
            return jsonify({"status": "deleted"})
        finally:
            store.close()
    except Exception as e:
        logger.error(f"Scouting item {request.method} error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/scouting/items/<item_id>/notes', methods=['PATCH'])
def patch_scouting_item_notes(item_id):
    """Update team notes for a greenfield watchlist site or pipeline/bess asset."""
    try:
        data = request.get_json(silent=True) or {}
        item_type = (data.get("type") or "").strip()
        notes = data.get("notes")
        if notes is None:
            notes = ""
        if not isinstance(notes, str):
            return jsonify({"error": "notes must be a string"}), 400
        if item_type not in VALID_SCOUTING_TYPES:
            return jsonify({"error": f"type must be one of {sorted(VALID_SCOUTING_TYPES)}"}), 400
        store = ImagingDataStore()
        try:
            if item_type == "greenfield":
                if not store.get_watchlist_site(item_id):
                    return jsonify({"error": "not found"}), 404
                store.update_watchlist_notes(item_id, notes)
                item = store.get_watchlist_site(item_id)
            else:
                if not store.get_pipeline_asset(item_id):
                    return jsonify({"error": "not found"}), 404
                store.update_pipeline_notes(item_id, notes)
                item = store.get_pipeline_asset(item_id)
            return jsonify({"status": "ok", "item": item})
        finally:
            store.close()
    except Exception as e:
        logger.error(f"Scouting notes patch error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Feasibility study endpoints (SEP-045)
# ---------------------------------------------------------------------------

FEASIBILITY_TABS = {"production", "trading", "grid", "regulatory", "financial"}


@app.route('/api/scouting/items/<item_id>/feasibility', methods=['GET'])
def get_feasibility_all(item_id):
    """Return all tab results and progress for a scouting item."""
    try:
        store = ImagingDataStore()
        results = store.get_feasibility_results(item_id)
        progress = store.get_feasibility_progress(item_id)
        store.close()
        return jsonify({"results": results, "progress": progress})
    except Exception as e:
        logger.error(f"Feasibility get all error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/scouting/items/<item_id>/feasibility/<tab>', methods=['GET'])
def get_feasibility_tab(item_id, tab):
    """Return a single tab result or 404 if not yet run."""
    if tab not in FEASIBILITY_TABS:
        return jsonify({"error": f"tab must be one of {sorted(FEASIBILITY_TABS)}"}), 400
    try:
        store = ImagingDataStore()
        result = store.get_feasibility_result(item_id, tab)
        store.close()
        if result is None:
            return jsonify({"error": f"Tab '{tab}' has not been run for item '{item_id}'"}), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Feasibility get tab error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/scouting/items/<item_id>/feasibility/<tab>', methods=['POST'])
def run_feasibility_tab_endpoint(item_id, tab):
    """Run a feasibility tab analysis, persist result, and return it."""
    if tab not in FEASIBILITY_TABS:
        return jsonify({"error": f"tab must be one of {sorted(FEASIBILITY_TABS)}"}), 400
    try:
        data = request.get_json(silent=True) or {}
        item_type = (data.get("item_type") or "brownfield").strip()

        store = ImagingDataStore()

        # Retrieve item data to pass to workflow
        item_data = {}
        if item_type == "greenfield":
            item = store.get_watchlist_site(item_id)
        else:
            item = store.get_pipeline_asset(item_id)

        if item:
            if item_type == "greenfield":
                item_data = {
                    "asset_name": item.get("name", ""),
                    "technology": item.get("technology", ""),
                    "country": item.get("country", ""),
                    "lat": item.get("lat"),
                    "lon": item.get("lon"),
                    "capacity_mw": 0,
                }
            else:
                item_data = {
                    "asset_name": item.get("asset_name", ""),
                    "technology": item.get("technology", ""),
                    "capacity_mw": item.get("capacity_mw", 0),
                    "country": item.get("country", ""),
                    "lat": item.get("lat"),
                    "lon": item.get("lon"),
                }

        # For financial tab, include prior results
        extra_kwargs = {}
        if tab == "financial":
            extra_kwargs["prior_results"] = store.get_feasibility_results(item_id)

        from workflows.feasibility import run_feasibility_tab
        workflow_result = run_feasibility_tab(
            item_id=item_id,
            item_type=item_type,
            tab=tab,
            item_data=item_data,
            **extra_kwargs,
        )

        # Persist result
        findings = {
            "key_finding": workflow_result.get("key_finding", ""),
            "risks": workflow_result.get("risks", []),
            "gaps": workflow_result.get("gaps", []),
            "sources": workflow_result.get("sources", []),
            "chart_b64": workflow_result.get("chart_b64"),
        }
        store.upsert_feasibility_result(
            item_id=item_id,
            item_type=item_type,
            tab=tab,
            conclusion=workflow_result.get("conclusion", "marginal"),
            confidence=workflow_result.get("confidence", "medium"),
            findings=findings,
        )
        store.close()

        return jsonify(workflow_result)
    except Exception as e:
        logger.error(f"Feasibility run tab error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Imaging (OSINT mineral intelligence) endpoints
# ---------------------------------------------------------------------------

@app.route('/api/imaging/deposits', methods=['GET'])
def get_imaging_deposits():
    """Return mineral deposits as GeoJSON with viability scores."""
    try:
        commodity = request.args.get('commodity')
        country = request.args.get('country')
        store = ImagingDataStore()
        img_config = getattr(config, "IMAGING", {})
        stale_hours = img_config.get("stale_threshold_hours", 168)
        # Auto-fetch from MRDS when store is empty or stale
        staleness = store.get_staleness("deposits")
        if staleness is None or staleness > stale_hours:
            logger.info("Imaging deposits stale (%.1fh), fetching from MRDS",
                        staleness or -1)
            deposits = fetch_deposits()
            store.upsert_deposits(deposits.get("features", []))
        geojson = store.get_deposits(commodity=commodity, country=country)
        scored_features = score_all_deposits(geojson.get("features", []))
        store.close()
        return jsonify({"type": "FeatureCollection", "features": scored_features})
    except Exception as e:
        logger.error(f"Imaging deposits error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/imaging/concessions', methods=['GET'])
def get_imaging_concessions():
    """Return mining concessions as GeoJSON."""
    try:
        country = request.args.get('country')
        store = ImagingDataStore()
        geojson = store.get_concessions(country=country)
        store.close()
        return jsonify(geojson)
    except Exception as e:
        logger.error(f"Imaging concessions error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/imaging/generation', methods=['GET'])
def get_imaging_generation():
    """Return renewable generation assets as GeoJSON."""
    try:
        technology = request.args.get('technology')
        status = request.args.get('status')
        country = request.args.get('country')
        min_capacity = request.args.get('min_capacity_mw', type=float)
        store = ImagingDataStore()
        img_config = getattr(config, "IMAGING", {})
        stale_hours = img_config.get("stale_threshold_hours", 168)
        staleness = store.get_staleness("generation_assets")
        if staleness is None or staleness > stale_hours:
            logger.info(
                "Imaging generation assets stale (%.1fh), loading workbook",
                staleness or -1,
            )
            generation = load_generation_assets()
            store.upsert_generation_assets(generation.get("features", []))
        geojson = store.get_generation_assets(
            technology=technology,
            status=status,
            country=country,
            min_capacity_mw=min_capacity,
        )
        store.close()
        return jsonify(geojson)
    except Exception as e:
        logger.error(f"Imaging generation error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/imaging/search', methods=['GET'])
def imaging_discovery_search():
    """Search local discovery datasets (deposits, concessions, generation, scouting rows)."""
    try:
        q = (request.args.get("q") or "").strip()
        limit = request.args.get("limit", 20, type=int) or 20
        if len(q) < 2:
            return jsonify({"results": [], "query": q})
        store = ImagingDataStore()
        try:
            results = store.search_discovery(q, limit=limit)
        finally:
            store.close()
        return jsonify({"results": results, "query": q})
    except Exception as e:
        logger.error(f"Imaging search error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/geocode', methods=['GET'])
def geocode_lookup():
    """Proxy place search via Nominatim (OpenStreetMap). Use for jump-to-place when not in local DB."""
    import urllib.error
    import urllib.parse
    import urllib.request

    try:
        q = (request.args.get("q") or "").strip()
        limit = request.args.get("limit", 5, type=int) or 5
        limit = max(1, min(limit, 10))
        if len(q) < 2:
            return jsonify({"results": []})
        params = urllib.parse.urlencode(
            {"q": q, "format": "json", "limit": str(limit), "addressdetails": "0"}
        )
        url = f"https://nominatim.openstreetmap.org/search?{params}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Zorora/1.0 (energy discovery; +https://github.com/AsobaCloud/zorora)",
                "Accept-Language": "en",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            payload = json.loads(resp.read().decode())
        results = []
        for r in payload:
            try:
                lat = float(r["lat"])
                lon = float(r["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            results.append(
                {
                    "label": r.get("display_name") or q,
                    "lat": lat,
                    "lon": lon,
                }
            )
        return jsonify({"results": results})
    except urllib.error.HTTPError as e:
        logger.warning("Geocode HTTP error: %s", e)
        return jsonify({"results": [], "error": str(e)}), 200
    except Exception as e:
        logger.warning("Geocode error: %s", e)
        return jsonify({"results": [], "error": str(e)}), 200


@app.route('/api/imaging/config', methods=['GET'])
def get_imaging_config():
    """Return imaging tile URLs, filter options, and viability thresholds."""
    img_config = getattr(config, "IMAGING", {})
    return jsonify({
        "satellite_tile_url": img_config.get("satellite_tile_url", ""),
        "viirs_tile_url": img_config.get("viirs_tile_url", ""),
        "target_commodities": img_config.get("target_commodities", []),
        "generation_technologies": ["solar", "wind", "hydropower", "bioenergy", "geothermal"],
        "resource_layers": [
            {
                "key": "solar_resource",
                "label": "Solar Resource",
                "url": img_config.get("solar_overlay_tile_url", ""),
                "attribution": img_config.get("solar_overlay_attribution", ""),
            },
        ],
        "scouting_technologies": ["solar", "wind"],
        "viability_tiers": {"high": [65, 100], "medium": [35, 64], "low": [0, 34]},
    })


@app.route('/api/imaging/refresh', methods=['POST'])
def refresh_imaging_data():
    """Force-refresh deposits and concessions from upstream sources."""
    try:
        from tools.imaging.mrds_client import fetch_deposits
        from tools.imaging.concessions_client import fetch_concessions_sa
        store = ImagingDataStore()
        deposits = fetch_deposits()
        store.upsert_deposits(deposits.get("features", []))
        concessions = fetch_concessions_sa()
        store.upsert_concessions(concessions.get("features", []))
        generation = load_generation_assets()
        store.upsert_generation_assets(generation.get("features", []))
        store.close()
        return jsonify({
            "status": "ok",
            "deposits": len(deposits.get("features", [])),
            "concessions": len(concessions.get("features", [])),
            "generation_assets": len(generation.get("features", [])),
        })
    except Exception as e:
        logger.error(f"Imaging refresh error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Discovery (grid infrastructure) endpoints
# ---------------------------------------------------------------------------

_discovery_mts_cache = None
_discovery_supply_cache = None
_discovery_metrics_cache = None
_discovery_substations_cache = None


@app.route('/api/discovery/gcca/mts-zones', methods=['GET'])
def get_discovery_mts_zones():
    """Return MTS substation zones as GeoJSON with DAM node annotation."""
    global _discovery_mts_cache
    try:
        if _discovery_mts_cache is None:
            from tools.imaging.gcca_client import load_mts_zones
            from tools.imaging.grid_metrics import SUPPLY_AREA_DAM_NODE
            fc = load_mts_zones()
            for f in fc.get("features", []):
                area = f.get("properties", {}).get("supplyarea", "")
                f["properties"]["dam_node"] = SUPPLY_AREA_DAM_NODE.get(area, "rsan")
            _discovery_mts_cache = fc
        return jsonify(_discovery_mts_cache)
    except Exception as e:
        logger.error(f"MTS zones error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/discovery/gcca/supply-areas', methods=['GET'])
def get_discovery_supply_areas():
    """Return supply area boundary polygons as GeoJSON with DAM node annotation."""
    global _discovery_supply_cache
    try:
        if _discovery_supply_cache is None:
            from tools.imaging.gcca_client import load_supply_areas
            from tools.imaging.grid_metrics import SUPPLY_AREA_DAM_NODE
            fc = load_supply_areas()
            for f in fc.get("features", []):
                area = f.get("properties", {}).get("supplyarea", "")
                f["properties"]["dam_node"] = SUPPLY_AREA_DAM_NODE.get(area, "rsan")
            _discovery_supply_cache = fc
        return jsonify(_discovery_supply_cache)
    except Exception as e:
        logger.error(f"Supply areas error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/discovery/gcca/substations', methods=['GET'])
def get_discovery_substations():
    """Return MTS substation point locations as GeoJSON with DAM node annotation."""
    global _discovery_substations_cache
    try:
        if _discovery_substations_cache is None:
            from tools.imaging.gcca_client import load_substations
            from tools.imaging.grid_metrics import SUPPLY_AREA_DAM_NODE
            fc = load_substations()
            for f in fc.get("features", []):
                area = f.get("properties", {}).get("supply_area", "")
                f["properties"]["dam_node"] = SUPPLY_AREA_DAM_NODE.get(area, "rsan")
            _discovery_substations_cache = fc
        return jsonify(_discovery_substations_cache)
    except Exception as e:
        logger.error(f"Substations error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def _ensure_zone_metrics():
    """Compute and cache zone metrics on first call."""
    global _discovery_metrics_cache
    if _discovery_metrics_cache is not None:
        return _discovery_metrics_cache
    from tools.imaging.gcca_client import load_mts_zones
    from tools.imaging.grid_metrics import compute_zone_metrics
    from tools.market.sapp_client import parse_all_dam_files
    mts = load_mts_zones()
    dam = parse_all_dam_files()
    store = ImagingDataStore()
    gen_fc = store.get_generation_assets()
    store.close()
    gen_features = gen_fc.get("features", []) if gen_fc else []
    _discovery_metrics_cache = compute_zone_metrics(mts, dam, gen_features)
    return _discovery_metrics_cache


@app.route('/api/discovery/zone-metrics', methods=['GET'])
def get_discovery_zone_metrics_all():
    """Return DAM price stats + RE asset counts for all MTS zones."""
    try:
        metrics = _ensure_zone_metrics()
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"Zone metrics error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/discovery/zone-metrics/<substation>', methods=['GET'])
def get_discovery_zone_metrics(substation):
    """Return DAM price stats + RE asset count for a specific MTS zone."""
    try:
        metrics = _ensure_zone_metrics()
        zone = metrics.get(substation)
        if zone is None:
            return jsonify({"error": f"Unknown substation: {substation}"}), 404
        return jsonify(zone)
    except Exception as e:
        logger.error(f"Zone metrics error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Greenfield scouting endpoints
# ---------------------------------------------------------------------------

@app.route('/api/scouting/score', methods=['POST'])
def score_greenfield_site():
    """Score a clicked greenfield candidate site."""
    try:
        data = request.get_json() or {}
        if "lat" not in data or "lon" not in data:
            return jsonify({"error": "lat and lon are required"}), 400
        technology = (data.get("technology") or "").strip().lower()
        if not technology:
            return jsonify({"error": "technology is required"}), 400

        lat = float(data["lat"])
        lon = float(data["lon"])
        store = ImagingDataStore()
        try:
            site = _compute_greenfield_score(
                store,
                lat,
                lon,
                technology,
                name=(data.get("name") or "").strip() or None,
                country=(data.get("country") or "").strip() or None,
            )
        finally:
            store.close()
        return jsonify({"site": site})
    except Exception as e:
        logger.error(f"Scouting score error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/scouting/watchlist', methods=['GET'])
def list_scout_watchlist():
    """List persisted greenfield scouting watchlist entries."""
    try:
        technology = request.args.get("technology")
        store = ImagingDataStore()
        items = store.list_watchlist_sites(technology=technology)
        store.close()
        return jsonify({"items": items, "count": len(items)})
    except Exception as e:
        logger.error(f"Scouting watchlist error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/scouting/watchlist', methods=['POST'])
def create_scout_watchlist_item():
    """Persist a scored site in the greenfield watchlist."""
    try:
        data = request.get_json() or {}
        site = data.get("site") or {}
        if not site:
            return jsonify({"error": "site is required"}), 400

        store = ImagingDataStore()
        saved = store.upsert_watchlist_site(site)
        store.close()
        return jsonify({"status": "ok", "site": saved})
    except Exception as e:
        logger.error(f"Scouting watchlist create error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/scouting/watchlist/<site_id>', methods=['DELETE'])
def delete_scout_watchlist_item(site_id):
    """Delete a site from the greenfield watchlist."""
    try:
        store = ImagingDataStore()
        store.delete_watchlist_site(site_id)
        store.close()
        return jsonify({"status": "deleted"})
    except Exception as e:
        logger.error(f"Scouting watchlist delete error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/scouting/compare', methods=['GET'])
def compare_scout_watchlist_sites():
    """Return watchlist sites for side-by-side comparison."""
    try:
        ids = [item.strip() for item in (request.args.get("ids") or "").split(",") if item.strip()]
        store = ImagingDataStore()
        items = store.get_watchlist_sites_by_ids(ids)
        store.close()
        return jsonify({"items": items, "count": len(items)})
    except Exception as e:
        logger.error(f"Scouting compare error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/research/history', methods=['GET'])
def get_research_history():
    """
    Get research history.
    
    Query params:
    - limit: int (default: 10)
    - query: str (optional search)
    
    Returns:
    {
        "results": [
            {
                "research_id": str,
                "query": str,
                "created_at": str,
                "total_sources": int,
                "synthesis_preview": str
            },
            ...
        ]
    }
    """
    try:
        limit = int(request.args.get('limit', 10))
        search_query = request.args.get('query', None)
        
        results = research_engine.search_research(query=search_query, limit=limit)
        
        return jsonify({"results": results})
        
    except Exception as e:
        logger.error(f"History error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# Settings API Routes

@app.route('/api/settings/config', methods=['GET'])
def get_settings_config():
    """
    Get current configuration.
    
    Returns:
    {
        "api_url": str,
        "model": str,
        "model_endpoints": {...},
        "specialized_models": {...},
        "hf_endpoints": {...},
        "hf_token": str (masked),
    }
    """
    try:
        config = config_manager.read_config()
        
        # Mask API tokens (always mask in responses)
        for token_key in ["hf_token", "openai_api_key", "anthropic_api_key"]:
            if config.get(token_key):
                token = config[token_key]
                if len(token) > 8:
                    masked = f"{token[:4]}...{token[-4:]}"
                else:
                    masked = "***"
                config[token_key] = masked
        
        return jsonify(config)
    except Exception as e:
        logger.error(f"Error getting config: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/settings/models', methods=['GET'])
def get_settings_models():
    """
    Get available models from LM Studio and HF endpoints.
    
    NOTE: This fetches models live on every request - no caching.
    
    Returns:
    {
        "models": [
            {"name": str, "origin": str, "type": str, ...},
            ...
        ]
    }
    """
    try:
        models = model_fetcher.fetch_all_models()
        return jsonify({"models": models})
    except Exception as e:
        logger.error(f"Error fetching models: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/settings/endpoints', methods=['GET'])
def get_settings_endpoints():
    """
    Get saved endpoints (HF, OpenAI, Anthropic).
    
    Returns:
    {
        "endpoints": [
            {"key": str, "provider": str, "url": str, "model": str, ...},
            ...
        ]
    }
    """
    try:
        config = config_manager.read_config()
        endpoints = []
        
        # HF endpoints
        for key, endpoint_config in config.get("hf_endpoints", {}).items():
            endpoint_data = {
                "key": key,
                "provider": "hf",
                "url": endpoint_config.get("url", ""),
                "model": endpoint_config.get("model_name", ""),
                "model_name": endpoint_config.get("model_name", ""),  # Keep for backward compat
                "timeout": endpoint_config.get("timeout", 120),
                "enabled": endpoint_config.get("enabled", True),
            }
            # Mask API key if present
            if endpoint_config.get("api_key"):
                token = endpoint_config["api_key"]
                if len(token) > 8:
                    masked = f"{token[:4]}...{token[-4:]}"
                else:
                    masked = "***"
                endpoint_data["api_key"] = masked
            endpoints.append(endpoint_data)
        
        # OpenAI endpoints
        for key, endpoint_config in config.get("openai_endpoints", {}).items():
            endpoint_data = {
                "key": key,
                "provider": "openai",
                "url": "https://api.openai.com/v1/chat/completions",  # Fixed URL
                "model": endpoint_config.get("model", ""),
                "timeout": endpoint_config.get("timeout", 60),
                "enabled": endpoint_config.get("enabled", True),
                "max_tokens": endpoint_config.get("max_tokens", 4096),
            }
            # Mask API key if present
            if endpoint_config.get("api_key"):
                token = endpoint_config["api_key"]
                if len(token) > 8:
                    masked = f"{token[:4]}...{token[-4:]}"
                else:
                    masked = "***"
                endpoint_data["api_key"] = masked
            endpoints.append(endpoint_data)
        
        # Anthropic endpoints
        for key, endpoint_config in config.get("anthropic_endpoints", {}).items():
            endpoint_data = {
                "key": key,
                "provider": "anthropic",
                "url": "https://api.anthropic.com/v1/messages",  # Fixed URL
                "model": endpoint_config.get("model", ""),
                "timeout": endpoint_config.get("timeout", 60),
                "enabled": endpoint_config.get("enabled", True),
                "max_tokens": endpoint_config.get("max_tokens", 4096),
            }
            # Mask API key if present
            if endpoint_config.get("api_key"):
                token = endpoint_config["api_key"]
                if len(token) > 8:
                    masked = f"{token[:4]}...{token[-4:]}"
                else:
                    masked = "***"
                endpoint_data["api_key"] = masked
            endpoints.append(endpoint_data)
        
        return jsonify({"endpoints": endpoints})
    except Exception as e:
        logger.error(f"Error getting endpoints: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/settings/endpoint', methods=['POST'])
def save_endpoint():
    """
    Add or update an endpoint (HF, OpenAI, or Anthropic).
    
    Request body:
    {
        "key": str,
        "provider": str ("hf" | "openai" | "anthropic"),
        "url": str (required for HF only),
        "model": str (required for OpenAI/Anthropic, or "model_name" for HF),
        "model_name": str (required for HF, alias for "model"),
        "timeout": int (optional),
        "enabled": bool (optional),
        "max_tokens": int (optional, for OpenAI/Anthropic),
    }
    
    Returns:
    {"success": bool, "error": str}
    """
    try:
        data = request.get_json()
        provider = data.get("provider", "hf").lower()
        
        # Validate required fields
        if not data.get("key"):
            return jsonify({"success": False, "error": "Missing 'key' field"}), 400
        
        # Validate key (Python identifier)
        import re
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_-]*$', data["key"]):
            return jsonify({"success": False, "error": "Invalid endpoint key (must be valid Python identifier)"}), 400
        
        # Read current config
        current = config_manager.read_config()
        
        if provider == "hf":
            # HF endpoint validation
            if not data.get("url") or not (data.get("model_name") or data.get("model")):
                return jsonify({"success": False, "error": "HF endpoint requires 'url' and 'model_name'"}), 400
            
            if not data["url"].startswith(("http://", "https://")):
                return jsonify({"success": False, "error": "URL must start with http:// or https://"}), 400
            
            # Validate API key is not masked
            if "api_key" in data and isinstance(data["api_key"], str) and "..." in data["api_key"]:
                return jsonify({"success": False, "error": "Invalid API key format (masked token detected)"}), 400
            
            hf_endpoints = current.get("hf_endpoints", {}).copy()
            endpoint_config = {
                "url": data["url"],
                "model_name": data.get("model_name") or data.get("model"),
                "timeout": data.get("timeout", 120),
                "enabled": data.get("enabled", True),
            }
            # Only include api_key if provided and not masked
            if "api_key" in data and data["api_key"]:
                endpoint_config["api_key"] = data["api_key"]
            hf_endpoints[data["key"]] = endpoint_config
            result = config_manager.write_config({"hf_endpoints": hf_endpoints})
            
        elif provider == "openai":
            # OpenAI endpoint validation
            if not data.get("model"):
                return jsonify({"success": False, "error": "OpenAI endpoint requires 'model'"}), 400
            
            # Validate API key is not masked
            if "api_key" in data and isinstance(data["api_key"], str) and "..." in data["api_key"]:
                return jsonify({"success": False, "error": "Invalid API key format (masked token detected)"}), 400
            
            openai_endpoints = current.get("openai_endpoints", {}).copy()
            endpoint_config = {
                "model": data["model"],
                "timeout": data.get("timeout", 60),
                "enabled": data.get("enabled", True),
                "max_tokens": data.get("max_tokens", 4096),
            }
            # Only include api_key if provided and not masked
            if "api_key" in data and data["api_key"]:
                endpoint_config["api_key"] = data["api_key"]
            openai_endpoints[data["key"]] = endpoint_config
            result = config_manager.write_config({"openai_endpoints": openai_endpoints})
            
        elif provider == "anthropic":
            # Anthropic endpoint validation
            if not data.get("model"):
                return jsonify({"success": False, "error": "Anthropic endpoint requires 'model'"}), 400
            
            # Validate API key is not masked
            if "api_key" in data and isinstance(data["api_key"], str) and "..." in data["api_key"]:
                return jsonify({"success": False, "error": "Invalid API key format (masked token detected)"}), 400
            
            anthropic_endpoints = current.get("anthropic_endpoints", {}).copy()
            endpoint_config = {
                "model": data["model"],
                "timeout": data.get("timeout", 60),
                "enabled": data.get("enabled", True),
                "max_tokens": data.get("max_tokens", 4096),
            }
            # Only include api_key if provided and not masked
            if "api_key" in data and data["api_key"]:
                endpoint_config["api_key"] = data["api_key"]
            anthropic_endpoints[data["key"]] = endpoint_config
            result = config_manager.write_config({"anthropic_endpoints": anthropic_endpoints})
            
        else:
            return jsonify({"success": False, "error": f"Invalid provider: {provider}. Must be 'hf', 'openai', or 'anthropic'"}), 400
        
        if result["success"]:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": result["error"]}), 400
            
    except Exception as e:
        logger.error(f"Error saving endpoint: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/settings/endpoint/<endpoint_key>', methods=['DELETE'])
def delete_endpoint(endpoint_key):
    """
    Delete an endpoint (HF, OpenAI, or Anthropic).
    
    NOTE: If the endpoint is in use by any role, those roles are automatically
    reassigned to "local" endpoint without user confirmation.
    
    Returns:
    {"success": bool, "error": str}
    """
    try:
        # Read current config
        current = config_manager.read_config()
        
        updates = {}
        endpoint_found = False
        
        # Check and remove from HF endpoints
        hf_endpoints = current.get("hf_endpoints", {}).copy()
        if endpoint_key in hf_endpoints:
            del hf_endpoints[endpoint_key]
            updates["hf_endpoints"] = hf_endpoints
            endpoint_found = True
        
        # Check and remove from OpenAI endpoints
        openai_endpoints = current.get("openai_endpoints", {}).copy()
        if endpoint_key in openai_endpoints:
            del openai_endpoints[endpoint_key]
            updates["openai_endpoints"] = openai_endpoints
            endpoint_found = True
        
        # Check and remove from Anthropic endpoints
        anthropic_endpoints = current.get("anthropic_endpoints", {}).copy()
        if endpoint_key in anthropic_endpoints:
            del anthropic_endpoints[endpoint_key]
            updates["anthropic_endpoints"] = anthropic_endpoints
            endpoint_found = True
        
        if not endpoint_found:
            return jsonify({"success": False, "error": "Endpoint not found"}), 404
        
        # Auto-reassign any roles using this endpoint to "local"
        # No confirmation required - automatic and silent
        model_endpoints = current.get("model_endpoints", {}).copy()
        for role, endpoint in list(model_endpoints.items()):
            if endpoint == endpoint_key:
                model_endpoints[role] = "local"  # Automatic fallback
        
        updates["model_endpoints"] = model_endpoints
        
        # Write config
        result = config_manager.write_config(updates)
        
        if result["success"]:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": result["error"]}), 400
            
    except Exception as e:
        logger.error(f"Error deleting endpoint: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/settings/config', methods=['POST'])
def save_settings_config():
    """
    Save configuration changes.
    
    NOTE: Server is NOT automatically restarted. Changes take effect only after
    manual restart. Success message includes restart instruction.
    
    Request body:
    {
        "model_endpoints": {...},
        "specialized_models": {...},
        "hf_token": str (optional, must NOT be masked),
    }
    
    Returns:
    {"success": bool, "error": str, "message": str}
    """
    try:
        data = request.get_json()
        
        # Validate API tokens are not masked
        for token_key in ["hf_token", "openai_api_key", "anthropic_api_key"]:
            if token_key in data and isinstance(data[token_key], str) and "..." in data[token_key]:
                return jsonify({
                    "success": False,
                    "error": f"Invalid {token_key} format (masked token detected - token unchanged)"
                }), 400
        
        # Validate and write config
        result = config_manager.write_config(data)
        
        if result["success"]:
            return jsonify({
                "success": True,
                "message": "Configuration saved successfully. Please restart the server for changes to take effect."
            })
        else:
            return jsonify({
                "success": False,
                "error": result["error"]
            }), 400
            
    except Exception as e:
        logger.error(f"Error saving config: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
