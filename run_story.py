"""Main entrypoint for generating YouTube story content."""

import json
from pathlib import Path

import click

from config import load_settings
from image_generator import generate_images_from_prompts
from logging_config import get_logger
from story_generator import StoryGenerator, StoryRequest
from utils import create_run_output_dir, slugify
from video_composer import create_video_from_images_and_audio
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
@click.option(
    "--generate-images",
    is_flag=True,
    default=False,
    help="Generate images from prompts using Hugging Face (free)",
)
@click.option(
    "--generate-video",
    is_flag=True,
    default=False,
    help="Generate final video combining images and audio",
)
def main(
    topic: str,
    target_seconds: int,
    num_images: int,
    generate_images: bool,
    generate_video: bool,
) -> None:
    """
    Generate AI story content for YouTube Shorts.

    This script generates:
    - A short story script (30-60 seconds of spoken text)
    - A strong hook line
    - A YouTube title
    - A YouTube description
    - A list of image prompts (for 4-8 images)
    - An MP3 narration file
    - Images (if --generate-images flag is used)
    - Final video (if --generate-video flag is used)

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
    logger.info(f"Generate images: {generate_images}")
    logger.info(f"Generate video: {generate_video}")
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
        narration_path = None
        try:
            narration_path = output_dir / "narration.mp3"
            generate_voice_audio(result.story_script, narration_path, settings, logger)
            logger.info(f"Voice audio generated: {narration_path}")
        except Exception as e:
            logger.error(f"Failed to generate voice audio: {e}")
            logger.warning("Continuing without audio file...")
            narration_path = None

        # Generate images
        image_paths = []
        if generate_images:
            logger.info("Step 5: Generating images from prompts...")
            try:
                images_dir = output_dir / "images"
                image_paths = generate_images_from_prompts(
                    result.image_prompts, images_dir, settings, logger
                )
                logger.info(f"Generated {len(image_paths)} images")
            except Exception as e:
                logger.error(f"Failed to generate images: {e}")
                logger.warning("Continuing without images...")
        else:
            logger.info("Step 5: Skipping image generation (use --generate-images to enable)")

        # Generate video
        if generate_video:
            logger.info("Step 6: Generating final video...")
            if not image_paths:
                logger.warning("No images available for video generation")
                logger.warning("Run with --generate-images first, or provide images manually")
            elif not narration_path or not narration_path.exists():
                logger.warning("No audio available for video generation")
                logger.warning("Audio generation must succeed for video creation")
            else:
                try:
                    video_path = output_dir / "video.mp4"
                    create_video_from_images_and_audio(
                        image_paths,
                        narration_path,
                        video_path,
                        settings,
                        logger,
                        show_text=True,
                        text_content=result.story_script,
                    )
                    logger.info(f"Video generated: {video_path}")
                except Exception as e:
                    logger.error(f"Failed to generate video: {e}")
                    logger.warning("Continuing without video file...")
        else:
            logger.info("Step 6: Skipping video generation (use --generate-video to enable)")

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
        if image_paths:
            print(f"  - {len(image_paths)} images in images/ directory")
        if (output_dir / "video.mp4").exists():
            print(f"  - video.mp4")

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        print("Check the logs for more details.")
        raise click.Abort()


if __name__ == "__main__":
    main()

