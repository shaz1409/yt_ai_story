"""Metadata Generator - generates clickbait titles, descriptions, tags, and hooks."""

from typing import Any

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import VideoPlan
from app.services.llm_client import LLMClient


class VideoMetadata:
    """Metadata for a video (title, description, tags, hook)."""

    def __init__(self, title: str, description: str, tags: list[str], hook_line: str = ""):
        self.title = title
        self.description = description
        self.tags = tags
        self.hook_line = hook_line


class MetadataGenerator:
    """Generates viral YouTube Shorts metadata (titles, descriptions, tags, hooks)."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize metadata generator.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger
        self.use_llm = getattr(settings, "use_llm_for_metadata", True)
        
        if self.use_llm and settings.openai_api_key:
            self.llm_client = LLMClient(settings, logger)
        else:
            self.llm_client = None
            if self.use_llm:
                self.logger.warning("LLM metadata generation enabled but OpenAI API key not set, falling back to heuristics")

    def generate_metadata(self, video_plan: VideoPlan) -> VideoMetadata:
        """
        Generate clickbait metadata for a video plan.

        Args:
            video_plan: VideoPlan object

        Returns:
            VideoMetadata with title, description, tags, hook_line
        """
        self.logger.info("Generating video metadata...")

        # Try LLM generation if enabled
        if self.use_llm and self.llm_client:
            try:
                llm_metadata = self.llm_client.generate_metadata(video_plan, video_plan.style)
                
                metadata = VideoMetadata(
                    title=llm_metadata["title"],
                    description=llm_metadata["description"],
                    tags=llm_metadata["tags"],
                    hook_line=llm_metadata.get("hook_line", ""),
                )
                
                self.logger.info(f"Generated metadata via LLM: {metadata.title[:50]}...")
                return metadata

            except Exception as e:
                self.logger.warning(f"LLM metadata generation failed: {e}, falling back to heuristics")

        # Fallback to heuristic generation
        return self._generate_metadata_heuristic(video_plan)

    def _generate_metadata_heuristic(self, video_plan: VideoPlan) -> VideoMetadata:
        """
        Generate metadata using heuristic/rules (fallback).

        Args:
            video_plan: VideoPlan object

        Returns:
            VideoMetadata
        """
        # Generate clickable title
        base_title = video_plan.title or video_plan.topic
        style = video_plan.style.lower()

        if style == "ragebait":
            title = f"[SHOCKING] {base_title} - You Won't Believe This!"
        elif style == "relationship_drama":
            title = f"{base_title} - This Will Break Your Heart"
        else:  # courtroom_drama
            title = f"[SHOCKING] {base_title} - The Verdict Will Shock You"

        # Ensure under 100 characters
        if len(title) > 100:
            title = title[:97] + "..."

        # Generate hashtags
        tags = self._generate_hashtags(video_plan)

        # Build description
        description_parts = [
            video_plan.logline or f"A dramatic story about {video_plan.topic}",
            "",
            " ".join(tags),
            "",
            f"Episode: {video_plan.episode_id}",
        ]
        description = "\n".join(description_parts)

        # Generate hook line from first scene
        hook_line = ""
        if video_plan.scenes:
            first_scene = video_plan.scenes[0]
            if first_scene.narration:
                hook_line = first_scene.narration[0].text[:100]  # First narration line

        return VideoMetadata(
            title=title,
            description=description,
            tags=[tag.replace("#", "") for tag in tags if tag.startswith("#")],
            hook_line=hook_line,
        )

    def _generate_hashtags(self, video_plan: VideoPlan, max_tags: int = 10) -> list[str]:
        """
        Generate relevant hashtags from VideoPlan.

        Args:
            video_plan: VideoPlan object
            max_tags: Maximum number of tags

        Returns:
            List of hashtag strings
        """
        tags = []

        # Style-based tags
        style = video_plan.style.lower()
        if "courtroom" in style:
            tags.extend(["#courtroom", "#justice", "#legal", "#drama", "#verdict"])
        elif "ragebait" in style:
            tags.extend(["#ragebait", "#shocking", "#drama", "#viral"])
        elif "relationship" in style:
            tags.extend(["#relationship", "#drama", "#emotional", "#story"])

        # Topic-based tags
        topic_lower = video_plan.topic.lower()
        if "teen" in topic_lower or "young" in topic_lower:
            tags.append("#teen")
        if "judge" in topic_lower or "court" in topic_lower:
            tags.extend(["#judge", "#court"])
        if "laugh" in topic_lower or "reaction" in topic_lower:
            tags.append("#reaction")
        if "karma" in topic_lower or "consequences" in topic_lower:
            tags.append("#karma")

        # Universal tags
        tags.extend(["#shorts", "#story", "#drama"])

        # Remove duplicates and limit
        unique_tags = list(dict.fromkeys(tags))  # Preserves order
        return unique_tags[:max_tags]

