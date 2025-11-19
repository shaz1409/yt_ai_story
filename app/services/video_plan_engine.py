"""Video Plan Engine - creates master JSON structure for video generation."""

import datetime
from typing import Any

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import (
    CharacterSet,
    DialoguePlan,
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

        video_plan = VideoPlan(
            episode_id=episode_id,
            topic=topic,
            duration_target_seconds=duration_seconds,
            style=style,
            title=story_script.title,
            logline=story_script.logline,
            characters=character_set.characters,
            scenes=video_scenes,
            created_at=datetime.datetime.utcnow().isoformat(),
            version="1.0",
        )

        self.logger.info(f"Created video plan with {len(video_scenes)} scenes and {len(character_set.characters)} characters")
        return video_plan

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
        Generate optional B-roll image prompts.

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

