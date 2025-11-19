"""Logging configuration for the YouTube story generator."""

import sys
from pathlib import Path
from typing import Optional

from loguru import logger


def get_logger(name: str, log_file: Optional[Path] = None) -> "logger":
    """
    Get a configured logger instance.

    Args:
        name: Name of the logger (typically __name__ or module name).
        log_file: Optional path to log file. If None, uses outputs/latest_run.log.

    Returns:
        Configured logger instance.
    """
    # Remove default handler
    logger.remove()

    # Console handler with formatting
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True,
    )

    # File handler
    if log_file is None:
        # Ensure outputs directory exists
        output_dir = Path("outputs")
        output_dir.mkdir(exist_ok=True)
        log_file = output_dir / "latest_run.log"

    # Ensure log file directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="INFO",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
    )

    return logger.bind(name=name)

