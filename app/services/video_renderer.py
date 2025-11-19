"""Video Renderer - generates final .mp4 video from VideoPlan."""

import io
from pathlib import Path
from typing import Any

import requests
from moviepy.editor import AudioFileClip, CompositeVideoClip, ImageClip, TextClip, VideoFileClip, concatenate_videoclips
from PIL import Image

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import Character, DialogueLine, VideoPlan
from app.services.character_video_engine import CharacterVideoEngine
from app.services.tts_client import TTSClient


class VideoRenderer:
    """Renders VideoPlan into final vertical .mp4 video."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize video renderer.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger
        self.tts_client = TTSClient(settings, logger)
        self.character_video_engine = CharacterVideoEngine(settings, logger)
        self.use_talking_heads = getattr(settings, "use_talking_heads", True)
        self.max_talking_head_lines = getattr(settings, "max_talking_head_lines_per_video", 3)

    def render(self, video_plan: VideoPlan, output_dir: Path) -> Path:
        """
        Main entrypoint: render VideoPlan into final .mp4 video.

        Args:
            video_plan: VideoPlan to render
            output_dir: Directory to save output files

        Returns:
            Path to final .mp4 video file
        """
        self.logger.info("=" * 60)
        self.logger.info("Starting video rendering")
        self.logger.info(f"Episode ID: {video_plan.episode_id}")
        self.logger.info(f"Title: {video_plan.title}")
        self.logger.info(f"Target duration: {video_plan.duration_target_seconds}s")
        self.logger.info("=" * 60)

        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Generate narration audio
        self.logger.info("Step 1: Generating narration audio...")
        narration_text = self._extract_narration_text(video_plan)
        audio_path = output_dir / f"{video_plan.episode_id}_narration.mp3"
        self._generate_narration_audio(narration_text, audio_path, video_plan)

        # Step 2: Generate character assets (if talking heads enabled)
        talking_head_clips = {}
        if self.use_talking_heads:
            self.logger.info("Step 2a: Generating character assets...")
            character_assets = self.character_video_engine.ensure_character_assets(
                video_plan, output_dir, video_plan.style
            )
            self.logger.info(f"Generated {len(character_assets)} character face images")

            # Step 2b: Generate dialogue audio and talking-head clips
            self.logger.info("Step 2b: Generating dialogue audio and talking-head clips...")
            talking_head_clips = self._generate_talking_head_clips(video_plan, output_dir)
            self.logger.info(f"Generated {len(talking_head_clips)} talking-head clips")
        else:
            self.logger.info("Talking heads disabled, skipping character asset generation")

        # Step 3: Generate scene visuals
        self.logger.info("Step 3: Generating scene visuals...")
        scene_visuals = self._generate_scene_visuals(video_plan, output_dir)

        # Step 4: Compose final video
        self.logger.info("Step 4: Composing final video...")
        video_path = output_dir / f"{video_plan.episode_id}_video.mp4"
        self._compose_video(video_plan, audio_path, scene_visuals, video_path, talking_head_clips)

        self.logger.info("=" * 60)
        self.logger.info("Video rendering complete!")
        self.logger.info(f"Final video: {video_path}")
        self.logger.info("=" * 60)

        return video_path

    def _extract_narration_text(self, video_plan: VideoPlan) -> str:
        """Extract all narration text from VideoPlan."""
        narration_lines = []
        for scene in video_plan.scenes:
            for narration in scene.narration:
                narration_lines.append(narration.text)

        return " ".join(narration_lines)

    def _generate_talking_head_clips(
        self, video_plan: VideoPlan, output_dir: Path
    ) -> dict[tuple[int, str], Path]:
        """
        Generate talking-head clips for selected dialogue lines.

        Args:
            video_plan: VideoPlan with dialogue
            output_dir: Directory to save clips

        Returns:
            Mapping: (scene_id, dialogue_line_id) -> clip_path
        """
        # Collect all dialogue lines
        all_dialogue_lines = []
        for scene in video_plan.scenes:
            for dialogue in scene.dialogue:
                all_dialogue_lines.append((scene.scene_id, dialogue))

        if not all_dialogue_lines:
            self.logger.info("No dialogue lines found")
            return {}

        # Select top N dialogue lines by emotion/importance
        selected_lines = self._select_dialogue_lines_for_animation(all_dialogue_lines)

        # Create character lookup
        character_map = {char.id: char for char in video_plan.characters}

        # Generate clips
        talking_head_clips = {}
        dialogue_audio_dir = output_dir / "dialogue_audio"
        dialogue_audio_dir.mkdir(parents=True, exist_ok=True)
        talking_head_dir = output_dir / "talking_heads"
        talking_head_dir.mkdir(parents=True, exist_ok=True)

        for scene_id, dialogue_line in selected_lines:
            character = character_map.get(dialogue_line.character_id)
            if not character:
                self.logger.warning(f"Character not found: {dialogue_line.character_id}")
                continue

            # Generate dialogue audio
            dialogue_audio_path = dialogue_audio_dir / f"dialogue_{dialogue_line.character_id}_{scene_id}.mp3"
            try:
                self.tts_client.generate_speech(
                    dialogue_line.text,
                    dialogue_audio_path,
                    voice_profile=character.voice_profile,
                )
            except Exception as e:
                self.logger.error(f"Failed to generate dialogue audio: {e}")
                continue

            # Generate talking-head clip
            try:
                clip_path = self.character_video_engine.generate_talking_head_clip(
                    character,
                    dialogue_line,
                    dialogue_audio_path,
                    talking_head_dir,
                    video_plan.style,
                )
                talking_head_clips[(scene_id, dialogue_line.character_id)] = clip_path
            except Exception as e:
                self.logger.error(f"Failed to generate talking-head clip: {e}")
                continue

        return talking_head_clips

    def _select_dialogue_lines_for_animation(
        self, dialogue_lines: list[tuple[int, DialogueLine]]
    ) -> list[tuple[int, DialogueLine]]:
        """
        Select top N dialogue lines for animation based on emotion/importance.

        Args:
            dialogue_lines: List of (scene_id, DialogueLine) tuples

        Returns:
            Selected dialogue lines (up to max_talking_head_lines)
        """
        # Score lines by emotion
        emotion_scores = {
            "angry": 5,
            "shocked": 4,
            "rage": 5,
            "tense": 3,
            "emotional": 3,
            "sad": 2,
            "neutral": 1,
        }

        scored_lines = []
        for scene_id, dialogue in dialogue_lines:
            emotion = dialogue.emotion.lower() if dialogue.emotion else "neutral"
            score = emotion_scores.get(emotion, 1)
            # Also prioritize lines in conflict/twist scenes (scene_id 2-3)
            if scene_id >= 2:
                score += 1
            scored_lines.append((score, scene_id, dialogue))

        # Sort by score descending
        scored_lines.sort(key=lambda x: x[0], reverse=True)

        # Take top N
        selected = [
            (scene_id, dialogue) for _, scene_id, dialogue in scored_lines[: self.max_talking_head_lines]
        ]

        self.logger.info(
            f"Selected {len(selected)} dialogue lines for animation (from {len(dialogue_lines)} total)"
        )
        return selected

    def _generate_narration_audio(self, text: str, output_path: Path, video_plan: VideoPlan) -> None:
        """
        Generate narration audio using TTS.

        Args:
            text: Narration text
            output_path: Path to save audio file
            video_plan: VideoPlan (for voice selection if needed)
        """
        # Try to find narrator character for voice selection
        narrator_voice_id = None
        for char in video_plan.characters:
            if char.role == "narrator":
                # Could use voice_profile to select voice, but for now use default
                narrator_voice_id = None
                break

        self.tts_client.generate_speech(text, output_path, voice_id=narrator_voice_id)

    def _generate_scene_visuals(self, video_plan: VideoPlan, output_dir: Path) -> list[Path]:
        """
        Generate visuals for each scene.

        Args:
            video_plan: VideoPlan with scenes
            output_dir: Directory to save images

        Returns:
            List of image file paths, one per scene
        """
        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        scene_visuals = []

        for scene in video_plan.scenes:
            self.logger.info(f"Generating visual for scene {scene.scene_id}...")

            # Build rich image prompt with emotion and visual details
            prompt = self._build_rich_image_prompt(scene, video_plan.style)

            image_path = images_dir / f"scene_{scene.scene_id:02d}.png"

            try:
                self._generate_image(prompt, image_path)
                scene_visuals.append(image_path)
            except Exception as e:
                self.logger.error(f"Failed to generate image for scene {scene.scene_id}: {e}")
                # Create placeholder image
                self._create_placeholder_image(image_path, scene)
                scene_visuals.append(image_path)

        return scene_visuals

    def _build_rich_image_prompt(self, scene: Any, style: str) -> str:
        """
        Build rich image prompt from scene data with emotion and visual details.

        Args:
            scene: VideoScene object
            style: Story style

        Returns:
            Rich image prompt string
        """
        # Extract dominant emotion from narration
        emotions = [n.emotion for n in scene.narration if hasattr(n, "emotion")]
        dominant_emotion = max(set(emotions), key=emotions.count) if emotions else "dramatic"

        # Map emotions to descriptive terms
        emotion_map = {
            "dramatic": "intense, shocking",
            "shocked": "surprised, stunned",
            "emotional": "heartfelt, moving",
            "tense": "suspenseful, anxious",
            "satisfying": "triumphant, just",
            "neutral": "serious, focused",
        }
        emotion_desc = emotion_map.get(dominant_emotion, "dramatic")

        # Extract key subject from description (first 40 words)
        key_subject = " ".join(scene.description.split()[:40])

        # Build rich prompt
        prompt_parts = [
            f"Cinematic {scene.camera_style}",
            f"of {key_subject[:60]}",
            f"{emotion_desc} atmosphere",
            scene.background_prompt,
            f"{style.replace('_', ' ')} setting",
            "dramatic lighting",
            "ultra-detailed",
            "4k quality",
            "vertical format",
            "professional still from a legal drama show",
        ]

        prompt = ". ".join(prompt_parts) + "."

        return prompt

    def _generate_image(self, prompt: str, output_path: Path) -> None:
        """
        Generate image from prompt using Hugging Face or stub.

        Args:
            prompt: Image generation prompt
            output_path: Path to save image
        """
        # Check if Hugging Face token is available
        hf_token = getattr(self.settings, "huggingface_token", None)

        if hf_token:
            self._generate_image_hf(prompt, output_path)
        else:
            self.logger.warning("No Hugging Face token - using placeholder image")
            self._create_placeholder_image(output_path, None, prompt)

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
                "num_inference_steps": 20,
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
            target_size = (1080, 1920)  # 9:16 vertical
            image = image.resize(target_size, Image.Resampling.LANCZOS)
            image.save(output_path, "PNG", quality=95)

        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error calling Hugging Face API: {e}")

    def _create_placeholder_image(self, output_path: Path, scene: Any = None, prompt: str = "") -> None:
        """
        Create a placeholder image (colored background with text).

        Args:
            output_path: Path to save image
            scene: Optional scene object
            prompt: Optional prompt text
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create a simple colored background
        width, height = 1080, 1920
        image = Image.new("RGB", (width, height), color=(30, 30, 50))  # Dark blue-gray

        # Add text if available
        try:
            from PIL import ImageDraw, ImageFont

            draw = ImageDraw.Draw(image)
            text = scene.description[:50] if scene and scene.description else prompt[:50] if prompt else "Scene"

            # Try to use a font, fallback to default
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 60)
            except:
                font = ImageFont.load_default()

            # Center text
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            position = ((width - text_width) // 2, (height - text_height) // 2)

            draw.text(position, text, fill=(255, 255, 255), font=font)
        except Exception as e:
            self.logger.warning(f"Could not add text to placeholder: {e}")

        image.save(output_path, "PNG")

    def _compose_video(
        self,
        video_plan: VideoPlan,
        audio_path: Path,
        scene_visuals: list[Path],
        output_path: Path,
        talking_head_clips: dict[tuple[int, str], Path] = None,
    ) -> None:
        """
        Compose final video from audio and scene visuals, with optional talking-head clips.

        Args:
            video_plan: VideoPlan
            audio_path: Path to narration audio
            scene_visuals: List of scene image paths
            output_path: Path to save final video
            talking_head_clips: Optional mapping of (scene_id, character_id) -> clip_path
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if not scene_visuals:
            raise ValueError("No scene visuals provided")

        talking_head_clips = talking_head_clips or {}

        # Load audio to get duration
        audio_clip = AudioFileClip(str(audio_path))
        audio_duration = audio_clip.duration
        self.logger.info(f"Audio duration: {audio_duration:.2f} seconds")

        # Calculate duration per scene based on narration lines
        total_narration_lines = sum(len(scene.narration) for scene in video_plan.scenes)
        if total_narration_lines == 0:
            # Fallback: equal duration per scene
            duration_per_scene = audio_duration / len(scene_visuals)
        else:
            # Weight by narration lines per scene
            scene_durations = []
            for scene in video_plan.scenes:
                scene_narration_count = len(scene.narration)
                if scene_narration_count > 0:
                    scene_durations.append((scene_narration_count / total_narration_lines) * audio_duration)
                else:
                    scene_durations.append(audio_duration / len(video_plan.scenes))

        # Build timeline: collect all clips (scene visuals + talking-head clips)
        video_clips = []
        current_time = 0.0
        transition_duration = 0.5

        for scene_idx, (scene, image_path, scene_duration) in enumerate(
            zip(video_plan.scenes, scene_visuals, scene_durations)
        ):
            if not image_path.exists():
                self.logger.warning(f"Image not found: {image_path}, skipping...")
                current_time += scene_duration
                continue

            scene_id = scene.scene_id

            # Check if this scene has talking-head clips
            scene_talking_heads = [
                (char_id, clip_path)
                for (s_id, char_id), clip_path in talking_head_clips.items()
                if s_id == scene_id
            ]

            if scene_talking_heads and self.use_talking_heads:
                # Insert talking-head clips into scene
                self.logger.info(
                    f"Scene {scene_id} has {len(scene_talking_heads)} talking-head clips, inserting..."
                )

                # Split scene duration: use talking-head for dialogue, scene image for rest
                # Simple approach: alternate between scene image and talking-head
                remaining_duration = scene_duration
                talking_head_duration = remaining_duration / (len(scene_talking_heads) + 1)

                # Start with scene image
                if talking_head_duration > 0.5:
                    img_clip = ImageClip(str(image_path)).set_duration(talking_head_duration)
                    img_clip = img_clip.resize((1080, 1920))
                    if scene_idx > 0:
                        img_clip = img_clip.fadein(transition_duration)
                    video_clips.append(img_clip)
                    remaining_duration -= talking_head_duration

                # Insert talking-head clips
                for char_id, clip_path in scene_talking_heads:
                    if not clip_path.exists():
                        self.logger.warning(f"Talking-head clip not found: {clip_path}")
                        continue

                    try:
                        talking_head_clip = VideoFileClip(str(clip_path))
                        # Ensure it fits remaining duration
                        if talking_head_clip.duration > remaining_duration:
                            talking_head_clip = talking_head_clip.subclip(0, remaining_duration)
                        video_clips.append(talking_head_clip)
                        remaining_duration -= talking_head_clip.duration
                    except Exception as e:
                        self.logger.error(f"Failed to load talking-head clip: {e}")
                        # Fallback to scene image
                        img_clip = ImageClip(str(image_path)).set_duration(talking_head_duration)
                        img_clip = img_clip.resize((1080, 1920))
                        video_clips.append(img_clip)

                # End with scene image if remaining duration
                if remaining_duration > 0.5:
                    img_clip = ImageClip(str(image_path)).set_duration(remaining_duration)
                    img_clip = img_clip.resize((1080, 1920))
                    if scene_idx < len(scene_visuals) - 1:
                        img_clip = img_clip.fadeout(transition_duration)
                    video_clips.append(img_clip)

            else:
                # Normal scene: just use scene image
                self.logger.info(f"Processing scene {scene_idx+1}/{len(scene_visuals)}: {image_path.name} ({scene_duration:.2f}s)")

                img_clip = ImageClip(str(image_path)).set_duration(scene_duration)
                img_clip = img_clip.resize((1080, 1920))

                # Add fade transitions
                if scene_idx > 0:
                    img_clip = img_clip.fadein(transition_duration)
                if scene_idx < len(scene_visuals) - 1:
                    img_clip = img_clip.fadeout(transition_duration)

                video_clips.append(img_clip)

            current_time += scene_duration

        if not video_clips:
            raise ValueError("No valid scene visuals found")

        # Concatenate all clips with transitions
        self.logger.info("Concatenating video clips with fade transitions...")
        final_video = concatenate_videoclips(video_clips, method="compose", padding=-transition_duration)

        # Add narration text overlay (optional - can be disabled)
        # For now, we'll skip text overlay to keep it clean
        # But the structure is here if needed

        # Set audio
        self.logger.info("Adding audio to video...")
        final_video = final_video.set_audio(audio_clip)

        # Set FPS
        final_video = final_video.set_fps(30)

        # Write video file
        self.logger.info(f"Rendering video to: {output_path}...")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        final_video.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            fps=30,
            preset="medium",
            bitrate="8000k",
            logger=None,  # Suppress MoviePy verbose logging
        )

        # Clean up
        final_video.close()
        audio_clip.close()

        self.logger.info(f"Successfully created video: {output_path}")
        self.logger.info(f"Video duration: {audio_duration:.2f} seconds")

