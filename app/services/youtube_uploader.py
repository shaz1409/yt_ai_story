"""YouTube Uploader - uploads videos to YouTube via Data API v3."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.config import Settings
from app.core.logging_config import get_logger


class YouTubeUploader:
    """Uploads videos to YouTube using Data API v3."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize YouTube uploader.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger
        self._youtube_service = None

    def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: Optional[list[str]] = None,
        privacy_status: str = "public",
        category_id: str = "22",  # People & Blogs
        scheduled_publish_at: Optional[datetime] = None,
    ) -> str:
        """
        Upload video to YouTube.

        Args:
            video_path: Path to video file
            title: Video title
            description: Video description
            tags: Optional list of tags
            privacy_status: Privacy status (public, unlisted, private)
            category_id: YouTube category ID (default: 22 for People & Blogs)
            scheduled_publish_at: Optional datetime for scheduled publication.
                If provided, privacy_status will be set to "private" and video will be scheduled.

        Returns:
            YouTube video ID or URL

        Raises:
            Exception: If upload fails
        """
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # If scheduling is requested, privacy must be "private"
        if scheduled_publish_at is not None:
            if privacy_status != "private":
                self.logger.warning(
                    f"Scheduled publish time provided but privacy_status is '{privacy_status}'. "
                    "Setting to 'private' (required for scheduled uploads)."
                )
            privacy_status = "private"

        self.logger.info("=" * 60)
        self.logger.info("Starting YouTube upload")
        self.logger.info(f"Video: {video_path}")
        self.logger.info(f"Title: {title}")
        self.logger.info(f"Privacy: {privacy_status}")
        if scheduled_publish_at:
            self.logger.info(f"Scheduled publish time: {scheduled_publish_at.isoformat()}")
            self.logger.info(f"Scheduled publish time (local): {scheduled_publish_at}")
        else:
            self.logger.info("Publishing immediately (no schedule)")
        self.logger.info("=" * 60)

        # Retry logic for upload
        max_retries = 3
        retry_delays = [2, 5, 10]  # seconds
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                # Sleep before retry (except first attempt)
                if attempt > 1:
                    import time
                    delay = retry_delays[min(attempt - 2, len(retry_delays) - 1)]
                    self.logger.info(f"Waiting {delay}s before retry attempt {attempt}/{max_retries}...")
                    time.sleep(delay)

                youtube = self._get_youtube_service()

                # Prepare video metadata
                status_dict = {
                    "privacyStatus": privacy_status,
                }
                
                # Add publishAt if scheduling is requested
                if scheduled_publish_at is not None:
                    # YouTube requires RFC 3339 format (ISO 8601)
                    from datetime import timezone
                    
                    if scheduled_publish_at.tzinfo is None:
                        # Naive datetime - convert to UTC and add "Z"
                        publish_at_utc = scheduled_publish_at.replace(tzinfo=timezone.utc)
                        publish_at_iso = publish_at_utc.isoformat().replace("+00:00", "Z")
                        self.logger.warning(
                            f"Scheduled publish time is timezone-naive, assuming UTC: {publish_at_iso}"
                        )
                    else:
                        # Timezone-aware datetime - use isoformat() directly (RFC3339 compatible)
                        # DO NOT add "Z" manually - isoformat() handles timezone offset correctly
                        publish_at_iso = scheduled_publish_at.isoformat()
                    
                    status_dict["publishAt"] = publish_at_iso
                    self.logger.info(f"Scheduling video for {scheduled_publish_at.isoformat()}")
                    self.logger.info(f"Setting publishAt to: {publish_at_iso}")
                
                body = {
                    "snippet": {
                        "title": title,
                        "description": description,
                        "tags": tags or [],
                        "categoryId": category_id,
                    },
                    "status": status_dict,
                }

                # Upload video
                if attempt > 1:
                    self.logger.info(f"Retry attempt {attempt}/{max_retries} for YouTube upload...")
                else:
                    self.logger.info("Uploading video to YouTube...")
                
                # Import MediaFileUpload for file upload
                from googleapiclient.http import MediaFileUpload
                
                insert_request = youtube.videos().insert(
                    part=",".join(body.keys()),
                    body=body,
                    media_body=MediaFileUpload(str(video_path), chunksize=-1, resumable=True),
                )

                response = self._resumable_upload(insert_request)

                video_id = response["id"]
                video_url = f"https://www.youtube.com/watch?v={video_id}"

                self.logger.info("=" * 60)
                self.logger.info("YouTube upload complete!")
                self.logger.info(f"Video ID: {video_id}")
                self.logger.info(f"Video URL: {video_url}")
                
                # Log scheduling confirmation
                if scheduled_publish_at is not None:
                    # Check if publishAt was accepted in response
                    if "status" in response and "publishAt" in response["status"]:
                        confirmed_publish_at = response["status"]["publishAt"]
                        self.logger.info(f"✅ Scheduled publish confirmed: {confirmed_publish_at}")
                        self.logger.info(f"   Video will be published at: {scheduled_publish_at}")
                    else:
                        self.logger.warning(
                            "⚠️  Scheduled publish time provided but not found in API response. "
                            "Check YouTube Studio to verify scheduling."
                        )
                else:
                    self.logger.info("Video published immediately (public)")
                
                self.logger.info("=" * 60)

                return video_url

            except Exception as e:
                last_error = e
                self.logger.warning(f"YouTube upload attempt {attempt}/{max_retries} failed: {e}")
                if attempt < max_retries:
                    continue
                else:
                    self.logger.error(f"YouTube upload failed after {max_retries} attempts: {e}", exc_info=True)
                    raise

    def _get_youtube_service(self):
        """Get authenticated YouTube service."""
        if self._youtube_service:
            return self._youtube_service

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError:
            raise ImportError(
                "Google API libraries not installed. Install with: "
                "pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
            )

        creds = None
        token_file = Path(self.settings.youtube_token_file or "youtube_token.json")

        # Load existing token
        if token_file.exists():
            self.logger.info(f"Loading YouTube token from: {token_file}")
            creds = Credentials.from_authorized_user_file(str(token_file), self.settings.youtube_api_scopes)

        # If no valid credentials, run OAuth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                self.logger.info("Refreshing YouTube token...")
                creds.refresh(Request())
            else:
                self.logger.info("Starting YouTube OAuth flow...")
                if not self.settings.youtube_client_secrets_file:
                    raise ValueError(
                        "YouTube client secrets file not configured. "
                        "Set YOUTUBE_CLIENT_SECRETS_FILE in .env or config."
                    )

                secrets_file = Path(self.settings.youtube_client_secrets_file)
                if not secrets_file.exists():
                    raise FileNotFoundError(
                        f"YouTube client secrets file not found: {secrets_file}. "
                        "Download from https://console.cloud.google.com/apis/credentials"
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    str(secrets_file), self.settings.youtube_api_scopes
                )
                creds = flow.run_local_server(port=0)

            # Save token for future use
            self.logger.info(f"Saving YouTube token to: {token_file}")
            token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(token_file, "w") as token:
                token.write(creds.to_json())

        # Build YouTube service
        self._youtube_service = build("youtube", "v3", credentials=creds)
        return self._youtube_service

    def _resumable_upload(self, insert_request):
        """
        Execute resumable upload with progress logging.

        Args:
            insert_request: YouTube API insert request

        Returns:
            API response
        """
        response = None
        error = None
        retry = 0
        max_retries = 10

        while response is None:
            try:
                self.logger.info("Uploading file...")
                status, response = insert_request.next_chunk()
                if response is not None:
                    if "id" in response:
                        self.logger.info(f"Upload successful! Video ID: {response['id']}")
                    else:
                        raise Exception(f"Upload failed: {response}")
                elif status:
                    progress = int(status.progress() * 100)
                    self.logger.info(f"Upload progress: {progress}%")
            except Exception as e:
                if retry < max_retries:
                    self.logger.warning(f"Upload error (retry {retry + 1}/{max_retries}): {e}")
                    retry += 1
                else:
                    error = e
                    break

        if error:
            raise error

        return response

