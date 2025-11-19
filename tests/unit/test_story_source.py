"""Tests for StorySourceService."""

import pytest

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import StoryCandidate
from app.services.story_source import StorySourceService


@pytest.fixture
def settings():
    """Create test settings."""
    return Settings()


@pytest.fixture
def logger():
    """Create test logger."""
    return get_logger(__name__)


@pytest.fixture
def story_source(settings, logger):
    """Create StorySourceService instance."""
    return StorySourceService(settings, logger)


def test_generate_candidates_for_niche_returns_candidates(story_source):
    """Test that generate_candidates_for_niche returns the expected number of candidates."""
    candidates = story_source.generate_candidates_for_niche(niche="courtroom", num_candidates=5)

    assert len(candidates) == 5
    assert all(isinstance(c, StoryCandidate) for c in candidates)
    assert all(c.raw_text for c in candidates)
    assert all(c.title for c in candidates)
    assert all(c.id for c in candidates)
    assert all(c.niche == "courtroom" for c in candidates)


def test_generate_candidates_for_niche_different_niches(story_source):
    """Test that different niches return different candidates."""
    courtroom_candidates = story_source.generate_candidates_for_niche(niche="courtroom", num_candidates=3)
    relationship_candidates = story_source.generate_candidates_for_niche(niche="relationship_drama", num_candidates=3)

    assert len(courtroom_candidates) == 3
    assert len(relationship_candidates) == 3

    # Titles should be different
    courtroom_titles = {c.title for c in courtroom_candidates}
    relationship_titles = {c.title for c in relationship_candidates}
    assert courtroom_titles != relationship_titles


def test_generate_candidates_from_topic(story_source):
    """Test generating candidates from a specific topic."""
    candidates = story_source.generate_candidates_from_topic(
        topic="teen laughs in court", niche="courtroom", num_candidates=3
    )

    assert len(candidates) == 3
    assert all(isinstance(c, StoryCandidate) for c in candidates)
    assert all(c.raw_text for c in candidates)
    assert all("teen" in c.raw_text.lower() or "court" in c.raw_text.lower() for c in candidates)


def test_candidate_has_required_fields(story_source):
    """Test that each candidate has all required fields."""
    candidates = story_source.generate_candidates_for_niche(niche="injustice", num_candidates=1)

    assert len(candidates) == 1
    candidate = candidates[0]

    assert candidate.id
    assert candidate.title
    assert candidate.raw_text
    assert candidate.source
    assert candidate.niche == "injustice"
    assert isinstance(candidate.metadata, dict)


def test_generate_candidates_handles_unknown_niche(story_source):
    """Test that unknown niches fall back to default."""
    candidates = story_source.generate_candidates_for_niche(niche="unknown_niche", num_candidates=2)

    assert len(candidates) == 2
    # Should fall back to courtroom templates
    assert all(c.raw_text for c in candidates)

