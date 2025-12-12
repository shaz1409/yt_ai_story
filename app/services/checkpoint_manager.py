"""Checkpoint Manager - saves and restores pipeline progress for resume on failure."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.config import Settings
from app.core.logging_config import get_logger


class CheckpointManager:
    """Manages pipeline checkpoints for resume on failure."""

    # Pipeline stages
    STAGE_STORY_GENERATED = "story_generated"
    STAGE_VIDEO_RENDERED = "video_rendered"
    STAGE_UPLOADED = "uploaded"

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize checkpoint manager.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger
        self.checkpoint_dir = Path(settings.storage_path) / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(
        self,
        episode_id: str,
        stage: str,
        data: dict,
    ):
        """
        Save a checkpoint for an episode.

        Args:
            episode_id: Episode identifier
            stage: Pipeline stage (STAGE_STORY_GENERATED, STAGE_VIDEO_RENDERED, etc.)
            data: Checkpoint data (episode_id, video_plan, video_path, etc.)
        """
        checkpoint_file = self.checkpoint_dir / f"{episode_id}_{stage}.json"
        
        checkpoint_data = {
            "episode_id": episode_id,
            "stage": stage,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }

        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint_data, f, indent=2, default=str)

        self.logger.info(f"Saved checkpoint: {episode_id} at stage {stage}")

    def load_checkpoint(self, episode_id: str, stage: str) -> Optional[dict]:
        """
        Load a checkpoint for an episode.

        Args:
            episode_id: Episode identifier
            stage: Pipeline stage

        Returns:
            Checkpoint data dict or None if not found
        """
        checkpoint_file = self.checkpoint_dir / f"{episode_id}_{stage}.json"

        if not checkpoint_file.exists():
            return None

        try:
            with open(checkpoint_file, "r") as f:
                checkpoint_data = json.load(f)
            self.logger.info(f"Loaded checkpoint: {episode_id} at stage {stage}")
            return checkpoint_data.get("data")
        except Exception as e:
            self.logger.warning(f"Failed to load checkpoint {checkpoint_file}: {e}")
            return None

    def has_checkpoint(self, episode_id: str, stage: str) -> bool:
        """
        Check if a checkpoint exists.

        Args:
            episode_id: Episode identifier
            stage: Pipeline stage

        Returns:
            True if checkpoint exists
        """
        checkpoint_file = self.checkpoint_dir / f"{episode_id}_{stage}.json"
        return checkpoint_file.exists()

    def clear_checkpoint(self, episode_id: str, stage: str):
        """
        Clear a checkpoint (after successful completion).

        Args:
            episode_id: Episode identifier
            stage: Pipeline stage
        """
        checkpoint_file = self.checkpoint_dir / f"{episode_id}_{stage}.json"
        if checkpoint_file.exists():
            checkpoint_file.unlink()
            self.logger.debug(f"Cleared checkpoint: {episode_id} at stage {stage}")

    def clear_all_checkpoints(self, episode_id: str):
        """
        Clear all checkpoints for an episode.

        Args:
            episode_id: Episode identifier
        """
        for checkpoint_file in self.checkpoint_dir.glob(f"{episode_id}_*.json"):
            checkpoint_file.unlink()
        self.logger.debug(f"Cleared all checkpoints for: {episode_id}")

    def list_checkpoints(self, episode_id: Optional[str] = None) -> list[dict]:
        """
        List all checkpoints.

        Args:
            episode_id: Optional episode ID filter

        Returns:
            List of checkpoint metadata dicts
        """
        checkpoints = []
        pattern = f"{episode_id}_*.json" if episode_id else "*.json"

        for checkpoint_file in self.checkpoint_dir.glob(pattern):
            try:
                with open(checkpoint_file, "r") as f:
                    checkpoint_data = json.load(f)
                checkpoints.append({
                    "episode_id": checkpoint_data.get("episode_id"),
                    "stage": checkpoint_data.get("stage"),
                    "timestamp": checkpoint_data.get("timestamp"),
                    "file": str(checkpoint_file),
                })
            except Exception as e:
                self.logger.warning(f"Failed to read checkpoint {checkpoint_file}: {e}")

        return checkpoints

