"""Optimisation Engine - selects optimal video plans based on performance data."""

import random
from collections import defaultdict
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.schemas import EpisodeMetadata, VideoPlan


class PlannedVideo(BaseModel):
    """A planned video with metadata for batch generation."""

    niche: str = Field(..., description="Story niche (e.g., 'courtroom', 'relationship_drama')")
    style: str = Field(..., description="Story style (e.g., 'courtroom_drama', 'ragebait')")
    pattern_type: str = Field(..., description="Story pattern type")
    primary_emotion: str = Field(..., description="Primary emotion of the story")
    secondary_emotion: Optional[str] = Field(default=None, description="Secondary emotion if applicable")
    topic_hint: Optional[str] = Field(default=None, description="Optional topic hint for story generation")


class OptimisationEngine:
    """Engine for optimizing video batch selection based on historical performance."""

    def __init__(self, settings: Any, repository: Any, logger: Any):
        """
        Initialize the optimisation engine.

        Args:
            settings: Application settings
            repository: Episode repository for loading historical data
            logger: Logger instance
        """
        self.settings = settings
        self.repository = repository
        self.logger = logger

    def select_batch_plan(self, batch_count: int, fallback_niche: Optional[str] = None) -> list[PlannedVideo]:
        """
        Select optimal batch plan based on historical performance data.

        Args:
            batch_count: Number of videos to plan
            fallback_niche: Default niche to use if no data available (defaults to 'courtroom')

        Returns:
            List of PlannedVideo objects
        """
        self.logger.info(f"Selecting batch plan for {batch_count} videos...")

        # Load recent episodes
        recent_episodes = self._load_recent_episodes(limit=100)
        self.logger.info(f"Loaded {len(recent_episodes)} recent episodes")

        # Check if we have performance data
        episodes_with_performance = [
            ep for ep in recent_episodes
            if ep.metadata and ep.metadata.views_24h is not None
        ]

        if not episodes_with_performance:
            # No performance data - return simple mix
            self.logger.info("No performance data available, using simple mix strategy")
            return self._generate_simple_mix(batch_count, fallback_niche or "courtroom")
        else:
            # Performance data exists - use optimization strategy
            self.logger.info(f"Found {len(episodes_with_performance)} episodes with performance data")
            return self._generate_optimized_plan(episodes_with_performance, batch_count, fallback_niche)

    def _load_recent_episodes(self, limit: int = 100) -> list[VideoPlan]:
        """
        Load recent episodes from repository.

        Args:
            limit: Maximum number of episodes to load

        Returns:
            List of VideoPlan objects, sorted by most recent first
        """
        episode_ids = self.repository.list_episodes()
        
        # Load episodes (limit to most recent)
        episodes = []
        for episode_id in episode_ids[:limit]:
            episode = self.repository.load_episode(episode_id)
            if episode:
                episodes.append(episode)

        # Sort by created_at if available (most recent first)
        episodes.sort(
            key=lambda ep: ep.created_at or "",
            reverse=True
        )

        return episodes

    def _generate_simple_mix(self, batch_count: int, default_niche: str) -> list[PlannedVideo]:
        """
        Generate a simple mix of niches and emotions when no performance data is available.

        Args:
            batch_count: Number of videos to plan
            default_niche: Default niche to use

        Returns:
            List of PlannedVideo objects
        """
        # Simple mix strategy: rotate through common niches and emotions
        niches = ["courtroom", "relationship_drama", "injustice"]
        styles = ["courtroom_drama", "ragebait", "relationship_drama"]
        pattern_types = ["ragebait", "karma", "twist", "redemption"]
        primary_emotions = ["anger", "shock", "sadness", "satisfaction"]
        secondary_emotions = ["disgust", "fear", "hope", None]

        planned = []
        for i in range(batch_count):
            planned.append(PlannedVideo(
                niche=niches[i % len(niches)] if default_niche not in niches else default_niche,
                style=styles[i % len(styles)],
                pattern_type=pattern_types[i % len(pattern_types)],
                primary_emotion=primary_emotions[i % len(primary_emotions)],
                secondary_emotion=secondary_emotions[i % len(secondary_emotions)],
                topic_hint=None
            ))

        self.logger.info(f"Generated simple mix: {len(planned)} planned videos")
        return planned

    def _generate_optimized_plan(
        self,
        episodes_with_performance: list[VideoPlan],
        batch_count: int,
        fallback_niche: Optional[str]
    ) -> list[PlannedVideo]:
        """
        Generate optimized plan based on historical performance.

        Groups episodes by (niche, pattern_type, primary_emotion) and scores them
        by views_24h or engagement metrics, then samples proportionally.

        Args:
            episodes_with_performance: List of episodes with performance data
            batch_count: Number of videos to plan
            fallback_niche: Fallback niche if needed

        Returns:
            List of PlannedVideo objects
        """
        # Group episodes by (niche, pattern_type, primary_emotion)
        groups = defaultdict(list)
        
        for episode in episodes_with_performance:
            if not episode.metadata:
                continue
            
            key = (
                episode.metadata.niche,
                episode.metadata.pattern_type,
                episode.metadata.primary_emotion
            )
            groups[key].append(episode)

        self.logger.info(f"Grouped into {len(groups)} unique combinations")

        # Score each group
        group_scores = {}
        for key, group_episodes in groups.items():
            # Calculate average performance score
            scores = []
            for ep in group_episodes:
                if not ep.metadata:
                    continue
                
                # Use views_24h as primary metric, fallback to engagement if available
                if ep.metadata.views_24h is not None:
                    # Normalize views (assume max 100k for scoring)
                    view_score = min(ep.metadata.views_24h / 100000.0, 1.0)
                    
                    # Add engagement bonus if available
                    engagement_bonus = 0.0
                    if ep.metadata.likes_24h:
                        engagement_bonus += (ep.metadata.likes_24h / ep.metadata.views_24h) * 0.1 if ep.metadata.views_24h > 0 else 0.0
                    if ep.metadata.comments_24h:
                        engagement_bonus += (ep.metadata.comments_24h / ep.metadata.views_24h) * 0.1 if ep.metadata.views_24h > 0 else 0.0
                    
                    scores.append(view_score + engagement_bonus)
            
            if scores:
                group_scores[key] = sum(scores) / len(scores)
            else:
                group_scores[key] = 0.0

        # Normalize scores to probabilities
        total_score = sum(group_scores.values())
        if total_score == 0:
            # No scores available, fall back to simple mix
            self.logger.warning("All group scores are zero, falling back to simple mix")
            return self._generate_simple_mix(batch_count, fallback_niche or "courtroom")

        group_probs = {key: score / total_score for key, score in group_scores.items()}

        # Sample proportionally to scores
        planned = []
        keys = list(group_probs.keys())
        probs = list(group_probs.values())

        for _ in range(batch_count):
            # Sample a group based on probabilities
            selected_key = random.choices(keys, weights=probs, k=1)[0]
            niche, pattern_type, primary_emotion = selected_key

            # Get a representative episode from this group for additional metadata
            representative = groups[selected_key][0]
            metadata = representative.metadata if representative.metadata else None

            planned.append(PlannedVideo(
                niche=niche,
                style=metadata.style if metadata else (fallback_niche or "courtroom") + "_drama",
                pattern_type=pattern_type,
                primary_emotion=primary_emotion,
                secondary_emotion=metadata.secondary_emotion if metadata else None,
                topic_hint=None  # Could be extracted from representative episode if needed
            ))

        self.logger.info(f"Generated optimized plan: {len(planned)} planned videos")
        self.logger.debug(f"Sample planned videos: {[f'{p.niche}/{p.pattern_type}/{p.primary_emotion}' for p in planned[:3]]}")
        
        return planned

