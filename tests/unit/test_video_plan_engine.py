"""Tests for Video Plan Engine service."""

import pytest

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import CharacterSet, DialoguePlan, NarrationPlan, Scene, StoryScript
from app.services.video_plan_engine import VideoPlanEngine


@pytest.fixture
def video_plan_engine():
    """Create VideoPlanEngine instance for testing."""
    settings = Settings()
    logger = get_logger(__name__)
    return VideoPlanEngine(settings, logger)


@pytest.fixture
def sample_story_script():
    """Create sample story script."""
    from app.models.schemas import NarrationLine

    return StoryScript(
        title="Test Story",
        logline="A test story",
        scenes=[
            Scene(
                scene_id=1,
                description="Scene 1 description",
                narration_lines=[NarrationLine(text="Narration 1", emotion="neutral", scene_id=1)],
                character_actions=[],
            ),
            Scene(
                scene_id=2,
                description="Scene 2 description",
                narration_lines=[NarrationLine(text="Narration 2", emotion="dramatic", scene_id=2)],
                character_actions=[],
            ),
        ],
    )


@pytest.fixture
def sample_character_set():
    """Create sample character set."""
    from app.models.schemas import Character

    return CharacterSet(
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
        narrator_id=None,
    )


@pytest.fixture
def sample_dialogue_plan():
    """Create sample dialogue plan."""
    from app.models.schemas import DialogueLine

    return DialoguePlan(
        lines=[
            DialogueLine(
                character_id="char_1",
                text="Test dialogue",
                emotion="neutral",
                scene_id=1,
                approx_timing_hint=5.0,
            )
        ]
    )


@pytest.fixture
def sample_narration_plan():
    """Create sample narration plan."""
    from app.models.schemas import NarrationLine

    return NarrationPlan(
        lines=[
            NarrationLine(text="Narration 1", emotion="neutral", scene_id=1),
            NarrationLine(text="Narration 2", emotion="dramatic", scene_id=2),
        ]
    )


def test_create_video_plan(
    video_plan_engine,
    sample_story_script,
    sample_character_set,
    sample_dialogue_plan,
    sample_narration_plan,
):
    """Test video plan creation produces valid structure."""
    episode_id = "test_episode_123"
    topic = "test topic"
    duration = 60

    video_plan = video_plan_engine.create_video_plan(
        episode_id=episode_id,
        topic=topic,
        story_script=sample_story_script,
        character_set=sample_character_set,
        dialogue_plan=sample_dialogue_plan,
        narration_plan=sample_narration_plan,
        duration_seconds=duration,
    )

    # Check metadata
    assert video_plan.episode_id == episode_id
    assert video_plan.topic == topic
    assert video_plan.duration_target_seconds == duration
    assert video_plan.title == sample_story_script.title
    assert video_plan.logline == sample_story_script.logline

    # Check scenes
    assert len(video_plan.scenes) == len(sample_story_script.scenes)
    for scene in video_plan.scenes:
        assert scene.scene_id > 0
        assert scene.description
        assert scene.background_prompt
        assert scene.camera_style
        assert isinstance(scene.b_roll_prompts, list)

    # Check characters
    assert len(video_plan.characters) == len(sample_character_set.characters)

    # Check schema correctness (can be serialized)
    plan_dict = video_plan.model_dump()
    assert "episode_id" in plan_dict
    assert "scenes" in plan_dict
    assert "characters" in plan_dict

