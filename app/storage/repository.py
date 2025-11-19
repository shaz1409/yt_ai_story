"""Storage repository for episodes."""

import json
from pathlib import Path
from typing import Any, Optional

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import VideoPlan


class EpisodeRepository:
    """Repository for storing and loading episodes."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize the repository.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger
        self.storage_path = Path(settings.storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def save_episode(self, video_plan: VideoPlan) -> None:
        """
        Save an episode to storage.

        Args:
            video_plan: Video plan to save
        """
        self.logger.info(f"Saving episode: {video_plan.episode_id}")

        file_path = self.storage_path / f"{video_plan.episode_id}.json"

        # Convert to dict and save as JSON
        plan_dict = video_plan.model_dump()
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(plan_dict, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Episode saved to: {file_path}")

    def load_episode(self, episode_id: str) -> Optional[VideoPlan]:
        """
        Load an episode from storage.

        Args:
            episode_id: Episode identifier

        Returns:
            Video plan if found, None otherwise
        """
        self.logger.info(f"Loading episode: {episode_id}")

        file_path = self.storage_path / f"{episode_id}.json"

        if not file_path.exists():
            self.logger.warning(f"Episode not found: {episode_id}")
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            plan_dict = json.load(f)

        video_plan = VideoPlan(**plan_dict)
        self.logger.info(f"Episode loaded: {episode_id}")
        return video_plan

    def list_episodes(self) -> list[str]:
        """
        List all episode IDs.

        Returns:
            List of episode IDs
        """
        episode_files = list(self.storage_path.glob("*.json"))
        episode_ids = [f.stem for f in episode_files]
        self.logger.info(f"Found {len(episode_ids)} episodes")
        return episode_ids

