"""Main entrypoint for generating YouTube story content."""

import json
from pathlib import Path

import click

from config import load_settings
from logging_config import get_logger
from story_generator import StoryGenerator, StoryRequest
from utils import create_run_output_dir, slugify
from voice_generator import generate_voice_audio


@click.command()
@click.option(
    "--topic",
    required=True,
    type=str,
    help="Topic for the story (e.g., 'teen laughs in court after verdict')",
)
@click.option(
    "--target-seconds",
    default=45,
    type=int,
    help="Target duration in seconds (default: 45)",
)
@click.option(
    "--num-images",
    default=6,
    type=int,
    help="Number of image prompts to generate (default: 6)",
)
def main(topic: str, target_seconds: int, num_images: int) -> None:
    """
    Generate AI story content for YouTube Shorts.

    This script generates:
    - A short story script (30-60 seconds of spoken text)
    - A strong hook line
    - A YouTube title
    - A YouTube description
    - A list of image prompts (for 4-8 images)
    - An MP3 narration file

    All outputs are saved to a timestamped folder under outputs/.
    """
    # Load settings
    try:
        settings = load_settings()
    except Exception as e:
        print(f"Error loading settings: {e}")
        print("Please ensure .env file exists with required API keys.")
        return

    # Initialize logger
    logger = get_logger(__name__)

    logger.info("=" * 60)
    logger.info("Starting YouTube Story Generator")
    logger.info(f"Topic: {topic}")
    logger.info(f"Target duration: {target_seconds} seconds")
    logger.info(f"Number of images: {num_images}")
    logger.info("=" * 60)

    try:
        # Build story request
        request = StoryRequest(
            topic=topic,
            target_duration_seconds=target_seconds,
            num_images=num_images,
        )

        # Generate story
        logger.info("Step 1: Generating story content...")
        generator = StoryGenerator(settings, logger)
        result = generator.generate_story(request)

        # Create output directory
        logger.info("Step 2: Creating output directory...")
        slug = slugify(topic)
        output_dir = create_run_output_dir(settings.output_base_dir, slug)
        logger.info(f"Output directory: {output_dir}")

        # Write text files
        logger.info("Step 3: Writing output files...")

        # Hook
        (output_dir / "hook.txt").write_text(result.hook, encoding="utf-8")

        # Story script
        (output_dir / "story_script.txt").write_text(result.story_script, encoding="utf-8")

        # Title
        (output_dir / "title.txt").write_text(result.title, encoding="utf-8")

        # Description
        (output_dir / "description.txt").write_text(result.description, encoding="utf-8")

        # Image prompts (numbered, one per line)
        image_prompts_text = "\n".join(f"{i+1}. {prompt}" for i, prompt in enumerate(result.image_prompts))
        (output_dir / "image_prompts.txt").write_text(image_prompts_text, encoding="utf-8")

        # Metadata JSON
        metadata = {
            "topic": topic,
            "target_duration_seconds": target_seconds,
            "num_images": num_images,
            "hook": result.hook,
            "story_script": result.story_script,
            "title": result.title,
            "description": result.description,
            "image_prompts": result.image_prompts,
        }
        (output_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        logger.info("Text files written successfully")

        # Generate voice audio
        logger.info("Step 4: Generating voice audio...")
        try:
            narration_path = output_dir / "narration.mp3"
            generate_voice_audio(result.story_script, narration_path, settings, logger)
            logger.info(f"Voice audio generated: {narration_path}")
        except Exception as e:
            logger.error(f"Failed to generate voice audio: {e}")
            logger.warning("Continuing without audio file...")

        # Summary
        logger.info("=" * 60)
        logger.info("Story generation complete!")
        logger.info(f"Output directory: {output_dir.absolute()}")
        logger.info("=" * 60)

        print(f"\n✅ Success! Output saved to: {output_dir.absolute()}")
        print(f"\nGenerated files:")
        print(f"  - hook.txt")
        print(f"  - story_script.txt")
        print(f"  - title.txt")
        print(f"  - description.txt")
        print(f"  - image_prompts.txt")
        print(f"  - metadata.json")
        if (output_dir / "narration.mp3").exists():
            print(f"  - narration.mp3")

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        print("Check the logs for more details.")
        raise click.Abort()


if __name__ == "__main__":
    main()

