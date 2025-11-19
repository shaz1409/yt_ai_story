"""Tests for storage repository."""

import pytest
from pathlib import Path

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import Character, CharacterSet, VideoPlan, VideoScene
from app.storage.repository import EpisodeRepository


@pytest.fixture
def temp_storage_path(tmp_path):
    """Create temporary storage path."""
    return tmp_path / "test_storage"


@pytest.fixture
def repository(temp_storage_path):
    """Create repository with temp storage."""
    settings = Settings()
    settings.storage_path = str(temp_storage_path)
    logger = get_logger(__name__)
    return EpisodeRepository(settings, logger)


@pytest.fixture
def sample_video_plan():
    """Create sample video plan for testing."""
    return VideoPlan(
        episode_id="test_episode_1",
        topic="test topic",
        duration_target_seconds=60,
        style="courtroom_drama",
        title="Test Story",
        logline="A test story",
        characters=[
            Character(
                id="char_1",
                role="judge",
                name="Judge Test",
                appearance={},
                personality="authoritative",
                voice_profile="deep",
            )
        ],
        scenes=[
            VideoScene(
                scene_id=1,
                description="Scene 1",
                background_prompt="A courtroom",
                camera_style="wide_shot",
                narration=[],
                dialogue=[],
                b_roll_prompts=[],
            )
        ],
    )


def test_save_episode(repository, sample_video_plan, temp_storage_path):
    """Test saving episode creates file."""
    repository.save_episode(sample_video_plan)

    file_path = temp_storage_path / f"{sample_video_plan.episode_id}.json"
    assert file_path.exists()


def test_load_episode(repository, sample_video_plan):
    """Test loading episode returns correct data."""
    repository.save_episode(sample_video_plan)

    loaded_plan = repository.load_episode(sample_video_plan.episode_id)

    assert loaded_plan is not None
    assert loaded_plan.episode_id == sample_video_plan.episode_id
    assert loaded_plan.title == sample_video_plan.title
    assert len(loaded_plan.scenes) == len(sample_video_plan.scenes)
    assert len(loaded_plan.characters) == len(sample_video_plan.characters)


def test_load_nonexistent_episode(repository):
    """Test loading non-existent episode returns None."""
    loaded = repository.load_episode("nonexistent_episode")
    assert loaded is None


def test_list_episodes(repository, sample_video_plan):
    """Test listing episodes returns all episode IDs."""
    repository.save_episode(sample_video_plan)

    episodes = repository.list_episodes()

    assert len(episodes) > 0
    assert sample_video_plan.episode_id in episodes

