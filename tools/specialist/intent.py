"""
Intent detector tool for fast request classification.
"""

import logging
import json
import re
from tools.specialist.client import create_specialist_client

logger = logging.getLogger(__name__)


def use_intent_detector(user_input: str, recent_context: str = "") -> str:
    """
    Fast intent detection using small thinking model.
    Analyzes user input to determine which tool should handle it.

    Args:
        user_input: The user's request to analyze
        recent_context: Recent conversation context (optional)

    Returns:
        JSON with detected intent: {"tool": "tool_name", "confidence": "high|medium|low", "reasoning": "brief explanation"}
    """
    if not user_input or not isinstance(user_input, str):
        return '{"tool": "none", "confidence": "low", "reasoning": "empty input"}'

    if len(user_input) > 2000:
        return '{"tool": "none", "confidence": "low", "reasoning": "input too long"}'

    try:
        import config

        logger.info(f"Detecting intent for: {user_input[:100]}...")

        model_config = config.SPECIALIZED_MODELS["intent_detector"]
        client = create_specialist_client("intent_detector", model_config)

        # Build context-aware prompt
        context_section = ""
        if recent_context:
            context_section = f"\n\nRecent context:\n{recent_context[:500]}\n"

        system_prompt = """You are an intent detector. Analyze the user request and output ONLY a JSON object.

CRITICAL: Output ONLY the JSON object. NO thinking tags, NO explanations, NO markdown.
Do NOT use <think> tags. Just output the JSON directly.

Available tools:
- write_file: User wants to save/write/create a file (keywords: "write to", "save to", "create file", ".py file", ".md file")
- read_file: User wants to ONLY read/view a file WITHOUT analysis (keywords: "read", "show me", "view file", "content of") - BUT NOT if they also want analysis
- list_files: User wants to list directory contents (keywords: "list files", "show files", "ls", "what files", "directory contents")
- analyze_image: User wants to analyze/OCR/convert an EXISTING image (keywords: "analyze image", "convert image", "OCR", "extract text from image", ".png", ".jpg", "image to markdown", "what's in this image")
- generate_image: User wants to CREATE/GENERATE a new image from text (keywords: "generate image", "create image", "make an image", "draw", "visualize", "illustration of", "picture of")
- use_coding_agent: User wants to generate/modify code (keywords: "write function", "create script", "generate code")
- use_reasoning_model: User wants analysis/planning/thinking (keywords: "analyze", "deep dive", "implications", "think deeply", "examine", "investigate") - PRIORITIZE this over read_file if analysis keywords present
- web_search: User wants current web information (keywords: "search", "latest", "current news", "what's happening")
- get_newsroom_headlines: User wants today's news from Asoba newsroom (keywords: "today's news", "newsroom", "headlines today")
- use_energy_analyst: User wants energy policy/regulatory info (keywords: "FERC", "ISO", "NEM", "tariff", "energy regulation")
- use_search_model: User wants general knowledge questions (keywords: "what is", "explain", "how does")

CRITICAL PRIORITY RULES:
1. If user mentions BOTH a file AND analysis keywords ("analyze", "deep dive", "implications", "think about"), choose use_reasoning_model NOT read_file. The reasoning model can request file reads if needed.
2. If user mentions an EXISTING image file (.png, .jpg, etc.) or image analysis/OCR keywords, choose analyze_image.
3. If user wants to CREATE/GENERATE a new image from text description, choose generate_image.

Output format (ONLY this, nothing else):
{"tool": "tool_name", "confidence": "high|medium|low", "reasoning": "one sentence why"}

Examples:
Input: "write this to report.md"
Output: {"tool": "write_file", "confidence": "high", "reasoning": "explicit file write request with filename"}

Input: "read the file nuclear.md"
Output: {"tool": "read_file", "confidence": "high", "reasoning": "simple file read without analysis"}

Input: "show me what's in config.py"
Output: {"tool": "read_file", "confidence": "high", "reasoning": "view file contents without analysis"}

Input: "deep dive analysis about news_themes.md"
Output: {"tool": "use_reasoning_model", "confidence": "high", "reasoning": "analysis request - reasoning model will read file if needed"}

Input: "analyze the implications in the file we just read"
Output: {"tool": "use_reasoning_model", "confidence": "high", "reasoning": "analysis/implications request requires reasoning"}

Input: "list files in the current directory"
Output: {"tool": "list_files", "confidence": "high", "reasoning": "request to list directory contents"}

Input: "convert gdp.png to markdown"
Output: {"tool": "analyze_image", "confidence": "high", "reasoning": "image file with conversion request requires vision model"}

Input: "what's in this screenshot.jpg?"
Output: {"tool": "analyze_image", "confidence": "high", "reasoning": "image analysis request"}

Input: "generate an image of a sunset over mountains"
Output: {"tool": "generate_image", "confidence": "high", "reasoning": "text-to-image generation request"}

Input: "create a python script for clustering"
Output: {"tool": "use_coding_agent", "confidence": "high", "reasoning": "code generation request"}

Input: "save the plan to plan.md"
Output: {"tool": "write_file", "confidence": "high", "reasoning": "save/write with filename"}

Remember: Output ONLY the JSON. No thinking process, no tags, no extra text."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{context_section}\nUser request: {user_input}\n\nOutput (JSON only, no thinking):"}
        ]

        # Non-streaming for fast JSON response
        response = client.chat_complete(messages)
        content = client.extract_content(response)

        if not content or not content.strip():
            return '{"tool": "none", "confidence": "low", "reasoning": "empty response from model"}'

        # Try to extract JSON from response (model might wrap it in markdown or thinking tags)
        content = content.strip()

        # Remove thinking tags first - they often wrap the entire response
        # Remove everything from <think> to </think> (inclusive)
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)

        # If there's a dangling <think> tag, remove everything from it onwards
        if '<think>' in content:
            content = content[:content.index('<think>')]

        content = content.strip()

        # Remove markdown code blocks
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(l for l in lines if not l.startswith("```"))
            content = content.strip()

        # Now try to extract JSON object
        # Look for a line that starts with { and contains "tool"
        # Use a more permissive regex that handles multi-line JSON
        json_match = re.search(r'\{.*?"tool".*?\}', content, re.DOTALL)
        if json_match:
            content = json_match.group(0)
        else:
            # Fallback: if content starts with {, assume it's all JSON
            if content.startswith('{'):
                # Try to find the matching closing brace
                brace_count = 0
                for i, char in enumerate(content):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            content = content[:i+1]
                            break

        # Validate JSON
        try:
            parsed = json.loads(content)
            if "tool" not in parsed:
                parsed["tool"] = "none"
            if "confidence" not in parsed:
                parsed["confidence"] = "low"
            if "reasoning" not in parsed:
                parsed["reasoning"] = "no reasoning provided"
            return json.dumps(parsed)
        except json.JSONDecodeError:
            logger.warning(f"Intent detector returned invalid JSON after cleaning: {content[:200]}")
            return '{"tool": "none", "confidence": "low", "reasoning": "invalid JSON from model"}'

    except Exception as e:
        logger.error(f"Intent detector error: {e}")
        return f'{{"tool": "none", "confidence": "low", "reasoning": "error: {str(e)}"}}'
