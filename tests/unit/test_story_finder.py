"""Tests for Story Finder service."""

import pytest

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.services.story_finder import StoryFinder


@pytest.fixture
def story_finder():
    """Create StoryFinder instance for testing."""
    settings = Settings()
    logger = get_logger(__name__)
    return StoryFinder(settings, logger)


def test_find_candidates(story_finder):
    """Test finding candidates returns non-empty list."""
    topic = "courtroom drama"
    candidates = story_finder.find_candidates(topic)

    assert len(candidates) > 0
    assert all(c.title for c in candidates)
    assert all(c.raw_text for c in candidates)
    assert all(c.source_id for c in candidates)


def test_score_candidate(story_finder):
    """Test candidate scoring returns valid score."""
    from app.models.schemas import StoryCandidate

    candidate = StoryCandidate(
        source_id="test_1",
        title="Test Story Title",
        raw_text="A dramatic story with intense emotional moments and unexpected twists.",
        metadata={"engagement_score": 0.9},
    )

    score = story_finder.score_candidate(candidate)

    assert 0.0 <= score <= 1.0
    assert candidate.viral_score == score


def test_get_best_story(story_finder):
    """Test getting best story returns highest scored candidate."""
    topic = "teen laughs in court"
    best_story = story_finder.get_best_story(topic)

    assert best_story is not None
    assert best_story.title
    assert best_story.raw_text
    assert best_story.viral_score is not None
    assert 0.0 <= best_story.viral_score <= 1.0

