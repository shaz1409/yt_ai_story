"""Tests for Narration Engine service."""

import pytest

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import Scene, StoryScript
from app.services.narration_engine import NarrationEngine


@pytest.fixture
def narration_engine():
    """Create NarrationEngine instance for testing."""
    settings = Settings()
    logger = get_logger(__name__)
    return NarrationEngine(settings, logger)


@pytest.fixture
def sample_story_script():
    """Create sample story script."""
    from app.models.schemas import NarrationLine

    return StoryScript(
        title="Test Story",
        logline="A test",
        scenes=[
            Scene(
                scene_id=1,
                description="Scene 1",
                narration_lines=[
                    NarrationLine(text="First narration", emotion="neutral", scene_id=1),
                    NarrationLine(text="Second narration", emotion="dramatic", scene_id=1),
                ],
                character_actions=[],
            ),
            Scene(
                scene_id=2,
                description="Scene 2",
                narration_lines=[NarrationLine(text="Third narration", emotion="tense", scene_id=2)],
                character_actions=[],
            ),
        ],
    )


def test_generate_narration(narration_engine, sample_story_script):
    """Test narration generation creates valid narration plan."""
    narration_plan = narration_engine.generate_narration(sample_story_script)

    assert narration_plan is not None
    assert len(narration_plan.lines) > 0

    # Check all narration lines have required fields
    for line in narration_plan.lines:
        assert line.text
        assert line.emotion
        assert line.scene_id > 0

    # Check all scenes are represented
    scene_ids = {scene.scene_id for scene in sample_story_script.scenes}
    narration_scene_ids = {line.scene_id for line in narration_plan.lines}
    assert narration_scene_ids.issubset(scene_ids)

