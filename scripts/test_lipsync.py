#!/usr/bin/env python3
"""Test script for lip-sync provider integration."""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import Settings
from app.core.logging_config import get_logger, setup_logging
from app.services.lipsync_provider import get_lipsync_provider


def main():
    """Test lip-sync provider with sample image and audio."""
    parser = argparse.ArgumentParser(description="Test lip-sync provider")
    parser.add_argument(
        "--image",
        type=str,
        required=True,
        help="Path to character face image (PNG/JPG)",
    )
    parser.add_argument(
        "--audio",
        type=str,
        required=True,
        help="Path to dialogue audio file (MP3/WAV)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="test_lipsync_output.mp4",
        help="Output video path (default: test_lipsync_output.mp4)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["did", "heygen", "auto"],
        default="auto",
        help="Lip-sync provider to use (default: auto-detect from config)",
    )
    args = parser.parse_args()

    # Setup logging
    setup_logging()
    logger = get_logger(__name__)

    # Load settings
    settings = Settings()
    
    # Override provider if specified
    if args.provider != "auto":
        settings.lipsync_provider = args.provider
        settings.lipsync_enabled = True
        logger.info(f"Using provider: {args.provider}")

    # Validate inputs
    image_path = Path(args.image)
    audio_path = Path(args.audio)
    output_path = Path(args.output)

    if not image_path.exists():
        logger.error(f"Image file not found: {image_path}")
        return 1

    if not audio_path.exists():
        logger.error(f"Audio file not found: {audio_path}")
        return 1

    logger.info("=" * 60)
    logger.info("LIP-SYNC TEST")
    logger.info("=" * 60)
    logger.info(f"Image: {image_path}")
    logger.info(f"Audio: {audio_path}")
    logger.info(f"Output: {output_path}")
    logger.info(f"Provider: {args.provider} (from config: {settings.lipsync_provider})")
    logger.info("=" * 60)

    # Get lip-sync provider
    provider = get_lipsync_provider(settings, logger)
    
    if not provider:
        logger.error("No lip-sync provider available!")
        logger.error("Please configure:")
        logger.error("  - LIPSYNC_ENABLED=true")
        logger.error("  - LIPSYNC_PROVIDER=did or heygen")
        logger.error("  - LIPSYNC_API_KEY=xxx (or DID_API_KEY / HEYGEN_API_KEY)")
        return 1

    logger.info(f"Using provider: {provider.__class__.__name__}")

    # Generate talking-head
    try:
        logger.info("Generating lip-sync video...")
        result_path = provider.generate_talking_head(image_path, audio_path, output_path)
        logger.info("=" * 60)
        logger.info("✅ SUCCESS!")
        logger.info("=" * 60)
        logger.info(f"Output video: {result_path}")
        logger.info(f"File size: {result_path.stat().st_size / 1024 / 1024:.2f} MB")
        
        # Check duration
        try:
            from moviepy.editor import VideoFileClip
            clip = VideoFileClip(str(result_path))
            logger.info(f"Video duration: {clip.duration:.2f}s")
            clip.close()
        except Exception as e:
            logger.warning(f"Could not check video duration: {e}")
        
        return 0

    except NotImplementedError as e:
        logger.error("=" * 60)
        logger.error("❌ PROVIDER NOT IMPLEMENTED")
        logger.error("=" * 60)
        logger.error(f"{e}")
        return 1

    except Exception as e:
        logger.error("=" * 60)
        logger.error("❌ FAILED")
        logger.error("=" * 60)
        logger.error(f"Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())

