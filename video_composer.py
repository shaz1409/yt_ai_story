"""Video composition using MoviePy to combine images, audio, and text overlays."""

from pathlib import Path
from typing import Any, Optional

from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    concatenate_videoclips,
)

from config import Settings


def create_video_from_images_and_audio(
    image_paths: list[Path],
    audio_path: Path,
    output_path: Path,
    settings: Settings,
    logger: Any,
    show_text: bool = True,
    text_content: Optional[str] = None,
) -> None:
    """
    Create a video by combining images with audio narration.

    Args:
        image_paths: List of paths to image files.
        audio_path: Path to audio narration file.
        settings: Application settings.
        logger: Logger instance.
        show_text: Whether to overlay text on the video.
        text_content: Text content to overlay (if show_text is True).

    Raises:
        Exception: If video creation fails.
    """
    if not image_paths:
        raise ValueError("No images provided for video creation")

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    logger.info(f"Creating video from {len(image_paths)} images and audio...")

    try:
        # Load audio to get duration
        audio_clip = AudioFileClip(str(audio_path))
        audio_duration = audio_clip.duration
        logger.info(f"Audio duration: {audio_duration:.2f} seconds")

        # Calculate duration per image
        duration_per_image = audio_duration / len(image_paths)
        logger.info(f"Duration per image: {duration_per_image:.2f} seconds")

        # Create video clips from images
        video_clips = []
        for i, image_path in enumerate(image_paths):
            if not image_path.exists():
                logger.warning(f"Image not found: {image_path}, skipping...")
                continue

            logger.info(f"Processing image {i+1}/{len(image_paths)}: {image_path.name}")

            # Create image clip with duration
            img_clip = ImageClip(str(image_path)).set_duration(duration_per_image)

            # Resize to YouTube Shorts format (1080x1920) if needed
            img_clip = img_clip.resize(height=1920)

            # Center the image if it's not the right aspect ratio
            if img_clip.w < 1080:
                img_clip = img_clip.resize(width=1080)

            # Crop to 9:16 if needed
            if img_clip.w / img_clip.h > 9 / 16:
                # Image is too wide, crop width
                new_width = int(img_clip.h * 9 / 16)
                x_center = img_clip.w / 2
                img_clip = img_clip.crop(x_center=x_center, width=new_width)
            elif img_clip.w / img_clip.h < 9 / 16:
                # Image is too tall, crop height
                new_height = int(img_clip.w * 16 / 9)
                y_center = img_clip.h / 2
                img_clip = img_clip.crop(y_center=y_center, height=new_height)

            # Ensure final size is 1080x1920
            img_clip = img_clip.resize((1080, 1920))

            video_clips.append(img_clip)

        if not video_clips:
            raise ValueError("No valid images found for video creation")

        # Concatenate all image clips
        logger.info("Concatenating video clips...")
        final_video = concatenate_videoclips(video_clips, method="compose")

        # Add text overlay if requested
        if show_text and text_content:
            logger.info("Adding text overlay...")
            # Split text into lines for better display
            words = text_content.split()
            lines = []
            current_line = ""
            for word in words:
                if len(current_line + " " + word) <= 40:  # ~40 chars per line
                    current_line += (" " if current_line else "") + word
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)

            text_lines = "\n".join(lines[:3])  # Max 3 lines

            # Create text clip (try with font, fallback without if font not available)
            try:
                txt_clip = (
                    TextClip(
                        text_lines,
                        fontsize=60,
                        color="white",
                        font="Arial-Bold",
                        stroke_color="black",
                        stroke_width=2,
                        method="caption",
                        size=(900, None),
                        align="center",
                    )
                    .set_duration(audio_duration)
                    .set_position(("center", "bottom"))
                    .set_margin(bottom=100)
                )
            except Exception as e:
                logger.warning(f"Could not use Arial-Bold font: {e}, using default font")
                txt_clip = (
                    TextClip(
                        text_lines,
                        fontsize=60,
                        color="white",
                        stroke_color="black",
                        stroke_width=2,
                        method="caption",
                        size=(900, None),
                        align="center",
                    )
                    .set_duration(audio_duration)
                    .set_position(("center", "bottom"))
                    .set_margin(bottom=100)
                )

            # Composite text over video
            final_video = CompositeVideoClip([final_video, txt_clip])

        # Set audio
        logger.info("Adding audio to video...")
        final_video = final_video.set_audio(audio_clip)

        # Set FPS
        final_video = final_video.set_fps(24)

        # Write video file
        logger.info(f"Rendering video to: {output_path}...")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Use codec optimized for YouTube
        final_video.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            fps=24,
            preset="medium",
            bitrate="8000k",
            logger=None,  # Suppress MoviePy's verbose logging
        )

        # Clean up
        final_video.close()
        audio_clip.close()

        logger.info(f"Successfully created video: {output_path}")
        logger.info(f"Video duration: {audio_duration:.2f} seconds")

    except Exception as e:
        logger.error(f"Error creating video: {e}")
        raise

