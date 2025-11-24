"""Tests for Story Rewriter service."""

import pytest

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.services.story_rewriter import StoryRewriter


@pytest.fixture
def story_rewriter():
    """Create StoryRewriter instance for testing."""
    settings = Settings()
    logger = get_logger(__name__)
    return StoryRewriter(settings, logger)


def test_rewrite_story(story_rewriter):
    """Test story rewriting creates valid script structure."""
    raw_text = "In a dramatic courtroom scene, a teenager sits nervously. The judge reads the verdict. Unexpectedly, the teen bursts into laughter, shocking everyone present."
    title = "Teen Laughs in Court"
    duration = 60

    script, pattern_type = story_rewriter.rewrite_story(raw_text, title, duration)

    assert script.title == title
    assert script.logline
    assert len(script.scenes) >= 2
    assert len(script.scenes) <= 4

    # Check scenes have required fields
    for scene in script.scenes:
        assert scene.scene_id > 0
        assert scene.description
        assert len(scene.narration_lines) > 0
        assert all(nl.text for nl in scene.narration_lines)
        assert all(nl.scene_id == scene.scene_id for nl in scene.narration_lines)


def test_rewrite_story_scene_count(story_rewriter):
    """Test scene count scales with duration."""
    raw_text = "A test story with enough content to be split into multiple scenes."
    title = "Test Story"

    # Short duration should produce fewer scenes
    short_script, _ = story_rewriter.rewrite_story(raw_text, title, 45)
    # Longer duration should produce more scenes
    long_script, _ = story_rewriter.rewrite_story(raw_text, title, 90)

    assert len(short_script.scenes) <= len(long_script.scenes)

