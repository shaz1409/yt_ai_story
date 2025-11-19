#!/usr/bin/env python3
"""
Test script for Hugging Face image generation.

Tests the configured HF image models and generates a test image.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import Settings
from app.core.logging_config import get_logger
import requests
import io
from PIL import Image


def generate_image_hf(
    prompt: str,
    output_path: Path,
    settings: Settings,
    logger,
) -> tuple[bool, str]:
    """
    Generate image using Hugging Face API with configurable models.
    
    Returns:
        Tuple of (success: bool, model_name: str or error_message: str)
    """
    # Build model list: primary first (if set), then fallback models
    models_to_try = []
    if settings.hf_image_model_primary:
        models_to_try.append(settings.hf_image_model_primary)
    models_to_try.extend(settings.hf_image_models)
    
    if not models_to_try:
        return False, "No models configured in hf_image_models"
    
    headers = {"Content-Type": "application/json"}
    hf_token = getattr(settings, "huggingface_token", "")
    if hf_token and hf_token.strip():
        headers["Authorization"] = f"Bearer {hf_token}"

    payload = {
        "inputs": prompt,
        "parameters": {
            "num_inference_steps": 20,
            "guidance_scale": 7.5,
        },
    }

    errors = []
    for model_id in models_to_try:
        api_url = f"https://api-inference.huggingface.co/models/{model_id}"
        try:
            logger.info(f"Trying model: {model_id}")
            response = requests.post(api_url, json=payload, headers=headers, timeout=60)

            if response.status_code == 503:
                logger.warning(f"Model {model_id} loading, waiting 10 seconds...")
                import time
                time.sleep(10)
                response = requests.post(api_url, json=payload, headers=headers, timeout=60)

            if response.status_code == 410:
                error_msg = f"Model {model_id} returned 410 (Gone) – check if this model still supports HF Inference API."
                logger.warning(error_msg)
                errors.append(error_msg)
                continue

            if response.status_code != 200:
                # Extract error message from response body (first 200 chars)
                error_body = ""
                try:
                    error_body = response.text[:200] if hasattr(response, "text") else ""
                except:
                    pass
                
                error_msg = f"Model {model_id}: status {response.status_code}"
                if error_body:
                    error_msg += f" - {error_body}"
                
                logger.warning(error_msg)
                errors.append(error_msg)
                continue

            # Success - save image
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image = Image.open(io.BytesIO(response.content))
            target_size = (1080, 1920)  # 9:16 vertical
            image = image.resize(target_size, Image.Resampling.LANCZOS)
            image.save(output_path, "PNG", quality=95)
            logger.info(f"✓ Successfully generated image using model: {model_id}")
            return True, model_id
                
        except Exception as e:
            error_msg = f"Model {model_id} failed: {e}"
            logger.warning(error_msg)
            errors.append(error_msg)
            continue
    
    # All models failed
    error_summary = "\n".join(f"  - {err}" for err in errors)
    return False, f"All models failed:\n{error_summary}"


def main():
    """Main test function."""
    logger = get_logger(__name__)
    settings = Settings()
    
    logger.info("=" * 60)
    logger.info("Hugging Face Image Generation Test")
    logger.info("=" * 60)
    
    # Show configuration
    logger.info(f"Primary model (if set): {settings.hf_image_model_primary or '(none)'}")
    logger.info(f"Fallback models: {settings.hf_image_models}")
    logger.info(f"HF Token: {'Set' if settings.huggingface_token else 'Not set (optional)'}")
    logger.info("")
    
    # Test prompt
    test_prompt = "A professional courtroom setting with wooden benches, judge's bench, formal atmosphere, cinematic lighting"
    output_path = Path("outputs/hf_test/test_image.png")
    
    logger.info(f"Test prompt: {test_prompt[:80]}...")
    logger.info(f"Output path: {output_path}")
    logger.info("")
    
    # Generate image
    success, result = generate_image_hf(test_prompt, output_path, settings, logger)
    
    logger.info("")
    logger.info("=" * 60)
    if success:
        logger.info(f"✓ SUCCESS: Image generated using model: {result}")
        logger.info(f"  Saved to: {output_path.absolute()}")
    else:
        logger.error(f"✗ FAILED: {result}")
        logger.error("")
        logger.error("Troubleshooting:")
        logger.error("  1. Check if models are available on Hugging Face Inference API")
        logger.error("  2. Verify HF_IMAGE_MODEL_PRIMARY or hf_image_models in config")
        logger.error("  3. Check network connectivity")
        logger.error("  4. If using token, verify HUGGINGFACE_TOKEN is set correctly")
    logger.info("=" * 60)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

