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
    EditPattern,
    EpisodeMetadata,
    NarrationPlan,
    StoryScript,
    VideoPlan,
    VideoScene,
)


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

            # Get emotional marker from scene (if available)
            scene_emotion = getattr(scene, "emotion", None)
            if not scene_emotion:
                # Fallback: detect emotion from scene role
                scene_role = self._detect_scene_role_from_description(scene.description)
                emotion_map = {
                    "hook": "shocked",
                    "setup": "tense",
                    "conflict": "angered",
                    "twist": "shocked",
                    "resolution": "relieved",
                }
                scene_emotion = emotion_map.get(scene_role, "tense")

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
                emotion=scene_emotion,  # Add emotional marker
            )

            video_scenes.append(video_scene)

        # Ensure first visual scene is explicitly linked to HOOK text
        if video_scenes and story_script.scenes:
            first_scene = story_script.scenes[0]
            first_video_scene = video_scenes[0]
            # If first scene has HOOK narration, ensure it's prominently featured
            hook_narration = [n for n in first_video_scene.narration if "HOOK" in n.text.upper() or first_scene.scene_id == 1]
            if hook_narration:
                self.logger.info(f"First scene explicitly linked to HOOK: {hook_narration[0].text[:50]}...")

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

        # Sample character spoken lines with improved timing (every 8-12 seconds)
        # and ensure they're tied to reveals/contradictions
        character_spoken_lines = self._sample_character_spoken_lines_with_timing(
            dialogue_plan, video_scenes, character_set.characters, duration_seconds
        )

        # Generate 4-6 cinematic B-roll scenes
        b_roll_scenes = self._generate_cinematic_broll_scenes(
            story_script, video_scenes, style, niche, primary_emotion, duration_seconds
        )

        # Calculate reveal points (timestamps when revelations occur)
        reveal_points = self._calculate_reveal_points(
            character_spoken_lines, video_scenes, duration_seconds
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
            reveal_points=reveal_points,  # Optional field
        )

        self.logger.info(f"Created video plan with {len(video_scenes)} scenes and {len(character_set.characters)} characters")
        self.logger.info(f"Metadata: {num_beats} beats, {num_dialogue_lines} dialogue lines, {num_narration_lines} narration lines")
        self.logger.info(f"Character spoken lines: {len(character_spoken_lines)} (sampled from {num_dialogue_lines} dialogue lines)")
        self.logger.info(f"Reveal points: {len(reveal_points)} timestamps at {reveal_points}")
        self.logger.info(f"Edit pattern: {edit_pattern}")
        return video_plan

    def _calculate_reveal_points(
        self,
        character_spoken_lines: list[CharacterSpokenLine],
        video_scenes: list[VideoScene],
        duration_seconds: int,
    ) -> list[int]:
        """
        Calculate reveal points (timestamps in seconds) when revelations occur.

        Args:
            character_spoken_lines: Character spoken lines
            video_scenes: Video scenes
            duration_seconds: Total duration

        Returns:
            List of reveal point timestamps (in seconds, as integers)
        """
        reveal_points = []
        
        # Keywords that indicate revelations
        reveal_keywords = ["not", "never", "didn't", "wasn't", "can't", "won't", "actually", "truth", "real", "really", "secret", "hidden", "found out", "discovered"]
        contradiction_keywords = ["but", "however", "except", "though", "although", "despite"]
        
        # Check character spoken lines for reveals
        for line in character_spoken_lines:
            text_lower = line.line_text.lower()
            if any(kw in text_lower for kw in reveal_keywords + contradiction_keywords):
                timestamp = int(line.approx_timing_seconds)
                if 0 <= timestamp <= duration_seconds:
                    reveal_points.append(timestamp)
        
        # Also check scene descriptions for TURNING_POINT or TWIST beats
        for scene in video_scenes:
            desc_lower = scene.description.lower()
            if "turning_point" in desc_lower or "twist" in desc_lower or "reveal" in desc_lower:
                # Estimate timestamp based on scene position
                scene_idx = scene.scene_id - 1
                total_scenes = len(video_scenes)
                if total_scenes > 0:
                    estimated_time = int((scene_idx / total_scenes) * duration_seconds)
                    if estimated_time not in reveal_points:
                        reveal_points.append(estimated_time)
        
        # Sort and deduplicate
        reveal_points = sorted(list(set(reveal_points)))
        
        return reveal_points

    def _sample_character_spoken_lines_with_timing(
        self,
        dialogue_plan: DialoguePlan,
        video_scenes: list[VideoScene],
        characters: list[Any],
        duration_seconds: int,
    ) -> list[CharacterSpokenLine]:
        """
        Sample character spoken lines ensuring they occur every 8-12 seconds
        and are tied to reveals/contradictions.

        Args:
            dialogue_plan: Dialogue plan with all dialogue lines
            video_scenes: Video scenes for timing context
            characters: List of characters
            duration_seconds: Total video duration

        Returns:
            List of CharacterSpokenLine objects (spaced every 8-12 seconds)
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

        # Identify lines that are reveals or contradictions
        reveal_keywords = ["not", "never", "didn't", "wasn't", "can't", "won't", "actually", "truth", "real", "really"]
        contradiction_keywords = ["but", "however", "except", "though", "although", "despite"]
        
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
            text_lower = dialogue.text.lower()
            
            # Boost score for reveals/contradictions
            if any(kw in text_lower for kw in reveal_keywords):
                score += 2  # Reveals are high priority
            if any(kw in text_lower for kw in contradiction_keywords):
                score += 1  # Contradictions are also important
            
            # Boost score for rhetorical questions (reveals often come as questions)
            if "?" in dialogue.text:
                score += 1
            
            scored_lines.append((score, dialogue))

        # Sort by score (descending)
        scored_lines.sort(key=lambda x: x[0], reverse=True)

        # Calculate target spacing: every 8-12 seconds
        target_spacing = random.uniform(8.0, 12.0)
        max_lines = int(duration_seconds / target_spacing) + 1
        max_lines = min(max_lines, len(character_dialogue), 6)  # Cap at 6 lines max

        # Select lines with timing constraints
        selected_dialogue = []
        current_time = 0.0
        
        for score, dialogue in scored_lines:
            if len(selected_dialogue) >= max_lines:
                break
            
            # Check if this line fits the timing window
            target_time = current_time + target_spacing
            if target_time <= duration_seconds:
                # Update timing to match spacing
                dialogue.approx_timing_hint = target_time
                selected_dialogue.append(dialogue)
                current_time = target_time
            else:
                # If we're near the end, still include high-scoring lines
                if score >= 3 and len(selected_dialogue) < 3:
                    dialogue.approx_timing_hint = min(current_time + 5.0, duration_seconds - 2.0)
                    selected_dialogue.append(dialogue)
                    current_time = dialogue.approx_timing_hint

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
            f"(spaced every ~{target_spacing:.1f}s, from {len(character_dialogue)} total character dialogue lines)"
        )

        return character_spoken_lines

    def _sample_character_spoken_lines(
        self,
        dialogue_plan: DialoguePlan,
        video_scenes: list[VideoScene],
        characters: list[Any],
    ) -> list[CharacterSpokenLine]:
        """
        Legacy method - kept for backward compatibility.
        Use _sample_character_spoken_lines_with_timing instead.
        """
        return self._sample_character_spoken_lines_with_timing(
            dialogue_plan, video_scenes, characters, 60  # Default 60s
        )

    def _assign_edit_pattern(
        self,
        niche: str,
        style: str,
        num_dialogue_lines: int,
        num_narration_lines: int,
    ) -> EditPattern:
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
            return EditPattern.TALKING_HEAD_HEAVY
        elif dialogue_ratio < 0.15:  # Low dialogue content
            # Mostly narration -> broll_cinematic
            self.logger.info(f"Low dialogue ratio ({dialogue_ratio:.2f}), assigning broll_cinematic")
            return EditPattern.BROLL_CINEMATIC

        # For medium dialogue ratios, use weighted random based on niche/style
        pattern_weights = self._get_pattern_weights_for_niche(niche, style)
        
        # Sample based on weights
        patterns = list(pattern_weights.keys())
        weights = list(pattern_weights.values())
        selected_pattern_str = random.choices(patterns, weights=weights, k=1)[0]
        
        # Convert string to EditPattern enum
        try:
            selected_pattern = EditPattern(selected_pattern_str)
        except ValueError:
            self.logger.warning(f"Unknown edit pattern '{selected_pattern_str}', defaulting to TALKING_HEAD_HEAVY")
            selected_pattern = EditPattern.TALKING_HEAD_HEAVY
        
        self.logger.info(
            f"Medium dialogue ratio ({dialogue_ratio:.2f}), sampled pattern: {selected_pattern.value} "
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
            Dictionary mapping pattern string -> weight
        """
        # Default weights
        default_weights = {
            EditPattern.TALKING_HEAD_HEAVY.value: 0.33,
            EditPattern.BROLL_CINEMATIC.value: 0.33,
            EditPattern.MIXED_RAPID.value: 0.34,
        }

        # Niche-specific weights
        niche_weights = {
            "courtroom": {
                EditPattern.TALKING_HEAD_HEAVY.value: 0.4,
                EditPattern.BROLL_CINEMATIC.value: 0.2,
                EditPattern.MIXED_RAPID.value: 0.4,
            },
            "relationship_drama": {
                EditPattern.TALKING_HEAD_HEAVY.value: 0.5,
                EditPattern.BROLL_CINEMATIC.value: 0.3,
                EditPattern.MIXED_RAPID.value: 0.2,
            },
            "injustice": {
                EditPattern.TALKING_HEAD_HEAVY.value: 0.3,
                EditPattern.BROLL_CINEMATIC.value: 0.4,
                EditPattern.MIXED_RAPID.value: 0.3,
            },
        }

        # Style-specific overrides
        if style == "courtroom_drama":
            return niche_weights.get("courtroom", default_weights)
        elif style == "ragebait":
            # Ragebait benefits from rapid cuts
            return {
                EditPattern.TALKING_HEAD_HEAVY.value: 0.3,
                EditPattern.BROLL_CINEMATIC.value: 0.2,
                EditPattern.MIXED_RAPID.value: 0.5,
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

