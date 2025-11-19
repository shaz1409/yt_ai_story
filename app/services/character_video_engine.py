"""Character Video Engine - generates character face images and talking-head clips."""

import io
from pathlib import Path
from typing import Any, Optional

import requests
from moviepy.editor import AudioFileClip, ImageClip
from PIL import Image

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import Character, DialogueLine, VideoPlan


class TalkingHeadProvider:
    """Abstract provider for talking-head video generation."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize talking-head provider.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger

    def generate_talking_head(
        self, base_image_path: Path, audio_path: Path, output_path: Path
    ) -> Path:
        """
        Generate a talking-head video clip from base image and audio.

        Args:
            base_image_path: Path to character's base face image
            audio_path: Path to dialogue audio file
            output_path: Path to save output video clip

        Returns:
            Path to generated video clip

        Note:
            This is a stub implementation that creates a simple video with
            the static image + subtle zoom/pan + synced audio. In production,
            this can be swapped with a real talking-head API (D-ID, HeyGen, etc.).
        """
        self.logger.info(f"Generating talking-head clip: {base_image_path.name} + {audio_path.name}")

        try:
            # Load audio to get duration
            audio_clip = AudioFileClip(str(audio_path))
            duration = audio_clip.duration

            # Load base image
            image_clip = ImageClip(str(base_image_path))
            image_clip = image_clip.set_duration(duration)

            # Resize to vertical format (1080x1920)
            target_size = (1080, 1920)
            image_clip = image_clip.resize(target_size)

            # Add subtle zoom effect (zoom in from 1.0 to 1.05 over duration)
            def make_frame(t):
                zoom_factor = 1.0 + (0.05 * (t / duration))
                new_size = (int(target_size[0] * zoom_factor), int(target_size[1] * zoom_factor))
                resized = image_clip.resize(new_size)
                # Center crop
                x_center = (new_size[0] - target_size[0]) // 2
                y_center = (new_size[1] - target_size[1]) // 2
                frame = resized.get_frame(t)
                if len(frame.shape) == 3:
                    return frame[y_center : y_center + target_size[1], x_center : x_center + target_size[0]]
                return frame

            from moviepy.video.VideoClip import VideoClip
            video_clip = VideoClip(make_frame, duration=duration)
            video_clip = video_clip.set_audio(audio_clip)
            video_clip = video_clip.set_fps(24)

            # Write video
            output_path.parent.mkdir(parents=True, exist_ok=True)
            video_clip.write_videofile(
                str(output_path),
                codec="libx264",
                audio_codec="aac",
                fps=24,
                preset="medium",
                logger=None,  # Suppress MoviePy logs
            )

            # Cleanup
            audio_clip.close()
            video_clip.close()

            self.logger.info(f"Talking-head clip generated: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Failed to generate talking-head clip: {e}")
            raise


class CharacterVideoEngine:
    """Generates character face images and talking-head video clips."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize character video engine.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger
        self.talking_head_provider = TalkingHeadProvider(settings, logger)

    def generate_character_face_image(
        self, character: Character, output_dir: Path, style: str = "courtroom_drama"
    ) -> Path:
        """
        Generate a single photorealistic base image for this character.

        Args:
            character: Character object
            output_dir: Directory to save image
            style: Story style (for prompt generation)

        Returns:
            Path to the generated image file
        """
        self.logger.info(f"Generating face image for character: {character.name} ({character.role})")

        output_dir.mkdir(parents=True, exist_ok=True)
        image_path = output_dir / f"character_{character.id}_face.png"

        # Build photoreal prompt
        prompt = self._build_character_face_prompt(character, style)

        # Generate image
        try:
            self._generate_character_image(prompt, image_path)
        except Exception as e:
            self.logger.error(f"Failed to generate character image: {e}, creating placeholder")
            self._create_placeholder_character_image(image_path, character)

        return image_path

    def generate_talking_head_clip(
        self,
        character: Character,
        dialogue_line: DialogueLine,
        audio_path: Path,
        output_dir: Path,
        style: str = "courtroom_drama",
    ) -> Path:
        """
        Generate a short talking-head video clip for a dialogue line.

        Args:
            character: Character object
            dialogue_line: DialogueLine to animate
            audio_path: Path to dialogue audio file
            output_dir: Directory to save clip
            style: Story style

        Returns:
            Path to the generated video clip
        """
        self.logger.info(
            f"Generating talking-head clip for {character.name}: '{dialogue_line.text[:50]}...'"
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        clip_path = output_dir / f"talking_head_{character.id}_{dialogue_line.character_id}.mp4"

        # Ensure character face image exists
        character_faces_dir = output_dir / "character_faces"
        face_image_path = character_faces_dir / f"character_{character.id}_face.png"

        if not face_image_path.exists():
            self.logger.info(f"Character face image not found, generating: {face_image_path}")
            self.generate_character_face_image(character, character_faces_dir, style)

        # Generate talking-head clip
        self.talking_head_provider.generate_talking_head(face_image_path, audio_path, clip_path)

        return clip_path

    def ensure_character_assets(
        self, video_plan: VideoPlan, output_dir: Path, style: str = "courtroom_drama"
    ) -> dict[str, Path]:
        """
        Ensure all main characters have base face images generated.

        Args:
            video_plan: VideoPlan with characters
            output_dir: Directory to save assets
            style: Story style

        Returns:
            Mapping: character_id -> image_path
        """
        self.logger.info("Ensuring character assets are generated...")

        character_faces_dir = output_dir / "character_faces"
        character_faces_dir.mkdir(parents=True, exist_ok=True)

        character_assets = {}

        # Generate faces for all non-narrator characters
        for character in video_plan.characters:
            if character.role.lower() != "narrator":
                face_path = character_faces_dir / f"character_{character.id}_face.png"

                if not face_path.exists():
                    self.logger.info(f"Generating face for character: {character.name}")
                    face_path = self.generate_character_face_image(character, character_faces_dir, style)
                else:
                    self.logger.debug(f"Character face already exists: {character.name}")

                character_assets[character.id] = face_path

        self.logger.info(f"Ensured {len(character_assets)} character face images")
        return character_assets

    def _build_character_face_prompt(self, character: Character, style: str) -> str:
        """
        Build photorealistic character face prompt.

        Args:
            character: Character object
            style: Story style

        Returns:
            Image generation prompt
        """
        # Extract appearance details
        appearance = character.appearance or {}
        age = appearance.get("age", "middle-aged")
        gender = appearance.get("gender", "")
        ethnicity = appearance.get("ethnicity", "")
        hair = appearance.get("hair", "")
        expression = appearance.get("expression", "serious")

        # Build role-specific context
        role_context = {
            "judge": "authoritative judge in black robes",
            "defendant": "defendant in formal attire",
            "lawyer": "professional lawyer in business suit",
            "prosecutor": "serious prosecutor in formal suit",
            "witness": "witness in courtroom",
        }
        role_desc = role_context.get(character.role.lower(), f"{character.role} in courtroom")

        # Build prompt parts
        prompt_parts = [
            "Photorealistic portrait",
            f"{age} {gender}".strip() if gender else age,
            ethnicity if ethnicity else "",
            role_desc,
            f"facial expression: {expression}",
            hair if hair else "",
            f"{character.personality} personality",
            f"{style.replace('_', ' ')} style",
            "cinematic lighting",
            "ultra-realistic",
            "4k quality",
            "vertical portrait",
            "close-up headshot",
            "still from a legal drama TV show",
            "professional photography",
        ]

        # Filter out empty parts and join
        prompt = ". ".join([p for p in prompt_parts if p.strip()]) + "."

        return prompt

    def _generate_character_image(self, prompt: str, output_path: Path) -> None:
        """
        Generate character image using Hugging Face or stub.

        Args:
            prompt: Image generation prompt
            output_path: Path to save image
        """
        hf_token = getattr(self.settings, "huggingface_token", None)

        if hf_token:
            self._generate_image_hf(prompt, output_path)
        else:
            self.logger.warning("No Hugging Face token - using placeholder character image")
            self._create_placeholder_character_image(output_path, None, prompt)

    def _generate_image_hf(self, prompt: str, output_path: Path) -> None:
        """Generate image using Hugging Face API."""
        model_id = "stabilityai/stable-diffusion-2-1"
        api_url = f"https://api-inference.huggingface.co/models/{model_id}"

        headers = {"Content-Type": "application/json"}
        hf_token = getattr(self.settings, "huggingface_token", "")
        if hf_token and hf_token.strip():
            headers["Authorization"] = f"Bearer {hf_token}"

        payload = {
            "inputs": prompt,
            "parameters": {
                "num_inference_steps": 25,  # More steps for better quality
                "guidance_scale": 7.5,
            },
        }

        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=60)

            if response.status_code == 503:
                self.logger.warning("Model loading, waiting 10 seconds...")
                import time

                time.sleep(10)
                response = requests.post(api_url, json=payload, headers=headers, timeout=60)

            if response.status_code != 200:
                raise Exception(f"Hugging Face API error: {response.status_code}")

            # Save and resize image
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image = Image.open(io.BytesIO(response.content))
            # Crop to portrait aspect ratio (focus on face)
            target_size = (1080, 1920)  # 9:16 vertical
            image = image.resize(target_size, Image.Resampling.LANCZOS)
            image.save(output_path, "PNG", quality=95)

        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error calling Hugging Face API: {e}")

    def _create_placeholder_character_image(
        self, output_path: Path, character: Optional[Character] = None, prompt: str = ""
    ) -> None:
        """
        Create a placeholder character image.

        Args:
            output_path: Path to save image
            character: Optional character object
            prompt: Optional prompt text
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create a simple colored background with character name
        target_size = (1080, 1920)
        image = Image.new("RGB", target_size, color=(40, 40, 60))  # Dark blue-gray

        try:
            from PIL import ImageDraw, ImageFont

            draw = ImageDraw.Draw(image)

            # Try to use a font, fallback to default
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 80)
            except:
                font = ImageFont.load_default()

            # Draw character name or placeholder text
            text = character.name if character else "Character"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            position = ((target_size[0] - text_width) // 2, (target_size[1] - text_height) // 2)
            draw.text(position, text, fill=(255, 255, 255), font=font)

        except Exception as e:
            self.logger.warning(f"Could not add text to placeholder: {e}")

        image.save(output_path, "PNG")
        self.logger.info(f"Created placeholder character image: {output_path}")

