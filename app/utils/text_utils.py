"""Text utility functions for story processing."""

# This module is part of app.utils package


def estimate_spoken_duration(text: str, words_per_minute: int = 150) -> int:
    """
    Estimate the spoken duration of text in seconds.

    Args:
        text: Text to estimate duration for.
        words_per_minute: Average speaking rate (default 150 WPM).

    Returns:
        Estimated duration in seconds.
    """
    word_count = len(text.split())
    minutes = word_count / words_per_minute
    seconds = int(minutes * 60)
    return seconds


def truncate_to_target_duration(text: str, target_seconds: int, words_per_minute: int = 150) -> str:
    """
    Truncate text to approximately match a target spoken duration.

    Args:
        text: Text to truncate.
        target_seconds: Target duration in seconds.
        words_per_minute: Average speaking rate (default 150 WPM).

    Returns:
        Truncated text that should be close to target duration.
    """
    target_words = int((target_seconds / 60) * words_per_minute)
    words = text.split()
    if len(words) <= target_words:
        return text
    # Truncate to target word count, trying to end at sentence boundary
    truncated_words = words[:target_words]
    truncated_text = " ".join(truncated_words)
    # Try to find last sentence boundary
    last_period = truncated_text.rfind(".")
    last_exclamation = truncated_text.rfind("!")
    last_question = truncated_text.rfind("?")
    last_boundary = max(last_period, last_exclamation, last_question)
    if last_boundary > len(truncated_text) * 0.7:  # Only use if not too early
        truncated_text = truncated_text[: last_boundary + 1]
    return truncated_text

