"""Voice generation using ElevenLabs API."""

from pathlib import Path
from typing import Any

import requests

from config import Settings


def generate_voice_audio(
    text: str,
    output_path: Path,
    settings: Settings,
    logger: Any,
) -> None:
    """
    Generate voice audio from text using ElevenLabs API.

    Args:
        text: Text to convert to speech.
        output_path: Path where the audio file will be saved.
        settings: Application settings containing API credentials.
        logger: Logger instance.

    Raises:
        Exception: If API call fails or response is invalid.
    """
    if not text or not text.strip():
        logger.warning("Empty text provided for voice generation")
        raise ValueError("Text cannot be empty")

    logger.info(f"Generating voice audio for {len(text)} characters of text...")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": settings.elevenlabs_api_key,
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
        logger.info("Sending request to ElevenLabs API...")
        response = requests.post(url, json=data, headers=headers, timeout=30)

        if response.status_code != 200:
            logger.error(f"ElevenLabs API error: {response.status_code} - {response.text}")
            raise Exception(f"ElevenLabs API returned status {response.status_code}: {response.text}")

        # Save audio file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)

        logger.info(f"Successfully generated voice audio: {output_path}")
        logger.info(f"Audio file size: {len(response.content)} bytes")

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error calling ElevenLabs API: {e}")
        raise
    except Exception as e:
        logger.error(f"Error generating voice audio: {e}")
        raise

