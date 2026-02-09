"""Flask web application for Zorora deep research UI."""

import logging
import threading
import uuid
import json
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify, Response, stream_with_context

from engine.research_engine import ResearchEngine
from engine.deep_research_service import run_deep_research, build_results_payload
from ui.web.config_manager import ConfigManager, ModelFetcher
from tools.research.newsroom import fetch_newsroom_api
from tools.specialist.client import create_specialist_client
import config

logger = logging.getLogger(__name__)

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')

# Initialize research engine
research_engine = ResearchEngine()

# Initialize config managers
config_manager = ConfigManager()
model_fetcher = ModelFetcher()

# Progress tracking for research workflows
research_progress = {}  # {research_id: {"status": str, "message": str, "phase": str}}
chat_threads = {}  # lightweight in-memory thread store keyed by context id


def _parse_date(date_str: str):
    """Parse date string to date object (supports ISO prefixes)."""
    if not date_str:
        return None
    try:
        return datetime.strptime(str(date_str)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _filter_newsroom_articles(articles, topic=None, date_from=None, date_to=None, limit=100):
    """Filter newsroom articles by topic and date range."""
    topic_terms = [t.strip().lower() for t in (topic or "").split() if t.strip()]
    start_date = _parse_date(date_from)
    end_date = _parse_date(date_to)
    filtered = []

    for article in articles:
        article_date = _parse_date(article.get("date"))
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


def _news_intel_synthesis(articles, topic=None, date_from=None, date_to=None):
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
        entries.append(f"- [{date_str}] {headline} ({source})\\n  Topics: {topics}\\n  URL: {url}")

    scope = f"topic='{topic or 'all'}', date_from='{date_from or 'none'}', date_to='{date_to or 'none'}'"
    prompt = (
        "You are producing a newsroom intelligence brief from API-fetched articles.\\n"
        f"Scope: {scope}\\n"
        f"Total articles: {len(articles)}\\n\\n"
        "Provide:\\n"
        "1) Executive Summary (4-6 bullets)\\n"
        "2) Key Themes\\n"
        "3) Notable Signals/Risks\\n"
        "4) Watchlist (next 1-2 weeks)\\n"
        "Use citations as [Headline].\\n\\n"
        "Articles:\\n"
        + "\\n\\n".join(entries)
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
    except Exception as e:
        logger.warning(f"News intel synthesis fallback triggered: {e}")

    # Deterministic fallback summary
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
        f"News Intel Summary ({len(articles)} articles)\\n\\n"
        "Top Themes:\\n"
        + ("\\n".join(bullets) if bullets else "- No dominant themes detected")
        + "\\n\\nRecent Headlines:\\n"
        + "\\n".join(latest)
    )


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
    for source in sources[:30]:
        title = source.get("title") or source.get("headline") or "Untitled"
        source_type = source.get("source_type") or source.get("source") or "unknown"
        url = source.get("url", "")
        publication_date = str(source.get("publication_date") or source.get("date") or "")[:10]
        source_lines.append(f"- {title} | {source_type} | {publication_date} | {url}")

    history_lines = []
    for item in history[-8:]:
        role = "User" if item.get("role") == "user" else "Assistant"
        content = str(item.get("content", ""))[:900]
        if content:
            history_lines.append(f"{role}: {content}")

    strict_instructions = (
        "Use only provided context and sources. If evidence is insufficient, say so explicitly."
        if strict_citations
        else "Prioritize provided context and sources; clearly label any inference beyond them."
    )

    prompt = (
        "You are an evidence-grounded research assistant responding to a follow-up discussion prompt.\n"
        f"Context: {context_label}\n"
        f"Context summary:\n{context_summary[:4000]}\n\n"
        f"Source list:\n{chr(10).join(source_lines) if source_lines else '- No sources provided'}\n\n"
        f"Prior conversation:\n{chr(10).join(history_lines) if history_lines else '- No previous messages'}\n\n"
        f"User question: {message}\n\n"
        f"Rules: {strict_instructions}\n"
        "Keep response concise, cite sources inline using bracket format [Source Title]."
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


@app.route('/')
def index():
    """Render main research UI"""
    return render_template('index.html')


def _run_research_with_progress(research_id: str, query: str, depth: int):
    """Run research workflow in background thread and emit progress updates."""
    try:
        def on_progress(status: str, phase: str, message: str):
            research_progress[research_id] = {
                "status": status,
                "message": message,
                "phase": phase
            }

        state = run_deep_research(
            query=query,
            depth=depth,
            max_results_per_source=10,
            progress_callback=on_progress,
        )

        research_id_actual = research_engine.save_research(state)

        research_progress[research_id] = {
            "status": "completed",
            "message": f"Research complete! Found {state.total_sources} sources.",
            "phase": "complete",
            "results": build_results_payload(state, query, research_id=research_id_actual, max_sources=20),
        }
        
    except Exception as e:
        logger.error(f"Research error: {e}", exc_info=True)
        research_progress[research_id] = {
            "status": "error",
            "message": f"Error: {str(e)}",
            "phase": "error"
        }


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
            daemon=True
        )
        thread.start()
        
        return jsonify({
            "research_id": research_id,
            "status": "started",
            "query": query
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

        strict_citations = bool(data.get("strict_citations", True))
        history = data.get("history") or []
        selected_source_ids = set(data.get("selected_source_ids") or [])

        research_data = _load_research_by_id(research_id)
        if not research_data:
            return jsonify({"error": "Research not found"}), 404

        original_query = research_data.get("query") or research_data.get("original_query") or "research query"
        synthesis = research_data.get("synthesis") or ""
        sources = research_data.get("sources") or []

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
            }
        )
    except Exception as e:
        logger.error(f"Research chat error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/news-intel/articles', methods=['POST'])
def get_news_intel_articles():
    """Fetch newsroom articles from API and filter by topic/date range."""
    try:
        data = request.get_json() or {}
        topic = (data.get("topic") or "").strip()
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        limit = int(data.get("limit", 100))
        limit = max(1, min(limit, 200))

        today = datetime.now(timezone.utc).date()
        start_date = _parse_date(date_from)
        end_date = _parse_date(date_to)
        if start_date and end_date and start_date > end_date:
            return jsonify({"error": "date_from must be <= date_to"}), 400

        days_back = 365
        if start_date:
            days_back = max(1, min(365, (today - start_date).days + 1))

        articles = fetch_newsroom_api(query=None, days_back=days_back, max_results=500)
        filtered = _filter_newsroom_articles(
            articles,
            topic=topic,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )

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
            for article in filtered
        ]
        return jsonify({"count": len(serialized), "articles": serialized})
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
        limit = int(data.get("limit", 100))
        limit = max(1, min(limit, 200))

        today = datetime.now(timezone.utc).date()
        start_date = _parse_date(date_from)
        end_date = _parse_date(date_to)
        if start_date and end_date and start_date > end_date:
            return jsonify({"error": "date_from must be <= date_to"}), 400

        days_back = 365
        if start_date:
            days_back = max(1, min(365, (today - start_date).days + 1))

        articles = fetch_newsroom_api(query=None, days_back=days_back, max_results=500)
        filtered = _filter_newsroom_articles(
            articles,
            topic=topic,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
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

        return jsonify({"reply": reply, "mode": "evidence" if strict_citations else "advisory", "thread_size": len(thread)})
    except Exception as e:
        logger.error(f"News intel chat error: {e}", exc_info=True)
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
