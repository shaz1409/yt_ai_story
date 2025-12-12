"""Analytics Service - tracks video performance and engagement metrics."""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.config import Settings
from app.core.logging_config import get_logger


class AnalyticsService:
    """Tracks video performance metrics from YouTube and other sources."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize analytics service.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger
        self.analytics_file = Path(settings.storage_path) / "analytics.json"
        self._analytics_data = None

    def _load_analytics(self) -> dict:
        """Load analytics data from storage."""
        if self._analytics_data is not None:
            return self._analytics_data

        if self.analytics_file.exists():
            import json
            try:
                with open(self.analytics_file, "r") as f:
                    self._analytics_data = json.load(f)
                return self._analytics_data
            except Exception as e:
                self.logger.warning(f"Failed to load analytics data: {e}")
                self._analytics_data = {}
        else:
            self._analytics_data = {}

        return self._analytics_data

    def _save_analytics(self):
        """Save analytics data to storage."""
        import json

        self.analytics_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.analytics_file, "w") as f:
            json.dump(self._analytics_data, f, indent=2, default=str)

    def record_video_upload(
        self,
        episode_id: str,
        youtube_video_id: str,
        title: str,
        niche: Optional[str] = None,
        style: Optional[str] = None,
        published_at: Optional[datetime] = None,
    ):
        """
        Record that a video was uploaded to YouTube.

        Args:
            episode_id: Episode identifier
            youtube_video_id: YouTube video ID
            title: Video title
            niche: Story niche
            style: Story style
            published_at: Publication timestamp
        """
        data = self._load_analytics()
        
        if "videos" not in data:
            data["videos"] = {}

        data["videos"][episode_id] = {
            "youtube_video_id": youtube_video_id,
            "title": title,
            "niche": niche,
            "style": style,
            "published_at": published_at.isoformat() if published_at else None,
            "recorded_at": datetime.now().isoformat(),
            "metrics": {
                "views": None,
                "likes": None,
                "comments": None,
                "engagement_rate": None,
                "last_updated": None,
            },
        }

        self._analytics_data = data
        self._save_analytics()
        self.logger.info(f"Recorded video upload: {episode_id} -> {youtube_video_id}")

    def update_video_metrics(
        self,
        episode_id: str,
        views: Optional[int] = None,
        likes: Optional[int] = None,
        comments: Optional[int] = None,
        engagement_rate: Optional[float] = None,
    ):
        """
        Update performance metrics for a video.

        Args:
            episode_id: Episode identifier
            views: View count
            likes: Like count
            comments: Comment count
            engagement_rate: Engagement rate (0.0-1.0)
        """
        data = self._load_analytics()

        if "videos" not in data or episode_id not in data["videos"]:
            self.logger.warning(f"Video {episode_id} not found in analytics. Call record_video_upload() first.")
            return

        video_data = data["videos"][episode_id]
        if "metrics" not in video_data:
            video_data["metrics"] = {}

        if views is not None:
            video_data["metrics"]["views"] = views
        if likes is not None:
            video_data["metrics"]["likes"] = likes
        if comments is not None:
            video_data["metrics"]["comments"] = comments
        if engagement_rate is not None:
            video_data["metrics"]["engagement_rate"] = engagement_rate

        video_data["metrics"]["last_updated"] = datetime.now().isoformat()

        self._analytics_data = data
        self._save_analytics()
        self.logger.debug(f"Updated metrics for {episode_id}: views={views}, likes={likes}")

    def get_video_metrics(self, episode_id: str) -> Optional[dict]:
        """
        Get performance metrics for a video.

        Args:
            episode_id: Episode identifier

        Returns:
            Metrics dict or None if not found
        """
        data = self._load_analytics()

        if "videos" not in data or episode_id not in data["videos"]:
            return None

        return data["videos"][episode_id].get("metrics", {})

    def get_top_performers(
        self, metric: str = "views", limit: int = 10, niche: Optional[str] = None
    ) -> list[dict]:
        """
        Get top performing videos by metric.

        Args:
            metric: Metric to sort by ("views", "likes", "comments", "engagement_rate")
            limit: Number of results to return
            niche: Optional niche filter

        Returns:
            List of video data dicts, sorted by metric (descending)
        """
        data = self._load_analytics()

        if "videos" not in data:
            return []

        videos = []
        for episode_id, video_data in data["videos"].items():
            if niche and video_data.get("niche") != niche:
                continue

            metrics = video_data.get("metrics", {})
            metric_value = metrics.get(metric)

            if metric_value is not None:
                videos.append(
                    {
                        "episode_id": episode_id,
                        "youtube_video_id": video_data.get("youtube_video_id"),
                        "title": video_data.get("title"),
                        "niche": video_data.get("niche"),
                        "style": video_data.get("style"),
                        metric: metric_value,
                        "metrics": metrics,
                    }
                )

        # Sort by metric (descending)
        videos.sort(key=lambda x: x.get(metric, 0) or 0, reverse=True)

        return videos[:limit]

    def get_performance_summary(self) -> dict:
        """
        Get overall performance summary.

        Returns:
            Summary dict with aggregate metrics
        """
        data = self._load_analytics()

        if "videos" not in data:
            return {
                "total_videos": 0,
                "total_views": 0,
                "total_likes": 0,
                "total_comments": 0,
                "avg_engagement_rate": 0.0,
            }

        videos = data["videos"]
        total_videos = len(videos)
        total_views = 0
        total_likes = 0
        total_comments = 0
        engagement_rates = []

        for video_data in videos.values():
            metrics = video_data.get("metrics", {})
            if metrics.get("views"):
                total_views += metrics["views"]
            if metrics.get("likes"):
                total_likes += metrics["likes"]
            if metrics.get("comments"):
                total_comments += metrics["comments"]
            if metrics.get("engagement_rate"):
                engagement_rates.append(metrics["engagement_rate"])

        avg_engagement = (
            sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0.0
        )

        return {
            "total_videos": total_videos,
            "total_views": total_views,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "avg_engagement_rate": avg_engagement,
        }

