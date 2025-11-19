"""I/O utility functions for file and directory operations."""

# This module is part of app.utils package

import re
from datetime import datetime
from pathlib import Path


def slugify(text: str) -> str:
    """
    Convert text to a filesystem-safe slug.

    Args:
        text: Input text to slugify.

    Returns:
        Filesystem-safe slug string.
    """
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and special characters with hyphens
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    # Remove leading/trailing hyphens
    text = text.strip("-")
    # Limit length
    if len(text) > 100:
        text = text[:100].rstrip("-")
    return text


def create_run_output_dir(base_dir: str, slug: str) -> Path:
    """
    Create a timestamped output directory for a story run.

    Args:
        base_dir: Base directory for outputs (e.g., "outputs").
        slug: Slugified identifier for the run (e.g., from topic or title).

    Returns:
        Path to the created directory.
    """
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    # Create directory name
    dir_name = f"{timestamp}_{slug}"
    # Create full path
    output_dir = Path(base_dir) / dir_name
    # Create directory
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

