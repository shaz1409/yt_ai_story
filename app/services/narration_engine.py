"""Narration Engine - generates voiceover narration."""

from typing import Any

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import NarrationLine, NarrationPlan, StoryScript


class NarrationEngine:
    """Produces voiceover narration that carries the story."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize the narration engine.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger

    def generate_narration(self, story_script: StoryScript) -> NarrationPlan:
        """
        Generate narration plan from story script.

        The narration lines are already in the story script scenes,
        so this primarily reorganizes and enhances them.

        Args:
            story_script: Story script with narration lines

        Returns:
            Narration plan with all narration lines
        """
        self.logger.info("Generating narration plan")

        narration_lines = []

        for scene in story_script.scenes:
            # Add all narration lines from the scene
            for narration_line in scene.narration_lines:
                # Enhance narration if needed (in production, LLM could refine)
                narration_lines.append(narration_line)

        narration_plan = NarrationPlan(lines=narration_lines)

        self.logger.info(f"Generated {len(narration_lines)} narration lines")
        return narration_plan

