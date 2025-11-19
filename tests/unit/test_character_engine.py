"""Tests for Character Engine service."""

import pytest

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import Scene, StoryScript
from app.services.character_engine import CharacterEngine


@pytest.fixture
def character_engine():
    """Create CharacterEngine instance for testing."""
    settings = Settings()
    logger = get_logger(__name__)
    return CharacterEngine(settings, logger)


@pytest.fixture
def sample_story_script():
    """Create sample story script for testing."""
    from app.models.schemas import NarrationLine

    return StoryScript(
        title="Test Story",
        logline="A test story",
        scenes=[
            Scene(
                scene_id=1,
                description="Scene 1",
                narration_lines=[NarrationLine(text="Narration", emotion="neutral", scene_id=1)],
                character_actions=[],
            )
        ],
    )


def test_generate_characters(character_engine, sample_story_script):
    """Test character generation creates unique characters."""
    character_set = character_engine.generate_characters(sample_story_script)

    assert len(character_set.characters) > 0
    assert character_set.narrator_id is not None

    # Check all characters have required fields
    for char in character_set.characters:
        assert char.id
        assert char.role
        assert char.name
        assert char.personality
        assert char.voice_profile

    # Check uniqueness
    character_ids = [char.id for char in character_set.characters]
    assert len(character_ids) == len(set(character_ids))  # All unique

    # Check narrator exists
    narrator = next((c for c in character_set.characters if c.id == character_set.narrator_id), None)
    assert narrator is not None
    assert narrator.role == "narrator"


def test_characters_unique_per_episode(character_engine, sample_story_script):
    """Test that characters are unique for each episode (no reuse)."""
    set1 = character_engine.generate_characters(sample_story_script)
    set2 = character_engine.generate_characters(sample_story_script)

    # Character IDs should be different (unique per episode)
    ids1 = {char.id for char in set1.characters}
    ids2 = {char.id for char in set2.characters}
    assert ids1.isdisjoint(ids2)  # No overlap

