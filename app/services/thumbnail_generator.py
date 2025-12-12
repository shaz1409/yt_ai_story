"""Thumbnail Generator - generates YouTube thumbnails from video frames or HF generation."""

import numpy as np
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoFileClip

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import EpisodeMetadata, VideoPlan
from app.services.hf_endpoint_client import HFEndpointClient


class ThumbnailGenerator:
    """Generates YouTube thumbnails (1280x720) from video or HF generation."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize thumbnail generator.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger
        self.thumbnail_enabled = getattr(settings, "thumbnail_enabled", True)
        self.thumbnail_mode = getattr(settings, "thumbnail_mode", "hybrid").lower()
        
        # Initialize HF client if needed
        self.hf_client = None
        if self.thumbnail_mode in ["generated", "hybrid"]:
            try:
                self.hf_client = HFEndpointClient(settings, logger)
            except Exception as e:
                self.logger.warning(f"HF client not available for thumbnail generation: {e}")
        
        # Create thumbnails directory
        self.thumbnails_dir = Path("outputs/thumbnails")
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)

    def generate_thumbnail(
        self,
        video_plan: VideoPlan,
        video_path: Path,
        episode_id: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Generate a thumbnail for an episode.

        Args:
            video_plan: VideoPlan with episode metadata
            video_path: Path to the rendered video file
            episode_id: Optional episode ID (defaults to video_plan.episode_id)

        Returns:
            Path to generated thumbnail, or None if generation failed/disabled
        """
        if not self.thumbnail_enabled:
            self.logger.debug("Thumbnail generation is disabled")
            return None

        episode_id = episode_id or video_plan.episode_id
        thumbnail_path = self.thumbnails_dir / f"{episode_id}.jpg"

        # If thumbnail already exists, reuse it
        if thumbnail_path.exists():
            self.logger.info(f"Thumbnail already exists: {thumbnail_path}")
            return thumbnail_path

        self.logger.info(f"Generating thumbnail for episode: {episode_id}")
        self.logger.info(f"Thumbnail mode: {self.thumbnail_mode}")

        try:
            if self.thumbnail_mode == "frame":
                return self._generate_frame_thumbnail(video_path, thumbnail_path, video_plan)
            elif self.thumbnail_mode == "generated":
                return self._generate_hf_thumbnail(video_path, thumbnail_path, video_plan)
            elif self.thumbnail_mode == "hybrid":
                # Try generated first, fallback to frame
                try:
                    result = self._generate_hf_thumbnail(video_path, thumbnail_path, video_plan)
                    if result:
                        self.logger.info("✅ Generated thumbnail via HF (hybrid mode)")
                        return result
                except Exception as e:
                    self.logger.warning(f"HF thumbnail generation failed, falling back to frame: {e}")
                
                # Fallback to frame
                return self._generate_frame_thumbnail(video_path, thumbnail_path, video_plan)
            else:
                self.logger.warning(f"Unknown thumbnail mode: {self.thumbnail_mode}, using frame mode")
                return self._generate_frame_thumbnail(video_path, thumbnail_path, video_plan)

        except Exception as e:
            self.logger.error(f"Thumbnail generation failed: {e}", exc_info=True)
            return None

    def _generate_frame_thumbnail(
        self, video_path: Path, thumbnail_path: Path, video_plan: VideoPlan
    ) -> Path:
        """
        Generate thumbnail by extracting best frame from video.

        Args:
            video_path: Path to video file
            thumbnail_path: Path to save thumbnail
            video_plan: VideoPlan for context

        Returns:
            Path to generated thumbnail
        """
        self.logger.info("Extracting best frame from video...")

        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        try:
            clip = VideoFileClip(str(video_path))
            duration = clip.duration

            # Strategy: Find visually interesting frame
            # 1. Prioritize frames with character talking-heads (if available)
            # 2. Or high-contrast scene frames
            # 3. Or middle of video (usually most interesting)

            best_frame_time = duration / 2  # Default: middle of video

            # If we have character spoken lines, try to find a frame during character speech
            if video_plan.character_spoken_lines:
                # Use first character spoken line timing
                first_line = video_plan.character_spoken_lines[0]
                # Approximate timing (character clips are usually in first 30 seconds)
                # Use approx_timing_seconds if available, otherwise estimate
                if hasattr(first_line, "approx_timing_seconds") and first_line.approx_timing_seconds > 0:
                    best_frame_time = min(first_line.approx_timing_seconds, duration * 0.5)
                else:
                    best_frame_time = min(15.0, duration * 0.3)

            # Extract frame
            frame = clip.get_frame(best_frame_time)
            clip.close()

            # Convert to PIL Image
            img = Image.fromarray(frame.astype(np.uint8))

            # Resize/crop to 1280x720 (YouTube thumbnail standard)
            thumbnail = self._resize_to_thumbnail(img, target_size=(1280, 720))

            # Save
            thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
            thumbnail.save(thumbnail_path, "JPEG", quality=95)
            self.logger.info(f"✅ Frame-based thumbnail saved: {thumbnail_path}")

            return thumbnail_path

        except Exception as e:
            self.logger.error(f"Frame extraction failed: {e}")
            raise

    def _generate_hf_thumbnail(
        self, video_path: Path, thumbnail_path: Path, video_plan: VideoPlan
    ) -> Path:
        """
        Generate thumbnail using HF image generation.

        Args:
            video_path: Path to video file (for context, not used directly)
            thumbnail_path: Path to save thumbnail
            video_plan: VideoPlan with episode metadata

        Returns:
            Path to generated thumbnail
        """
        if not self.hf_client:
            raise ValueError("HF client not available for thumbnail generation")

        self.logger.info("Generating thumbnail via HF endpoint...")

        # Build prompt from video plan metadata
        metadata = video_plan.metadata
        title = video_plan.title
        logline = video_plan.logline
        niche = metadata.niche if metadata else "courtroom"
        primary_emotion = metadata.primary_emotion if metadata else "dramatic"
        style = video_plan.style

        # Build dramatic thumbnail prompt
        prompt = self._build_thumbnail_prompt(
            title=title,
            logline=logline,
            niche=niche,
            primary_emotion=primary_emotion,
            style=style,
        )

        self.logger.info(f"Thumbnail prompt: {prompt[:120]}...")

        # Generate image via HF
        self.hf_client.generate_image(
            prompt=prompt,
            output_path=thumbnail_path,
            image_type="scene_broll",
            seed=None,  # Random seed for variety
            sharpness=10,  # High sharpness for thumbnail
            realism_level="ultra",
            film_style="kodak_portra",
        )

        # Resize to 1280x720 if needed
        img = Image.open(thumbnail_path)
        thumbnail = self._resize_to_thumbnail(img, target_size=(1280, 720))
        thumbnail.save(thumbnail_path, "JPEG", quality=95)

        # Optionally overlay title text
        if getattr(self.settings, "thumbnail_add_text", True):
            thumbnail = self._add_text_overlay(thumbnail, title, logline)
            thumbnail.save(thumbnail_path, "JPEG", quality=95)

        self.logger.info(f"✅ HF-generated thumbnail saved: {thumbnail_path}")
        return thumbnail_path

    def _build_thumbnail_prompt(
        self,
        title: str,
        logline: str,
        niche: str,
        primary_emotion: str,
        style: str,
    ) -> str:
        """
        Build a dramatic thumbnail prompt.

        Args:
            title: Episode title
            logline: Episode logline
            niche: Story niche
            primary_emotion: Primary emotion
            style: Story style

        Returns:
            Thumbnail generation prompt
        """
        # Map emotions to visual descriptors
        emotion_descriptors = {
            "shocked": "shocked expressions, wide eyes, dramatic moment",
            "angered": "tense confrontation, angry faces, high stakes",
            "rage": "intense conflict, emotional outburst, dramatic tension",
            "sad": "emotional moment, somber atmosphere, impactful scene",
            "relieved": "resolution moment, emotional release, satisfying conclusion",
            "vindicated": "justice served, triumphant moment, emotional payoff",
        }
        emotion_desc = emotion_descriptors.get(primary_emotion, "dramatic moment, high emotional impact")

        # Build prompt
        prompt = (
            f"cinematic, highly detailed, dramatic YouTube thumbnail, "
            f"{niche} scene, {emotion_desc}, "
            f"professional composition, high contrast, vibrant colors, "
            f"1280x720 aspect ratio, vertical framing, "
            f"engaging visual that captures: {logline[:100]}, "
            f"photorealistic, film quality, shallow depth of field, "
            f"cinematic lighting, dramatic shadows"
        )

        return prompt

    def _resize_to_thumbnail(self, img: Image.Image, target_size: tuple[int, int] = (1280, 720)) -> Image.Image:
        """
        Resize and crop image to thumbnail dimensions.

        Args:
            img: Input image
            target_size: Target size (width, height)

        Returns:
            Resized/cropped image
        """
        target_width, target_height = target_size
        img_width, img_height = img.size

        # Calculate aspect ratios
        target_aspect = target_width / target_height
        img_aspect = img_width / img_height

        if img_aspect > target_aspect:
            # Image is wider - crop width
            new_width = int(img_height * target_aspect)
            left = (img_width - new_width) // 2
            img = img.crop((left, 0, left + new_width, img_height))
        else:
            # Image is taller - crop height
            new_height = int(img_width / target_aspect)
            top = (img_height - new_height) // 2
            img = img.crop((0, top, img_width, top + new_height))

        # Resize to exact target size
        img = img.resize(target_size, Image.Resampling.LANCZOS)
        return img

    def _add_text_overlay(self, img: Image.Image, title: str, logline: Optional[str] = None) -> Image.Image:
        """
        Add text overlay to thumbnail (optional).

        Args:
            img: Thumbnail image
            title: Title text
            logline: Optional logline text

        Returns:
            Image with text overlay
        """
        try:
            # Create a copy for drawing
            overlay = img.copy()
            draw = ImageDraw.Draw(overlay)

            # Try to load a bold font, fallback to default
            try:
                # Try system fonts (varies by OS)
                font_paths = [
                    "/System/Library/Fonts/Helvetica.ttc",  # macOS
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
                    "C:/Windows/Fonts/arialbd.ttf",  # Windows
                ]
                font = None
                for path in font_paths:
                    if Path(path).exists():
                        font = ImageFont.truetype(path, 60)
                        break
                
                if font is None:
                    font = ImageFont.load_default()
            except Exception:
                font = ImageFont.load_default()

            # Shorten title if too long
            max_title_length = 40
            display_title = title[:max_title_length] + "..." if len(title) > max_title_length else title

            # Draw title with shadow for readability
            text_color = (255, 255, 255)  # White
            shadow_color = (0, 0, 0)  # Black shadow
            text_position = (40, 40)

            # Draw shadow
            for adj in [(2, 2), (2, -2), (-2, 2), (-2, -2)]:
                draw.text(
                    (text_position[0] + adj[0], text_position[1] + adj[1]),
                    display_title,
                    font=font,
                    fill=shadow_color,
                )

            # Draw text
            draw.text(text_position, display_title, font=font, fill=text_color)

            return overlay

        except Exception as e:
            self.logger.warning(f"Text overlay failed (non-critical): {e}")
            return img  # Return original if overlay fails

