"""Query refinement module for deep research.

Analyzes user queries to detect missing dimensions (time period, geography,
analysis type, scope) and returns structured refinement suggestions with
option pills for the UI.
"""

import json
import logging
import re
from datetime import date

logger = logging.getLogger(__name__)


def refine_query(raw_query: str) -> dict:
    """Analyze a research query and return structured refinement suggestions.

    Uses the reasoning model to detect what dimensions are present vs. missing,
    then returns a structured dict with detected dimensions, gaps (with suggested
    options), and a refined query string.

    Args:
        raw_query: The user's original research question.

    Returns:
        dict with keys: status, original_query, dimensions, gaps, refined_query,
        skip_refinement.
    """
    if not raw_query or not raw_query.strip():
        return _passthrough(raw_query)

    today = date.today().isoformat()

    try:
        import config
        from tools.specialist.client import create_specialist_client

        prompt = (
            f"Today's date is {today}.\n\n"
            f"Analyze this research query and identify which dimensions are specified "
            f"and which are missing. Return ONLY valid JSON, no explanation.\n\n"
            f"Query: {raw_query}\n\n"
            f"Detect these dimensions:\n"
            f"- topic: The main subject (always present if query is coherent)\n"
            f"- time_period: Any time bounds (e.g., 'last 3 months', '2024-2025', 'recent')\n"
            f"- geographic_focus: Any geographic scope (e.g., 'United States', 'global', 'Europe')\n"
            f"- analysis_type: Type of analysis requested (e.g., 'market overview', 'trend analysis', 'policy review')\n"
            f"- scope: Specific scope constraints (e.g., 'residential sector', 'Fortune 500 companies')\n\n"
            f"Return JSON in this exact format:\n"
            f'{{\n'
            f'  "status": "needs_refinement" or "well_specified",\n'
            f'  "dimensions": {{\n'
            f'    "topic": {{"detected": true, "value": "extracted topic"}},\n'
            f'    "time_period": {{"detected": true/false, "value": "extracted value or null"}},\n'
            f'    "geographic_focus": {{"detected": true/false, "value": "extracted value or null"}},\n'
            f'    "analysis_type": {{"detected": true/false, "value": "extracted value or null"}},\n'
            f'    "scope": {{"detected": true/false, "value": "extracted value or null"}}\n'
            f'  }},\n'
            f'  "gaps": [\n'
            f'    {{\n'
            f'      "dimension": "time_period",\n'
            f'      "question": "What time period should this cover?",\n'
            f'      "options": ["Last 30 days", "Last 3 months", "Last 12 months", "2024-2025"]\n'
            f'    }}\n'
            f'  ],\n'
            f'  "refined_query": "improved version of the query incorporating detected dimensions"\n'
            f'}}\n\n'
            f"Rules:\n"
            f"- If 2 or fewer dimensions are missing, set status to 'well_specified'\n"
            f"- Each gap must have 3-5 options as short labels\n"
            f"- The refined_query should be a clear, specific research question\n"
            f"- Return ONLY the JSON object, nothing else\n"
        )

        model_config = config.SPECIALIZED_MODELS["reasoning"]
        client = create_specialist_client("reasoning", model_config)
        # Override timeout: refinement is non-critical UI enhancement,
        # fail fast rather than block the request for minutes
        client.adapter.timeout = 15
        messages = [
            {"role": "system", "content": "You are a JSON API. Return ONLY valid JSON objects. No prose, no explanation, no markdown."},
            {"role": "user", "content": prompt},
        ]
        response = client.chat_complete(messages, tools=None)
        result = client.extract_content(response)

        if not result or not result.strip():
            logger.warning("Refinement model returned empty response")
            return _passthrough(raw_query)

        logger.debug(f"Refinement raw output (first 500 chars): {result[:500]}")

        parsed = _parse_refinement_json(result)
        if not parsed:
            logger.warning(f"Failed to parse refinement JSON, using passthrough. Raw (first 300): {result[:300]}")
            return _passthrough(raw_query)

        # Ensure required fields exist
        parsed.setdefault("original_query", raw_query)
        parsed.setdefault("status", "needs_refinement")
        parsed.setdefault("dimensions", {})
        parsed.setdefault("gaps", [])
        parsed.setdefault("refined_query", raw_query)

        # Determine skip_refinement
        if parsed["status"] == "well_specified" or len(parsed.get("gaps", [])) == 0:
            parsed["skip_refinement"] = True
        else:
            parsed["skip_refinement"] = False

        logger.info(f"Refinement result: status={parsed['status']}, gaps={len(parsed['gaps'])}, skip={parsed['skip_refinement']}")
        return parsed

    except Exception as e:
        logger.warning(f"Query refinement failed: {e}")
        return _passthrough(raw_query)


def _parse_refinement_json(text: str) -> dict | None:
    """Parse JSON from model output, handling think tags and markdown fences."""
    if not text:
        return None

    # Strip <think>...</think> tags
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

    # Strip markdown code fences
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()

    # Try direct JSON parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON object from surrounding text
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _passthrough(raw_query: str) -> dict:
    """Return a passthrough response that skips refinement."""
    return {
        "status": "well_specified",
        "original_query": raw_query or "",
        "dimensions": {
            "topic": {"detected": True, "value": raw_query or ""},
        },
        "gaps": [],
        "refined_query": raw_query or "",
        "skip_refinement": True,
    }
