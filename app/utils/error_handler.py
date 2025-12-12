"""Error Handler - provides user-friendly error messages and graceful degradation."""

from typing import Any, Optional


def format_error_message(
    operation: str,
    error: Exception,
    context: Optional[dict] = None,
    suggestion: Optional[str] = None,
) -> str:
    """
    Format a user-friendly error message.

    Args:
        operation: What operation was being performed (e.g., "Generating character face image")
        error: The exception that occurred
        context: Additional context (e.g., {"character_id": "judge_123", "episode_id": "ep_456"})
        suggestion: Optional suggestion for how to fix the issue

    Returns:
        Formatted error message
    """
    error_type = type(error).__name__
    error_msg = str(error)

    # Build context string
    context_str = ""
    if context:
        context_parts = [f"{k}={v}" for k, v in context.items()]
        context_str = f" ({', '.join(context_parts)})"

    # Build message
    message = f"❌ {operation} failed{context_str}\n"
    message += f"   Error: {error_type}: {error_msg}"

    if suggestion:
        message += f"\n   💡 Suggestion: {suggestion}"

    return message


def get_fallback_suggestion(service: str, error: Exception) -> Optional[str]:
    """
    Get a suggestion for how to handle a service failure.

    Args:
        service: Service name (e.g., "TTS", "Image Generation", "YouTube Upload")
        error: The exception

    Returns:
        Suggestion string or None
    """
    error_msg = str(error).lower()

    if service == "TTS":
        if "api key" in error_msg or "not configured" in error_msg:
            return "Check your TTS API key in .env file. Falling back to stub audio (silent)."
        elif "rate limit" in error_msg or "429" in error_msg:
            return "Rate limit exceeded. Wait a few minutes and try again. Video will use stub audio."
        elif "network" in error_msg or "timeout" in error_msg:
            return "Network error. Check your internet connection. Falling back to stub audio."
        else:
            return "TTS generation failed. Video will use stub audio (silent)."

    elif service == "Image Generation":
        if "api key" in error_msg or "not configured" in error_msg:
            return "Check your HF_ENDPOINT_TOKEN in .env file. Using placeholder image."
        elif "rate limit" in error_msg or "429" in error_msg:
            return "Rate limit exceeded. Wait a few minutes and try again. Using placeholder image."
        elif "503" in error_msg or "loading" in error_msg:
            return "Endpoint is loading. This is normal for cold starts. Retrying automatically..."
        elif "network" in error_msg or "timeout" in error_msg:
            return "Network error. Check your internet connection. Using placeholder image."
        else:
            return "Image generation failed. Using placeholder image. Video quality may be reduced."

    elif service == "YouTube Upload":
        if "oauth" in error_msg or "authentication" in error_msg:
            return "YouTube authentication failed. Re-run to trigger OAuth flow."
        elif "rate limit" in error_msg or "429" in error_msg:
            return "YouTube API rate limit exceeded. Wait and try again later."
        elif "network" in error_msg or "timeout" in error_msg:
            return "Network error during upload. Video is saved locally. Try uploading again later."
        else:
            return "Upload failed. Video is saved locally. Check logs for details."

    elif service == "Talking-Head Generation":
        if "not found" in error_msg or "missing" in error_msg:
            return "Character face image not found. Regenerating character assets..."
        else:
            return "Talking-head generation failed. Falling back to scene visual."

    elif service == "LLM":
        if "api key" in error_msg or "not configured" in error_msg:
            return "Check your OPENAI_API_KEY in .env file. Falling back to heuristics."
        elif "rate limit" in error_msg or "429" in error_msg:
            return "OpenAI rate limit exceeded. Wait a few minutes. Falling back to heuristics."
        elif "network" in error_msg or "timeout" in error_msg:
            return "Network error. Check your internet connection. Falling back to heuristics."
        else:
            return "LLM generation failed. Falling back to heuristics."

    return None

