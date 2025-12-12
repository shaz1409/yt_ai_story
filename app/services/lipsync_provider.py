"""Lip-Sync Provider - abstract interface for real talking-head generation with mouth movement."""

import base64
import time
from pathlib import Path
from typing import Any, Optional

import requests
from moviepy.editor import AudioFileClip, VideoFileClip

from app.core.config import Settings
from app.core.logging_config import get_logger


class LipSyncProvider:
    """Abstract provider for lip-sync talking-head video generation."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize lip-sync provider.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger

    def generate_talking_head(
        self, base_image_path: Path, audio_path: Path, output_path: Path
    ) -> Path:
        """
        Generate a talking-head video clip with real lip-sync.

        Args:
            base_image_path: Path to character's base face image
            audio_path: Path to dialogue audio file
            output_path: Path to save output video clip

        Returns:
            Path to generated video clip

        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        raise NotImplementedError("Subclass must implement generate_talking_head()")


class DIDLipSyncProvider(LipSyncProvider):
    """D-ID API provider for lip-sync talking-head generation."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize D-ID provider.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        super().__init__(settings, logger)
        # Support both new LIPSYNC_API_KEY and legacy DID_API_KEY
        self.api_key = getattr(settings, "lipsync_api_key", None) or getattr(settings, "did_api_key", None)
        self.api_url = getattr(settings, "did_api_url", "https://api.d-id.com")
        
        if not self.api_key:
            self.logger.warning("D-ID API key not configured. Lip-sync will not work.")

    def generate_talking_head(
        self, base_image_path: Path, audio_path: Path, output_path: Path
    ) -> Path:
        """
        Generate talking-head using D-ID API.

        Args:
            base_image_path: Path to character's base face image
            audio_path: Path to dialogue audio file
            output_path: Path to save output video clip

        Returns:
            Path to generated video clip

        Raises:
            ValueError: If API key not configured
            Exception: If API call fails
        """
        if not self.api_key:
            raise ValueError("D-ID API key not configured. Set DID_API_KEY in .env")

        self.logger.info(f"Generating lip-sync talking-head via D-ID API...")
        self.logger.info(f"  Image: {base_image_path.name}")
        self.logger.info(f"  Audio: {audio_path.name}")

        # D-ID uses Bearer token authentication
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            # Step 1: Upload image
            self.logger.debug("Uploading image to D-ID...")
            with open(base_image_path, "rb") as img_file:
                img_data = base64.b64encode(img_file.read()).decode("utf-8")
            
            image_response = requests.post(
                f"{self.api_url}/images",
                json={"image": f"data:image/png;base64,{img_data}"},
                headers=headers,
                timeout=30,
            )
            image_response.raise_for_status()
            image_id = image_response.json().get("id")
            self.logger.debug(f"Image uploaded: {image_id}")

            # Step 2: Upload audio
            self.logger.debug("Uploading audio to D-ID...")
            with open(audio_path, "rb") as audio_file:
                audio_data = base64.b64encode(audio_file.read()).decode("utf-8")
            
            audio_response = requests.post(
                f"{self.api_url}/audios",
                json={"audio": f"data:audio/mp3;base64,{audio_data}"},
                headers=headers,
                timeout=30,
            )
            audio_response.raise_for_status()
            audio_id = audio_response.json().get("id")
            self.logger.debug(f"Audio uploaded: {audio_id}")

            # Step 3: Create talk
            self.logger.debug("Creating D-ID talk...")
            talk_response = requests.post(
                f"{self.api_url}/talks",
                json={
                    "source_url": f"{self.api_url}/images/{image_id}",
                    "script": {
                        "type": "audio",
                        "audio_url": f"{self.api_url}/audios/{audio_id}",
                    },
                    "config": {
                        "result_format": "mp4",
                        "stitch": True,
                    },
                },
                headers=headers,
                timeout=30,
            )
            talk_response.raise_for_status()
            talk_id = talk_response.json().get("id")
            self.logger.debug(f"Talk created: {talk_id}")

            # Step 4: Poll for completion
            self.logger.debug("Polling for talk completion...")
            max_polls = 60  # 5 minutes max (5s * 60)
            poll_interval = 5  # seconds
            
            for poll_count in range(max_polls):
                status_response = requests.get(
                    f"{self.api_url}/talks/{talk_id}",
                    headers=headers,
                    timeout=30,
                )
                status_response.raise_for_status()
                status_data = status_response.json()
                status = status_data.get("status")
                
                if status == "done":
                    result_url = status_data.get("result_url")
                    if not result_url:
                        raise Exception("Talk completed but no result_url found")
                    self.logger.debug(f"Talk completed: {result_url}")
                    break
                elif status == "error":
                    error_msg = status_data.get("error", "Unknown error")
                    raise Exception(f"D-ID talk failed: {error_msg}")
                
                if poll_count < max_polls - 1:
                    time.sleep(poll_interval)
                    self.logger.debug(f"Talk status: {status}, waiting {poll_interval}s...")
            else:
                raise Exception(f"Talk did not complete within {max_polls * poll_interval} seconds")

            # Step 5: Download result
            self.logger.debug("Downloading result video...")
            video_response = requests.get(result_url, timeout=120)
            video_response.raise_for_status()
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(video_response.content)
            
            # Step 6: Ensure duration matches audio (trim/pad if needed)
            self._align_duration(output_path, audio_path)
            
            self.logger.info(f"✅ D-ID lip-sync video generated: {output_path}")
            return output_path

        except requests.exceptions.RequestException as e:
            error_msg = f"D-ID API error: {e}"
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_body = e.response.json()
                    error_msg += f" - {error_body}"
                except:
                    error_msg += f" - Status: {e.response.status_code}"
            self.logger.error(error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            self.logger.error(f"D-ID generation failed: {e}")
            raise

    def _align_duration(self, video_path: Path, audio_path: Path) -> None:
        """
        Ensure video duration matches audio duration (trim or pad if needed).

        Args:
            video_path: Path to video file
            audio_path: Path to audio file
        """
        try:
            audio_clip = AudioFileClip(str(audio_path))
            audio_duration = audio_clip.duration
            audio_clip.close()

            video_clip = VideoFileClip(str(video_path))
            video_duration = video_clip.duration

            # If durations differ by more than 0.1s, adjust
            if abs(video_duration - audio_duration) > 0.1:
                self.logger.debug(
                    f"Aligning durations: video={video_duration:.2f}s, audio={audio_duration:.2f}s"
                )
                
                if video_duration > audio_duration:
                    # Trim video to match audio
                    trimmed = video_clip.subclip(0, audio_duration)
                    trimmed.write_videofile(
                        str(video_path),
                        codec="libx264",
                        audio_codec="aac",
                        fps=24,
                        preset="medium",
                        logger=None,
                    )
                    trimmed.close()
                else:
                    # Pad video with last frame to match audio
                    last_frame = video_clip.get_frame(video_clip.duration - 0.1)
                    from moviepy.video.VideoClip import ImageClip
                    from moviepy.video.fx import freeze
                    
                    padding_duration = audio_duration - video_duration
                    padding = ImageClip(last_frame).set_duration(padding_duration)
                    final = video_clip.concatenate_videoclips([video_clip, padding])
                    final.write_videofile(
                        str(video_path),
                        codec="libx264",
                        audio_codec="aac",
                        fps=24,
                        preset="medium",
                        logger=None,
                    )
                    final.close()
            
            video_clip.close()
        except Exception as e:
            self.logger.warning(f"Duration alignment failed (non-critical): {e}")


class HeyGenLipSyncProvider(LipSyncProvider):
    """HeyGen API provider for lip-sync talking-head generation."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize HeyGen provider.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        super().__init__(settings, logger)
        # Support both new LIPSYNC_API_KEY and legacy HEYGEN_API_KEY
        self.api_key = getattr(settings, "lipsync_api_key", None) or getattr(settings, "heygen_api_key", None)
        self.api_url = getattr(settings, "heygen_api_url", "https://api.heygen.com")
        
        if not self.api_key:
            self.logger.warning("HeyGen API key not configured. Lip-sync will not work.")

    def generate_talking_head(
        self, base_image_path: Path, audio_path: Path, output_path: Path
    ) -> Path:
        """
        Generate talking-head using HeyGen API.

        Args:
            base_image_path: Path to character's base face image
            audio_path: Path to dialogue audio file
            output_path: Path to save output video clip

        Returns:
            Path to generated video clip

        Raises:
            ValueError: If API key not configured
            Exception: If API call fails
        """
        if not self.api_key:
            raise ValueError("HeyGen API key not configured. Set HEYGEN_API_KEY in .env")

        self.logger.info(f"Generating lip-sync talking-head via HeyGen API...")
        self.logger.info(f"  Image: {base_image_path.name}")
        self.logger.info(f"  Audio: {audio_path.name}")

        headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

        try:
            # Step 1: Upload image
            self.logger.debug("Uploading image to HeyGen...")
            with open(base_image_path, "rb") as img_file:
                files = {"file": (base_image_path.name, img_file, "image/png")}
                upload_headers = {"X-Api-Key": self.api_key}
                image_response = requests.post(
                    f"{self.api_url}/v1/upload",
                    files=files,
                    headers=upload_headers,
                    timeout=30,
                )
            image_response.raise_for_status()
            image_url = image_response.json().get("data", {}).get("url")
            if not image_url:
                raise Exception("HeyGen image upload failed: no URL returned")
            self.logger.debug(f"Image uploaded: {image_url}")

            # Step 2: Upload audio
            self.logger.debug("Uploading audio to HeyGen...")
            with open(audio_path, "rb") as audio_file:
                files = {"file": (audio_path.name, audio_file, "audio/mpeg")}
                upload_headers = {"X-Api-Key": self.api_key}
                audio_response = requests.post(
                    f"{self.api_url}/v1/upload",
                    files=files,
                    headers=upload_headers,
                    timeout=30,
                )
            audio_response.raise_for_status()
            audio_url = audio_response.json().get("data", {}).get("url")
            if not audio_url:
                raise Exception("HeyGen audio upload failed: no URL returned")
            self.logger.debug(f"Audio uploaded: {audio_url}")

            # Step 3: Create video task
            self.logger.debug("Creating HeyGen video task...")
            task_response = requests.post(
                f"{self.api_url}/v1/video/generate",
                json={
                    "video_input_config": {
                        "image_url": image_url,
                    },
                    "audio_url": audio_url,
                    "dimension": {
                        "width": 1080,
                        "height": 1920,
                    },
                },
                headers=headers,
                timeout=30,
            )
            task_response.raise_for_status()
            task_id = task_response.json().get("data", {}).get("video_id")
            if not task_id:
                raise Exception("HeyGen task creation failed: no video_id returned")
            self.logger.debug(f"Video task created: {task_id}")

            # Step 4: Poll for completion
            self.logger.debug("Polling for video completion...")
            max_polls = 60  # 5 minutes max (5s * 60)
            poll_interval = 5  # seconds
            
            for poll_count in range(max_polls):
                status_response = requests.get(
                    f"{self.api_url}/v1/video_status.get?video_id={task_id}",
                    headers=headers,
                    timeout=30,
                )
                status_response.raise_for_status()
                status_data = status_response.json().get("data", {})
                status = status_data.get("status")
                
                if status == "completed":
                    result_url = status_data.get("video_url")
                    if not result_url:
                        raise Exception("Video completed but no video_url found")
                    self.logger.debug(f"Video completed: {result_url}")
                    break
                elif status == "failed":
                    error_msg = status_data.get("error", "Unknown error")
                    raise Exception(f"HeyGen video generation failed: {error_msg}")
                
                if poll_count < max_polls - 1:
                    time.sleep(poll_interval)
                    self.logger.debug(f"Video status: {status}, waiting {poll_interval}s...")
            else:
                raise Exception(f"Video did not complete within {max_polls * poll_interval} seconds")

            # Step 5: Download result
            self.logger.debug("Downloading result video...")
            video_response = requests.get(result_url, timeout=120)
            video_response.raise_for_status()
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(video_response.content)
            
            # Step 6: Ensure duration matches audio (trim/pad if needed)
            self._align_duration(output_path, audio_path)
            
            self.logger.info(f"✅ HeyGen lip-sync video generated: {output_path}")
            return output_path

        except requests.exceptions.RequestException as e:
            error_msg = f"HeyGen API error: {e}"
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_body = e.response.json()
                    error_msg += f" - {error_body}"
                except:
                    error_msg += f" - Status: {e.response.status_code}"
            self.logger.error(error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            self.logger.error(f"HeyGen generation failed: {e}")
            raise

    def _align_duration(self, video_path: Path, audio_path: Path) -> None:
        """
        Ensure video duration matches audio duration (trim or pad if needed).

        Args:
            video_path: Path to video file
            audio_path: Path to audio file
        """
        try:
            audio_clip = AudioFileClip(str(audio_path))
            audio_duration = audio_clip.duration
            audio_clip.close()

            video_clip = VideoFileClip(str(video_path))
            video_duration = video_clip.duration

            # If durations differ by more than 0.1s, adjust
            if abs(video_duration - audio_duration) > 0.1:
                self.logger.debug(
                    f"Aligning durations: video={video_duration:.2f}s, audio={audio_duration:.2f}s"
                )
                
                if video_duration > audio_duration:
                    # Trim video to match audio
                    trimmed = video_clip.subclip(0, audio_duration)
                    trimmed.write_videofile(
                        str(video_path),
                        codec="libx264",
                        audio_codec="aac",
                        fps=24,
                        preset="medium",
                        logger=None,
                    )
                    trimmed.close()
                else:
                    # Pad video with last frame to match audio
                    last_frame = video_clip.get_frame(video_clip.duration - 0.1)
                    from moviepy.video.VideoClip import ImageClip
                    
                    padding_duration = audio_duration - video_duration
                    padding = ImageClip(last_frame).set_duration(padding_duration)
                    final = video_clip.concatenate_videoclips([video_clip, padding])
                    final.write_videofile(
                        str(video_path),
                        codec="libx264",
                        audio_codec="aac",
                        fps=24,
                        preset="medium",
                        logger=None,
                    )
                    final.close()
            
            video_clip.close()
        except Exception as e:
            self.logger.warning(f"Duration alignment failed (non-critical): {e}")


def get_lipsync_provider(settings: Settings, logger: Any) -> Optional[LipSyncProvider]:
    """
    Get the configured lip-sync provider, if available.

    Priority (new config):
    1. Use LIPSYNC_PROVIDER setting if LIPSYNC_ENABLED is true
    2. Fall back to legacy detection (DID_API_KEY or HEYGEN_API_KEY)
    3. None (fallback to basic talking-head)

    Args:
        settings: Application settings
        logger: Logger instance

    Returns:
        LipSyncProvider instance or None if none configured
    """
    # Check if lip-sync is enabled
    lipsync_enabled = getattr(settings, "lipsync_enabled", False) or getattr(settings, "use_lipsync", False)
    if not lipsync_enabled:
        logger.debug("Lip-sync is disabled in settings")
        return None

    # Get provider preference
    provider_name = getattr(settings, "lipsync_provider", "none").lower()
    
    # Support both new LIPSYNC_API_KEY and legacy keys
    lipsync_api_key = getattr(settings, "lipsync_api_key", None)
    did_api_key = getattr(settings, "did_api_key", None)
    heygen_api_key = getattr(settings, "heygen_api_key", None)

    # Try to select provider based on LIPSYNC_PROVIDER setting
    if provider_name == "did":
        api_key = lipsync_api_key or did_api_key
        if api_key:
            logger.info("Using D-ID for lip-sync (configured via LIPSYNC_PROVIDER)")
            provider = DIDLipSyncProvider(settings, logger)
            # Temporarily set the API key if using LIPSYNC_API_KEY
            if lipsync_api_key and not did_api_key:
                provider.api_key = lipsync_api_key
            return provider
        else:
            logger.warning("LIPSYNC_PROVIDER=did but no API key found (check LIPSYNC_API_KEY or DID_API_KEY)")
    
    elif provider_name == "heygen":
        api_key = lipsync_api_key or heygen_api_key
        if api_key:
            logger.info("Using HeyGen for lip-sync (configured via LIPSYNC_PROVIDER)")
            provider = HeyGenLipSyncProvider(settings, logger)
            # Temporarily set the API key if using LIPSYNC_API_KEY
            if lipsync_api_key and not heygen_api_key:
                provider.api_key = lipsync_api_key
            return provider
        else:
            logger.warning("LIPSYNC_PROVIDER=heygen but no API key found (check LIPSYNC_API_KEY or HEYGEN_API_KEY)")
    
    # Fall back to legacy detection (for backward compatibility)
    if did_api_key:
        logger.info("Using D-ID for lip-sync (detected from DID_API_KEY)")
        return DIDLipSyncProvider(settings, logger)
    
    if heygen_api_key:
        logger.info("Using HeyGen for lip-sync (detected from HEYGEN_API_KEY)")
        return HeyGenLipSyncProvider(settings, logger)
    
    # No provider configured
    logger.debug("No lip-sync provider configured")
    return None

