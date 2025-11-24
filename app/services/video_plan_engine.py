"""Video Plan Engine - creates master JSON structure for video generation."""

import datetime
import random
from typing import Any, Optional

from app.core.config import Settings
from app.core.logging_config import get_logger

from app.models.schemas import (
    BrollScene,
    CharacterSet,
    CharacterSpokenLine,
    DialoguePlan,
    EpisodeMetadata,
    NarrationPlan,
    StoryScript,
    VideoPlan,
    VideoScene,
)

# Edit pattern constants
EDIT_PATTERN_TALKING_HEAD_HEAVY = "talking_head_heavy"
EDIT_PATTERN_BROLL_CINEMATIC = "broll_cinematic"
EDIT_PATTERN_MIXED_RAPID = "mixed_rapid"

# Valid edit patterns
VALID_EDIT_PATTERNS = [
    EDIT_PATTERN_TALKING_HEAD_HEAVY,
    EDIT_PATTERN_BROLL_CINEMATIC,
    EDIT_PATTERN_MIXED_RAPID,
]


class VideoPlanEngine:
    """Creates final video plan structure for external video generators."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize the video plan engine.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger

    def create_video_plan(
        self,
        episode_id: str,
        topic: str,
        story_script: StoryScript,
        character_set: CharacterSet,
        dialogue_plan: DialoguePlan,
        narration_plan: NarrationPlan,
        duration_seconds: int,
        style: str = "courtroom_drama",
        niche: Optional[str] = None,
        primary_emotion: Optional[str] = None,
        secondary_emotion: Optional[str] = None,
        pattern_type: Optional[str] = None,
    ) -> VideoPlan:
        """
        Create complete video plan from all components.

        Args:
            episode_id: Unique episode identifier
            topic: Original topic
            story_script: Story script with scenes
            character_set: Generated characters
            dialogue_plan: Dialogue plan
            narration_plan: Narration plan
            duration_seconds: Target duration
            style: Story style

        Returns:
            Complete video plan
        """
        self.logger.info(f"Creating video plan for episode: {episode_id}")

        # Create video scenes from story scenes
        video_scenes = []

        for scene in story_script.scenes:
            # Get dialogue for this scene
            scene_dialogue = [d for d in dialogue_plan.lines if d.scene_id == scene.scene_id]

            # Get narration for this scene
            scene_narration = [n for n in narration_plan.lines if n.scene_id == scene.scene_id]

            # Generate background prompt
            background_prompt = self._generate_background_prompt(scene, style)

            # Determine camera style
            camera_style = self._determine_camera_style(scene.scene_id, len(story_script.scenes))

            # Generate B-roll prompts (optional)
            b_roll_prompts = self._generate_b_roll_prompts(scene)

            video_scene = VideoScene(
                scene_id=scene.scene_id,
                description=scene.description,
                background_prompt=background_prompt,
                camera_style=camera_style,
                narration=scene_narration,
                dialogue=scene_dialogue,
                b_roll_prompts=b_roll_prompts,
            )

            video_scenes.append(video_scene)

        # Count beats (from scenes - each scene represents a beat in beat-based generation)
        # For legacy generation, count scenes as beats
        num_beats = len(video_scenes)
        
        # Count dialogue and narration lines
        num_dialogue_lines = len(dialogue_plan.lines)
        num_narration_lines = len(narration_plan.lines)
        
        # Check for CTA and twist in scenes
        has_cta = any("CTA" in scene.description.upper() or "call-to-action" in scene.description.lower() for scene in story_script.scenes)
        has_twist = any("TWIST" in scene.description.upper() or "twist" in scene.description.lower() for scene in story_script.scenes)
        
        # If we have pattern_type, we can be more precise about CTA/TWIST
        if pattern_type:
            # Pattern A, B, C all have CTA at the end
            has_cta = True
            # Pattern A and C have TWIST
            has_twist = pattern_type in ["A", "C"]

        # Assign edit pattern based on niche, dialogue/narration ratio, or weighted random
        edit_pattern = self._assign_edit_pattern(
            niche=niche or "courtroom",
            style=style,
            num_dialogue_lines=num_dialogue_lines,
            num_narration_lines=num_narration_lines,
        )

        # Create EpisodeMetadata
        metadata = EpisodeMetadata(
            niche=niche or "courtroom",  # Default to courtroom if not provided
            pattern_type=pattern_type or "legacy",
            primary_emotion=primary_emotion or "dramatic",
            secondary_emotion=secondary_emotion,
            topics=[topic] if topic else [],
            moral_axes=[],
            num_beats=num_beats,
            num_scenes=len(video_scenes),
            num_dialogue_lines=num_dialogue_lines,
            num_narration_lines=num_narration_lines,
            has_twist=has_twist,
            has_cta=has_cta,
            style=style,
            hf_model=None,  # Will be populated during rendering
            tts_provider=None,  # Will be populated during rendering
            llm_model_story=getattr(self.settings, "dialogue_model", None),
            llm_model_dialogue=getattr(self.settings, "dialogue_model", None),
            talking_heads_enabled=getattr(self.settings, "use_talking_heads", True),
            edit_pattern=edit_pattern,
        )

        # Sample 2-4 dialogue lines for character speech (not narrator)
        character_spoken_lines = self._sample_character_spoken_lines(
            dialogue_plan, video_scenes, character_set.characters
        )

        # Generate 4-6 cinematic B-roll scenes
        b_roll_scenes = self._generate_cinematic_broll_scenes(
            story_script, video_scenes, style, niche, primary_emotion, duration_seconds
        )

        video_plan = VideoPlan(
            episode_id=episode_id,
            topic=topic,
            duration_target_seconds=duration_seconds,
            style=style,
            title=story_script.title,
            logline=story_script.logline,
            characters=character_set.characters,
            scenes=video_scenes,
            character_spoken_lines=character_spoken_lines,
            b_roll_scenes=b_roll_scenes,
            created_at=datetime.datetime.utcnow().isoformat(),
            version="1.0",
            metadata=metadata,
        )

        self.logger.info(f"Created video plan with {len(video_scenes)} scenes and {len(character_set.characters)} characters")
        self.logger.info(f"Metadata: {num_beats} beats, {num_dialogue_lines} dialogue lines, {num_narration_lines} narration lines")
        self.logger.info(f"Character spoken lines: {len(character_spoken_lines)} (sampled from {num_dialogue_lines} dialogue lines)")
        self.logger.info(f"Edit pattern: {edit_pattern}")
        return video_plan

    def _sample_character_spoken_lines(
        self,
        dialogue_plan: DialoguePlan,
        video_scenes: list[VideoScene],
        characters: list[Any],
    ) -> list[CharacterSpokenLine]:
        """
        Sample 2-4 dialogue lines that should be spoken by characters (not narrator).

        Args:
            dialogue_plan: Dialogue plan with all dialogue lines
            video_scenes: Video scenes for timing context
            characters: List of characters

        Returns:
            List of CharacterSpokenLine objects (2-4 lines)
        """
        import random

        # Filter out narrator dialogue (if any)
        character_dialogue = [
            d for d in dialogue_plan.lines
            if d.character_id and d.character_id not in [c.id for c in characters if c.role == "narrator"]
        ]

        if not character_dialogue:
            self.logger.info("No character dialogue found, skipping character spoken lines")
            return []

        # Sample 2-4 lines (prefer high-emotion lines)
        target_count = random.randint(2, 4)
        target_count = min(target_count, len(character_dialogue))

        # Score lines by emotion (prioritize high-emotion lines)
        scored_lines = []
        emotion_scores = {
            "angry": 3,
            "rage": 3,
            "shocked": 2,
            "tense": 2,
            "emotional": 2,
            "defensive": 2,
            "neutral": 1,
        }

        for dialogue in character_dialogue:
            score = emotion_scores.get(dialogue.emotion.lower(), 1)
            scored_lines.append((score, dialogue))

        # Sort by score (descending) and take top N
        scored_lines.sort(key=lambda x: x[0], reverse=True)
        selected_dialogue = [d for _, d in scored_lines[:target_count]]

        # Convert to CharacterSpokenLine
        character_spoken_lines = []
        for dialogue in selected_dialogue:
            character_spoken_lines.append(
                CharacterSpokenLine(
                    character_id=dialogue.character_id,
                    line_text=dialogue.text,
                    emotion=dialogue.emotion,
                    scene_id=dialogue.scene_id,
                    approx_timing_seconds=dialogue.approx_timing_hint,
                )
            )

        self.logger.info(
            f"Sampled {len(character_spoken_lines)} character spoken lines "
            f"(from {len(character_dialogue)} total character dialogue lines)"
        )

        return character_spoken_lines

    def _assign_edit_pattern(
        self,
        niche: str,
        style: str,
        num_dialogue_lines: int,
        num_narration_lines: int,
    ) -> str:
        """
        Assign edit pattern based on niche, dialogue/narration ratio, or weighted random.

        Args:
            niche: Story niche
            style: Story style
            num_dialogue_lines: Number of dialogue lines
            num_narration_lines: Number of narration lines

        Returns:
            Edit pattern string
        """
        # Calculate dialogue ratio
        total_lines = num_dialogue_lines + num_narration_lines
        dialogue_ratio = num_dialogue_lines / total_lines if total_lines > 0 else 0.0

        # Rule-based assignment based on dialogue ratio
        if dialogue_ratio > 0.4:  # High dialogue content
            # Strong dialogue -> talking_head_heavy
            self.logger.info(f"High dialogue ratio ({dialogue_ratio:.2f}), assigning talking_head_heavy")
            return EDIT_PATTERN_TALKING_HEAD_HEAVY
        elif dialogue_ratio < 0.15:  # Low dialogue content
            # Mostly narration -> broll_cinematic
            self.logger.info(f"Low dialogue ratio ({dialogue_ratio:.2f}), assigning broll_cinematic")
            return EDIT_PATTERN_BROLL_CINEMATIC

        # For medium dialogue ratios, use weighted random based on niche/style
        pattern_weights = self._get_pattern_weights_for_niche(niche, style)
        
        # Sample based on weights
        patterns = list(pattern_weights.keys())
        weights = list(pattern_weights.values())
        selected_pattern = random.choices(patterns, weights=weights, k=1)[0]
        
        self.logger.info(
            f"Medium dialogue ratio ({dialogue_ratio:.2f}), sampled pattern: {selected_pattern} "
            f"(weights: {pattern_weights})"
        )
        return selected_pattern

    def _get_pattern_weights_for_niche(self, niche: str, style: str) -> dict[str, float]:
        """
        Get pattern weights for a given niche/style.

        Args:
            niche: Story niche
            style: Story style

        Returns:
            Dictionary mapping pattern -> weight
        """
        # Default weights
        default_weights = {
            EDIT_PATTERN_TALKING_HEAD_HEAVY: 0.33,
            EDIT_PATTERN_BROLL_CINEMATIC: 0.33,
            EDIT_PATTERN_MIXED_RAPID: 0.34,
        }

        # Niche-specific weights
        niche_weights = {
            "courtroom": {
                EDIT_PATTERN_TALKING_HEAD_HEAVY: 0.4,
                EDIT_PATTERN_BROLL_CINEMATIC: 0.2,
                EDIT_PATTERN_MIXED_RAPID: 0.4,
            },
            "relationship_drama": {
                EDIT_PATTERN_TALKING_HEAD_HEAVY: 0.5,
                EDIT_PATTERN_BROLL_CINEMATIC: 0.3,
                EDIT_PATTERN_MIXED_RAPID: 0.2,
            },
            "injustice": {
                EDIT_PATTERN_TALKING_HEAD_HEAVY: 0.3,
                EDIT_PATTERN_BROLL_CINEMATIC: 0.4,
                EDIT_PATTERN_MIXED_RAPID: 0.3,
            },
        }

        # Style-specific overrides
        if style == "courtroom_drama":
            return niche_weights.get("courtroom", default_weights)
        elif style == "ragebait":
            # Ragebait benefits from rapid cuts
            return {
                EDIT_PATTERN_TALKING_HEAD_HEAVY: 0.3,
                EDIT_PATTERN_BROLL_CINEMATIC: 0.2,
                EDIT_PATTERN_MIXED_RAPID: 0.5,
            }

        return niche_weights.get(niche, default_weights)

    def _generate_background_prompt(self, scene: Any, style: str) -> str:
        """
        Generate background/environment prompt for video generation.

        Args:
            scene: Scene object
            style: Story style

        Returns:
            Background prompt string
        """
        if style == "courtroom_drama":
            base = "A professional courtroom setting with"
            details = "wooden benches, judge's bench, witness stand, American flag, formal atmosphere"
        elif style == "crime_drama":
            base = "A dramatic crime scene or courtroom with"
            details = "tense atmosphere, dramatic lighting, formal setting"
        else:
            base = "A dramatic setting with"
            details = "professional atmosphere, formal environment"

        return f"{base} {details}. {scene.description[:100]}"

    def _determine_camera_style(self, scene_id: int, total_scenes: int) -> str:
        """
        Determine camera style for scene.

        Args:
            scene_id: Scene number
            total_scenes: Total number of scenes

        Returns:
            Camera style string
        """
        # Opening scene: wide shot
        if scene_id == 1:
            return "wide_shot"
        # Middle scenes: medium shots
        elif scene_id < total_scenes:
            return "medium_shot"
        # Final scene: close up for emotional impact
        else:
            return "close_up"

    def _generate_b_roll_prompts(self, scene: Any) -> list[str]:
        """
        Generate optional B-roll image prompts (legacy method).

        Args:
            scene: Scene object

        Returns:
            List of B-roll prompts
        """
        # Stub: In production, LLM would generate relevant B-roll prompts
        return [
            f"B-roll: {scene.description[:50]}",
            f"Detail shot related to {scene.description[:30]}",
        ]

    def _generate_cinematic_broll_scenes(
        self,
        story_script: Any,
        video_scenes: list[VideoScene],
        style: str,
        niche: Optional[str],
        primary_emotion: Optional[str],
        duration_seconds: int,
    ) -> list[BrollScene]:
        """
        Generate 4-6 cinematic B-roll scenes contextual to the story.

        Args:
            story_script: Story script
            video_scenes: Video scenes
            style: Story style
            niche: Story niche
            primary_emotion: Primary emotion
            duration_seconds: Video duration

        Returns:
            List of BrollScene objects
        """
        import random

        # Determine number of B-roll scenes (4-6)
        num_broll = random.randint(4, 6)

        # Contextual B-roll prompts based on niche/style
        niche_lower = (niche or "courtroom").lower()
        style_lower = style.lower()
        emotion_lower = (primary_emotion or "dramatic").lower()

        broll_scenes = []
        categories = ["establishing_scene", "mid_shot", "emotional_closeup", "dramatic_insert"]

        # Generate contextual prompts
        contextual_prompts = self._build_contextual_broll_prompts(
            niche_lower, style_lower, emotion_lower, story_script
        )

        # Distribute B-roll scenes across video duration
        timing_spacing = duration_seconds / (num_broll + 1)

        for i in range(num_broll):
            category = categories[i % len(categories)]
            prompt_template = contextual_prompts.get(category, contextual_prompts.get("mid_shot", ""))
            
            # Customize prompt based on category
            if category == "establishing_scene":
                prompt = f"{prompt_template}, wide angle establishing shot, cinematic composition"
            elif category == "mid_shot":
                prompt = f"{prompt_template}, medium shot, natural framing"
            elif category == "emotional_closeup":
                prompt = f"{prompt_template}, close-up detail, shallow depth of field, emotional focus"
            elif category == "dramatic_insert":
                prompt = f"{prompt_template}, dramatic insert shot, tight framing, cinematic lighting"
            else:
                prompt = prompt_template

            # Add photorealistic style
            prompt += ", cinematic real photograph, shallow depth of field, 35mm lens, natural lighting, film grain, 8k resolution, vertical format 9:16"

            # Calculate timing (distribute evenly across video)
            timing = (i + 1) * timing_spacing

            # Associate with nearest scene
            scene_id = min(i % len(video_scenes) + 1, len(video_scenes))

            broll_scene = BrollScene(
                category=category,
                prompt=prompt,
                timing_hint=timing,
                scene_id=scene_id,
            )

            broll_scenes.append(broll_scene)

        self.logger.info(f"Generated {len(broll_scenes)} cinematic B-roll scenes for {niche_lower} niche")
        return broll_scenes

    def _build_contextual_broll_prompts(
        self, niche: str, style: str, emotion: str, story_script: Any
    ) -> dict[str, str]:
        """
        Build contextual B-roll prompts based on niche, style, and emotion.

        Args:
            niche: Story niche
            style: Story style
            emotion: Primary emotion
            story_script: Story script

        Returns:
            Dictionary mapping category -> prompt
        """
        prompts = {}

        # Courtroom-specific prompts
        if "courtroom" in niche or "courtroom" in style:
            prompts["establishing_scene"] = "wide angle shot of courtroom hallway, warm lighting, empty corridor, professional architecture"
            prompts["mid_shot"] = "judge's bench close-up, gavel on desk, formal courtroom setting, dramatic shadows"
            prompts["emotional_closeup"] = "defendant's hands gripping chair, tension visible, shallow focus, emotional moment"
            prompts["dramatic_insert"] = "judge slamming gavel, dramatic motion blur, cinematic lighting, intense moment"

        # Relationship drama prompts
        elif "relationship" in niche or "relationship" in style:
            prompts["establishing_scene"] = "suburban house driveway, evening lighting, quiet neighborhood, establishing context"
            prompts["mid_shot"] = "living room with tension, soft shadows, domestic setting, emotional atmosphere"
            prompts["emotional_closeup"] = "phone screen showing text message, close-up, shallow depth of field, emotional focus"
            prompts["dramatic_insert"] = "door slamming shut, dramatic motion, cinematic framing, intense moment"

        # Crime/injustice prompts
        elif "crime" in niche or "injustice" in niche or "police" in niche:
            prompts["establishing_scene"] = "police station exterior, harsh lighting, urban setting, establishing context"
            prompts["mid_shot"] = "police interview room, harsh top lighting, sterile environment, tension visible"
            prompts["emotional_closeup"] = "handcuffs on table, close-up detail, shallow focus, symbolic moment"
            prompts["dramatic_insert"] = "evidence bag being sealed, dramatic motion, cinematic lighting, procedural detail"

        # Default/generic prompts
        else:
            prompts["establishing_scene"] = "wide angle establishing shot, professional setting, natural lighting, cinematic composition"
            prompts["mid_shot"] = "medium shot of relevant environment, natural framing, contextual detail"
            prompts["emotional_closeup"] = "close-up detail shot, shallow depth of field, emotional focus, cinematic lighting"
            prompts["dramatic_insert"] = "dramatic insert shot, tight framing, motion blur, intense moment"

        # Enhance with emotion
        if "rage" in emotion or "anger" in emotion:
            for key in prompts:
                prompts[key] += ", harsh lighting, tense atmosphere, visible tension"
        elif "shock" in emotion or "surprise" in emotion:
            for key in prompts:
                prompts[key] += ", dramatic lighting, wide composition, surprise element"
        elif "sad" in emotion or "emotional" in emotion:
            for key in prompts:
                prompts[key] += ", soft lighting, melancholic atmosphere, emotional depth"

        return prompts

