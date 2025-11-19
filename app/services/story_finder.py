"""Story Finder service - finds and ranks story candidates."""

import uuid
from typing import Any

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import StoryCandidate


class StoryFinder:
    """Finds and selects story candidates with high viral potential."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize the story finder.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger

    def find_candidates(self, topic: str) -> list[StoryCandidate]:
        """
        Find story candidates matching the topic.

        For now, this is a stub that simulates finding candidates.
        In production, this would:
        - Scrape news sites, Reddit, social media
        - Query databases
        - Use LLM to generate variations

        Args:
            topic: Story topic to search for

        Returns:
            List of story candidates
        """
        self.logger.info(f"Finding candidates for topic: {topic}")

        # Stub implementation: Generate mock candidates
        # In production, replace with actual scraping/LLM calls
        candidates = [
            StoryCandidate(
                id=f"source_{uuid.uuid4().hex[:8]}",
                source_id=f"source_{uuid.uuid4().hex[:8]}",
                title=f"{topic} - Breaking News",
                raw_text=f"In a dramatic turn of events related to {topic}, the situation unfolded with unexpected consequences. "
                f"Witnesses described the scene as intense and emotional. The story has captured public attention "
                f"due to its compelling narrative and dramatic elements.",
                source="stub",
                niche="courtroom",
                source_type="scraped",
                metadata={"category": "drama", "engagement_score": 0.85},
            ),
            StoryCandidate(
                id=f"source_{uuid.uuid4().hex[:8]}",
                source_id=f"source_{uuid.uuid4().hex[:8]}",
                title=f"{topic} - Viral Moment",
                raw_text=f"The viral moment involving {topic} has sparked widespread discussion. "
                f"Social media users have been sharing their reactions, creating a wave of engagement. "
                f"The emotional impact of this story makes it highly shareable.",
                source="stub",
                niche="courtroom",
                source_type="scraped",
                metadata={"category": "viral", "engagement_score": 0.92},
            ),
            StoryCandidate(
                id=f"source_{uuid.uuid4().hex[:8]}",
                source_id=f"source_{uuid.uuid4().hex[:8]}",
                title=f"{topic} - Deep Dive",
                raw_text=f"A comprehensive look at {topic} reveals multiple layers of complexity. "
                f"The story involves multiple characters and dramatic tension that builds throughout. "
                f"This narrative structure is ideal for short-form video content.",
                source="stub",
                niche="courtroom",
                source_type="scraped",
                metadata={"category": "drama", "engagement_score": 0.78},
            ),
        ]

        self.logger.info(f"Found {len(candidates)} candidates")
        return candidates

    def score_candidate(self, candidate: StoryCandidate) -> float:
        """
        Score a candidate for viral potential.

        Scoring factors:
        - Emotional impact
        - Dramatic tension
        - Character count
        - Narrative structure
        - Engagement metrics (if available)

        Args:
            candidate: Story candidate to score

        Returns:
            Viral score (0.0 to 1.0)
        """
        self.logger.debug(f"Scoring candidate: {candidate.title}")

        score = 0.5  # Base score

        # Factor 1: Engagement score from metadata
        if "engagement_score" in candidate.metadata:
            score += candidate.metadata["engagement_score"] * 0.3

        # Factor 2: Text length (optimal range)
        text_length = len(candidate.raw_text)
        if 200 <= text_length <= 800:
            score += 0.2
        elif text_length < 200:
            score += 0.1

        # Factor 3: Emotional keywords
        emotional_keywords = ["dramatic", "intense", "emotional", "shocking", "unexpected", "viral"]
        keyword_count = sum(1 for keyword in emotional_keywords if keyword.lower() in candidate.raw_text.lower())
        score += min(keyword_count * 0.05, 0.2)

        # Factor 4: Title quality
        if len(candidate.title) > 20:
            score += 0.1

        # Normalize to 0.0-1.0
        score = min(score, 1.0)
        candidate.viral_score = score

        self.logger.debug(f"Candidate '{candidate.title}' scored: {score:.2f}")
        return score

    def get_best_story(self, topic: str) -> StoryCandidate:
        """
        Find candidates and return the best one.

        Args:
            topic: Story topic

        Returns:
            Best story candidate
        """
        self.logger.info(f"Getting best story for topic: {topic}")

        candidates = self.find_candidates(topic)

        if not candidates:
            raise ValueError(f"No candidates found for topic: {topic}")

        # Score all candidates
        scored_candidates = [(self.score_candidate(c), c) for c in candidates]

        # Sort by score (descending)
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        best_candidate = scored_candidates[0][1]
        self.logger.info(f"Selected best candidate: {best_candidate.title} (score: {best_candidate.viral_score:.2f})")

        return best_candidate

