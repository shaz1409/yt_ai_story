"""TTS (Text-to-Speech) client abstraction for multiple providers."""

from pathlib import Path
from typing import Any, Optional

import requests

from app.core.config import Settings
from app.core.logging_config import get_logger


class TTSClient:
    """Abstract TTS client supporting multiple providers."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize TTS client.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger
        self.provider = self._detect_provider()

    def _detect_provider(self) -> str:
        """Detect which TTS provider to use based on available credentials."""
        if hasattr(self.settings, "elevenlabs_api_key") and self.settings.elevenlabs_api_key:
            return "elevenlabs"
        elif hasattr(self.settings, "openai_api_key") and self.settings.openai_api_key:
            return "openai"
        else:
            return "stub"

    def generate_speech(
        self,
        text: str,
        output_path: Path,
        voice_id: Optional[str] = None,
        voice_profile: Optional[str] = None,
    ) -> None:
        """
        Generate speech from text and save to file.

        Args:
            text: Text to convert to speech
            output_path: Path to save audio file
            voice_id: Optional voice ID (provider-specific, takes precedence)
            voice_profile: Optional voice profile string (e.g., "deep male", "young female")

        Raises:
            Exception: If generation fails
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        # Map voice_profile to voice_id if voice_id not provided
        if not voice_id and voice_profile:
            voice_id = self._map_voice_profile_to_id(voice_profile)

        self.logger.info(f"Generating speech using {self.provider} provider for {len(text)} characters...")

        if self.provider == "elevenlabs":
            self._generate_elevenlabs(text, output_path, voice_id)
        elif self.provider == "openai":
            self._generate_openai(text, output_path, voice_id)
        else:
            self._generate_stub(text, output_path)

        self.logger.info(f"Speech generated: {output_path}")

    def _map_voice_profile_to_id(self, voice_profile: str) -> Optional[str]:
        """
        Map a voice profile string to a provider-specific voice ID.

        Args:
            voice_profile: Voice profile string (e.g., "deep male", "young female")

        Returns:
            Voice ID if mapping exists, None otherwise
        """
        if not voice_profile:
            return None

        profile_lower = voice_profile.lower()

        # OpenAI TTS voice mapping
        if self.provider == "openai":
            # OpenAI has: alloy, echo, fable, onyx, nova, shimmer
            if "male" in profile_lower or "man" in profile_lower or "deep" in profile_lower:
                return "onyx"  # Deep male voice
            elif "female" in profile_lower or "woman" in profile_lower or "young" in profile_lower:
                return "nova"  # Young female voice
            elif "neutral" in profile_lower:
                return "alloy"  # Neutral voice
            else:
                return "alloy"  # Default

        # ElevenLabs would need actual voice IDs from their API
        # For now, return None to use default
        elif self.provider == "elevenlabs":
            # Could implement mapping if you have multiple ElevenLabs voices
            return None

        return None

    def _generate_elevenlabs(self, text: str, output_path: Path, voice_id: Optional[str] = None) -> None:
        """Generate speech using ElevenLabs API."""
        if not hasattr(self.settings, "elevenlabs_api_key") or not self.settings.elevenlabs_api_key:
            raise ValueError("ElevenLabs API key not configured")

        voice_id = voice_id or getattr(self.settings, "elevenlabs_voice_id", None)
        if not voice_id:
            raise ValueError("ElevenLabs voice ID not configured")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.settings.elevenlabs_api_key,
        }

        data = {
            "text": text,
            "model_id": "eleven_turbo_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        try:
            response = requests.post(url, json=data, headers=headers, timeout=30)

            if response.status_code != 200:
                raise Exception(f"ElevenLabs API returned status {response.status_code}: {response.text}")

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(response.content)

        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error calling ElevenLabs API: {e}")

    def _generate_openai(self, text: str, output_path: Path, voice_id: Optional[str] = None) -> None:
        """Generate speech using OpenAI TTS API."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("OpenAI package not installed. Install with: pip install openai")

        if not self.settings.openai_api_key:
            raise ValueError("OpenAI API key not configured")

        client = OpenAI(api_key=self.settings.openai_api_key)

        # Default voice if not specified
        voice = voice_id or "alloy"

        try:
            response = client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
            )

            output_path.parent.mkdir(parents=True, exist_ok=True)
            response.stream_to_file(str(output_path))

        except Exception as e:
            raise Exception(f"OpenAI TTS API error: {e}")

    def _generate_stub(self, text: str, output_path: Path) -> None:
        """
        Generate stub audio (silent or placeholder).

        This creates a minimal audio file for testing when no TTS provider is configured.
        """
        self.logger.warning("Using stub TTS - generating silent audio placeholder")
        # Create a minimal silent audio file using a simple approach
        # For a real stub, you might use pydub or similar
        try:
            from pydub import AudioSegment

            # Create silent audio matching approximate duration
            # Rough estimate: 150 words per minute = 2.5 words per second
            word_count = len(text.split())
            duration_seconds = max(1.0, word_count / 2.5)

            silent_audio = AudioSegment.silent(duration=int(duration_seconds * 1000))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            silent_audio.export(str(output_path), format="mp3")

        except ImportError:
            # If pydub not available, try to create a minimal WAV file using wave module
            self.logger.warning("pydub not available, creating minimal WAV file")
            try:
                import wave
                import struct

                # Rough estimate: 150 words per minute = 2.5 words per second
                word_count = len(text.split())
                duration_seconds = max(1.0, word_count / 2.5)
                sample_rate = 44100
                num_samples = int(duration_seconds * sample_rate)

                output_path = output_path.with_suffix(".wav")  # Change to .wav
                output_path.parent.mkdir(parents=True, exist_ok=True)

                with wave.open(str(output_path), "wb") as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(sample_rate)
                    # Write silent audio (zeros)
                    wav_file.writeframes(b"\x00\x00" * num_samples)

                self.logger.info(f"Created stub WAV file: {output_path}")
            except Exception as e:
                self.logger.error(f"Could not create stub audio: {e}")
                raise ImportError(
                    "Stub TTS requires pydub or wave module. Install with: pip install pydub"
                )

