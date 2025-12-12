"""Pydantic models and schemas for the story generation pipeline."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================


class EditPattern(str, Enum):
    """Edit pattern/visual style for video composition."""

    TALKING_HEAD_HEAVY = "talking_head_heavy"
    BROLL_CINEMATIC = "broll_cinematic"
    MIXED_RAPID = "mixed_rapid"


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


class Beat(BaseModel):
    """A story beat in the narrative structure."""

    type: str = Field(..., description="Beat type: HOOK, TRIGGER, CONTEXT, CLASH, TWIST, CTA")
    speaker: str = Field(..., description="Speaker: 'narrator' or character_id")
    target_emotion: str = Field(..., description="Target emotion: rage, injustice, shock, disgust")
    text: str = Field(..., description="Beat text content")


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


class CharacterVoiceProfile(BaseModel):
    """Detailed voice profile for character TTS generation."""

    gender: str = Field(..., description="Gender (male, female, any)")
    age_range: str = Field(..., description="Age range (e.g., '18-25', '50-70')")
    tone_adjectives: list[str] = Field(default_factory=list, description="Tone adjectives (e.g., 'stern', 'nervous', 'authoritative')")
    example_text: Optional[str] = Field(default=None, description="Example reference text for voice matching")


class Character(BaseModel):
    """A character in the story."""

    id: str = Field(..., description="Unique character identifier")
    role: str = Field(..., description="Character role (judge, defendant, lawyer, narrator, etc.)")
    name: str = Field(..., description="Character name")
    appearance: dict[str, Any] = Field(default_factory=dict, description="Physical appearance details")
    personality: str = Field(..., description="Personality description")
    voice_profile: str = Field(..., description="Voice profile for TTS (e.g., 'deep male', 'young female')")
    detailed_voice_profile: Optional[CharacterVoiceProfile] = Field(
        default=None, description="Detailed voice profile with gender, age, tone (for character speech)"
    )
    # Enhanced character depth fields
    motivation: Optional[str] = Field(default=None, description="Character's core motivation or goal")
    fear_insecurity: Optional[str] = Field(default=None, description="Character's fear or insecurity")
    belief_worldview: Optional[str] = Field(default=None, description="Character's belief or worldview")
    preferred_speech_style: Optional[str] = Field(default=None, description="Preferred speech style (formal, casual, defensive, etc.)")
    emotional_trigger: Optional[str] = Field(default=None, description="What triggers strong emotional reactions in this character")


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
# Episode Metadata Models
# ============================================================================


class EpisodeMetadata(BaseModel):
    """Metadata about an episode for analytics and tracking."""

    niche: str = Field(..., description="Story niche (e.g., 'courtroom', 'relationship_drama')")
    pattern_type: str = Field(..., description="Story pattern type")
    primary_emotion: str = Field(..., description="Primary emotion of the story")
    secondary_emotion: Optional[str] = Field(default=None, description="Secondary emotion if applicable")
    topics: list[str] = Field(default_factory=list, description="List of topics/tags")
    moral_axes: list[str] = Field(default_factory=list, description="Moral dimensions explored")

    num_beats: int = Field(..., description="Number of story beats")
    num_scenes: int = Field(..., description="Number of scenes")
    num_dialogue_lines: int = Field(..., description="Total number of dialogue lines")
    num_narration_lines: int = Field(..., description="Total number of narration lines")
    has_twist: bool = Field(..., description="Whether the story has a twist")
    has_cta: bool = Field(..., description="Whether the story has a call-to-action")

    style: str = Field(..., description="Story style (e.g., 'courtroom_drama')")
    hf_model: Optional[str] = Field(default=None, description="Hugging Face model used for image generation")
    tts_provider: Optional[str] = Field(default=None, description="TTS provider used (e.g., 'elevenlabs', 'openai')")
    llm_model_story: Optional[str] = Field(default=None, description="LLM model used for story generation")
    llm_model_dialogue: Optional[str] = Field(default=None, description="LLM model used for dialogue generation")
    talking_heads_enabled: bool = Field(default=True, description="Whether talking heads were enabled")

    video_duration_sec: Optional[float] = Field(default=None, description="Actual video duration in seconds")
    audio_duration_sec: Optional[float] = Field(default=None, description="Actual audio duration in seconds")
    num_broll_clips: Optional[int] = Field(default=None, description="Number of B-roll clips used")
    num_talking_head_clips: Optional[int] = Field(default=None, description="Number of talking head clips used")

    youtube_video_id: Optional[str] = Field(default=None, description="YouTube video ID if published")
    published_at: Optional[datetime] = Field(default=None, description="Publication timestamp")
    published_hour_local: Optional[int] = Field(default=None, description="Publication hour in local timezone (0-23)")
    planned_publish_at: Optional[datetime] = Field(default=None, description="Scheduled publish time (set before upload)")

    views_24h: Optional[int] = Field(default=None, description="Views in first 24 hours")
    likes_24h: Optional[int] = Field(default=None, description="Likes in first 24 hours")
    comments_24h: Optional[int] = Field(default=None, description="Comments in first 24 hours")
    avg_view_duration_24h: Optional[float] = Field(default=None, description="Average view duration in first 24 hours (seconds)")
    avg_view_percent_24h: Optional[float] = Field(default=None, description="Average view percentage in first 24 hours (0-100)")
    edit_pattern: Optional[EditPattern] = Field(
        default=None,
        description="Edit pattern/visual style for this episode (talking_head_heavy, broll_cinematic, mixed_rapid)",
    )


# ============================================================================
# Video Plan Engine Models
# ============================================================================


class CharacterSpokenLine(BaseModel):
    """A line that should be spoken by a character (not narrator)."""

    character_id: str = Field(..., description="Character ID who will speak this line")
    line_text: str = Field(..., description="Text to be spoken by the character")
    emotion: str = Field(default="neutral", description="Emotion for the line")
    scene_id: int = Field(..., description="Scene ID where this line appears")
    approx_timing_seconds: float = Field(default=0.0, description="Approximate timing in seconds from scene start")


class BrollScene(BaseModel):
    """A B-roll scene for cinematic context."""

    category: str = Field(..., description="B-roll category: establishing_scene, mid_shot, emotional_closeup, dramatic_insert")
    prompt: str = Field(..., description="Photorealistic prompt for this B-roll scene")
    timing_hint: float = Field(default=0.0, description="Approximate timing in seconds from video start")
    scene_id: int = Field(..., description="Associated scene ID")


class VideoScene(BaseModel):
    """A scene in the video plan."""

    scene_id: int = Field(..., description="Scene identifier")
    description: str = Field(..., description="Scene description")
    background_prompt: str = Field(..., description="Background/environment prompt for video generation")
    camera_style: str = Field(default="medium_shot", description="Camera style (close_up, medium_shot, wide_shot, etc.)")
    narration: list[NarrationLine] = Field(default_factory=list, description="Narration lines for this scene")
    dialogue: list[DialogueLine] = Field(default_factory=list, description="Dialogue lines for this scene")
    b_roll_prompts: list[str] = Field(default_factory=list, description="Optional B-roll image prompts (legacy)")
    b_roll_scenes: list[BrollScene] = Field(default_factory=list, description="Cinematic B-roll scenes for this video scene")
    character_spoken_lines: list[CharacterSpokenLine] = Field(
        default_factory=list, description="Lines that should be spoken by characters (not narrator)"
    )
    emotion: Optional[str] = Field(default=None, description="Emotional marker for this scene/beat (tense, angered, sad, shocked, relieved, vindicated)")


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
    character_spoken_lines: list[CharacterSpokenLine] = Field(
        default_factory=list, description="Lines that should be spoken by characters (sampled from dialogue, 2-4 per video)"
    )
    b_roll_scenes: list[BrollScene] = Field(
        default_factory=list, description="Cinematic B-roll scenes for the entire video (4-6 scenes)"
    )
    
    # Optional reveal points (timestamps when revelations occur)
    reveal_points: Optional[list[int]] = Field(
        default=None, description="List of timestamps (in seconds) when revelations or contradictions occur in the story"
    )

    # Generation metadata
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    version: str = Field(default="1.0", description="Plan version")
    
    # Episode metadata (optional for backward compatibility)
    metadata: Optional[EpisodeMetadata] = Field(default=None, description="Episode metadata for analytics and tracking")


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

