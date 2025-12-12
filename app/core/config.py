"""Application configuration using pydantic-settings."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be configured via environment variables or a .env file.
    See .env.example for a template.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ========================================================================
    # Application Settings
    # ========================================================================
    app_name: str = Field(default="AI Story Shorts Factory", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)")

    # ========================================================================
    # LLM API Keys & Settings
    # ========================================================================
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model name")
    anthropic_model: str = Field(default="claude-3-haiku-20240307", description="Anthropic model name")

    # ========================================================================
    # TTS (Text-to-Speech) Settings
    # ========================================================================
    elevenlabs_api_key: Optional[str] = Field(default=None, description="ElevenLabs API key")
    elevenlabs_voice_id: Optional[str] = Field(default=None, description="ElevenLabs voice ID")
    tts_api_key: Optional[str] = Field(default=None, description="Generic TTS API key (deprecated)")

    # ========================================================================
    # Image Generation Settings
    # ========================================================================
    hf_endpoint_url: Optional[str] = Field(
        default=None,
        description="Hugging Face Inference Endpoint URL (required for image generation, e.g., https://xxx.eu.endpoints.huggingface.cloud). Set via HF_ENDPOINT_URL env var.",
    )
    hf_endpoint_token: Optional[str] = Field(
        default=None,
        description="Hugging Face Inference Endpoint token (required for image generation). Set via HF_ENDPOINT_TOKEN env var.",
    )
    huggingface_token: Optional[str] = Field(
        default=None, description="Hugging Face token (legacy, kept for backward compatibility)"
    )

    # ========================================================================
    # Video Rendering & Talking Heads
    # ========================================================================
    use_talking_heads: bool = Field(
        default=True, description="Enable talking-head character animations (default: true)"
    )
    max_talking_head_lines_per_video: int = Field(
        default=3, description="Maximum number of dialogue lines to animate per video (default: 3)"
    )
    character_image_style: str = Field(
        default="photorealistic",
        description="Character image style: 'photorealistic' (ultra-realistic) or 'artistic' (legacy style)",
    )
    min_image_quality_score: float = Field(
        default=0.65,
        description="Minimum acceptable image quality score (0.0 to 1.0, default: 0.65)",
    )
    max_image_retry_attempts: int = Field(
        default=3,
        description="Maximum number of retry attempts for image generation if quality validation fails (default: 3)",
    )
    video_width: int = Field(
        default=1080,
        description="Video output width in pixels (default: 1080 for vertical format)",
    )
    video_height: int = Field(
        default=1920,
        description="Video output height in pixels (default: 1920 for vertical format)",
    )
    image_post_processing_enabled: bool = Field(
        default=True,
        description="Enable image post-processing enhancement (default: true)",
    )
    image_look: str = Field(
        default="cinematic",
        description="Image look/style: 'cinematic', 'neutral', or 'warm' (default: cinematic)",
    )
    image_sharpness_strength: str = Field(
        default="medium",
        description="Sharpness enhancement strength: 'low', 'medium', or 'high' (default: medium)",
    )

    # ========================================================================
    # Lip-Sync Settings (Optional)
    # ========================================================================
    # Lip-Sync Settings
    lipsync_enabled: bool = Field(
        default=False,
        description="Enable real lip-sync for talking-heads (requires LIPSYNC_PROVIDER and API key)",
    )
    lipsync_provider: str = Field(
        default="none",
        description="Lip-sync provider: 'did', 'heygen', or 'none' (default: 'none')",
    )
    lipsync_api_key: Optional[str] = Field(
        default=None,
        description="Lip-sync API key (used for selected provider, can also use DID_API_KEY or HEYGEN_API_KEY)",
    )
    # Legacy D-ID settings (for backward compatibility)
    did_api_key: Optional[str] = Field(
        default=None, description="D-ID API key for real lip-sync talking-heads (optional, legacy)"
    )
    did_api_url: str = Field(
        default="https://api.d-id.com", description="D-ID API URL (default: https://api.d-id.com)"
    )
    # Legacy HeyGen settings (for backward compatibility)
    heygen_api_key: Optional[str] = Field(
        default=None, description="HeyGen API key for real lip-sync talking-heads (optional, legacy)"
    )
    heygen_api_url: str = Field(
        default="https://api.heygen.com", description="HeyGen API URL (default: https://api.heygen.com)"
    )
    # Legacy use_lipsync setting (for backward compatibility)
    use_lipsync: bool = Field(
        default=False,
        description="Enable real lip-sync for talking-heads (legacy, use LIPSYNC_ENABLED instead)",
    )

    # ========================================================================
    # Rate Limiting Settings
    # ========================================================================
    enable_rate_limiting: bool = Field(
        default=True,
        description="Enable rate limiting for API calls to prevent hitting limits (default: true)",
    )
    openai_rate_limit: int = Field(
        default=60, description="OpenAI API calls per minute (default: 60)"
    )
    hf_rate_limit: int = Field(
        default=30, description="Hugging Face API calls per minute (default: 30)"
    )
    elevenlabs_rate_limit: int = Field(
        default=100, description="ElevenLabs API calls per minute (default: 100)"
    )

    # ========================================================================
    # Parallelism Settings
    # ========================================================================
    max_parallel_episodes: int = Field(
        default=3,
        description="Maximum number of episodes to process concurrently (default: 3, set to 1 for sequential)",
    )
    max_parallel_api_calls: int = Field(
        default=5,
        description="Maximum number of parallel API calls within a single episode (TTS, image generation) (default: 5)",
    )

    # ========================================================================
    # Thumbnail Settings
    # ========================================================================
    thumbnail_enabled: bool = Field(
        default=True,
        description="Enable automatic thumbnail generation (default: true)",
    )
    thumbnail_mode: str = Field(
        default="hybrid",
        description="Thumbnail generation mode: 'frame' (extract from video), 'generated' (HF generation), or 'hybrid' (try generated, fallback to frame) (default: 'hybrid')",
    )
    thumbnail_add_text: bool = Field(
        default=True,
        description="Add title text overlay to generated thumbnails (default: true)",
    )

    # ========================================================================
    # YouTube Upload Settings
    # ========================================================================
    youtube_client_secrets_file: Optional[str] = Field(
        default=None, description="Path to YouTube OAuth client secrets JSON file"
    )
    youtube_token_file: Optional[str] = Field(
        default="youtube_token.json", description="Path to store YouTube OAuth token"
    )
    youtube_api_scopes: list[str] = Field(
        default=["https://www.googleapis.com/auth/youtube.upload"],
        description="YouTube API scopes",
    )

    # ========================================================================
    # Scheduling Settings
    # ========================================================================
    timezone: str = Field(
        default="Europe/London",
        description="Timezone for scheduling (e.g., 'Europe/London', 'America/New_York', 'America/Los_Angeles')",
    )
    daily_posting_hours: list[int] = Field(
        default=[11, 14, 18, 20, 22],
        description="Posting hours in local time for daily batch mode (24-hour format, e.g., [11, 14, 18, 20, 22])",
    )

    # ========================================================================
    # Story Generation Settings
    # ========================================================================
    default_duration_seconds: int = Field(default=60, description="Default video duration in seconds")
    min_duration_seconds: int = Field(default=45, description="Minimum video duration")
    max_duration_seconds: int = Field(default=90, description="Maximum video duration")
    default_style: str = Field(
        default="courtroom_drama", description="Default story style (courtroom_drama, ragebait, relationship_drama)"
    )

    # ========================================================================
    # Story Sourcing & Virality Scoring
    # ========================================================================
    use_llm_for_story_finder: bool = Field(
        default=False, description="Use LLM for story finding and virality scoring (default: false, uses stubs)"
    )

    # ========================================================================
    # Service Toggles (LLM Usage)
    # ========================================================================
    use_llm_for_rewriter: bool = Field(default=False, description="Use LLM for story rewriting")
    use_llm_for_characters: bool = Field(default=False, description="Use LLM for character generation")
    use_llm_for_dialogue: bool = Field(default=True, description="Use LLM for dialogue generation (default: true)")
    use_llm_for_narration: bool = Field(default=False, description="Use LLM for narration generation")
    use_llm_for_metadata: bool = Field(default=True, description="Use LLM for metadata generation (titles, descriptions) (default: true)")
    dialogue_model: str = Field(default="gpt-4o-mini", description="LLM model for dialogue and metadata generation")
    max_dialogue_lines_per_scene: int = Field(default=2, description="Maximum dialogue lines per scene (default: 2)")
    use_optimisation: bool = Field(
        default=False,
        validation_alias="USE_OPTIMISATION",
        description="Enable optimisation features (default: false)",
    )

    # ========================================================================
    # Storage Settings
    # ========================================================================
    storage_type: str = Field(default="json", description="Storage type: json or sqlite")
    storage_path: str = Field(default="storage/episodes", description="Storage path for episodes")

    # ========================================================================
    # Deprecated / Legacy Settings
    # ========================================================================
    video_api_url: Optional[str] = Field(
        default=None, description="Video generation API URL (deprecated, not used)"
    )


# Global settings instance
settings = Settings()

