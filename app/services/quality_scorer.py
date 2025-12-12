"""Quality Scorer - computes quality scores for episodes."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import EpisodeMetadata, VideoPlan


class QualityScorer:
    """Computes quality scores for episodes based on visual, content, and technical metrics."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize quality scorer.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger
        self.metrics_file = Path(settings.storage_path) / "quality_metrics.jsonl"
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

    def compute_quality_scores(
        self,
        video_plan: VideoPlan,
        episode_metadata: Optional[EpisodeMetadata] = None,
        image_scores: Optional[list[float]] = None,
        content_metrics: Optional[dict] = None,
    ) -> dict:
        """
        Compute quality scores for an episode.

        Args:
            video_plan: VideoPlan with episode content
            episode_metadata: Optional EpisodeMetadata
            image_scores: Optional list of image quality scores (from ImageQualityValidator)
            content_metrics: Optional dict with additional content metrics

        Returns:
            Dictionary with scores:
            {
                "visual_score": float (0-100),
                "content_score": float (0-100),
                "technical_score": float (0-100),
                "overall_score": float (0-100),
            }
        """
        metadata = episode_metadata or video_plan.metadata

        # Visual Score (0-100)
        visual_score = self._compute_visual_score(image_scores)

        # Content Score (0-100)
        content_score = self._compute_content_score(video_plan, metadata)

        # Technical Score (0-100)
        technical_score = self._compute_technical_score(video_plan, metadata)

        # Overall Score (weighted average)
        overall_score = (
            visual_score * 0.3 + content_score * 0.4 + technical_score * 0.3
        )

        scores = {
            "visual_score": round(visual_score, 2),
            "content_score": round(content_score, 2),
            "technical_score": round(technical_score, 2),
            "overall_score": round(overall_score, 2),
        }

        self.logger.debug(f"Quality scores computed: {scores}")
        return scores

    def _compute_visual_score(self, image_scores: Optional[list[float]]) -> float:
        """
        Compute visual quality score based on image quality validator scores.

        Args:
            image_scores: List of image quality scores (0.0-1.0 from ImageQualityValidator)

        Returns:
            Visual score (0-100)
        """
        if not image_scores or len(image_scores) == 0:
            # No image scores available - assume moderate quality
            return 70.0

        avg_score = sum(image_scores) / len(image_scores)
        # Convert from 0.0-1.0 scale to 0-100 scale
        visual_score = avg_score * 100

        # Bonus for high average (>0.8) or penalty for low average (<0.6)
        if avg_score >= 0.8:
            visual_score = min(100, visual_score * 1.1)  # 10% bonus
        elif avg_score < 0.6:
            visual_score = max(0, visual_score * 0.9)  # 10% penalty

        return visual_score

    def _compute_content_score(
        self, video_plan: VideoPlan, metadata: Optional[EpisodeMetadata]
    ) -> float:
        """
        Compute content quality score based on dialogue variety, characters, beats.

        Args:
            video_plan: VideoPlan with content
            metadata: Optional EpisodeMetadata

        Returns:
            Content score (0-100)
        """
        score = 0.0
        max_score = 100.0

        # Dialogue length variety (0-25 points)
        dialogue_lines = video_plan.character_spoken_lines
        if dialogue_lines:
            line_lengths = [len(line.line_text.split()) for line in dialogue_lines]
            if len(line_lengths) > 1:
                # Calculate coefficient of variation (std/mean)
                mean_length = sum(line_lengths) / len(line_lengths)
                variance = sum((x - mean_length) ** 2 for x in line_lengths) / len(line_lengths)
                std_dev = variance ** 0.5
                if mean_length > 0:
                    cv = std_dev / mean_length
                    # Higher variety (CV) = better score, capped at 25
                    variety_score = min(25, cv * 20)
                    score += variety_score
            else:
                score += 15  # Single line gets moderate score
        else:
            score += 10  # No dialogue gets low score

        # Number of unique characters speaking (0-25 points)
        if dialogue_lines:
            unique_characters = len(set(line.character_id for line in dialogue_lines))
            # 1 character = 10 points, 2 = 20, 3+ = 25
            character_score = min(25, unique_characters * 10)
            score += character_score
        else:
            score += 5  # No characters speaking

        # Presence of twist and resolution beats (0-30 points)
        if metadata:
            if metadata.has_twist:
                score += 15
            if metadata.has_cta:  # CTA often indicates resolution
                score += 15
        else:
            # Check scenes for twist/resolution indicators
            scene_descriptions = " ".join([s.description.lower() for s in video_plan.scenes])
            if "twist" in scene_descriptions or "shocking" in scene_descriptions:
                score += 15
            if "resolution" in scene_descriptions or "conclusion" in scene_descriptions:
                score += 15

        # Dialogue quality (presence of character spoken lines) (0-20 points)
        if len(dialogue_lines) >= 2:
            score += 20
        elif len(dialogue_lines) == 1:
            score += 10
        else:
            score += 5

        return min(max_score, score)

    def _compute_technical_score(
        self, video_plan: VideoPlan, metadata: Optional[EpisodeMetadata]
    ) -> float:
        """
        Compute technical quality score based on generation success and duration accuracy.

        Args:
            video_plan: VideoPlan with technical info
            metadata: Optional EpisodeMetadata

        Returns:
            Technical score (0-100)
        """
        score = 100.0  # Start with perfect score, deduct for issues

        # Duration accuracy (0-50 points)
        if metadata and metadata.video_duration_sec and video_plan.duration_target_seconds:
            actual_duration = metadata.video_duration_sec
            target_duration = video_plan.duration_target_seconds
            duration_diff = abs(actual_duration - target_duration)
            duration_ratio = duration_diff / target_duration

            # Perfect match (within 2%) = 50 points
            # 10% off = 40 points, 20% off = 30 points, etc.
            if duration_ratio <= 0.02:
                duration_score = 50
            elif duration_ratio <= 0.10:
                duration_score = 50 - (duration_ratio - 0.02) * 125  # Linear decay
            elif duration_ratio <= 0.20:
                duration_score = 40 - (duration_ratio - 0.10) * 100
            else:
                duration_score = max(0, 30 - (duration_ratio - 0.20) * 150)

            score = score - 50 + duration_score  # Replace base score with duration score
        else:
            # No duration data - assume moderate accuracy
            score = score - 50 + 35

        # Generation success indicators (0-50 points)
        # Check for presence of key components
        has_characters = len(video_plan.characters) > 0
        has_scenes = len(video_plan.scenes) > 0
        has_narration = any(len(scene.narration) > 0 for scene in video_plan.scenes)

        if has_characters and has_scenes and has_narration:
            score += 50  # All components present
        elif has_characters and has_scenes:
            score += 40  # Missing narration
        elif has_scenes:
            score += 30  # Missing characters
        else:
            score += 10  # Minimal content

        return min(100.0, max(0.0, score))

    def log_quality_metrics(
        self,
        episode_id: str,
        scores: dict,
        video_plan: VideoPlan,
        metadata: Optional[EpisodeMetadata] = None,
    ) -> None:
        """
        Log quality metrics to JSONL file.

        Args:
            episode_id: Episode ID
            scores: Quality scores dict
            video_plan: VideoPlan for additional metrics
            metadata: Optional EpisodeMetadata
        """
        try:
            metadata = metadata or video_plan.metadata

            # Collect additional metrics
            n_images = (
                len(video_plan.b_roll_scenes) + len(video_plan.scenes)
                if video_plan.b_roll_scenes or video_plan.scenes
                else 0
            )
            n_dialogue_lines = len(video_plan.character_spoken_lines)
            duration_seconds = (
                metadata.video_duration_sec if metadata and metadata.video_duration_sec else None
            )

            metric_entry = {
                "episode_id": episode_id,
                "timestamp": datetime.now().isoformat(),
                "visual_score": scores.get("visual_score", 0),
                "content_score": scores.get("content_score", 0),
                "technical_score": scores.get("technical_score", 0),
                "overall_score": scores.get("overall_score", 0),
                "duration_seconds": duration_seconds,
                "n_images": n_images,
                "n_dialogue_lines": n_dialogue_lines,
                "n_characters": len(video_plan.characters),
                "n_scenes": len(video_plan.scenes),
                "has_twist": metadata.has_twist if metadata else False,
                "has_cta": metadata.has_cta if metadata else False,
            }

            # Append to JSONL file
            with open(self.metrics_file, "a") as f:
                f.write(json.dumps(metric_entry) + "\n")

            self.logger.info(f"Quality metrics logged: overall_score={scores.get('overall_score', 0):.2f}")

        except Exception as e:
            # Non-critical: log warning but don't fail
            self.logger.warning(f"Failed to log quality metrics (non-critical): {e}")

