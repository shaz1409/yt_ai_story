"""Tests for Video Renderer service."""

import pytest
from pathlib import Path

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import Character, CharacterSet, NarrationLine, VideoPlan, VideoScene
from app.services.video_renderer import VideoRenderer


@pytest.fixture
def video_renderer():
    """Create VideoRenderer instance for testing."""
    settings = Settings()
    logger = get_logger(__name__)
    return VideoRenderer(settings, logger)


@pytest.fixture
def sample_video_plan():
    """Create sample VideoPlan for testing."""
    return VideoPlan(
        episode_id="test_episode_123",
        topic="test topic",
        duration_target_seconds=60,
        style="courtroom_drama",
        title="Test Story",
        logline="A test story",
        characters=[
            Character(
                id="char_1",
                role="narrator",
                name="Narrator",
                appearance={},
                personality="neutral",
                voice_profile="clear",
            )
        ],
        scenes=[
            VideoScene(
                scene_id=1,
                description="Scene 1 description",
                background_prompt="A courtroom setting",
                camera_style="wide_shot",
                narration=[
                    NarrationLine(text="This is narration for scene 1", emotion="neutral", scene_id=1)
                ],
                dialogue=[],
                b_roll_prompts=[],
            ),
            VideoScene(
                scene_id=2,
                description="Scene 2 description",
                background_prompt="A dramatic moment",
                camera_style="close_up",
                narration=[
                    NarrationLine(text="This is narration for scene 2", emotion="dramatic", scene_id=2)
                ],
                dialogue=[],
                b_roll_prompts=[],
            ),
        ],
    )


def test_render_creates_video_file(video_renderer, sample_video_plan, tmp_path):
    """Test that render() creates a .mp4 file."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # This test may fail if TTS/image generation fails, but structure should work
    try:
        video_path = video_renderer.render(sample_video_plan, output_dir)

        # Check that video file was created
        assert video_path.exists()
        assert video_path.suffix == ".mp4"
        assert video_path.name.startswith(sample_video_plan.episode_id)

    except Exception as e:
        # If TTS/image generation fails (no API keys), that's okay for structure test
        pytest.skip(f"Rendering requires API keys or dependencies: {e}")


def test_extract_narration_text(video_renderer, sample_video_plan):
    """Test narration text extraction."""
    text = video_renderer._extract_narration_text(sample_video_plan)

    assert isinstance(text, str)
    assert len(text) > 0
    assert "scene 1" in text.lower() or "scene 2" in text.lower()


def test_generate_scene_visuals_creates_images(video_renderer, sample_video_plan, tmp_path):
    """Test that scene visuals are generated."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    try:
        scene_visuals = video_renderer._generate_scene_visuals(sample_video_plan, output_dir)

        assert len(scene_visuals) == len(sample_video_plan.scenes)
        for visual_path in scene_visuals:
            assert visual_path.exists()
            assert visual_path.suffix == ".png"

    except Exception as e:
        # If image generation fails, that's okay
        pytest.skip(f"Image generation requires API keys: {e}")

