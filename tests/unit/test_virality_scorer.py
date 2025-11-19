"""Tests for ViralityScorer."""

import pytest

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import StoryCandidate, ViralityScore
from app.services.virality_scorer import ViralityScorer


@pytest.fixture
def settings():
    """Create test settings."""
    return Settings()


@pytest.fixture
def logger():
    """Create test logger."""
    return get_logger(__name__)


@pytest.fixture
def virality_scorer(settings, logger):
    """Create ViralityScorer instance."""
    return ViralityScorer(settings, logger)


@pytest.fixture
def sample_candidate():
    """Create a sample story candidate."""
    return StoryCandidate(
        id="test_candidate_1",
        source_id="test_candidate_1",
        title="Shocking Verdict in Courtroom Drama",
        raw_text="In a packed courtroom, the judge delivers a verdict that leaves everyone stunned. "
        "The defendant's reaction is completely unexpected, causing chaos in the gallery. "
        "This shocking turn of events has captured public attention.",
        source="stub_courtroom",
        niche="courtroom",
    )


def test_score_candidate_returns_virality_score(virality_scorer, sample_candidate):
    """Test that score_candidate returns a valid ViralityScore."""
    score = virality_scorer.score_candidate(sample_candidate)

    assert isinstance(score, ViralityScore)
    assert score.candidate_id == sample_candidate.id
    assert 0.0 <= score.overall_score <= 1.0
    assert 0.0 <= score.shock <= 1.0
    assert 0.0 <= score.rage <= 1.0
    assert 0.0 <= score.injustice <= 1.0
    assert 0.0 <= score.relatability <= 1.0
    assert 0.0 <= score.twist_strength <= 1.0
    assert 0.0 <= score.clarity <= 1.0


def test_score_candidate_high_shock_content(virality_scorer):
    """Test that high-shock content gets higher shock scores."""
    high_shock = StoryCandidate(
        id="high_shock",
        source_id="high_shock",
        title="Unexpected Verdict Shocks Everyone",
        raw_text="The verdict was shocking and unexpected. Everyone was stunned. "
        "The courtroom erupted in chaos. No one saw this coming.",
        source="stub",
        niche="courtroom",
    )

    low_shock = StoryCandidate(
        id="low_shock",
        source_id="low_shock",
        title="Regular Courtroom Proceeding",
        raw_text="The judge read the verdict. The defendant listened. The case concluded.",
        source="stub",
        niche="courtroom",
    )

    high_score = virality_scorer.score_candidate(high_shock)
    low_score = virality_scorer.score_candidate(low_shock)

    assert high_score.shock > low_score.shock


def test_rank_candidates_sorts_by_score(virality_scorer):
    """Test that rank_candidates sorts candidates by overall_score descending."""
    candidates = [
        StoryCandidate(
            id=f"candidate_{i}",
            source_id=f"candidate_{i}",
            title=f"Story {i}",
            raw_text="A regular story with moderate drama and some emotional content.",
            source="stub",
            niche="courtroom",
        )
        for i in range(3)
    ]

    # Make one candidate more viral
    candidates[1].raw_text = (
        "A shocking and unexpected verdict that leaves everyone stunned. "
        "The injustice is appalling and infuriating. This will trigger outrage."
    )

    ranked = virality_scorer.rank_candidates(candidates)

    assert len(ranked) == 3
    assert all(isinstance(score, ViralityScore) for _, score in ranked)

    # Check sorting (descending)
    scores = [score.overall_score for _, score in ranked]
    assert scores == sorted(scores, reverse=True)

    # The high-viral candidate should be first
    assert ranked[0][0].id == "candidate_1"


def test_rank_candidates_returns_all_candidates(virality_scorer):
    """Test that rank_candidates returns all input candidates."""
    candidates = [
        StoryCandidate(
            id=f"candidate_{i}",
            source_id=f"candidate_{i}",
            title=f"Story {i}",
            raw_text="A story with some drama.",
            source="stub",
            niche="courtroom",
        )
        for i in range(5)
    ]

    ranked = virality_scorer.rank_candidates(candidates)

    assert len(ranked) == 5
    ranked_ids = {candidate.id for candidate, _ in ranked}
    input_ids = {candidate.id for candidate in candidates}
    assert ranked_ids == input_ids


def test_score_candidate_handles_empty_text(virality_scorer):
    """Test that scorer handles edge cases like empty text."""
    candidate = StoryCandidate(
        id="empty",
        source_id="empty",
        title="Empty Story",
        raw_text="",
        source="stub",
        niche="courtroom",
    )

    score = virality_scorer.score_candidate(candidate)

    assert isinstance(score, ViralityScore)
    assert 0.0 <= score.overall_score <= 1.0
    # Clarity should be low for empty text
    assert score.clarity < 0.5

