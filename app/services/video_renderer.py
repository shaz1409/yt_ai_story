"""Video Renderer - generates final .mp4 video from VideoPlan."""

import io
from pathlib import Path
from typing import Any

import requests
from moviepy.editor import AudioFileClip, CompositeVideoClip, ImageClip, TextClip, VideoFileClip, concatenate_videoclips
from PIL import Image

# Compatibility shim for Pillow 10.0.0+ (ANTIALIAS was removed)
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

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
            self.logger.info(f"Generated {len(talking_head_clips)} talking-head clips (some may have failed and will use fallback)")
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
        """Generate image using Hugging Face API with configurable models."""
        # Build model list: primary first (if set), then fallback models
        models_to_try = []
        if self.settings.hf_image_model_primary:
            models_to_try.append(self.settings.hf_image_model_primary)
        models_to_try.extend(self.settings.hf_image_models)
        
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

        last_error = None
        for model_id in models_to_try:
            api_url = f"https://api-inference.huggingface.co/models/{model_id}"
            try:
                self.logger.debug(f"Trying model: {model_id}")
                response = requests.post(api_url, json=payload, headers=headers, timeout=60)

                if response.status_code == 503:
                    self.logger.warning(f"Model {model_id} loading, waiting 10 seconds...")
                    import time
                    time.sleep(10)
                    response = requests.post(api_url, json=payload, headers=headers, timeout=60)

                if response.status_code == 410:
                    # Model gone, try next
                    self.logger.warning(
                        f"Model {model_id} returned 410 (Gone) – check if this model still supports HF Inference API."
                    )
                    continue

                if response.status_code != 200:
                    # Extract error message from response body (first 200 chars)
                    error_body = ""
                    try:
                        error_body = response.text[:200] if hasattr(response, "text") else ""
                    except:
                        pass
                    
                    error_msg = f"Hugging Face API error for {model_id}: status {response.status_code}"
                    if error_body:
                        error_msg += f" - {error_body}"
                    
                    self.logger.warning(error_msg)
                    raise Exception(error_msg)

                # Success - save image and break out of loop
                output_path.parent.mkdir(parents=True, exist_ok=True)
                image = Image.open(io.BytesIO(response.content))
                target_size = (1080, 1920)  # 9:16 vertical
                image = image.resize(target_size, Image.Resampling.LANCZOS)
                image.save(output_path, "PNG", quality=95)
                self.logger.info(f"Successfully generated image using model: {model_id}")
                return  # Success, exit function
                
            except Exception as e:
                last_error = e
                self.logger.warning(f"Model {model_id} failed: {e}, trying next...")
                continue
        
        # All models failed
        raise Exception(f"All Hugging Face models failed. Last error: {last_error}")

    def _create_placeholder_image(self, output_path: Path, scene: Any = None, prompt: str = "") -> None:
        """
        Create a professional placeholder image (blurred background with readable text overlay).

        Args:
            output_path: Path to save image
            scene: Optional scene object
            prompt: Optional prompt text
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        from PIL import ImageDraw, ImageFont, ImageFilter

        # Create image (1080x1920 vertical)
        width, height = 1080, 1920
        
        # Create gradient background (dark blue-gray to darker)
        image = Image.new("RGB", (width, height), color=(20, 25, 40))
        draw = ImageDraw.Draw(image)
        
        # Add gradient effect (darker at edges)
        for y in range(height):
            alpha = int(255 * (1 - abs(y - height // 2) / (height // 2)) * 0.3)
            color = (20 + alpha // 10, 25 + alpha // 10, 40 + alpha // 8)
            draw.rectangle([(0, y), (width, y + 1)], fill=color)
        
        # Apply blur for professional look
        image = image.filter(ImageFilter.GaussianBlur(radius=2))

        # Try to load a bold font
        try:
            font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 72)
            font_medium = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
        except:
            try:
                font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
                font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
            except:
                font_large = ImageFont.load_default()
                font_medium = ImageFont.load_default()

        # Extract scene description or use prompt
        if scene and hasattr(scene, 'description'):
            text = scene.description
        else:
            text = prompt or "Scene"
        
        # Clean up text - remove camera/lighting metadata, keep core description
        import re
        text = re.sub(r'^(Extreme Close-Up|Medium Shot|Wide Shot|Dramatic Close-Up|Close-Up) of\s+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+[A-Z][a-z]+ atmosphere\.\s+.*?lighting\.\s+.*?setting.*$', '', text)
        
        # Split into words and create readable lines (max 8 words per line, 3 lines max)
        words = text.split()[:24]  # Max 24 words total
        lines = []
        current_line = []
        for word in words:
            if len(current_line) < 8:
                current_line.append(word)
            else:
                lines.append(" ".join(current_line))
                current_line = [word]
                if len(lines) >= 3:
                    break
        if current_line and len(lines) < 3:
            lines.append(" ".join(current_line))
        
        if not lines:
            lines = [text[:50]]

        # Draw semi-transparent overlay for text readability
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 120))
        image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(image)

        # Center text vertically
        total_text_height = len(lines) * 100
        y_start = (height - total_text_height) // 2

        # Draw text with shadow for readability
        for i, line in enumerate(lines):
            y_pos = y_start + i * 100
            font = font_large if i == 0 else font_medium
            
            # Get text dimensions for centering
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x_pos = (width - text_width) // 2
            
            # Draw shadow (slightly offset)
            draw.text((x_pos + 2, y_pos + 2), line, fill=(0, 0, 0, 180), font=font)
            # Draw main text
            draw.text((x_pos, y_pos), line, fill=(255, 255, 255), font=font)

        image.save(output_path, "PNG", quality=95)

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
        target_duration = video_plan.duration_target_seconds
        self.logger.info(f"Audio duration: {audio_duration:.2f} seconds, target: {target_duration}s")

        # If audio is shorter than target, extend it to match target duration
        # This ensures the video matches the requested length
        if audio_duration < target_duration * 0.9:  # If audio is < 90% of target
            # Loop audio to fill target duration
            loops_needed = int(target_duration / audio_duration) + 1
            audio_clips = [audio_clip] * loops_needed
            from moviepy.editor import concatenate_audioclips
            extended_audio = concatenate_audioclips(audio_clips)
            # Trim to exact target duration
            audio_clip = extended_audio.subclip(0, target_duration)
            self.logger.info(f"Extending audio from {audio_duration:.2f}s to {target_duration}s (looped {loops_needed}x and trimmed)")
            final_audio_duration = target_duration
        elif audio_duration > target_duration * 1.1:  # If audio is > 110% of target
            # Trim audio to match target
            audio_clip = audio_clip.subclip(0, target_duration)
            self.logger.info(f"Trimming audio from {audio_duration:.2f}s to {target_duration}s")
            final_audio_duration = target_duration
        else:
            # Use audio duration as-is (close enough to target, ±10%)
            final_audio_duration = audio_duration
            self.logger.info(f"Audio duration ({audio_duration:.2f}s) is close to target ({target_duration}s), using as-is")

        # Calculate duration per scene based on narration lines
        total_narration_lines = sum(len(scene.narration) for scene in video_plan.scenes)
        if total_narration_lines == 0:
            # Fallback: equal duration per scene
            duration_per_scene = final_audio_duration / len(scene_visuals)
            scene_durations = [duration_per_scene] * len(scene_visuals)
        else:
            # Weight by narration lines per scene
            scene_durations = []
            for scene in video_plan.scenes:
                scene_narration_count = len(scene.narration)
                if scene_narration_count > 0:
                    scene_durations.append((scene_narration_count / total_narration_lines) * final_audio_duration)
                else:
                    scene_durations.append(final_audio_duration / len(video_plan.scenes))

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
        self.logger.info(f"Video duration: {final_audio_duration:.2f} seconds (target: {target_duration}s)")

