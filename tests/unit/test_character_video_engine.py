"""Tests for CharacterVideoEngine."""

import pytest
from pathlib import Path

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import Character, DialogueLine
from app.services.character_video_engine import CharacterVideoEngine


@pytest.fixture
def settings():
    """Create test settings."""
    return Settings()


@pytest.fixture
def logger():
    """Create test logger."""
    return get_logger(__name__)


@pytest.fixture
def character_video_engine(settings, logger):
    """Create CharacterVideoEngine instance."""
    return CharacterVideoEngine(settings, logger)


@pytest.fixture
def sample_character():
    """Create a sample character."""
    return Character(
        id="char_judge_1",
        role="judge",
        name="Judge Williams",
        appearance={"age": "middle-aged", "gender": "male", "hair": "gray"},
        personality="authoritative and stern",
        voice_profile="deep male",
    )


@pytest.fixture
def sample_dialogue_line():
    """Create a sample dialogue line."""
    return DialogueLine(
        character_id="char_judge_1",
        text="I find you guilty as charged.",
        emotion="stern",
        scene_id=3,
        approx_timing_hint=5.0,
    )


def test_generate_character_face_image_creates_file(character_video_engine, sample_character, tmp_path):
    """Test that generate_character_face_image creates an image file."""
    output_dir = tmp_path / "character_faces"
    image_path = character_video_engine.generate_character_face_image(
        sample_character, output_dir, style="courtroom_drama"
    )

    assert image_path.exists()
    assert image_path.suffix == ".png"
    assert output_dir.exists()


def test_generate_talking_head_clip_creates_file(
    character_video_engine, sample_character, sample_dialogue_line, tmp_path
):
    """Test that generate_talking_head_clip creates a video file."""
    # Create a dummy audio file
    audio_path = tmp_path / "test_audio.mp3"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create minimal audio file (using pydub if available, or skip test)
    try:
        from pydub import AudioSegment
        silent_audio = AudioSegment.silent(duration=2000)  # 2 seconds
        silent_audio.export(str(audio_path), format="mp3")
    except ImportError:
        pytest.skip("pydub not available for creating test audio")

    output_dir = tmp_path / "talking_heads"
    clip_path = character_video_engine.generate_talking_head_clip(
        sample_character, sample_dialogue_line, audio_path, output_dir, style="courtroom_drama"
    )

    # The clip should be created (even if it's a stub)
    assert clip_path.exists()
    assert clip_path.suffix == ".mp4"


def test_ensure_character_assets_creates_images(character_video_engine, tmp_path):
    """Test that ensure_character_assets generates face images for characters."""
    from app.models.schemas import VideoPlan, VideoScene, NarrationLine

    # Create a minimal VideoPlan
    characters = [
        Character(
            id="char_1",
            role="judge",
            name="Judge",
            appearance={},
            personality="stern",
            voice_profile="deep male",
        ),
        Character(
            id="char_2",
            role="defendant",
            name="Defendant",
            appearance={},
            personality="nervous",
            voice_profile="young male",
        ),
    ]

    video_plan = VideoPlan(
        episode_id="test_episode",
        topic="test topic",
        duration_target_seconds=60,
        style="courtroom_drama",
        title="Test Episode",
        logline="A test story",
        characters=characters,
        scenes=[
            VideoScene(
                scene_id=1,
                description="Test scene",
                background_prompt="courtroom",
                narration=[NarrationLine(text="Test narration", emotion="neutral")],
            )
        ],
    )

    output_dir = tmp_path / "assets"
    character_assets = character_video_engine.ensure_character_assets(video_plan, output_dir, "courtroom_drama")

    # Should have generated assets for non-narrator characters
    assert len(character_assets) == 2  # Both characters
    assert all(path.exists() for path in character_assets.values())


def test_character_face_prompt_includes_role(character_video_engine, sample_character):
    """Test that character face prompt includes role information."""
    prompt = character_video_engine._build_character_face_prompt(sample_character, "courtroom_drama")

    assert "judge" in prompt.lower() or "authoritative" in prompt.lower()
    assert "photorealistic" in prompt.lower() or "realistic" in prompt.lower()
    assert "courtroom" in prompt.lower() or "legal" in prompt.lower()


def test_talking_head_provider_handles_missing_audio(character_video_engine, tmp_path):
    """Test that talking-head provider handles missing audio gracefully."""
    from app.services.character_video_engine import TalkingHeadProvider

    provider = TalkingHeadProvider(character_video_engine.settings, character_video_engine.logger)

    # Create a dummy image
    image_path = tmp_path / "test_image.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    from PIL import Image
    Image.new("RGB", (1080, 1920), color=(0, 0, 0)).save(image_path)

    # Non-existent audio should raise an error
    audio_path = tmp_path / "nonexistent.mp3"
    output_path = tmp_path / "output.mp4"

    with pytest.raises(Exception):
        provider.generate_talking_head(image_path, audio_path, output_path)

