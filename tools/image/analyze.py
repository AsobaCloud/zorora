"""
Image analysis tool using vision-language model.
"""

import logging
from pathlib import Path
from tools.file_ops.utils import _validate_path
from tools.specialist.client import create_specialist_client

logger = logging.getLogger(__name__)


def analyze_image(path: str, task: str = "Convert this image to markdown format, preserving all text, tables, charts, and structure. Use OCR to extract any text.") -> str:
    """
    Analyze an image using a vision-language model (VL model) for OCR and content extraction.

    Args:
        path: Path to the image file
        task: Description of what to do with the image (default: OCR and convert to markdown)

    Returns:
        Analysis/OCR output from the VL model
    """
    # Validate path security
    is_valid, error = _validate_path(path)
    if not is_valid:
        return error

    file_path = Path(path)
    if not file_path.exists():
        return f"Error: File '{path}' does not exist."
    if not file_path.is_file():
        return f"Error: '{path}' is not a file."

    # Check if it's an image file by extension
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif', '.webp'}
    if file_path.suffix.lower() not in image_extensions:
        return f"Error: '{path}' does not appear to be an image file (supported: {', '.join(image_extensions)})"

    # Check file size limit (10MB for images)
    if file_path.stat().st_size > 10_000_000:
        return f"Error: Image file '{path}' too large (>10MB)"

    try:
        import base64
        import config

        logger.info(f"Analyzing image: {path} with task: {task[:100]}...")

        # Read and encode image as base64
        with open(file_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        # Determine image MIME type
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff',
            '.webp': 'image/webp'
        }
        mime_type = mime_types.get(file_path.suffix.lower(), 'image/png')

        # Create VL model client using specialized vision config
        model_config = config.SPECIALIZED_MODELS["vision"]
        client = create_specialist_client("vision", model_config)

        # Create multimodal message with OpenAI-compatible format
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": task},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_data}"
                        }
                    }
                ]
            }
        ]

        logger.info(f"Sending image to VL model (size: {len(image_data)} bytes)")

        # Stream the response for real-time feedback
        print("\n", flush=True)  # New line before streaming
        full_response = []

        for chunk in client.chat_complete_stream(messages):
            print(chunk, end='', flush=True)
            full_response.append(chunk)

        print("\n", flush=True)  # New line after streaming

        content = ''.join(full_response)
        if not content or not content.strip():
            return "Error: VL model returned empty response"

        return content.strip()

    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        return f"Error: Failed to analyze image: {str(e)}"
