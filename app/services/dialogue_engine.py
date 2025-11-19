"""Dialogue Engine - generates emotion-tagged dialogue."""

from typing import Any

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import CharacterSet, DialogueLine, DialoguePlan, Scene, StoryScript


class DialogueEngine:
    """Generates believable, emotion-tagged dialogue for characters."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize the dialogue engine.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger

    def generate_dialogue(
        self,
        story_script: StoryScript,
        character_set: CharacterSet,
    ) -> DialoguePlan:
        """
        Generate dialogue for the story.

        For now, this is a stub that creates basic dialogue.
        In production, this would use LLM to:
        - Create natural, character-appropriate dialogue
        - Match dialogue to scene context
        - Add appropriate emotional tags
        - Time dialogue appropriately

        Args:
            story_script: Story script with scenes
            character_set: Generated characters

        Returns:
            Dialogue plan with all dialogue lines
        """
        self.logger.info("Generating dialogue for story")

        dialogue_lines = []

        # Map characters by role for easy lookup
        character_map = {char.role: char for char in character_set.characters}

        for scene in story_script.scenes:
            scene_dialogue = self._generate_scene_dialogue(scene, character_map)
            dialogue_lines.extend(scene_dialogue)

        dialogue_plan = DialoguePlan(lines=dialogue_lines)

        self.logger.info(f"Generated {len(dialogue_lines)} dialogue lines across {len(story_script.scenes)} scenes")
        return dialogue_plan

    def _generate_scene_dialogue(self, scene: Scene, character_map: dict) -> list[DialogueLine]:
        """
        Generate dialogue for a single scene.

        Args:
            scene: Scene to generate dialogue for
            character_map: Map of role -> Character

        Returns:
            List of dialogue lines for this scene
        """
        dialogue_lines = []

        # Generate 1-3 dialogue lines per scene based on scene content
        # In production, LLM would analyze scene and generate appropriate dialogue

        # Example: If defendant is present, add their dialogue
        if "defendant" in character_map:
            defendant = character_map["defendant"]
            dialogue_lines.append(
                DialogueLine(
                    character_id=defendant.id,
                    text="I can't believe this is happening.",
                    emotion="shocked",
                    scene_id=scene.scene_id,
                    approx_timing_hint=5.0,
                )
            )

        # Example: If judge is present, add their dialogue
        if "judge" in character_map and scene.scene_id == 1:
            judge = character_map["judge"]
            dialogue_lines.append(
                DialogueLine(
                    character_id=judge.id,
                    text="The court will now proceed.",
                    emotion="neutral",
                    scene_id=scene.scene_id,
                    approx_timing_hint=2.0,
                )
            )

        # Example: If lawyer is present, add their dialogue
        if "lawyer" in character_map and scene.scene_id > 1:
            lawyer = character_map["lawyer"]
            dialogue_lines.append(
                DialogueLine(
                    character_id=lawyer.id,
                    text="Your honor, I object!",
                    emotion="tense",
                    scene_id=scene.scene_id,
                    approx_timing_hint=8.0,
                )
            )

        return dialogue_lines

