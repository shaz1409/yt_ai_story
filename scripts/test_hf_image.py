#!/usr/bin/env python3
"""
Test script for Hugging Face image generation.

Tests the configured HF Inference Endpoint and generates a test image.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.services.hf_endpoint_client import HFEndpointClient


def main():
    """Main test function."""
    logger = get_logger(__name__)
    settings = Settings()
    
    logger.info("=" * 60)
    logger.info("Hugging Face Image Generation Test")
    logger.info("=" * 60)
    
    # Show configuration
    logger.info(f"HF Endpoint URL: {settings.hf_endpoint_url or '(not set)'}")
    logger.info(f"HF Endpoint Token: {'Set' if settings.hf_endpoint_token else 'Not set'}")
    logger.info("")
    
    # Test prompt
    test_prompt = "A professional courtroom setting with wooden benches, judge's bench, formal atmosphere, cinematic lighting"
    output_path = Path("outputs/hf_test/test_image.png")
    
    logger.info(f"Test prompt: {test_prompt[:80]}...")
    logger.info(f"Output path: {output_path}")
    logger.info("")
    
    # Generate image using HF Endpoint Client
    try:
        client = HFEndpointClient(settings, logger)
        client.generate_image(test_prompt, output_path)
        
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"✓ SUCCESS: Image generated using HF Endpoint")
        logger.info(f"  Saved to: {output_path.absolute()}")
        logger.info("=" * 60)
        return 0
        
    except ValueError as e:
        logger.error("")
        logger.error("=" * 60)
        logger.error(f"✗ CONFIGURATION ERROR: {e}")
        logger.error("")
        logger.error("Troubleshooting:")
        logger.error("  1. Set HF_ENDPOINT_URL in your .env file")
        logger.error("  2. Set HF_ENDPOINT_TOKEN in your .env file")
        logger.error("  3. Verify your endpoint URL is correct")
        logger.error("=" * 60)
        return 1
        
    except Exception as e:
        logger.error("")
        logger.error("=" * 60)
        logger.error(f"✗ FAILED: {e}")
        logger.error("")
        logger.error("Troubleshooting:")
        logger.error("  1. Check network connectivity")
        logger.error("  2. Verify HF_ENDPOINT_URL and HF_ENDPOINT_TOKEN are correct")
        logger.error("  3. Check if your endpoint is active and accessible")
        logger.error("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())

