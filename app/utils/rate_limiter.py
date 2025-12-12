"""Rate Limiter - throttles API calls to prevent hitting rate limits."""

import time
from collections import defaultdict
from threading import Lock
from typing import Optional


class RateLimiter:
    """Thread-safe rate limiter using token bucket algorithm."""

    def __init__(
        self,
        max_calls: int = 60,
        time_window: float = 60.0,
        burst_size: Optional[int] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            max_calls: Maximum number of calls allowed in time_window
            time_window: Time window in seconds (default: 60 seconds)
            burst_size: Maximum burst size (defaults to max_calls)
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.burst_size = burst_size or max_calls
        
        # Track calls per endpoint
        self.calls = defaultdict(list)
        self.lock = Lock()

    def wait_if_needed(self, endpoint: str = "default"):
        """
        Wait if rate limit would be exceeded.

        Args:
            endpoint: Endpoint identifier (for per-endpoint limiting)
        """
        with self.lock:
            now = time.time()
            calls = self.calls[endpoint]
            
            # Remove calls outside time window
            calls[:] = [call_time for call_time in calls if now - call_time < self.time_window]
            
            # Check if we're at the limit
            if len(calls) >= self.max_calls:
                # Calculate wait time (oldest call + time_window - now)
                oldest_call = calls[0]
                wait_time = (oldest_call + self.time_window) - now
                if wait_time > 0:
                    time.sleep(wait_time)
                    # Clean up again after waiting
                    now = time.time()
                    calls[:] = [call_time for call_time in calls if now - call_time < self.time_window]
            
            # Record this call
            calls.append(now)

    def can_proceed(self, endpoint: str = "default") -> bool:
        """
        Check if a call can proceed without waiting.

        Args:
            endpoint: Endpoint identifier

        Returns:
            True if call can proceed immediately
        """
        with self.lock:
            now = time.time()
            calls = self.calls[endpoint]
            
            # Remove calls outside time window
            calls[:] = [call_time for call_time in calls if now - call_time < self.time_window]
            
            return len(calls) < self.max_calls

    def reset(self, endpoint: Optional[str] = None):
        """
        Reset rate limiter for an endpoint or all endpoints.

        Args:
            endpoint: Endpoint identifier, or None for all endpoints
        """
        with self.lock:
            if endpoint:
                self.calls[endpoint] = []
            else:
                self.calls.clear()


# Global rate limiters for different APIs
_openai_limiter: Optional[RateLimiter] = None
_hf_limiter: Optional[RateLimiter] = None
_elevenlabs_limiter: Optional[RateLimiter] = None


def get_openai_limiter(max_calls: int = 60, time_window: float = 60.0) -> RateLimiter:
    """Get or create OpenAI rate limiter."""
    global _openai_limiter
    if _openai_limiter is None:
        _openai_limiter = RateLimiter(max_calls=max_calls, time_window=time_window)
    return _openai_limiter


def get_hf_limiter(max_calls: int = 30, time_window: float = 60.0) -> RateLimiter:
    """Get or create Hugging Face rate limiter."""
    global _hf_limiter
    if _hf_limiter is None:
        _hf_limiter = RateLimiter(max_calls=max_calls, time_window=time_window)
    return _hf_limiter


def get_elevenlabs_limiter(max_calls: int = 100, time_window: float = 60.0) -> RateLimiter:
    """Get or create ElevenLabs rate limiter."""
    global _elevenlabs_limiter
    if _elevenlabs_limiter is None:
        _elevenlabs_limiter = RateLimiter(max_calls=max_calls, time_window=time_window)
    return _elevenlabs_limiter

