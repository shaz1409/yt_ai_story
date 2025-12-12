"""Character Video Engine - generates character face images and talking-head clips."""

from pathlib import Path
from typing import Any, Optional

from moviepy.editor import AudioFileClip, ImageClip
from PIL import Image

# Compatibility shim for Pillow 10.0.0+ (ANTIALIAS was removed)
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import Character, DialogueLine, VideoPlan
from app.services.hf_endpoint_client import HFEndpointClient
from app.services.image_quality_validator import ImageQualityValidator
from app.services.lipsync_provider import get_lipsync_provider
from app.utils.image_post_processor import ImagePostProcessor


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

            # Resize to vertical format
            video_width = getattr(self.settings, "video_width", 1080)
            video_height = getattr(self.settings, "video_height", 1920)
            target_size = (video_width, video_height)
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
        
        # Initialize lip-sync provider if available
        self.lipsync_provider = None
        lipsync_enabled = getattr(settings, "lipsync_enabled", False) or getattr(settings, "use_lipsync", False)
        if lipsync_enabled:
            self.lipsync_provider = get_lipsync_provider(settings, logger)
            if self.lipsync_provider:
                self.logger.info("Lip-sync provider initialized (real mouth movement enabled)")
            else:
                self.logger.warning("Lip-sync requested but no provider configured. Falling back to basic talking-head.")
        
        # Fallback to basic talking-head provider
        self.talking_head_provider = TalkingHeadProvider(settings, logger)
        
        # Initialize HF Endpoint client for image generation
        try:
            self.hf_endpoint_client = HFEndpointClient(settings, logger)
        except ValueError as e:
            self.logger.warning(f"HF Endpoint not configured: {e}. Will use placeholder images.")
            self.hf_endpoint_client = None
        
        # Initialize image quality validator
        self.image_validator = ImageQualityValidator(settings, logger)
        
        # Initialize image post-processor
        self.image_post_processor = ImagePostProcessor(settings, logger)

    def generate_character_face_image(
        self,
        character: Character,
        output_dir: Path,
        style: str = "courtroom_drama",
        image_style: str = "photorealistic",
    ) -> Path:
        """
        Generate a single photorealistic base image for this character.

        Uses seed locking based on character_id for consistent appearance across shots.

        Args:
            character: Character object
            output_dir: Directory to save image
            style: Story style (for prompt generation)
            image_style: Image style ("photorealistic" or "artistic")

        Returns:
            Path to the generated image file
        """
        self.logger.info(
            f"Generating {image_style} face image for character: {character.name} ({character.role})"
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        image_path = output_dir / f"character_{character.id}_face.png"

        # Build photoreal prompt
        prompt = self._build_character_face_prompt(character, style, image_style)

        # Generate character identity seed from character_id for consistency
        character_seed = self._generate_character_seed(character.id)

        # Generate image with seed locking and quality validation
        max_attempts = getattr(self.settings, "max_image_retry_attempts", 3)
        for attempt in range(1, max_attempts + 1):
            try:
                self._generate_character_image(
                    prompt,
                    image_path,
                    seed=character_seed,
                    sharpness=8,
                    realism_level="ultra",
                    film_style="kodak_portra",
                )
                
                # Validate image quality
                if image_path.exists():
                    score = self.image_validator.score_image(image_path, "character_portrait")
                    if score >= self.image_validator.min_acceptable_score:
                        self.logger.info(f"✅ Accepted character image with quality score {score:.3f}: {image_path.name}")
                        
                        # Post-process image after validation
                        processed_path = self.image_post_processor.get_processed_path(image_path)
                        enhanced_path = self.image_post_processor.enhance_image(
                            image_path, processed_path, "character_portrait"
                        )
                        return enhanced_path
                    else:
                        self.logger.warning(
                            f"Image quality score {score:.3f} below threshold "
                            f"({self.image_validator.min_acceptable_score:.3f})"
                        )
                        if attempt < max_attempts:
                            self.logger.info(f"Regenerating character image (attempt {attempt + 1}/{max_attempts})")
                            # Vary seed slightly for retry
                            character_seed = (character_seed + attempt * 1000) % (2**32)
                            continue
                        else:
                            self.logger.warning("Max retries reached, using fallback character image")
                            break
                else:
                    self.logger.warning(f"Generated image not found: {image_path}")
                    if attempt < max_attempts:
                        self.logger.info(f"Retrying character image generation (attempt {attempt + 1}/{max_attempts})")
                        continue
                    else:
                        break
                        
            except Exception as e:
                self.logger.error(f"Failed to generate character image (attempt {attempt}/{max_attempts}): {e}")
                if attempt < max_attempts:
                    self.logger.info(f"Retrying character image generation (attempt {attempt + 1}/{max_attempts})")
                    # Vary seed slightly for retry
                    character_seed = (character_seed + attempt * 1000) % (2**32)
                    continue
                else:
                    break

        # All attempts failed - use fallback
        fallback_path = self._get_fallback_character_image(image_path, character)
        if fallback_path and fallback_path.exists():
            self.logger.info(f"Using fallback character image: {fallback_path}")
            # Post-process fallback image
            processed_path = self.image_post_processor.get_processed_path(fallback_path)
            enhanced_path = self.image_post_processor.enhance_image(
                fallback_path, processed_path, "character_portrait"
            )
            return enhanced_path
        else:
            self.logger.warning("No fallback available, creating placeholder character image")
            self._create_placeholder_character_image(image_path, character)
            # Post-process placeholder image
            processed_path = self.image_post_processor.get_processed_path(image_path)
            enhanced_path = self.image_post_processor.enhance_image(
                image_path, processed_path, "character_portrait"
            )
            return enhanced_path

    def _generate_character_seed(self, character_id: str) -> int:
        """
        Generate a deterministic seed from character_id for consistent appearance.

        Args:
            character_id: Character ID

        Returns:
            Integer seed (0-4294967295)
        """
        import hashlib

        # Hash character_id to get a consistent seed
        hash_obj = hashlib.md5(character_id.encode())
        hash_int = int(hash_obj.hexdigest(), 16)
        # Convert to 32-bit integer (0 to 4294967295)
        seed = hash_int % (2**32)
        return seed

    def generate_talking_head_clip(
        self,
        character: Character,
        dialogue_line: DialogueLine,
        audio_path: Path,
        output_dir: Path,
        style: str = "courtroom_drama",
        emotion: str = "neutral",
    ) -> Path:
        """
        Generate a short talking-head video clip for a dialogue line.

        Uses HF FLUX image of the character as base.
        If direct talking-head isn't possible, falls back to Ken Burns + subtle mouth-movement effect.

        Args:
            character: Character object
            dialogue_line: DialogueLine to animate
            audio_path: Path to dialogue audio file
            output_dir: Directory to save clip
            style: Story style
            emotion: Emotion for the clip (affects visual treatment)

        Returns:
            Path to the generated video clip
        """
        self.logger.info(
            f"Generating talking-head clip for {character.name} (emotion: {emotion}): '{dialogue_line.text[:50]}...'"
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        clip_path = output_dir / f"talking_head_{character.id}_{dialogue_line.character_id}.mp4"

        # Ensure character face image exists
        # Check both new location (outputs/characters/) and legacy location
        characters_dir = output_dir.parent / "characters" if output_dir.name != "characters" else output_dir
        character_faces_dir = output_dir / "character_faces"
        
        face_image_path = characters_dir / f"character_{character.id}_face.png"
        if not face_image_path.exists():
            face_image_path = character_faces_dir / f"character_{character.id}_face.png"

        if not face_image_path.exists():
            self.logger.info(f"Character face image not found, generating: {face_image_path}")
            image_style = getattr(self.settings, "character_image_style", "photorealistic")
            self.generate_character_face_image(character, characters_dir, style, image_style)
            face_image_path = characters_dir / f"character_{character.id}_face.png"

        # Generate talking-head clip with fallback
        try:
            # Try lip-sync provider first if available
            if self.lipsync_provider:
                try:
                    self.logger.info(f"Attempting real lip-sync for {character.name}...")
                    clip_path = self.lipsync_provider.generate_talking_head(face_image_path, audio_path, clip_path)
                    self.logger.info(f"Generated lip-sync talking-head clip: {clip_path}")
                    return clip_path
                except NotImplementedError:
                    self.logger.warning("Lip-sync provider not fully implemented, falling back to basic talking-head")
                except Exception as e:
                    self.logger.warning(f"Lip-sync generation failed: {e}, falling back to basic talking-head")
            
            # Fallback to basic talking head provider (Ken Burns + zoom effect)
            self.talking_head_provider.generate_talking_head(face_image_path, audio_path, clip_path)
            self.logger.info(f"Generated basic talking-head clip: {clip_path}")
            return clip_path
        except Exception as e:
            self.logger.warning(f"Talking-head generation failed for {character.name}: {e}, will fallback to scene visual")
            # Return None to signal failure - VideoRenderer will handle fallback
            raise

    def _generate_stable_character_id(self, character: Character) -> str:
        """
        Generate a stable character identifier based on role and appearance.
        
        This allows the same character (e.g., "Judge Williams") to reuse the same
        face image across different episodes.
        
        Args:
            character: Character object
            
        Returns:
            Stable character identifier (e.g., "judge_abc123def456")
        """
        import hashlib
        import json
        
        # Create hash from role + appearance + personality
        # Exclude episode-specific fields like "unique_id" from appearance
        appearance = character.appearance or {}
        stable_appearance = {k: v for k, v in appearance.items() if k != "unique_id"}
        
        stable_data = {
            "role": character.role.lower(),
            "appearance": stable_appearance,
            "personality": character.personality,
        }
        
        # Create deterministic hash
        stable_json = json.dumps(stable_data, sort_keys=True)
        stable_hash = hashlib.md5(stable_json.encode()).hexdigest()[:12]
        
        stable_id = f"{character.role.lower()}_{stable_hash}"
        return stable_id

    def ensure_character_assets(
        self,
        video_plan: VideoPlan,
        output_dir: Path,
        style: str = "courtroom_drama",
        image_style: str = "photorealistic",
    ) -> dict[str, Path]:
        """
        Ensure all main characters have base face images generated.

        Images are cached by stable character ID (role + appearance hash) to allow
        reuse across episodes. Same character (e.g., "Judge Williams") will use
        the same face image.

        Args:
            video_plan: VideoPlan with characters
            output_dir: Directory to save assets
            style: Story style
            image_style: Image style ("photorealistic" or "artistic")

        Returns:
            Mapping: character_id -> image_path
        """
        self.logger.info("Ensuring character assets are generated...")

        # Use dedicated characters directory (global cache)
        # Store in a shared location so all episodes can reuse faces
        # Get project root (3 levels up from this file: app/services/character_video_engine.py)
        project_root = Path(__file__).parent.parent.parent
        characters_dir = project_root / "outputs" / "characters"
        characters_dir.mkdir(parents=True, exist_ok=True)

        # Also keep in character_faces for backward compatibility
        character_faces_dir = output_dir / "character_faces"
        character_faces_dir.mkdir(parents=True, exist_ok=True)

        character_assets = {}

        # Generate faces for all non-narrator characters
        for character in video_plan.characters:
            if character.role.lower() != "narrator":
                # Generate stable ID for caching
                stable_id = self._generate_stable_character_id(character)
                
                # Primary location: outputs/characters/ (global cache)
                face_path = characters_dir / f"character_{stable_id}_face.png"
                # Secondary location: character_faces/ (episode-specific, for backward compatibility)
                legacy_path = character_faces_dir / f"character_{character.id}_face.png"

                if not face_path.exists():
                    self.logger.info(
                        f"Generating {image_style} face for character: {character.name} "
                        f"(role: {character.role}, stable_id: {stable_id})"
                    )
                    # Generate with stable_id for seed consistency
                    # Create a temporary character with stable_id for generation
                    temp_character = Character(
                        id=stable_id,  # Use stable_id for seed generation
                        role=character.role,
                        name=character.name,
                        appearance=character.appearance,
                        personality=character.personality,
                        voice_profile=character.voice_profile,
                        detailed_voice_profile=character.detailed_voice_profile,
                    )
                    face_path = self.generate_character_face_image(
                        temp_character, characters_dir, style, image_style
                    )
                    # Also copy to legacy location for backward compatibility
                    if face_path.exists():
                        import shutil
                        shutil.copy2(face_path, legacy_path)
                        self.logger.debug(f"Copied character image to legacy location: {legacy_path}")
                else:
                    # Check if processed version exists
                    processed_path = self.image_post_processor.get_processed_path(face_path)
                    if processed_path.exists():
                        face_path = processed_path
                        self.logger.debug(f"Using cached processed face: {processed_path}")
                    else:
                        # Post-process the cached original
                        enhanced_path = self.image_post_processor.enhance_image(
                            face_path, processed_path, "character_portrait"
                        )
                        face_path = enhanced_path
                    
                    self.logger.info(
                        f"Reusing cached face for character: {character.name} "
                        f"(role: {character.role}, stable_id: {stable_id})"
                    )
                    # Copy cached face to legacy location for this episode
                    if face_path.exists() and not legacy_path.exists():
                        import shutil
                        shutil.copy2(face_path, legacy_path)
                        self.logger.debug(f"Copied cached face to legacy location: {legacy_path}")

                character_assets[character.id] = face_path

        self.logger.info(
            f"Ensured {len(character_assets)} character face images "
            f"(cached in {characters_dir})"
        )
        return character_assets

    def _build_character_face_prompt(
        self, character: Character, style: str, image_style: str = "photorealistic"
    ) -> str:
        """
        Build photorealistic character face prompt for character portrait.

        Args:
            character: Character object
            style: Story style
            image_style: Image style ("photorealistic" or "artistic")

        Returns:
            Image generation prompt
        """
        # Extract appearance details with personality mapping
        appearance = character.appearance or {}
        age = self._map_personality_to_age(character, appearance)
        gender = self._map_personality_to_gender(character, appearance)
        ethnicity = appearance.get("ethnicity", self._map_personality_to_ethnicity(character))
        hair = appearance.get("hair", self._map_personality_to_hair(character))
        expression = appearance.get("expression", self._map_personality_to_expression(character))
        clothing = self._map_personality_to_clothing(character)

        if image_style == "photorealistic":
            # Ultra-realistic photorealistic prompt
            prompt_parts = [
                "ultra-realistic portrait of a human",
                f"{age} {gender}".strip() if gender else age,
                ethnicity if ethnicity else "",
                "cinematic lighting",
                "shallow depth of field",
                "50mm lens",
                "natural skin texture",
                "detailed facial features",
                f"facial expression: {expression}",
                hair if hair else "",
                clothing if clothing else "",
                "professional photography",
                "Kodak Portra 400 film grain",
                "Sony FX3 color grading",
                "8k resolution",
                "vertical format 9:16",
                "sharp focus on eyes",
                "soft bokeh background",
            ]
        else:
            # Artistic/legacy style (backward compatible)
            role_context = {
                "judge": "authoritative judge in black robes",
                "defendant": "defendant in formal attire",
                "lawyer": "professional lawyer in business suit",
                "prosecutor": "serious prosecutor in formal suit",
                "witness": "witness in courtroom",
            }
            role_desc = role_context.get(character.role.lower(), f"{character.role} in courtroom")

            prompt_parts = [
                "Close-up portrait",
                f"{age} {gender}".strip() if gender else age,
                ethnicity if ethnicity else "",
                role_desc,
                f"facial expression: {expression}",
                hair if hair else "",
                f"{character.personality} personality",
                "neutral or slightly dramatic lighting",
                "single subject",
                "photorealistic",
                "ultra-realistic",
                "4k quality",
                "vertical format",
                "professional headshot",
            ]

        # Filter out empty parts and join
        prompt = ". ".join([p for p in prompt_parts if p.strip()]) + "."

        return prompt

    def _map_personality_to_age(self, character: Character, appearance: dict) -> str:
        """Map personality traits to age range."""
        age = appearance.get("age") or appearance.get("age_range", "")
        if age:
            return age

        personality_lower = character.personality.lower()
        if any(trait in personality_lower for trait in ["experienced", "authoritative", "stern", "judge"]):
            return "50-70 years old"
        elif any(trait in personality_lower for trait in ["young", "teen", "teenager", "defendant"]):
            return "18-25 years old"
        elif any(trait in personality_lower for trait in ["professional", "confident", "lawyer", "prosecutor"]):
            return "35-50 years old"
        else:
            return "30-45 years old"

    def _map_personality_to_gender(self, character: Character, appearance: dict) -> str:
        """Map personality traits to gender."""
        gender = appearance.get("gender", "")
        if gender and gender != "any":
            return gender

        # Default based on role (can be randomized in future)
        role = character.role.lower()
        if role in ["judge", "lawyer", "prosecutor"]:
            return "male"  # Default, can be randomized
        elif role in ["defendant", "witness"]:
            return "any"  # More diverse
        else:
            return "any"

    def _map_personality_to_ethnicity(self, character: Character) -> str:
        """Map personality traits to ethnicity (diverse representation)."""
        # For now, return empty to let model generate diverse representation
        # In future, can add logic based on story context or character traits
        return ""

    def _map_personality_to_hair(self, character: Character) -> str:
        """Map personality traits to hair style."""
        personality_lower = character.personality.lower()
        if "authoritative" in personality_lower or "judge" in character.role.lower():
            return "short professional haircut, graying"
        elif "young" in personality_lower or "teen" in personality_lower:
            return "modern hairstyle"
        else:
            return "professional hairstyle"

    def _map_personality_to_expression(self, character: Character) -> str:
        """Map personality traits to facial expression."""
        personality_lower = character.personality.lower()
        if "stern" in personality_lower or "authoritative" in personality_lower:
            return "serious, determined"
        elif "nervous" in personality_lower or "anxious" in personality_lower:
            return "worried, tense"
        elif "confident" in personality_lower:
            return "confident, composed"
        elif "defensive" in personality_lower:
            return "defensive, guarded"
        else:
            return "neutral, professional"

    def _map_personality_to_clothing(self, character: Character) -> str:
        """Map personality traits to clothing."""
        role = character.role.lower()
        if role == "judge":
            return "black judicial robes"
        elif role in ["lawyer", "prosecutor"]:
            return "professional business suit, formal attire"
        elif role == "defendant":
            return "formal courtroom attire"
        else:
            return "professional attire"

    def _generate_character_image(
        self,
        prompt: str,
        output_path: Path,
        seed: Optional[int] = None,
        sharpness: int = 8,
        realism_level: str = "ultra",
        film_style: str = "kodak_portra",
    ) -> None:
        """
        Generate character image using HF Inference Endpoint with photorealistic parameters.

        Args:
            prompt: Image generation prompt
            output_path: Path to save image
            seed: Random seed for consistency (0-4294967295)
            sharpness: Sharpness level (1-10, default 8)
            realism_level: Realism level ("high", "ultra", "photoreal")
            film_style: Film style ("kodak_portra", "canon", "sony_fx3", "fuji")
        """
        if self.hf_endpoint_client:
            try:
                self.hf_endpoint_client.generate_image(
                    prompt,
                    output_path,
                    image_type="character_portrait",
                    seed=seed,
                    sharpness=sharpness,
                    realism_level=realism_level,
                    film_style=film_style,
                )
            except Exception as e:
                self.logger.error(f"HF Endpoint image generation failed: {e}, using placeholder")
                self._create_placeholder_character_image(output_path, None, prompt)
        else:
            self.logger.warning("HF Endpoint not configured - using placeholder character image")
            self._create_placeholder_character_image(output_path, None, prompt)


    def _get_fallback_character_image(
        self, output_path: Path, character: Optional[Character] = None
    ) -> Optional[Path]:
        """
        Get fallback character image from assets/characters_fallbacks/.
        
        Args:
            output_path: Desired output path (used to determine fallback name)
            character: Character object (optional, for role-based fallback)
            
        Returns:
            Path to fallback image if found, None otherwise
        """
        fallback_dir = Path("assets/characters_fallbacks")
        if not fallback_dir.exists():
            fallback_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Created fallback directory: {fallback_dir}")
            return None
        
        # Try to find a fallback image
        # First, try role-based fallback
        if character and character.role:
            role_fallback = fallback_dir / f"{character.role.lower()}_fallback.png"
            if role_fallback.exists():
                return role_fallback
        
        # Try generic fallback
        generic_fallback = fallback_dir / "character_fallback.png"
        if generic_fallback.exists():
            return generic_fallback
        
        # Try any PNG in the directory
        fallback_images = list(fallback_dir.glob("*.png"))
        if fallback_images:
            return fallback_images[0]
        
        return None

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
        video_width = getattr(self.settings, "video_width", 1080)
        video_height = getattr(self.settings, "video_height", 1920)
        target_size = (video_width, video_height)
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

