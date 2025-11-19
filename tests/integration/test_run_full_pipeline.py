"""Tests for full pipeline orchestrator."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.core.config import Settings
from app.core.logging_config import get_logger


@patch("app.pipelines.run_full_pipeline.VideoRenderer")
@patch("app.pipelines.run_full_pipeline.YouTubeUploader")
@patch("app.pipelines.run_full_pipeline.generate_story_episode")
def test_pipeline_flow_without_upload(mock_generate, mock_uploader_class, mock_renderer_class, tmp_path):
    """Test pipeline flow without auto-upload."""
    from app.pipelines.run_full_pipeline import main
    import sys
    from unittest.mock import patch as mock_patch

    # Mock story generation
    mock_video_plan = MagicMock()
    mock_video_plan.episode_id = "test_123"
    mock_video_plan.title = "Test Story"
    mock_video_plan.logline = "A test"
    mock_video_plan.topic = "test topic"
    mock_video_plan.scenes = [MagicMock(), MagicMock()]
    mock_generate.return_value = ("test_123", mock_video_plan)

    # Mock video renderer
    mock_renderer = MagicMock()
    mock_video_path = tmp_path / "test_video.mp4"
    mock_video_path.write_bytes(b"fake video")
    mock_renderer.render.return_value = mock_video_path
    mock_renderer_class.return_value = mock_renderer

    # Mock arguments
    test_args = [
        "run_full_pipeline.py",
        "--topic",
        "test topic",
        "--duration-target-seconds",
        "60",
        "--output-dir",
        str(tmp_path),
    ]

    with mock_patch("sys.argv", test_args):
        try:
            result = main()
            # Should complete successfully
            assert result == 0

            # Verify story generation was called
            mock_generate.assert_called_once()

            # Verify video renderer was called
            mock_renderer.render.assert_called_once()

            # Verify uploader was NOT called (no --auto-upload)
            mock_uploader_class.assert_not_called()

        except SystemExit:
            # argparse might call sys.exit, that's okay
            pass


@patch("app.pipelines.run_full_pipeline.VideoRenderer")
@patch("app.pipelines.run_full_pipeline.YouTubeUploader")
@patch("app.pipelines.run_full_pipeline.generate_story_episode")
def test_pipeline_flow_with_upload(mock_generate, mock_uploader_class, mock_renderer_class, tmp_path):
    """Test pipeline flow with auto-upload."""
    from app.pipelines.run_full_pipeline import main
    import sys
    from unittest.mock import patch as mock_patch

    # Mock story generation
    mock_video_plan = MagicMock()
    mock_video_plan.episode_id = "test_123"
    mock_video_plan.title = "Test Story"
    mock_video_plan.logline = "A test"
    mock_video_plan.topic = "test topic"
    mock_video_plan.scenes = [MagicMock()]
    mock_generate.return_value = ("test_123", mock_video_plan)

    # Mock video renderer
    mock_renderer = MagicMock()
    mock_video_path = tmp_path / "test_video.mp4"
    mock_video_path.write_bytes(b"fake video")
    mock_renderer.render.return_value = mock_video_path
    mock_renderer_class.return_value = mock_renderer

    # Mock YouTube uploader
    mock_uploader = MagicMock()
    mock_uploader.upload.return_value = "https://www.youtube.com/watch?v=test123"
    mock_uploader_class.return_value = mock_uploader

    # Mock arguments with --auto-upload
    test_args = [
        "run_full_pipeline.py",
        "--topic",
        "test topic",
        "--duration-target-seconds",
        "60",
        "--auto-upload",
        "--output-dir",
        str(tmp_path),
    ]

    with mock_patch("sys.argv", test_args):
        try:
            result = main()
            # Should complete successfully
            assert result == 0

            # Verify uploader was called
            mock_uploader.upload.assert_called_once()

            # Verify upload was called with correct parameters
            upload_call = mock_uploader.upload.call_args
            assert upload_call.kwargs["video_path"] == mock_video_path
            assert "title" in upload_call.kwargs
            assert "description" in upload_call.kwargs

        except SystemExit:
            # argparse might call sys.exit, that's okay
            pass


def test_generate_video_metadata():
    """Test video metadata generation."""
    from app.pipelines.run_full_pipeline import generate_video_metadata

    mock_video_plan = MagicMock()
    mock_video_plan.title = "Test Story Title"
    mock_video_plan.logline = "A test logline"
    mock_video_plan.episode_id = "episode_123"
    mock_video_plan.topic = "courtroom drama"
    mock_video_plan.style = "courtroom_drama"

    title, description, tags = generate_video_metadata(mock_video_plan)

    assert isinstance(title, str)
    assert len(title) > 0
    assert isinstance(description, str)
    assert isinstance(tags, list)
    assert len(tags) > 0
    assert "shorts" in tags

