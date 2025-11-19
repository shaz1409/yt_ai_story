"""Tests for Dialogue Engine service."""

import pytest

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import Character, CharacterSet, Scene, StoryScript
from app.services.dialogue_engine import DialogueEngine


@pytest.fixture
def dialogue_engine():
    """Create DialogueEngine instance for testing."""
    settings = Settings()
    logger = get_logger(__name__)
    return DialogueEngine(settings, logger)


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
                narration_lines=[NarrationLine(text="Narration", emotion="neutral", scene_id=1)],
                character_actions=[],
            ),
            Scene(
                scene_id=2,
                description="Scene 2",
                narration_lines=[NarrationLine(text="More narration", emotion="dramatic", scene_id=2)],
                character_actions=[],
            ),
        ],
    )


@pytest.fixture
def sample_character_set():
    """Create sample character set."""
    return CharacterSet(
        characters=[
            Character(
                id="char_1",
                role="defendant",
                name="Test Defendant",
                appearance={},
                personality="nervous",
                voice_profile="young anxious",
            ),
            Character(
                id="char_2",
                role="judge",
                name="Judge Test",
                appearance={},
                personality="authoritative",
                voice_profile="deep authoritative",
            ),
        ],
        narrator_id=None,
    )


def test_generate_dialogue(dialogue_engine, sample_story_script, sample_character_set):
    """Test dialogue generation creates valid dialogue plan."""
    dialogue_plan = dialogue_engine.generate_dialogue(sample_story_script, sample_character_set)

    assert dialogue_plan is not None
    assert isinstance(dialogue_plan.lines, list)

    # Check dialogue lines have required fields
    for line in dialogue_plan.lines:
        assert line.character_id
        assert line.text
        assert line.emotion
        assert line.scene_id > 0
        assert line.approx_timing_hint >= 0

    # Check dialogue is assigned to valid scenes
    scene_ids = {scene.scene_id for scene in sample_story_script.scenes}
    for line in dialogue_plan.lines:
        assert line.scene_id in scene_ids

