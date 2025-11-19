"""Shared pytest fixtures and configuration."""

import pytest

from app.core.config import Settings
from app.core.logging_config import get_logger


@pytest.fixture
def settings():
    """Create test settings instance."""
    return Settings()


@pytest.fixture
def logger():
    """Create test logger instance."""
    return get_logger(__name__)

