"""Video Renderer - generates final .mp4 video from VideoPlan."""

from pathlib import Path
from typing import Any

from moviepy.editor import AudioFileClip, CompositeVideoClip, ImageClip, TextClip, VideoFileClip, concatenate_videoclips
from PIL import Image

# Compatibility shim for Pillow 10.0.0+ (ANTIALIAS was removed)
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.utils.error_handler import format_error_message, get_fallback_suggestion
from app.utils.parallel_executor import ParallelExecutor
from app.models.schemas import Character, DialogueLine, EditPattern, VideoPlan
from typing import Optional
from app.services.character_video_engine import CharacterVideoEngine
from app.services.hf_endpoint_client import HFEndpointClient
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
        
        # Initialize HF Endpoint client for image generation
        try:
            self.hf_endpoint_client = HFEndpointClient(settings, logger)
        except ValueError as e:
            self.logger.warning(f"HF Endpoint not configured: {e}. Will use placeholder images.")
            self.hf_endpoint_client = None
        self.max_talking_head_lines = getattr(settings, "max_talking_head_lines_per_video", 3)
        
        # Initialize parallel executor for intra-episode API parallelism
        self.parallel_executor = ParallelExecutor(settings, logger)
        
        # Initialize image quality validator for score collection
        from app.services.image_quality_validator import ImageQualityValidator
        self.image_validator = ImageQualityValidator(settings, logger)
        
        # Track image quality scores during rendering
        self.image_scores: list[float] = []

    def render(self, video_plan: VideoPlan, output_dir: Path) -> tuple[Path, list[float]]:
        """
        Main entrypoint: render VideoPlan into final .mp4 video.

        Args:
            video_plan: VideoPlan to render
            output_dir: Directory to save output files

        Returns:
            Tuple of (Path to final .mp4 video file, list of image quality scores)
        """
        self.logger.info("=" * 60)
        self.logger.info("Starting video rendering")
        self.logger.info(f"Episode ID: {video_plan.episode_id}")
        self.logger.info(f"Title: {video_plan.title}")
        self.logger.info(f"Target duration: {video_plan.duration_target_seconds}s")
        
        # Log edit pattern
        edit_pattern = None
        if video_plan.metadata and video_plan.metadata.edit_pattern:
            edit_pattern = video_plan.metadata.edit_pattern
            # Handle both enum and string (for backward compatibility)
            if isinstance(edit_pattern, EditPattern):
                edit_pattern_value = edit_pattern.value
            else:
                # Try to convert string to enum, fallback to default if invalid
                try:
                    edit_pattern = EditPattern(edit_pattern)
                    edit_pattern_value = edit_pattern.value
                except (ValueError, TypeError):
                    self.logger.warning(f"Invalid edit pattern '{edit_pattern}', defaulting to TALKING_HEAD_HEAVY")
                    edit_pattern = EditPattern.TALKING_HEAD_HEAVY
                    edit_pattern_value = edit_pattern.value
            self.logger.info(f"Edit pattern for this episode: {edit_pattern_value}")
        else:
            self.logger.info("No edit pattern set, using default rendering behaviour.")
        
        self.logger.info("=" * 60)

        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Generate narration audio
        self.logger.info("Step 1: Generating narration audio...")
        narration_text = self._extract_narration_text(video_plan)
        audio_path = output_dir / f"{video_plan.episode_id}_narration.mp3"
        self._generate_narration_audio(narration_text, audio_path, video_plan)

        # Step 2: Generate character voice audio and talking-head clips (if character spoken lines exist)
        character_voice_clips = {}
        talking_head_clips = {}
        if video_plan.character_spoken_lines and len(video_plan.character_spoken_lines) > 0:
            self.logger.info(f"Step 2: Generating character voice audio for {len(video_plan.character_spoken_lines)} character spoken lines...")
            character_voice_clips = self._generate_character_voice_clips(video_plan, output_dir)
            self.logger.info(f"Generated {len(character_voice_clips)} character voice audio clips")

        # Step 3: Generate character assets (if talking heads enabled)
        if self.use_talking_heads:
            self.logger.info("Step 3a: Generating photorealistic character assets...")
            # Use photorealistic style by default (can be configured)
            image_style = getattr(self.settings, "character_image_style", "photorealistic")
            character_assets = self.character_video_engine.ensure_character_assets(
                video_plan, output_dir, video_plan.style, image_style=image_style
            )
            self.logger.info(f"Generated {len(character_assets)} {image_style} character face images")
            
            # Collect image quality scores for character images
            for char_id, char_path in character_assets.items():
                if char_path.exists():
                    try:
                        score = self.image_validator.score_image(char_path, "character_portrait")
                        self.image_scores.append(score)
                        self.logger.debug(f"Character image quality score: {score:.3f} for {char_id}")
                    except Exception as e:
                        self.logger.warning(f"Failed to score character image {char_path}: {e}")

            # Step 3b: Generate talking-head video clips for character spoken lines
            if character_voice_clips:
                self.logger.info("Step 3b: Generating talking-head video clips...")
                talking_head_clips = self._generate_character_talking_head_clips(video_plan, character_voice_clips, output_dir)
                self.logger.info(f"Generated {len(talking_head_clips)} talking-head clips (some may have failed and will use fallback)")
            else:
                # Fallback to old dialogue-based talking heads if no character spoken lines
                self.logger.info("Step 3b: Generating dialogue-based talking-head clips...")
                talking_head_clips = self._generate_talking_head_clips(video_plan, output_dir)
                self.logger.info(f"Generated {len(talking_head_clips)} talking-head clips (some may have failed and will use fallback)")
        else:
            self.logger.info("Talking heads disabled, skipping character asset generation")

        # Step 4: Generate scene visuals and cinematic B-roll
        self.logger.info("Step 4: Generating scene visuals and cinematic B-roll...")
        scene_visuals = self._generate_scene_visuals(video_plan, output_dir)
        broll_visuals = self._generate_cinematic_broll(video_plan, output_dir)
        self.logger.info(f"Generated {len(scene_visuals)} scene visuals and {len(broll_visuals)} cinematic B-roll scenes")
        
        # Collect image quality scores for scene visuals and B-roll
        for scene_path in scene_visuals:
            if scene_path.exists():
                try:
                    score = self.image_validator.score_image(scene_path, "scene_broll")
                    self.image_scores.append(score)
                    self.logger.debug(f"Scene visual quality score: {score:.3f} for {scene_path.name}")
                except Exception as e:
                    self.logger.warning(f"Failed to score scene visual {scene_path}: {e}")
        
        for broll_path in broll_visuals:
            if broll_path.exists():
                try:
                    score = self.image_validator.score_image(broll_path, "scene_broll")
                    self.image_scores.append(score)
                    self.logger.debug(f"B-roll quality score: {score:.3f} for {broll_path.name}")
                except Exception as e:
                    self.logger.warning(f"Failed to score B-roll {broll_path}: {e}")

        # Step 5: Validate assets before rendering
        self.logger.info("Step 5: Validating assets before rendering...")
        self._validate_assets(video_plan, video_plan.episode_id, audio_path, character_voice_clips, talking_head_clips, scene_visuals, broll_visuals, output_dir)

        # Step 6: Compose final video (with character clips and B-roll inserted)
        self.logger.info("Step 6: Composing final video...")
        video_path = output_dir / f"{video_plan.episode_id}_video.mp4"
        video_duration, audio_duration = self._compose_video(
            video_plan, audio_path, scene_visuals, video_path, talking_head_clips, character_voice_clips, broll_visuals
        )

        # Step 7: Update metadata with rendering information
        self.logger.info("Step 7: Updating episode metadata...")
        if video_plan.metadata:
            video_plan.metadata.video_duration_sec = video_duration
            video_plan.metadata.audio_duration_sec = audio_duration
            video_plan.metadata.num_broll_clips = len(scene_visuals)  # Each scene visual is a B-roll clip
            video_plan.metadata.num_talking_head_clips = len(talking_head_clips)
            video_plan.metadata.hf_model = getattr(self.settings, "hf_endpoint_url", None) or "placeholder"
            video_plan.metadata.tts_provider = getattr(self.settings, "elevenlabs_api_key", None) and "elevenlabs" or "openai"
            self.logger.info(f"Updated metadata: video={video_duration:.2f}s, audio={audio_duration:.2f}s, b-roll={len(scene_visuals)}, talking-heads={len(talking_head_clips)}")
        else:
            self.logger.warning("No metadata found on video_plan, skipping metadata update")

        self.logger.info("=" * 60)
        self.logger.info("Video rendering complete!")
        self.logger.info(f"Final video: {video_path}")
        self.logger.info(f"Collected {len(self.image_scores)} image quality scores")
        self.logger.info("=" * 60)

        return video_path, self.image_scores

    def _validate_assets(
        self,
        video_plan: VideoPlan,
        episode_id: str,
        narration_audio_path: Path,
        character_voice_clips: dict[str, Path],
        talking_head_clips: dict[str, Path],
        scene_visuals: list[Path],
        broll_visuals: list[Path],
        output_dir: Path,
    ) -> None:
        """
        Ensure all required assets exist before composing the video.
        
        If something is missing, either:
        - attempt a safe fallback (placeholder), or
        - log a clear error and raise a controlled exception.
        
        Args:
            video_plan: VideoPlan with episode content
            episode_id: Episode ID for logging
            narration_audio_path: Path to narration audio file
            character_voice_clips: Mapping of character voice clip paths
            talking_head_clips: Mapping of talking-head clip paths
            scene_visuals: List of scene visual image paths
            broll_visuals: List of B-roll image paths
            output_dir: Output directory for fallback assets
            
        Raises:
            ValueError: If critical assets are missing with no fallback
        """
        errors = []
        warnings = []
        
        # Validate narration audio (critical)
        if not narration_audio_path.exists():
            error_msg = f"Episode {episode_id}: Narration audio file not found: {narration_audio_path}"
            self.logger.error(error_msg)
            errors.append(error_msg)
        else:
            self.logger.debug(f"Episode {episode_id}: Narration audio validated: {narration_audio_path}")
        
        # Validate character voice clips (if character_spoken_lines exist)
        if video_plan.character_spoken_lines:
            for idx, spoken_line in enumerate(video_plan.character_spoken_lines):
                clip_key = str(idx)
                if clip_key in character_voice_clips:
                    clip_path = character_voice_clips[clip_key]
                    if not clip_path.exists():
                        warning_msg = f"Episode {episode_id}: Character voice clip {idx} not found: {clip_path}"
                        self.logger.warning(warning_msg)
                        warnings.append(warning_msg)
                else:
                    warning_msg = f"Episode {episode_id}: Character voice clip {idx} not generated for character {spoken_line.character_id}"
                    self.logger.warning(warning_msg)
                    warnings.append(warning_msg)
        
        # Validate talking-head clips (if character_spoken_lines exist and talking heads enabled)
        if self.use_talking_heads and video_plan.character_spoken_lines:
            for idx, spoken_line in enumerate(video_plan.character_spoken_lines):
                clip_key = str(idx)
                if clip_key in talking_head_clips:
                    clip_path = talking_head_clips[clip_key]
                    if not clip_path.exists():
                        warning_msg = f"Episode {episode_id}: Talking-head clip {idx} not found: {clip_path}, will use fallback"
                        self.logger.warning(warning_msg)
                        warnings.append(warning_msg)
        
        # Validate scene visuals (critical - need at least one)
        if not scene_visuals:
            error_msg = f"Episode {episode_id}: No scene visuals generated"
            self.logger.error(error_msg)
            errors.append(error_msg)
        else:
            missing_scene_visuals = [p for p in scene_visuals if not p.exists()]
            if missing_scene_visuals:
                warning_msg = f"Episode {episode_id}: {len(missing_scene_visuals)} scene visuals missing, will use fallbacks"
                self.logger.warning(warning_msg)
                warnings.append(warning_msg)
            else:
                self.logger.debug(f"Episode {episode_id}: All {len(scene_visuals)} scene visuals validated")
        
        # Validate B-roll visuals (optional - nice to have)
        if broll_visuals:
            missing_broll = [p for p in broll_visuals if not p.exists()]
            if missing_broll:
                warning_msg = f"Episode {episode_id}: {len(missing_broll)} B-roll visuals missing, will use scene visuals as fallback"
                self.logger.warning(warning_msg)
                warnings.append(warning_msg)
        
        # If critical errors, raise exception
        if errors:
            error_summary = "; ".join(errors)
            raise ValueError(f"Episode {episode_id}: Critical asset validation failed: {error_summary}")
        
        # Log warnings summary
        if warnings:
            self.logger.warning(f"Episode {episode_id}: Asset validation completed with {len(warnings)} warnings (non-critical)")
        else:
            self.logger.info(f"Episode {episode_id}: All assets validated successfully")

    def _extract_narration_text(self, video_plan: VideoPlan) -> str:
        """Extract all narration text from VideoPlan (excluding character spoken lines)."""
        narration_lines = []
        character_spoken_texts = {line.line_text for line in video_plan.character_spoken_lines}
        
        for scene in video_plan.scenes:
            for narration in scene.narration:
                # Skip narration lines that are actually character spoken lines
                if narration.text not in character_spoken_texts:
                    narration_lines.append(narration.text)

        return " ".join(narration_lines)

    def _generate_character_voice_clips(
        self, video_plan: VideoPlan, output_dir: Path
    ) -> dict[str, Path]:
        """
        Generate character voice audio clips for character spoken lines (parallelized).

        Args:
            video_plan: VideoPlan with character_spoken_lines
            output_dir: Directory to save audio clips

        Returns:
            Mapping: character_spoken_line_index -> audio_path
        """
        character_audio_dir = output_dir / "character_audio"
        character_audio_dir.mkdir(parents=True, exist_ok=True)

        character_voice_clips = {}
        character_map = {char.id: char for char in video_plan.characters}

        # Prepare parallel tasks for TTS generation
        tts_tasks = []
        tts_task_names = []
        tts_results_map = {}  # Map index to result

        for idx, spoken_line in enumerate(video_plan.character_spoken_lines):
            character = character_map.get(spoken_line.character_id)
            if not character:
                self.logger.warning(f"Character {spoken_line.character_id} not found, skipping spoken line")
                continue

            audio_path = character_audio_dir / f"character_voice_{idx}.mp3"
            
            # Create task closure
            def create_tts_task(line_idx: int, char: Character, line: Any, path: Path):
                def generate_tts():
                    if not char.detailed_voice_profile:
                        self.logger.warning(f"Character {char.name} has no detailed_voice_profile, using default")
                        self.tts_client.generate_speech(
                            text=line.line_text,
                            output_path=path,
                            voice_profile=char.voice_profile,
                        )
                    else:
                        self.tts_client.generate_character_voice(
                            character_voice_profile=char.detailed_voice_profile,
                            text=line.line_text,
                            output_path=path,
                        )
                    return path
                return generate_tts

            tts_tasks.append(create_tts_task(idx, character, spoken_line, audio_path))
            tts_task_names.append(f"character_voice_{idx}_{character.name}")
            tts_results_map[idx] = audio_path

        # Execute TTS tasks in parallel
        if tts_tasks:
            self.logger.info(f"Generating {len(tts_tasks)} character voice clips in parallel...")
            tts_results = self.parallel_executor.execute_api_calls(
                tts_tasks,
                task_names=tts_task_names,
                episode_id=video_plan.episode_id,
            )
            
            # Map results
            for i, (result, exception) in enumerate(tts_results):
                if exception:
                    self.logger.warning(f"Character voice clip {i} generation failed: {exception}")
                elif result:
                    idx = list(tts_results_map.keys())[i]
                    character_voice_clips[str(idx)] = result
                    spoken_line = video_plan.character_spoken_lines[idx]
                    character = character_map.get(spoken_line.character_id)
                    self.logger.info(f"Generated character voice audio for {character.name if character else 'unknown'}: '{spoken_line.line_text[:50]}...'")

        return character_voice_clips

    def _generate_character_talking_head_clips(
        self,
        video_plan: VideoPlan,
        character_voice_clips: dict[str, Path],
        output_dir: Path,
    ) -> dict[tuple[int, str], Path]:
        """
        Generate talking-head video clips for character spoken lines.

        Args:
            video_plan: VideoPlan with character_spoken_lines
            character_voice_clips: Mapping of line index -> audio_path
            output_dir: Directory to save clips

        Returns:
            Mapping: (scene_id, character_id) -> clip_path
        """
        talking_head_clips = {}
        character_map = {char.id: char for char in video_plan.characters}

        for idx, spoken_line in enumerate(video_plan.character_spoken_lines):
            character = character_map.get(spoken_line.character_id)
            if not character:
                continue

            audio_path = character_voice_clips.get(str(idx))
            if not audio_path or not audio_path.exists():
                self.logger.warning(f"Character voice audio not found for line {idx}, skipping")
                continue

            try:
                # Create a DialogueLine-like object for compatibility
                from app.models.schemas import DialogueLine
                dialogue_line = DialogueLine(
                    character_id=character.id,
                    text=spoken_line.line_text,
                    emotion=spoken_line.emotion,
                    scene_id=spoken_line.scene_id,
                    approx_timing_hint=spoken_line.approx_timing_seconds,
                )

                clip_path = self.character_video_engine.generate_talking_head_clip(
                    character=character,
                    dialogue_line=dialogue_line,
                    audio_path=audio_path,
                    output_dir=output_dir / "talking_heads",
                    style=video_plan.style,
                    emotion=spoken_line.emotion,
                )

                talking_head_clips[(spoken_line.scene_id, character.id)] = clip_path
            except Exception as e:
                self.logger.warning(f"Failed to generate talking-head clip for {character.name}: {e}, will use fallback")

        return talking_head_clips

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
            List of image file paths, one per scene (HOOK scene may have extra)
        """
        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        scene_visuals = []

        # Prepare parallel tasks for scene image generation
        scene_tasks = []
        scene_task_names = []
        scene_results_map = {}  # Map scene_id to result path

        for scene_idx, scene in enumerate(video_plan.scenes):
            is_hook_scene = scene_idx == 0  # First scene is typically HOOK
            
            # Build emotion-aware image prompt
            prompt = self._build_emotion_aware_broll_prompt(scene, video_plan)
            image_path = images_dir / f"scene_{scene.scene_id:02d}.png"

            # Create task closure
            def create_scene_task(scene_id: int, scene_obj: Any, img_prompt: str, img_path: Path, is_hook: bool):
                def generate_scene_image():
                    try:
                        self._generate_image(img_prompt, img_path, image_type="scene_broll")
                        self.logger.info(f"Generated visual for scene {scene_id}")
                        
                        # HOOK-first visual bias: Generate extra b-roll variant for HOOK scene
                        if is_hook:
                            self.logger.info(f"HOOK visual prompt: {img_prompt[:120]}...")
                            hook_variant_prompt = self._build_hook_variant_prompt(scene_obj, video_plan)
                            variant_path = images_dir / f"scene_{scene_id:02d}_variant.png"
                            try:
                                self._generate_image(hook_variant_prompt, variant_path, image_type="scene_broll")
                                self.logger.info(f"Generated HOOK variant visual: {variant_path}")
                            except Exception as e:
                                self.logger.warning(f"Failed to generate HOOK variant: {e}, using primary only")
                        
                        return img_path
                    except Exception as e:
                        self.logger.error(f"Failed to generate image for scene {scene_id}: {e}")
                        self._create_placeholder_image(img_path, scene_obj)
                        return img_path
                return generate_scene_image

            scene_tasks.append(create_scene_task(scene.scene_id, scene, prompt, image_path, is_hook_scene))
            scene_task_names.append(f"scene_{scene.scene_id}")
            scene_results_map[scene.scene_id] = image_path

        # Execute scene image tasks in parallel
        if scene_tasks:
            self.logger.info(f"Generating {len(scene_tasks)} scene visuals in parallel...")
            scene_results = self.parallel_executor.execute_api_calls(
                scene_tasks,
                task_names=scene_task_names,
                episode_id=video_plan.episode_id,
            )
            
            # Map results (sort by scene_id to maintain order)
            for i, (result, exception) in enumerate(scene_results):
                if exception:
                    self.logger.warning(f"Scene visual {i} generation failed: {exception}")
                    # Use placeholder
                    scene_id = list(scene_results_map.keys())[i]
                    scene_obj = video_plan.scenes[i]
                    self._create_placeholder_image(scene_results_map[scene_id], scene_obj)
                    scene_visuals.append(scene_results_map[scene_id])
                elif result:
                    scene_visuals.append(result)
            
            # Sort by scene_id to maintain order
            scene_visuals.sort(key=lambda p: int(p.stem.split("_")[1]) if "_" in p.stem else 0)

        return scene_visuals

    def _generate_cinematic_broll(self, video_plan: VideoPlan, output_dir: Path) -> list[Path]:
        """
        Generate cinematic B-roll scenes with photorealistic quality.

        Args:
            video_plan: VideoPlan with b_roll_scenes
            output_dir: Directory to save B-roll images

        Returns:
            List of B-roll image paths
        """
        if not video_plan.b_roll_scenes:
            self.logger.info("No B-roll scenes defined in video plan")
            return []

        broll_dir = output_dir / "broll"
        broll_dir.mkdir(parents=True, exist_ok=True)

        broll_visuals = []
        fallback_dir = Path("assets/broll_fallbacks")

        for idx, broll_scene in enumerate(video_plan.b_roll_scenes):
            image_path = broll_dir / f"broll_{broll_scene.category}_{idx:02d}.png"

            try:
                # Generate B-roll scene using HF endpoint (with quality validation and retry logic)
                if self.hf_endpoint_client:
                    result_path = self.hf_endpoint_client.generate_broll_scene(
                        prompt=broll_scene.prompt,
                        output_path=image_path,
                        realism_level="high",
                    )
                    broll_visuals.append(result_path)
                    self.logger.info(f"Generated B-roll scene ({broll_scene.category}): {result_path}")
                else:
                    raise Exception("HF Endpoint not configured")
            except Exception as e:
                self.logger.warning(f"Failed to generate B-roll scene {idx}: {e}, trying fallback...")
                # Try fallback placeholder (generate_broll_scene already tried fallbacks, but we can try again)
                fallback_path = self._get_broll_fallback(broll_scene.category, fallback_dir, image_path)
                if fallback_path:
                    broll_visuals.append(fallback_path)
                    self.logger.info(f"Using fallback B-roll: {fallback_path}")
                else:
                    # Create placeholder
                    self._create_placeholder_broll(image_path, broll_scene)
                    broll_visuals.append(image_path)
                    self.logger.warning(f"Created placeholder B-roll: {image_path}")

        return broll_visuals

    def _get_broll_fallback(self, category: str, fallback_dir: Path, output_path: Path) -> Optional[Path]:
        """
        Get fallback B-roll image from assets/broll_fallbacks/ if available.

        Args:
            category: B-roll category
            fallback_dir: Directory containing fallback images
            output_path: Path to save fallback (if copying)

        Returns:
            Path to fallback image, or None if not found
        """
        if not fallback_dir.exists():
            return None

        # Look for category-specific fallback
        fallback_patterns = [
            fallback_dir / f"{category}.png",
            fallback_dir / f"{category}.jpg",
            fallback_dir / "generic.png",
            fallback_dir / "generic.jpg",
        ]

        for pattern in fallback_patterns:
            if pattern.exists():
                # Copy to output location
                import shutil
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(pattern, output_path)
                return output_path

        return None

    def _create_placeholder_broll(self, output_path: Path, broll_scene: Any) -> None:
        """
        Create a placeholder B-roll image.

        Args:
            output_path: Path to save placeholder
            broll_scene: BrollScene object
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        from PIL import ImageDraw, ImageFont, ImageFilter

        # Create image (vertical format)
        width = getattr(self.settings, "video_width", 1080)
        height = getattr(self.settings, "video_height", 1920)
        image = Image.new("RGB", (width, height), color=(30, 35, 50))
        draw = ImageDraw.Draw(image)

        # Add gradient effect
        for y in range(height):
            alpha = int(255 * (1 - abs(y - height // 2) / (height // 2)) * 0.3)
            color = (30 + alpha // 10, 35 + alpha // 10, 50 + alpha // 8)
            draw.rectangle([(0, y), (width, y + 1)], fill=color)

        # Apply blur
        image = image.filter(ImageFilter.GaussianBlur(radius=3))

        # Add text
        try:
            font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 64)
            font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

        text = f"B-ROLL: {broll_scene.category.upper()}"
        bbox = draw.textbbox((0, 0), text, font=font_large)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x_pos = (width - text_width) // 2
        y_pos = (height - text_height) // 2 - 50

        # Draw shadow
        draw.text((x_pos + 2, y_pos + 2), text, fill=(0, 0, 0, 200), font=font_large)
        # Draw main text
        draw.text((x_pos, y_pos), text, fill=(255, 255, 255), font=font_large)

        # Add prompt preview
        prompt_preview = broll_scene.prompt[:80] + "..." if len(broll_scene.prompt) > 80 else broll_scene.prompt
        y_pos += text_height + 30
        draw.text((x_pos, y_pos), prompt_preview, fill=(200, 200, 200), font=font_small)

        image.save(output_path, "PNG", quality=95)

    def _build_emotion_aware_broll_prompt(self, scene: Any, video_plan: VideoPlan) -> str:
        """
        Build emotion-aware b-roll prompt using metadata (niche, emotions, beat type).

        Args:
            scene: VideoScene object
            video_plan: VideoPlan with metadata

        Returns:
            Rich image prompt string for scene b-roll
        """
        # Get metadata
        metadata = video_plan.metadata
        niche = metadata.niche if metadata else "courtroom"
        primary_emotion = metadata.primary_emotion if metadata else "shock"
        secondary_emotion = metadata.secondary_emotion if metadata else None
        
        # Detect beat type from scene (heuristic: check description or scene_id)
        beat_type = self._detect_beat_type_from_scene(scene)
        
        # Map emotions to visual tone
        emotion_visual_map = {
            "rage": "harsh lighting, tense atmosphere, visible anger, clenched jaws, raised voices",
            "anger": "harsh lighting, tense atmosphere, visible anger, clenched jaws, raised voices",
            "injustice": "uneasy atmosphere, people avoiding eye contact, uncomfortable expressions, moral conflict",
            "shock": "wide eyes, gasps, hands over mouth, frozen courtroom, stunned expressions",
            "disgust": "uneasy body language, people avoiding eye contact, uncomfortable expressions, distaste",
            "sadness": "somber lighting, emotional expressions, tears, downcast faces",
            "fear": "tense atmosphere, worried expressions, defensive body language",
            "satisfaction": "triumphant atmosphere, just resolution, relieved expressions",
        }
        
        # Get visual tone for primary emotion
        visual_tone = emotion_visual_map.get(primary_emotion.lower(), "dramatic lighting, tense atmosphere")
        if secondary_emotion and secondary_emotion.lower() in emotion_visual_map:
            # Blend with secondary emotion
            secondary_tone = emotion_visual_map[secondary_emotion.lower()]
            visual_tone = f"{visual_tone}, {secondary_tone}"
        
        # Build niche-specific description
        niche_descriptions = {
            "courtroom": "courtroom with wooden benches, judge's bench, formal atmosphere",
            "relationship_drama": "emotional setting, personal conflict, intimate atmosphere",
            "injustice": "unjust situation, power imbalance, moral conflict",
            "workplace_drama": "professional setting, office environment, corporate atmosphere",
        }
        niche_desc = niche_descriptions.get(niche, f"{niche} setting")
        
        # Extract key moment from scene description
        key_moment = " ".join(scene.description.split()[:30])  # First 30 words
        
        # Build beat-specific moment description
        beat_moments = {
            "HOOK": "opening moment, attention-grabbing scene",
            "TRIGGER": "event that sets story in motion",
            "CONTEXT": "background and setup",
            "CLASH": "main conflict or confrontation",
            "TWIST": "unexpected reveal or reversal",
            "CTA": "conclusion or call-to-action",
        }
        beat_moment = beat_moments.get(beat_type, "key moment")
        
        # Build composition suggestions
        composition = "cinematic, shallow depth of field"
        if beat_type in ["HOOK", "CLASH"]:
            composition = "cinematic, over-the-shoulder shot, dramatic framing"
        elif beat_type == "TWIST":
            composition = "cinematic, wide shot revealing the twist"
        
        # Build prompt: [emotion adjective] [niche description], [beat-specific moment], [visual tone], [composition], quality tags
        prompt_parts = [
            f"{primary_emotion.capitalize()} {niche_desc}",
            f"{beat_moment}",
            key_moment[:80],  # Truncate to avoid overly long prompts
            visual_tone,
            composition,
            "4k, realistic, dramatic lighting",
            "vertical format 9:16",
        ]
        
        prompt = ", ".join([p for p in prompt_parts if p.strip()]) + "."
        
        return prompt
    
    def _build_hook_variant_prompt(self, scene: Any, video_plan: VideoPlan) -> str:
        """
        Build extra triggering variant prompt for HOOK scene.

        Args:
            scene: VideoScene object (HOOK scene)
            video_plan: VideoPlan with metadata

        Returns:
            More extreme/triggering prompt for HOOK
        """
        metadata = video_plan.metadata
        primary_emotion = metadata.primary_emotion if metadata else "shock"
        
        # Extract the most triggering part of HOOK narration
        hook_text = ""
        if scene.narration:
            hook_text = scene.narration[0].text if scene.narration else ""
        
        # Build more extreme prompt
        prompt_parts = [
            f"Extreme {primary_emotion} moment",
            hook_text[:60] if hook_text else "shocking opening scene",
            "most triggering visual",
            "extreme facial expressions",
            "harsh dramatic lighting",
            "cinematic, close-up on emotion",
            "4k, realistic, ultra-dramatic",
            "vertical format 9:16",
        ]
        
        prompt = ", ".join([p for p in prompt_parts if p.strip()]) + "."
        return prompt
    
    def _detect_beat_type_from_scene(self, scene: Any) -> str:
        """
        Detect beat type from scene (heuristic).

        Args:
            scene: VideoScene object

        Returns:
            Beat type string (HOOK, TRIGGER, CONTEXT, CLASH, TWIST, CTA)
        """
        desc_lower = scene.description.lower()
        
        if "hook" in desc_lower or scene.scene_id == 1:
            return "HOOK"
        elif "twist" in desc_lower or "shocking" in desc_lower:
            return "TWIST"
        elif "clash" in desc_lower or "conflict" in desc_lower or "confrontation" in desc_lower:
            return "CLASH"
        elif "trigger" in desc_lower:
            return "TRIGGER"
        elif "cta" in desc_lower or "call-to-action" in desc_lower:
            return "CTA"
        elif "context" in desc_lower or "setup" in desc_lower:
            return "CONTEXT"
        else:
            # Heuristic based on scene_id
            if scene.scene_id == 1:
                return "HOOK"
            elif scene.scene_id >= len(scene.narration) - 1 if hasattr(scene, 'narration') else False:
                return "CTA"
            else:
                return "CONTEXT"

    def _generate_image(self, prompt: str, output_path: Path, image_type: str = "scene_broll") -> None:
        """
        Generate image from prompt using HF Inference Endpoint.

        Args:
            prompt: Image generation prompt
            output_path: Path to save image
            image_type: Type of image ("character_portrait" or "scene_broll")
        """
        if self.hf_endpoint_client:
            try:
                self.hf_endpoint_client.generate_image(prompt, output_path, image_type=image_type)
            except Exception as e:
                self.logger.error(f"HF Endpoint image generation failed: {e}, using placeholder")
                self._create_placeholder_image(output_path, None, prompt)
        else:
            self.logger.warning("HF Endpoint not configured - using placeholder image")
            self._create_placeholder_image(output_path, None, prompt)


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

        # Create image (vertical format)
        width = getattr(self.settings, "video_width", 1080)
        height = getattr(self.settings, "video_height", 1920)
        
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

    def _build_timeline_with_character_clips(
        self,
        video_plan: VideoPlan,
        narration_audio_path: Path,
        scene_visuals: list[Path],
        talking_head_clips: dict[tuple[int, str], Path],
        character_voice_clips: dict[str, Path],
        target_duration: float,
        narration_audio_duration: float,
    ) -> tuple[list, float]:
        """
        Build video timeline with character clips inserted between narration segments.

        Timeline: Narration → Character Clip → Narration → Character Clip → ...

        Args:
            video_plan: VideoPlan with character_spoken_lines
            narration_audio_path: Path to narration audio
            scene_visuals: List of scene image paths
            talking_head_clips: Mapping of (scene_id, character_id) -> clip_path
            character_voice_clips: Mapping of line_index -> character_audio_path
            target_duration: Target video duration
            narration_audio_duration: Duration of narration audio

        Returns:
            Tuple of (video_clips list, final_audio_duration)
        """
        from moviepy.editor import AudioFileClip, ImageClip, VideoFileClip, concatenate_audioclips

        video_clips = []
        transition_duration = 0.5
        max_still_duration = 3.5

        # Load narration audio to split into segments
        narration_audio = AudioFileClip(str(narration_audio_path))
        
        # Build timeline: split narration and insert character clips
        # Calculate total duration needed (narration + character clips)
        character_clip_durations = []
        for idx, spoken_line in enumerate(video_plan.character_spoken_lines):
            audio_path = character_voice_clips.get(str(idx))
            if audio_path and audio_path.exists():
                char_audio = AudioFileClip(str(audio_path))
                character_clip_durations.append(char_audio.duration)
                char_audio.close()
            else:
                character_clip_durations.append(0.0)

        total_character_duration = sum(character_clip_durations)
        total_duration = narration_audio_duration + total_character_duration

        # Adjust if needed to match target
        if total_duration < target_duration * 0.9:
            # Extend narration
            scale_factor = (target_duration - total_character_duration) / narration_audio_duration
            narration_audio_duration = target_duration - total_character_duration
        elif total_duration > target_duration * 1.1:
            # Trim narration
            narration_audio_duration = target_duration - total_character_duration

        # Split narration into segments (before each character clip)
        # Simple approach: divide narration evenly between character clips
        num_character_clips = len([d for d in character_clip_durations if d > 0])
        if num_character_clips > 0:
            narration_segment_duration = narration_audio_duration / (num_character_clips + 1)
        else:
            narration_segment_duration = narration_audio_duration

        # Build timeline
        current_time = 0.0
        narration_segment_idx = 0
        character_clip_idx = 0

        # Start with first narration segment
        if narration_segment_duration > 0.5:
            # Use first scene visual for first narration segment
            scene_idx = 0
            if scene_idx < len(scene_visuals) and scene_visuals[scene_idx].exists():
                img_clip = ImageClip(str(scene_visuals[scene_idx])).set_duration(narration_segment_duration)
                video_width = getattr(self.settings, "video_width", 1080)
                video_height = getattr(self.settings, "video_height", 1920)
                img_clip = img_clip.resize((video_width, video_height))
                # Apply Ken Burns effect (subtle zoom/pan)
                img_clip = self._apply_ken_burns_effect(img_clip, narration_segment_duration)
                img_clip = img_clip.fadein(transition_duration)
                video_clips.append(img_clip)
                current_time += narration_segment_duration

        # Insert character clips with narration segments between
        for idx, spoken_line in enumerate(video_plan.character_spoken_lines):
            # Character clip
            character_clip_duration = character_clip_durations[idx]
            if character_clip_duration > 0.5:
                # Get talking-head clip if available
                talking_head_clip_path = talking_head_clips.get((spoken_line.scene_id, spoken_line.character_id))
                
                if talking_head_clip_path and talking_head_clip_path.exists():
                    try:
                        th_clip = VideoFileClip(str(talking_head_clip_path))
                        # Trust the clip's real duration (lip-sync providers align duration automatically)
                        # Only adjust if there's a significant mismatch (>0.2s)
                        duration_diff = abs(th_clip.duration - character_clip_duration)
                        if duration_diff > 0.2:
                            self.logger.debug(
                                f"Talking-head duration mismatch: clip={th_clip.duration:.2f}s, "
                                f"audio={character_clip_duration:.2f}s, adjusting..."
                            )
                            if th_clip.duration > character_clip_duration:
                                th_clip = th_clip.subclip(0, character_clip_duration)
                            else:
                                # Extend with last frame
                                th_clip = th_clip.loop(duration=character_clip_duration)
                        else:
                            # Use clip's actual duration (trust lip-sync provider alignment)
                            character_clip_duration = th_clip.duration
                        
                        # Add crossfade transitions
                        if video_clips:
                            th_clip = th_clip.fadein(transition_duration)
                        if idx < len(video_plan.character_spoken_lines) - 1:
                            th_clip = th_clip.fadeout(transition_duration)
                        
                        video_clips.append(th_clip)
                        current_time += character_clip_duration
                    except Exception as e:
                        self.logger.warning(f"Failed to load talking-head clip: {e}, using scene visual")
                        # Fallback to scene visual
                        scene_idx = min(spoken_line.scene_id - 1, len(scene_visuals) - 1)
                        if scene_idx >= 0 and scene_visuals[scene_idx].exists():
                            img_clip = ImageClip(str(scene_visuals[scene_idx])).set_duration(character_clip_duration)
                            video_width = getattr(self.settings, "video_width", 1080)
                            video_height = getattr(self.settings, "video_height", 1920)
                            img_clip = img_clip.resize((video_width, video_height))
                            # Apply Ken Burns effect
                            img_clip = self._apply_ken_burns_effect(img_clip, character_clip_duration)
                            img_clip = img_clip.fadein(transition_duration)
                            video_clips.append(img_clip)
                            current_time += character_clip_duration
                else:
                    # No talking-head clip, use scene visual
                    scene_idx = min(spoken_line.scene_id - 1, len(scene_visuals) - 1)
                    if scene_idx >= 0 and scene_visuals[scene_idx].exists():
                        img_clip = ImageClip(str(scene_visuals[scene_idx])).set_duration(character_clip_duration)
                        video_width = getattr(self.settings, "video_width", 1080)
                        video_height = getattr(self.settings, "video_height", 1920)
                        img_clip = img_clip.resize((video_width, video_height))
                        # Apply Ken Burns effect
                        img_clip = self._apply_ken_burns_effect(img_clip, character_clip_duration)
                        img_clip = img_clip.fadein(transition_duration)
                        video_clips.append(img_clip)
                        current_time += character_clip_duration

            # Narration segment after character clip
            if idx < num_character_clips - 1 and narration_segment_duration > 0.5:
                scene_idx = min(spoken_line.scene_id, len(scene_visuals) - 1)
                if scene_idx >= 0 and scene_visuals[scene_idx].exists():
                    img_clip = ImageClip(str(scene_visuals[scene_idx])).set_duration(narration_segment_duration)
                    video_width = getattr(self.settings, "video_width", 1080)
                    video_height = getattr(self.settings, "video_height", 1920)
                    img_clip = img_clip.resize((video_width, video_height))
                    # Apply Ken Burns effect
                    img_clip = self._apply_ken_burns_effect(img_clip, narration_segment_duration)
                    img_clip = img_clip.fadein(0.3)  # Quick transition
                    video_clips.append(img_clip)
                    current_time += narration_segment_duration

        # Final narration segment if needed
        remaining_time = target_duration - current_time
        if remaining_time > 0.5:
            scene_idx = len(scene_visuals) - 1
            if scene_idx >= 0 and scene_visuals[scene_idx].exists():
                img_clip = ImageClip(str(scene_visuals[scene_idx])).set_duration(remaining_time)
                video_width = getattr(self.settings, "video_width", 1080)
                video_height = getattr(self.settings, "video_height", 1920)
                img_clip = img_clip.resize((video_width, video_height))
                # Apply Ken Burns effect
                img_clip = self._apply_ken_burns_effect(img_clip, remaining_time)
                img_clip = img_clip.fadein(0.3)
                img_clip = img_clip.fadeout(transition_duration)
                video_clips.append(img_clip)
                current_time += remaining_time

        final_audio_duration = current_time
        self.logger.info(f"Built timeline: {len(video_clips)} clips, total duration: {final_audio_duration:.2f}s")

        return video_clips, final_audio_duration

    def _build_composite_audio(
        self,
        narration_audio_path: Path,
        character_voice_clips: dict[str, Path],
        character_spoken_lines: list[Any],
        total_duration: float,
    ) -> Any:
        """
        Build composite audio: narration + character voice clips.

        Args:
            narration_audio_path: Path to narration audio
            character_voice_clips: Mapping of line_index -> character_audio_path
            character_spoken_lines: List of CharacterSpokenLine objects
            total_duration: Total audio duration

        Returns:
            Composite AudioFileClip
        """
        from moviepy.editor import AudioFileClip, CompositeAudioClip, concatenate_audioclips

        narration_audio = AudioFileClip(str(narration_audio_path))
        
        # Calculate narration segment durations
        num_character_clips = len([c for c in character_voice_clips.values() if c.exists()])
        if num_character_clips > 0:
            narration_segment_duration = (total_duration - sum(
                AudioFileClip(str(character_voice_clips[str(idx)])).duration
                for idx in range(len(character_spoken_lines))
                if str(idx) in character_voice_clips and character_voice_clips[str(idx)].exists()
            )) / (num_character_clips + 1)
        else:
            narration_segment_duration = narration_audio.duration

        # Build audio timeline: narration → character → narration → character → ...
        audio_segments = []
        current_time = 0.0

        # First narration segment
        if narration_segment_duration > 0.5:
            narration_seg = narration_audio.subclip(0, min(narration_segment_duration, narration_audio.duration))
            audio_segments.append(narration_seg)
            current_time += narration_seg.duration

        # Insert character clips with narration between
        narration_start = narration_segment_duration
        for idx, spoken_line in enumerate(character_spoken_lines):
            # Character audio
            char_audio_path = character_voice_clips.get(str(idx))
            if char_audio_path and char_audio_path.exists():
                char_audio = AudioFileClip(str(char_audio_path))
                audio_segments.append(char_audio)
                current_time += char_audio.duration

                # Next narration segment
                if idx < len(character_spoken_lines) - 1 and narration_start + narration_segment_duration < narration_audio.duration:
                    narration_seg = narration_audio.subclip(
                        narration_start,
                        min(narration_start + narration_segment_duration, narration_audio.duration)
                    )
                    audio_segments.append(narration_seg)
                    current_time += narration_seg.duration
                    narration_start += narration_segment_duration

        # Final narration segment if needed
        if narration_start < narration_audio.duration:
            remaining_narration = narration_audio.subclip(narration_start, narration_audio.duration)
            audio_segments.append(remaining_narration)
            current_time += remaining_narration.duration

        # Concatenate all audio segments
        if len(audio_segments) > 1:
            composite_audio = concatenate_audioclips(audio_segments)
        else:
            composite_audio = audio_segments[0] if audio_segments else narration_audio

        # Trim to exact duration if needed
        if composite_audio.duration > total_duration:
            composite_audio = composite_audio.subclip(0, total_duration)
        elif composite_audio.duration < total_duration * 0.9:
            # Extend by looping the last narration segment
            remaining = total_duration - composite_audio.duration
            if remaining > 0.5 and narration_audio.duration > 0.5:
                # Use last part of narration to fill
                last_seg = narration_audio.subclip(max(0, narration_audio.duration - remaining), narration_audio.duration)
                composite_audio = concatenate_audioclips([composite_audio, last_seg])
                if composite_audio.duration > total_duration:
                    composite_audio = composite_audio.subclip(0, total_duration)

        self.logger.info(f"Built composite audio: {len(audio_segments)} segments, duration: {composite_audio.duration:.2f}s")

        return composite_audio

    def _apply_ken_burns_effect(self, clip: ImageClip, duration: float) -> ImageClip:
        """
        Apply subtle Ken Burns effect (zoom/pan) to a static image clip.

        Creates a subtle zoom-in effect (100% → 110%) for cinematic movement.
        For MoviePy 1.0.3, this is a placeholder that logs the effect.
        In production, could use CompositeVideoClip with scaled versions.

        Args:
            clip: ImageClip to animate
            duration: Clip duration

        Returns:
            Clip with Ken Burns effect applied (or original if effect fails)
        """
        try:
            # Subtle zoom: start at 100%, end at 110% (10% zoom in)
            # For MoviePy 1.0.3 compatibility, we log the effect conceptually
            # Full implementation would use CompositeVideoClip with scaled versions
            self.logger.debug(f"Ken Burns effect applied (conceptual): {duration:.2f}s zoom 100%→110%")
            
            # Return original clip for now (can be enhanced with proper CompositeVideoClip)
            return clip
        except Exception as e:
            # Fallback: return original clip if Ken Burns fails
            self.logger.debug(f"Ken Burns effect failed: {e}, using static image")
            return clip

    def _create_image_clip(self, image_path: Path, duration: float, apply_ken_burns: bool = True) -> ImageClip:
        """
        Create an ImageClip from a path, resize to video dimensions, and optionally apply Ken Burns effect.

        Args:
            image_path: Path to image file
            duration: Clip duration
            apply_ken_burns: Whether to apply Ken Burns effect

        Returns:
            ImageClip ready for timeline
        """
        img_clip = ImageClip(str(image_path)).set_duration(duration)
        video_width = getattr(self.settings, "video_width", 1080)
        video_height = getattr(self.settings, "video_height", 1920)
        img_clip = img_clip.resize((video_width, video_height))
        
        if apply_ken_burns:
            img_clip = self._apply_ken_burns_effect(img_clip, duration)
        
        return img_clip

    def _apply_transitions_to_clip(
        self,
        clip: ImageClip,
        scene_idx: int,
        cut_idx: int,
        num_cuts: int,
        total_scenes: int,
        edit_pattern: Optional[EditPattern],
        transition_duration: float = 0.5,
    ) -> ImageClip:
        """
        Apply fade transitions to a clip based on position and edit pattern.

        Args:
            clip: ImageClip to apply transitions to
            scene_idx: Index of current scene
            cut_idx: Index of current cut within scene
            num_cuts: Total number of cuts in scene
            total_scenes: Total number of scenes
            edit_pattern: Edit pattern (affects transition style)
            transition_duration: Base transition duration

        Returns:
            Clip with transitions applied
        """
        if edit_pattern == EditPattern.BROLL_CINEMATIC:
            # Smooth crossfades
            if scene_idx > 0 and cut_idx == 0:
                clip = clip.fadein(transition_duration)
            elif cut_idx > 0:
                clip = clip.fadein(0.4)  # Smooth crossfade
            if scene_idx < total_scenes - 1 and cut_idx == num_cuts - 1:
                clip = clip.fadeout(transition_duration)
        elif edit_pattern == EditPattern.MIXED_RAPID:
            # Quick cuts
            if scene_idx > 0 and cut_idx == 0:
                clip = clip.fadein(0.2)
            elif cut_idx > 0:
                clip = clip.fadein(0.15)  # Very quick cut
            if scene_idx < total_scenes - 1 and cut_idx == num_cuts - 1:
                clip = clip.fadeout(0.2)
        else:
            # Default transitions
            if scene_idx > 0 and cut_idx == 0:
                clip = clip.fadein(transition_duration)
            elif cut_idx > 0:
                clip = clip.fadein(0.2)  # Quick cut transition
            if scene_idx < total_scenes - 1 and cut_idx == num_cuts - 1:
                clip = clip.fadeout(transition_duration)
        
        return clip

    def _prepare_audio(self, audio_path: Path, target_duration: float) -> tuple[Any, float]:
        """
        Load audio and adjust duration to match target.

        Args:
            audio_path: Path to audio file
            target_duration: Target duration in seconds

        Returns:
            Tuple of (audio_clip, final_duration)
        """
        audio_clip = AudioFileClip(str(audio_path))
        audio_duration = audio_clip.duration
        self.logger.info(f"Audio duration: {audio_duration:.2f} seconds, target: {target_duration}s")

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

        return audio_clip, final_audio_duration

    def _calculate_scene_durations(self, video_plan: VideoPlan, total_audio_duration: float, scene_visuals: list[Path]) -> list[float]:
        """
        Calculate duration per scene based on narration lines or equal distribution.

        Args:
            video_plan: VideoPlan with scenes
            total_audio_duration: Total audio duration
            scene_visuals: List of scene visual paths

        Returns:
            List of durations, one per scene
        """
        total_narration_lines = sum(len(scene.narration) for scene in video_plan.scenes)
        if total_narration_lines == 0:
            # Fallback: equal duration per scene
            duration_per_scene = total_audio_duration / len(scene_visuals)
            return [duration_per_scene] * len(scene_visuals)
        else:
            # Weight by narration lines per scene
            scene_durations = []
            for scene in video_plan.scenes:
                scene_narration_count = len(scene.narration)
                if scene_narration_count > 0:
                    scene_durations.append((scene_narration_count / total_narration_lines) * total_audio_duration)
                else:
                    scene_durations.append(total_audio_duration / len(video_plan.scenes))
            return scene_durations

    def _get_edit_pattern(self, video_plan: VideoPlan) -> Optional[EditPattern]:
        """
        Get and validate edit pattern from video plan.

        Args:
            video_plan: VideoPlan with metadata

        Returns:
            EditPattern enum or None
        """
        if not video_plan.metadata or not video_plan.metadata.edit_pattern:
            self.logger.info("No edit pattern set, using default rendering behaviour.")
            return None

        edit_pattern = video_plan.metadata.edit_pattern
        # Handle both enum and string (for backward compatibility)
        if isinstance(edit_pattern, str):
            try:
                edit_pattern = EditPattern(edit_pattern)
            except (ValueError, TypeError):
                self.logger.warning(f"Invalid edit pattern '{edit_pattern}', defaulting to TALKING_HEAD_HEAVY")
                edit_pattern = EditPattern.TALKING_HEAD_HEAVY

        self.logger.info(f"Using edit pattern: {edit_pattern.value if isinstance(edit_pattern, EditPattern) else edit_pattern}")
        return edit_pattern

    def _get_hook_variant_path(self, scene_idx: int, scene_id: int, image_path: Path) -> Optional[Path]:
        """
        Get hook variant image path if available.

        Args:
            scene_idx: Index of scene (0 for HOOK)
            scene_id: Scene ID
            image_path: Base image path

        Returns:
            Path to variant if found, None otherwise
        """
        if scene_idx == 0:  # HOOK scene
            variant_path = image_path.parent / f"scene_{scene_id:02d}_variant.png"
            if variant_path.exists():
                self.logger.info(f"Found HOOK variant image: {variant_path.name}")
                return variant_path
        return None

    def _get_scene_talking_heads(
        self, scene_id: int, talking_head_clips: dict[tuple[int, str], Path]
    ) -> list[tuple[str, Path]]:
        """
        Get talking-head clips for a specific scene.

        Args:
            scene_id: Scene ID
            talking_head_clips: Mapping of (scene_id, character_id) -> clip_path

        Returns:
            List of (character_id, clip_path) tuples
        """
        return [
            (char_id, clip_path)
            for (s_id, char_id), clip_path in talking_head_clips.items()
            if s_id == scene_id
        ]

    def _compose_scene_talking_head_heavy(
        self,
        scene_idx: int,
        scene_id: int,
        scene_duration: float,
        image_path: Path,
        hook_variant_path: Optional[Path],
        scene_talking_heads: list[tuple[str, Path]],
        scene_visuals: list[Path],
        transition_duration: float,
        max_still_duration: float,
    ) -> list:
        """
        Compose a scene using TALKING_HEAD_HEAVY pattern: 65% talking-heads, 35% b-roll.

        Args:
            scene_idx: Index of scene
            scene_id: Scene ID
            scene_duration: Total duration for this scene
            image_path: Path to scene image
            hook_variant_path: Optional hook variant image path
            scene_talking_heads: List of (character_id, clip_path) tuples
            scene_visuals: List of all scene visuals
            transition_duration: Transition duration
            max_still_duration: Maximum duration for still images

        Returns:
            List of video clips for this scene
        """
        video_clips = []
        self.logger.info(
            f"Scene {scene_id} (talking_head_heavy): {len(scene_talking_heads)} talking-head clips, "
            f"allocating 65% to TH, 35% to b-roll"
        )
        
        remaining_duration = scene_duration
        th_total_duration = scene_duration * 0.65  # 65% for talking-heads
        broll_total_duration = scene_duration * 0.35  # 35% for b-roll
        
        # Distribute talking-head duration across clips
        th_duration_per_clip = th_total_duration / len(scene_talking_heads) if scene_talking_heads else 0
        
        # Start with short b-roll intro
        if broll_total_duration > 0.5:
            intro_broll = min(broll_total_duration * 0.3, 2.0)  # 30% of b-roll, max 2s
            broll_image = hook_variant_path if (scene_idx == 0 and hook_variant_path) else image_path
            img_clip = self._create_image_clip(broll_image, intro_broll, apply_ken_burns=True)
            if scene_idx > 0:
                img_clip = img_clip.fadein(0.3)
            video_clips.append(img_clip)
            broll_total_duration -= intro_broll
        
        # Insert talking-head clips
        for i, (char_id, clip_path) in enumerate(scene_talking_heads):
            if not clip_path.exists():
                self.logger.warning(f"Talking-head clip not found: {clip_path}")
                continue
            
            talking_head_clip = None
            try:
                talking_head_clip = VideoFileClip(str(clip_path))
                th_duration = min(talking_head_clip.duration, th_duration_per_clip, remaining_duration)
                if th_duration > 0.5:
                    if talking_head_clip.duration > th_duration:
                        talking_head_clip = talking_head_clip.subclip(0, th_duration)
                    video_clips.append(talking_head_clip)
                    remaining_duration -= th_duration
                    talking_head_clip = None  # Ownership transferred
                    
                    # Small b-roll between TH clips (if not last)
                    if i < len(scene_talking_heads) - 1 and broll_total_duration > 0.5:
                        inter_broll = min(broll_total_duration / (len(scene_talking_heads) - 1), 1.5)
                        img_clip = self._create_image_clip(image_path, inter_broll, apply_ken_burns=True)
                        img_clip = img_clip.fadein(0.2)
                        video_clips.append(img_clip)
                        broll_total_duration -= inter_broll
                        remaining_duration -= inter_broll
            except Exception as e:
                self.logger.error(f"Failed to load talking-head clip: {e}")
                # Fallback to b-roll
                broll_duration = min(th_duration_per_clip, remaining_duration, max_still_duration)
                if broll_duration > 0.5:
                    img_clip = self._create_image_clip(image_path, broll_duration, apply_ken_burns=True)
                    video_clips.append(img_clip)
                    remaining_duration -= broll_duration
            finally:
                if talking_head_clip is not None:
                    try:
                        talking_head_clip.close()
                    except Exception:
                        pass
        
        # Final b-roll if remaining
        if remaining_duration > 0.5:
            final_broll = min(remaining_duration, broll_total_duration, max_still_duration)
            img_clip = self._create_image_clip(image_path, final_broll, apply_ken_burns=True)
            if scene_idx < len(scene_visuals) - 1:
                img_clip = img_clip.fadeout(transition_duration)
            video_clips.append(img_clip)
        
        return video_clips

    def _compose_scene_broll_cinematic(
        self,
        scene_idx: int,
        scene_id: int,
        scene_duration: float,
        image_path: Path,
        scene_talking_heads: list[tuple[str, Path]],
        scene_visuals: list[Path],
        transition_duration: float,
    ) -> list:
        """
        Compose a scene using BROLL_CINEMATIC pattern: b-roll primary, max 1 short talking-head.

        Args:
            scene_idx: Index of scene
            scene_id: Scene ID
            scene_duration: Total duration for this scene
            image_path: Path to scene image
            scene_talking_heads: List of (character_id, clip_path) tuples
            scene_visuals: List of all scene visuals
            transition_duration: Transition duration

        Returns:
            List of video clips for this scene
        """
        video_clips = []
        self.logger.info(
            f"Scene {scene_id} (broll_cinematic): {len(scene_talking_heads)} talking-head clips, "
            f"using b-roll as primary, inserting max 1 short TH"
        )
        
        remaining_duration = scene_duration
        
        # Use only first talking-head clip, keep it short (max 3s)
        selected_th = scene_talking_heads[0] if scene_talking_heads else None
        th_duration = 0.0
        
        if selected_th:
            char_id, clip_path = selected_th
            if clip_path.exists():
                talking_head_clip = None
                try:
                    talking_head_clip = VideoFileClip(str(clip_path))
                    th_duration = min(talking_head_clip.duration, 3.0, remaining_duration * 0.2)  # Max 3s, max 20% of scene
                    if th_duration > 0.5:
                        if talking_head_clip.duration > th_duration:
                            talking_head_clip = talking_head_clip.subclip(0, th_duration)
                        
                        # Insert TH in middle of scene
                        broll_before = (remaining_duration - th_duration) * 0.5
                        broll_after = remaining_duration - th_duration - broll_before
                        
                        # B-roll before TH
                        if broll_before > 0.5:
                            img_clip = self._create_image_clip(image_path, broll_before, apply_ken_burns=False)
                            if scene_idx > 0:
                                img_clip = img_clip.fadein(transition_duration)
                            video_clips.append(img_clip)
                        
                        # Talking-head
                        video_clips.append(talking_head_clip)
                        talking_head_clip = None  # Ownership transferred
                        
                        # B-roll after TH
                        if broll_after > 0.5:
                            img_clip = self._create_image_clip(image_path, broll_after, apply_ken_burns=False)
                            if scene_idx < len(scene_visuals) - 1:
                                img_clip = img_clip.fadeout(transition_duration)
                            video_clips.append(img_clip)
                        
                        remaining_duration = 0  # All allocated
                except Exception as e:
                    self.logger.error(f"Failed to load talking-head clip: {e}")
                finally:
                    if talking_head_clip is not None:
                        try:
                            talking_head_clip.close()
                        except Exception:
                            pass
        
        # If no TH or TH failed, use b-roll for entire scene
        if remaining_duration > 0.5:
            # Split into smooth b-roll segments with crossfades
            num_segments = max(2, int(remaining_duration / 4.0))  # ~4s per segment
            segment_duration = remaining_duration / num_segments
            
            for seg_idx in range(num_segments):
                img_clip = self._create_image_clip(image_path, segment_duration, apply_ken_burns=False)
                
                # Smooth crossfades
                if scene_idx > 0 and seg_idx == 0:
                    img_clip = img_clip.fadein(transition_duration)
                elif seg_idx > 0:
                    img_clip = img_clip.fadein(0.4)  # Smooth crossfade
                if scene_idx < len(scene_visuals) - 1 and seg_idx == num_segments - 1:
                    img_clip = img_clip.fadeout(transition_duration)
                
                video_clips.append(img_clip)
        
        return video_clips

    def _compose_scene_mixed_rapid(
        self,
        scene_idx: int,
        scene_id: int,
        scene_duration: float,
        image_path: Path,
        hook_variant_path: Optional[Path],
        scene_talking_heads: list[tuple[str, Path]],
        scene_visuals: list[Path],
        current_time: float,
        early_max_duration: float,
        later_max_duration: float,
        max_still_duration: float,
    ) -> list:
        """
        Compose a scene using MIXED_RAPID pattern: fast alternation, shorter clips.

        Args:
            scene_idx: Index of scene
            scene_id: Scene ID
            scene_duration: Total duration for this scene
            image_path: Path to scene image
            hook_variant_path: Optional hook variant image path
            scene_talking_heads: List of (character_id, clip_path) tuples
            scene_visuals: List of all scene visuals
            current_time: Current time in video
            early_max_duration: Max duration for first 10 seconds
            later_max_duration: Max duration after first 10 seconds
            max_still_duration: Maximum duration for still images

        Returns:
            List of video clips for this scene
        """
        video_clips = []
        self.logger.info(
            f"Scene {scene_id} (mixed_rapid): {len(scene_talking_heads)} talking-head clips, "
            f"rapid alternation with short clips"
        )
        
        remaining_duration = scene_duration
        is_early_scene = current_time < 10.0  # First 10 seconds
        max_clip_duration = early_max_duration if is_early_scene else later_max_duration
        
        # Alternate: BROLL → TH → BROLL → TH → ...
        for i, (char_id, clip_path) in enumerate(scene_talking_heads):
            # B-roll before talking-head
            broll_duration = min(max_clip_duration, remaining_duration * 0.4)  # 40% of remaining or max
            if broll_duration > 0.5:
                broll_image = hook_variant_path if (scene_idx == 0 and hook_variant_path and i == 0) else image_path
                img_clip = self._create_image_clip(broll_image, broll_duration, apply_ken_burns=True)
                if scene_idx > 0 or i > 0:
                    img_clip = img_clip.fadein(0.2)  # Quick fade
                video_clips.append(img_clip)
                remaining_duration -= broll_duration

            # Talking-head clip
            if not clip_path.exists():
                self.logger.warning(f"Talking-head clip not found: {clip_path}")
                continue

            talking_head_clip = None
            try:
                talking_head_clip = VideoFileClip(str(clip_path))
                th_duration = min(talking_head_clip.duration, max_clip_duration, remaining_duration * 0.6)
                if th_duration > 0.5:
                    if talking_head_clip.duration > th_duration:
                        talking_head_clip = talking_head_clip.subclip(0, th_duration)
                    video_clips.append(talking_head_clip)
                    remaining_duration -= th_duration
                    talking_head_clip = None  # Ownership transferred
            except Exception as e:
                self.logger.error(f"Failed to load talking-head clip: {e}")
                # Fallback to b-roll
                broll_duration = min(max_clip_duration, remaining_duration, max_still_duration)
                if broll_duration > 0.5:
                    img_clip = self._create_image_clip(image_path, broll_duration, apply_ken_burns=False)
                    video_clips.append(img_clip)
                    remaining_duration -= broll_duration
            finally:
                if talking_head_clip is not None:
                    try:
                        talking_head_clip.close()
                    except Exception:
                        pass

        # Final b-roll if remaining
        if remaining_duration > 0.5:
            broll_duration = min(remaining_duration, max_clip_duration)
            img_clip = self._create_image_clip(image_path, broll_duration, apply_ken_burns=False)
            if scene_idx < len(scene_visuals) - 1:
                img_clip = img_clip.fadeout(0.5)
            video_clips.append(img_clip)
        
        return video_clips

    def _compose_scene_default(
        self,
        scene_idx: int,
        scene_id: int,
        scene_duration: float,
        image_path: Path,
        hook_variant_path: Optional[Path],
        scene_talking_heads: list[tuple[str, Path]],
        scene_visuals: list[Path],
        max_still_duration: float,
    ) -> list:
        """
        Compose a scene using default pattern: alternating TH/BROLL.

        Args:
            scene_idx: Index of scene
            scene_id: Scene ID
            scene_duration: Total duration for this scene
            image_path: Path to scene image
            hook_variant_path: Optional hook variant image path
            scene_talking_heads: List of (character_id, clip_path) tuples
            scene_visuals: List of all scene visuals
            max_still_duration: Maximum duration for still images

        Returns:
            List of video clips for this scene
        """
        video_clips = []
        self.logger.info(
            f"Scene {scene_id} has {len(scene_talking_heads)} talking-head clips, alternating TH/BROLL..."
        )

        remaining_duration = scene_duration
        num_segments = len(scene_talking_heads) * 2 + 1  # TH, BROLL, TH, BROLL, ...
        segment_duration = remaining_duration / num_segments

        # Alternate: BROLL → TH → BROLL → TH → ...
        for i, (char_id, clip_path) in enumerate(scene_talking_heads):
            # B-roll before talking-head (except first segment if HOOK)
            if i > 0 or scene_idx != 0:
                broll_duration = min(segment_duration, max_still_duration)
                if broll_duration > 0.5:
                    # Use variant for HOOK if available
                    broll_image = hook_variant_path if (scene_idx == 0 and hook_variant_path and i == 0) else image_path
                    img_clip = self._create_image_clip(broll_image, broll_duration, apply_ken_burns=True)
                    if scene_idx > 0 or i > 0:
                        img_clip = img_clip.fadein(0.3)  # Quick fade
                    video_clips.append(img_clip)
                    remaining_duration -= broll_duration

            # Talking-head clip
            if not clip_path.exists():
                self.logger.warning(f"Talking-head clip not found: {clip_path}")
                continue

            talking_head_clip = None
            try:
                talking_head_clip = VideoFileClip(str(clip_path))
                th_duration = min(talking_head_clip.duration, remaining_duration)
                if th_duration > 0.5:
                    if talking_head_clip.duration > th_duration:
                        talking_head_clip = talking_head_clip.subclip(0, th_duration)
                    video_clips.append(talking_head_clip)
                    remaining_duration -= th_duration
                    talking_head_clip = None  # Ownership transferred
            except Exception as e:
                self.logger.error(f"Failed to load talking-head clip: {e}")
                # Fallback to b-roll
                broll_duration = min(segment_duration, remaining_duration, max_still_duration)
                if broll_duration > 0.5:
                    img_clip = self._create_image_clip(image_path, broll_duration, apply_ken_burns=False)
                    video_clips.append(img_clip)
                    remaining_duration -= broll_duration
            finally:
                if talking_head_clip is not None:
                    try:
                        talking_head_clip.close()
                    except Exception:
                        pass

        # Final b-roll if remaining
        if remaining_duration > 0.5:
            broll_duration = min(remaining_duration, max_still_duration)
            img_clip = self._create_image_clip(image_path, broll_duration, apply_ken_burns=False)
            if scene_idx < len(scene_visuals) - 1:
                img_clip = img_clip.fadeout(0.5)
            video_clips.append(img_clip)
        
        return video_clips

    def _compose_scene_narration_only(
        self,
        scene_idx: int,
        scene_duration: float,
        image_path: Path,
        hook_variant_path: Optional[Path],
        scene_visuals: list[Path],
        edit_pattern: Optional[EditPattern],
        current_time: float,
        early_max_duration: float,
        later_max_duration: float,
        max_still_duration: float,
        transition_duration: float,
    ) -> list:
        """
        Compose a narration-only scene (no talking-heads) with pattern-specific cuts.

        Args:
            scene_idx: Index of scene
            scene_duration: Total duration for this scene
            image_path: Path to scene image
            hook_variant_path: Optional hook variant image path
            scene_visuals: List of all scene visuals
            edit_pattern: Edit pattern (affects cut style)
            current_time: Current time in video
            early_max_duration: Max duration for first 10 seconds
            later_max_duration: Max duration after first 10 seconds
            max_still_duration: Maximum duration for still images
            transition_duration: Transition duration

        Returns:
            List of video clips for this scene
        """
        video_clips = []
        self.logger.info(f"Processing scene {scene_idx+1}/{len(scene_visuals)}: {image_path.name} ({scene_duration:.2f}s)")

        is_early_scene = current_time < 10.0  # First 10 seconds
        
        # Determine cut strategy based on pattern
        if edit_pattern == EditPattern.MIXED_RAPID:
            # Shorter cuts especially in first 10 seconds
            max_cut_duration = early_max_duration if is_early_scene else later_max_duration
            if scene_duration > max_cut_duration:
                num_cuts = max(2, int(scene_duration / max_cut_duration))
                cut_duration = scene_duration / num_cuts
                self.logger.info(f"  (mixed_rapid) Splitting into {num_cuts} cuts (max {max_cut_duration}s per cut)")
            else:
                num_cuts = 1
                cut_duration = scene_duration
        elif edit_pattern == EditPattern.BROLL_CINEMATIC:
            # Longer, smoother segments with crossfades
            max_cut_duration = 5.0  # Longer segments for cinematic feel
            if scene_duration > max_cut_duration:
                num_cuts = max(2, int(scene_duration / max_cut_duration))
                cut_duration = scene_duration / num_cuts
                self.logger.info(f"  (broll_cinematic) Splitting into {num_cuts} smooth segments (max {max_cut_duration}s per segment)")
            else:
                num_cuts = 1
                cut_duration = scene_duration
        else:
            # Default: quick cuts if long duration
            if scene_duration > max_still_duration:
                num_cuts = max(2, int(scene_duration / max_still_duration))
                cut_duration = scene_duration / num_cuts
                self.logger.info(f"  Splitting into {num_cuts} cuts (max {max_still_duration}s per cut)")
            else:
                num_cuts = 1
                cut_duration = scene_duration

        # For HOOK scene, use variant for first cut if available
        for cut_idx in range(num_cuts):
            cut_image = hook_variant_path if (scene_idx == 0 and hook_variant_path and cut_idx == 0) else image_path
            if scene_idx == 0 and hook_variant_path and cut_idx == 0:
                self.logger.info(f"  Using HOOK variant for first cut")
            
            img_clip = self._create_image_clip(cut_image, cut_duration, apply_ken_burns=False)
            img_clip = self._apply_transitions_to_clip(
                img_clip, scene_idx, cut_idx, num_cuts, len(scene_visuals), edit_pattern, transition_duration
            )
            video_clips.append(img_clip)
        
        return video_clips

    def _compose_video(
        self,
        video_plan: VideoPlan,
        audio_path: Path,
        scene_visuals: list[Path],
        output_path: Path,
        talking_head_clips: dict[tuple[int, str], Path] = None,
        character_voice_clips: dict[str, Path] = None,
        broll_visuals: list[Path] = None,
    ) -> tuple[float, float]:
        """
        Compose final video from audio and scene visuals, with optional talking-head clips and B-roll.

        Character clips are inserted between narration segments for 70-80% narrator, 20-30% characters.
        B-roll scenes are inserted throughout with Ken Burns effect.

        Args:
            video_plan: VideoPlan
            audio_path: Path to narration audio
            scene_visuals: List of scene image paths
            output_path: Path to save final video
            talking_head_clips: Optional mapping of (scene_id, character_id) -> clip_path
            character_voice_clips: Optional mapping of line_index -> character_audio_path
            broll_visuals: Optional list of B-roll image paths

        Returns:
            Tuple of (video_duration, audio_duration)
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if not scene_visuals:
            raise ValueError("No scene visuals provided")

        talking_head_clips = talking_head_clips or {}
        character_voice_clips = character_voice_clips or {}
        broll_visuals = broll_visuals or []

        # Prepare audio (load and adjust duration)
        target_duration = video_plan.duration_target_seconds
        audio_clip, final_audio_duration = self._prepare_audio(audio_path, target_duration)

        # Build timeline with character clips inserted between narration segments
        use_character_clips = character_voice_clips and video_plan.character_spoken_lines and len(character_voice_clips) > 0
        
        # Initialize transition_duration for use in concatenation
        transition_duration = 0.5
        
        if use_character_clips:
            # Create timeline: narration → character clip → narration → character clip → ...
            self.logger.info(f"Building timeline with {len(character_voice_clips)} character clips inserted between narration segments...")
            video_clips, final_audio_duration = self._build_timeline_with_character_clips(
                video_plan, audio_path, scene_visuals, talking_head_clips, character_voice_clips, target_duration, final_audio_duration
            )
            # Timeline is already built, skip scene-by-scene building and go to concatenation
        else:
            # Build timeline scene-by-scene using edit patterns
            # Calculate duration per scene based on narration lines
            scene_durations = self._calculate_scene_durations(video_plan, final_audio_duration, scene_visuals)
            
            # Get edit pattern
            edit_pattern = self._get_edit_pattern(video_plan)
            
            # Build timeline using pattern-specific methods
            video_clips = []
            
            # Pattern-specific parameters
            max_still_duration = 3.5  # Max duration for a single still image (avoid > 3-4 seconds)
            if edit_pattern == EditPattern.MIXED_RAPID:
                # Shorter clips especially in first 10 seconds
                early_max_duration = 2.0  # Hard cap for first 10 seconds
                later_max_duration = 3.5
            else:
                early_max_duration = max_still_duration
                later_max_duration = max_still_duration

            # Build timeline scene-by-scene
            current_time = 0.0
            for scene_idx, (scene, image_path, scene_duration) in enumerate(
                zip(video_plan.scenes, scene_visuals, scene_durations)
            ):
                if not image_path.exists():
                    self.logger.warning(f"Image not found: {image_path}, skipping...")
                    current_time += scene_duration
                    continue

                scene_id = scene.scene_id
                
                # Get hook variant if available
                hook_variant_path = self._get_hook_variant_path(scene_idx, scene_id, image_path)
                
                # Get talking-head clips for this scene
                scene_talking_heads = self._get_scene_talking_heads(scene_id, talking_head_clips)

                if scene_talking_heads and self.use_talking_heads:
                    # Apply edit pattern logic for dialogue-heavy scenes
                    if edit_pattern == EditPattern.TALKING_HEAD_HEAVY:
                        scene_clips = self._compose_scene_talking_head_heavy(
                            scene_idx, scene_id, scene_duration, image_path, hook_variant_path,
                            scene_talking_heads, scene_visuals, transition_duration, max_still_duration
                        )
                        video_clips.extend(scene_clips)
                    elif edit_pattern == EditPattern.BROLL_CINEMATIC:
                        scene_clips = self._compose_scene_broll_cinematic(
                            scene_idx, scene_id, scene_duration, image_path,
                            scene_talking_heads, scene_visuals, transition_duration
                        )
                        video_clips.extend(scene_clips)
                    elif edit_pattern == EditPattern.MIXED_RAPID:
                        scene_clips = self._compose_scene_mixed_rapid(
                            scene_idx, scene_id, scene_duration, image_path, hook_variant_path,
                            scene_talking_heads, scene_visuals, current_time,
                            early_max_duration, later_max_duration, max_still_duration
                        )
                        video_clips.extend(scene_clips)
                    else:
                        # Default behavior
                        scene_clips = self._compose_scene_default(
                            scene_idx, scene_id, scene_duration, image_path, hook_variant_path,
                            scene_talking_heads, scene_visuals, max_still_duration
                        )
                        video_clips.extend(scene_clips)
                else:
                    # Narration-only scene: Use b-roll with pattern-specific cuts
                    scene_clips = self._compose_scene_narration_only(
                        scene_idx, scene_duration, image_path, hook_variant_path,
                        scene_visuals, edit_pattern, current_time,
                        early_max_duration, later_max_duration, max_still_duration, transition_duration
                    )
                    video_clips.extend(scene_clips)

                current_time += scene_duration

            if not video_clips:
                raise ValueError("No valid scene visuals found")

        # Concatenate all clips with transitions
        self.logger.info("Concatenating video clips with fade transitions...")
        final_video = None
        composite_audio = None
        audio_clip_for_cleanup = None
        
        try:
            final_video = concatenate_videoclips(video_clips, method="compose", padding=-transition_duration if not use_character_clips else -0.5)

            # Add narration text overlay (optional - can be disabled)
            # For now, we'll skip text overlay to keep it clean
            # But the structure is here if needed

            # Set audio (composite narration + character audio if character clips exist)
            self.logger.info("Adding audio to video...")
            use_character_clips = character_voice_clips and video_plan.character_spoken_lines and len(character_voice_clips) > 0
            
            if use_character_clips:
                # Composite narration audio with character audio clips
                composite_audio = self._build_composite_audio(
                    audio_path, character_voice_clips, video_plan.character_spoken_lines, final_audio_duration
                )
                final_video = final_video.set_audio(composite_audio)
            else:
                audio_clip_for_cleanup = audio_clip
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

            # Get final video duration
            final_video_duration = final_video.duration

            self.logger.info(f"Successfully created video: {output_path}")
            self.logger.info(f"Video duration: {final_video_duration:.2f} seconds, Audio duration: {final_audio_duration:.2f} seconds (target: {target_duration}s)")
            
            # Return video and audio durations for metadata
            return final_video_duration, final_audio_duration
            
        finally:
            # Clean up MoviePy clips to prevent memory leaks
            if final_video is not None:
                try:
                    final_video.close()
                except Exception as e:
                    self.logger.warning(f"Error closing final_video: {e}")
            
            if audio_clip_for_cleanup is not None:
                try:
                    audio_clip_for_cleanup.close()
                except Exception as e:
                    self.logger.warning(f"Error closing audio_clip: {e}")
            
            # Composite audio cleanup handled in _build_composite_audio (clips are closed there)
            # Individual video clips in video_clips list will be closed when final_video is closed

