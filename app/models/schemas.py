"""Pydantic models and schemas for the story generation pipeline."""

from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Story Finder Models
# ============================================================================


class StoryCandidate(BaseModel):
    """A candidate story from external sources."""

    id: str = Field(..., description="Unique identifier for the candidate")
    source_id: Optional[str] = Field(default=None, description="Unique identifier from source (deprecated, use id)")
    title: str = Field(..., description="Story title")
    raw_text: str = Field(..., description="Raw story text")
    source: str = Field(default="stub", description="Source type (e.g., 'stub_aita', 'stub_courtroom', 'user_topic_llm')")
    niche: str = Field(default="courtroom", description="Story niche (e.g., 'courtroom', 'relationship_drama', 'injustice')")
    source_url: Optional[str] = Field(default=None, description="Source URL if available")
    source_type: str = Field(default="scraped", description="Source type (scraped, manual, etc.) - deprecated")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    viral_score: Optional[float] = Field(default=None, description="Calculated viral potential score (deprecated, use ViralityScore)")

    def model_post_init(self, __context: Any) -> None:
        """Set source_id to id if not provided for backward compatibility."""
        if self.source_id is None:
            self.source_id = self.id


class ViralityScore(BaseModel):
    """Detailed virality score for a story candidate."""

    candidate_id: str = Field(..., description="ID of the candidate being scored")
    overall_score: float = Field(..., ge=0.0, le=1.0, description="Overall virality score (0.0-1.0)")
    shock: float = Field(..., ge=0.0, le=1.0, description="Shock value - surprising, unexpected events")
    rage: float = Field(..., ge=0.0, le=1.0, description="Rage factor - triggers anger/indignation")
    injustice: float = Field(..., ge=0.0, le=1.0, description="Injustice factor - unfair treatment, bad outcomes")
    relatability: float = Field(..., ge=0.0, le=1.0, description="Relatability - common situations people recognize")
    twist_strength: float = Field(..., ge=0.0, le=1.0, description="Twist strength - how strong the reversal is")
    clarity: float = Field(..., ge=0.0, le=1.0, description="Clarity - how easy the story is to follow")


# ============================================================================
# Story Rewriter Models
# ============================================================================


class NarrationLine(BaseModel):
    """A single line of narration."""

    text: str = Field(..., description="Narration text")
    emotion: str = Field(default="neutral", description="Emotion tag (neutral, dramatic, tense, etc.)")
    scene_id: int = Field(..., description="Associated scene ID")


class CharacterAction(BaseModel):
    """A character action within a scene."""

    character_id: Optional[str] = Field(default=None, description="Character ID if known")
    action_description: str = Field(..., description="Description of the action")
    emotion: str = Field(default="neutral", description="Emotion tag")


class Scene(BaseModel):
    """A scene in the story script."""

    scene_id: int = Field(..., description="Scene identifier (1-indexed)")
    description: str = Field(..., description="Scene description")
    narration_lines: list[NarrationLine] = Field(default_factory=list, description="Narration for this scene")
    character_actions: list[CharacterAction] = Field(default_factory=list, description="Character actions in scene")


class StoryScript(BaseModel):
    """Rewritten story script with scenes."""

    title: str = Field(..., description="Story title")
    logline: str = Field(..., description="One-line story summary")
    scenes: list[Scene] = Field(..., description="List of scenes (2-4 scenes typical)")


# ============================================================================
# Character Engine Models
# ============================================================================


class Character(BaseModel):
    """A character in the story."""

    id: str = Field(..., description="Unique character identifier")
    role: str = Field(..., description="Character role (judge, defendant, lawyer, narrator, etc.)")
    name: str = Field(..., description="Character name")
    appearance: dict[str, Any] = Field(default_factory=dict, description="Physical appearance details")
    personality: str = Field(..., description="Personality description")
    voice_profile: str = Field(..., description="Voice profile for TTS (e.g., 'deep male', 'young female')")


class CharacterSet(BaseModel):
    """Set of characters for an episode."""

    characters: list[Character] = Field(..., description="List of characters")
    narrator_id: Optional[str] = Field(default=None, description="ID of narrator character if separate")


# ============================================================================
# Dialogue Engine Models
# ============================================================================


class DialogueLine(BaseModel):
    """A single line of dialogue."""

    character_id: str = Field(..., description="Character ID speaking")
    text: str = Field(..., description="Dialogue text")
    emotion: str = Field(..., description="Emotion tag (angry, sad, shocked, tense, neutral)")
    scene_id: int = Field(..., description="Associated scene ID")
    approx_timing_hint: float = Field(default=0.0, description="Approximate timing in seconds from scene start")


class DialoguePlan(BaseModel):
    """Complete dialogue plan for the story."""

    lines: list[DialogueLine] = Field(..., description="All dialogue lines")


# ============================================================================
# Narration Engine Models
# ============================================================================


class NarrationPlan(BaseModel):
    """Complete narration plan for the story."""

    lines: list[NarrationLine] = Field(..., description="All narration lines")


# ============================================================================
# Video Plan Engine Models
# ============================================================================


class VideoScene(BaseModel):
    """A scene in the video plan."""

    scene_id: int = Field(..., description="Scene identifier")
    description: str = Field(..., description="Scene description")
    background_prompt: str = Field(..., description="Background/environment prompt for video generation")
    camera_style: str = Field(default="medium_shot", description="Camera style (close_up, medium_shot, wide_shot, etc.)")
    narration: list[NarrationLine] = Field(default_factory=list, description="Narration lines for this scene")
    dialogue: list[DialogueLine] = Field(default_factory=list, description="Dialogue lines for this scene")
    b_roll_prompts: list[str] = Field(default_factory=list, description="Optional B-roll image prompts")


class VideoPlan(BaseModel):
    """Complete video plan for external video generation."""

    # Metadata
    episode_id: str = Field(..., description="Unique episode identifier")
    topic: str = Field(..., description="Original topic")
    duration_target_seconds: int = Field(..., description="Target duration in seconds")
    style: str = Field(default="courtroom_drama", description="Story style")

    # Content
    title: str = Field(..., description="Episode title")
    logline: str = Field(..., description="One-line summary")
    characters: list[Character] = Field(..., description="All characters in this episode")
    scenes: list[VideoScene] = Field(..., description="All video scenes")

    # Generation metadata
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    version: str = Field(default="1.0", description="Plan version")


# ============================================================================
# API Request/Response Models
# ============================================================================


class GenerateStoryRequest(BaseModel):
    """Request to generate a story."""

    topic: str = Field(..., description="Story topic (e.g., 'courtroom drama – teen laughs at verdict')")
    duration_target_seconds: int = Field(default=60, ge=45, le=90, description="Target duration in seconds")


class GenerateStoryResponse(BaseModel):
    """Response from story generation."""

    episode_id: str = Field(..., description="Unique episode identifier")
    title: str = Field(..., description="Episode title")
    logline: str = Field(..., description="One-line summary")
    scene_count: int = Field(..., description="Number of scenes")
    character_count: int = Field(..., description="Number of characters")
    status: str = Field(default="completed", description="Generation status")

