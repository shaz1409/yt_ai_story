"""Configuration management for the YouTube story generator."""

import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    openai_api_key: str
    elevenlabs_api_key: str
    elevenlabs_voice_id: str
    model_name: str = Field(default="gpt-4o-mini")
    output_base_dir: str = Field(default="outputs")
    huggingface_token: str = Field(default="", description="Optional HF token for higher rate limits")

    class Config:
        """Pydantic config."""

        case_sensitive = False


def load_settings() -> Settings:
    """Load settings from environment variables."""
    load_dotenv()
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", ""),
        elevenlabs_voice_id=os.getenv("ELEVENLABS_VOICE_ID", ""),
        model_name=os.getenv("MODEL_NAME", "gpt-4o-mini"),
        output_base_dir=os.getenv("OUTPUT_BASE_DIR", "outputs"),
        huggingface_token=os.getenv("HUGGINGFACE_TOKEN", ""),
    )

