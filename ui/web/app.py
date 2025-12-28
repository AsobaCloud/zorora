"""Flask web application for Zorora deep research UI."""

import logging
from flask import Flask, render_template, request, jsonify
from datetime import datetime

from engine.research_engine import ResearchEngine
from ui.web.config_manager import ConfigManager, ModelFetcher

logger = logging.getLogger(__name__)

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')

# Initialize research engine
research_engine = ResearchEngine()

# Initialize config managers
config_manager = ConfigManager()
model_fetcher = ModelFetcher()


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
        
        # Mask HF token (always mask in responses)
        if config.get("hf_token"):
            token = config["hf_token"]
            if len(token) > 8:
                masked = f"{token[:4]}...{token[-4:]}"
            else:
                masked = "***"
            config["hf_token"] = masked
        
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
    Get saved HF endpoints.
    
    Returns:
    {
        "endpoints": [
            {"key": str, "url": str, "model_name": str, ...},
            ...
        ]
    }
    """
    try:
        config = config_manager.read_config()
        endpoints = []
        
        for key, endpoint_config in config.get("hf_endpoints", {}).items():
            endpoints.append({
                "key": key,
                "url": endpoint_config.get("url", ""),
                "model_name": endpoint_config.get("model_name", ""),
                "timeout": endpoint_config.get("timeout", 120),
                "enabled": endpoint_config.get("enabled", True),
            })
        
        return jsonify({"endpoints": endpoints})
    except Exception as e:
        logger.error(f"Error getting endpoints: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/settings/endpoint', methods=['POST'])
def save_endpoint():
    """
    Add or update an HF endpoint.
    
    Request body:
    {
        "key": str,
        "url": str,
        "model_name": str,
        "timeout": int (optional),
        "enabled": bool (optional),
    }
    
    Returns:
    {"success": bool, "error": str}
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get("key") or not data.get("url") or not data.get("model_name"):
            return jsonify({"success": False, "error": "Missing required fields"}), 400
        
        # Validate URL
        if not data["url"].startswith(("http://", "https://")):
            return jsonify({"success": False, "error": "URL must start with http:// or https://"}), 400
        
        # Validate key (Python identifier)
        import re
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_-]*$', data["key"]):
            return jsonify({"success": False, "error": "Invalid endpoint key (must be valid Python identifier)"}), 400
        
        # Read current config
        current = config_manager.read_config()
        
        # Update HF endpoints
        hf_endpoints = current.get("hf_endpoints", {}).copy()
        hf_endpoints[data["key"]] = {
            "url": data["url"],
            "model_name": data["model_name"],
            "timeout": data.get("timeout", 120),
            "enabled": data.get("enabled", True),
        }
        
        # Write config
        result = config_manager.write_config({"hf_endpoints": hf_endpoints})
        
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
    Delete an HF endpoint.
    
    NOTE: If the endpoint is in use by any role, those roles are automatically
    reassigned to "local" endpoint without user confirmation.
    
    Returns:
    {"success": bool, "error": str}
    """
    try:
        # Read current config
        current = config_manager.read_config()
        
        # Remove endpoint
        hf_endpoints = current.get("hf_endpoints", {}).copy()
        if endpoint_key not in hf_endpoints:
            return jsonify({"success": False, "error": "Endpoint not found"}), 404
        
        del hf_endpoints[endpoint_key]
        
        # Auto-reassign any roles using this endpoint to "local"
        # No confirmation required - automatic and silent
        model_endpoints = current.get("model_endpoints", {}).copy()
        for role, endpoint in list(model_endpoints.items()):
            if endpoint == endpoint_key:
                model_endpoints[role] = "local"  # Automatic fallback
        
        # Write config
        result = config_manager.write_config({
            "hf_endpoints": hf_endpoints,
            "model_endpoints": model_endpoints,
        })
        
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
        
        # Validate HF token is not masked
        if "hf_token" in data and isinstance(data["hf_token"], str) and "..." in data["hf_token"]:
            return jsonify({
                "success": False,
                "error": "Invalid token format (masked token detected - token unchanged)"
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
