"""Image generation using Hugging Face Stable Diffusion API (free tier)."""

import base64
import io
from pathlib import Path
from typing import Any

import requests
from PIL import Image

from config import Settings


def generate_image(
    prompt: str,
    output_path: Path,
    settings: Settings,
    logger: Any,
    model_id: str = "stabilityai/stable-diffusion-2-1",
) -> None:
    """
    Generate an image from a text prompt using Hugging Face Inference API (free tier).

    Args:
        prompt: Text prompt describing the image to generate.
        output_path: Path where the image will be saved.
        settings: Application settings (may contain HF token for higher rate limits).
        logger: Logger instance.
        model_id: Hugging Face model ID to use (default: stable-diffusion-2-1).

    Raises:
        Exception: If API call fails or response is invalid.
    """
    if not prompt or not prompt.strip():
        logger.warning("Empty prompt provided for image generation")
        raise ValueError("Prompt cannot be empty")

    logger.info(f"Generating image for prompt: {prompt[:50]}...")

    # Hugging Face Inference API endpoint (free tier, no auth required)
    api_url = f"https://api-inference.huggingface.co/models/{model_id}"

    headers = {"Content-Type": "application/json"}

    # Optional: Add token if available for higher rate limits
    hf_token = settings.huggingface_token if hasattr(settings, "huggingface_token") else ""
    if hf_token and hf_token.strip():
        headers["Authorization"] = f"Bearer {hf_token}"

    payload = {
        "inputs": prompt,
        "parameters": {
            "num_inference_steps": 20,  # Lower for faster generation (free tier)
            "guidance_scale": 7.5,
        },
    }

    try:
        logger.info("Sending request to Hugging Face API...")
        response = requests.post(api_url, json=payload, headers=headers, timeout=60)

        if response.status_code == 503:
            # Model might be loading, wait and retry once
            logger.warning("Model is loading, waiting 10 seconds and retrying...")
            import time

            time.sleep(10)
            response = requests.post(api_url, json=payload, headers=headers, timeout=60)

        if response.status_code != 200:
            error_msg = response.text
            logger.error(f"Hugging Face API error: {response.status_code} - {error_msg}")
            raise Exception(f"Hugging Face API returned status {response.status_code}: {error_msg}")

        # Save image
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.open(io.BytesIO(response.content))
        # Resize to YouTube Shorts format (9:16 aspect ratio, 1080x1920 recommended)
        target_size = (1080, 1920)
        image = image.resize(target_size, Image.Resampling.LANCZOS)
        image.save(output_path, "PNG", quality=95)

        logger.info(f"Successfully generated image: {output_path}")
        logger.info(f"Image size: {target_size[0]}x{target_size[1]}")

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error calling Hugging Face API: {e}")
        raise
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        raise


def generate_images_from_prompts(
    prompts: list[str],
    output_dir: Path,
    settings: Settings,
    logger: Any,
) -> list[Path]:
    """
    Generate multiple images from a list of prompts.

    Args:
        prompts: List of text prompts for image generation.
        output_dir: Directory where images will be saved.
        settings: Application settings.
        logger: Logger instance.

    Returns:
        List of paths to generated image files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    image_paths = []

    for i, prompt in enumerate(prompts, start=1):
        logger.info(f"Generating image {i}/{len(prompts)}...")
        image_path = output_dir / f"image_{i:02d}.png"
        try:
            generate_image(prompt, image_path, settings, logger)
            image_paths.append(image_path)
        except Exception as e:
            logger.error(f"Failed to generate image {i}: {e}")
            logger.warning("Continuing with remaining images...")
            # Continue with other images even if one fails

    logger.info(f"Generated {len(image_paths)}/{len(prompts)} images successfully")
    return image_paths

