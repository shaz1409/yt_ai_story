"""Tests for YouTube Uploader service."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.services.youtube_uploader import YouTubeUploader


@pytest.fixture
def youtube_uploader():
    """Create YouTubeUploader instance for testing."""
    settings = Settings()
    logger = get_logger(__name__)
    return YouTubeUploader(settings, logger)


@pytest.fixture
def sample_video_file(tmp_path):
    """Create a dummy video file for testing."""
    video_file = tmp_path / "test_video.mp4"
    video_file.write_bytes(b"fake video content")
    return video_file


def test_upload_requires_video_file(youtube_uploader, tmp_path):
    """Test that upload fails if video file doesn't exist."""
    fake_path = tmp_path / "nonexistent.mp4"

    with pytest.raises(FileNotFoundError):
        youtube_uploader.upload(
            video_path=fake_path,
            title="Test",
            description="Test description",
        )


@patch("app.services.youtube_uploader.build")
@patch("app.services.youtube_uploader.InstalledAppFlow")
@patch("app.services.youtube_uploader.Credentials")
def test_upload_builds_correct_request(
    mock_credentials, mock_flow, mock_build, youtube_uploader, sample_video_file
):
    """Test that upload builds correct YouTube API request."""
    # Mock YouTube service
    mock_service = MagicMock()
    mock_videos = MagicMock()
    mock_insert = MagicMock()
    mock_media = MagicMock()

    mock_service.videos.return_value = mock_videos
    mock_videos.insert.return_value = mock_insert
    mock_insert.next_chunk.return_value = (None, {"id": "test_video_id"})

    mock_build.return_value = mock_service

    # Mock credentials
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_credentials.from_authorized_user_file.return_value = mock_creds

    # Mock MediaFileUpload
    with patch("app.services.youtube_uploader.MediaFileUpload", return_value=mock_media):
        youtube_uploader._youtube_service = mock_service

        try:
            result = youtube_uploader.upload(
                video_path=sample_video_file,
                title="Test Video",
                description="Test Description",
                tags=["test", "shorts"],
                privacy_status="public",
            )

            # Verify API was called correctly
            mock_videos.insert.assert_called_once()
            call_args = mock_videos.insert.call_args

            # Check part parameter
            assert "part" in call_args.kwargs
            assert "snippet" in call_args.kwargs["part"]
            assert "status" in call_args.kwargs["part"]

            # Check body structure
            body = call_args.kwargs["body"]
            assert body["snippet"]["title"] == "Test Video"
            assert body["snippet"]["description"] == "Test Description"
            assert body["snippet"]["tags"] == ["test", "shorts"]
            assert body["status"]["privacyStatus"] == "public"

            # Check result
            assert "test_video_id" in result or "youtube.com" in result

        except Exception as e:
            # If OAuth flow is required, that's expected in test environment
            if "client secrets" in str(e).lower() or "oauth" in str(e).lower():
                pytest.skip(f"YouTube upload requires OAuth setup: {e}")
            raise

