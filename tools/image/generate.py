"""
Image generation tool using Flux Schnell model.
"""

import logging
from pathlib import Path
from datetime import datetime
import requests

logger = logging.getLogger(__name__)


def generate_image(prompt: str, filename: str = "") -> str:
    """
    Generate an image from a text prompt using Flux Schnell model.

    Args:
        prompt: Text description of the image to generate
        filename: Optional filename to save image (default: auto-generated with timestamp)

    Returns:
        Path to the generated image file
    """
    if not prompt or not isinstance(prompt, str):
        return "Error: prompt must be a non-empty string"

    if len(prompt) > 1000:
        return "Error: prompt too long (max 1000 characters)"

    try:
        import config

        logger.info(f"Generating image with Flux Schnell: {prompt[:100]}...")

        # Get image generation config
        model_config = config.SPECIALIZED_MODELS.get("image_generation")
        if not model_config:
            return "Error: Image generation not configured. Use /models to set up the image_generation endpoint."

        # Determine endpoint
        endpoint_key = config.MODEL_ENDPOINTS.get("image_generation", "local")
        if endpoint_key == "local":
            return "Error: Image generation requires a HuggingFace endpoint. Use /models to configure it."

        # Get HF endpoint config
        hf_config = config.HF_ENDPOINTS.get(endpoint_key)
        if not hf_config or not hf_config.get("enabled", True):
            return f"Error: HuggingFace endpoint '{endpoint_key}' not found or disabled."

        # Get HF token
        hf_token = getattr(config, 'HF_TOKEN', None)
        if not hf_token:
            return "Error: HF_TOKEN not configured. Use /models to set your HuggingFace token."

        # Prepare request
        url = hf_config["url"]
        headers = {
            "Authorization": f"Bearer {hf_token}",
            "Content-Type": "application/json"
        }

        # Flux Schnell optimized parameters (16:9 aspect ratio, 1344x768)
        payload = {
            "inputs": prompt,
            "parameters": {
                "guidance_scale": 0.0,  # Flux Schnell optimized
                "num_inference_steps": 4,  # Flux Schnell optimized for 4 steps
                "width": 1344,  # 16:9 aspect ratio
                "height": 768
            }
        }

        timeout = hf_config.get("timeout", 120)

        logger.info(f"Sending request to {url}")
        print(f"\n🎨 Generating image (1344x768, ~{timeout}s)...\n", flush=True)

        # Make request
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)

        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}"
            try:
                error_detail = response.json()
                error_msg += f": {error_detail}"
            except:
                error_msg += f": {response.text[:200]}"
            return f"Error: Image generation failed - {error_msg}"

        # Save image
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"generated_{timestamp}.png"

        # Ensure .png extension
        if not filename.endswith(('.png', '.jpg', '.jpeg')):
            filename += '.png'

        filepath = Path(filename)
        filepath.write_bytes(response.content)

        file_size = len(response.content) / 1024  # KB
        logger.info(f"Image saved to {filepath} ({file_size:.1f} KB)")

        return f"✅ Image generated successfully!\nSaved to: {filepath}\nSize: {file_size:.1f} KB\nResolution: 1344x768 (16:9)"

    except requests.Timeout:
        return f"Error: Image generation timed out after {timeout}s. Flux Schnell is usually fast - check endpoint status."
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        return f"Error: Failed to generate image: {str(e)}"
