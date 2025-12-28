"""Flask web application for Zorora deep research UI."""

import logging
from flask import Flask, render_template, request, jsonify
from datetime import datetime

from engine.research_engine import ResearchEngine

logger = logging.getLogger(__name__)

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')

# Initialize research engine
research_engine = ResearchEngine()


@app.route('/')
def index():
    """Render main research UI"""
    return render_template('index.html')


@app.route('/api/research', methods=['POST'])
def start_research():
    """
    Start deep research workflow.
    
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
        
        # Execute research (synchronous for MVP)
        state = research_engine.deep_research(query, depth=depth)
        
        # Format response
        response = {
            "research_id": state.started_at.strftime("%Y%m%d_%H%M%S"),
            "status": "completed",
            "query": query,
            "synthesis": state.synthesis,
            "total_sources": state.total_sources,
            "findings_count": len(state.findings),
            "sources": [
                {
                    "source_id": s.source_id,
                    "title": s.title,
                    "url": s.url,
                    "credibility_score": s.credibility_score,
                    "credibility_category": s.credibility_category,
                    "source_type": s.source_type
                }
                for s in state.sources_checked[:20]  # Top 20 sources
            ],
            "completed_at": state.completed_at.isoformat() if state.completed_at else None
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Research error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


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
        # Search for research by ID pattern
        results = research_engine.search_research(query=research_id, limit=1)
        
        if not results:
            return jsonify({"error": "Research not found"}), 404
        
        # Load full research data
        research_data = research_engine.load_research(results[0]['research_id'])
        
        if not research_data:
            return jsonify({"error": "Research data not found"}), 404
        
        return jsonify(research_data)
        
    except Exception as e:
        logger.error(f"Get research error: {e}", exc_info=True)
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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
